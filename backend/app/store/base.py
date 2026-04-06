from abc import ABC, abstractmethod
from typing import List, Optional
from app.models import Session


class SessionStore(ABC):
    @abstractmethod
    def save_session(self, session: Session) -> None: ...

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]: ...

    @abstractmethod
    def get_all_sessions(self) -> List[Session]: ...

    @abstractmethod
    def update_session(self, session: Session) -> None: ...
