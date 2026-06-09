#!/usr/bin/env python3
"""
ReleaseNotesPoster.py

Creates/updates a Confluence page for a release with:
- A sentence: "Tickets in the table below are what went out in Release <release>. This release went out on <release_date>."
- A Jira Issues macro (live table) with JQL: fixVersion = "<release>" ORDER BY issuetype ASC
- Optional Slack notification on success

Enhancements:
- CLI arg for release (and optional date)  -> `python ReleaseNotesPoster.py WMS_05.00_2026 2026-03-31`
- If date omitted, fetches releaseDate from Jira Versions API for project key (e.g., OY2)

Env:
- Confluence: CONF_BASE_URL + (CONF_TOKEN or CONF_USERNAME/CONF_PASSWORD), CONF_SPACE_KEY, CONF_PARENT_PATH
- Jira: JIRA_BASE_URL + (JIRA_TOKEN or JIRA_USERNAME/JIRA_PASSWORD), JIRA_PROJECT_KEY
- Slack (optional): SLACK_WEBHOOK_URL
"""

import os
import sys
import html
import re
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+.*",
)

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
AUTOMATION_DIR = PROJECT_DIR.parent
CASEFORGE_ENV = AUTOMATION_DIR / "CaseForge" / ".env"

# ---------------------------
# Load environment (.env then .env.local)
# ---------------------------
load_dotenv(dotenv_path=PROJECT_DIR / ".env", override=False)
load_dotenv(dotenv_path=PROJECT_DIR / ".env.local", override=True)
load_dotenv(dotenv_path=CASEFORGE_ENV, override=False)

# ---------------------------
# Confluence config
# ---------------------------
CONF_BASE = (os.getenv("CONF_BASE_URL") or "").rstrip("/")
CONF_SPACE_KEY = (os.getenv("CONF_SPACE_KEY") or "").strip()
CONF_PARENT_PATH = (os.getenv("CONF_PARENT_PATH") or "Product Teams/MAC Suite/MAC Suite Teams/Knight Riders/WMS & MMDL Releases").strip()
CONF_CREATE_PARENT_PATH = (os.getenv("CONF_CREATE_PARENT_PATH", "false").strip().lower() in {"1", "true", "yes", "on"})

CONF_TOKEN = os.getenv("CONF_TOKEN")
CONF_USERNAME = os.getenv("CONF_USERNAME")
CONF_PASSWORD = os.getenv("CONF_PASSWORD")

VERIFY_SSL = (os.getenv("VERIFY_SSL", "true").lower() != "false")

# ---------------------------
# Jira config
# ---------------------------
JIRA_BASE = (os.getenv("JIRA_BASE_URL") or "").rstrip("/")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_PASSWORD = os.getenv("JIRA_PASSWORD")
JIRA_PROJECT_KEY = (os.getenv("JIRA_PROJECT_KEY") or "OY2").strip()  # <== use OY2 as default based on your URL

# ---------------------------
# Slack (optional)
# ---------------------------
SLACK_WEBHOOK_URL = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()

