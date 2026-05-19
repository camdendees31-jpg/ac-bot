"""
Animal Company Bot — Backend API
Stores pairing codes, issues API keys, and serves user data.
Runs on Railway as a web service.
"""

import os
import sqlite3
import secrets
import hashlib
import re
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH      = os.getenv("DB_PATH", "ac_bot.db")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "change-this-secret")  # shared with the bot

# ── DB setup ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id    TEXT PRIMARY KEY,
            discord_name  TEXT NOT NULL,
            pairing_code  TEXT NOT NULL UNIQUE,
            api_key       TEXT NOT NULL UNIQUE,
            registered_at TEXT NOT NULL,
            last_used     TEXT
        )
    """)
    conn.commit()
    conn.close()

# ── Auth guard ────────────────────────────────────────────────────────────────
def require_internal(x_internal_key: str = Header(...)):
    if x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

# ── Models ────────────────────────────────────────────────────────────────────
class AuthRequest(BaseModel):
    discord_id:   str
    discord_name: str
    pairing_code: str

class UserResponse(BaseModel):
    discord_id:    str
    discord_name:  str
    pairing_code:  str
    api_key:       str
    registered_at: str
    last_used:     str | None

# ── Helpers ───────────────────────────────────────────────────────────────────
AC_CODE_RE = re.compile(r'^[A-Z0-9]{4,32}$', re.IGNORECASE)

def validate_pairing_code(code: str) -> bool:
    """
    Animal Company pairing codes appear as short alphanumeric strings
    shown on the in-game computer's Pair screen.
    Adjust regex if you know the exact format.
    """
    return bool(AC_CODE_RE.match(code.strip()))

def generate_api_key() -> str:
    return "ac_" + secrets.token_urlsafe(32)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="AC Bot Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth", dependencies=[Depends(require_internal)])
def auth(req: AuthRequest, db: sqlite3.Connection = Depends(get_db)):
    """
    Register or update a user's pairing code.
    Returns their API key (creates one if first time).
    """
    code = req.pairing_code.strip().upper()

    if not validate_pairing_code(code):
        raise HTTPException(
            status_code=422,
            detail="Invalid pairing code format. It should be a short alphanumeric code from the in-game computer."
        )

    # Check if this pairing code belongs to someone else
    existing = db.execute(
        "SELECT discord_id FROM users WHERE pairing_code = ?", (code,)
    ).fetchone()

    if existing and existing["discord_id"] != req.discord_id:
        raise HTTPException(
            status_code=409,
            detail="That pairing code is already registered to a different Discord account."
        )

    # Check if user already has an account
    user = db.execute(
        "SELECT * FROM users WHERE discord_id = ?", (req.discord_id,)
    ).fetchone()

    if user:
        # Update pairing code and name, keep existing API key
        db.execute(
            "UPDATE users SET pairing_code = ?, discord_name = ? WHERE discord_id = ?",
            (code, req.discord_name, req.discord_id)
        )
        db.commit()
        user = db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (req.discord_id,)
        ).fetchone()
    else:
        # New user — create record
        api_key = generate_api_key()
        now     = now_iso()
        db.execute(
            "INSERT INTO users (discord_id, discord_name, pairing_code, api_key, registered_at) VALUES (?,?,?,?,?)",
            (req.discord_id, req.discord_name, code, api_key, now)
        )
        db.commit()
        user = db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (req.discord_id,)
        ).fetchone()

    return dict(user)


@app.get("/api/{discord_id}", dependencies=[Depends(require_internal)])
def get_api(discord_id: str, db: sqlite3.Connection = Depends(get_db)):
    """
    Fetch a user's data by Discord ID.
    """
    user = db.execute(
        "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No account found. Run /get-auth first.")

    # Update last_used
    db.execute(
        "UPDATE users SET last_used = ? WHERE discord_id = ?",
        (now_iso(), discord_id)
    )
    db.commit()

    return dict(user)


@app.get("/users/count", dependencies=[Depends(require_internal)])
def user_count(db: sqlite3.Connection = Depends(get_db)):
    count = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    return {"total_users": count}
