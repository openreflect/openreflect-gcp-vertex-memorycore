#!/usr/bin/env python3
"""
Memory Bank MCP Server
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.server import run

if __name__ == "__main__":
    run()
