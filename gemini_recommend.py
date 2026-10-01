"""
gemini_recommend.py - AI-generated peak-consumption recommendations
------------------------------------------------------------------------
Calls the Gemini REST API directly (no SDK).
Uses gemini-3.6-flash which is the model available for new API keys.
Falls back to rule-based logic automatically if the API fails.
"""

print("[gemini_recommend] FILE VERSION LOADED: v6-gemini36-2026-08-19")

import os
import json
import re
import requests

API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"


def _rule_based_fallback(row, predicted_power, disturbance):
    """Rule-based fallback, used if Gemini is unavailable or fails."""
    reasons = []
    tips = []

    if row.get("Temperature", 25) >= 32:
        reasons.append("high temperature (likely AC/cooling load)")
        tips.append("pre-cool the room earlier, or raise the AC setpoint by 1-2C during this window")
    if 18 <= row.get("Hour", 12) <= 21:
        reasons.append("evening peak hours (typical high-usage window)")
        tips.append("stagger high-power appliances outside 6-9 PM")
    if row.get("Is_Weekend", 0) == 1:
        reasons.append("weekend usage pattern")
        tips.append("shift non-urgent heavy appliance use to off-peak hours")
    if predicted_power - row.get("Power", 0) > 50:
        reasons.append("rapid upward trend in recent consumption")
        tips.append("check if a high-draw appliance was just switched on")
    if disturbance and disturbance != "NORMAL":
        reasons.append(f"active power quality disturbance detected ({disturbance})")
        tips.append("inspect connected equipment for faults or non-linear loads")

    if not reasons:
        reasons.append("gradual load increase based on recent trend")
        tips.append("monitor and avoid starting new heavy appliances")

    return "; ".join(reasons), "; ".join(tips)


def _is_garbage(text):
    """Return True if the response looks like a prompt echo or garbage."""
    garbage_patterns = [
        "with NO other text",
        "no markdown",
        "no extra text",
        "fill in the",
        "return only",
        "reply with only",
    ]
    lower = text.lower()
    if len(text) < 5:
        return True
    if any(p in lower for p in garbage_patterns):
        return True
    # Starts/ends with partial JSON artifact with no real content
    if text.strip() in ('"}', '{', '}', '{"', '"}'):
        return True
    return False


def _extract_json_ish(text):
    """Extract reason+tip from any model output format (JSON, arrow, or plain text)."""
    text = text.strip()

    # Strip markdown code fences
    if "```" in text:
        text = re.sub(r"```[a-z]*", "", text).replace("```", "").strip()

    if _is_garbage(text):
        return None

    # 1. Try standard full JSON parse
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            parsed = json.loads(text[start:end + 1])
            if parsed.get("reason") and parsed.get("tip"):
                return parsed
        except Exception:
            pass

    # 2. Regex extraction — works on both full and TRUNCATED JSON
    reason_match = re.search(r'"reason"\s*:\s*"([^"]{5,})"', text)
    tip_match = re.search(r'"tip"\s*:\s*"([^"]{5,})"', text)
    if reason_match:
        reason = reason_match.group(1).strip()
        tip = tip_match.group(1).strip() if tip_match else "Monitor and reduce high-draw appliances."
        return {"reason": reason, "tip": tip}

    # 3. Arrow-separated format: REASON -> TIP
    if "->" in text:
        parts = text.split("->", 1)
        reason = parts[0].strip().strip('"').strip()
        tip = parts[1].strip().strip('"').strip()
        if len(reason) > 5 and len(tip) > 5:
            return {"reason": reason, "tip": tip}

    # 4. Period-separated sentences (first = reason, rest = tip)
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 5]
    if len(sentences) >= 2:
        return {"reason": sentences[0], "tip": ". ".join(sentences[1:])}

    # 5. Use the whole text as reason only if it looks meaningful
    if len(text) > 10 and not text.startswith(("{", "}")):
        return {"reason": text[:100].strip(), "tip": "Monitor and reduce high-draw appliances."}

    return None




def get_recommendation(row, predicted_power, disturbance="NORMAL"):
    """Returns (reason, tip) strings. Tries Gemini first, falls back on any failure."""
    if not API_KEY or API_KEY.startswith("PASTE_") or API_KEY.startswith("YOUR_"):
        print("[gemini_recommend] No API key configured, using rule-based fallback.")
        return _rule_based_fallback(row, predicted_power, disturbance)

    prompt = (
        "Smart home energy data:\n"
        f"- Power now: {row.get('Power','N/A')} W\n"
        f"- Predicted power in 1 hour: {round(predicted_power, 1)} W\n"
        f"- Temperature: {row.get('Temperature','N/A')} C\n"
        f"- Hour of day: {row.get('Hour','N/A')}\n"
        f"- Disturbance: {disturbance}\n\n"
        "Task: Identify the most likely cause of this predicted peak and give one short action.\n"
        "Return a JSON object with exactly two keys:\n"
        "1) 'reason': A short string explaining the likely cause.\n"
        "2) 'tip': A short string giving an actionable tip to reduce power."
    )

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 1500,
                    "responseMimeType": "application/json",
                },
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"[gemini_recommend] HTTP {resp.status_code}: {resp.text[:400]}")
            return _rule_based_fallback(row, predicted_power, disturbance)

        data = resp.json()
        # Join all parts in case the model splits output across multiple parts
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        print(f"[gemini_recommend] Full raw output dict: {json.dumps(data)}")
        parsed = _extract_json_ish(text)
        if not parsed:
            print("[gemini_recommend] Could not parse JSON from response, using fallback.")
            return _rule_based_fallback(row, predicted_power, disturbance)

        reason = parsed.get("reason", "").strip()
        tip = parsed.get("tip", "").strip()

        if not reason or not tip:
            return _rule_based_fallback(row, predicted_power, disturbance)

        print(f"[gemini_recommend] SUCCESS — reason: {reason}")
        return reason, tip

    except Exception as e:
        print(f"[gemini_recommend] Exception: {e}, using fallback.")
        return _rule_based_fallback(row, predicted_power, disturbance)
