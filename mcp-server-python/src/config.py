"""Configuration module"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file (only if file exists, for local development)
# Cloud Run uses environment variables directly, so .env is optional
if os.path.exists(".env"):
    load_dotenv()


class Config(BaseModel):
    """Simple configuration with sensible defaults and validation."""

    project_id: str = Field(default="", description="Google Cloud Project ID")
    location: str = Field(
        default="us-central1", description="Google Cloud location for Vertex AI"
    )
    agent_engine_name: Optional[str] = Field(
        default=None, description="Existing Agent Engine resource name"
    )
    api_key: Optional[str] = Field(
        default=None, description="Google API key for authentication"
    )
    connector_bearer_token: Optional[str] = Field(
        default=None,
        description="Optional bearer token for HTTPS/SSE connector authentication",
    )

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            agent_engine_name=os.getenv("AGENT_ENGINE_NAME"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            connector_bearer_token=os.getenv("CONNECTOR_BEARER_TOKEN"),
        )

    def is_valid(self) -> bool:
        """Check if configuration is valid for initialization."""
        # Valid if we can authenticate to GCP; Agent Engine may be created later
        return bool(self.project_id or self.api_key)
