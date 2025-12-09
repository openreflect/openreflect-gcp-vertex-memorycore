"""Data formatting utilities"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def format_memory(memory: Any) -> Dict[str, Any]:
    """
    Format a memory object consistently.

    Args:
        memory: Raw memory object from Vertex AI

    Returns:
        Formatted memory dictionary
    """
    return {
        "name": getattr(memory, "name", None),
        "fact": getattr(memory, "fact", None),
        "scope": getattr(memory, "scope", None),
        "created_time": str(getattr(memory, "created_time", None)),
        "updated_time": str(getattr(memory, "updated_time", None)),
    }


def format_conversation_events(conversation: List[Dict[str, str]]) -> List[Dict]:
    """
    Convert conversation to Vertex AI events format.

    Args:
        conversation: List of conversation turns

    Returns:
        List of events in Vertex AI format
    """
    events = []
    for turn in conversation:
        events.append(
            {"content": {"role": turn["role"], "parts": [{"text": turn["content"]}]}}
        )
    return events


def format_ttl_expiration(ttl_seconds: int) -> str:
    """
    Calculate expiration time from TTL.

    Args:
        ttl_seconds: Time to live in seconds

    Returns:
        ISO format expiration string
    """
    expiration = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return expiration.isoformat().replace("+00:00", "Z")


def format_error_response(error: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Format error response consistently.

    Args:
        error: Error message
        details: Optional additional details

    Returns:
        Formatted error response
    """
    response = {"status": "error", "error": error}
    if details:
        response["details"] = details
    return response


def format_success_response(
    data: Dict[str, Any] = None, message: str = None
) -> Dict[str, Any]:
    """
    Format success response consistently.

    Args:
        data: Response data
        message: Optional success message

    Returns:
        Formatted success response
    """
    response = {"status": "success"}
    if message:
        response["message"] = message
    if data:
        response.update(data)
    return response
