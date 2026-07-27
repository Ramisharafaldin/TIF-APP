"""Health-check suite for `tif-ai doctor` (Phase 4, §5.5)."""

import os
import sys
import shutil
import socket
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CheckResult:
    def __init__(self, name: str, ok: bool, detail: str = "", warning: bool = False):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.warning = warning

    @property
    def status(self) -> str:
        if self.ok:
            return "OK" if not self.warning else "WARN"
        return "FAIL"


def _check_python() -> CheckResult:
    version = sys.version_info
    ok = (version.major, version.minor) >= (3, 8)
    return CheckResult("Python", ok, f"{version.major}.{version.minor}.{version.micro}")


def _check_git() -> CheckResult:
    if shutil.which("git"):
        return CheckResult("Git", True, shutil.which("git"))
    return CheckResult("Git", False, "git not found on PATH", warning=True)


def _check_docker() -> CheckResult:
    if shutil.which("docker"):
        return CheckResult("Docker", True, "available (optional)", warning=True)
    return CheckResult("Docker", True, "not installed (optional, not required)", warning=True)


def _check_node() -> CheckResult:
    # Decision C: optional/skippable future-proofing only.
    if shutil.which("node"):
        return CheckResult("Node.js", True, "available (optional)", warning=True)
    return CheckResult("Node.js", True, "not installed (optional, skippable)", warning=True)


def _check_mongodb() -> CheckResult:
    try:
        from db.mongo_client import check_connectivity, get_mongo_uri
        ok = check_connectivity()
        return CheckResult("MongoDB", ok, get_mongo_uri() if ok else "unreachable")
    except Exception as e:
        return CheckResult("MongoDB", False, str(e))


def _check_ai_provider() -> CheckResult:
    try:
        os.environ.setdefault("AI_ENABLED", "true")
        from utils.ai_config import ai_config
        provider = ai_config.get_provider_name()
        if not os.environ.get("AI_ENABLED", "false").lower() == "true":
            return CheckResult("AI Provider", True, f"{provider} (AI disabled)", warning=True)
        from ai_providers import get_provider
        p = get_provider(provider)
        ok, msg = p.validate_connection()
        detail = f"{provider}: {msg}"
        return CheckResult("AI Provider", ok, detail)
    except Exception as e:
        return CheckResult("AI Provider", False, str(e))


def _check_port(port: int = 5000) -> CheckResult:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        result = s.connect_ex(("127.0.0.1", port))
        # Port open => something is listening; that's fine for a running app.
        if result == 0:
            return CheckResult(f"Port {port}", True, "listening (app may be running)")
        return CheckResult(f"Port {port}", True, "free", warning=True)
    except Exception as e:
        return CheckResult(f"Port {port}", True, f"cannot probe ({e})", warning=True)
    finally:
        s.close()


def _check_disk(min_gb: float = 1.0) -> CheckResult:
    try:
        if hasattr(shutil, "disk_usage"):
            total, used, free = shutil.disk_usage(os.getcwd())
            free_gb = free / (1024 ** 3)
            ok = free_gb >= min_gb
            return CheckResult("Disk space", ok, f"{free_gb:.1f} GB free")
    except Exception as e:
        return CheckResult("Disk space", True, f"cannot probe ({e})", warning=True)
    return CheckResult("Disk space", True, "unknown", warning=True)


def _check_env_file() -> CheckResult:
    if os.path.exists(".env"):
        return CheckResult(".env", True, "present")
    if os.path.exists(".env.example"):
        return CheckResult(".env", False, ".env missing (copy .env.example to .env)", warning=True)
    return CheckResult(".env", False, "no .env or .env.example found")


def _check_agent_protocol() -> CheckResult:
    # Optional: presence of agent protocol docs (§5.5). Non-fatal.
    candidates = [
        "TIF-AI_AGENT_REQUIREMENTS_v1.0.md",
        "agent_protocol.md",
    ]
    found = [c for c in candidates if os.path.exists(c)]
    if found:
        return CheckResult("Agent protocol", True, ", ".join(found), warning=True)
    return CheckResult("Agent protocol", True, "none found (optional)", warning=True)


def run_all_checks() -> list:
    """Run all health checks and return a list of CheckResult."""
    return [
        _check_python(),
        _check_git(),
        _check_docker(),
        _check_node(),
        _check_mongodb(),
        _check_ai_provider(),
        _check_port(5000),
        _check_disk(),
        _check_env_file(),
        _check_agent_protocol(),
    ]


def summarize() -> dict:
    """Return a summary dict with overall status + per-check details."""
    results = run_all_checks()
    failed = [r for r in results if not r.ok]
    overall = "HEALTHY" if not failed else "ISSUES FOUND"
    return {
        "overall": overall,
        "generated_at": datetime.now().isoformat(),
        "checks": [
            {"name": r.name, "status": r.status, "detail": r.detail}
            for r in results
        ],
        "failures": len(failed),
    }
