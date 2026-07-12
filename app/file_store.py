"""
Handles uploaded files: extracts readable text and stores it so /chat and
/job can pull it in as context for the LLM.
"""

import sqlite3
import os
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sessions.db")

MAX_CHARS_PER_FILE = 300000
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".csv",
    ".html", ".css", ".yaml", ".yml", ".xml", ".sql", ".sh", ".java",
    ".c", ".cpp", ".go", ".rs", ".rb", ".php", ".log", ".ini", ".cfg",
}


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    return conn


def _extract_text(filename: str, raw_bytes: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()

    if ext in TEXT_EXTENSIONS:
        try:
            return raw_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[Could not decode {filename} as text: {e}]"

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return f"[{filename}: install 'pypdf' to extract PDF text — pip install pypdf]"
        except Exception as e:
            return f"[Could not extract text from {filename}: {e}]"

    if ext == ".docx":
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            return f"[{filename}: install 'python-docx' to extract Word text — pip install python-docx]"
        except Exception as e:
            return f"[Could not extract text from {filename}: {e}]"

    try:
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return f"[{filename}: unsupported file type, could not extract text]"


def save_file(filename: str, raw_bytes: bytes) -> dict:
    text = _extract_text(filename, raw_bytes)
    truncated = len(text) > MAX_CHARS_PER_FILE
    if truncated:
        text = text[:MAX_CHARS_PER_FILE] + "\n\n[...truncated, file was longer...]"

    file_id = str(uuid.uuid4())[:8]
    conn = _get_conn()
    conn.execute(
        "INSERT INTO files (file_id, filename, content) VALUES (?, ?, ?)",
        (file_id, filename, text),
    )
    conn.commit()
    conn.close()

    return {
        "file_id": file_id,
        "filename": filename,
        "char_count": len(text),
        "truncated": truncated,
        "preview": text[:200],
    }


def get_files_text(file_ids: list[str]) -> str:
    if not file_ids:
        return ""
    conn = _get_conn()
    blocks = []
    for fid in file_ids:
        row = conn.execute(
            "SELECT filename, content FROM files WHERE file_id = ?", (fid,)
        ).fetchone()
        if row:
            filename, content = row
            blocks.append(f"--- File: {filename} ---\n{content}")
    conn.close()
    return "\n\n".join(blocks)