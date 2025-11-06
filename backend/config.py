"""Configuration management from environment variables"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
_ = load_dotenv()

# FastAPI configuration
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

# mitmproxy configuration
MITMPROXY_PORT = int(os.getenv("MITMPROXY_PORT", "8080"))

# Database configuration
DB_PATH = os.getenv("DB_PATH", "firewall.db")
DB_URL = f"sqlite:///{DB_PATH}"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Rules file path
RULES_FILE = os.getenv("RULES_FILE", "rules.json")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
