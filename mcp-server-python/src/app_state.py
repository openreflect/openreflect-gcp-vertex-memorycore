"""Application state management"""

from typing import Any, Optional

from .config import Config


class AppState:
    """Simple application state container following the Zen: "Simple is better than complex"."""

    def __init__(self):
        self.client: Optional[Any] = None
        self.agent_engine: Optional[Any] = None
        self.config: Config = Config()
        self.initialized: bool = False

    def is_ready(self) -> bool:
        """Check if the app is ready to handle memory operations."""
        return self.initialized and self.agent_engine is not None

    def reset(self) -> None:
        """Reset the application state."""
        self.client = None
        self.agent_engine = None
        self.initialized = False


# Global application state
app = AppState()
