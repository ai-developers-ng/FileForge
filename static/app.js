// ============================================
// CSRF Token
// ============================================
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

// ============================================
// SSE Helper - stream job progress with polling fallback
// ============================================
const streamJob = (jobId, onUpdate) => {
  if (typeof EventSource !== "undefined") {
    const es = new EventSource(`/api/jobs/${jobId}/stream`);
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onUpdate(data);
      if (data.status === "completed" || data.status === "failed") {
        es.close();
      }
    };
    es.onerror = () => {
      es.close();
      const poll = async () => {
        const response = await fetch(`/api/jobs/${jobId}`);
        const job = await response.json();
        onUpdate(job);
        if (job.status !== "completed" && job.status !== "failed") {
          setTimeout(poll, 2000);
        }
      };
      poll();
    };
  } else {
    const poll = async () => {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      onUpdate(job);
      if (job.status !== "completed" && job.status !== "failed") {
        setTimeout(poll, 2000);
      }
    };
    poll();
  }
};

// ============================================
// Tab Switching
// ============================================
const tabs = document.querySelectorAll(".tab[data-tab]");
const tabPanels = document.querySelectorAll(".tab-panel");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    if (tab.getAttribute("aria-disabled") === "true") return;

    tabs.forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    tabPanels.forEach((p) => {
      p.classList.remove("active");
    });

    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    const panelId = tab.dataset.tab + "-panel";
    const panel = document.getElementById(panelId);
    if (panel) {
      panel.classList.add("active");
    }
  });
});

// ============================================
// OCR Tab Elements & State
// ============================================
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const uploadForm = document.getElementById("uploadForm");
const statusMessage = document.getElementById("statusMessage");
const resultFilename = document.getElementById("resultFilename");
const resultStatus = document.getElementById("resultStatus");
const resultText = document.getElementById("resultText");
const downloadTxt = document.getElementById("downloadTxt");
const downloadJson = document.getElementById("downloadJson");
const downloadPdf = document.getElementById("downloadPdf");
const copyText = document.getElementById("copyText");
const progressFill = document.getElementById("progressFill");
const progressPercent = document.getElementById("progressPercent");
const progressTrack = document.querySelector("#ocr-panel .progress-track");

let selectedFiles = [];
let activeJobs = [];
let lastJobMode = "text";

// ============================================
// Image Converter Tab Elements & State
// ============================================
const imageDropzone = document.getElementById("imageDropzone");
const imageFileInput = document.getElementById("imageFileInput");
const imageFileList = document.getElementById("imageFileList");
const imageUploadForm = document.getElementById("imageUploadForm");
const imageStatusMessage = document.getElementById("imageStatusMessage");
const imageResultFilename = document.getElementById("imageResultFilename");
const imageResultStatus = document.getElementById("imageResultStatus");
const imageProgressFill = document.getElementById("imageProgressFill");
const imageProgressPercent = document.getElementById("imageProgressPercent");
const imagePreviewArea = document.getElementById("imagePreviewArea");
const qualitySlider = document.getElementById("qualitySlider");
const qualityValue = document.getElementById("qualityValue");
const brightnessSlider = document.getElementById("brightnessSlider");
const brightnessValue = document.getElementById("brightnessValue");
const contrastSlider = document.getElementById("contrastSlider");
const contrastValue = document.getElementById("contrastValue");

let selectedImageFiles = [];
let activeImageJobs = [];

// ============================================
// Document Converter Tab Elements & State
// ============================================
const documentDropzone = document.getElementById("documentDropzone");
const documentFileInput = document.getElementById("documentFileInput");
const documentFileList = document.getElementById("documentFileList");
const documentUploadForm = document.getElementById("documentUploadForm");
const documentStatusMessage = document.getElementById("documentStatusMessage");
const documentResultFilename = document.getElementById("documentResultFilename");
const documentResultStatus = document.getElementById("documentResultStatus");
const documentProgressFill = document.getElementById("documentProgressFill");
const documentProgressPercent = document.getElementById("documentProgressPercent");
const documentPreviewArea = document.getElementById("documentPreviewArea");

let selectedDocumentFiles = [];
let activeDocumentJobs = [];

// ============================================
// Audio Converter Tab Elements & State
// ============================================
const audioDropzone = document.getElementById("audioDropzone");
const audioFileInput = document.getElementById("audioFileInput");
const audioFileList = document.getElementById("audioFileList");
const audioUploadForm = document.getElementById("audioUploadForm");
const audioStatusMessage = document.getElementById("audioStatusMessage");
const audioResultFilename = document.getElementById("audioResultFilename");
const audioResultStatus = document.getElementById("audioResultStatus");
const audioProgressFill = document.getElementById("audioProgressFill");
const audioProgressPercent = document.getElementById("audioProgressPercent");
const audioPreviewArea = document.getElementById("audioPreviewArea");

let selectedAudioFiles = [];
let activeAudioJobs = [];

// ============================================
// Video Converter Tab Elements & State
// ============================================
const videoDropzone = document.getElementById("videoDropzone");
const videoFileInput = document.getElementById("videoFileInput");
const videoFileList = document.getElementById("videoFileList");
const videoUploadForm = document.getElementById("videoUploadForm");
const videoStatusMessage = document.getElementById("videoStatusMessage");
const videoResultFilename = document.getElementById("videoResultFilename");
const videoResultStatus = document.getElementById("videoResultStatus");
const videoProgressFill = document.getElementById("videoProgressFill");
const videoProgressPercent = document.getElementById("videoProgressPercent");
const videoPreviewArea = document.getElementById("videoPreviewArea");

let selectedVideoFiles = [];
let activeVideoJobs = [];

// ============================================
// OCR Tab Functions
// ============================================
const getSelectedMode = () =>
  uploadForm?.querySelector("input[name='mode']:checked")?.value || "text";

const getAvailabilityForMode = (mode) => {
  switch (mode) {
    case "ocr":
      return { txt: false, json: false, pdf: true, copy: false };
    case "both":
      return { txt: true, json: true, pdf: true, copy: true };
    default:
      return { txt: true, json: true, pdf: false, copy: true };
  }
};