# ---------------------------
# TestRail (optional)
# ---------------------------
TESTRAIL_BASE = (os.getenv("TESTRAIL_BASE_URL") or "").rstrip("/")
TESTRAIL_PROJECT_ID = (os.getenv("TESTRAIL_PROJECT_ID") or "").strip()
TESTRAIL_PROJECT_NAME = (os.getenv("TESTRAIL_PROJECT_NAME") or "").strip()
TESTRAIL_USERNAME = (os.getenv("TESTRAIL_USERNAME") or os.getenv("TESTRAIL_EMAIL") or "").strip()
TESTRAIL_SECRET = (os.getenv("TESTRAIL_API_KEY") or os.getenv("TESTRAIL_PASSWORD") or "").strip()
TESTRAIL_ENVIRONMENTS = ("DEV", "VAL", "PROD")
TESTRAIL_RUN_NAME_TEMPLATES = {
    "DEV": (os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_DEV") or "{release} - DEV (Functional Testing)").strip(),
    "VAL": (os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_VAL") or "{release} - VAL (Regression Testing)").strip(),
    "PROD": (os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_PROD") or "{release} - PROD (Smoke Testing)").strip(),
}
TESTRAIL_ENV_LABELS = {
    "DEV": (os.getenv("TESTRAIL_ENV_LABEL_DEV") or "DEV Functional Testing").strip(),
    "VAL": (os.getenv("TESTRAIL_ENV_LABEL_VAL") or "VAL Regression Testing").strip(),
    "PROD": (os.getenv("TESTRAIL_ENV_LABEL_PROD") or "PROD Smoke Testing").strip(),
}
TESTRAIL_ATTACH_SNAPSHOT = (
    os.getenv("TESTRAIL_ATTACH_SNAPSHOT", "true").strip().lower() in {"1", "true", "yes", "on"}
)

# ---------------------------
# Sessions
# ---------------------------
conf = requests.Session()
conf.verify = VERIFY_SSL
conf.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
if CONF_TOKEN:
    conf.headers["Authorization"] = f"Bearer {CONF_TOKEN}"
elif CONF_USERNAME and CONF_PASSWORD:
    conf.auth = HTTPBasicAuth(CONF_USERNAME, CONF_PASSWORD)
else:
    sys.exit("[ERROR] Confluence auth missing. Set CONF_TOKEN or CONF_USERNAME/CONF_PASSWORD.")

jira = requests.Session()
jira.verify = VERIFY_SSL
jira.headers.update({"Accept": "application/json"})
if JIRA_TOKEN:
    jira.headers["Authorization"] = f"Bearer {JIRA_TOKEN}"
elif JIRA_USERNAME and JIRA_PASSWORD:
    jira.auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_PASSWORD)
# else: Jira lookups will be skipped gracefully if not configured

testrail = requests.Session()
testrail.verify = VERIFY_SSL
testrail.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
if TESTRAIL_USERNAME and TESTRAIL_SECRET:
    testrail.auth = HTTPBasicAuth(TESTRAIL_USERNAME, TESTRAIL_SECRET)

# ---------------------------
# Helpers (diagnostic)
# ---------------------------
def _json_or_error(resp, where=""):
    try:
        return resp.json()
    except Exception as e:
        snippet = resp.text[:1000].replace("\n", " ")
        raise RuntimeError(f"{where} expected JSON; status={resp.status_code}. First 1KB: {snippet}") from e

def _raise(resp, where=""):
    if resp.status_code >= 400:
        snippet = resp.text[:1000].replace("\n", " ")
        raise RuntimeError(f"{where} failed; status={resp.status_code}. {snippet}")

def _env_ready(*values: str) -> bool:
    return all(bool(value) for value in values)

# ---------------------------
# Confluence REST
# ---------------------------
def get_space_or_fail(space_key: str):
    url = f"{CONF_BASE}/rest/api/space/{space_key}"
    r = conf.get(url, timeout=30)
    _raise(r, "Space check")
    return _json_or_error(r, "Space check")  # 200 OK or raises

def search_title(space_key: str, title: str):
    url = f"{CONF_BASE}/rest/api/content"
    r = conf.get(
        url,
        params={"spaceKey": space_key, "title": title, "type": "page", "status": "current"},
        timeout=60,
    )
    _raise(r, "Title search")
    return _json_or_error(r, "Title search").get("results", [])

def list_children(parent_id: str, limit: int = 200):
    url = f"{CONF_BASE}/rest/api/content/{parent_id}/child/page"
    start, out = 0, []
    while True:
        r = conf.get(url, params={"limit": limit, "start": start}, timeout=60)
        _raise(r, "Children GET")
        js = _json_or_error(r, "Children GET")
        res = js.get("results", [])
        if not res:
            break
        out.extend(res)
        size = js.get("size", 0)
        start += size
        if size == 0:
            break
    return out

def find_child_by_title(parent_id: str, title: str):
    for c in list_children(parent_id):
        if c.get("title") == title:
            return c["id"]
    return None

def find_page_by_title(space_key: str, title: str):
    hits = search_title(space_key, title)
    return hits[0]["id"] if hits else None

def create_root(space_key: str, title: str, body_storage: str = "<p>(auto-created)</p>"):
    url = f"{CONF_BASE}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": body_storage, "representation": "storage"}},
    }
    r = conf.post(url, json=payload, timeout=60)
    _raise(r, "Create root")
    return _json_or_error(r, "Create root")["id"]

