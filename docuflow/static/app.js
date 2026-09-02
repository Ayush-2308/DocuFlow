const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file");
const fileLabel = document.getElementById("file-label");
const drop = document.getElementById("drop");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const submit = document.getElementById("submit");

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
    renderResult(result);
  } catch (error) {
    statusEl.textContent = error.message || "Something went wrong.";
  } finally {
    submit.disabled = false;
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

function renderResult(data) {
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

  resultEl.hidden = false;
  resultEl.innerHTML = `
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
