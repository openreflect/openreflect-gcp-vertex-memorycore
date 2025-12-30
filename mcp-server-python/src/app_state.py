"""Application state management"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from contextvars import ContextVar

from .config import Config

# Context variable to track the session ID for the current request
current_session_id: ContextVar[Optional[str]] = ContextVar("current_session_id", default=None)


@dataclass
class SessionState:
    """State for a single user session."""
    session_id: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    auth_method: Optional[str] = None  # "oauth" or "passphrase"
    authenticated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_authenticated(self) -> bool:
        """Check if the session is authenticated."""
        return self.user_id is not None


class AppState:
    """Simple application state container following the Zen: \"Simple is better than complex\"."""

    def __init__(self):
        self.client: Optional[Any] = None
        self.agent_engine: Optional[Any] = None
        self.config: Config = Config()
        self.initialized: bool = False
        # In-memory session store: session_id -> SessionState
        self.sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionState:
        """Get an existing session or create a new one."""
        if not session_id or session_id not in self.sessions:
            new_id = session_id or str(uuid.uuid4())
            self.sessions[new_id] = SessionState(session_id=new_id)
            return self.sessions[new_id]
        return self.sessions[session_id]

    def is_ready(self) -> bool:
        """Check if the app is ready to handle memory operations."""
        return self.initialized and self.agent_engine is not None

    def reset(self) -> None:
        """Reset the application state."""
        self.client = None
        self.agent_engine = None
        self.initialized = False
        self.sessions = {}


# Global application state singleton
app = AppState()
