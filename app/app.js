const form = document.querySelector("#generator-form");
const fileInput = document.querySelector("#resume-file");
const uploadLabel = document.querySelector("#upload-label");
const button = document.querySelector("#generate-button");
const toast = document.querySelector("#toast");
const results = document.querySelector("#results");
const emptyState = document.querySelector("#empty-state");
const tabs = document.querySelector("#tabs");
const previewTitle = document.querySelector("#preview-title");
const previewContent = document.querySelector("#preview-content");
const activeDownload = document.querySelector("#active-download");

const views = [
  ["resume", "Tailored resume", "tailored_resume.docx"],
  ["cover", "Cover letter", "cover_letter.md"],
  ["coverTex", "Cover letter LaTeX", "cover_letter.tex"],
  ["dm", "Recruiter DM", "recruiter_dm.md"],
  ["brief", "Application brief", "application_brief.md"],
];

let currentData = null;

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  uploadLabel.innerHTML = `<strong>${escapeHtml(file.name)}</strong><small>${formatBytes(file.size)}</small>`;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideToast();
  button.disabled = true;
  button.lastChild.textContent = " Generating...";

  try {
    const file = fileInput.files[0];
    const resumeData = file ? await readFileAsBase64(file) : "";
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: document.querySelector("#job-url").value,
        jd_text: document.querySelector("#jd-text").value,
        instructions: document.querySelector("#instructions").value,
        cover_instructions: document.querySelector("#cover-instructions").value,
        company_name: document.querySelector("#company-name").value,
        role_name: document.querySelector("#role-name").value,
        resume_name: file?.name || "",
        resume_data: resumeData,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Generation failed.");
    currentData = data;
    renderResults(data);
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
    button.lastChild.textContent = " Generate package";
  }
});

function renderResults(data) {
  emptyState.hidden = true;
  results.hidden = false;
  document.querySelector("#result-title").textContent = humanize(data.role_type) + " application";
  document.querySelector("#result-meta").textContent =
    `${data.bullet_count} sourced points · Base: ${data.base_source || "general vault"}`;
  document.querySelector("#skill-list").innerHTML = data.skills
    .map((skill) => `<span>${escapeHtml(skill)}</span>`).join("");

  tabs.innerHTML = "";
  views.forEach(([key, label]) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.textContent = label;
    tab.addEventListener("click", () => selectView(key));
    tab.dataset.key = key;
    tabs.appendChild(tab);
  });

  document.querySelector("#artifact-list").innerHTML = data.artifacts.map((artifact) => {
    if (!artifact.available) {
      const note = artifact.name.endsWith(".pdf") ? "compiler unavailable" : "not generated";
      return `<div class="artifact unavailable"><span>${escapeHtml(artifact.name)}</span><small>${note}</small></div>`;
    }
    return `<div class="artifact"><span>${escapeHtml(artifact.name)}</span><a href="${artifact.url}" download>Download</a></div>`;
  }).join("");

  selectView("resume");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectView(key) {
  const view = views.find(([viewKey]) => viewKey === key);
  if (!view || !currentData) return;
  const [, label, filename] = view;
  tabs.querySelectorAll("button").forEach((tab) => tab.classList.toggle("active", tab.dataset.key === key));
  previewTitle.textContent = label;
  previewContent.textContent = currentData.previews[key] || "Preview unavailable.";
  const artifact = currentData.artifacts.find((item) => item.name === filename && item.available);
  activeDownload.hidden = !artifact;
  if (artifact) activeDownload.href = artifact.url;
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(new Error("Could not read the resume file."));
    reader.readAsDataURL(file);
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function humanize(value) {
  return value.split("-").map((word) => {
    if (word === "ai") return "AI";
    if (word === "sre") return "SRE";
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(" / ");
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
}

function hideToast() {
  toast.hidden = true;
}
