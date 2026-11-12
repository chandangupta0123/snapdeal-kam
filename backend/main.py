"""FastAPI server: serves the frontend and exposes the JSON API.
Run from the project root:  uvicorn backend.main:app --reload"""
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from ai import gemini_client, kam_agent          # noqa: E402  (after load_dotenv)
from backend import analyzer, data_loader as dl  # noqa: E402 

app = FastAPI(title="Snapdeal AI Virtual KAM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def payload(ds):
    return {**ds, "rows": analyzer.describe(ds), "ai": gemini_client.available(), "model": gemini_client.model_name()}


@app.get("/api/sample")
def sample():
    return payload(dl.sample_data())


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 10_000_000:
        raise HTTPException(413, "File too large (max 10 MB).")
    try:
        try:
            ds = dl.parse_file(file.filename, data)
        except ValueError:
            if not file.filename.lower().endswith(".pdf"):
                raise
            j = await kam_agent.extract_metrics(dl.pdf_text(data))        # Gemini reads messy PDFs
            m = {k: [dl.num(x) for x in v] for k, v in j["metrics"].items() if k in dl.MET and isinstance(v, list) and len(v) == 2}
            ds = dl.finalize(m, j.get("periods") or ["Previous", "Current"], file.filename + " (read by Gemini)")
    except Exception as e:
        raise HTTPException(400, str(e))
    return payload(ds)


class Msg(BaseModel):
    role: str   # "user" | "model"
    text: str


class ChatReq(BaseModel):
    dataset: dict
    history: list[Msg]
    lang: str = "en-IN"


@app.post("/api/chat")
async def chat(req: ChatReq):
    an = analyzer.analyze(req.dataset)
    hist = [m.model_dump() for m in req.history]
    if not any(m["role"] == "user" for m in hist):
        raise HTTPException(400, "No user message yet.")
    return await kam_agent.reply(hist, analyzer.data_brief(req.dataset, an), an, req.lang)


@app.post("/api/summary")
async def summary(req: ChatReq):
    an = analyzer.analyze(req.dataset)
    hist = [m.model_dump() for m in req.history]
    s = await kam_agent.summarise(hist, analyzer.data_brief(req.dataset, an), analyzer.local_summary(an), req.lang)
    return {**s, "spoken": analyzer.spoken_summary(s, req.lang)}


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
