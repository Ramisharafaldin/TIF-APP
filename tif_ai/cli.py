"""
tif-ai CLI entry point (Phase 4, §5).

Usage:
    tif-ai install          # interactive setup wizard
    tif-ai doctor           # health checks
    tif-ai run              # launch the Flask app (launcher.py)
    tif-ai stop|restart     # process management around the Flask app
    tif-ai status|version   # process + version info
    tif-ai logs             # tail app logs
    tif-ai clean            # clear logs/flask_sessions/temp uploads
    tif-ai reset            # wipe app data (clear_all_data)
    tif-ai backup|restore   # mongodump / mongorestore
    tif-ai test             # run the test suite
    tif-ai config export|import
    tif-ai ai switch|test|models|pull
    tif-ai diagnostics      # wrap utils/diagnostics.py
"""

import os
import sys
import json
import subprocess
import shutil
import signal
import time
import logging

# Ensure the repository root (where `utils`, `db`, `scripts`, `data_store*.py`
# live) is importable even when invoked as an installed console script.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import click
from colorama import init as colorama_init, Fore, Style

import tif_ai
from tif_ai.config_dir import get_config_dir, export_config, import_config
from tif_ai.doctor import run_all_checks, summarize
from tif_ai.ai_ops import list_providers, current_provider, switch_provider, test_provider, pull_model

colorama_init(autoreset=True)

logger = logging.getLogger(__name__)

PID_FILE = os.path.join(get_config_dir(), "tif_ai.pid")
FLASK_PORT = 5000


def _c(text: str, color: str) -> str:
    return f"{color}{text}{Style.RESET_ALL}"


def _echo_status(res) -> int:
    sym = {("OK",): _c("[OK]", Fore.GREEN), ("WARN",): _c("[WARN]", Fore.YELLOW),
           ("FAIL",): _c("[FAIL]", Fore.RED)}.get((res.status,), _c("[?]", Fore.WHITE))
    line = f"  {sym} {res.name:<18} {res.status:<5} {res.detail}"
    try:
        click.echo(line)
    except UnicodeEncodeError:
        click.echo(line.encode("ascii", "replace").decode("ascii"))
    return 0 if res.ok else 1


# ----------------------------------------------------------------------
# Top-level group
# ----------------------------------------------------------------------
@click.group()
@click.version_option(version=tif_ai.__version__, prog_name="tif-ai")
def cli():
    """TIF-AI cross-platform CLI & setup wizard."""


# ----------------------------------------------------------------------
# install (wizard)
# ----------------------------------------------------------------------
@cli.command()
def install():
    """Run the interactive setup wizard (§5.4)."""
    from tif_ai.wizard import run_wizard
    run_wizard()
    click.echo(_c("\nRunning `tif-ai doctor` to verify setup...", Fore.CYAN))
    ctx = click.get_current_context()
    ctx.invoke(doctor)


# ----------------------------------------------------------------------
# doctor
# ----------------------------------------------------------------------
@cli.command()
def doctor():
    """Run health checks (§5.5)."""
    click.echo(_c("=== TIF-AI Doctor ===", Fore.CYAN))
    failures = 0
    for res in run_all_checks():
        failures += _echo_status(res)
    if failures:
        click.echo(_c(f"\n{failures} check(s) failed.", Fore.RED))
        sys.exit(1)
    click.echo(_c("\nAll critical checks passed.", Fore.GREEN))


# ----------------------------------------------------------------------
# run / stop / restart / status / version
# ----------------------------------------------------------------------
@cli.command()
def run():
    """Launch the Flask app (launcher.py)."""
    _clean_stale_pid()
    if _is_running():
        click.echo(_c("TIF-AI appears to be running already.", Fore.YELLOW))
        return
    click.echo(_c("Starting TIF-AI...", Fore.CYAN))
    # Prefer .venv Python (has all dependencies); fall back to sys.executable
    venv_python = os.path.join(_PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable
    click.echo(_c(f"Using Python: {python_exe}", Fore.WHITE))
    try:
        launcher = os.path.join(_PROJECT_ROOT, "launcher.py")
        proc = subprocess.Popen(
            [python_exe, launcher],
            cwd=_PROJECT_ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
        click.echo(_c(f"Started (pid {proc.pid}). Open http://localhost:{FLASK_PORT}", Fore.GREEN))
    except Exception as e:
        click.echo(_c(f"Failed to start: {e}", Fore.RED))


@cli.command()
def stop():
    """Stop the running Flask app."""
    _stop_running()
    click.echo(_c("Stop signal sent.", Fore.GREEN))


@cli.command()
def restart():
    """Restart the Flask app."""
    _stop_running()
    time.sleep(1)
    ctx = click.get_current_context()
    ctx.invoke(run)


def _clean_stale_pid():
    pid = _read_pid()
    if pid is None:
        return
    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_process", f"where processid={pid}", "get", "commandline", "/format:value"],
            stderr=subprocess.DEVNULL, text=True
        )
        if "launcher.py" not in out:
            os.remove(PID_FILE)
    except Exception:
        os.remove(PID_FILE)
        return

def _is_running() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_process", f"where processid={pid}", "get", "commandline", "/format:value"],
            stderr=subprocess.DEVNULL, text=True
        )
        return "launcher.py" in out
    except Exception:
        return False


