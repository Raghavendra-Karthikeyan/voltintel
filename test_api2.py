import os, requests, json
API_KEY = os.getenv("GEMINI_API_KEY")
URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent'
prompt = 'Return a JSON with reason and tip.'
resp = requests.post(URL, params={'key': API_KEY}, json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 300, 'responseMimeType': 'application/json'}})
print(json.dumps(resp.json(), indent=2))