def create_child(space_key: str, title: str, parent_id: str, body_storage: str):
    url = f"{CONF_BASE}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"id": str(parent_id)}],
        "body": {"storage": {"value": body_storage, "representation": "storage"}},
    }
    r = conf.post(url, json=payload, timeout=60)
    _raise(r, "Create child")
    return _json_or_error(r, "Create child")["id"]

def get_title_and_version(page_id: str):
    url = f"{CONF_BASE}/rest/api/content/{page_id}"
    r = conf.get(url, params={"expand": "version,title"}, timeout=60)
    _raise(r, "Get page")
    js = _json_or_error(r, "Get page")
    return js.get("title"), (js.get("version") or {}).get("number", 0)

def update_storage(page_id: str, title: str, storage_body: str, current_version: int):
    url = f"{CONF_BASE}/rest/api/content/{page_id}"
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": current_version + 1},  # Confluence requires version bump
        "body": {"storage": {"value": storage_body, "representation": "storage"}},
    }
    r = conf.put(url, json=payload, timeout=60)
    _raise(r, "Update page")
    return _json_or_error(r, "Update page")

def get_attachment_by_filename(page_id: str, filename: str):
    url = f"{CONF_BASE}/rest/api/content/{page_id}/child/attachment"
    r = conf.get(url, params={"filename": filename}, timeout=60)
    _raise(r, "Attachment search")
    results = _json_or_error(r, "Attachment search").get("results", [])
    return results[0] if results else None

def confluence_file_headers():
    headers = {"Accept": "application/json", "X-Atlassian-Token": "no-check"}
    if CONF_TOKEN:
        headers["Authorization"] = f"Bearer {CONF_TOKEN}"
    return headers

def upload_or_update_attachment(page_id: str, filename: str, content: bytes, content_type: str):
    existing = get_attachment_by_filename(page_id, filename)
    headers = confluence_file_headers()
    files = {"file": (filename, content, content_type)}
    data = {"comment": "Automated TestRail quality snapshot"}

    if existing:
        attachment_id = existing["id"]
        url = f"{CONF_BASE}/rest/api/content/{page_id}/child/attachment/{attachment_id}/data"
        r = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            auth=None if CONF_TOKEN else conf.auth,
            verify=VERIFY_SSL,
            timeout=60,
        )
        _raise(r, "Attachment update")
        return _json_or_error(r, "Attachment update")

    url = f"{CONF_BASE}/rest/api/content/{page_id}/child/attachment"
    r = requests.post(
        url,
        headers=headers,
        files=files,
        data=data,
        auth=None if CONF_TOKEN else conf.auth,
        verify=VERIFY_SSL,
        timeout=60,
    )
    _raise(r, "Attachment upload")
    return _json_or_error(r, "Attachment upload")

def resolve_or_create_path(space_key: str, path: str) -> str:
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Empty CONF_PARENT_PATH")

    # root
    root_title = parts[0]
    parent_id = find_page_by_title(space_key, root_title)
    if not parent_id:
        if not CONF_CREATE_PARENT_PATH:
            raise RuntimeError(
                f"CONF_PARENT_PATH root page not found: {root_title}. "
                "Fix CONF_PARENT_PATH or set CONF_CREATE_PARENT_PATH=true to auto-create missing pages."
            )
        parent_id = create_root(space_key, root_title)

    # descend
    for seg in parts[1:]:
        child_id = find_child_by_title(parent_id, seg)
        if child_id:
            parent_id = child_id
        else:
            if not CONF_CREATE_PARENT_PATH:
                raise RuntimeError(
                    f"CONF_PARENT_PATH segment not found under its expected parent: {seg}. "
                    "Fix CONF_PARENT_PATH or set CONF_CREATE_PARENT_PATH=true to auto-create missing pages."
                )
            parent_id = create_child(space_key, seg, parent_id, "<p>(auto-created)</p>")
    return parent_id

