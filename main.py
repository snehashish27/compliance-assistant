import uuid
import time
import os
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from document_parser import extract_text
from detector import detect_and_mask, classify_risk
from compliance_engine import generate_compliance_summary, build_rag_chain
class ReportRequest(BaseModel):
    session_id: str
app = FastAPI(title="Proteccio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
SESSIONS = {}
class ChatRequest(BaseModel):
    session_id: str
    message: str
@app.post("/api/analyze")
async def analyze_documents(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    combined_raw = ""
    aggregated_counts = {}
    total_flagged = 0
    processed_files = []
    for file in files:
        file_bytes = await file.read()
        extracted = extract_text(file.filename, file_bytes)
        combined_raw += f"\n\n--- Document: {file.filename} ---\n\n{extracted}"
        processed_files.append(file.filename)
    for file_text in combined_raw.split("--- Document:"):
        if not file_text.strip():
            continue
        res = detect_and_mask(file_text)
        total_flagged += res["total_findings"]
        for entity, count in res["counts"].items():
            aggregated_counts[entity] = aggregated_counts.get(entity, 0) + count
    global_results = detect_and_mask(combined_raw)
    calculated_risk = classify_risk(aggregated_counts)
    print(f"[DEBUG] Starting FAISS index build for session...")
    qa_chain = build_rag_chain(global_results["masked_text"])
    if qa_chain is None:
        print("[DEBUG] ⚠️  build_rag_chain returned None — chat will be unavailable")
    else:
        print("[DEBUG] ✅ RAG chain built successfully — chat is ready")
    SESSIONS[session_id] = {
        "qa_chain": qa_chain,
        "masked_context": global_results["masked_text"],
        "metrics": {
            "total": total_flagged,
            "breakdown": aggregated_counts,
            "risk": calculated_risk
        },
        "processed_files": processed_files,
        "analysis_timestamp": time.strftime("%d %b %Y, %H:%M"),
        "report": None
    }
    return {
        "session_id": session_id,
        "metrics": SESSIONS[session_id]["metrics"],
        "processed_files": processed_files,
        "masked_context": global_results["masked_text"]
    }
@app.post("/api/generate-report")
async def generate_report(request: ReportRequest):
    session = SESSIONS.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("report"):
        return {"report": session["report"]}
    metrics = session["metrics"]
    try:
        report = generate_compliance_summary(
            metrics["total"], metrics["breakdown"], metrics["risk"]
        )
        session["report"] = report
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
@app.post("/api/chat")
async def chat(request: ChatRequest):
    session = SESSIONS.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    qa_chain = session.get("qa_chain")
    if not qa_chain:
        raise HTTPException(status_code=500, detail="RAG index offline")
    try:
        response = qa_chain.invoke({"question": request.message})
        reply = response.get("answer") or response.get("result") or str(response)
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"⚠️ Error: {str(e)}"}
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
