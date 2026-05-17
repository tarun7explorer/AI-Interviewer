import json
import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Path as FPath, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import database as db
import ai_engine as ai
import utils

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOTAL_QUESTIONS = 10
ALLOWED_ORIGINS = ["*"]

# ── VERCEL FIX: Route to /tmp ──
_default_resume_dir = "/tmp/resume" if os.environ.get("VERCEL") else str(Path(__file__).parent.parent / "data" / "resume")
RESUME_DIR = Path(os.getenv("RESUME_DIR", _default_resume_dir))

ROLE_TOPICS = {
    "AI Engineer": [
        {"topic": "Embeddings", "difficulty": "easy", "question_type": "text"},
        {"topic": "Retrieval-Augmented Generation", "difficulty": "easy", "question_type": "text"},
        {"topic": "Overfitting", "difficulty": "medium", "question_type": "text"},
        {"topic": "Model Evaluation", "difficulty": "medium", "question_type": "text"},
        {"topic": "Neural Networks", "difficulty": "hard", "question_type": "text"},
        {"topic": "Transformers", "difficulty": "hard", "question_type": "text"},
        {"topic": "Embeddings", "difficulty": "medium", "question_type": "mcq"},
        {"topic": "Retrieval-Augmented Generation", "difficulty": "medium", "question_type": "mcq"},
        {"topic": "Overfitting", "difficulty": "hard", "question_type": "mcq"},
        {"topic": "Transformers", "difficulty": "hard", "question_type": "mcq"},
    ],
    "Backend Developer": [
        {"topic": "RESTful APIs", "difficulty": "easy", "question_type": "text"},
        {"topic": "Database Optimization", "difficulty": "easy", "question_type": "text"},
        {"topic": "Asynchronous Programming", "difficulty": "medium", "question_type": "text"},
        {"topic": "System Design", "difficulty": "medium", "question_type": "text"},
        {"topic": "Database Optimization", "difficulty": "hard", "question_type": "text"},
        {"topic": "Asynchronous Programming", "difficulty": "hard", "question_type": "text"},
        {"topic": "RESTful APIs", "difficulty": "medium", "question_type": "mcq"},
        {"topic": "Asynchronous Programming", "difficulty": "medium", "question_type": "mcq"},
        {"topic": "Database Optimization", "difficulty": "hard", "question_type": "mcq"},
        {"topic": "System Design", "difficulty": "hard", "question_type": "mcq"},
    ],
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    ai.rebuild_knowledge_base()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class QuestionOut(BaseModel):
    question_id: int
    body: str
    topic: str
    difficulty: str
    question_type: str
    options: Optional[list[str]]
    question_number: int
    total_questions: int

class FeedbackOut(BaseModel):
    score: float
    strengths: list[str]
    improvements: list[str]
    ideal_answer_summary: str
    keywords_matched: list[str]
    keywords_missing: list[str]
    latency_ms: float

class StartInterviewResponse(BaseModel):
    candidate_id: int
    message: str
    resume_saved: bool
    first_question: QuestionOut

class SubmitAnswerResponse(BaseModel):
    answer_id: int
    feedback: FeedbackOut
    next_question: Optional[QuestionOut]
    interview_complete: bool
    message: str

class AnswerReportItem(BaseModel):
    topic: str
    difficulty: str
    question_type: str
    question: str
    options: Optional[list[str]]
    answer: str
    duration_sec: Optional[int]
    score: Optional[float]
    strengths: Optional[list[str]]
    improvements: Optional[list[str]]
    ideal_answer: Optional[str]
    answered_at: str

class ResultsResponse(BaseModel):
    candidate_id: int
    candidate_name: str
    candidate_email: str
    role: str
    resume_path: Optional[str]
    average_score: Optional[float]
    grade: str
    total_questions: int
    answers_submitted: int
    interview_complete: bool
    answers: list[AnswerReportItem]
    summary: str

class SubmitAnswerRequest(BaseModel):
    candidate_id: int = Field(..., gt=0)
    question_id: int = Field(..., gt=0)
    answer: str = Field(..., min_length=1, max_length=8000)
    chosen_option: Optional[int] = Field(None, ge=0, le=3)
    duration_sec: Optional[int] = Field(None, ge=0, le=7200)

def _get_topics_for_role(role: str) -> list[dict]:
    return ROLE_TOPICS.get(role, ROLE_TOPICS["AI Engineer"])

def _score_to_grade(score: Optional[float]) -> str:
    if score is None: return "N/A"
    if score >= 9.0: return "Exceptional (A+)"
    if score >= 8.0: return "Strong (A)"
    if score >= 7.0: return "Proficient (B)"
    if score >= 5.5: return "Developing (C)"
    if score >= 4.0: return "Below Expectations (D)"
    return "Needs Significant Improvement (F)"

def _build_summary(avg: Optional[float], role: str, total: int, submitted: int) -> str:
    if avg is None or submitted == 0: return "Interview not yet completed."
    return f"Candidate answered {submitted}/{total} questions for the {role} role. Average score: {avg:.1f}/10. Grade: {_score_to_grade(avg)}."

def _safe_json_list(raw: Optional[str]) -> Optional[list[str]]:
    if raw is None: return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except Exception: return [raw] if raw.strip() else None

def _safe_json_options(raw: Optional[str]) -> Optional[list[str]]:
    if raw is None: return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) == 4: return [str(o) for o in parsed]
    except Exception: pass
    return None

