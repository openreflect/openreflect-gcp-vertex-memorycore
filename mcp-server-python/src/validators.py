"""Input validation utilities"""

from typing import Dict, List, Optional


def validate_scope(scope: Dict[str, str]) -> Optional[str]:
    """
    Validate scope dictionary format.
    
    Args:
        scope: Dictionary with string keys and values
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(scope, dict):
        return "Scope must be a dictionary"
    
    if not scope:
        return "Scope cannot be empty"
    
    for key, value in scope.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return f"Scope keys and values must be strings: {key}={value}"
    
    return None


def validate_conversation(conversation: List[Dict[str, str]]) -> Optional[str]:
    """
    Validate conversation format.
    
    Args:
        conversation: List of conversation turns
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(conversation, list):
        return "Conversation must be a list"
    
    if not conversation:
        return "Conversation cannot be empty"
    
    valid_roles = {"user", "assistant", "system"}
    
    for i, turn in enumerate(conversation):
        if not isinstance(turn, dict):
            return f"Turn {i} must be a dictionary"
        
        if "role" not in turn:
            return f"Turn {i} missing 'role' field"
        
        if "content" not in turn:
            return f"Turn {i} missing 'content' field"
        
        if turn["role"] not in valid_roles:
            return f"Turn {i} has invalid role: {turn['role']}"
    
    return None


def validate_memory_fact(fact: str) -> Optional[str]:
    """
    Validate memory fact content.
    
    Args:
        fact: The fact to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    if not fact or not fact.strip():
        return "Fact cannot be empty"
    
    if len(fact) > 10000:  # Reasonable limit
        return f"Fact too long: {len(fact)} characters (max 10000)"
    
    return None