"""
ai_engine.py  –  Core AI logic for the Interview System.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Literal, Optional

from dotenv import load_dotenv

from utils import (
    clean_text,
    chunk_text,
    safe_json_loads,
    truncate_text,
    Timer,
    load_knowledge_base,
    list_available_roles,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "huggingface").lower()
HF_API_KEY: str   = os.getenv("HF_API_KEY", "")

# Vercel deploys the 'data' folder next to 'api'
KB_DIR = Path(__file__).parent.parent / "data" / "knowledge_base"
MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "3000"))

LLM_MODEL: str = os.getenv("LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")

@dataclass
class KBChunk:
    role: str
    filename: str
    text: str
    char_start: int = 0

@dataclass
class KnowledgeBaseIndex:
    chunks: list[KBChunk] = field(default_factory=list)

    def build(self, kb_dir: Path = KB_DIR) -> "KnowledgeBaseIndex":
        self.chunks.clear()
        if not kb_dir.exists():
            logger.warning("Knowledge-base directory '%s' not found.", kb_dir)
            return self

        for txt_file in sorted(kb_dir.glob("*.txt")):
            raw = txt_file.read_text(encoding="utf-8")
            cleaned = clean_text(raw)
            for i, chunk_text_piece in enumerate(chunk_text(cleaned, chunk_size=400, overlap=40)):
                self.chunks.append(
                    KBChunk(role=txt_file.stem, filename=txt_file.name, text=chunk_text_piece, char_start=i)
                )
        return self

    def retrieve(self, query: str, role: Optional[str] = None, top_k: int = 3, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        if not self.chunks:
            return ""

        query_tokens = set(re.findall(r"\w+", query.lower()))
        pool = [c for c in self.chunks if (role is None or c.role == role)]
        if not pool:
            pool = self.chunks

        def _score(chunk: KBChunk) -> int:
            chunk_tokens = set(re.findall(r"\w+", chunk.text.lower()))
            return len(query_tokens & chunk_tokens)

        ranked = sorted(pool, key=_score, reverse=True)[:top_k]
        combined = "\n\n---\n\n".join(c.text for c in ranked)
        return truncate_text(combined, max_chars=max_chars)

_kb_index: KnowledgeBaseIndex = KnowledgeBaseIndex()
_kb_built: bool = False

def _ensure_kb() -> KnowledgeBaseIndex:
    global _kb_index, _kb_built
    if not _kb_built:
        _kb_index.build(KB_DIR)
        _kb_built = True
    return _kb_index

def rebuild_knowledge_base() -> None:
    global _kb_built
    _kb_built = False
    _ensure_kb()

def _call_llm(system_prompt: str, user_prompt: str) -> str:
    if LLM_PROVIDER == "huggingface":
        return _call_huggingface(system_prompt, user_prompt)
    return _call_mock(system_prompt, user_prompt)

def _call_huggingface(system_prompt: str, user_prompt: str) -> str:
    if not HF_API_KEY:
        logger.warning("HF_API_KEY not set — falling back to smart mock.")
        return _call_mock(system_prompt, user_prompt)

    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")

    url = "https://api-inference.huggingface.co/v1/chat/completions"
    req = urllib.request.Request(
        url, data=payload, headers={"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("HuggingFace request failed: %s — falling back to mock.", exc)
        return _call_mock(system_prompt, user_prompt)


_MOCK_FEEDBACK_TEMPLATE = {
    "score": 7.5,
    "strengths": ["Clear definition of the core concept.", "Mentioned at least one relevant tool."],
    "improvements": ["Could elaborate on real-world trade-offs.", "A concrete code example would strengthen the answer."],
    "ideal_answer_summary": "A complete answer should define the concept precisely.",
    "keywords_matched": ["concept", "technique"],
    "keywords_missing": ["trade-off", "example"],
}

def _call_mock(system_prompt: str, user_prompt: str) -> str:
    lower = user_prompt.lower() + system_prompt.lower()
    
    # Extract topic dynamically from the prompt to avoid repeating the exact same question
    topic_match = re.search(r"about: (.*?)\.", user_prompt)
    topic = topic_match.group(1) if topic_match else "this topic"

    if "mcq" in lower or "options" in lower:
        return json.dumps({
            "question": f"[MOCK MCQ] Which of the following statements is true regarding {topic}?",
            "options": [f"It decreases {topic} efficiency.", f"It represents the core of {topic}.", "It translates data to Python.", "It removes necessary variables."],
            "correct_option": 1
        })
    
    if "evaluat" in lower or "score" in lower:
        feedback = dict(_MOCK_FEEDBACK_TEMPLATE)
        feedback["score"] = round(random.uniform(6.0, 9.5), 1)
        feedback["ideal_answer_summary"] = f"A strong answer would accurately describe {topic} and reference your resume experience if applicable."
        return json.dumps(feedback)
    
    return f"[MOCK QUESTION] Based on your background and resume, how would you approach a problem involving {topic}?"

@dataclass
class GeneratedQuestion:
    question: str
    topic: str
    difficulty: str
    role: str
    question_type: str
    options: Optional[list[str]] = None
    correct_option: Optional[int] = None
    context_used: str = ""
    provider: str = ""
    latency_ms: float = 0.0

@dataclass
class EvaluationResult:
    score: float
    strengths: list[str]
    improvements: list[str]
    ideal_answer_summary: str
    keywords_matched: list[str]
    keywords_missing: list[str]
    context_used: str
    raw_llm_response: str
    provider: str
    latency_ms: float = 0.0

_OPEN_QUESTION_SYSTEM = "You are a senior technical interviewer. Output ONLY the question text. Personalize it using the resume context if provided."
_OPEN_QUESTION_USER = "RESUME CONTEXT:\n{resume}\n\nKB CONTEXT:\n{context}\nGenerate a {difficulty} open-ended interview question about: {topic}. Role: {role}."
_MCQ_SYSTEM = 'You are an interviewer. Generate ONE MCQ. Respond ONLY with JSON: {"question": "...", "options": ["A","B","C","D"], "correct_option": 0}'
_MCQ_USER = "RESUME CONTEXT:\n{resume}\n\nKB CONTEXT:\n{context}\nGenerate a {difficulty} MCQ about: {topic}. Role: {role}."
_EVALUATION_SYSTEM = 'Evaluate answer. Respond ONLY with JSON: {"score": 8.5, "strengths": [], "improvements": [], "ideal_answer_summary": "", "keywords_matched": [], "keywords_missing": []}'
_EVALUATION_USER = "CONTEXT:\n{context}\nQUESTION:\n{question}\nANSWER:\n{answer}"

def generate_question(topic: str, difficulty: str = "medium", role: str = "AI Engineer", question_type: str = "text", resume_text: str = "") -> GeneratedQuestion:
    kb = _ensure_kb()
    context = kb.retrieve(query=topic, role=None)
    
    resume_snippet = resume_text[:1000] if resume_text else "No resume provided."

    if question_type == "mcq":
        return _generate_mcq(topic, difficulty, role, context, resume_snippet)
    return _generate_open(topic, difficulty, role, context, resume_snippet)

def _generate_open(topic: str, difficulty: str, role: str, context: str, resume: str) -> GeneratedQuestion:
    system_p = _OPEN_QUESTION_SYSTEM
    user_p = _OPEN_QUESTION_USER.format(resume=resume, context=context, difficulty=difficulty, topic=topic, role=role)
    with Timer() as t:
        raw = _call_llm(system_p, user_p)
    return GeneratedQuestion(question=clean_text(raw), topic=topic, difficulty=difficulty, role=role, question_type="text", provider=LLM_PROVIDER, latency_ms=t.elapsed_ms)

def _generate_mcq(topic: str, difficulty: str, role: str, context: str, resume: str) -> GeneratedQuestion:
    system_p = _MCQ_SYSTEM
    user_p = _MCQ_USER.format(resume=resume, context=context, difficulty=difficulty, topic=topic, role=role)
    with Timer() as t:
        raw = _call_llm(system_p, user_p)
    parsed = safe_json_loads(raw) or {"question": f"Question about {topic}?", "options": ["A","B","C","D"], "correct_option": 0}
    return GeneratedQuestion(question=clean_text(str(parsed.get("question", "Question?"))), topic=topic, difficulty=difficulty, role=role, question_type="mcq", options=[str(o) for o in parsed.get("options", [])], correct_option=int(parsed.get("correct_option", 0)), provider=LLM_PROVIDER, latency_ms=t.elapsed_ms)

def evaluate_answer(question: str, user_answer: str, topic: str = "", role: str = "AI Engineer", question_type: str = "text", correct_option: Optional[int] = None, chosen_option: Optional[int] = None) -> EvaluationResult:
    if question_type == "mcq":
        is_correct = chosen_option == correct_option
        score = 10.0 if is_correct else 0.0
        return EvaluationResult(score=score, strengths=["Correct!"] if is_correct else [], improvements=["Review the material."] if not is_correct else [], ideal_answer_summary=f"Option {chr(65+(correct_option or 0))} was correct.", keywords_matched=[], keywords_missing=[], context_used="", raw_llm_response="", provider=LLM_PROVIDER)
    
    kb = _ensure_kb()
    context = kb.retrieve(query=f"{question} {user_answer[:200]}")
    with Timer() as t:
        raw = _call_llm(_EVALUATION_SYSTEM, _EVALUATION_USER.format(context=context, question=question, answer=user_answer))
    
    parsed = safe_json_loads(raw) or _MOCK_FEEDBACK_TEMPLATE
    return EvaluationResult(score=float(parsed.get("score", 5.0)), strengths=parsed.get("strengths", []), improvements=parsed.get("improvements", []), ideal_answer_summary=parsed.get("ideal_answer_summary", ""), keywords_matched=parsed.get("keywords_matched", []), keywords_missing=parsed.get("keywords_missing", []), context_used=context, raw_llm_response=raw, provider=LLM_PROVIDER, latency_ms=t.elapsed_ms)

async def async_generate_question(topic: str, difficulty: str = "medium", role: str = "AI Engineer", question_type: str = "text", resume_text: str = "") -> GeneratedQuestion:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(generate_question, topic, difficulty, role, question_type, resume_text))

async def async_evaluate_answer(question: str, user_answer: str, topic: str = "", role: str = "AI Engineer", question_type: str = "text", correct_option: Optional[int] = None, chosen_option: Optional[int] = None) -> EvaluationResult:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(evaluate_answer, question, user_answer, topic, role, question_type, correct_option, chosen_option))