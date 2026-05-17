import os
import re
import json
import time
import logging
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── VERCEL FIX: Route Resumes to /tmp, but ensure Knowledge Base is found ──
_default_resumes_dir = "/tmp/resumes" if os.environ.get("VERCEL") else "data/resumes"
RESUMES_DIR = Path(os.getenv("RESUME_DIR", _default_resumes_dir))
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

KB_DIR = Path(__file__).parent.parent / "data" / "knowledge_base"


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\S\n\t]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 4000, suffix: str = "…") -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> list[str]:
    """Split text into overlapping chunks of approximately chunk_size characters."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    return [s.strip() for s in sentences if s.strip()]


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def sanitise_filename(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[\s-]+", "_", name)


def _extract_with_pypdf2(pdf_path: Path) -> str:
    try:
        import PyPDF2  # type: ignore
        text_parts: list[str] = []
        with open(pdf_path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                part = page.extract_text()
                if part:
                    text_parts.append(part)
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("PyPDF2 not installed; falling back to pdfplumber.")
        raise
    except Exception as exc:
        logger.error("PyPDF2 failed on '%s': %s", pdf_path, exc)
        raise


def parse_resume_pdf(filename: str, resumes_dir: Path = RESUMES_DIR) -> dict:
    pdf_path = resumes_dir / filename
    result: dict[str, Any] = {
        "filename": filename,
        "raw_text": "",
        "clean_text": "",
        "word_count": 0,
        "char_count": 0,
        "parsed_at": datetime.utcnow().isoformat(),
        "error": None,
    }

    if not pdf_path.exists():
        result["error"] = f"File not found: {pdf_path}"
        logger.warning(result["error"])
        return result

    try:
        raw = _extract_with_pypdf2(pdf_path)
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["raw_text"] = raw
    result["clean_text"] = clean_text(raw)
    result["word_count"] = word_count(result["clean_text"])
    result["char_count"] = len(result["clean_text"])
    return result


def list_resumes(resumes_dir: Path = RESUMES_DIR) -> list[str]:
    if not resumes_dir.exists():
        return []
    return sorted(f.name for f in resumes_dir.iterdir() if f.suffix.lower() == ".pdf")


def success_response(data: Any, message: str = "OK") -> dict:
    return {
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }


def error_response(message: str, details: Any = None, code: int = 400) -> dict:
    return {
        "status": "error",
        "message": message,
        "details": details,
        "code": code,
        "timestamp": datetime.utcnow().isoformat(),
    }


def load_knowledge_base(role: str, kb_dir: Path = KB_DIR) -> str:
    filename = sanitise_filename(role) + ".txt"
    kb_path = kb_dir / filename

    if not kb_path.exists():
        role_words = {w.lower() for w in role.split()}
        candidates = list(kb_dir.glob("*.txt"))
        for candidate in candidates:
            stem_words = set(candidate.stem.split("_"))
            if role_words & stem_words:
                kb_path = candidate
                break

    if not kb_path.exists():
        return ""

    try:
        raw = kb_path.read_text(encoding="utf-8")
        return clean_text(raw)
    except Exception:
        return ""


def list_available_roles(kb_dir: Path = KB_DIR) -> list[str]:
    if not kb_dir.exists():
        return []
    return [p.stem for p in sorted(kb_dir.glob("*.txt"))]


class Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return round((self._end - self._start) * 1000, 2)


def safe_json_loads(raw: str, fallback: Any = None) -> Any:
    if not raw:
        return fallback
    # Strip markdown code fences if present (e.g. ```json ... ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return fallback