def _read_pid():
    if os.path.exists(PID_FILE):
        try:
            return int(open(PID_FILE, encoding="utf-8").read().strip())
        except Exception:
            return None
    return None


def _stop_running():
    pid = _read_pid()
    if pid is None:
        click.echo(_c("No running process found.", Fore.YELLOW))
        return
    if not _is_running():
        click.echo(_c("Stale PID file detected. Cleaning up.", Fore.YELLOW))
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


@cli.command()
def status():
    """Show process + version info."""
    running = _is_running()
    click.echo(f"TIF-AI version : {tif_ai.__version__}")
    click.echo(f"Running        : {'yes (pid %s)' % _read_pid() if running else 'no'}")
    click.echo(f"Config dir     : {get_config_dir()}")
    click.echo(f"AI provider    : {current_provider()}")


@cli.command()
def version():
    """Print version info."""
    click.echo(f"tif-ai {tif_ai.__version__}")


# ----------------------------------------------------------------------
# logs / clean
# ----------------------------------------------------------------------
@cli.command()
@click.option("--lines", default=50, help="Number of lines to show.")
def logs(lines):
    """Tail application logs."""
    candidates = ["errors.log", "logs/errors.log"]
    target = next((c for c in candidates if os.path.exists(c)), None)
    if not target:
        click.echo(_c("No log file found (errors.log).", Fore.YELLOW))
        return
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.readlines()[-lines:]
        click.echo("".join(content))
    except Exception as e:
        click.echo(_c(f"Could not read logs: {e}", Fore.RED))


@cli.command()
def clean():
    """Clear logs, flask_sessions, and temp uploads."""
    targets = ["logs", "flask_sessions", "uploads"]
    removed = []
    for t in targets:
        if os.path.isdir(t):
            shutil.rmtree(t, ignore_errors=True)
            removed.append(t)
    if removed:
        click.echo(_c(f"Cleared: {', '.join(removed)}", Fore.GREEN))
    else:
        click.echo(_c("Nothing to clean.", Fore.YELLOW))


# ----------------------------------------------------------------------
# reset
# ----------------------------------------------------------------------
@cli.command()
@click.confirmation_option(prompt="This wipes ALL app data (except users). Continue?")
def reset():
    """Wipe application data via data_store.clear_all_data (§5.5)."""
    try:
        from data_store import get_data_store, clear_all_data
        clear_all_data()
        click.echo(_c("Application data reset.", Fore.GREEN))
    except Exception as e:
        click.echo(_c(f"Reset failed: {e}", Fore.RED))
        sys.exit(1)


# ----------------------------------------------------------------------
# backup / restore
# ----------------------------------------------------------------------
@cli.command()
@click.option("--out", default="tif_backup", help="Output directory for the dump.")
def backup(out):
    """Backup MongoDB via mongodump (§5.1, §5.5)."""
    if not shutil.which("mongodump"):
        click.echo(_c("mongodump not found. Install MongoDB Database Tools.", Fore.RED))
        sys.exit(1)
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db = os.getenv("MONGODB_DB_NAME", "tif")
    cmd = ["mongodump", f"--uri={uri}", f"--db={db}", f"--out={out}"]
    click.echo(_c(f"Backing up {db} to {out}...", Fore.CYAN))
    rc = subprocess.call(cmd)
    sys.exit(rc)


@cli.command()
@click.option("--in", "src", default="tif_backup", help="Dump directory to restore.")
def restore(src):
    """Restore MongoDB via mongorestore (§5.1, §5.5)."""
    if not shutil.which("mongorestore"):
        click.echo(_c("mongorestore not found. Install MongoDB Database Tools.", Fore.RED))
        sys.exit(1)
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db = os.getenv("MONGODB_DB_NAME", "tif")
    cmd = ["mongorestore", f"--uri={uri}", f"--db={db}", f"{src}/{db}"]
    click.echo(_c(f"Restoring {db} from {src}...", Fore.CYAN))
    rc = subprocess.call(cmd)
    sys.exit(rc)


# ----------------------------------------------------------------------
# test
# ----------------------------------------------------------------------
@cli.command()
def test():
    """Run the test suite (test_*.py)."""
    tests = [f for f in os.listdir(".") if f.startswith("test_") and f.endswith(".py")]
    if not tests:
        click.echo(_c("No test_*.py files found.", Fore.YELLOW))
        return
    rc = subprocess.call([sys.executable, "-m", "pytest", "-q"] + tests)
    sys.exit(rc)


# ----------------------------------------------------------------------
# config
# ----------------------------------------------------------------------
@cli.group()
def config():
    """Export/import the OS config directory (§5.3)."""