# ---------------------------
# Jira: fetch releaseDate from Version by name
# ---------------------------
def get_release_date_from_jira(project_key: str, version_name: str) -> str:
    """
    Return releaseDate (YYYY-MM-DD) for the version named `version_name`
    in Jira project `project_key`. Tries Cloud v3 endpoint first, then DC/Server v2.
    If Jira isn't configured or date not set, return "".
    """
    if not (JIRA_BASE and project_key and (JIRA_TOKEN or (JIRA_USERNAME and JIRA_PASSWORD))):
        return ""

    def _fetch(url):
        try:
            r = jira.get(url, timeout=60)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    # Both v3 and v2 "Get project versions" return a list of version objects with "name", "releaseDate" etc.
    # See Atlassian REST references. [3](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-project-versions/)[4](https://jira-api.apidog.io/api-3933628)
    endpoints = [
        f"{JIRA_BASE}/rest/api/3/project/{project_key}/versions",
        f"{JIRA_BASE}/rest/api/2/project/{project_key}/versions",
    ]

    for url in endpoints:
        data = _fetch(url)
        if not data:
            continue
        # The response is typically a list; if paginated variant is used it may have 'values'
        versions = data if isinstance(data, list) else data.get("values", [])
        for v in versions:
            if str(v.get("name")) == version_name:
                return str(v.get("releaseDate") or "")
    return ""

# ---------------------------
# TestRail: quality snapshots
# ---------------------------
def normalize_run_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", " ", name.upper()).strip()

def testrail_configured() -> bool:
    return _env_ready(TESTRAIL_BASE, TESTRAIL_USERNAME, TESTRAIL_SECRET)

def missing_testrail_settings():
    missing = []
    if not TESTRAIL_BASE:
        missing.append("TESTRAIL_BASE_URL")
    if not TESTRAIL_USERNAME:
        missing.append("TESTRAIL_USERNAME or TESTRAIL_EMAIL")
    if not TESTRAIL_SECRET:
        missing.append("TESTRAIL_API_KEY or TESTRAIL_PASSWORD")
    return missing

def testrail_request(path: str):
    url = f"{TESTRAIL_BASE}/index.php?/api/v2/{path}"
    r = testrail.get(url, timeout=60)
    _raise(r, f"TestRail {path}")
    return _json_or_error(r, f"TestRail {path}")

def testrail_get_projects():
    if TESTRAIL_PROJECT_ID:
        return [{"id": int(TESTRAIL_PROJECT_ID), "name": TESTRAIL_PROJECT_ID}]

    projects, seen, offset = [], set(), 0
    while True:
        payload = testrail_request(f"get_projects&limit=250&offset={offset}")
        if isinstance(payload, dict) and "projects" in payload:
            batch = payload.get("projects", [])
            for project in batch:
                project_id = project.get("id")
                if project_id in seen:
                    continue
                seen.add(project_id)
                projects.append(project)
            if not (payload.get("_links") or {}).get("next"):
                break
            offset += int(payload.get("limit") or len(batch) or 250)
            continue
        if isinstance(payload, list):
            for project in payload:
                project_id = project.get("id")
                if project_id in seen:
                    continue
                seen.add(project_id)
                projects.append(project)
        break

    if TESTRAIL_PROJECT_NAME:
        target = normalize_run_name(TESTRAIL_PROJECT_NAME)
        projects = [
            project for project in projects
            if normalize_run_name(str(project.get("name") or "")) == target
        ]
    return projects

def testrail_get_runs(project_id: int):
    runs, seen = [], set()
    for is_completed in (0, 1):
        offset = 0
        while True:
            payload = testrail_request(
                f"get_runs/{project_id}&is_completed={is_completed}&limit=250&offset={offset}"
            )
            if isinstance(payload, dict) and "runs" in payload:
                batch = payload.get("runs", [])
                for run in batch:
                    run_id = run.get("id")
                    if run_id in seen:
                        continue
                    seen.add(run_id)
                    runs.append(run)
                if not (payload.get("_links") or {}).get("next"):
                    break
                offset += int(payload.get("limit") or len(batch) or 250)
                continue
            if isinstance(payload, list):
                for run in payload:
                    run_id = run.get("id")
                    if run_id in seen:
                        continue
                    seen.add(run_id)
                    runs.append(run)
            break
    return runs

def testrail_get_run(run_id: int):
    return testrail_request(f"get_run/{run_id}")