def _next_topic_index(candidate_id: int, role: str) -> Optional[int]:
    topics = _get_topics_for_role(role)
    answers = db.get_answers_by_candidate(candidate_id)
    return len(answers) if len(answers) < len(topics) else None

def _get_candidate_resume_text(candidate: dict) -> str:
    if candidate and candidate.get("resume_path") and os.path.exists(candidate["resume_path"]):
        try:
            return utils._extract_with_pypdf2(Path(candidate["resume_path"]))
        except Exception:
            return ""
    return ""

async def _persist_question(topic: str, difficulty: str, role: str, question_type: str, resume_text: str = ""):
    gq = await ai.async_generate_question(topic=topic, difficulty=difficulty, role=role, question_type=question_type, resume_text=resume_text)
    options_json = json.dumps(gq.options) if gq.options else None
    qid = db.insert_question(role=role, topic=topic, body=gq.question, difficulty=difficulty, question_type=question_type, options=options_json, correct_option=gq.correct_option)
    return qid, gq.question, gq.options, gq.correct_option

def _save_resume(upload: UploadFile, candidate_id: int) -> Optional[str]:
    try:
        suffix = Path(upload.filename or "resume.pdf").suffix or ".pdf"
        filename = f"candidate_{candidate_id}_{uuid.uuid4().hex[:8]}{suffix}"
        dest = RESUME_DIR / filename
        with dest.open("wb") as f: shutil.copyfileobj(upload.file, f)
        return str(dest)
    except Exception: return None

# ── DUAL ROUTING HACK: Ensures Vercel's /api rewrites don't throw 404s ──

@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "provider": ai.LLM_PROVIDER, "model": ai.LLM_MODEL}

