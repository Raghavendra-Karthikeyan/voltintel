# Smart Meter Dashboard — Backend

Connects your two project pieces into one live system:
  - Circuit simulation (Wokwi) sends readings here
  - Trained ML model predicts peak consumption 1 hour ahead
  - Dashboard displays both, live, in your browser

## Files
- `app.py` — Flask backend (API + serves the dashboard)
- `dashboard.html` — the live dashboard page (oscilloscope-style dark UI)
- `trained_model.pkl` — your trained Random Forest model (from Step 2)
- `peak_threshold.txt` — the peak threshold value

## Setup

```bash
pip install flask joblib pandas numpy scikit-learn
python app.py
```

Then open **http://localhost:5000** in your browser — you'll see the live dashboard (empty until data is sent).

## Test it without Wokwi first

In a second terminal, send a fake reading to confirm everything works:

```bash
curl -X POST http://localhost:5000/ingest -H "Content-Type: application/json" -d "{\"Voltage\": 231.2, \"Current\": 1.8, \"Power\": 416.2, \"Energy\": 0.104, \"Hour\": 19, \"Day\": 8, \"Month\": 8, \"Is_Weekend\": 0, \"Temperature\": 33.5, \"Humidity\": 55, \"Disturbance\": \"NORMAL\"}"
```

Refresh the dashboard — you should see the voltage/power values and a prediction appear.

## Connecting Wokwi to this backend

Your ESP32 code needs to send an HTTP POST to `/ingest` every time it takes a reading. Since Wokwi runs in the cloud, it can't reach `localhost` on your PC directly — you need to either:

1. **Use ngrok** (easiest for a demo): run `ngrok http 5000` on your PC, it gives you a public URL like `https://abc123.ngrok.io` — use that as the target URL in your ESP32 code instead of localhost.
2. **Deploy this backend to a free host** (Render, Railway, PythonAnywhere) — gives you a permanent public URL.

Once you have a public URL, the ESP32 code needs to POST JSON like this to `<your-url>/ingest`:
```json
{
  "Voltage": 230.5, "Current": 1.2, "Power": 276.6, "Energy": 0.069,
  "Hour": 19, "Day": 8, "Month": 8, "Is_Weekend": 0,
  "Temperature": 31.5, "Humidity": 60, "Disturbance": "NORMAL"
}
```

Ask Claude for the exact Wokwi/ESP32 WiFi + HTTP POST code when you're ready for this step.

## Endpoints

- `POST /ingest` — submit a new reading, returns the reading + ML prediction
- `GET /latest` — most recent reading + prediction (dashboard polls this every 1s)
- `GET /history` — last 200 readings (for the chart)
- `GET /` — the dashboard page itself
