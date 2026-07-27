"""Interactive setup wizard for `tif-ai install` (Phase 4, §5.4)."""

import os
import sys
import json
import subprocess
import logging

from tif_ai.config_dir import write_config, get_config_dir

logger = logging.getLogger(__name__)

PROVIDER_MENU = [
    ("ollama", "Ollama (local, free, private)"),
    ("lmstudio", "LM Studio (local OpenAI-compatible)"),
    ("openrouter", "OpenRouter (cloud, many models)"),
    ("gemini", "Google Gemini"),
    ("openai", "OpenAI"),
    ("azure_openai", "Azure OpenAI"),
    ("custom", "Custom OpenAI-compatible endpoint"),
]


def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{text}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val or default


def _choose(prompt: str, options: list) -> int:
    """Render a numbered menu; return the chosen index."""
    print(prompt)
    for i, (key, desc) in enumerate(options, 1):
        print(f"  {i}. {desc}")
    while True:
        try:
            choice = int(_prompt("Select", "1"))
        except ValueError:
            choice = 0
        if 1 <= choice <= len(options):
            return choice - 1
        print("Invalid selection, try again.")


def detect_environment() -> dict:
    """§5.4 step 1: environment detection (Node.js/Docker optional)."""
    import shutil
    info = {
        "os": sys.platform,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "git": bool(shutil.which("git")),
        "docker": bool(shutil.which("docker")),
        "node": bool(shutil.which("node")),
    }
    print("== Environment detection ==")
    print(f"  OS: {info['os']}")
    print(f"  Python: {info['python']}")
    print(f"  Git: {'yes' if info['git'] else 'no'}")
    print(f"  Docker: {'yes (optional)' if info['docker'] else 'no (optional, not required)'}")
    if not info["node"]:
        print("  Node.js: not found (optional/skippable per Decision C)")
    else:
        print("  Node.js: yes (optional)")
    return info


def configure_mongodb() -> str:
    """§5.4 step 2: request + validate MONGODB_URI."""
    print("\n== MongoDB (external service) ==")
    print("  TIF connects to an existing MongoDB. It does not install MongoDB.")
    uri = _prompt("MONGODB_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    db_name = _prompt("MONGODB_DB_NAME", os.getenv("MONGODB_DB_NAME", "tif"))
    # Validate connectivity.
    os.environ["MONGODB_URI"] = uri
    os.environ["MONGODB_DB_NAME"] = db_name
    ok = False
    try:
        from db.mongo_client import check_connectivity
        ok = check_connectivity()
    except Exception as e:
        print(f"  ! Could not validate: {e}")
    if ok:
        print("  [OK] MongoDB connection OK")
    else:
        print("  ! Could not connect - you can fix the URI later in .env / config.")
    return uri


def configure_ai_provider() -> dict:
    """§5.4 step 3: AI provider selection + per-provider vars."""
    print("\n== AI provider ==")
    idx = _choose("Select an AI provider:", PROVIDER_MENU)
    key, _ = PROVIDER_MENU[idx]
    config = {"AI_PROVIDER": key}
    print(f"  Selected: {key}")
    if key == "ollama":
        config["OLLAMA_HOST"] = _prompt("OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        config["OLLAMA_MODEL"] = _prompt("OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "llama3"))
        _ollama_model_flow(config)
    elif key == "lmstudio":
        config["LMSTUDIO_ENDPOINT"] = _prompt("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1")
        config["LMSTUDIO_MODEL"] = _prompt("LMSTUDIO_MODEL", "")
    elif key == "openrouter":
        config["OPENROUTER_API_KEY"] = _prompt("OPENROUTER_API_KEY", "")
        config["OPENROUTER_MODEL"] = _prompt("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    elif key == "openai":
        config["OPENAI_API_KEY"] = _prompt("OPENAI_API_KEY", "")
        config["OPENAI_MODEL"] = _prompt("OPENAI_MODEL", "gpt-4o-mini")
    elif key == "azure_openai":
        config["AZURE_OPENAI_ENDPOINT"] = _prompt("AZURE_OPENAI_ENDPOINT", "")
        config["AZURE_OPENAI_DEPLOYMENT"] = _prompt("AZURE_OPENAI_DEPLOYMENT", "")
        config["AZURE_OPENAI_API_KEY"] = _prompt("AZURE_OPENAI_API_KEY", "")
        config["AZURE_OPENAI_API_VERSION"] = _prompt("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    elif key == "custom":
        config["CUSTOM_AI_ENDPOINT"] = _prompt("CUSTOM_AI_ENDPOINT", "http://localhost:8000/v1")
        config["CUSTOM_AI_API_KEY"] = _prompt("CUSTOM_AI_API_KEY", "")
        config["CUSTOM_AI_MODEL"] = _prompt("CUSTOM_AI_MODEL", "custom-model")
    elif key == "gemini":
        config["GEMINI_API_KEY"] = _prompt("GEMINI_API_KEY", "")
        config["GEMINI_MODEL_NAME"] = _prompt("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
    config["AI_ENABLED"] = "true"
    return config


def _ollama_model_flow(config: dict):
    """§5.4 step 4: Ollama detect/list/pull models."""
    from tif_ai.ai_ops import pull_model, test_provider
    try:
        res = test_provider("ollama")
        models = res.get("models", [])
        if models:
            print(f"  Installed Ollama models: {', '.join(models)}")
            pick = _prompt("Use one of these? (model name or leave blank to keep selection)", "")
            if pick:
                config["OLLAMA_MODEL"] = pick
                return
        pull = _prompt("Pull a model now? (model name, or blank to skip)", "")
        if pull:
            out = pull_model(pull, config.get("OLLAMA_HOST"))
            print(f"  {out.get('status')}: {out.get('detail')}")
    except Exception as e:
        print(f"  Ollama model step skipped: {e}")


def run_wizard() -> dict:
    """Run the full wizard and return the assembled config dict."""
    print("=== TIF-AI Setup Wizard ===")
    env = detect_environment()
    mongo_uri = configure_mongodb()
    ai_cfg = configure_ai_provider()

    config = {
        "version": 1,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "environment": env,
        "DB_BACKEND": "mongodb",
        "MONGODB_URI": mongo_uri,
        "MONGODB_DB_NAME": os.getenv("MONGODB_DB_NAME", "tif"),
        **ai_cfg,
    }
    # Persist to OS config dir (§5.4 step 5).
    try:
        path = write_config(config)
        print(f"\n[OK] Config written to: {path}")
    except Exception as e:
        print(f"\n! Could not write config dir: {e}")

    # Also write the repo .env so the running app picks it up.
    _write_repo_env(config)
    return config


def _write_repo_env(config: dict):
    """Mirror chosen vars into the repo .env for immediate app use."""
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    keys = set(config.keys())
    out = [ln for ln in lines if ln.strip().split("=", 1)[0] not in keys]
    for k, v in config.items():
        if v not in (None, ""):
            out.append(f"{k}={v}\n")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(out)
        print(f"[OK] Repo .env updated: {env_path}")
    except Exception as e:
        print(f"! Could not write .env: {e}")