def testrail_get_plans(project_id: int):
    plans, seen = [], set()
    for is_completed in (0, 1):
        offset = 0
        while True:
            payload = testrail_request(
                f"get_plans/{project_id}&is_completed={is_completed}&limit=250&offset={offset}"
            )
            if isinstance(payload, dict) and "plans" in payload:
                batch = payload.get("plans", [])
                for plan in batch:
                    plan_id = plan.get("id")
                    if plan_id in seen:
                        continue
                    seen.add(plan_id)
                    plans.append(plan)
                if not (payload.get("_links") or {}).get("next"):
                    break
                offset += int(payload.get("limit") or len(batch) or 250)
                continue
            if isinstance(payload, list):
                for plan in payload:
                    plan_id = plan.get("id")
                    if plan_id in seen:
                        continue
                    seen.add(plan_id)
                    plans.append(plan)
            break
    return plans

def testrail_get_plan(plan_id: int):
    return testrail_request(f"get_plan/{plan_id}")

def testrail_get_plan_runs(project_id: int):
    runs = []
    for plan in testrail_get_plans(project_id):
        plan_id = int(plan["id"])
        plan_name = str(plan.get("name") or "")
        try:
            detailed = testrail_get_plan(plan_id)
        except Exception as e:
            print(f"[WARN] TestRail plan skipped ({plan_name}): {e}")
            continue
        for entry in detailed.get("entries", []):
            entry_name = str(entry.get("name") or "")
            for run in entry.get("runs", []):
                run["_plan_id"] = plan_id
                run["_plan_name"] = plan_name
                run["_entry_name"] = entry_name
                runs.append(run)
    return runs

def testrail_get_results_for_run(run_id: int):
    results, offset = [], 0
    while True:
        payload = testrail_request(f"get_results_for_run/{run_id}&limit=250&offset={offset}")
        if isinstance(payload, dict) and "results" in payload:
            batch = payload.get("results", [])
            results.extend(batch)
            if not (payload.get("_links") or {}).get("next"):
                break
            offset += int(payload.get("limit") or len(batch) or 250)
            continue
        if isinstance(payload, list):
            results.extend(payload)
        break
    return results

def testrail_run_id_override(environment: str) -> str:
    return (os.getenv(f"TESTRAIL_RUN_ID_{environment}") or "").strip()

def expected_testrail_run_names(release: str, environment: str):
    template = TESTRAIL_RUN_NAME_TEMPLATES[environment]
    names = [
        template.format(release=release, environment=environment),
        f"{release} - {environment}",
        f"{release} {environment}",
    ]
    if environment == "DEV":
        names.append(f"{release} - DEV (Functional Testing)")
    elif environment == "VAL":
        names.append(f"{release} - VAL (Regression Testing)")
    elif environment == "PROD":
        names.append(f"{release} - PROD (Smoke Testing)")

    deduped, seen = [], set()
    for name in names:
        normalized = normalize_run_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(name)
    return deduped

def pick_testrail_run(release: str, environment: str):
    run_id = testrail_run_id_override(environment)
    if run_id:
        if not run_id.isdigit():
            print(f"[WARN] Ignoring TESTRAIL_RUN_ID_{environment} because it is not numeric.")
        else:
            run = testrail_get_run(int(run_id))
            run["_project_id"] = int(TESTRAIL_PROJECT_ID or 0)
            run["_project_name"] = str(TESTRAIL_PROJECT_ID or "explicit run ID")
            return run

    target_names = [normalize_run_name(name) for name in expected_testrail_run_names(release, environment)]
    release_token = normalize_run_name(release)
    env_token = normalize_run_name(environment)
    candidates = []

    projects = testrail_get_projects()
    for project in projects:
        project_id = int(project["id"])
        for run in testrail_get_runs(project_id) + testrail_get_plan_runs(project_id):
            name = str(run.get("name") or "")
            plan_name = str(run.get("_plan_name") or "")
            entry_name = str(run.get("_entry_name") or "")
            search_name = " ".join(part for part in (plan_name, entry_name, name) if part)
            normalized = normalize_run_name(search_name)
            exact_match = normalized in target_names
            release_match = release_token in normalized
            if not exact_match and not release_match:
                continue
            score = 0
            if exact_match:
                score += 100
            if release_match:
                score += 30
            if env_token in normalized:
                score += 25
            if environment == "DEV" and "FUNCTIONAL" in normalized:
                score += 20
            if environment == "VAL" and "REGRESSION" in normalized:
                score += 20
            if environment == "PROD" and "SMOKE" in normalized:
                score += 20
            if not bool(run.get("is_completed")):
                score += 5
            if score > 0:
                run["_project_id"] = project_id
                run["_project_name"] = str(project.get("name") or project_id)
                candidates.append((score, run))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            int(item[1].get("updated_on") or item[1].get("created_on") or 0),
        ),
        reverse=True,
    )
    return candidates[0][1]