@app.post("/start_interview", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
@app.post("/api/start_interview", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(name: str = Form(...), email: str = Form(...), role: str = Form(...), resume: UploadFile = File(None)):
    email = email.strip().lower()
    existing = db.get_candidate_by_email(email)
    
    if existing:
        candidate_id = existing["id"]
        # FIX: Clear previous answers so the candidate can retake the interview endlessly!
        with db.get_connection() as conn:
            conn.execute("DELETE FROM Answers WHERE candidate_id = ?", (candidate_id,))
    else:
        candidate_id = db.insert_candidate(name=name.strip(), email=email, role=role)

    resume_saved = False
    resume_text = ""
    if resume and resume.filename:
        resume_path = _save_resume(resume, candidate_id)
        if resume_path:
            db.update_candidate_resume(candidate_id, resume_path)
            resume_saved = True
            try:
                resume_text = utils._extract_with_pypdf2(Path(resume_path))
            except Exception: pass

    topics = _get_topics_for_role(role)
    first_topic = topics[0]
    qid, qbody, opts, _ = await _persist_question(first_topic["topic"], first_topic["difficulty"], role, first_topic["question_type"], resume_text)

    return StartInterviewResponse(
        candidate_id=candidate_id, message=f"Welcome! Your {role} interview has started.", resume_saved=resume_saved,
        first_question=QuestionOut(question_id=qid, body=qbody, topic=first_topic["topic"], difficulty=first_topic["difficulty"], question_type=first_topic["question_type"], options=opts, question_number=1, total_questions=TOTAL_QUESTIONS)
    )

@app.post("/submit_answer", response_model=SubmitAnswerResponse)
@app.post("/api/submit_answer", response_model=SubmitAnswerResponse)
async def submit_answer(body: SubmitAnswerRequest):
    candidate = db.get_candidate_by_id(body.candidate_id)
    question_row = db.get_question_by_id(body.question_id)
    if not candidate or not question_row: raise HTTPException(status_code=404, detail="Not found")

    eval_result = await ai.async_evaluate_answer(
        question=question_row["body"], user_answer=body.answer, topic=question_row["topic"],
        role=candidate["role"], question_type=question_row.get("question_type", "text"),
        correct_option=question_row.get("correct_option"), chosen_option=body.chosen_option,
    )

    answer_id = db.insert_answer(candidate_id=body.candidate_id, question_id=body.question_id, body=body.answer, duration_sec=body.duration_sec)
    db.insert_feedback(answer_id=answer_id, score=eval_result.score, strengths=json.dumps(eval_result.strengths), improvements=json.dumps(eval_result.improvements), ideal_answer=eval_result.ideal_answer_summary, raw_llm_json=eval_result.raw_llm_response)

    next_topic_idx = _next_topic_index(body.candidate_id, candidate["role"])
    next_q = None
    interview_complete = next_topic_idx is None

    if next_topic_idx is not None:
        next_t = _get_topics_for_role(candidate["role"])[next_topic_idx]
        resume_text = _get_candidate_resume_text(candidate)
        nqid, nqbody, nopts, _ = await _persist_question(next_t["topic"], next_t["difficulty"], candidate["role"], next_t["question_type"], resume_text)
        next_q = QuestionOut(question_id=nqid, body=nqbody, topic=next_t["topic"], difficulty=next_t["difficulty"], question_type=next_t["question_type"], options=nopts, question_number=next_topic_idx+1, total_questions=TOTAL_QUESTIONS)

    return SubmitAnswerResponse(
        answer_id=answer_id,
        feedback=FeedbackOut(score=eval_result.score, strengths=eval_result.strengths, improvements=eval_result.improvements, ideal_answer_summary=eval_result.ideal_answer_summary, keywords_matched=eval_result.keywords_matched, keywords_missing=eval_result.keywords_missing, latency_ms=eval_result.latency_ms),
        next_question=next_q, interview_complete=interview_complete, message="Great work!" if not interview_complete else "Interview complete!"
    )

@app.get("/results/{candidate_id}", response_model=ResultsResponse)
@app.get("/api/results/{candidate_id}", response_model=ResultsResponse)
async def get_results(candidate_id: int):
    candidate = db.get_candidate_by_id(candidate_id)
    if not candidate: raise HTTPException(status_code=404, detail="Candidate not found.")

    report_rows = db.get_full_report(candidate_id)
    avg_score = db.get_average_score(candidate_id)
    answers_out = [
        AnswerReportItem(topic=row["topic"], difficulty=row["difficulty"], question_type=row.get("question_type", "text"), question=row["question"], options=_safe_json_options(row.get("options")), answer=row["answer"], duration_sec=row.get("duration_sec"), score=row.get("score"), strengths=_safe_json_list(row.get("strengths")), improvements=_safe_json_list(row.get("improvements")), ideal_answer=row.get("ideal_answer"), answered_at=row["answered_at"]) for row in report_rows
    ]

    return ResultsResponse(
        candidate_id=candidate_id, candidate_name=candidate["name"], candidate_email=candidate["email"], role=candidate["role"], resume_path=candidate.get("resume_path"), average_score=avg_score, grade=_score_to_grade(avg_score), total_questions=TOTAL_QUESTIONS, answers_submitted=len(report_rows), interview_complete=(len(report_rows) >= TOTAL_QUESTIONS), answers=answers_out, summary=_build_summary(avg_score, candidate["role"], TOTAL_QUESTIONS, len(report_rows))
    )