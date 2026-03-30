import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit


class MaintenanceDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, sqlite_db_path: Path, postgres_url: str):
        super().__init__(parent)
        self.title("Maintenance")
        self.transient(parent)
        self.grab_set()
        self.geometry("760x460")
        self.minsize(700, 420)

        self._sqlite_db_path = sqlite_db_path
        self._postgres_url = postgres_url.strip()
        self._running = False
        self._last_backup_file: Path | None = None

        default_backup_dir = (Path(__file__).resolve().parents[1] / "data" / "backups").resolve()
        self._dest_dir_var = tk.StringVar(value=str(default_backup_dir))
        self._status_var = tk.StringVar(value="No backups run yet.")
        self._restore_confirm_var = tk.StringVar(value="")
        self._restore_source_var = tk.StringVar(value="")
        default_target = "Postgres" if self._postgres_url else "SQLite"
        self._restore_target_var = tk.StringVar(value=default_target)
        self._restore_state_var = tk.StringVar(value="Restore requires typing RESTORE and runs a safety backup first.")

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text="Backups", font=("Helvetica", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        ttk.Label(outer, text="Destination").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Entry(outer, textvariable=self._dest_dir_var).grid(row=1, column=1, sticky="ew", pady=(0, 6), padx=(8, 8))
        ttk.Button(outer, text="Browse...", command=self._choose_destination).grid(row=1, column=2, sticky="e", pady=(0, 6))

        backup_buttons = ttk.Frame(outer)
        backup_buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 12))
        self._backup_sqlite_btn = ttk.Button(
            backup_buttons,
            text="Backup SQLite",
            command=lambda: self._run_backup_async("sqlite"),
        )
        self._backup_sqlite_btn.pack(side="left", padx=(0, 8))
        self._backup_postgres_btn = ttk.Button(
            backup_buttons,
            text="Backup Postgres",
            command=lambda: self._run_backup_async("postgres"),
        )
        self._backup_postgres_btn.pack(side="left", padx=(0, 8))
        self._backup_both_btn = ttk.Button(
            backup_buttons,
            text="Backup Both",
            command=lambda: self._run_backup_async("both"),
        )
        self._backup_both_btn.pack(side="left")

        ttk.Separator(outer, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(outer, text="Last backup", font=("Helvetica", 12, "bold")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        ttk.Label(outer, textvariable=self._status_var, justify="left").grid(row=5, column=0, columnspan=3, sticky="w")

        ttk.Separator(outer, orient="horizontal").grid(row=6, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(outer, text="Restore", font=("Helvetica", 12, "bold")).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        ttk.Label(
            outer,
            text="Danger zone. Restoring can overwrite data. A safety backup runs automatically before restore.",
            foreground="#8A2E2E",
        ).grid(row=8, column=0, columnspan=3, sticky="w")
        ttk.Label(outer, text="Source file").grid(row=9, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(outer, textvariable=self._restore_source_var).grid(row=9, column=1, sticky="ew", pady=(8, 0), padx=(8, 8))
        ttk.Button(outer, text="Browse...", command=self._choose_restore_source).grid(row=9, column=2, sticky="e", pady=(8, 0))
        ttk.Label(outer, text="Target").grid(row=10, column=0, sticky="w", pady=(8, 0))
        self._restore_target_combo = ttk.Combobox(
            outer,
            textvariable=self._restore_target_var,
            values=["SQLite", "Postgres"],
            state="readonly",
            width=16,
        )
        self._restore_target_combo.grid(row=10, column=1, sticky="w", pady=(8, 0), padx=(8, 0))
        ttk.Label(outer, text="Type RESTORE").grid(row=11, column=0, sticky="w", pady=(8, 0))
        restore_entry = ttk.Entry(outer, textvariable=self._restore_confirm_var, width=24)
        restore_entry.grid(row=11, column=1, sticky="w", pady=(8, 0), padx=(8, 0))
        self._restore_button = ttk.Button(outer, text="Restore", command=self._run_restore_async, state="disabled")
        self._restore_button.grid(row=11, column=2, sticky="e", pady=(8, 0))
        ttk.Label(outer, textvariable=self._restore_state_var).grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 0))

        footer = ttk.Frame(outer)
        footer.grid(row=13, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
        self._restore_confirm_var.trace_add("write", lambda *_args: self._update_restore_button_state())
        self._restore_source_var.trace_add("write", lambda *_args: self._update_restore_button_state())
        self._restore_target_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_restore_button_state(), add="+")
        self._update_restore_button_state()
        self._refresh_last_backup_status()

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            initialdir=self._dest_dir_var.get() or str(Path.cwd()),
            mustexist=False,
            title="Choose backup destination",
        )
        if selected:
            self._dest_dir_var.set(selected)
            self._refresh_last_backup_status()

    def _set_backup_buttons_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._backup_sqlite_btn.configure(state=state)
        self._backup_postgres_btn.configure(state=state)
        self._backup_both_btn.configure(state=state)

    def _update_restore_button_state(self) -> None:
        if self._running:
            self._restore_button.configure(state="disabled")
            return
        source_text = self._restore_source_var.get().strip()
        has_source = bool(source_text and Path(source_text).expanduser().exists())
        confirmed = self._restore_confirm_var.get().strip().upper() == "RESTORE"
        target = self._restore_target_var.get().strip()
        target_ok = target in {"SQLite", "Postgres"}
        postgres_ok = target != "Postgres" or bool(self._postgres_url)
        state = "normal" if has_source and confirmed and target_ok and postgres_ok else "disabled"
        self._restore_button.configure(state=state)
        if target == "Postgres" and not self._postgres_url:
            self._restore_state_var.set("Postgres URL not configured. Set PALEO_DESKTOP_DATABASE_URL or DATABASE_URL.")
        elif not confirmed:
            self._restore_state_var.set("Type RESTORE to enable restore.")
        elif not has_source:
            self._restore_state_var.set("Choose a restore source file.")
        else:
            self._restore_state_var.set("Restore will create a pre-restore safety backup first.")

    def _choose_restore_source(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            initialdir=self._dest_dir_var.get() or str(Path.cwd()),
            title="Select restore source file",
            filetypes=(
                ("SQL and DB files", "*.sql *.db *.sqlite *.sqlite3"),
                ("All files", "*.*"),
            ),
        )
        if selected:
            self._restore_source_var.set(selected)

    def _run_backup_async(self, mode: str) -> None:
        if self._running:
            return
        destination = Path(self._dest_dir_var.get().strip() or ".").expanduser()
        if not destination:
            messagebox.showerror("Backup", "Choose a backup destination.")
            return

        self._running = True
        self._set_backup_buttons_state(False)
        self._update_restore_button_state()
        self._status_var.set("Running backup...")
        result_queue: queue.Queue[tuple[list[Path], str | None]] = queue.Queue(maxsize=1)
        thread = threading.Thread(target=self._run_backup_worker, args=(mode, destination, result_queue), daemon=True)
        thread.start()
        self.after(100, lambda: self._poll_backup_result(result_queue))

    def _poll_backup_result(self, result_queue: queue.Queue[tuple[list[Path], str | None]]) -> None:
        try:
            outputs, error_text = result_queue.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, lambda: self._poll_backup_result(result_queue))
            return
        self._finish_backup(outputs, error_text)

    def _run_backup_worker(
        self,
        mode: str,
        destination: Path,
        result_queue: queue.Queue[tuple[list[Path], str | None]],
    ) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        outputs: list[Path] = []
        error_text: str | None = None
        try:
            destination.mkdir(parents=True, exist_ok=True)
            if mode in {"sqlite", "both"}:
                outputs.append(_backup_sqlite(self._sqlite_db_path, destination, timestamp))
            if mode in {"postgres", "both"}:
                if not self._postgres_url:
                    raise RuntimeError("Postgres URL is not configured (PALEO_DESKTOP_DATABASE_URL/DATABASE_URL).")
                outputs.append(_backup_postgres(self._postgres_url, destination, timestamp))
        except Exception as exc:
            error_text = str(exc)
        result_queue.put((outputs, error_text))

    def _finish_backup(self, outputs: list[Path], error_text: str | None) -> None:
        self._running = False
        self._set_backup_buttons_state(True)
        self._update_restore_button_state()
        if error_text:
            self._status_var.set(f"Backup failed: {error_text}")
            messagebox.showerror("Backup Failed", error_text)
            return
        if not outputs:
            self._status_var.set("No backup files created.")
            return
        self._last_backup_file = outputs[-1]
        lines = [f"- {path.name} ({_human_size(path.stat().st_size)})" for path in outputs if path.exists()]
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._status_var.set(f"Success at {started}\n" + "\n".join(lines))
        messagebox.showinfo("Backup Complete", "\n".join(str(path) for path in outputs))
        self._refresh_last_backup_status()

    def _run_restore_async(self) -> None:
        if self._running:
            return
        source_path = Path(self._restore_source_var.get().strip()).expanduser()
        target = self._restore_target_var.get().strip()
        if not source_path.exists():
            messagebox.showerror("Restore", f"Restore source not found:\n{source_path}")
            return
        if target not in {"SQLite", "Postgres"}:
            messagebox.showerror("Restore", "Choose a valid restore target.")
            return
        if target == "Postgres" and not self._postgres_url:
            messagebox.showerror("Restore", "Postgres URL is not configured.")
            return
        if self._restore_confirm_var.get().strip().upper() != "RESTORE":
            messagebox.showerror("Restore", "Type RESTORE to continue.")
            return
        destination = Path(self._dest_dir_var.get().strip() or ".").expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        proceed = messagebox.askyesno(
            "Confirm Restore",
            f"This will restore {target} from:\n{source_path}\n\n"
            f"A safety backup will be created first in:\n{destination}\n\nContinue?",
            icon="warning",
            parent=self,
        )
        if not proceed:
            return

        self._running = True
        self._set_backup_buttons_state(False)
        self._update_restore_button_state()
        self._status_var.set(f"Running {target} restore...")
        result_queue: queue.Queue[tuple[str, Path, Path | None, str | None]] = queue.Queue(maxsize=1)
        thread = threading.Thread(
            target=self._run_restore_worker,
            args=(target, source_path, destination, result_queue),
            daemon=True,
        )
        thread.start()
        self.after(100, lambda: self._poll_restore_result(result_queue))

    def _poll_restore_result(self, result_queue: queue.Queue[tuple[str, Path, Path | None, str | None]]) -> None:
        try:
            target, source_path, safety_backup_path, error_text = result_queue.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, lambda: self._poll_restore_result(result_queue))
            return
        self._finish_restore(target, source_path, safety_backup_path, error_text)

    def _run_restore_worker(
        self,
        target: str,
        source_path: Path,
        destination: Path,
        result_queue: queue.Queue[tuple[str, Path, Path | None, str | None]],
    ) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup_path: Path | None = None
        error_text: str | None = None
        try:
            if target == "SQLite":
                safety_backup_path = _backup_sqlite(self._sqlite_db_path, destination, f"{timestamp}_pre_restore")
                _restore_sqlite(source_path, self._sqlite_db_path)
            else:
                safety_backup_path = _backup_postgres(self._postgres_url, destination, f"{timestamp}_pre_restore")
                _restore_postgres(source_path, self._postgres_url)
        except Exception as exc:
            error_text = str(exc)
        result_queue.put((target, source_path, safety_backup_path, error_text))

    def _finish_restore(
        self,
        target: str,
        source_path: Path,
        safety_backup_path: Path | None,
        error_text: str | None,
    ) -> None:
        self._running = False
        self._set_backup_buttons_state(True)
        self._update_restore_button_state()
        if error_text:
            self._status_var.set(f"Restore failed: {error_text}")
            messagebox.showerror("Restore Failed", error_text)
            return
        backup_note = f"\nSafety backup: {safety_backup_path}" if safety_backup_path else ""
        self._status_var.set(f"Restore complete for {target} from {source_path.name}.{backup_note}")
        messagebox.showinfo(
            "Restore Complete",
            f"Restored {target} from:\n{source_path}\n{backup_note}",
        )

    def _refresh_last_backup_status(self) -> None:
        destination = Path(self._dest_dir_var.get().strip() or ".").expanduser()
        if not destination.exists() or not destination.is_dir():
            self._status_var.set(f"No backups found in {destination}")
            return
        patterns = ("sqlite_*.db", "postgres_*.sql")
        backup_files: list[Path] = []
        for pattern in patterns:
            backup_files.extend(destination.glob(pattern))
        backup_files = [path for path in backup_files if path.is_file()]
        if not backup_files:
            self._status_var.set(f"No backups found in {destination}")
            return
        backup_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        latest = backup_files[0]
        latest_mtime = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        self._last_backup_file = latest
        self._status_var.set(
            f"Latest backup: {latest.name} ({_human_size(latest.stat().st_size)}) at {latest_mtime}\n"
            f"Found {len(backup_files)} backup file(s) in {destination}"
        )


