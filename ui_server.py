#!/usr/bin/env python3
"""Local browser UI for the original ReleaseNotesPoster flow."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
ENV_PATH = ROOT / ".env.local"
RUNNER = ROOT / "run_poster.py"
HOST = "127.0.0.1"
DEFAULT_PORT = 8770

RELEASE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED_ENV_KEYS = ("CONF_BASE_URL", "CONF_SPACE_KEY")
SECRET_KEYS = {"CONF_TOKEN", "CONF_PASSWORD", "JIRA_TOKEN", "JIRA_PASSWORD", "SLACK_WEBHOOK_URL"}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def read_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned = re.split(r"\s+#", value.strip(), maxsplit=1)[0]
        values[key.strip()] = cleaned.strip('"').strip("'")
    return values


def config_status() -> dict:
    config = read_env_file()
    missing = [key for key in REQUIRED_ENV_KEYS if not config.get(key)]
    return {
        "envFileExists": ENV_PATH.exists(),
        "ready": not missing,
        "missing": missing,
        "confluenceBaseUrl": config.get("CONF_BASE_URL", ""),
        "spaceKey": config.get("CONF_SPACE_KEY", ""),
        "parentPath": config.get("CONF_PARENT_PATH", ""),
        "createParentPath": config.get("CONF_CREATE_PARENT_PATH", "").lower() in {"1", "true", "yes", "on"},
        "jiraBaseUrl": config.get("JIRA_BASE_URL", ""),
        "jiraProjectKey": config.get("JIRA_PROJECT_KEY", ""),
        "hasConfluenceToken": bool(config.get("CONF_TOKEN") or config.get("CONF_PASSWORD")),
        "hasJiraToken": bool(config.get("JIRA_TOKEN") or config.get("JIRA_PASSWORD")),
    }


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def public_job(job: dict) -> dict:
    return {
        "id": job["id"],
        "status": job["status"],
        "release": job["release"],
        "releaseDate": job["releaseDate"],
        "startedAt": job["startedAt"],
        "finishedAt": job.get("finishedAt"),
        "exitCode": job.get("exitCode"),
        "output": list(job["output"]),
        "pageUrl": job.get("pageUrl", ""),
        "error": job.get("error", ""),
    }


def append_output(job_id: str, line: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job:
            job["output"].append(line.rstrip("\n"))


def run_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["status"] = "running"
        release = job["release"]
        release_date = job["releaseDate"]

    command = [sys.executable, str(RUNNER), release]
    if release_date:
        command.append(release_date)

    append_output(job_id, f"$ python run_poster.py {release}{' ' + release_date if release_date else ''}")

    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        assert process.stdout is not None
        for line in process.stdout:
            append_output(job_id, line)

        exit_code = process.wait()
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["exitCode"] = exit_code
            job["finishedAt"] = time.time()
            job["status"] = "success" if exit_code == 0 else "failed"
            for output_line in job["output"]:
                if "[INFO] URL:" in output_line:
                    job["pageUrl"] = output_line.split("[INFO] URL:", 1)[1].strip()
    except Exception as exc:
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finishedAt"] = time.time()
            job["exitCode"] = 1
            job["output"].append(f"[ERROR] {exc}")


def create_job(payload: dict) -> tuple[int, dict]:
    release = str(payload.get("release") or "").strip()
    release_date = str(payload.get("releaseDate") or "").strip()
    confirmed = bool(payload.get("confirmed"))

    error = validate_release_inputs(release, release_date)
    if error:
        return 400, {"error": error}
    if not confirmed:
        return 400, {"error": "Confirm that this should create or update the Confluence page."}
    if not RUNNER.exists():
        return 500, {"error": "run_poster.py was not found."}

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "release": release,
        "releaseDate": release_date,
        "startedAt": time.time(),
        "finishedAt": None,
        "exitCode": None,
        "output": [],
        "pageUrl": "",
        "error": "",
    }

    with JOBS_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return 201, public_job(job)


def validate_release_inputs(release: str, release_date: str) -> str:
    if not release:
        return "Release is required."
    if not RELEASE_RE.match(release):
        return "Release can only include letters, numbers, dots, dashes, and underscores."
    if release_date and not DATE_RE.match(release_date):
        return "Release date must use YYYY-MM-DD format."
    return ""


def create_preview(payload: dict) -> tuple[int, dict]:
    release = str(payload.get("release") or "").strip()
    release_date = str(payload.get("releaseDate") or "").strip()

    error = validate_release_inputs(release, release_date)
    if error:
        return 400, {"error": error}

    jql = f'fixVersion = "{release}" ORDER BY issuetype ASC'
    columns = "key,summary,type,status,priority,assignee,updated,fixVersion"
    title = f"{release} — Release Notes"

    if release_date:
        sentence = (
            f"Tickets in the table below are what went out in Release {release}. "
            f"This release went out on {release_date}."
        )
        date_note = "Using manually entered release date."
    else:
        sentence = f"Tickets in the table below are what went out in Release {release}."
        date_note = "No date entered. Posting will try to use the Jira version release date."

    return 200, {
        "title": title,
        "release": release,
        "releaseDate": release_date,
        "dateNote": date_note,
        "sentence": sentence,
        "jql": jql,
        "columns": columns,
        "maximumIssues": 200,
    }


class UiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])

        if path == "/api/config":
            json_response(self, 200, config_status())
            return

        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if not job:
                    json_response(self, 404, {"error": "Job not found."})
                    return
                payload = public_job(job)
            json_response(self, 200, payload)
            return

        if path in ("", "/"):
            path = "/index.html"

        file_path = (WEB_ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(WEB_ROOT.resolve())) or not file_path.exists():
            self.send_error(404)
            return

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]

        if path == "/api/preview":
            try:
                status, payload = create_preview(read_json(self))
                json_response(self, status, payload)
            except json.JSONDecodeError:
                json_response(self, 400, {"error": "Invalid JSON payload."})
            return

        if path != "/api/jobs":
            self.send_error(404)
            return

        try:
            status, payload = create_job(read_json(self))
            json_response(self, status, payload)
        except json.JSONDecodeError:
            json_response(self, 400, {"error": "Invalid JSON payload."})


def run_server(port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((HOST, port), UiHandler)
    print(f"Release Notes Poster UI running at http://{HOST}:{port}")
    print("This UI uses ./run.sh and the original ReleaseNotesPoster.py flow.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
