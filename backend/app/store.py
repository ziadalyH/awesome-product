from typing import Dict, Optional
from .models import Session

# In-memory store: session_id -> Session
# Trade-off: use a database for persistence in production
_sessions: Dict[str, Session] = {}


def save_session(session: Session) -> None:
    _sessions[session.session_id] = session


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)


def get_all_sessions() -> list[Session]:
    return sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)


def update_session(session: Session) -> None:
    _sessions[session.session_id] = session
