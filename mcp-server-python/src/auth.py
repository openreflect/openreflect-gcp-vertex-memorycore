"""Authentication and identity derivation logic."""

import hashlib
from typing import Optional


def derive_user_id_from_google(google_sub: str, secret: str) -> str:
    """
    Derive a stable user_id from Google's stable user ID (sub claim).
    
    Args:
        google_sub: The 'sub' claim from Google's ID token.
        secret: Server-side secret (IDENTITY_SECRET).
        
    Returns:
        Deterministic user_id: "usr_" + 16 hex chars.
    """
    hash_input = f"google:{google_sub}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"


def derive_user_id_from_key(key: str, secret: str) -> str:
    """
    Derive a deterministic user_id from a key (passphrase).
    
    Args:
        key: User-provided key/passphrase (case-insensitive).
        secret: Server-side secret (IDENTITY_SECRET).
        
    Returns:
        Deterministic user_id: "usr_" + 16 hex chars.
    """
    # Normalize: lowercase, strip whitespace
    normalized = key.lower().strip()
    
    # Hash with secret to prevent rainbow table attacks
    # Using 'passphrase:' prefix to maintain backwards compatibility with existing hashes
    hash_input = f"passphrase:{normalized}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    
    # Take first 8 bytes (16 hex chars) for user_id
    return f"usr_{hash_bytes[:8].hex()}"
