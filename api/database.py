import sqlite3
import logging
import os
from contextlib import contextmanager
from typing import Optional

# ── VERCEL FIX: Must use /tmp folder in serverless environments ──
DB_PATH = "/tmp/interview.db" if os.environ.get("VERCEL") else "interview.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_connection(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("DB transaction rolled back: %s", exc)
        raise
    finally:
        conn.close()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS Candidates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    email        TEXT    UNIQUE NOT NULL,
    role         TEXT    NOT NULL,
    resume_path  TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    role          TEXT    NOT NULL,
    topic         TEXT    NOT NULL,
    body          TEXT    NOT NULL,
    difficulty    TEXT    NOT NULL DEFAULT 'medium',
    question_type TEXT    NOT NULL DEFAULT 'text',
    options       TEXT,
    correct_option INTEGER,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Answers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES Candidates(id) ON DELETE CASCADE,
    question_id  INTEGER NOT NULL REFERENCES Questions(id)  ON DELETE CASCADE,
    body         TEXT    NOT NULL,
    duration_sec INTEGER,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id    INTEGER NOT NULL UNIQUE REFERENCES Answers(id) ON DELETE CASCADE,
    score        REAL    NOT NULL,
    strengths    TEXT,
    improvements TEXT,
    ideal_answer TEXT,
    raw_llm_json TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

MIGRATION_SQL = [
    "ALTER TABLE Questions ADD COLUMN question_type TEXT NOT NULL DEFAULT 'text'",
    "ALTER TABLE Questions ADD COLUMN options TEXT",
    "ALTER TABLE Questions ADD COLUMN correct_option INTEGER",
    "ALTER TABLE Candidates ADD COLUMN resume_path TEXT",
]

def init_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        for sql in MIGRATION_SQL:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass 
    logger.info("Database initialised at '%s'.", db_path)

def insert_candidate(name: str, email: str, role: str, resume_path: Optional[str] = None, db_path: str = DB_PATH) -> int:
    sql = "INSERT INTO Candidates (name, email, role, resume_path) VALUES (?, ?, ?, ?)"
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (name, email, role, resume_path))
        return cursor.lastrowid

def update_candidate_resume(candidate_id: int, resume_path: str, db_path: str = DB_PATH) -> None:
    sql = "UPDATE Candidates SET resume_path = ? WHERE id = ?"
    with get_connection(db_path) as conn:
        conn.execute(sql, (resume_path, candidate_id))

def get_candidate_by_id(candidate_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    sql = "SELECT * FROM Candidates WHERE id = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (candidate_id,)).fetchone()
    return dict(row) if row else None

def get_candidate_by_email(email: str, db_path: str = DB_PATH) -> Optional[dict]:
    sql = "SELECT * FROM Candidates WHERE email = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (email,)).fetchone()
    return dict(row) if row else None

def list_candidates(db_path: str = DB_PATH) -> list[dict]:
    sql = "SELECT * FROM Candidates ORDER BY created_at DESC"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]

def insert_question(role: str, topic: str, body: str, difficulty: str = "medium", question_type: str = "text", options: Optional[str] = None, correct_option: Optional[int] = None, db_path: str = DB_PATH) -> int:
    sql = "INSERT INTO Questions (role, topic, body, difficulty, question_type, options, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?)"
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (role, topic, body, difficulty, question_type, options, correct_option))
        return cursor.lastrowid

def get_question_by_id(question_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    sql = "SELECT * FROM Questions WHERE id = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (question_id,)).fetchone()
    return dict(row) if row else None

def get_questions_by_role(role: str, db_path: str = DB_PATH) -> list[dict]:
    sql = "SELECT * FROM Questions WHERE role = ? ORDER BY difficulty"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, (role,)).fetchall()
    return [dict(r) for r in rows]

def insert_answer(candidate_id: int, question_id: int, body: str, duration_sec: Optional[int] = None, db_path: str = DB_PATH) -> int:
    sql = "INSERT INTO Answers (candidate_id, question_id, body, duration_sec) VALUES (?, ?, ?, ?)"
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (candidate_id, question_id, body, duration_sec))
        return cursor.lastrowid

def get_answers_by_candidate(candidate_id: int, db_path: str = DB_PATH) -> list[dict]:
    sql = "SELECT a.*, q.body AS question_body, q.topic, q.role, q.question_type FROM Answers a JOIN Questions q ON q.id = a.question_id WHERE a.candidate_id = ? ORDER BY a.created_at ASC"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, (candidate_id,)).fetchall()
    return [dict(r) for r in rows]

def get_answer_by_id(answer_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    sql = "SELECT * FROM Answers WHERE id = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (answer_id,)).fetchone()
    return dict(row) if row else None

def insert_feedback(answer_id: int, score: float, strengths: Optional[str] = None, improvements: Optional[str] = None, ideal_answer: Optional[str] = None, raw_llm_json: Optional[str] = None, db_path: str = DB_PATH) -> int:
    sql = "INSERT INTO Feedback (answer_id, score, strengths, improvements, ideal_answer, raw_llm_json) VALUES (?, ?, ?, ?, ?, ?)"
    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (answer_id, score, strengths, improvements, ideal_answer, raw_llm_json))
        return cursor.lastrowid

def get_feedback_by_answer(answer_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    sql = "SELECT * FROM Feedback WHERE answer_id = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (answer_id,)).fetchone()
    return dict(row) if row else None

def get_full_report(candidate_id: int, db_path: str = DB_PATH) -> list[dict]:
    sql = """
        SELECT
            c.name          AS candidate_name,
            c.email         AS candidate_email,
            c.role          AS candidate_role,
            q.topic         AS topic,
            q.body          AS question,
            q.difficulty    AS difficulty,
            q.question_type AS question_type,
            q.options       AS options,
            q.correct_option AS correct_option,
            a.id            AS answer_id,
            a.body          AS answer,
            a.duration_sec,
            f.score,
            f.strengths,
            f.improvements,
            f.ideal_answer,
            a.created_at    AS answered_at
        FROM   Candidates c
        JOIN   Answers    a ON a.candidate_id = c.id
        JOIN   Questions  q ON q.id = a.question_id
        LEFT JOIN Feedback f ON f.answer_id = a.id
        WHERE  c.id = ?
        ORDER  BY a.created_at ASC
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, (candidate_id,)).fetchall()
    return [dict(r) for r in rows]

def get_average_score(candidate_id: int, db_path: str = DB_PATH) -> Optional[float]:
    sql = "SELECT AVG(f.score) AS avg_score FROM Feedback f JOIN Answers a ON a.id = f.answer_id WHERE a.candidate_id = ?"
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (candidate_id,)).fetchone()
    return round(row["avg_score"], 2) if row and row["avg_score"] is not None else None