"""Thin async wrapper over the Gemini REST API (free tier from aistudio.google.com/app/apikey)."""
import os
import httpx

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


async def generate(contents, system, max_tokens=350, json_mode=False) -> str:
    cfg = {"temperature": 0.6, "maxOutputTokens": max_tokens}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
     
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": cfg}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(URL.format(model=model_name()), json=body, headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY", "")})
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()
