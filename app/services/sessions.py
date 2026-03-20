"""
session_store.py
----------------
Simple in-memory store for parsed statement DataFrames.
Keyed by a UUID session_id returned to the client on upload.

Why in-memory and not a database?
  - Statements are temporary — users don't need them persisted
  - Keeps the app dependency-free (no Redis, no SQLite needed)
  - Sessions expire after TTL_MINUTES to prevent memory leaks

Limitations:
  - Does NOT survive a server restart
  - Does NOT work across multiple server processes (single worker only)
  - If you scale to multiple workers later, swap this for Redis
"""

import uuid
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd

logger = logging.getLogger(__name__)

TTL_MINUTES = 30   # sessions expire after 30 minutes of inactivity
MAX_SESSIONS = 100  # evict oldest sessions if store grows too large


@dataclass
class Session:
    df:         pd.DataFrame
    filename:   str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used:  datetime = field(default_factory=datetime.utcnow)

    @property
    def total_rows(self) -> int:
        return len(self.df)

    def is_expired(self) -> bool:
        return datetime.utcnow() - self.last_used > timedelta(minutes=TTL_MINUTES)

    def touch(self):
        self.last_used = datetime.utcnow()


class SessionStore:
    def __init__(self):
        self._store: dict[str, Session] = {}

    def save(self, df: pd.DataFrame, filename: str) -> str:
        """Store a DataFrame and return a new session_id."""
        self._evict_expired()

        # If store is still too large, evict oldest by last_used
        if len(self._store) >= MAX_SESSIONS:
            oldest_id = min(self._store, key=lambda k: self._store[k].last_used)
            del self._store[oldest_id]
            logger.warning(f"Session store full — evicted oldest session {oldest_id}")

        session_id = str(uuid.uuid4())
        self._store[session_id] = Session(df=df.copy(), filename=filename)
        logger.info(f"Session created: {session_id} ({len(df)} rows, file={filename})")
        return session_id

    def get(self, session_id: str) -> Session | None:
        """Retrieve a session, updating last_used. Returns None if not found or expired."""
        session = self._store.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            del self._store[session_id]
            logger.info(f"Session expired and removed: {session_id}")
            return None
        session.touch()
        return session

    def delete(self, session_id: str):
        """Explicitly delete a session."""
        self._store.pop(session_id, None)

    def _evict_expired(self):
        expired = [sid for sid, s in self._store.items() if s.is_expired()]
        for sid in expired:
            del self._store[sid]
        if expired:
            logger.info(f"Evicted {len(expired)} expired session(s)")

    @property
    def active_count(self) -> int:
        return len(self._store)


# Single global instance shared across all requests
store = SessionStore()