def defect_keys_from_testrail_results(results):
    keys, seen = [], set()
    for result in results:
        defects = str(result.get("defects") or "")
        for raw in defects.split(","):
            key = raw.strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys

def get_testrail_summary(release: str, environment: str):
    if not testrail_configured():
        print(f"[WARN] TestRail settings missing ({', '.join(missing_testrail_settings())}); skipping TestRail validation.")
        return None

    run = pick_testrail_run(release, environment)
    if not run:
        expected = "; ".join(expected_testrail_run_names(release, environment))
        print(f"[WARN] No {environment} TestRail run found. Expected one of: {expected}")
        return None

    resolved_run = run if "passed_count" in run else testrail_get_run(int(run["id"]))
    results = testrail_get_results_for_run(int(resolved_run["id"]))
    defect_keys = defect_keys_from_testrail_results(results)

    passed = int(resolved_run.get("passed_count") or 0)
    failed = int(resolved_run.get("failed_count") or 0)
    blocked = int(resolved_run.get("blocked_count") or 0)
    retest = int(resolved_run.get("retest_count") or 0)
    untested = int(resolved_run.get("untested_count") or 0)
    total = passed + failed + blocked + retest + untested

    return {
        "environment": environment,
        "environment_label": TESTRAIL_ENV_LABELS[environment],
        "id": int(resolved_run["id"]),
        "project_id": int(run.get("_project_id") or 0),
        "project_name": str(run.get("_project_name") or ""),
        "name": str(resolved_run.get("name") or ""),
        "url": str(resolved_run.get("url") or f"{TESTRAIL_BASE}/index.php?/runs/view/{resolved_run['id']}"),
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "retest": retest,
        "untested": untested,
        "total": total,
        "defect_keys": defect_keys,
    }

def get_testrail_summaries(release: str):
    summaries = {}
    if not TESTRAIL_ATTACH_SNAPSHOT:
        return summaries
    for environment in TESTRAIL_ENVIRONMENTS:
        try:
            summary = get_testrail_summary(release, environment)
            if summary:
                summaries[environment] = summary
                print(f"[INFO] TestRail {environment} run found: {summary['name']}")
        except Exception as e:
            print(f"[WARN] TestRail {environment} validation skipped: {e}")
    return summaries

def testrail_snapshot_filename(release: str, environment: str) -> str:
    safe_release = re.sub(r"[^A-Za-z0-9_.-]+", "-", release).strip("-")
    return f"testrail-{safe_release}-{environment.lower()}.svg"

def render_testrail_summary_table(summaries) -> str:
    if not summaries:
        return ""

    rows = []
    for environment in TESTRAIL_ENVIRONMENTS:
        summary = summaries.get(environment)
        if not summary:
            rows.append(
                "<tr>"
                f"<td><strong>{html.escape(TESTRAIL_ENV_LABELS[environment])}</strong></td>"
                "<td colspan=\"8\">No matching TestRail run found.</td>"
                "</tr>"
            )
            continue

        defects = ", ".join(summary["defect_keys"][:10])
        if len(summary["defect_keys"]) > 10:
            defects += " ..."
        defects = defects or "None"
        rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(summary['url'])}\"><strong>{html.escape(summary['environment_label'])}</strong></a><br />"
            f"<span>{html.escape(summary['name'])}</span></td>"
            f"<td>{summary['total']}</td>"
            f"<td>{summary['passed']}</td>"
            f"<td>{summary['failed']}</td>"
            f"<td>{summary['blocked']}</td>"
            f"<td>{summary['retest']}</td>"
            f"<td>{summary['untested']}</td>"
            f"<td>{html.escape(defects)}</td>"
            "</tr>"
        )

    return (
        "<h2>TestRail Validation</h2>"
        "<p>The table below summarizes DEV, VAL, and PROD TestRail runs for this release.</p>"
        "<table>"
        "<thead>"
        "<tr>"
        "<th>Environment</th>"
        "<th>Total</th>"
        "<th>Passed</th>"
        "<th>Failed</th>"
        "<th>Blocked</th>"
        "<th>Retest</th>"
        "<th>Untested</th>"
        "<th>Linked defects</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(rows)}"
        "</tbody>"
        "</table>"
    )

