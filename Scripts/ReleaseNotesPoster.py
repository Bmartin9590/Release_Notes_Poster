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
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# ---------------------------
# Load environment (.env then .env.local)
# ---------------------------
load_dotenv(dotenv_path=Path(".env"), override=False)
load_dotenv(dotenv_path=Path(".env.local"), override=True)

# ---------------------------
# Confluence config
# ---------------------------
CONF_BASE = (os.getenv("CONF_BASE_URL") or "").rstrip("/")
CONF_SPACE_KEY = (os.getenv("CONF_SPACE_KEY") or "").strip()
CONF_PARENT_PATH = (os.getenv("CONF_PARENT_PATH") or "Product Teams/MAC Suite/MAC Suite Teams/Knight Riders/WMS & MMDL Releases").strip()

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
    r = conf.get(url, params={"spaceKey": space_key, "title": title}, timeout=60)
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

def resolve_or_create_path(space_key: str, path: str) -> str:
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Empty CONF_PARENT_PATH")

    # root
    root_title = parts[0]
    parent_id = find_page_by_title(space_key, root_title) or create_root(space_key, root_title)

    # descend
    for seg in parts[1:]:
        child_id = find_child_by_title(parent_id, seg)
        if child_id:
            parent_id = child_id
        else:
            existing_id = find_page_by_title(space_key, seg)
            if existing_id:
                print(f"[INFO] Reusing existing page in space for path segment: {seg}")
                parent_id = existing_id
            else:
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
# Page body with sentence + Jira Issues macro
# ---------------------------
def build_storage_body(release: str, release_date: str = "") -> str:
    jql = f'fixVersion = "{release}" ORDER BY issuetype ASC'
    columns = "key,summary,type,status,priority,assignee,updated,fixVersion"

    if release_date:
        sentence = (
            f'Tickets in the table below are what went out in Release {html.escape(release)}. '
            f'This release went out on {html.escape(release_date)}.'
        )
    else:
        sentence = (
            f'Tickets in the table below are what went out in Release {html.escape(release)}.'
        )

    return (
        f"<h2>Release: {html.escape(release)}</h2>"
        f"<p>{sentence}</p>"
        f'<ac:structured-macro ac:name="jira" ac:schema-version="1">'
        f'  <ac:parameter ac:name="jqlQuery">{html.escape(jql)}</ac:parameter>'
        f'  <ac:parameter ac:name="columns">{html.escape(columns)}</ac:parameter>'
        f'  <ac:parameter ac:name="maximumIssues">200</ac:parameter>'
        f'  <ac:parameter ac:name="cache">true</ac:parameter>'
        f"</ac:structured-macro>"
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

    storage_body = build_storage_body(release, release_date)
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