def _backup_sqlite(sqlite_db_path: Path, destination: Path, timestamp: str) -> Path:
    source = sqlite_db_path.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"SQLite database not found: {source}")
    target = destination / f"sqlite_{source.stem}_{timestamp}.db"
    with sqlite3.connect(source) as src_conn, sqlite3.connect(target) as dst_conn:
        src_conn.backup(dst_conn)
        cursor = dst_conn.execute("PRAGMA quick_check")
        row = cursor.fetchone()
        result = row[0] if row else ""
        if str(result).lower() != "ok":
            raise RuntimeError(f"SQLite quick_check failed for backup: {result}")
    return target


def _backup_postgres(database_url: str, destination: Path, timestamp: str) -> Path:
    parts = urlsplit(database_url)
    db_name = parts.path.strip("/") or "postgres"
    target = destination / f"postgres_{db_name}_{timestamp}.sql"

    pg_dump_path = shutil.which("pg_dump")
    if pg_dump_path:
        cmd = [
            pg_dump_path,
            "--no-owner",
            "--no-privileges",
            "--encoding=UTF8",
            "--file",
            str(target),
            database_url,
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip() or "pg_dump failed."
            raise RuntimeError(details)
        return target

    docker_path = shutil.which("docker")
    username = parts.username or os.getenv("POSTGRES_USER", "paleo")
    password = parts.password or os.getenv("POSTGRES_PASSWORD", "")
    if docker_path and username:
        cmd = [
            docker_path,
            "exec",
            "-e",
            f"PGPASSWORD={password}",
            "paleo_postgres",
            "pg_dump",
            "-h",
            "localhost",
            "-U",
            username,
            "-d",
            db_name,
            "--no-owner",
            "--no-privileges",
            "--encoding=UTF8",
        ]
        with target.open("wb") as out_fp:
            completed = subprocess.run(cmd, stdout=out_fp, stderr=subprocess.PIPE, check=False)
        if completed.returncode != 0:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            error_text = completed.stderr.decode("utf-8", errors="replace").strip() or "docker pg_dump failed."
            raise RuntimeError(error_text)
        return target

    raise RuntimeError("Postgres backup requires 'pg_dump' (preferred) or Docker access to container 'paleo_postgres'.")


def _restore_sqlite(source_path: Path, target_db_path: Path) -> None:
    source = source_path.expanduser().resolve()
    target = target_db_path.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"SQLite restore source not found: {source}")
    with sqlite3.connect(source) as src_conn:
        check = src_conn.execute("PRAGMA quick_check").fetchone()
        check_value = check[0] if check else ""
        if str(check_value).lower() != "ok":
            raise RuntimeError(f"Restore source failed SQLite quick_check: {check_value}")
        with sqlite3.connect(target) as dst_conn:
            src_conn.backup(dst_conn)
            dst_check = dst_conn.execute("PRAGMA quick_check").fetchone()
            dst_value = dst_check[0] if dst_check else ""
            if str(dst_value).lower() != "ok":
                raise RuntimeError(f"Restored SQLite DB failed quick_check: {dst_value}")