def render_testrail_snapshot_svg(release: str, summary) -> bytes:
    width, height = 920, 420
    total = max(summary["total"], 1)
    metrics = [
        ("Passed", summary["passed"], "#2f7d5c"),
        ("Failed", summary["failed"], "#b54b3b"),
        ("Blocked", summary["blocked"], "#c8922d"),
        ("Retest", summary["retest"], "#7d5fd6"),
        ("Untested", summary["untested"], "#6f7b83"),
    ]
    cards = []
    for index, (label, value, color) in enumerate(metrics):
        x = 40 + index * 170
        cards.append(
            f'<rect x="{x}" y="210" width="145" height="104" rx="14" fill="#ffffff" stroke="#d9e1ec"/>'
            f'<text x="{x + 16}" y="246" fill="#657084" font-size="15" font-weight="700">{html.escape(label)}</text>'
            f'<text x="{x + 16}" y="288" fill="{color}" font-size="36" font-weight="800">{value}</text>'
        )

    bar_x, bar_y, bar_w = 40, 340, 840
    offset = 0.0
    segments = []
    for label, value, color in metrics:
        if value <= 0:
            continue
        seg_w = max((value / total) * bar_w, 2)
        segments.append(
            f'<rect x="{bar_x + offset:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="26" fill="{color}">'
            f'<title>{html.escape(label)}: {value}</title>'
            "</rect>"
        )
        offset += seg_w

    defect_text = ", ".join(summary["defect_keys"][:12]) if summary["defect_keys"] else "No linked defects reported"
    if len(summary["defect_keys"]) > 12:
        defect_text += " ..."

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" rx="24" fill="#f5f7fb"/>
  <rect x="24" y="24" width="872" height="372" rx="20" fill="#ffffff" stroke="#d9e1ec"/>
  <text x="40" y="72" fill="#172033" font-family="Arial, sans-serif" font-size="30" font-weight="800">{html.escape(release)} {html.escape(summary["environment_label"])}</text>
  <text x="40" y="108" fill="#657084" font-family="Arial, sans-serif" font-size="17">{html.escape(summary["name"])}</text>
  <text x="40" y="150" fill="#172033" font-family="Arial, sans-serif" font-size="58" font-weight="800">{summary["total"]}</text>
  <text x="160" y="150" fill="#657084" font-family="Arial, sans-serif" font-size="20">total tests</text>
  <text x="40" y="184" fill="#657084" font-family="Arial, sans-serif" font-size="16">Linked defects: {html.escape(defect_text)}</text>
  {"".join(cards)}
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="26" rx="13" fill="#e8edf4"/>
  {"".join(segments)}
