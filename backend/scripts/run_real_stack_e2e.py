"""Run real-browser E2E tests against isolated, ephemeral database services."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_NAME = "nexusmatch_e2e_test"
DATABASE_USER = "nexusmatch_e2e"
DATABASE_PASSWORD = "nexusmatch_e2e_test_only"
DATABASE_HOST_PORT = 5433
MONGODB_HOST_PORT = 27018
BACKEND_PORT = 8001
FRONTEND_PORT = 5174
DATABASE_ALLOWLIST = {DATABASE_NAME}
PROTECTED_DATABASES = {
    "nexusmatch",
    "nexusmatch_m5_test_20261013",
    "nexusmatch_ci_local_test_20261013",
    "nexusmatch_ci_test",
}


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = PROJECT_ROOT,
) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{' '.join(command)}"
        )


def ensure_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"Port {port} is already in use. Stop the conflicting service "
                "before running the isolated integration suite."
            ) from exc


def database_environment() -> dict[str, str]:
    if DATABASE_NAME in PROTECTED_DATABASES or DATABASE_NAME not in DATABASE_ALLOWLIST:
        raise RuntimeError("Refusing to use a database outside the explicit allowlist.")

    dsn = make_conninfo(
        host="127.0.0.1",
        port=DATABASE_HOST_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
    )
    env = os.environ.copy()
    env.update(
        {
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": str(DATABASE_HOST_PORT),
            "POSTGRES_DB": DATABASE_NAME,
            "POSTGRES_USER": DATABASE_USER,
            "POSTGRES_PASSWORD": DATABASE_PASSWORD,
            "MONGODB_HOST": "127.0.0.1",
            "MONGODB_PORT": str(MONGODB_HOST_PORT),
            "MONGODB_DATABASE": "nexusmatch_e2e_telemetry",
            "MONGO_INITDB_ROOT_USERNAME": "nexusmatch_e2e_admin",
            "MONGO_INITDB_ROOT_PASSWORD": DATABASE_PASSWORD,
            "NEXUSMATCH_TEST_DATABASE_URL": dsn,
            "NEXUSMATCH_REAL_E2E": "1",
            "VITE_API_BASE_URL": f"http://127.0.0.1:{BACKEND_PORT}/api/v1",
        }
    )
    return env


def verify_empty_database(env: dict[str, str]) -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from scripts.verify_test_database import verify_test_database

    verify_test_database(env["NEXUSMATCH_TEST_DATABASE_URL"], require_empty=True)


def verify_migrations(env: dict[str, str]) -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from scripts.migrate import discover_migrations, migration_checksum

    migrations = discover_migrations()
    with psycopg.connect(env["NEXUSMATCH_TEST_DATABASE_URL"]) as connection:
        recorded = connection.execute(
            "SELECT version, filename, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        expected = [
            (
                path.name.split("_", maxsplit=1)[0],
                path.name,
                migration_checksum(path),
            )
            for path in migrations
        ]
        has_bye_column = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'matches'
                  AND column_name = 'is_bye'
            )
            """
        ).fetchone()[0]
    if recorded != expected or not has_bye_column:
        raise RuntimeError(
            "Migration verification failed: recorded migration checksums or "
            "the matches.is_bye schema do not match the current migration set."
        )


def wait_for_backend(process: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend exited before readiness; log: {log_path}")
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{BACKEND_PORT}/api/v1/health", timeout=2
            ) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError(f"Backend did not become healthy; log: {log_path}")


def print_backend_log(log_path: Path) -> None:
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8", errors="replace")
        if log:
            print("\nBackend output:\n" + log, file=sys.stderr)


def main() -> int:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker Desktop with Docker Compose is required.")

    for port in (
        DATABASE_HOST_PORT,
        MONGODB_HOST_PORT,
        BACKEND_PORT,
        FRONTEND_PORT,
    ):
        ensure_port_available(port)

    compose_file = PROJECT_ROOT / "compose.e2e.yaml"
    project = f"nexusmatch-e2e-{uuid.uuid4().hex[:12]}"
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--file",
        str(compose_file),
    ]
    env = database_environment()
    backend: subprocess.Popen | None = None
    compose_started = False
    log_path: Path | None = None

    try:
        compose_started = True
        run(compose + ["up", "--detach", "--wait"], env=env)

        deadline = time.monotonic() + 45
        while True:
            try:
                verify_empty_database(env)
                break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)

        run([sys.executable, "backend/scripts/migrate.py"], env=env)
        verify_migrations(env)
        run([sys.executable, "-m", "pytest", "backend/tests", "-q"], env=env)

        log_descriptor, log_name = tempfile.mkstemp(
            prefix="nexusmatch-e2e-backend-",
            suffix=".log",
        )
        log_path = Path(log_name)
        with os.fdopen(log_descriptor, "w", encoding="utf-8") as log_file:
            backend = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--app-dir",
                    "backend",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(BACKEND_PORT),
                ],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

        wait_for_backend(backend, log_path)
        npm_command = (
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "npm.cmd"]
            if os.name == "nt"
            else ["npm"]
        )
        run(
            npm_command + ["run", "e2e:integration"],
            env=env,
            cwd=PROJECT_ROOT / "frontend",
        )
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError, psycopg.Error) as exc:
        print(f"Real-stack integration run failed: {exc}", file=sys.stderr)
        if log_path:
            print_backend_log(log_path)
        return 1
    finally:
        if backend is not None and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=10)
        if compose_started:
            result = subprocess.run(
                compose + ["down"],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
            )
            if result.returncode:
                print(
                    "Warning: could not stop the isolated Compose project cleanly.",
                    file=sys.stderr,
                )
        if log_path:
            log_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
