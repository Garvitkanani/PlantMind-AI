"""
System self-check utilities for startup/runtime diagnostics.
"""

import json
import os
from typing import Dict, Tuple
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from src.database.connection import SessionLocal
from src.scheduler import get_scheduler_status


def _status(ok: bool, message: str, details: Dict | None = None) -> Dict:
    return {"ok": ok, "message": message, "details": details or {}}


def check_database() -> Dict:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return _status(True, "Database reachable")
    except Exception as exc:
        return _status(False, f"Database check failed: {exc}")
    finally:
        db.close()


def _ollama_tags_url() -> Tuple[str, str]:
    api_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    parsed = urlparse(api_url)
    tags_url = f"{parsed.scheme}://{parsed.netloc}/api/tags"
    return api_url, tags_url


def check_ollama() -> Dict:
    expected_model = os.environ.get("OLLAMA_MODEL", "phi3:mini")
    api_url, tags_url = _ollama_tags_url()
    try:
        response = httpx.get(tags_url, timeout=8)
        response.raise_for_status()
        payload = response.json()
        models = [m.get("name") for m in payload.get("models", [])]
        has_model = expected_model in models
        return _status(
            has_model,
            "Ollama reachable and model available"
            if has_model
            else f"Ollama reachable but model '{expected_model}' not found",
            {"api_url": api_url, "tags_url": tags_url, "expected_model": expected_model, "models": models},
        )
    except Exception as exc:
        return _status(False, f"Ollama check failed: {exc}", {"api_url": api_url, "tags_url": tags_url, "expected_model": expected_model})


def check_gmail_reader() -> Dict:
    token_path = os.environ.get("GMAIL_TOKEN_PATH", "config/token.json")
    creds_path = os.environ.get("GMAIL_CLIENT_SECRET", "config/credentials.json")

    creds_exists = os.path.exists(creds_path)
    token_exists = os.path.exists(token_path)

    if not creds_exists:
        return _status(False, f"Gmail reader credentials missing: {creds_path}")

    # Token may be created after first auth flow, so treat missing token as degraded.
    if not token_exists:
        return _status(False, "Gmail reader token missing (auth not completed yet)", {"credentials_path": creds_path, "token_path": token_path})

    # Validate token JSON shape quickly.
    try:
        with open(token_path, "r", encoding="utf-8") as token_file:
            token_data = json.load(token_file)
        required_keys = {"client_id", "client_secret", "refresh_token"}
        has_keys = all(token_data.get(k) for k in required_keys)
        if not has_keys:
            return _status(False, "Gmail reader token exists but appears incomplete", {"token_path": token_path})
    except Exception as exc:
        return _status(False, f"Gmail reader token parse failed: {exc}", {"token_path": token_path})

    return _status(True, "Gmail reader configuration looks valid", {"credentials_path": creds_path, "token_path": token_path})


def check_gmail_sender() -> Dict:
    smtp_user = os.environ.get("GMAIL_SMTP_EMAIL") or os.environ.get("GMAIL_SENDER_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not smtp_user or not app_password:
        return _status(
            False,
            "Gmail sender not fully configured (set GMAIL_SMTP_EMAIL and GMAIL_APP_PASSWORD)",
            {"smtp_user_set": bool(smtp_user), "app_password_set": bool(app_password)},
        )

    return _status(True, "Gmail sender configuration present", {"smtp_user_set": True, "app_password_set": True})


def run_system_self_check() -> Dict:
    checks = {
        "database": check_database(),
        "ollama": check_ollama(),
        "gmail_reader": check_gmail_reader(),
        "gmail_sender": check_gmail_sender(),
        "scheduler": _status(True, "Scheduler status collected", get_scheduler_status()),
    }
    all_ok = all(item.get("ok", False) for item in checks.values())
    return {
        "ok": all_ok,
        "checks": checks,
    }