const getDisabledReason = (mode, action, ready) => {
  if (ready) return "";
  const availability = getAvailabilityForMode(mode);
  if (!availability[action]) {
    if (action === "pdf") return "Run PDF to OCRd PDF or OCR + Text extraction.";
    if (action === "txt" || action === "copy") {
      return "Run Text extraction or OCR + Text extraction.";
    }
    if (action === "json") return "Run Text extraction or OCR + Text extraction.";
  }
  return "Run a job to enable this action.";
};

const renderFiles = (files) => {
  if (!fileList) return;
  fileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    fileList.appendChild(pill);
  });
};

const updateFilePillStatus = (index, status, jobId = null) => {
  const pill = fileList?.querySelector(`[data-file-index="${index}"]`);
  if (pill) {
    const statusSpan = pill.querySelector(".file-status");
    if (statusSpan) {
      if (status === "Done" && jobId) {
        const available = getAvailabilityForMode(lastJobMode);
        const links = [];
        if (available.txt) links.push(`<a href="/api/jobs/${jobId}/download/txt" class="file-download-link">TXT</a>`);
        if (available.json) links.push(`<a href="/api/jobs/${jobId}/download/json" class="file-download-link">JSON</a>`);
        if (available.pdf) links.push(`<a href="/api/jobs/${jobId}/download/pdf" class="file-download-link">PDF</a>`);
        statusSpan.innerHTML = links.length > 0 ? links.join(" ") : "Done";
      } else {
        statusSpan.textContent = status;
      }
    }
  }
};

const setStatus = (message) => {
  if (statusMessage) statusMessage.textContent = message;
};

const setResultMeta = (name, status) => {
  if (resultFilename) resultFilename.textContent = name;
  if (resultStatus) resultStatus.textContent = status;
};

const setProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (progressFill) progressFill.style.width = `${safeValue}%`;
  if (progressPercent) progressPercent.textContent = `${Math.round(safeValue)}%`;
  if (progressTrack) progressTrack.setAttribute("aria-valuenow", String(Math.round(safeValue)));
};

const handleFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedFiles = [...files];
  renderFiles(files);
};

const setActionState = (mode, jobId, ready) => {
  if (!downloadTxt || !downloadJson || !downloadPdf || !copyText) return;
  const available = getAvailabilityForMode(mode);
  const enable = (action, isAvailable, setter) => {
    const isReady = Boolean(ready && jobId && isAvailable);
    setter(isReady, isAvailable);
  };

  enable("txt", available.txt, (isReady) => {
    downloadTxt.href = isReady ? `/api/jobs/${jobId}/download/txt` : "#";
    downloadTxt.setAttribute("aria-disabled", isReady ? "false" : "true");
    downloadTxt.title = isReady ? "Download TXT" : getDisabledReason(mode, "txt", false);
  });

  enable("json", available.json, (isReady) => {
    downloadJson.href = isReady ? `/api/jobs/${jobId}/download/json` : "#";
    downloadJson.setAttribute("aria-disabled", isReady ? "false" : "true");
    downloadJson.title = isReady
      ? "Download JSON"
      : getDisabledReason(mode, "json", false);
  });

  enable("pdf", available.pdf, (isReady) => {
    downloadPdf.href = isReady ? `/api/jobs/${jobId}/download/pdf` : "#";
    downloadPdf.setAttribute("aria-disabled", isReady ? "false" : "true");
    downloadPdf.title = isReady ? "Download PDF" : getDisabledReason(mode, "pdf", false);
  });

  enable("copy", available.copy, (isReady) => {
    copyText.disabled = !isReady;
    copyText.setAttribute("aria-disabled", isReady ? "false" : "true");
    copyText.title = isReady ? "Copy text" : getDisabledReason(mode, "copy", false);
  });
};

const calculateOverallProgress = () => {
  if (activeJobs.length === 0) return 0;
  const totalProgress = activeJobs.reduce((sum, job) => sum + (job.progress || 0), 0);
  return totalProgress / activeJobs.length;
};

const updateOverallStatus = () => {
  const completed = activeJobs.filter((j) => j.status === "completed").length;
  const failed = activeJobs.filter((j) => j.status === "failed").length;
  const total = activeJobs.length;

  if (completed + failed === total) {
    if (failed > 0) {
      setStatus(`Completed: ${completed}/${total} (${failed} failed)`);
    } else {
      setStatus(`All ${total} file(s) completed.`);
    }
    setResultMeta(`${completed} file(s) processed`, "Done");
  } else {
    const processing = total - completed - failed;
    setStatus(`Processing ${processing} of ${total} file(s)...`);
    setResultMeta(`${completed}/${total} completed`, "Running");
  }

  setProgress(calculateOverallProgress());
};

const pollJob = async (jobIndex, jobId, jobMode) => {
  const onUpdate = (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;

    activeJobs[jobIndex].progress = job.status === "completed" || job.status === "failed" ? 100 : progress;
    activeJobs[jobIndex].status = job.status;
    activeJobs[jobIndex].result = job;

    if (job.status === "completed") {
      updateFilePillStatus(jobIndex, "Done", jobId);
    } else if (job.status === "failed") {
      updateFilePillStatus(jobIndex, "Failed");
    } else {
      updateFilePillStatus(jobIndex, `${progress}%`);
    }

    updateOverallStatus();

    if (job.status === "completed" || job.status === "failed") {
      (async () => {
        if (activeJobs.length === 1) {
          const lastCompleted = activeJobs.find((j) => j.status === "completed");
          if (lastCompleted) {
            setActionState(jobMode, lastCompleted.jobId, true);
            try {
              const resultResponse = await fetch(`/api/jobs/${lastCompleted.jobId}/result`);
              const result = await resultResponse.json();
              resultText.value = result.final_text || "No text extracted.";
            } catch {
              resultText.value = "Could not fetch result.";
            }
          }
        } else {
          setActionState(jobMode, null, false);
          const completedJobs = activeJobs.filter((j) => j.status === "completed" && j.jobId);
          const allTexts = [];
          for (const completedJob of completedJobs) {
            try {
              const resultResponse = await fetch(`/api/jobs/${completedJob.jobId}/result`);
              const result = await resultResponse.json();
              if (result.final_text) {
                allTexts.push(`--- ${completedJob.filename} ---\n${result.final_text}`);
              }
            } catch {
              // Skip failed fetches
            }
          }
          resultText.value = allTexts.length > 0
            ? allTexts.join("\n\n")
            : "No text extracted from files.";
        }
      })();
    }
  };

  // Try SSE first, fallback to polling
  if (typeof EventSource !== "undefined") {
    const es = new EventSource(`/api/jobs/${jobId}/stream`);
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onUpdate(data);
      if (data.status === "completed" || data.status === "failed") {
        es.close();
      }
    };
    es.onerror = () => {
      es.close();
      // Fallback to polling
      const poll = async () => {
        const response = await fetch(`/api/jobs/${jobId}`);
        const job = await response.json();
        onUpdate(job);
        if (job.status !== "completed" && job.status !== "failed") {
          setTimeout(poll, 2000);
        }
      };
      poll();
    };
  } else {
    const poll = async () => {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      onUpdate(job);
      if (job.status !== "completed" && job.status !== "failed") {
        setTimeout(poll, 2000);
      }
    };
    poll();
  }
};

