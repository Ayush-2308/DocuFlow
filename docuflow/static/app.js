const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file");
const fileLabel = document.getElementById("file-label");
const drop = document.getElementById("drop");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const submit = document.getElementById("submit");
const tabUpload = document.getElementById("tab-upload");
const tabSearch = document.getElementById("tab-search");
const panelUpload = document.getElementById("panel-upload");
const panelSearch = document.getElementById("panel-search");
const searchForm = document.getElementById("search-form");
const searchQuery = document.getElementById("search-query");
const searchKey = document.getElementById("search-api-key");
const searchSubmit = document.getElementById("search-submit");
const searchStatus = document.getElementById("search-status");
const searchResult = document.getElementById("search-result");

const savedKey = sessionStorage.getItem("docuflowSearchKey");
if (savedKey && searchKey) searchKey.value = savedKey;

function showTab(name) {
  const upload = name === "upload";
  tabUpload.classList.toggle("is-active", upload);
  tabSearch.classList.toggle("is-active", !upload);
  tabUpload.setAttribute("aria-selected", String(upload));
  tabSearch.setAttribute("aria-selected", String(!upload));
  panelUpload.hidden = !upload;
  panelSearch.hidden = upload;
}

tabUpload.addEventListener("click", () => showTab("upload"));
tabSearch.addEventListener("click", () => showTab("search"));

fileInput.addEventListener("change", () => {
  fileLabel.textContent = fileInput.files[0]?.name || "Drop a PDF or image here";
});

["dragenter", "dragover"].forEach((eventName) => {
  drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    drop.classList.add("drag");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    drop.classList.remove("drag");
  });
});
drop.addEventListener("drop", (event) => {
  const files = event.dataTransfer?.files;
  if (files && files[0]) {
    fileInput.files = files;
    fileLabel.textContent = files[0].name;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;

  const body = new FormData();
  body.append("file", file);
  body.append("doc_type_hint", document.getElementById("doc_type_hint").value);

  submit.disabled = true;
  resultEl.hidden = true;
  statusEl.hidden = false;
  statusEl.textContent = "Queued. OCR and extraction run in the background…";

  try {
    const started = await fetch("/upload", { method: "POST", body });
    const startPayload = await started.json();
    if (!started.ok) {
      throw new Error(startPayload.detail || "Upload failed");
    }
    const result = await pollJob(startPayload.job_id);
    statusEl.textContent = "Done.";
    renderResult(resultEl, result);
  } catch (error) {
    statusEl.textContent = error.message || "Something went wrong.";
  } finally {
    submit.disabled = false;
  }
});

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = searchQuery.value.trim();
  const apiKey = searchKey.value.trim();
  if (!query || !apiKey) return;
  sessionStorage.setItem("docuflowSearchKey", apiKey);

  searchSubmit.disabled = true;
  searchResult.hidden = true;
  searchStatus.hidden = false;
  searchStatus.textContent = "Searching stored records…";

  try {
    const response = await fetch(`/search?query=${encodeURIComponent(query)}`, {
      headers: { "X-API-Key": apiKey },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Search failed");
    }
    searchStatus.textContent = payload.results?.length
      ? `Found ${payload.results.length} record(s).`
      : "No matching records.";
    renderSearchResults(payload);
  } catch (error) {
    searchStatus.textContent = error.message || "Search failed.";
  } finally {
    searchSubmit.disabled = false;
  }
});

async function pollJob(jobId) {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    const response = await fetch(`/jobs/${jobId}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Lost job status");
    }
    if (payload.status === "done") {
      return payload.result;
    }
    if (payload.status === "error") {
      throw new Error(payload.error || "Pipeline failed");
    }
    statusEl.textContent = "Still working (OCR + AI). Keep this tab open…";
  }
  throw new Error("Timed out after 5 minutes. Try again in a bit.");
}

function renderSearchResults(payload) {
  const hits = payload.results || [];
  searchResult.hidden = false;
  if (!hits.length) {
    searchResult.innerHTML = "<p>No stored documents matched that query.</p>";
    return;
  }
  searchResult.innerHTML = hits
    .map((hit) => {
      const data = hit.data || {};
      const rows = Object.entries(data)
        .map(([key, value]) => {
          const shown =
            typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "—");
          return `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(shown)}</dd>`;
        })
        .join("");
      return `
        <article class="search-hit">
          <div class="meta">
            <span class="chip">${escapeHtml(hit.document_type || "unknown")}</span>
            <span class="chip">${escapeHtml(hit.document_id || "")}</span>
          </div>
          <dl>${rows}</dl>
        </article>`;
    })
    .join("");
}

function renderResult(target, data) {
  const score = data.confidence_score;
  const status = data.status || "";
  const chipClass =
    status === "stored" ? "ok" : status === "needs_review" ? "warn" : "bad";
  const extracted = data.extracted_data || {};
  const rows = Object.entries(extracted)
    .map(([key, value]) => {
      const shown =
        typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "—");
      return `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(shown)}</dd>`;
    })
    .join("");
  const errors = (data.validation_errors || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  target.hidden = false;
  target.innerHTML = `
    <div class="meta">
      <span class="chip ${chipClass}">${escapeHtml(status || "unknown")}</span>
      <span class="chip">${escapeHtml(data.category || "Uncategorized")}</span>
      <span class="chip">confidence ${score == null ? "—" : Number(score).toFixed(2)}</span>
    </div>
    <h2>Extracted fields</h2>
    <dl>${rows || "<dt>None</dt><dd>No structured fields returned.</dd>"}</dl>
    ${errors ? `<h2>Validation</h2><ul class="errors">${errors}</ul>` : ""}
    <details>
      <summary>Raw OCR text</summary>
      <pre>${escapeHtml(data.raw_text || "")}</pre>
    </details>
    <details>
      <summary>Full JSON</summary>
      <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
    </details>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
