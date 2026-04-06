from typing import Dict, List, Optional
from app.models import Session
from app.store.base import SessionStore


class InMemorySessionStore(SessionStore):
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def save_session(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> List[Session]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def update_session(self, session: Session) -> None:
        self._sessions[session.session_id] = session