const submitFiles = async () => {
  if (!selectedFiles.length) {
    setStatus("Please choose file(s) first.");
    return;
  }

  lastJobMode = getSelectedMode();
  activeJobs = [];
  setProgress(0);
  setStatus(`Uploading ${selectedFiles.length} file(s)...`);
  setResultMeta("Uploading...", "Starting");
  setActionState(lastJobMode, null, false);

  for (let i = 0; i < selectedFiles.length; i++) {
    const file = selectedFiles[i];
    const formData = new FormData();
    formData.append("file", file);
    formData.set("mode", lastJobMode);
    formData.set("ocr_engine", "tesseract");
    formData.set("job_type", "ocr");
    formData.set("lang", uploadForm?.querySelector("select[name='lang']")?.value || "eng");

    updateFilePillStatus(i, "Uploading...");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        activeJobs.push({
          jobId: null,
          fileIndex: i,
          filename: file.name,
          status: "failed",
          progress: 100,
          error: payload.error || "Upload failed",
        });
        updateFilePillStatus(i, "Failed");
      } else {
        activeJobs.push({
          jobId: payload.job_id,
          fileIndex: i,
          filename: file.name,
          status: "queued",
          progress: 0,
        });
        updateFilePillStatus(i, "Queued");
        pollJob(i, payload.job_id, lastJobMode);
      }
    } catch (err) {
      activeJobs.push({
        jobId: null,
        fileIndex: i,
        filename: file.name,
        status: "failed",
        progress: 100,
        error: err.message,
      });
      updateFilePillStatus(i, "Failed");
    }
  }

  updateOverallStatus();
};

// ============================================
// Image Converter Tab Functions
// ============================================
const setImageStatus = (message) => {
  if (imageStatusMessage) imageStatusMessage.textContent = message;
};

const setImageResultMeta = (name, status) => {
  if (imageResultFilename) imageResultFilename.textContent = name;
  if (imageResultStatus) imageResultStatus.textContent = status;
};

const setImageProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (imageProgressFill) imageProgressFill.style.width = `${safeValue}%`;
  if (imageProgressPercent) imageProgressPercent.textContent = `${Math.round(safeValue)}%`;
};

const renderImageFiles = (files) => {
  if (!imageFileList) return;
  imageFileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    imageFileList.appendChild(pill);
  });
};

const updateImageFilePillStatus = (index, status, jobId = null) => {
  const pill = imageFileList?.querySelector(`[data-file-index="${index}"]`);
  if (pill) {
    const statusSpan = pill.querySelector(".file-status");
    if (statusSpan) {
      if (status === "Done" && jobId) {
        statusSpan.innerHTML = `<a href="/api/jobs/${jobId}/download/image" class="file-download-link image">Download</a>`;
      } else {
        statusSpan.textContent = status;
      }
    }
  }
};

const handleImageFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedImageFiles = [...files];
  renderImageFiles(files);
};

const calculateImageOverallProgress = () => {
  if (activeImageJobs.length === 0) return 0;
  const totalProgress = activeImageJobs.reduce((sum, job) => sum + (job.progress || 0), 0);
  return totalProgress / activeImageJobs.length;
};

const updateImageOverallStatus = () => {
  const completed = activeImageJobs.filter((j) => j.status === "completed").length;
  const failed = activeImageJobs.filter((j) => j.status === "failed").length;
  const total = activeImageJobs.length;

  if (completed + failed === total) {
    if (failed > 0) {
      setImageStatus(`Completed: ${completed}/${total} (${failed} failed)`);
    } else {
      setImageStatus(`All ${total} image(s) converted.`);
    }
    setImageResultMeta(`${completed} image(s) processed`, "Done");
  } else {
    const processing = total - completed - failed;
    setImageStatus(`Converting ${processing} of ${total} image(s)...`);
    setImageResultMeta(`${completed}/${total} completed`, "Running");
  }

  setImageProgress(calculateImageOverallProgress());
};

const pollImageJob = (jobIndex, jobId) => {
  streamJob(jobId, (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;
    activeImageJobs[jobIndex].progress = job.status === "completed" || job.status === "failed" ? 100 : progress;
    activeImageJobs[jobIndex].status = job.status;
    activeImageJobs[jobIndex].result = job;
    if (job.status === "completed") {
      updateImageFilePillStatus(jobIndex, "Done", jobId);
    } else if (job.status === "failed") {
      updateImageFilePillStatus(jobIndex, "Failed");
    } else {
      updateImageFilePillStatus(jobIndex, `${progress}%`);
    }
    updateImageOverallStatus();
  });
};