@config.command("export")
@click.argument("dest")
def config_export(dest):
    """Export config to DEST path."""
    try:
        path = export_config(dest)
        click.echo(_c(f"Exported config to {path}", Fore.GREEN))
    except Exception as e:
        click.echo(_c(str(e), Fore.RED))
        sys.exit(1)


@config.command("import")
@click.argument("src")
def config_import(src):
    """Import config from SRC path."""
    try:
        path = import_config(src)
        click.echo(_c(f"Imported config to {path}", Fore.GREEN))
    except Exception as e:
        click.echo(_c(str(e), Fore.RED))
        sys.exit(1)


# ----------------------------------------------------------------------
# ai (provider ops)
# ----------------------------------------------------------------------
@cli.group()
def ai():
    """AI provider operations (Phase 3 abstraction)."""


@ai.command("switch")
@click.argument("provider")
def ai_switch(provider):
    """Switch the active AI provider."""
    try:
        msg = switch_provider(provider)
        click.echo(_c(msg, Fore.GREEN))
    except ValueError as e:
        click.echo(_c(str(e), Fore.RED))
        sys.exit(1)


@ai.command("test")
@click.argument("provider", required=False)
def ai_test(provider):
    """Validate connectivity + list models for a provider."""
    res = test_provider(provider)
    click.echo(f"Provider : {res['provider']}")
    click.echo(f"Connected: {'yes' if res['connection_ok'] else 'no'}")
    click.echo(f"Message  : {res['message']}")
    if res["models"]:
        click.echo("Models   : " + ", ".join(res["models"]))


@ai.command("models")
def ai_models():
    """List available provider names."""
    for p in list_providers():
        mark = " *" if p == current_provider() else ""
        click.echo(f"  {p}{mark}")


@ai.command("pull")
@click.argument("model")
@click.option("--host", default=None, help="Ollama host (overrides OLLAMA_HOST).")
def ai_pull(model, host):
    """Pull an Ollama model."""
    out = pull_model(model, host)
    click.echo(_c(f"{out['status']}: {out.get('detail')}", Fore.GREEN if out["status"] == "pulled" else Fore.RED))


# ----------------------------------------------------------------------
# diagnostics
# ----------------------------------------------------------------------
@cli.command()
def diagnostics():
    """Run utils/diagnostics.py checks."""
    try:
        from utils.diagnostics import run_diagnostics
        result = run_diagnostics()
        click.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        # Fallback: run as a subprocess if diagnostics exposes a CLI.
        click.echo(_c(f"Diagnostics module unavailable ({e}); trying script.", Fore.YELLOW))
        if os.path.exists("utils/diagnostics.py"):
            rc = subprocess.call([sys.executable, "utils/diagnostics.py"])
            sys.exit(rc)
        sys.exit(1)


# ----------------------------------------------------------------------
# user management
# ----------------------------------------------------------------------
@cli.group()
def user():
    """User management (list, reset-password, create)."""


@user.command("list")
def user_list():
    """List all users."""
    try:
        from db.mongo_client import get_database
        db = get_database()
        count = db.users.count_documents({})
        if count == 0:
            click.echo(_c("No users found.", Fore.YELLOW))
            return
        click.echo(_c(f"{'Username':<20} {'Admin':<8} {'Role':<15}", Fore.CYAN))
        click.echo("-" * 45)
        for u in db.users.find({}, {"username": 1, "is_admin": 1, "role": 1, "_id": 0}).sort("username"):
            role = u.get("role", "") or ""
            click.echo(f"{u['username']:<20} {str(u.get('is_admin', False)):<8} {role:<15}")
    except Exception as e:
        click.echo(_c(f"Failed to list users: {e}", Fore.RED))
        sys.exit(1)


@user.command("reset-password")
@click.argument("username")
@click.argument("new_password")
def user_reset_password(username, new_password):
    """Reset password for USERNAME to NEW_PASSWORD."""
    try:
        os.environ.setdefault("DB_BACKEND", "mongodb")
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
        import auth_flask
        ok, msg = auth_flask.change_password(username, new_password)
        if ok:
            click.echo(_c(f"Password changed for '{username}'.", Fore.GREEN))
        else:
            click.echo(_c(msg, Fore.RED))
            sys.exit(1)
    except Exception as e:
        click.echo(_c(f"Failed to reset password: {e}", Fore.RED))
        sys.exit(1)


@user.command("create")
@click.argument("username")
@click.argument("password")
@click.option("--admin", is_flag=True, help="Grant admin privileges.")
@click.option("--role", default=None, help="RBAC role (viewer, analyst, admin, superadmin).")
def user_create(username, password, admin, role):
    """Create a new user with USERNAME and PASSWORD."""
    try:
        import auth_flask
        ok, msg = auth_flask.add_user(username, password, is_admin=admin, role=role)
        if ok:
            click.echo(_c(f"User '{username}' created.", Fore.GREEN))
        else:
            click.echo(_c(msg, Fore.RED))
            sys.exit(1)
    except Exception as e:
        click.echo(_c(f"Failed to create user: {e}", Fore.RED))
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
