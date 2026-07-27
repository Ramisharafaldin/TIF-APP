"""AI provider operations for `tif-ai ai` subcommands (Phase 4 §5.5, Phase 3)."""

import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

PROVIDERS = ["gemini", "ollama", "lmstudio", "openrouter", "openai", "azure_openai", "custom"]


def list_providers() -> list:
    return list(PROVIDERS)


def current_provider() -> str:
    from utils.ai_config import ai_config
    return ai_config.get_provider_name()


def switch_provider(name: str) -> str:
    """Set AI_PROVIDER in the repo .env (and config dir). Returns status msg."""
    name = (name or "").lower()
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Choices: {', '.join(PROVIDERS)}")
    _set_env_var("AI_PROVIDER", name)
    return f"AI_PROVIDER set to '{name}'. Restart the app / re-run doctor to apply."


def test_provider(name: str = None) -> dict:
    """Validate connectivity + list models for a provider."""
    from ai_providers import get_provider
    provider = name or current_provider()
    p = get_provider(provider)
    ok, msg = p.validate_connection()
    models = []
    try:
        models = p.list_models()
    except Exception as e:
        logger.warning(f"list_models failed: {e}")
    return {
        "provider": provider,
        "connection_ok": ok,
        "message": msg,
        "models": models[:20],
    }


def pull_model(model: str, host: str = None) -> dict:
    """Pull an Ollama model via its REST API (§5.4 step 4)."""
    import requests  # optional; only used for ollama pull
    host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    if not model:
        raise ValueError("model name required for pull")
    url = f"{host.rstrip('/')}/api/pull"
    try:
        resp = requests.post(url, json={"model": model, "stream": False}, timeout=600)
        resp.raise_for_status()
        return {"provider": "ollama", "model": model, "status": "pulled", "detail": "ok"}
    except Exception as e:
        return {"provider": "ollama", "model": model, "status": "error", "detail": str(e)}


def _set_env_var(key: str, value: str):
    """Write/overwrite an env var in the repo .env without clobbering others."""
    path = ".env"
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