const submitImageFiles = async () => {
  if (!selectedImageFiles.length) {
    setImageStatus("Please choose image(s) first.");
    return;
  }

  activeImageJobs = [];
  setImageProgress(0);
  setImageStatus(`Uploading ${selectedImageFiles.length} image(s)...`);
  setImageResultMeta("Uploading...", "Starting");

  for (let i = 0; i < selectedImageFiles.length; i++) {
    const file = selectedImageFiles[i];
    const formData = new FormData(imageUploadForm);
    formData.set("file", file);
    formData.set("job_type", "image");

    // Convert brightness/contrast from 0-200 range to 0.0-2.0
    const brightness = parseFloat(formData.get("brightness") || "100") / 100;
    const contrast = parseFloat(formData.get("contrast") || "100") / 100;
    formData.set("brightness", brightness.toString());
    formData.set("contrast", contrast.toString());

    // Convert grayscale checkbox to string
    const grayscale = imageUploadForm?.querySelector("input[name='grayscale']")?.checked;
    formData.set("grayscale", grayscale ? "true" : "false");

    updateImageFilePillStatus(i, "Uploading...");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        activeImageJobs.push({
          jobId: null,
          fileIndex: i,
          filename: file.name,
          status: "failed",
          progress: 100,
          error: payload.error || "Upload failed",
        });
        updateImageFilePillStatus(i, "Failed");
      } else {
        activeImageJobs.push({
          jobId: payload.job_id,
          fileIndex: i,
          filename: file.name,
          status: "queued",
          progress: 0,
        });
        updateImageFilePillStatus(i, "Queued");
        pollImageJob(i, payload.job_id);
      }
    } catch (err) {
      activeImageJobs.push({
        jobId: null,
        fileIndex: i,
        filename: file.name,
        status: "failed",
        progress: 100,
        error: err.message,
      });
      updateImageFilePillStatus(i, "Failed");
    }
  }

  updateImageOverallStatus();
};

// ============================================
// OCR Tab Event Listeners
// ============================================
dropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("is-dragging");
});

dropzone?.addEventListener("dragleave", () => {
  dropzone.classList.remove("is-dragging");
});

dropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("is-dragging");
  handleFiles(event.dataTransfer.files);
});

fileInput?.addEventListener("change", (event) => {
  handleFiles(event.target.files);
  event.target.value = "";
});

uploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitFiles();
});

copyText?.addEventListener("click", async () => {
  if (!resultText?.value) return;
  await navigator.clipboard.writeText(resultText.value);
  setStatus("Copied result text.");
});

uploadForm?.querySelectorAll("input[name='mode']").forEach((radio) => {
  radio.addEventListener("change", () => {
    setActionState(getSelectedMode(), null, false);
    setProgress(0);
  });
});

// ============================================
// Image Converter Tab Event Listeners
// ============================================
imageDropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  imageDropzone.classList.add("is-dragging");
});

imageDropzone?.addEventListener("dragleave", () => {
  imageDropzone.classList.remove("is-dragging");
});

imageDropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  imageDropzone.classList.remove("is-dragging");
  handleImageFiles(event.dataTransfer.files);
});

imageFileInput?.addEventListener("change", (event) => {
  handleImageFiles(event.target.files);
  event.target.value = "";
});

imageUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitImageFiles();
});

// Slider value displays
qualitySlider?.addEventListener("input", (e) => {
  if (qualityValue) qualityValue.textContent = e.target.value;
});

brightnessSlider?.addEventListener("input", (e) => {
  if (brightnessValue) brightnessValue.textContent = e.target.value;
});

contrastSlider?.addEventListener("input", (e) => {
  if (contrastValue) contrastValue.textContent = e.target.value;
});

// ============================================
// Document Converter Tab Functions
// ============================================
const setDocumentStatus = (message) => {
  if (documentStatusMessage) documentStatusMessage.textContent = message;
};

const setDocumentResultMeta = (name, status) => {
  if (documentResultFilename) documentResultFilename.textContent = name;
  if (documentResultStatus) documentResultStatus.textContent = status;
};

const setDocumentProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (documentProgressFill) documentProgressFill.style.width = `${safeValue}%`;
  if (documentProgressPercent) documentProgressPercent.textContent = `${Math.round(safeValue)}%`;
};

const renderDocumentFiles = (files) => {
  if (!documentFileList) return;
  documentFileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    documentFileList.appendChild(pill);
  });
};

const updateDocumentFilePillStatus = (index, status, jobId = null) => {
  const pill = documentFileList?.querySelector(`[data-file-index="${index}"]`);
  if (pill) {
    const statusSpan = pill.querySelector(".file-status");
    if (statusSpan) {
      if (status === "Done" && jobId) {
        statusSpan.innerHTML = `<a href="/api/jobs/${jobId}/download/document" class="file-download-link document">Download</a>`;
      } else {
        statusSpan.textContent = status;
      }
    }
  }
};

const handleDocumentFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedDocumentFiles = [...files];
  renderDocumentFiles(files);
};

const calculateDocumentOverallProgress = () => {
  if (activeDocumentJobs.length === 0) return 0;
  const totalProgress = activeDocumentJobs.reduce((sum, job) => sum + (job.progress || 0), 0);
  return totalProgress / activeDocumentJobs.length;
};

const updateDocumentOverallStatus = () => {
  const completed = activeDocumentJobs.filter((j) => j.status === "completed").length;
  const failed = activeDocumentJobs.filter((j) => j.status === "failed").length;
  const total = activeDocumentJobs.length;

  if (completed + failed === total) {
    if (failed > 0) {
      setDocumentStatus(`Completed: ${completed}/${total} (${failed} failed)`);
    } else {
      setDocumentStatus(`All ${total} document(s) converted.`);
    }
    setDocumentResultMeta(`${completed} document(s) processed`, "Done");
  } else {
    const processing = total - completed - failed;
    setDocumentStatus(`Converting ${processing} of ${total} document(s)...`);
    setDocumentResultMeta(`${completed}/${total} completed`, "Running");
  }

  setDocumentProgress(calculateDocumentOverallProgress());
};

const pollDocumentJob = (jobIndex, jobId) => {
  streamJob(jobId, (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;
    activeDocumentJobs[jobIndex].progress = job.status === "completed" || job.status === "failed" ? 100 : progress;
    activeDocumentJobs[jobIndex].status = job.status;
    activeDocumentJobs[jobIndex].result = job;
    if (job.status === "completed") {
      updateDocumentFilePillStatus(jobIndex, "Done", jobId);
    } else if (job.status === "failed") {
      updateDocumentFilePillStatus(jobIndex, "Failed");
    } else {
      updateDocumentFilePillStatus(jobIndex, `${progress}%`);
    }
    updateDocumentOverallStatus();
  });
};

