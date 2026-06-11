import os

import requests
from dotenv import load_dotenv


load_dotenv()


# API keys for fallback models
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_KEY_BACKUP = os.getenv("GROK_API_KEY_BACKUP")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def call_grok(prompt: str, api_key: str = None) -> str:
    """Generate a response using the Grok API (xAI)."""
    key_to_use = api_key or GROK_API_KEY
    if not key_to_use:
        raise RuntimeError("Grok API key not configured")
    # User is using GroqCloud API (starts with gsk_), not x.ai Grok
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key_to_use}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        
        # Raise an exception for any other status code so get_response falls back to Gemini
        raise RuntimeError(f"Grok API error {resp.status_code}: {resp.text}")
    except Exception as e:
        raise RuntimeError(f"Grok request failed: {e}")

def call_gemini(prompt: str) -> str:
    """Generate a response using the Gemini API."""
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Raise exception for any failure
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")
    except Exception as e:
        raise RuntimeError(f"Gemini request failed: {e}")

def get_response(prompt: str) -> str:
    """
    Try Grok first; if it fails due to rate-limit or auth issues,
    try the backup Groq key. If both fail, fall back to Gemini.
    """
    try:
        return call_grok(prompt)
    except RuntimeError as grok_err:
        try:
            return call_grok(prompt, api_key=GROK_API_KEY_BACKUP)
        except RuntimeError as backup_err:
            try:
                return call_gemini(prompt)
            except RuntimeError as gemini_err:
                return f"❌ All APIs failed:\n- Grok Primary: {grok_err}\n- Grok Backup: {backup_err}\n- Gemini: {gemini_err}"