def _restore_postgres(source_path: Path, database_url: str) -> None:
    source = source_path.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"Postgres restore source not found: {source}")
    parts = urlsplit(database_url)
    db_name = parts.path.strip("/") or "postgres"
    username = parts.username or os.getenv("POSTGRES_USER", "paleo")
    password = parts.password or os.getenv("POSTGRES_PASSWORD", "")
    reset_sql = "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

    psql_path = shutil.which("psql")
    if psql_path:
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
        reset_cmd = [psql_path, database_url, "-v", "ON_ERROR_STOP=1", "-c", reset_sql]
        restore_cmd = [psql_path, database_url, "-v", "ON_ERROR_STOP=1", "-f", str(source)]
        reset_run = subprocess.run(reset_cmd, capture_output=True, text=True, check=False, env=env)
        if reset_run.returncode != 0:
            details = reset_run.stderr.strip() or reset_run.stdout.strip() or "Postgres schema reset failed."
            raise RuntimeError(details)
        restore_run = subprocess.run(restore_cmd, capture_output=True, text=True, check=False, env=env)
        if restore_run.returncode != 0:
            details = restore_run.stderr.strip() or restore_run.stdout.strip() or "Postgres restore failed."
            raise RuntimeError(details)
        return

    docker_path = shutil.which("docker")
    if docker_path and username:
        reset_cmd = [
            docker_path,
            "exec",
            "-e",
            f"PGPASSWORD={password}",
            "paleo_postgres",
            "psql",
            "-U",
            username,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            reset_sql,
        ]
        reset_run = subprocess.run(reset_cmd, capture_output=True, text=True, check=False)
        if reset_run.returncode != 0:
            details = reset_run.stderr.strip() or reset_run.stdout.strip() or "Postgres schema reset failed."
            raise RuntimeError(details)
        restore_cmd = [
            docker_path,
            "exec",
            "-i",
            "-e",
            f"PGPASSWORD={password}",
            "paleo_postgres",
            "psql",
            "-U",
            username,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
        ]
        with source.open("rb") as source_fp:
            restore_run = subprocess.run(restore_cmd, stdin=source_fp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if restore_run.returncode != 0:
            details = restore_run.stderr.decode("utf-8", errors="replace").strip() or "Postgres restore failed."
            raise RuntimeError(details)
        return

    raise RuntimeError("Postgres restore requires 'psql' (preferred) or Docker access to container 'paleo_postgres'.")


def _human_size(num_bytes: int) -> str:
    size = float(max(num_bytes, 0))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"
