import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from app.api_auth import ApiAuthClient
from ui.login_dialog import login_interactive
from ui.planning_phase_window import PlanningPhaseWindow


def _load_dotenv_if_present() -> None:
    project_root = Path(__file__).resolve().parents[1]
    candidates = [project_root / "config" / "env" / "local.env", project_root / ".env"]
    env_path = next((path for path in candidates if path.exists()), None)
    if env_path is None:
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def run_planning_phase_app() -> None:
    _load_dotenv_if_present()
    api_base_url = os.getenv("PALEO_API_BASE_URL", "https://localhost").strip()
    verify_tls = os.getenv("PALEO_API_VERIFY_TLS", "0").strip().lower() in {"1", "true", "yes", "on"}
    db_backend = os.getenv("PALEO_DESKTOP_DB_BACKEND", "postgres").strip().lower()
    desktop_database_url = os.getenv("PALEO_DESKTOP_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()

    redacted_database_url = _redact_db_url(desktop_database_url)
    print(
        f"[paleo.desktop] resolved_backend={db_backend} "
        f"resolved_database_url={redacted_database_url or '(not set)'}",
        flush=True,
    )

    auth_client = ApiAuthClient(base_url=api_base_url, verify_tls=verify_tls)
    app = PlanningPhaseWindow(auth_client=auth_client, db_backend=db_backend)
    app.withdraw()
    if not login_interactive(auth_client, app):
        app.destroy()
        return
    app.deiconify()
    app.mainloop()


def _redact_db_url(value: str) -> str:
    if not value:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<invalid>"
    netloc = parts.netloc
    if "@" in netloc:
        user_info, host_part = netloc.rsplit("@", 1)
        if ":" in user_info:
            username = user_info.split(":", 1)[0]
            netloc = f"{username}:***@{host_part}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
