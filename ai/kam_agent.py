"""Orchestrates the conversation: Gemini first, offline engine as fallback."""
import json, re
from . import gemini_client as gem, offline_engine as off, prompts


def _contents(history):
    c = [{"role": "user", "parts": [{"text": "[Call connected. Seller is on the line.]"}]}]
    return c + [{"role": m["role"], "parts": [{"text": m["text"]}]} for m in history]


def _json(s):
    return json.loads(re.sub(r"```json|```", "", s).strip())


async def reply(history, brief, an, lang):
    err = None
    if gem.available():
        try:
            out = await gem.generate(_contents(history), prompts.system_prompt(brief, lang), 350)
            if "[WRAP_UP]" in out.upper():
                return {"wrap": True, "mode": "gemini"}
            text = re.sub(r"[*#`_]", "", re.sub(r"\[[A-Z_]+\]", "", out)).strip()
            return {"text": text or "Could you repeat that?", "mode": "gemini"}
        except Exception as e:                           # quota, network, bad key...
            err = str(e)[:150]
    return {**off.reply(history, an), "mode": "offline", "error": err}


async def summarise(history, brief, local, lang):
    if gem.available():
        try:
            tr = "\n".join(("Seller: " if m["role"] == "user" else "KAM: ") + m["text"] for m in history)
            j = _json(await gem.generate([{"role": "user", "parts": [{"text": prompts.summary_prompt(brief, tr, lang)}]}],
                                         "You output JSON only.", 600, json_mode=True))
            if j.get("issues") and j.get("actions"):
                return {"issues": j["issues"], "actions": j["actions"], "next_steps": j.get("next_steps", [])}
        except Exception:
            pass
    return local


async def extract_metrics(text):
    """Used for messy PDFs the regex parser cannot read."""
    if not gem.available():
        raise ValueError("Couldn't read numbers from this PDF. Add GEMINI_API_KEY on the server (it can read messy PDFs), or upload a CSV.")
    j = _json(await gem.generate([{"role": "user", "parts": [{"text": prompts.EXTRACT_PROMPT + text[:12000]}]}],
                                 "You extract structured data. Output JSON only.", 800, json_mode=True))
    return j