</svg>"""
    return svg.encode("utf-8")

def render_testrail_snapshot_embed(filename: str, label: str) -> str:
    return (
        "<p>"
        f"<strong>{html.escape(label)}</strong><br />"
        '<ac:image ac:height="360">'
        f'<ri:attachment ri:filename="{html.escape(filename)}" />'
        "</ac:image>"
        "</p>"
    )

# ---------------------------
# Page body with sentence + Jira Issues macro
# ---------------------------
def build_storage_body(release: str, release_date: str = "", testrail_summaries=None, testrail_snapshot_filenames=None) -> str:
    jql = f'fixVersion = "{release}" ORDER BY issuetype ASC'
    columns = "key,summary,type,status,priority,assignee,updated,fixVersion"
    testrail_summaries = testrail_summaries or {}
    testrail_snapshot_filenames = testrail_snapshot_filenames or {}

    if release_date:
        sentence = (
            f'Tickets in the table below are what went out in Release {html.escape(release)}. '
            f'This release went out on {html.escape(release_date)}.'
        )
    else:
        sentence = (
            f'Tickets in the table below are what went out in Release {html.escape(release)}.'
        )

    testrail_section = render_testrail_summary_table(testrail_summaries)
    snapshot_embeds = []
    for environment in TESTRAIL_ENVIRONMENTS:
        summary = testrail_summaries.get(environment)
        filename = testrail_snapshot_filenames.get(environment)
        if summary and filename:
            snapshot_embeds.append(render_testrail_snapshot_embed(filename, summary["environment_label"]))
    if snapshot_embeds:
        testrail_section += "<h3>TestRail Snapshots</h3>" + "".join(snapshot_embeds)

    return (
        f"<h2>Release: {html.escape(release)}</h2>"
        f"<p>{sentence}</p>"
        "<h2>Included Jira Tickets</h2>"
        f'<ac:structured-macro ac:name="jira" ac:schema-version="1">'
        f'  <ac:parameter ac:name="jqlQuery">{html.escape(jql)}</ac:parameter>'
        f'  <ac:parameter ac:name="columns">{html.escape(columns)}</ac:parameter>'
        f'  <ac:parameter ac:name="maximumIssues">200</ac:parameter>'
        f'  <ac:parameter ac:name="cache">true</ac:parameter>'
        f"</ac:structured-macro>"
        f"{testrail_section}"
    )

# ---------------------------
# Slack (optional)
# ---------------------------
# def post_to_slack(text: str):
#     if not SLACK_WEBHOOK_URL:
#         return
#     try:
#         r = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=15)
#         if r.status_code >= 400:
#             print(f"[WARN] Slack webhook returned {r.status_code}: {r.text[:300]}")
#     except Exception as e:
#         print(f"[WARN] Slack webhook error: {e}")

# ---------------------------
# CLI helpers
# ---------------------------
def get_release_from_cli_or_prompt():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return input("Enter release number (e.g., WMS_05.00_2026): ").strip()

def get_date_from_cli_or_none():
    # Optional CLI arg #2
    if len(sys.argv) > 2 and sys.argv[2].strip():
        return sys.argv[2].strip()
    return ""  # leave empty; we'll try Jira

# ---------------------------
# Main
# ---------------------------
def main():
    # Pre‑flight: ensure Confluence space exists
    get_space_or_fail(CONF_SPACE_KEY)

    release = get_release_from_cli_or_prompt()
    if not release:
        sys.exit("No release provided.")

    # Optional manual date; else try to fetch from Jira Versions
    release_date = get_date_from_cli_or_none()
    if not release_date:
        fetched = get_release_date_from_jira(JIRA_PROJECT_KEY, release)
        release_date = fetched or ""

    testrail_summaries = get_testrail_summaries(release)
    storage_body = build_storage_body(release, release_date, testrail_summaries=testrail_summaries)
    page_title = f"{release} — Release Notes"

    parent_id = resolve_or_create_path(CONF_SPACE_KEY, CONF_PARENT_PATH)

    # Idempotent: update if already present under parent
    existing = find_child_by_title(parent_id, page_title)
    if existing:
        title, ver = get_title_and_version(existing)
        update_storage(existing, title, storage_body, ver)
        page_id = existing
        action = "updated"
    else:
        page_id = create_child(CONF_SPACE_KEY, page_title, parent_id, storage_body)
        action = "created"

    if testrail_summaries:
        try:
            snapshot_filenames = {}
            for environment, summary in testrail_summaries.items():
                filename = testrail_snapshot_filename(release, environment)
                upload_or_update_attachment(
                    page_id,
                    filename,
                    render_testrail_snapshot_svg(release, summary),
                    "image/svg+xml",
                )
                snapshot_filenames[environment] = filename
                print(f"[INFO] TestRail {environment} snapshot attached: {filename}")
            title, ver = get_title_and_version(page_id)
            storage_body = build_storage_body(
                release,
                release_date,
                testrail_summaries=testrail_summaries,
                testrail_snapshot_filenames=snapshot_filenames,
            )
            update_storage(page_id, title, storage_body, ver)
        except Exception as e:
            print(f"[WARN] TestRail snapshot attachments skipped: {e}")

    page_url = f"{CONF_BASE}/pages/viewpage.action?pageId={page_id}"
    print(f"[INFO] Page {action}: {page_title}")
    print(f"[INFO] URL: {page_url}")

    # # Slack
    # msg_date = f" on {release_date}" if release_date else ""
    # post_to_slack(f"✅ Confluence page {action}: *{page_title}*{msg_date}\n{page_url}")

if __name__ == "__main__":
    try:
        # Minimal validation
        if not CONF_BASE or not CONF_SPACE_KEY:
            sys.exit("[ERROR] Set CONF_BASE_URL and CONF_SPACE_KEY in .env.local")
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
