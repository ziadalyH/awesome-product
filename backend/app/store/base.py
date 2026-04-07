"""Abstract base class for session persistence backends."""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.models import Session


class SessionStore(ABC):
    """Interface for storing and retrieving pipeline sessions."""

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist a new session."""
        ...

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID, or ``None`` if not found."""
        ...

    @abstractmethod
    def get_all_sessions(self) -> List[Session]:
        """Return all stored sessions."""
        ...

    @abstractmethod
    def update_session(self, session: Session) -> None:
        """Overwrite an existing session with updated data."""
        ...
