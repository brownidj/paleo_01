import os
import tkinter as tk
from pathlib import Path

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
    auth_client = ApiAuthClient(base_url=api_base_url, verify_tls=verify_tls)
    login_root = tk.Tk()
    login_root.withdraw()
    if not login_interactive(auth_client, login_root):
        login_root.destroy()
        return
    login_root.destroy()

    app = PlanningPhaseWindow(auth_client=auth_client, db_backend=db_backend)
    app.mainloop()
