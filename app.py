"""
app.py - Smart Meter Dashboard Backend
------------------------------------------
Combines the two project pieces into one live system:

  PART A (circuit simulation, e.g. Wokwi) -> POSTs live readings here
  PART B (trained ML model)                -> runs 1-hour-ahead prediction
  DASHBOARD (browser)                      -> polls /latest and displays both

Endpoints:
  POST /ingest   - receives a new reading from the ESP32 (real or simulated)
  GET  /latest   - returns the most recent reading + ML prediction (for dashboard polling)
  GET  /history  - returns recent readings (for the live chart)
  GET  /         - serves the dashboard HTML page

Run with:  python app.py
Then open: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, session, url_for
from collections import deque
from datetime import datetime, timedelta
import joblib
import os
import users
import email_alert
import gemini_recommend

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this-in-production")

# ---------- Load trained model ----------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "trained_model.pkl")
THRESHOLD_PATH = os.path.join(os.path.dirname(__file__), "peak_threshold.txt")

bundle = joblib.load(MODEL_PATH)
model = bundle["model"]
FEATURES = bundle["features"]
TARGET = bundle["target"]
HORIZON_MIN = bundle["horizon_minutes"]

with open(THRESHOLD_PATH) as f:
    PEAK_THRESHOLD = float(f.read())

# ---------- In-memory rolling history (last 200 readings) ----------
history = deque(maxlen=200)
last_was_peak = False  # tracks state so we email only when a peak STARTS, not every reading


# Recommendation logic now lives in gemini_recommend.py
# (calls Gemini API for a situation-specific recommendation, with an
# automatic rule-based fallback if the API key isn't configured or fails)


@app.route("/ingest", methods=["POST"])
def ingest():
    """
    Receives a live reading. Expected JSON body:
    {
      "Voltage": 230.5, "Current": 1.2, "Power": 276.6, "Energy": 0.069,
      "Hour": 19, "Day": 8, "Month": 8, "Is_Weekend": 0,
      "Temperature": 31.5, "Humidity": 60,
      "Disturbance": "NORMAL"   <-- optional, from the Part A circuit sim
    }
    """
    data = request.get_json(force=True)
    now = datetime.now()

    # Build lag features from history (last 4 power readings)
    recent_powers = [h["Power"] for h in list(history)[-4:]]
    while len(recent_powers) < 4:
        recent_powers.insert(0, data.get("Power", 0))

    row = {
        "Voltage": data.get("Voltage", 230),
        "Hour": data.get("Hour", now.hour),
        "Day": data.get("Day", now.day),
        "Month": data.get("Month", now.month),
        "Is_Weekend": data.get("Is_Weekend", 1 if now.weekday() >= 5 else 0),
        "Temperature": data.get("Temperature", 28),
        "Humidity": data.get("Humidity", 60),
        "Power": data.get("Power", 0),
        "Power_Lag1": recent_powers[-1],
        "Power_Lag2": recent_powers[-2],
        "Power_Lag3": recent_powers[-3],
        "Power_Lag4": recent_powers[-4],
    }

    X_live = [[row[f] for f in FEATURES]]
    predicted_power = float(model.predict(X_live)[0])
    predicted_time = (now + timedelta(minutes=HORIZON_MIN)).strftime("%H:%M:%S")
    is_peak = predicted_power >= PEAK_THRESHOLD

    reason, tip = ("", "")
    if is_peak:
        disturbance = data.get("Disturbance", "NORMAL")
        reason, tip = gemini_recommend.get_recommendation(row, predicted_power, disturbance)

    record = {
        "timestamp": now.strftime("%H:%M:%S"),
        "Voltage": row["Voltage"],
        "Current": data.get("Current", 0),
        "Power": row["Power"],
        "Energy": data.get("Energy", 0),
        "Temperature": row["Temperature"],
        "Humidity": row["Humidity"],
        "Disturbance": data.get("Disturbance", "NORMAL"),
        "device_hour": row["Hour"],
        "device_day": row["Day"],
        "device_month": row["Month"],
        "device_is_weekend": row["Is_Weekend"],
        "predicted_power": round(predicted_power, 1),
        "predicted_time": predicted_time,
        "is_peak": is_peak,
        "reason": reason,
        "tip": tip,
    }

    history.append(record)

    # ---------- Email alert: only when a peak STARTS (edge trigger) ----------
    global last_was_peak
    if is_peak and not last_was_peak:
        recipients = users.get_all_emails()
        email_alert.send_peak_alert(recipients, record["predicted_power"],
                                     record["predicted_time"], reason, tip)
    last_was_peak = is_peak

    return jsonify({"status": "ok", "record": record})


@app.route("/latest", methods=["GET"])
def latest():
    if not history:
        return jsonify({"status": "empty"})
    return jsonify({"status": "ok", "record": history[-1]})


@app.route("/history", methods=["GET"])
def get_history():
    return jsonify({"status": "ok", "records": list(history)})


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None)

    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not phone or not email or not password:
        return render_template("signup.html", error="All fields are required.")

    ok, message = users.create_user(phone, password, email)
    if not ok:
        return render_template("signup.html", error=message)

    session["phone"] = phone
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")

    if users.verify_user(phone, password):
        session["phone"] = phone
        return redirect(url_for("dashboard"))

    return render_template("login.html", error="Invalid phone number or password.")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/history-page")
def history_page():
    if "phone" not in session:
        return redirect(url_for("login"))
    return send_from_directory(os.path.dirname(__file__), "history.html")


@app.route("/")
def dashboard():
    if "phone" not in session:
        return redirect(url_for("login"))
    return send_from_directory(os.path.dirname(__file__), "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
