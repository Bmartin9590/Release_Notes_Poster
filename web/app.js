const $ = (selector) => document.querySelector(selector);

const form = $("#releaseForm");
const runButton = $("#runButton");
const previewButton = $("#previewButton");
const outputLog = $("#outputLog");
const jobStatus = $("#jobStatus");
const pageLink = $("#pageLink");
const configStatus = $("#configStatus");
const confSummary = $("#confSummary");
const jiraSummary = $("#jiraSummary");
const previewCard = $("#previewCard");
const previewTitle = $("#previewTitle");
const previewSentence = $("#previewSentence");
const previewJql = $("#previewJql");
const previewColumns = $("#previewColumns");
const previewMaxIssues = $("#previewMaxIssues");
const previewDateNote = $("#previewDateNote");

let pollTimer = null;

function setLog(lines) {
  outputLog.textContent = lines && lines.length ? lines.join("\n") : "Waiting for output...";
  outputLog.scrollTop = outputLog.scrollHeight;
}

function setJobStatus(job) {
  const labels = {
    queued: "Queued",
    running: "Running",
    success: "Completed",
    failed: "Failed",
  };
  jobStatus.textContent = labels[job.status] || "Waiting";
  runButton.disabled = job.status === "queued" || job.status === "running";
  previewButton.disabled = job.status === "queued" || job.status === "running";

  if (job.pageUrl) {
    pageLink.href = job.pageUrl;
    pageLink.classList.remove("hidden");
  }
}

function currentPayload() {
  return {
    release: $("#release").value.trim(),
    releaseDate: $("#releaseDate").value.trim(),
  };
}

function renderPreview(preview) {
  previewTitle.textContent = preview.title;
  previewSentence.textContent = preview.sentence;
  previewJql.textContent = preview.jql;
  previewColumns.textContent = preview.columns;
  previewMaxIssues.textContent = String(preview.maximumIssues);
  previewDateNote.textContent = preview.dateNote;
  previewCard.classList.remove("hidden");
  jobStatus.textContent = "Preview ready";
  setLog([
    "Preview generated locally.",
    "No Confluence page was created or updated.",
    "",
    `Title: ${preview.title}`,
    `JQL: ${preview.jql}`,
  ]);
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const config = await response.json();

  configStatus.classList.remove("ready", "missing");
  if (config.ready) {
    configStatus.textContent = "Settings ready";
    configStatus.classList.add("ready");
  } else {
    configStatus.textContent = config.envFileExists ? "Settings missing" : ".env.local missing";
    configStatus.classList.add("missing");
  }

  const confParts = [config.spaceKey, config.confluenceBaseUrl].filter(Boolean);
  confSummary.textContent = confParts.length ? confParts.join(" at ") : "Missing Confluence settings";

  const jiraParts = [config.jiraProjectKey, config.jiraBaseUrl].filter(Boolean);
  jiraSummary.textContent = jiraParts.length ? jiraParts.join(" at ") : "Jira date lookup optional";
}

async function pollJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  const job = await response.json();

  if (!response.ok) {
    throw new Error(job.error || "Unable to load job.");
  }

  setJobStatus(job);
  setLog(job.output);

  if (job.status === "success" || job.status === "failed") {
    clearInterval(pollTimer);
    pollTimer = null;
    runButton.disabled = false;
    if (job.error) {
      setLog([...job.output, job.error]);
    }
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearInterval(pollTimer);
  pageLink.classList.add("hidden");
  pageLink.href = "#";

  const payload = {
    ...currentPayload(),
    confirmed: $("#confirmed").checked,
  };

  runButton.disabled = true;
  jobStatus.textContent = "Starting";
  setLog(["Starting release notes poster..."]);

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const job = await response.json();

    if (!response.ok) {
      throw new Error(job.error || "Unable to start run.");
    }

    setJobStatus(job);
    setLog(job.output);
    pollTimer = setInterval(() => pollJob(job.id).catch(handleError), 1000);
    await pollJob(job.id);
  } catch (error) {
    handleError(error);
  }
});

previewButton.addEventListener("click", async () => {
  clearInterval(pollTimer);
  pageLink.classList.add("hidden");
  pageLink.href = "#";
  previewButton.disabled = true;
  runButton.disabled = false;
  jobStatus.textContent = "Generating preview";
  setLog(["Generating preview locally..."]);

  try {
    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentPayload()),
    });
    const preview = await response.json();

    if (!response.ok) {
      throw new Error(preview.error || "Unable to generate preview.");
    }

    renderPreview(preview);
  } catch (error) {
    handleError(error);
  } finally {
    previewButton.disabled = false;
  }
});

function handleError(error) {
  clearInterval(pollTimer);
  pollTimer = null;
  runButton.disabled = false;
  previewButton.disabled = false;
  jobStatus.textContent = "Failed";
  setLog([error.message || String(error)]);
}

loadConfig().catch(handleError);