const submitDocumentFiles = async () => {
  if (!selectedDocumentFiles.length) {
    setDocumentStatus("Please choose document(s) first.");
    return;
  }

  activeDocumentJobs = [];
  setDocumentProgress(0);
  setDocumentStatus(`Uploading ${selectedDocumentFiles.length} document(s)...`);
  setDocumentResultMeta("Uploading...", "Starting");

  for (let i = 0; i < selectedDocumentFiles.length; i++) {
    const file = selectedDocumentFiles[i];
    const formData = new FormData(documentUploadForm);
    formData.set("file", file);
    formData.set("job_type", "document");

    updateDocumentFilePillStatus(i, "Uploading...");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        activeDocumentJobs.push({
          jobId: null,
          fileIndex: i,
          filename: file.name,
          status: "failed",
          progress: 100,
          error: payload.error || "Upload failed",
        });
        updateDocumentFilePillStatus(i, "Failed");
      } else {
        activeDocumentJobs.push({
          jobId: payload.job_id,
          fileIndex: i,
          filename: file.name,
          status: "queued",
          progress: 0,
        });
        updateDocumentFilePillStatus(i, "Queued");
        pollDocumentJob(i, payload.job_id);
      }
    } catch (err) {
      activeDocumentJobs.push({
        jobId: null,
        fileIndex: i,
        filename: file.name,
        status: "failed",
        progress: 100,
        error: err.message,
      });
      updateDocumentFilePillStatus(i, "Failed");
    }
  }

  updateDocumentOverallStatus();
};

// ============================================
// Audio Converter Tab Functions
// ============================================
const setAudioStatus = (message) => {
  if (audioStatusMessage) audioStatusMessage.textContent = message;
};

const setAudioResultMeta = (name, status) => {
  if (audioResultFilename) audioResultFilename.textContent = name;
  if (audioResultStatus) audioResultStatus.textContent = status;
};

const setAudioProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (audioProgressFill) audioProgressFill.style.width = `${safeValue}%`;
  if (audioProgressPercent) audioProgressPercent.textContent = `${Math.round(safeValue)}%`;
};

const renderAudioFiles = (files) => {
  if (!audioFileList) return;
  audioFileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    audioFileList.appendChild(pill);
  });
};

const updateAudioFilePillStatus = (index, status, jobId = null) => {
  const pill = audioFileList?.querySelector(`[data-file-index="${index}"]`);
  if (pill) {
    const statusSpan = pill.querySelector(".file-status");
    if (statusSpan) {
      if (status === "Done" && jobId) {
        statusSpan.innerHTML = `<a href="/api/jobs/${jobId}/download/audio" class="file-download-link audio">Download</a>`;
      } else {
        statusSpan.textContent = status;
      }
    }
  }
};

const handleAudioFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedAudioFiles = [...files];
  renderAudioFiles(files);
};

const calculateAudioOverallProgress = () => {
  if (activeAudioJobs.length === 0) return 0;
  const totalProgress = activeAudioJobs.reduce((sum, job) => sum + (job.progress || 0), 0);
  return totalProgress / activeAudioJobs.length;
};

const updateAudioOverallStatus = () => {
  const completed = activeAudioJobs.filter((j) => j.status === "completed").length;
  const failed = activeAudioJobs.filter((j) => j.status === "failed").length;
  const total = activeAudioJobs.length;

  if (completed + failed === total) {
    if (failed > 0) {
      setAudioStatus(`Completed: ${completed}/${total} (${failed} failed)`);
    } else {
      setAudioStatus(`All ${total} audio file(s) converted.`);
    }
    setAudioResultMeta(`${completed} audio file(s) processed`, "Done");
  } else {
    const processing = total - completed - failed;
    setAudioStatus(`Converting ${processing} of ${total} audio file(s)...`);
    setAudioResultMeta(`${completed}/${total} completed`, "Running");
  }

  setAudioProgress(calculateAudioOverallProgress());
};

const pollAudioJob = (jobIndex, jobId) => {
  streamJob(jobId, (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;
    activeAudioJobs[jobIndex].progress = job.status === "completed" || job.status === "failed" ? 100 : progress;
    activeAudioJobs[jobIndex].status = job.status;
    activeAudioJobs[jobIndex].result = job;
    if (job.status === "completed") {
      updateAudioFilePillStatus(jobIndex, "Done", jobId);
    } else if (job.status === "failed") {
      updateAudioFilePillStatus(jobIndex, "Failed");
    } else {
      updateAudioFilePillStatus(jobIndex, `${progress}%`);
    }
    updateAudioOverallStatus();
  });
};

const submitAudioFiles = async () => {
  if (!selectedAudioFiles.length) {
    setAudioStatus("Please choose audio/video file(s) first.");
    return;
  }

  activeAudioJobs = [];
  setAudioProgress(0);
  setAudioStatus(`Uploading ${selectedAudioFiles.length} file(s)...`);
  setAudioResultMeta("Uploading...", "Starting");

  for (let i = 0; i < selectedAudioFiles.length; i++) {
    const file = selectedAudioFiles[i];
    const formData = new FormData(audioUploadForm);
    formData.set("file", file);
    formData.set("job_type", "audio");

    updateAudioFilePillStatus(i, "Uploading...");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        activeAudioJobs.push({
          jobId: null,
          fileIndex: i,
          filename: file.name,
          status: "failed",
          progress: 100,
          error: payload.error || "Upload failed",
        });
        updateAudioFilePillStatus(i, "Failed");
      } else {
        activeAudioJobs.push({
          jobId: payload.job_id,
          fileIndex: i,
          filename: file.name,
          status: "queued",
          progress: 0,
        });
        updateAudioFilePillStatus(i, "Queued");
        pollAudioJob(i, payload.job_id);
      }
    } catch (err) {
      activeAudioJobs.push({
        jobId: null,
        fileIndex: i,
        filename: file.name,
        status: "failed",
        progress: 100,
        error: err.message,
      });
      updateAudioFilePillStatus(i, "Failed");
    }
  }

  updateAudioOverallStatus();
};

