"""In-memory session store implementation."""

from typing import Dict, List, Optional
from app.models import Session
from app.store.base import SessionStore


class InMemorySessionStore(SessionStore):
    """``SessionStore`` backed by a plain Python dict.

    All data is lost on process restart.  Suitable for development and
    single-process deployments.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def save_session(self, session: Session) -> None:
        """Store a new session keyed by its ``session_id``."""
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> List[Session]:
        """Return all sessions sorted by ``created_at`` descending."""
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def update_session(self, session: Session) -> None:
        """Replace an existing session entry with updated data."""
        self._sessions[session.session_id] = session
