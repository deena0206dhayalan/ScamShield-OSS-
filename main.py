"""ScamShield OSS backend.

Three open-source models served from one GPU notebook (Kaggle / Colab):
  * faster-whisper large-v3-turbo  -> speech to text
  * qwen3:8b (Ollama)              -> coercion / scam analysis + Indian law mapping
  * qwen2.5vl:7b (Ollama)          -> forged warrant & predatory contract forensics

Run from the notebook (see notebooks/scamshield_kaggle.ipynb) or locally:
    uvicorn main:app --host 127.0.0.1 --port 8000
"""
import base64
import json
import os
import tempfile
from contextlib import asynccontextmanager

import ollama
from faster_whisper import WhisperModel
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from database import engine, init_db
from models import CallLog, EvidenceRecord

# ---------------------------------------------------------------- config
# Use 127.0.0.1, NOT 0.0.0.0: the python client cannot connect to 0.0.0.0 in Kaggle.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen3:8b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "float16")

client = ollama.Client(host=OLLAMA_URL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ScamShield OSS Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Faster-Whisper...")
whisper_model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
print("Whisper ready.")


# ---------------------------------------------------------------- helpers
def ask_json(model: str, messages: list, retries: int = 2) -> dict:
    """Call Ollama and return parsed JSON.

    Errors are raised as HTTPException so the response still carries CORS headers
    (a raw 500 would show up in the browser as an unhelpful "Failed to fetch").
    """
    last_err = "unknown error"
    for _ in range(retries + 1):
        try:
            res = client.chat(
                model=model,
                messages=messages,
                format="json",
                options={"temperature": 0.1},
            )
            return json.loads(res["message"]["content"])
        except json.JSONDecodeError as e:
            last_err = f"model returned invalid JSON: {e}"
        except ConnectionError:
            raise HTTPException(503, "Cannot reach Ollama. Is `ollama serve` running?")
        except Exception as e:  # model missing, OOM, etc.
            raise HTTPException(502, f"Model error ({model}): {e}")
    raise HTTPException(502, last_err)


def to_int(value, default=0) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- routes
@app.get("/health")
def health():
    try:
        models = [m.model for m in client.list().models]
        return {"ok": True, "ollama_models": models}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/analyze-call")
def analyze_call(audio: UploadFile = File(None), fallback_text: str = Form(None)):
    # 1. transcript: typed/simulated text wins, otherwise transcribe the audio chunk
    transcript = (fallback_text or "").strip()
    if audio is not None and not transcript:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(audio.file.read())
            tmp_path = tmp.name
        try:
            segments, _ = whisper_model.transcribe(tmp_path, beam_size=1)
            transcript = " ".join(seg.text for seg in segments).strip()
        finally:
            os.remove(tmp_path)

    if not transcript:
        return {
            "transcript": "", "coercion_score": 0, "status": "SAFE", "tactics": [],
            "bns_violation": "None", "advice": "Monitoring audio stream...",
        }

    # 2. coercion analysis + statute mapping (/no_think keeps Qwen3 from emitting reasoning text)
    prompt = f"""You are an Indian Cybercrime & Digital Arrest Scam Interceptor.
Analyze this live call transcript snippet: "{transcript}"

Return ONLY valid JSON with these exact keys:
- "coercion_score": integer from 0 to 100 indicating scam probability
- "status": "SAFE" (0-35), "SUSPICIOUS" (36-69), or "CRITICAL DIGITAL ARREST SCAM" (70-100)
- "tactics": list of strings (e.g., "Authority Impersonation (CBI/Customs)", "Isolation Demand", "Immediate Financial Transfer Threat")
- "bns_violation": cite applicable Indian law (e.g., "BNS Section 319 (Cheating by Personation) & Section 318 (Fraudulent Deception); IT Act Sec 66D")
- "advice": 1-sentence urgent instruction for the victim (e.g., "Police/CBI never conduct arrests on video call. Hang up and dial 1930 immediately.")
/no_think"""
    data = ask_json(TEXT_MODEL, [{"role": "user", "content": prompt}])

    data["coercion_score"] = to_int(data.get("coercion_score"))
    data.setdefault("status", "UNKNOWN")
    data.setdefault("tactics", [])
    data.setdefault("bns_violation", "None")
    data.setdefault("advice", "")
    data["transcript"] = transcript

    try:  # never let a DB problem break the live demo
        with Session(engine) as session:
            session.add(CallLog(
                transcript=transcript,
                coercion_score=data["coercion_score"],
                status=str(data["status"]),
                bns_violation=str(data["bns_violation"]),
            ))
            session.commit()
    except Exception as e:
        print("DB log failed:", e)

    return data


@app.post("/scan-document")
def scan_document(file: UploadFile = File(...)):
    b64_img = base64.b64encode(file.file.read()).decode("utf-8")

    prompt = """You are a Forensic Document & Predatory Contract Auditor (FinePrint Shield).
Inspect this document image (which may be a fake CBI/RBI/Customs arrest warrant, a suspicious legal notice, or an exploitative contract).

Return ONLY valid JSON with these exact keys:
- "authenticity_risk_score": integer from 0 to 100 (100 = definitely forged warrant or predatory contract)
- "verdict": short headline verdict (e.g., "FORGED CBI WARRANT DETECTED" or "PREDATORY CLAUSE FLAGGED")
- "red_flags": list of 3-4 specific visual or legal anomalies found (e.g., "Mismatched RBI/CBI emblem", "Demand for personal UPI security deposit", "Unenforceable penalty bond clause")
- "flagged_regions": list of objects with {"label": string, "box_2d": [ymin, xmin, ymax, xmax]} using normalized 0-1000 coordinates for suspicious stamps, signatures, or clauses
- "counter_notice": a formal 3-sentence legal refusal / NCRP 1930 cybercrime evidentiary summary
"""
    data = ask_json(VISION_MODEL, [{"role": "user", "content": prompt, "images": [b64_img]}])

    data["authenticity_risk_score"] = to_int(data.get("authenticity_risk_score"))
    data.setdefault("verdict", "Scan complete")
    data.setdefault("red_flags", [])
    data.setdefault("flagged_regions", [])
    data.setdefault("counter_notice", "")

    try:
        with Session(engine) as session:
            session.add(EvidenceRecord(
                file_name=file.filename or "uploaded_document",
                risk_score=data["authenticity_risk_score"],
                verdict=str(data["verdict"]),
                counter_notice=str(data["counter_notice"]),
            ))
            session.commit()
    except Exception as e:
        print("DB log failed:", e)

    return data


@app.get("/history")
def history(limit: int = 10):
    """Audit trail: latest analysed calls and scanned documents."""
    with Session(engine) as session:
        calls = session.exec(select(CallLog).order_by(CallLog.id.desc()).limit(limit)).all()
        evidence = session.exec(select(EvidenceRecord).order_by(EvidenceRecord.id.desc()).limit(limit)).all()
    return {"call_history": calls, "evidence_history": evidence}