// ============================================
// Video Converter Tab Functions
// ============================================
const setVideoStatus = (message) => {
  if (videoStatusMessage) videoStatusMessage.textContent = message;
};

const setVideoResultMeta = (name, status) => {
  if (videoResultFilename) videoResultFilename.textContent = name;
  if (videoResultStatus) videoResultStatus.textContent = status;
};

const setVideoProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (videoProgressFill) videoProgressFill.style.width = `${safeValue}%`;
  if (videoProgressPercent) videoProgressPercent.textContent = `${Math.round(safeValue)}%`;
};

const renderVideoFiles = (files) => {
  if (!videoFileList) return;
  videoFileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    videoFileList.appendChild(pill);
  });
};

const updateVideoFilePillStatus = (index, status, jobId = null) => {
  const pill = videoFileList?.querySelector(`[data-file-index="${index}"]`);
  if (pill) {
    const statusSpan = pill.querySelector(".file-status");
    if (statusSpan) {
      if (status === "Done" && jobId) {
        statusSpan.innerHTML = `<a href="/api/jobs/${jobId}/download/video" class="file-download-link video">Download</a>`;
      } else {
        statusSpan.textContent = status;
      }
    }
  }
};

const handleVideoFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedVideoFiles = [...files];
  renderVideoFiles(files);
};

const calculateVideoOverallProgress = () => {
  if (activeVideoJobs.length === 0) return 0;
  const totalProgress = activeVideoJobs.reduce((sum, job) => sum + (job.progress || 0), 0);
  return totalProgress / activeVideoJobs.length;
};

const updateVideoOverallStatus = () => {
  const completed = activeVideoJobs.filter((j) => j.status === "completed").length;
  const failed = activeVideoJobs.filter((j) => j.status === "failed").length;
  const total = activeVideoJobs.length;

  if (completed + failed === total) {
    if (failed > 0) {
      setVideoStatus(`Completed: ${completed}/${total} (${failed} failed)`);
    } else {
      setVideoStatus(`All ${total} video(s) converted.`);
    }
    setVideoResultMeta(`${completed} video(s) processed`, "Done");
  } else {
    const processing = total - completed - failed;
    setVideoStatus(`Converting ${processing} of ${total} video(s)...`);
    setVideoResultMeta(`${completed}/${total} completed`, "Running");
  }

  setVideoProgress(calculateVideoOverallProgress());
};

const pollVideoJob = (jobIndex, jobId) => {
  streamJob(jobId, (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;
    activeVideoJobs[jobIndex].progress = job.status === "completed" || job.status === "failed" ? 100 : progress;
    activeVideoJobs[jobIndex].status = job.status;
    activeVideoJobs[jobIndex].result = job;
    if (job.status === "completed") {
      updateVideoFilePillStatus(jobIndex, "Done", jobId);
    } else if (job.status === "failed") {
      updateVideoFilePillStatus(jobIndex, "Failed");
    } else {
      updateVideoFilePillStatus(jobIndex, `${progress}%`);
    }
    updateVideoOverallStatus();
  });
};

const submitVideoFiles = async () => {
  if (!selectedVideoFiles.length) {
    setVideoStatus("Please choose video file(s) first.");
    return;
  }

  activeVideoJobs = [];
  setVideoProgress(0);
  setVideoStatus(`Uploading ${selectedVideoFiles.length} video(s)...`);
  setVideoResultMeta("Uploading...", "Starting");

  for (let i = 0; i < selectedVideoFiles.length; i++) {
    const file = selectedVideoFiles[i];
    const formData = new FormData(videoUploadForm);
    formData.set("file", file);
    formData.set("job_type", "video");

    updateVideoFilePillStatus(i, "Uploading...");

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        activeVideoJobs.push({
          jobId: null,
          fileIndex: i,
          filename: file.name,
          status: "failed",
          progress: 100,
          error: payload.error || "Upload failed",
        });
        updateVideoFilePillStatus(i, "Failed");
      } else {
        activeVideoJobs.push({
          jobId: payload.job_id,
          fileIndex: i,
          filename: file.name,
          status: "queued",
          progress: 0,
        });
        updateVideoFilePillStatus(i, "Queued");
        pollVideoJob(i, payload.job_id);
      }
    } catch (err) {
      activeVideoJobs.push({
        jobId: null,
        fileIndex: i,
        filename: file.name,
        status: "failed",
        progress: 100,
        error: err.message,
      });
      updateVideoFilePillStatus(i, "Failed");
    }
  }

  updateVideoOverallStatus();
};

// ============================================
// Document Converter Tab Event Listeners
// ============================================
documentDropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  documentDropzone.classList.add("is-dragging");
});

documentDropzone?.addEventListener("dragleave", () => {
  documentDropzone.classList.remove("is-dragging");
});

documentDropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  documentDropzone.classList.remove("is-dragging");
  handleDocumentFiles(event.dataTransfer.files);
});

documentFileInput?.addEventListener("change", (event) => {
  handleDocumentFiles(event.target.files);
  event.target.value = "";
});

documentUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitDocumentFiles();
});

// ============================================
// Audio Converter Tab Event Listeners
// ============================================
audioDropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  audioDropzone.classList.add("is-dragging");
});

audioDropzone?.addEventListener("dragleave", () => {
  audioDropzone.classList.remove("is-dragging");
});

audioDropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  audioDropzone.classList.remove("is-dragging");
  handleAudioFiles(event.dataTransfer.files);
});

audioFileInput?.addEventListener("change", (event) => {
  handleAudioFiles(event.target.files);
  event.target.value = "";
});

audioUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAudioFiles();
});

// ============================================
// Video Converter Tab Event Listeners
// ============================================
videoDropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  videoDropzone.classList.add("is-dragging");
});

videoDropzone?.addEventListener("dragleave", () => {
  videoDropzone.classList.remove("is-dragging");
});

videoDropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  videoDropzone.classList.remove("is-dragging");
  handleVideoFiles(event.dataTransfer.files);
});

videoFileInput?.addEventListener("change", (event) => {
  handleVideoFiles(event.target.files);
  event.target.value = "";
});

videoUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitVideoFiles();
});

// ============================================
// PDF Tools Tab Elements & State
// ============================================
const pdfDropzone = document.getElementById("pdfDropzone");
const pdfFileInput = document.getElementById("pdfFileInput");
const pdfFileList = document.getElementById("pdfFileList");
const pdfUploadForm = document.getElementById("pdfUploadForm");
const pdfStatusMessage = document.getElementById("pdfStatusMessage");
const pdfResultFilename = document.getElementById("pdfResultFilename");
const pdfResultStatus = document.getElementById("pdfResultStatus");
const pdfProgressFill = document.getElementById("pdfProgressFill");
const pdfProgressPercent = document.getElementById("pdfProgressPercent");
const pdfPreviewArea = document.getElementById("pdfPreviewArea");
const pdfModeInput = document.getElementById("pdfModeInput");
const pdfDropzoneHint = document.getElementById("pdfDropzoneHint");
const pdfToolGrid = document.getElementById("pdfToolGrid");

let selectedPdfFiles = [];
let currentPdfTool = "merge";

// Tool configuration: hints, accept types, multi-file, options panel
const pdfToolConfig = {
  merge:        { hint: "Upload 2 or more PDF files to merge (Max 25MB each)", accept: ".pdf", multi: true, opts: null },
  split:        { hint: "Upload a PDF file to split into individual pages", accept: ".pdf", multi: false, opts: null },
  compress:     { hint: "Upload a PDF file to compress and reduce file size", accept: ".pdf", multi: false, opts: null },
  rotate:       { hint: "Upload a PDF file to rotate all pages", accept: ".pdf", multi: false, opts: "opts-rotate" },
  extract:      { hint: "Upload a PDF and specify page numbers to extract", accept: ".pdf", multi: false, opts: "opts-pages" },
  delete:       { hint: "Upload a PDF and specify page numbers to remove", accept: ".pdf", multi: false, opts: "opts-pages" },
  watermark:    { hint: "Upload a PDF to add a text watermark overlay", accept: ".pdf", multi: false, opts: "opts-watermark" },
  page_numbers: { hint: "Upload a PDF to add page numbers", accept: ".pdf", multi: false, opts: "opts-page-numbers" },
  protect:      { hint: "Upload a PDF to encrypt with a password", accept: ".pdf", multi: false, opts: "opts-password" },
  unlock:       { hint: "Upload a password-protected PDF to decrypt", accept: ".pdf", multi: false, opts: "opts-password" },
  to_images:    { hint: "Upload a PDF to convert each page to an image", accept: ".pdf", multi: false, opts: "opts-to-images" },
  from_images:  { hint: "Upload images to combine into a single PDF (PNG, JPG, etc.)", accept: ".png,.jpg,.jpeg,.gif,.bmp,.tif,.tiff,.webp", multi: true, opts: null },
  metadata:     { hint: "Upload a PDF to edit its metadata (title, author, etc.)", accept: ".pdf", multi: false, opts: "opts-metadata" },
};

const selectPdfTool = (tool) => {
  currentPdfTool = tool;
  const config = pdfToolConfig[tool];
  if (!config) return;

  // Update active button
  pdfToolGrid?.querySelectorAll(".pdf-tool-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tool === tool);
  });

  // Update hidden mode input
  if (pdfModeInput) pdfModeInput.value = tool;

  // Update dropzone hint and accept type
  if (pdfDropzoneHint) pdfDropzoneHint.textContent = config.hint;
  if (pdfFileInput) {
    pdfFileInput.accept = config.accept;
    pdfFileInput.multiple = config.multi;
  }

  // Show/hide option panels
  document.querySelectorAll(".pdf-tool-options").forEach((el) => {
    el.style.display = "none";
  });
  if (config.opts) {
    const optsEl = document.getElementById(config.opts);
    if (optsEl) optsEl.style.display = "";
  }

  // Update password label
  if (tool === "protect") {
    const label = document.getElementById("passwordLabel");
    if (label) label.textContent = "Set Password";
  } else if (tool === "unlock") {
    const label = document.getElementById("passwordLabel");
    if (label) label.textContent = "Enter Password";
  }

  // Clear selected files on tool change
  selectedPdfFiles = [];
  if (pdfFileList) pdfFileList.innerHTML = "";
  setPdfStatus("Ready to process.");
  setPdfResultMeta("Awaiting upload", "Idle");
  setPdfProgress(0);
  if (pdfPreviewArea) pdfPreviewArea.innerHTML = "<p>Processed PDF will be available for download.</p>";
};

// Attach tool selector event listeners
pdfToolGrid?.querySelectorAll(".pdf-tool-btn").forEach((btn) => {
  btn.addEventListener("click", () => selectPdfTool(btn.dataset.tool));
});

const setPdfStatus = (message) => {
  if (pdfStatusMessage) pdfStatusMessage.textContent = message;
};

const setPdfResultMeta = (name, status) => {
  if (pdfResultFilename) pdfResultFilename.textContent = name;
  if (pdfResultStatus) pdfResultStatus.textContent = status;
};

const setPdfProgress = (value) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  if (pdfProgressFill) pdfProgressFill.style.width = `${safeValue}%`;
  if (pdfProgressPercent) pdfProgressPercent.textContent = `${Math.round(safeValue)}%`;
};

const renderPdfFiles = (files) => {
  if (!pdfFileList) return;
  pdfFileList.innerHTML = "";
  [...files].forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    pill.dataset.fileIndex = index;
    pill.innerHTML = `<span>${file.name}</span><span class="file-status">${Math.ceil(
      file.size / 1024
    )} KB</span>`;
    pdfFileList.appendChild(pill);
  });
};

const handlePdfFiles = (files) => {
  if (!files || files.length === 0) return;
  selectedPdfFiles = [...files];
  renderPdfFiles(files);
};

