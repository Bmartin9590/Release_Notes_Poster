# Release Notes Poster

This folder now contains two release-note flows:

- `Scripts/ReleaseNotesPoster.py`
  Preserves the original POC that creates or updates a Confluence page with a Jira macro.
- `Scripts/ReleaseNotesCopilot.py`
  Builds a richer `VAL` or `PROD` release note draft from Jira tickets, keeps TestRail data in a separate quality section, writes a dashboard-style HTML preview, and can publish to Confluence.

## Environment

Create `.env.local` in this folder with your Confluence and Jira settings:

```dotenv
CONF_BASE_URL=https://your-confluence.example.com
CONF_TOKEN=replace_me
CONF_SPACE_KEY=ABC
CONF_PARENT_PATH=Medicaid and CHIP Business Information Solution (MACBIS)/MACBIS Archive/ARCHIVE - MAC Suite Teams/Knight Riders/WMS & MMDL Releases
CONF_CREATE_PARENT_PATH=false

JIRA_BASE_URL=https://your-jira.example.com
JIRA_TOKEN=replace_me
JIRA_PROJECT_KEY=OY2
```

You can also start from:

```bash
cp .env.example .env.local
```

Optional AI settings:

```dotenv
OPENAI_API_KEY=replace_me
OPENAI_MODEL=gpt-5-mini
```

Optional TestRail settings:

```dotenv
TESTRAIL_BASE_URL=https://your-testrail.example.com
TESTRAIL_USERNAME=your.email@example.com
TESTRAIL_API_KEY=replace_me
TESTRAIL_PROJECT_ID=123  # optional; if omitted, the original poster searches accessible projects
TESTRAIL_PROJECT_NAME=WMS & MMDL  # optional; filters accessible projects by name
TESTRAIL_RUN_ID_DEV=12345  # optional; bypasses name search for DEV
TESTRAIL_RUN_ID_VAL=12346  # optional; bypasses name search for VAL
TESTRAIL_RUN_ID_PROD=12347  # optional; bypasses name search for PROD
TESTRAIL_RUN_NAME_TEMPLATE_DEV={release} - DEV (Functional Testing)
TESTRAIL_RUN_NAME_TEMPLATE_VAL={release} - VAL (Regression Testing)
TESTRAIL_RUN_NAME_TEMPLATE_PROD={release} - PROD (Smoke Testing)
TESTRAIL_ENV_LABEL_DEV=DEV Functional Testing
TESTRAIL_ENV_LABEL_VAL=VAL Regression Testing
TESTRAIL_ENV_LABEL_PROD=PROD Smoke Testing
TESTRAIL_ATTACH_SNAPSHOT=true
```

`ReleaseNotesCopilot.py` also tries to reuse TestRail credentials from [CaseForge/.env](/Users/64055/Automation/CaseForge/.env).

## Quick Start

### Original Poster Flow

Create or update the Confluence page using the original non-Copilot flow:

```bash
cd /Users/64055/Automation/Release_Notes_Poster
./run.sh WMS_07.00_2026
```

On Windows:

```bat
cd path\to\Release_Notes_Poster
run.bat WMS_07.00_2026
```

Pass a release date manually:

```bash
./run.sh WMS_07.00_2026 2026-06-09
```

On Windows:

```bat
run.bat WMS_07.00_2026 2026-06-09
```

If the date is omitted, the script tries to use the Jira version release date.

### Local UI

Start the browser UI for the original non-Copilot flow:

```bash
python3 ui_server.py
```

On Windows, double-click `launch_ui.bat` or run:

```bat
py -3 ui_server.py
```

Or from the main `Automation` folder:

```bash
make release-notes-ui
```

Then open:

```text
http://127.0.0.1:8770
```

The UI runs `run_poster.py`, which bootstraps `.venv` and calls `Scripts/ReleaseNotesPoster.py` on macOS, Linux, and Windows. It does not use `run_copilot.sh`, `ReleaseNotesCopilot.py`, or OpenAI settings. If TestRail settings are present, the poster looks for DEV, VAL, and PROD TestRail runs, attaches generated quality snapshots to the Confluence page, and embeds the TestRail validation section at the bottom of the page. If `TESTRAIL_RUN_ID_DEV`, `TESTRAIL_RUN_ID_VAL`, or `TESTRAIL_RUN_ID_PROD` is set, the original poster uses that exact run for the matching environment; otherwise, if `TESTRAIL_PROJECT_ID` is omitted, it searches accessible TestRail projects for matching runs. Set `TESTRAIL_PROJECT_NAME=WMS & MMDL` to filter that accessible project list by name.

Use `Preview` to review the page title, release sentence, Jira macro JQL, columns, and issue limit without creating or updating a Confluence page.

By default, posting expects `CONF_PARENT_PATH` to already exist in Confluence. If a path segment is missing, the run fails with the missing segment name instead of creating pages in an unexpected location. Set `CONF_CREATE_PARENT_PATH=true` only if you want the scripts to auto-create missing parent pages.

macOS launcher:

```text
launch_ui.command
```

Windows launcher:

```text
launch_ui.bat
```

### Copilot Flow

Draft VAL release notes and write a dashboard preview:

```bash
cd /Users/64055/Automation/Release_Notes_Poster
./run_copilot.sh WMS_07.00_2026 VAL --preview-file previews/WMS_07.00_2026_VAL.html
```

Publish to Confluence once the draft looks right:

```bash
./run_copilot.sh WMS_07.00_2026 PROD --publish --preview-file previews/WMS_07.00_2026_PROD.html
```

## Copilot Notes

- Release note narrative is generated from Jira tickets only.
- TestRail contributes quality metrics only, such as pass/fail counts and defect totals.
- The default detail level is `mixed`, which keeps meaningful workflow and module names while avoiding code-level implementation jargon.
- `VAL` and `PROD` are the only supported environments for the copilot flow.
- Default TestRail run matching expects:
  `WMS_07.00_2026 - DEV (Functional Testing)`,
  `WMS_07.00_2026 - VAL (Regression Testing)`,
  `WMS_07.00_2026 - PROD (Smoke Testing)`.
