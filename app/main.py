"""
Run this with:
    uvicorn app.main:app --reload

Then test with:
    POST http://127.0.0.1:8000/chat
    { "session_id": "test-1", "message": "hello, who are you?" }
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from typing import Optional, List

from app.context_store import get_history, append_message
from app.router import call_llm, AllProvidersFailedError
from app.job_runner import run_job, MAX_ATTEMPTS_DEFAULT
from app.file_store import save_file, get_files_text

load_dotenv()  # reads your .env file into environment variables

app = FastAPI(title="Multi-LLM Router with Failover")

# Allows the frontend/index.html page (opened directly in a browser) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload one or more files (or a whole folder — the frontend sends all
    files in it). Extracts text from each and returns file_ids you can
    pass into /chat or /job to give the LLM that content as context.
    """
    results = []
    for f in files:
        raw = await f.read()
        info = save_file(f.filename, raw)
        results.append(info)
    return {"files": results}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: Optional[str] = None       # e.g. "groq" to force one provider; None = auto-failover
    file_ids: Optional[List[str]] = None  # file_ids returned from /upload


class ChatResponse(BaseModel):
    reply: str
    provider_used: str
    attempts: list


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # If files were attached, fold their content into this message
    message_text = req.message
    if req.file_ids:
        files_text = get_files_text(req.file_ids)
        if files_text:
            message_text = f"{req.message}\n\nReference these uploaded files:\n{files_text}"

    # 1. Save the user's new message into that session's history
    history = append_message(req.session_id, "user", message_text)

    # 2. Send the FULL history (not just the new message) to the router.
    #    This is what preserves context across a provider switch.
    try:
        result = call_llm(history, forced_provider=req.provider)
    except AllProvidersFailedError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 3. Save the assistant's reply so next turn has full context too
    append_message(req.session_id, "assistant", result["content"])

    return ChatResponse(
        reply=result["content"],
        provider_used=result["provider_used"],
        attempts=result["attempts"],
    )


class JobRequest(BaseModel):
    task: str
    tests: Optional[str] = None       # optional pytest code
    max_attempts: int = MAX_ATTEMPTS_DEFAULT
    provider: Optional[str] = None       # e.g. "cerebras" to force one provider; None = auto-failover
    file_ids: Optional[List[str]] = None  # file_ids returned from /upload


class JobResponse(BaseModel):
    job_id: str
    success: bool
    code: str
    attempts_used: int
    attempt_log: list
    final_provider: Optional[str] = None


@app.post("/job", response_model=JobResponse)
def job(req: JobRequest):
    """
    Give it a coding task (and optionally pytest tests). It writes code,
    runs it, and if it fails, sends the real error back to the LLM and
    retries — up to max_attempts times.
    """
    file_context = get_files_text(req.file_ids) if req.file_ids else None
    result = run_job(
        task=req.task,
        tests=req.tests,
        max_attempts=req.max_attempts,
        provider=req.provider,
        file_context=file_context,
    )
    return JobResponse(**result)


@app.get("/history/{session_id}")
def history(session_id: str):
    return {"session_id": session_id, "messages": get_history(session_id)}


@app.get("/")
def root():
    return {"status": "running", "docs": "/docs"}