#!/usr/bin/env python3
"""
ReleaseNotesCopilot.py

Builds release notes for VAL/PROD from Jira tickets only, while keeping
TestRail metrics in a separate quality section.

Default behavior is safe:
- fetch Jira tickets for a release
- generate or fall back to a structured draft
- optionally resolve a matching TestRail run and summarize quality
- optionally write a dashboard-style HTML preview
- only publish to Confluence when --publish is supplied
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+.*",
)

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:  # type: ignore[override]
        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

    def Field(default: Any = None, **_: Any) -> Any:  # type: ignore[misc]
        return default


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
AUTOMATION_DIR = PROJECT_DIR.parent
CASEFORGE_ENV = AUTOMATION_DIR / "CaseForge" / ".env"


def load_env() -> None:
    load_dotenv(PROJECT_DIR / ".env", override=False)
    load_dotenv(PROJECT_DIR / ".env.local", override=True)
    load_dotenv(CASEFORGE_ENV, override=False)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _raise(resp: requests.Response, where: str = "") -> None:
    if resp.status_code >= 400:
        snippet = resp.text[:1000].replace("\n", " ")
        raise RuntimeError(f"{where} failed; status={resp.status_code}. {snippet}")


def _json_or_error(resp: requests.Response, where: str = "") -> Any:
    try:
        return resp.json()
    except Exception as exc:
        snippet = resp.text[:1000].replace("\n", " ")
        raise RuntimeError(
            f"{where} expected JSON; status={resp.status_code}. First 1KB: {snippet}"
        ) from exc


def response_looks_like_html_login(resp: requests.Response) -> bool:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" in content_type:
        return True
    text = resp.text[:2000].lower()
    return "<!doctype html" in text or "<html" in text or "log into atlassian" in text


def require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing env var {name}")
    return value


@dataclass
class JiraConfig:
    base_url: str
    project_key: str
    session: requests.Session


@dataclass
class ConfluenceConfig:
    base_url: str
    space_key: str
    parent_path: str
    session: requests.Session


@dataclass
class TestRailConfig:
    base_url: str
    project_id: int
    run_name_templates: Dict[str, str]
    environment_labels: Dict[str, str]
    session: requests.Session


@dataclass
class JiraIssue:
    key: str
    summary: str
    issue_type: str
    status: str
    labels: List[str]
    components: List[str]
    description: str
    url: str


@dataclass
class TestRunSummary:
    run_id: int
    run_name: str
    run_url: str
    passed: int
    failed: int
    blocked: int
    retest: int
    untested: int
    total: int
    defects_found: int
    defects_resolved: int
    defects_open: int
    defect_keys: List[str]


class Highlight(BaseModel):
    title: str = Field(description="Short heading for a user-facing release highlight")
    summary: str = Field(description="1-2 sentence summary of the highlight")
    ticket_keys: List[str] = Field(description="Jira keys that support this highlight")


class ChangeTheme(BaseModel):
    heading: str = Field(description="Theme heading such as Reporting or User Management")
    summary: str = Field(description="Short paragraph describing the theme")
    bullet_points: List[str] = Field(description="Plain-language bullets for the theme")
    ticket_keys: List[str] = Field(description="Jira keys behind this theme")


class ReleaseNotesDraft(BaseModel):
    overview: str = Field(description="Short overview paragraph for the release")
    highlights: List[Highlight] = Field(description="High-level release highlights")
    change_themes: List[ChangeTheme] = Field(description="Grouped change sections")
    internal_notes: List[str] = Field(
        description="Optional medium-detail notes that are still useful to QA or release readers"
    )


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def limit_sentences(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text.strip()[:max_chars].rstrip()
    limited = " ".join(sentences[:max_sentences]).strip()
    if len(limited) <= max_chars:
        return limited
    trimmed = limited[: max_chars - 3].rstrip(" ,;:")
    return trimmed + "..."


def limit_text(text: str, max_chars: int = 90) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip(" ,;:") + "..."


def compact_release_draft(draft: ReleaseNotesDraft) -> ReleaseNotesDraft:
    compact_highlights: List[Highlight] = []
    for item in list(draft.highlights)[:3]:
        compact_highlights.append(
            Highlight(
                title=limit_text(item.title, max_chars=72),
                summary=limit_sentences(item.summary, max_sentences=1, max_chars=190),
                ticket_keys=list(item.ticket_keys)[:4],
            )
        )

    compact_themes: List[ChangeTheme] = []
    for theme in list(draft.change_themes)[:3]:
        compact_themes.append(
            ChangeTheme(
                heading=limit_text(theme.heading, max_chars=50),
                summary=limit_sentences(theme.summary, max_sentences=2, max_chars=240),
                bullet_points=[limit_sentences(point, max_sentences=1, max_chars=150) for point in list(theme.bullet_points)[:2]],
                ticket_keys=list(theme.ticket_keys)[:6],
            )
        )

    return ReleaseNotesDraft(
        overview=limit_sentences(draft.overview, max_sentences=2, max_chars=260),
        highlights=compact_highlights,
        change_themes=compact_themes,
        internal_notes=[limit_sentences(note, max_sentences=1, max_chars=180) for note in list(draft.internal_notes)[:2]],
    )


def build_jira_config() -> JiraConfig:
    base_url = (os.getenv("JIRA_BASE_URL") or "").rstrip("/")
    project_key = (os.getenv("JIRA_PROJECT_KEY") or "OY2").strip()
    token = (os.getenv("JIRA_TOKEN") or "").strip()
    username = (os.getenv("JIRA_USERNAME") or "").strip()
    password = (os.getenv("JIRA_PASSWORD") or "").strip()

    if not base_url:
        raise RuntimeError("Missing JIRA_BASE_URL")
    if not (token or (username and password)):
        raise RuntimeError("Missing Jira auth. Set JIRA_TOKEN or JIRA_USERNAME/JIRA_PASSWORD")

    session = requests.Session()
    session.verify = env_bool("VERIFY_SSL", True)
    session.headers.update({"Accept": "application/json"})
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    else:
        session.auth = HTTPBasicAuth(username, password)

    return JiraConfig(base_url=base_url, project_key=project_key, session=session)


def build_confluence_config() -> ConfluenceConfig:
    base_url = (os.getenv("CONF_BASE_URL") or "").rstrip("/")
    space_key = (os.getenv("CONF_SPACE_KEY") or "").strip()
    parent_path = (
        os.getenv("CONF_PARENT_PATH")
        or "Product Teams/MAC Suite/MAC Suite Teams/Knight Riders/WMS & MMDL Releases"
    ).strip()
    token = (os.getenv("CONF_TOKEN") or "").strip()
    username = (os.getenv("CONF_USERNAME") or "").strip()
    password = (os.getenv("CONF_PASSWORD") or "").strip()

    if not base_url or not space_key:
        raise RuntimeError("Missing CONF_BASE_URL or CONF_SPACE_KEY")
    if not (token or (username and password)):
        raise RuntimeError(
            "Missing Confluence auth. Set CONF_TOKEN or CONF_USERNAME/CONF_PASSWORD"
        )

    session = requests.Session()
    session.verify = env_bool("VERIFY_SSL", True)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    else:
        session.auth = HTTPBasicAuth(username, password)

    return ConfluenceConfig(
        base_url=base_url,
        space_key=space_key,
        parent_path=parent_path,
        session=session,
    )


def build_testrail_config() -> Optional[TestRailConfig]:
    base_url = (os.getenv("TESTRAIL_BASE_URL") or "").rstrip("/")
    project_id = (os.getenv("TESTRAIL_PROJECT_ID") or "").strip()
    username = (os.getenv("TESTRAIL_USERNAME") or os.getenv("TESTRAIL_EMAIL") or "").strip()
    secret = (os.getenv("TESTRAIL_API_KEY") or os.getenv("TESTRAIL_PASSWORD") or "").strip()
    generic_template = (os.getenv("TESTRAIL_RUN_NAME_TEMPLATE") or "").strip()
    run_name_templates = {
        "DEV": (
            os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_DEV")
            or generic_template
            or "{release} - DEV (Functional Testing)"
        ).strip(),
        "VAL": (
            os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_VAL")
            or generic_template
            or "{release} - VAL (Regression Testing)"
        ).strip(),
        "PROD": (
            os.getenv("TESTRAIL_RUN_NAME_TEMPLATE_PROD")
            or generic_template
            or "{release} - PROD (Smoke Testing)"
        ).strip(),
    }
    environment_labels = {
        "DEV": (
            os.getenv("TESTRAIL_ENV_LABEL_DEV")
            or "DEV Functional Testing"
        ).strip(),
        "VAL": (
            os.getenv("TESTRAIL_ENV_LABEL_VAL")
            or "VAL Regression Testing"
        ).strip(),
        "PROD": (
            os.getenv("TESTRAIL_ENV_LABEL_PROD")
            or "PROD Smoke Testing"
        ).strip(),
    }

    if not (base_url and project_id and username and secret):
        return None

    session = requests.Session()
    session.verify = env_bool("VERIFY_SSL", True)
    session.auth = (username, secret)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    return TestRailConfig(
        base_url=base_url,
        project_id=int(project_id),
        run_name_templates=run_name_templates,
        environment_labels=environment_labels,
        session=session,
    )


def confluence_get_space_or_fail(conf: ConfluenceConfig) -> None:
    url = f"{conf.base_url}/rest/api/space/{conf.space_key}"
    resp = conf.session.get(url, timeout=30)
    _raise(resp, "Space check")


def confluence_search_title(conf: ConfluenceConfig, title: str) -> List[Dict[str, Any]]:
    url = f"{conf.base_url}/rest/api/content"
    resp = conf.session.get(
        url,
        params={"spaceKey": conf.space_key, "title": title},
        timeout=60,
    )
    _raise(resp, "Title search")
    return _json_or_error(resp, "Title search").get("results", [])


def confluence_list_children(conf: ConfluenceConfig, parent_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    url = f"{conf.base_url}/rest/api/content/{parent_id}/child/page"
    start = 0
    out: List[Dict[str, Any]] = []

    while True:
        resp = conf.session.get(url, params={"limit": limit, "start": start}, timeout=60)
        _raise(resp, "Children GET")
        payload = _json_or_error(resp, "Children GET")
        results = payload.get("results", [])
        if not results:
            break
        out.extend(results)
        size = payload.get("size", 0)
        start += size
        if size == 0:
            break
    return out


def confluence_find_child_by_title(conf: ConfluenceConfig, parent_id: str, title: str) -> Optional[str]:
    for child in confluence_list_children(conf, parent_id):
        if child.get("title") == title:
            return child["id"]
    return None


def confluence_create_root(conf: ConfluenceConfig, title: str, body_storage: str = "<p>(auto-created)</p>") -> str:
    url = f"{conf.base_url}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": conf.space_key},
        "body": {"storage": {"value": body_storage, "representation": "storage"}},
    }
    resp = conf.session.post(url, json=payload, timeout=60)
    _raise(resp, "Create root")
    return _json_or_error(resp, "Create root")["id"]


def confluence_create_child(
    conf: ConfluenceConfig,
    title: str,
    parent_id: str,
    body_storage: str,
) -> str:
    url = f"{conf.base_url}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": conf.space_key},
        "ancestors": [{"id": str(parent_id)}],
        "body": {"storage": {"value": body_storage, "representation": "storage"}},
    }
    resp = conf.session.post(url, json=payload, timeout=60)
    _raise(resp, "Create child")
    return _json_or_error(resp, "Create child")["id"]


def confluence_get_title_and_version(conf: ConfluenceConfig, page_id: str) -> Tuple[str, int]:
    url = f"{conf.base_url}/rest/api/content/{page_id}"
    resp = conf.session.get(url, params={"expand": "version,title"}, timeout=60)
    _raise(resp, "Get page")
    payload = _json_or_error(resp, "Get page")
    return payload.get("title"), (payload.get("version") or {}).get("number", 0)


def confluence_update_storage(
    conf: ConfluenceConfig,
    page_id: str,
    title: str,
    storage_body: str,
    current_version: int,
) -> None:
    url = f"{conf.base_url}/rest/api/content/{page_id}"
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": current_version + 1},
        "body": {"storage": {"value": storage_body, "representation": "storage"}},
    }
    resp = conf.session.put(url, json=payload, timeout=60)
    _raise(resp, "Update page")


def confluence_resolve_or_create_path(conf: ConfluenceConfig, path: str) -> str:
    parts = [part.strip() for part in path.split("/") if part.strip()]
    if not parts:
        raise ValueError("Empty CONF_PARENT_PATH")

    hits = confluence_search_title(conf, parts[0])
    parent_id = hits[0]["id"] if hits else confluence_create_root(conf, parts[0])

    for segment in parts[1:]:
        child_id = confluence_find_child_by_title(conf, parent_id, segment)
        if child_id:
            parent_id = child_id
        else:
            parent_id = confluence_create_child(conf, segment, parent_id, "<p>(auto-created)</p>")
    return parent_id


def jira_get_release_date(config: JiraConfig, release: str) -> str:
    endpoints = [
        f"{config.base_url}/rest/api/3/project/{config.project_key}/versions",
        f"{config.base_url}/rest/api/2/project/{config.project_key}/versions",
    ]

    for url in endpoints:
        try:
            resp = config.session.get(url, timeout=60)
            if resp.status_code != 200:
                continue
            payload = resp.json()
        except Exception:
            continue

        versions = payload if isinstance(payload, list) else payload.get("values", [])
        for version in versions:
            if str(version.get("name")) == release:
                return str(version.get("releaseDate") or "")
    return ""


def adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        parts = [adf_to_text(item) for item in node]
        return "\n".join(part for part in parts if part.strip())
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")
    if node_type == "text":
        return str(node.get("text") or "")
    if node_type in {"paragraph", "heading"}:
        return "".join(adf_to_text(item) for item in node.get("content", [])) + "\n"
    if node_type in {"bulletList", "orderedList"}:
        lines: List[str] = []
        for item in node.get("content", []):
            text = adf_to_text(item).strip()
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines) + ("\n" if lines else "")
    if node_type == "listItem":
        return " ".join(part.strip() for part in [adf_to_text(item) for item in node.get("content", [])] if part.strip())
    if node_type in {"hardBreak", "rule"}:
        return "\n"
    return "".join(adf_to_text(item) for item in node.get("content", []))


def jira_search_release_issues(config: JiraConfig, release: str, max_results: int = 200) -> List[JiraIssue]:
    jql = f'fixVersion = "{release}" ORDER BY issuetype ASC, key ASC'
    start_at = 0
    out: List[JiraIssue] = []
    page_size = 100

    while start_at < max_results:
        limit = min(page_size, max_results - start_at)
        params = {
            "jql": jql,
            "fields": "summary,description,issuetype,status,labels,components",
            "maxResults": str(limit),
            "startAt": str(start_at),
        }
        payload = jira_search_payload(config, params, where="Jira issue search")
        issues = payload.get("issues", [])
        if not issues:
            break

        for raw_issue in issues:
            fields = raw_issue.get("fields", {})
            description = fields.get("description")
            out.append(
                JiraIssue(
                    key=str(raw_issue.get("key") or ""),
                    summary=str(fields.get("summary") or ""),
                    issue_type=str((fields.get("issuetype") or {}).get("name") or ""),
                    status=str((fields.get("status") or {}).get("name") or ""),
                    labels=[str(item) for item in (fields.get("labels") or [])],
                    components=[
                        str(component.get("name") or "")
                        for component in (fields.get("components") or [])
                        if component.get("name")
                    ],
                    description=adf_to_text(description).strip(),
                    url=f"{config.base_url}/browse/{raw_issue.get('key')}",
                )
            )

        start_at += len(issues)
        if len(issues) < limit:
            break
    return out


def jira_issue_status_map(config: JiraConfig, issue_keys: Sequence[str]) -> Dict[str, str]:
    if not issue_keys:
        return {}

    chunks = [issue_keys[i : i + 50] for i in range(0, len(issue_keys), 50)]
    statuses: Dict[str, str] = {}
    for chunk in chunks:
        jql = "key in ({})".format(", ".join(chunk))
        params = {
            "jql": jql,
            "fields": "status",
            "maxResults": str(len(chunk)),
            "startAt": "0",
        }
        payload = jira_search_payload(config, params, where="Jira defect lookup")
        for issue in payload.get("issues", []):
            statuses[str(issue.get("key") or "")] = str(
                ((issue.get("fields") or {}).get("status") or {}).get("name") or ""
            )
    return statuses


def jira_search_payload(config: JiraConfig, params: Dict[str, str], where: str) -> Dict[str, Any]:
    endpoints = [
        f"{config.base_url}/rest/api/3/search/jql",
        f"{config.base_url}/rest/api/3/search",
        f"{config.base_url}/rest/api/2/search",
        f"{config.base_url}/rest/api/latest/search",
    ]

    failures: List[str] = []
    for url in endpoints:
        try:
            resp = config.session.get(url, params=params, timeout=60, allow_redirects=True)
        except Exception as exc:
            failures.append(f"{url} -> request error: {exc}")
            continue

        if resp.status_code == 404:
            failures.append(f"{url} -> 404")
            continue

        if response_looks_like_html_login(resp):
            failures.append(f"{url} -> login HTML")
            continue

        if resp.status_code >= 400:
            snippet = resp.text[:200].replace("\n", " ")
            failures.append(f"{url} -> {resp.status_code} {snippet}")
            continue

        try:
            payload = resp.json()
        except Exception:
            snippet = resp.text[:200].replace("\n", " ")
            failures.append(f"{url} -> non-JSON response: {snippet}")
            continue

        if isinstance(payload, dict) and "issues" in payload:
            return payload

        failures.append(f"{url} -> JSON without issues payload")

    failure_text = "\n".join(f"  - {item}" for item in failures)
    raise RuntimeError(
        f"{where} could not get a JSON issues response from Jira.\n"
        "This usually means the Jira auth for search is not being accepted, or this Jira instance "
        "redirected the request to an Atlassian login page.\n"
        "Tried endpoints:\n"
        f"{failure_text}"
    )


def testrail_request(
    config: TestRailConfig,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{config.base_url}/index.php?/api/v2/{path}"
    resp: Optional[requests.Response] = None
    for attempt in range(5):
        resp = config.session.request(method, url, json=payload, timeout=30)
        if resp.status_code == 429:
            wait_seconds = int(resp.headers.get("Retry-After", "2"))
            time.sleep(wait_seconds)
            continue
        if resp.status_code >= 500 and attempt < 4:
            time.sleep(2**attempt)
            continue
        break

    if resp is None:
        raise RuntimeError("No response returned from TestRail.")
    _raise(resp, f"TestRail {path}")
    return _json_or_error(resp, f"TestRail {path}")


def testrail_get_runs(config: TestRailConfig) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    offset = 0
    while True:
        payload = testrail_request(
            config,
            "GET",
            f"get_runs/{config.project_id}&limit=250&offset={offset}",
        )
        if isinstance(payload, dict) and "runs" in payload:
            batch = payload.get("runs", [])
            runs.extend(batch)
            next_link = (payload.get("_links") or {}).get("next")
            if not next_link:
                break
            offset += int(payload.get("limit") or len(batch) or 250)
            continue
        if isinstance(payload, list):
            runs.extend(payload)
        break
    return runs


def testrail_get_run(config: TestRailConfig, run_id: int) -> Dict[str, Any]:
    return testrail_request(config, "GET", f"get_run/{run_id}")


def testrail_get_results_for_run(config: TestRailConfig, run_id: int) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    offset = 0
    while True:
        payload = testrail_request(
            config,
            "GET",
            f"get_results_for_run/{run_id}&limit=250&offset={offset}",
        )
        if isinstance(payload, dict) and "results" in payload:
            batch = payload.get("results", [])
            results.extend(batch)
            next_link = (payload.get("_links") or {}).get("next")
            if not next_link:
                break
            offset += int(payload.get("limit") or len(batch) or 250)
            continue
        if isinstance(payload, list):
            results.extend(payload)
        break
    return results


def normalize_run_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", " ", name.upper()).strip()


def environment_label(environment: str, tr_config: Optional[TestRailConfig] = None) -> str:
    normalized = environment.upper()
    if tr_config and normalized in tr_config.environment_labels:
        return tr_config.environment_labels[normalized]
    return {
        "DEV": "DEV Functional Testing",
        "VAL": "VAL Regression Testing",
        "PROD": "PROD Smoke Testing",
    }.get(normalized, normalized)


def expected_run_names(config: TestRailConfig, release: str, environment: str) -> List[str]:
    environment = environment.upper()
    exact_names: List[str] = []

    if environment in config.run_name_templates:
        exact_names.append(config.run_name_templates[environment].format(release=release, environment=environment))

    # Keep a couple of normalization-friendly fallbacks for older runs.
    exact_names.extend(
        [
            f"{release} {environment}",
            f"{release} - {environment}",
        ]
    )

    deduped: List[str] = []
    seen: set[str] = set()
    for name in exact_names:
        normalized = normalize_run_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(name)
    return deduped


def pick_release_run(
    config: TestRailConfig,
    release: str,
    environment: str,
    run_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if run_id is not None:
        return testrail_get_run(config, run_id)

    target_exact_names = [normalize_run_name(name) for name in expected_run_names(config, release, environment)]
    release_token = normalize_run_name(release)
    env_token = normalize_run_name(environment)

    candidates: List[Tuple[int, Dict[str, Any]]] = []
    for run in testrail_get_runs(config):
        name = str(run.get("name") or "")
        normalized = normalize_run_name(name)
        score = 0
        if normalized in target_exact_names:
            score += 100
        if release_token in normalized:
            score += 30
        if env_token in normalized:
            score += 20
        if release_token in normalized and env_token in normalized:
            score += 20
        if not bool(run.get("is_completed")):
            score += 5
        if score > 0:
            candidates.append((score, run))

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item[0],
            int((item[1].get("updated_on") or item[1].get("created_on") or 0)),
        ),
        reverse=True,
    )
    return candidates[0][1]


def defect_keys_from_results(results: Iterable[Dict[str, Any]]) -> List[str]:
    keys: List[str] = []
    seen: set[str] = set()
    for result in results:
        defects = str(result.get("defects") or "")
        for raw in defects.split(","):
            key = raw.strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def is_resolved_status(status: str) -> bool:
    normalized = status.strip().lower()
    return any(token in normalized for token in ("done", "closed", "resolved", "complete"))


def build_test_run_summary(
    jira_config: JiraConfig,
    tr_config: Optional[TestRailConfig],
    release: str,
    environment: str,
    run_id: Optional[int] = None,
) -> Optional[TestRunSummary]:
    if tr_config is None:
        return None

    run = pick_release_run(tr_config, release, environment, run_id=run_id)
    if not run:
        return None

    resolved_run = run if run_id is not None or "passed_count" in run else testrail_get_run(tr_config, int(run["id"]))
    results = testrail_get_results_for_run(tr_config, int(resolved_run["id"]))
    defect_keys = defect_keys_from_results(results)
    status_map = jira_issue_status_map(jira_config, defect_keys)
    defects_resolved = sum(1 for key in defect_keys if is_resolved_status(status_map.get(key, "")))

    passed = int(resolved_run.get("passed_count") or 0)
    failed = int(resolved_run.get("failed_count") or 0)
    blocked = int(resolved_run.get("blocked_count") or 0)
    retest = int(resolved_run.get("retest_count") or 0)
    untested = int(resolved_run.get("untested_count") or 0)
    total = passed + failed + blocked + retest + untested
    run_url = str(resolved_run.get("url") or f"{tr_config.base_url}/index.php?/runs/view/{resolved_run['id']}")

    return TestRunSummary(
        run_id=int(resolved_run["id"]),
        run_name=str(resolved_run.get("name") or ""),
        run_url=run_url,
        passed=passed,
        failed=failed,
        blocked=blocked,
        retest=retest,
        untested=untested,
        total=total,
        defects_found=len(defect_keys),
        defects_resolved=defects_resolved,
        defects_open=max(len(defect_keys) - defects_resolved, 0),
        defect_keys=defect_keys,
    )


def issue_payload_for_ai(issues: Sequence[JiraIssue], max_description_chars: int = 800) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for issue in issues:
        payload.append(
            {
                "key": issue.key,
                "summary": issue.summary,
                "issue_type": issue.issue_type,
                "status": issue.status,
                "labels": issue.labels,
                "components": issue.components,
                "description": issue.description[:max_description_chars],
            }
        )
    return payload


def fallback_release_notes(
    release: str,
    environment: str,
    detail_level: str,
    issues: Sequence[JiraIssue],
    extra_notes: Optional[Sequence[str]] = None,
) -> ReleaseNotesDraft:
    top_issues = list(issues[:5])
    highlights = [
        Highlight(
            title=issue.summary[:90],
            summary=(
                f"{issue.summary} "
                f"This item is included in {environment} release scope for {release}."
            ),
            ticket_keys=[issue.key],
        )
        for issue in top_issues
    ]

    groups: Dict[str, List[JiraIssue]] = {}
    for issue in issues:
        group = issue.issue_type or "Changes"
        groups.setdefault(group, []).append(issue)

    change_themes: List[ChangeTheme] = []
    for heading, grouped in list(groups.items())[:4]:
        bullet_points = [item.summary for item in grouped[:4]]
        change_themes.append(
            ChangeTheme(
                heading=heading,
                summary=(
                    f"{heading} updates are represented in this {environment} release and "
                    f"remain grounded in the associated Jira ticket descriptions."
                ),
                bullet_points=bullet_points,
                ticket_keys=[item.key for item in grouped[:6]],
            )
        )

    detail_hint = {
        "business": "high-level business-focused language",
        "mixed": "medium-detail release language with meaningful workflow names",
        "technical": "technical release language without code internals",
    }[detail_level]

    internal_notes = [
        "AI drafting is unavailable, so this release draft is a deterministic fallback.",
        "TestRail quality data remains separate from the Jira-sourced release narrative.",
    ]
    if extra_notes:
        internal_notes = list(extra_notes) + internal_notes

    draft = ReleaseNotesDraft(
        overview=(
            f"{release} for {environment} includes {len(issues)} Jira-tracked changes. "
            f"This fallback draft keeps a {detail_hint} until AI drafting is enabled."
        ),
        highlights=highlights,
        change_themes=change_themes,
        internal_notes=internal_notes,
    )
    return compact_release_draft(draft)


def generate_release_notes_with_ai(
    release: str,
    environment: str,
    detail_level: str,
    issues: Sequence[JiraIssue],
) -> ReleaseNotesDraft:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return fallback_release_notes(release, environment, detail_level, issues)

    try:
        from openai import OpenAI
    except ImportError:
        return fallback_release_notes(release, environment, detail_level, issues)

    detail_instruction = {
        "business": (
            "Use business-readable language. Avoid implementation details and keep the text suitable for broad stakeholders."
        ),
        "mixed": (
            "Use medium-detail release language. Keep product names, workflows, reports, validation behavior, and permission concepts. "
            "Remove code-level implementation details, selectors, field IDs, and internal engineering jargon."
        ),
        "technical": (
            "Use technical release language, but stay at the system and workflow level rather than code internals."
        ),
    }[detail_level]

    env_instruction = {
        "VAL": (
            "Write as a validation-ready release note. Describe what changed and what areas are in validation scope."
        ),
        "PROD": (
            "Write as a shipped release note. Describe what was delivered and the user-facing impact."
        ),
    }[environment]

    system_prompt = (
        "You write release notes from Jira issues only.\n"
        "Never invent capabilities that are not supported by the source tickets.\n"
        "Do not mention TestRail, automation code, selectors, DOM IDs, file names, or implementation classes.\n"
        "Keep the notes accurate, grouped, concise, and readable.\n"
        "Favor summarization over enumeration.\n"
        "Keep the whole response compact.\n"
        "Write an overview of no more than 2 sentences.\n"
        "Return at most 3 highlights.\n"
        "Return at most 3 change themes.\n"
        "Each highlight summary must be a single sentence.\n"
        "Each change theme summary must be at most 2 sentences.\n"
        "Each change theme must have at most 2 bullet points.\n"
        "Use only the most meaningful release information.\n"
        f"{detail_instruction}\n"
        f"{env_instruction}"
    )

    user_prompt = (
        f"Release: {release}\n"
        f"Environment: {environment}\n"
        f"Detail level: {detail_level}\n"
        "Generate structured release notes from the Jira ticket summaries and descriptions below.\n"
        "Use only the provided Jira data.\n\n"
        f"{json.dumps(issue_payload_for_ai(issues), indent=2)}"
    )

    model = (os.getenv("OPENAI_MODEL") or "gpt-5-mini").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=ReleaseNotesDraft,
        )
        parsed = response.output_parsed
        if not parsed:
            raise RuntimeError("OpenAI returned no parsed release note draft.")
        return compact_release_draft(parsed)
    except Exception as exc:
        message = str(exc)
        if len(message) > 240:
            message = message[:240].rstrip() + "..."
        return fallback_release_notes(
            release,
            environment,
            detail_level,
            issues,
            extra_notes=[
                "AI drafting fell back to the deterministic Jira-based draft.",
                f"OpenAI response: {message}",
            ],
        )


def jql_macro(release: str) -> str:
    jql = f'fixVersion = "{release}" ORDER BY issuetype ASC, key ASC'
    columns = "key,summary,type,status,priority,assignee,updated,fixVersion"
    return (
        f'<ac:structured-macro ac:name="jira" ac:schema-version="1">'
        f'  <ac:parameter ac:name="jqlQuery">{html.escape(jql)}</ac:parameter>'
        f'  <ac:parameter ac:name="columns">{html.escape(columns)}</ac:parameter>'
        f'  <ac:parameter ac:name="maximumIssues">200</ac:parameter>'
        f'  <ac:parameter ac:name="cache">true</ac:parameter>'
        f"</ac:structured-macro>"
    )


def render_quality_table(summary: Optional[TestRunSummary]) -> str:
    if summary is None:
        return (
            "<p>TestRail quality data is not available for this draft. "
            "Add TestRail configuration or pass a run ID to include release validation metrics.</p>"
        )

    return (
        "<table>"
        "<tbody>"
        f"<tr><th>Run</th><td><a href=\"{html.escape(summary.run_url)}\">{html.escape(summary.run_name)}</a></td></tr>"
        f"<tr><th>Total tests</th><td>{summary.total}</td></tr>"
        f"<tr><th>Passed</th><td>{summary.passed}</td></tr>"
        f"<tr><th>Failed</th><td>{summary.failed}</td></tr>"
        f"<tr><th>Blocked</th><td>{summary.blocked}</td></tr>"
        f"<tr><th>Retest</th><td>{summary.retest}</td></tr>"
        f"<tr><th>Untested</th><td>{summary.untested}</td></tr>"
        f"<tr><th>Bugs found</th><td>{summary.defects_found}</td></tr>"
        f"<tr><th>Bugs resolved</th><td>{summary.defects_resolved}</td></tr>"
        f"<tr><th>Open bugs</th><td>{summary.defects_open}</td></tr>"
        "</tbody>"
        "</table>"
    )


def build_confluence_storage_body(
    release: str,
    environment: str,
    environment_display: str,
    release_date: str,
    draft: ReleaseNotesDraft,
    quality_summary: Optional[TestRunSummary],
) -> str:
    header_sentence = (
        f"{html.escape(release)} {html.escape(environment_display)} release notes summarize Jira-tracked changes"
    )
    if release_date:
        header_sentence += f" for the release date {html.escape(release_date)}"
    header_sentence += "."

    highlights_html = "".join(
        (
            "<li>"
            f"<strong>{html.escape(item.title)}</strong>: {html.escape(item.summary)} "
            f"<em>({html.escape(', '.join(item.ticket_keys))})</em>"
            "</li>"
        )
        for item in draft.highlights
    )

    themes_html = "".join(
        (
            "<div>"
            f"<h3>{html.escape(theme.heading)}</h3>"
            f"<p>{html.escape(theme.summary)}</p>"
            "<ul>"
            + "".join(f"<li>{html.escape(point)}</li>" for point in theme.bullet_points)
            + "</ul>"
            f"<p><em>Source tickets: {html.escape(', '.join(theme.ticket_keys))}</em></p>"
            "</div>"
        )
        for theme in draft.change_themes
    )

    internal_notes_html = ""
    if draft.internal_notes:
        internal_notes_html = (
            "<h2>Additional Notes</h2><ul>"
            + "".join(f"<li>{html.escape(note)}</li>" for note in draft.internal_notes)
            + "</ul>"
        )

    return (
        f"<h1>{html.escape(release)} — {html.escape(environment)} Release Notes</h1>"
        f"<p>{header_sentence}</p>"
        "<h2>Overview</h2>"
        f"<p>{html.escape(draft.overview)}</p>"
        "<h2>Highlights</h2>"
        f"<ul>{highlights_html}</ul>"
        "<h2>What Changed</h2>"
        f"{themes_html}"
        "<h2>Quality Validation</h2>"
        f"<p><strong>Validation scope:</strong> {html.escape(environment_display)}</p>"
        f"{render_quality_table(quality_summary)}"
        f"{internal_notes_html}"
        "<h2>Included Jira Tickets</h2>"
        f"{jql_macro(release)}"
    )


def donut_segments(summary: TestRunSummary) -> str:
    total = max(summary.total, 1)
    segments = [
        ("Passed", summary.passed, "#2f7d5c"),
        ("Failed", summary.failed, "#b54b3b"),
        ("Blocked", summary.blocked, "#c8922d"),
        ("Retest", summary.retest, "#7d5fd6"),
        ("Untested", summary.untested, "#6f7b83"),
    ]

    circumference = 2 * 3.14159 * 54
    current = 0.0
    svg_parts: List[str] = []
    for _, value, color in segments:
        if value <= 0:
            continue
        ratio = value / total
        dash = ratio * circumference
        gap = circumference - dash
        svg_parts.append(
            f'<circle r="54" cx="80" cy="80" fill="transparent" stroke="{color}" '
            f'stroke-width="18" stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="-{current:.2f}" transform="rotate(-90 80 80)" />'
        )
        current += dash
    return "".join(svg_parts)


def build_preview_html(
    release: str,
    environment: str,
    environment_display: str,
    release_date: str,
    draft: ReleaseNotesDraft,
    quality_summary: Optional[TestRunSummary],
    issues: Sequence[JiraIssue],
) -> str:
    quality_cards = ""
    donut = ""
    defect_list = ""
    if quality_summary:
        quality_cards = (
            f'<div class="metric"><span>Total Tests</span><strong>{quality_summary.total}</strong></div>'
            f'<div class="metric"><span>Passed</span><strong>{quality_summary.passed}</strong></div>'
            f'<div class="metric"><span>Failed</span><strong>{quality_summary.failed}</strong></div>'
            f'<div class="metric"><span>Bugs Found</span><strong>{quality_summary.defects_found}</strong></div>'
            f'<div class="metric"><span>Bugs Resolved</span><strong>{quality_summary.defects_resolved}</strong></div>'
        )
        donut = (
            '<div class="chart-card">'
            '<svg viewBox="0 0 160 160" class="donut">'
            '<circle r="54" cx="80" cy="80" fill="transparent" stroke="#e7dcc7" stroke-width="18" />'
            f"{donut_segments(quality_summary)}"
            f'<text x="80" y="78" text-anchor="middle" class="donut-total">{quality_summary.total}</text>'
            '<text x="80" y="98" text-anchor="middle" class="donut-label">tests</text>'
            "</svg>"
            f'<p class="chart-caption">{html.escape(quality_summary.run_name)}</p>'
            "</div>"
        )
        if quality_summary.defect_keys:
            defect_list = (
                "<div class=\"defects\"><h4>Linked Defects</h4><p>"
                + html.escape(", ".join(quality_summary.defect_keys[:20]))
                + (" ..." if len(quality_summary.defect_keys) > 20 else "")
                + "</p></div>"
            )
    else:
        quality_cards = "<p class=\"muted\">No TestRail run was resolved for this preview.</p>"

    highlight_cards = "".join(
        (
            '<article class="highlight">'
            f"<h3>{html.escape(item.title)}</h3>"
            f"<p>{html.escape(item.summary)}</p>"
            f'<span class="chips">{html.escape(", ".join(item.ticket_keys))}</span>'
            "</article>"
        )
        for item in draft.highlights
    )

    theme_sections = "".join(
        (
            '<section class="theme">'
            f"<h3>{html.escape(theme.heading)}</h3>"
            f"<p>{html.escape(theme.summary)}</p>"
            "<ul>"
            + "".join(f"<li>{html.escape(point)}</li>" for point in theme.bullet_points)
            + "</ul>"
            f'<p class="source">Source: {html.escape(", ".join(theme.ticket_keys))}</p>'
            "</section>"
        )
        for theme in draft.change_themes
    )

    issue_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(issue.key)}</td>"
            f"<td>{html.escape(issue.issue_type)}</td>"
            f"<td>{html.escape(issue.summary)}</td>"
            f"<td>{html.escape(issue.status)}</td>"
            "</tr>"
        )
        for issue in issues
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(release)} {html.escape(environment)} Release Dashboard</title>
  <style>
    :root {{
      --bg: #f4efe4;
      --panel: #fff9ef;
      --ink: #21342f;
      --muted: #5d6e67;
      --accent: #c96b43;
      --accent-2: #2f7d5c;
      --border: #e6d7bd;
      --shadow: 0 18px 42px rgba(69, 57, 38, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(201,107,67,0.18), transparent 32%),
        linear-gradient(180deg, #fbf6ee 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 22px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    h1, h2, h3, h4 {{
      margin: 0 0 12px;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: -0.02em;
    }}
    h1 {{
      font-size: 2.5rem;
      margin-bottom: 8px;
    }}
    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin: 10px 0 18px;
    }}
    .pill {{
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(47,125,92,0.1);
      color: var(--accent-2);
      font-weight: 700;
      font-size: 0.9rem;
    }}
    .lede {{
      font-size: 1.08rem;
      line-height: 1.6;
      color: var(--muted);
      max-width: 58ch;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric {{
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric span {{
      display: block;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .metric strong {{
      font-size: 1.8rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 20px;
      margin-bottom: 22px;
    }}
    .highlights {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .highlight {{
      padding: 18px;
      background: rgba(255,255,255,0.72);
      border-radius: 18px;
      border: 1px solid var(--border);
    }}
    .highlight p {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .chips, .source {{
      color: var(--accent);
      font-size: 0.9rem;
      font-weight: 600;
    }}
    .theme {{
      padding: 18px 0;
      border-top: 1px solid var(--border);
    }}
    .theme:first-of-type {{
      border-top: 0;
      padding-top: 0;
    }}
    .theme p, .theme li, .muted {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .quality-layout {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 18px;
      align-items: center;
    }}
    .donut {{
      width: 100%;
      max-width: 180px;
      display: block;
      margin: 0 auto;
    }}
    .donut-total {{
      font-size: 2rem;
      font-weight: 800;
      fill: var(--ink);
    }}
    .donut-label {{
      fill: var(--muted);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .chart-caption {{
      text-align: center;
      color: var(--muted);
      margin-top: 8px;
      font-size: 0.95rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    @media (max-width: 900px) {{
      .hero, .grid, .quality-layout {{
        grid-template-columns: 1fr;
      }}
      .metrics {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="card">
        <h1>{html.escape(release)} / {html.escape(environment)}</h1>
        <div class="meta">
          <span class="pill">Release Date: {html.escape(release_date or "TBD")}</span>
          <span class="pill">Environment: {html.escape(environment_display)}</span>
          <span class="pill">Tickets: {len(issues)}</span>
        </div>
        <p class="lede">{html.escape(draft.overview)}</p>
      </div>
      <div class="card">
        <h2>Quality Snapshot</h2>
        <div class="metrics">{quality_cards}</div>
      </div>
    </section>

    <section class="card" style="margin-bottom: 22px;">
      <h2>Highlights</h2>
      <div class="highlights">{highlight_cards}</div>
    </section>

    <section class="grid">
      <div class="card">
        <h2>What Changed</h2>
        {theme_sections}
      </div>
      <div class="card">
        <h2>Validation Dashboard</h2>
        <div class="quality-layout">
          {donut}
          <div>
            <p><strong>Validation scope:</strong> {html.escape(environment_display)}</p>
            <p class="muted">TestRail data stays separate from the Jira-driven release narrative. This panel is meant to support release confidence, not to generate the notes themselves.</p>
            {defect_list}
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Included Jira Tickets</h2>
      <table>
        <thead>
          <tr><th>Key</th><th>Type</th><th>Summary</th><th>Status</th></tr>
        </thead>
        <tbody>
          {issue_rows}
        </tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate VAL/PROD release notes from Jira, with TestRail quality metrics kept separate."
    )
    parser.add_argument("release", help="Release key such as WMS_07.00_2026")
    parser.add_argument("environment", choices=["VAL", "PROD"], help="Release note environment")
    parser.add_argument(
        "--detail-level",
        choices=["business", "mixed", "technical"],
        default="mixed",
        help="AI release note detail level. Default: mixed",
    )
    parser.add_argument(
        "--release-date",
        default="",
        help="Optional release date in YYYY-MM-DD format. Defaults to Jira version release date when available.",
    )
    parser.add_argument(
        "--preview-file",
        default="",
        help="Optional path for a local HTML dashboard preview.",
    )
    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="Optional explicit TestRail run ID for the environment summary.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the generated notes to Confluence. Default is draft-only/local preview.",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Maximum Jira issues to fetch for the release. Default: 200",
    )
    return parser.parse_args()


def print_draft(draft: ReleaseNotesDraft, quality_summary: Optional[TestRunSummary]) -> None:
    print("\nOverview:")
    print(draft.overview)

    print("\nHighlights:")
    for item in draft.highlights:
        print(f"- {item.title}: {item.summary} [{', '.join(item.ticket_keys)}]")

    print("\nWhat Changed:")
    for theme in draft.change_themes:
        print(f"- {theme.heading}: {theme.summary}")
        for bullet in theme.bullet_points:
            print(f"  • {bullet}")
        print(f"  Source tickets: {', '.join(theme.ticket_keys)}")

    if draft.internal_notes:
        print("\nAdditional Notes:")
        for note in draft.internal_notes:
            print(f"- {note}")

    print("\nQuality Validation:")
    if quality_summary is None:
        print("- TestRail metrics unavailable")
    else:
        print(
            f"- Run {quality_summary.run_name}: "
            f"{quality_summary.passed} passed, {quality_summary.failed} failed, "
            f"{quality_summary.blocked} blocked, {quality_summary.untested} untested, "
            f"{quality_summary.defects_found} bugs found, {quality_summary.defects_resolved} resolved"
        )


def publish_release_notes(
    conf: ConfluenceConfig,
    release: str,
    environment: str,
    storage_body: str,
) -> str:
    confluence_get_space_or_fail(conf)
    parent_id = confluence_resolve_or_create_path(conf, conf.parent_path)
    page_title = f"{release} — {environment} Release Notes"
    existing = confluence_find_child_by_title(conf, parent_id, page_title)
    if existing:
        title, version = confluence_get_title_and_version(conf, existing)
        confluence_update_storage(conf, existing, title, storage_body, version)
        return f"{conf.base_url}/pages/viewpage.action?pageId={existing}"

    page_id = confluence_create_child(conf, page_title, parent_id, storage_body)
    return f"{conf.base_url}/pages/viewpage.action?pageId={page_id}"


def main() -> None:
    load_env()
    args = parse_args()

    jira_config = build_jira_config()
    confluence_config = build_confluence_config() if args.publish else None
    testrail_config = build_testrail_config()

    release_date = args.release_date or jira_get_release_date(jira_config, args.release)
    issues = jira_search_release_issues(jira_config, args.release, max_results=args.max_issues)
    if not issues:
        raise RuntimeError(f"No Jira issues found for release {args.release}.")

    draft = generate_release_notes_with_ai(
        release=args.release,
        environment=args.environment,
        detail_level=args.detail_level,
        issues=issues,
    )
    environment_display = environment_label(args.environment, testrail_config)
    quality_summary = build_test_run_summary(
        jira_config=jira_config,
        tr_config=testrail_config,
        release=args.release,
        environment=args.environment,
        run_id=args.run_id,
    )

    storage_body = build_confluence_storage_body(
        release=args.release,
        environment=args.environment,
        environment_display=environment_display,
        release_date=release_date,
        draft=draft,
        quality_summary=quality_summary,
    )

    print(f"[INFO] Built release note draft for {args.release} / {args.environment}")
    print_draft(draft, quality_summary)

    preview_path = Path(args.preview_file) if args.preview_file else (
        PROJECT_DIR / "previews" / f"{args.release}_{args.environment}_dashboard.html"
    )
    ensure_parent_dir(preview_path)
    preview_path.write_text(
        build_preview_html(
            release=args.release,
            environment=args.environment,
            environment_display=environment_display,
            release_date=release_date,
            draft=draft,
            quality_summary=quality_summary,
            issues=issues,
        ),
        encoding="utf-8",
    )
    print(f"\n[INFO] Preview written to {preview_path}")

    if args.publish:
        assert confluence_config is not None
        page_url = publish_release_notes(
            conf=confluence_config,
            release=args.release,
            environment=args.environment,
            storage_body=storage_body,
        )
        print(f"[INFO] Confluence page updated: {page_url}")
    else:
        print("\n[INFO] Draft only. Re-run with --publish when you are ready to post to Confluence.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