const pollPdfJob = (jobId) => {
  streamJob(jobId, (job) => {
    const progress =
      typeof job.progress === "number" ? Math.min(100, Math.max(0, job.progress)) : 0;
    setPdfProgress(progress);
    if (job.status === "completed") {
      setPdfStatus("Processing complete!");
      setPdfResultMeta("Done", "Completed");
      setPdfProgress(100);
      if (pdfPreviewArea) {
        pdfPreviewArea.innerHTML = `<a href="/api/jobs/${jobId}/download/pdf" class="primary btn" style="display:inline-block;margin-top:10px;">Download Result</a>`;
      }
    } else if (job.status === "failed") {
      setPdfStatus(`Failed: ${job.error || "unknown error"}`);
      setPdfResultMeta("Failed", "Error");
      setPdfProgress(100);
    } else {
      setPdfStatus(`Processing... ${progress}%`);
    }
  });
};

const submitPdfFiles = async () => {
  if (!selectedPdfFiles.length) {
    setPdfStatus("Please choose file(s) first.");
    return;
  }

  const pdfMode = currentPdfTool;

  if (pdfMode === "merge" && selectedPdfFiles.length < 2) {
    setPdfStatus("Please select at least 2 PDFs to merge.");
    return;
  }

  setPdfProgress(0);
  setPdfStatus("Uploading...");
  setPdfResultMeta("Uploading...", "Starting");
  if (pdfPreviewArea) pdfPreviewArea.innerHTML = "<p>Processing...</p>";

  const formData = new FormData();
  for (const file of selectedPdfFiles) {
    formData.append("files", file);
  }
  formData.set("pdf_mode", pdfMode);

  // Append tool-specific options from the form
  if (pdfMode === "rotate") {
    const deg = pdfUploadForm?.querySelector("input[name='rotate_degrees']:checked")?.value || "90";
    formData.set("rotate_degrees", deg);
  } else if (pdfMode === "extract" || pdfMode === "delete") {
    formData.set("page_range", pdfUploadForm?.querySelector("input[name='page_range']")?.value || "1");
  } else if (pdfMode === "watermark") {
    formData.set("watermark_text", pdfUploadForm?.querySelector("input[name='watermark_text']")?.value || "WATERMARK");
    formData.set("watermark_opacity", pdfUploadForm?.querySelector("input[name='watermark_opacity']")?.value || "0.3");
    formData.set("watermark_font_size", pdfUploadForm?.querySelector("input[name='watermark_font_size']")?.value || "60");
    formData.set("watermark_rotation", pdfUploadForm?.querySelector("input[name='watermark_rotation']")?.value || "45");
  } else if (pdfMode === "protect" || pdfMode === "unlock") {
    formData.set("password", pdfUploadForm?.querySelector("input[name='password']")?.value || "");
  } else if (pdfMode === "to_images") {
    formData.set("image_format", pdfUploadForm?.querySelector("select[name='image_format']")?.value || "png");
    formData.set("dpi", pdfUploadForm?.querySelector("select[name='dpi']")?.value || "200");
  } else if (pdfMode === "page_numbers") {
    formData.set("number_position", pdfUploadForm?.querySelector("select[name='number_position']")?.value || "bottom-center");
    formData.set("start_number", pdfUploadForm?.querySelector("input[name='start_number']")?.value || "1");
  } else if (pdfMode === "metadata") {
    formData.set("meta_title", pdfUploadForm?.querySelector("input[name='meta_title']")?.value || "");
    formData.set("meta_author", pdfUploadForm?.querySelector("input[name='meta_author']")?.value || "");
    formData.set("meta_subject", pdfUploadForm?.querySelector("input[name='meta_subject']")?.value || "");
    formData.set("meta_keywords", pdfUploadForm?.querySelector("input[name='meta_keywords']")?.value || "");
  }

  try {
    const response = await fetch("/api/pdf-jobs", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
      body: formData,
    });
    const payload = await response.json();

    if (!response.ok) {
      setPdfStatus(`Error: ${payload.error || "Upload failed"}`);
      setPdfResultMeta("Failed", "Error");
      return;
    }

    setPdfStatus("Processing...");
    setPdfResultMeta("Processing...", "Running");
    pollPdfJob(payload.job_id);
  } catch (err) {
    setPdfStatus(`Error: ${err.message}`);
    setPdfResultMeta("Failed", "Error");
  }
};

pdfDropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  pdfDropzone.classList.add("is-dragging");
});

pdfDropzone?.addEventListener("dragleave", () => {
  pdfDropzone.classList.remove("is-dragging");
});

pdfDropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  pdfDropzone.classList.remove("is-dragging");
  handlePdfFiles(event.dataTransfer.files);
});

pdfFileInput?.addEventListener("change", (event) => {
  handlePdfFiles(event.target.files);
  event.target.value = "";
});

pdfUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitPdfFiles();
});

// ============================================
// Dark Mode Toggle
// ============================================
const themeToggle = document.getElementById("themeToggle");

themeToggle?.addEventListener("click", () => {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const next = isDark ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
});

// ============================================
// Mobile Menu Toggle
// ============================================
const mobileMenuToggle = document.querySelector(".mobile-menu-toggle");
const mainNav = document.querySelector(".main-nav");

mobileMenuToggle?.addEventListener("click", () => {
  mobileMenuToggle.classList.toggle("active");
  mainNav?.classList.toggle("active");
});

// Close mobile menu when clicking on a link
mainNav?.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => {
    mobileMenuToggle?.classList.remove("active");
    mainNav?.classList.remove("active");
  });
});

// Close mobile menu when clicking outside
document.addEventListener("click", (event) => {
  if (
    mainNav?.classList.contains("active") &&
    !mainNav.contains(event.target) &&
    !mobileMenuToggle?.contains(event.target)
  ) {
    mobileMenuToggle?.classList.remove("active");
    mainNav?.classList.remove("active");
  }
});

// ============================================
// Initialization
// ============================================
setActionState(getSelectedMode(), null, false);
setProgress(0);
setImageProgress(0);
setDocumentProgress(0);
setAudioProgress(0);
setVideoProgress(0);
setPdfProgress(0);
