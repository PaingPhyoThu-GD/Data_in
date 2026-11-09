/**
 * Gemini Myanmar-English OCR, Telegram Chat Parser, and Database to JSON
 * Single Page Application Logic
 */

// Global Navigation State
let activeService = "ocr"; // "ocr" | "telegram" | "database"

// --- OCR State ---
let selectedFiles = [];
let defaultPrompt = "";
let latestOcrResponse = null;

// --- Telegram State ---
let selectedTgFile = null;
let selectedTgPhotos = [];
let activeTgSessionId = null;
let telegramChatData = null;

// --- Database State ---
let selectedDbFile = null;
let databaseData = null;
let activeTableName = null;
let dbSearchQuery = "";
let dbCurrentPage = 1;
let dbPageSize = 50;

// --- YouTube State ---
let selectedYtFile = null;
let youtubeChannelData = null;
let ytSearchQuery = "";
let ytSortBy = "default";
let ytViewMode = "grid";
let ytCurrentPage = 1;
let ytPageSize = 24;

// --- DOM Elements: Navigation ---
const tabOCR = document.getElementById("tabOCR");
const tabTelegram = document.getElementById("tabTelegram");
const tabDatabase = document.getElementById("tabDatabase");
const tabYouTube = document.getElementById("tabYouTube");
const viewOCR = document.getElementById("viewOCR");
const viewTelegram = document.getElementById("viewTelegram");
const viewDatabase = document.getElementById("viewDatabase");
const viewYouTube = document.getElementById("viewYouTube");
const brandSubtitle = document.getElementById("brandSubtitle");
const ocrStatusBadge = document.getElementById("ocrStatusBadge");
const btnToggleHistory = document.getElementById("btnToggleHistory");
const historyBtnLabel = document.getElementById("historyBtnLabel");

// --- DOM Elements: OCR ---
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const dropZone = document.getElementById("dropZone");
const btnPickFiles = document.getElementById("btnPickFiles");
const btnPickFolder = document.getElementById("btnPickFolder");
const selectedFilesSection = document.getElementById("selectedFilesSection");
const filesBadgeContainer = document.getElementById("filesBadgeContainer");
const selectedCountBadge = document.getElementById("selectedCountBadge");
const btnClearFiles = document.getElementById("btnClearFiles");

const batchSizeInput = document.getElementById("batchSizeInput");
const batchSizeVal = document.getElementById("batchSizeVal");
const promptInput = document.getElementById("promptInput");
const btnResetPrompt = document.getElementById("btnResetPrompt");
const mockModeCheck = document.getElementById("mockModeCheck");

const btnRunOCR = document.getElementById("btnRunOCR");
const loadingSection = document.getElementById("loadingSection");
const resultsSection = document.getElementById("resultsSection");
const resultsCountBadge = document.getElementById("resultsCountBadge");
const resultCardsContainer = document.getElementById("resultCardsContainer");
const btnCopyAll = document.getElementById("btnCopyAll");
const btnToggleRawJSON = document.getElementById("btnToggleRawJSON");
const rawJsonBox = document.getElementById("rawJsonBox");
const rawJsonContent = document.getElementById("rawJsonContent");
const btnCopyJSON = document.getElementById("btnCopyJSON");

const historySection = document.getElementById("historySection");
const historyListContainer = document.getElementById("historyListContainer");
const btnRefreshHistory = document.getElementById("btnRefreshHistory");
const modelLabel = document.getElementById("modelLabel");

// --- DOM Elements: Telegram Parser ---
const tgDropZone = document.getElementById("tgDropZone");
const tgFileInput = document.getElementById("tgFileInput");
const tgFolderInput = document.getElementById("tgFolderInput");
const tgPhotosInput = document.getElementById("tgPhotosInput");
const btnPickTgFile = document.getElementById("btnPickTgFile");
const btnPickTgFolder = document.getElementById("btnPickTgFolder");
const btnAttachTgPhotos = document.getElementById("btnAttachTgPhotos");

const tgSelectedFileContainer = document.getElementById("tgSelectedFileContainer");
const tgSelectedFileName = document.getElementById("tgSelectedFileName");
const tgSelectedFileSize = document.getElementById("tgSelectedFileSize");
const tgSelectedPhotosBadge = document.getElementById("tgSelectedPhotosBadge");
const btnRemoveTgFile = document.getElementById("btnRemoveTgFile");

const tgIncludeServiceCheck = document.getElementById("tgIncludeServiceCheck");
const btnConvertTelegram = document.getElementById("btnConvertTelegram");
const tgLoadingSection = document.getElementById("tgLoadingSection");
const tgResultsSection = document.getElementById("tgResultsSection");

const tgChatAvatar = document.getElementById("tgChatAvatar");
const tgChatTitle = document.getElementById("tgChatTitle");
const tgExportSource = document.getElementById("tgExportSource");
const tgStatTotal = document.getElementById("tgStatTotal");
const tgStatMedia = document.getElementById("tgStatMedia");
const tgStatReplies = document.getElementById("tgStatReplies");
const tgStatReactions = document.getElementById("tgStatReactions");

const tgSearchInput = document.getElementById("tgSearchInput");
const btnCopyTgJSON = document.getElementById("btnCopyTgJSON");
const btnDownloadTgJSON = document.getElementById("btnDownloadTgJSON");
const btnToggleTgRawJSON = document.getElementById("btnToggleTgRawJSON");
const tgRawJsonBox = document.getElementById("tgRawJsonBox");
const tgRawJsonContent = document.getElementById("tgRawJsonContent");
const tgMessageFeedContainer = document.getElementById("tgMessageFeedContainer");

const tgHistorySection = document.getElementById("tgHistorySection");
const tgHistoryListContainer = document.getElementById("tgHistoryListContainer");
const btnRefreshTgHistory = document.getElementById("btnRefreshTgHistory");

// --- DOM Elements: Database Converter ---
const dbDropZone = document.getElementById("dbDropZone");
const dbFileInput = document.getElementById("dbFileInput");
const btnPickDbFile = document.getElementById("btnPickDbFile");
const dbSelectedFileContainer = document.getElementById("dbSelectedFileContainer");
const dbSelectedFileName = document.getElementById("dbSelectedFileName");
const dbSelectedFileSize = document.getElementById("dbSelectedFileSize");
const btnRemoveDbFile = document.getElementById("btnRemoveDbFile");
const btnConvertDatabase = document.getElementById("btnConvertDatabase");
const dbLoadingSection = document.getElementById("dbLoadingSection");
const dbResultsSection = document.getElementById("dbResultsSection");

const dbName = document.getElementById("dbName");
const dbSource = document.getElementById("dbSource");
const dbFormatBadge = document.getElementById("dbFormatBadge");
const dbStatTables = document.getElementById("dbStatTables");
const dbStatRows = document.getElementById("dbStatRows");

const dbTableTabsContainer = document.getElementById("dbTableTabsContainer");
const dbActiveTableName = document.getElementById("dbActiveTableName");
const dbActiveTableRowCount = document.getElementById("dbActiveTableRowCount");
const dbSearchInput = document.getElementById("dbSearchInput");
const dbPageSizeSelect = document.getElementById("dbPageSizeSelect");
const btnCopyTableJSON = document.getElementById("btnCopyTableJSON");
const btnDownloadTableJSON = document.getElementById("btnDownloadTableJSON");
const btnCopyDbJSON = document.getElementById("btnCopyDbJSON");
const btnDownloadDbJSON = document.getElementById("btnDownloadDbJSON");
const btnToggleDbRawJSON = document.getElementById("btnToggleDbRawJSON");
const dbRawJsonBox = document.getElementById("dbRawJsonBox");
const dbRawJsonContent = document.getElementById("dbRawJsonContent");
const dbTableContainer = document.getElementById("dbTableContainer");

const dbPaginationContainer = document.getElementById("dbPaginationContainer");
const dbPaginationInfo = document.getElementById("dbPaginationInfo");
const dbPageIndicator = document.getElementById("dbPageIndicator");
const btnDbPrevPage = document.getElementById("btnDbPrevPage");
const btnDbNextPage = document.getElementById("btnDbNextPage");

const dbHistorySection = document.getElementById("dbHistorySection");
const dbHistoryListContainer = document.getElementById("dbHistoryListContainer");
const btnRefreshDbHistory = document.getElementById("btnRefreshDbHistory");

const SUPPORTED_OCR_EXTS = [".png", ".jpg", ".jpeg", ".jpe", ".webp", ".bmp"];
const SUPPORTED_PHOTO_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".gif"];
const SUPPORTED_DB_EXTS = [".sql", ".db", ".sqlite", ".sqlite3", ".csv", ".tsv", ".xlsx"];
const SUPPORTED_YT_EXTS = [".html", ".htm", ".json"];

// =============================================================================
// Initialization
// =============================================================================
document.addEventListener("DOMContentLoaded", async () => {
    lucide.createIcons();
    await fetchConfig();
    setupNavigation();
    setupOcrEventListeners();
    setupTelegramEventListeners();
    setupDatabaseEventListeners();
    setupYouTubeEventListeners();
});

// =============================================================================
// Service Switcher Navigation & Dynamic History Button
// =============================================================================
function setupNavigation() {
    tabOCR.addEventListener("click", () => switchService("ocr"));
    tabTelegram.addEventListener("click", () => switchService("telegram"));
    tabDatabase.addEventListener("click", () => switchService("database"));
    tabYouTube.addEventListener("click", () => switchService("youtube"));

    // Unified dynamic history button
    btnToggleHistory.addEventListener("click", toggleActiveHistory);
}

function switchService(serviceName) {
    if (activeService === serviceName) return;
    activeService = serviceName;

    // Reset all tabs
    [tabOCR, tabTelegram, tabDatabase, tabYouTube].forEach(btn => {
        btn.classList.remove("active");
        btn.classList.add("text-slate-400");
    });
    [viewOCR, viewTelegram, viewDatabase, viewYouTube].forEach(view => view.classList.add("hidden"));

    if (serviceName === "ocr") {
        tabOCR.classList.add("active");
        tabOCR.classList.remove("text-slate-400");
        viewOCR.classList.remove("hidden");

        ocrStatusBadge.classList.remove("hidden");
        historyBtnLabel.textContent = "OCR History";
        updateHistoryBtnVisualState(!historySection.classList.contains("hidden"));
        brandSubtitle.textContent = "Gemini Myanmar-English OCR & Telegram Chat Parser";
    } else if (serviceName === "telegram") {
        tabTelegram.classList.add("active");
        tabTelegram.classList.remove("text-slate-400");
        viewTelegram.classList.remove("hidden");

        ocrStatusBadge.classList.add("hidden");
        historyBtnLabel.textContent = "Telegram History";
        updateHistoryBtnVisualState(!tgHistorySection.classList.contains("hidden"));
        brandSubtitle.textContent = "Telegram Chat History HTML to Structured JSON Parser";
    } else if (serviceName === "database") {
        tabDatabase.classList.add("active");
        tabDatabase.classList.remove("text-slate-400");
        viewDatabase.classList.remove("hidden");

        ocrStatusBadge.classList.add("hidden");
        historyBtnLabel.textContent = "Database History";
        updateHistoryBtnVisualState(!dbHistorySection.classList.contains("hidden"));
        brandSubtitle.textContent = "Multi-Format Database Export (.sql, .db, .csv, .xlsx) to Structured JSON";
    } else if (serviceName === "youtube") {
        tabYouTube.classList.add("active");
        tabYouTube.classList.remove("text-slate-400");
        viewYouTube.classList.remove("hidden");

        ocrStatusBadge.classList.add("hidden");
        historyBtnLabel.textContent = "YouTube History";
        const ytHistSec = document.getElementById("ytHistorySection");
        updateHistoryBtnVisualState(ytHistSec && !ytHistSec.classList.contains("hidden"));
        brandSubtitle.textContent = "YouTube Channel Metadata & Video Catalog to Structured JSON";
    }
    lucide.createIcons();
}

function toggleActiveHistory() {
    if (activeService === "ocr") {
        historySection.classList.toggle("hidden");
        const isOpen = !historySection.classList.contains("hidden");
        updateHistoryBtnVisualState(isOpen);
        if (isOpen) {
            loadHistory();
            historySection.scrollIntoView({ behavior: "smooth" });
        }
    } else if (activeService === "telegram") {
        tgHistorySection.classList.toggle("hidden");
        const isOpen = !tgHistorySection.classList.contains("hidden");
        updateHistoryBtnVisualState(isOpen);
        if (isOpen) {
            loadTgHistory();
            tgHistorySection.scrollIntoView({ behavior: "smooth" });
        }
    } else if (activeService === "database") {
        dbHistorySection.classList.toggle("hidden");
        const isOpen = !dbHistorySection.classList.contains("hidden");
        updateHistoryBtnVisualState(isOpen);
        if (isOpen) {
            loadDbHistory();
            dbHistorySection.scrollIntoView({ behavior: "smooth" });
        }
    } else if (activeService === "youtube") {
        const ytHistSec = document.getElementById("ytHistorySection");
        if (ytHistSec) {
            ytHistSec.classList.toggle("hidden");
            const isOpen = !ytHistSec.classList.contains("hidden");
            updateHistoryBtnVisualState(isOpen);
            if (isOpen) {
                loadYtHistory();
                ytHistSec.scrollIntoView({ behavior: "smooth" });
            }
        }
    }
}

function updateHistoryBtnVisualState(isOpen) {
    if (isOpen) {
        btnToggleHistory.classList.add("history-btn-active");
    } else {
        btnToggleHistory.classList.remove("history-btn-active");
    }
}

// =============================================================================
// Runtime Configuration
// =============================================================================
async function fetchConfig() {
    try {
        const res = await fetch("/api/config");
        if (res.ok) {
            const data = await res.json();
            defaultPrompt = data.default_prompt || "";
            promptInput.value = defaultPrompt;
            batchSizeInput.value = data.default_batch_size || 2;
            batchSizeVal.textContent = batchSizeInput.value;
            if (data.model_name) {
                modelLabel.textContent = data.model_name;
            }
            if (!data.has_api_key) {
                mockModeCheck.checked = true;
                showToast("No GEMINI_API_KEY detected; defaulting to Mock Mode.", "info");
            }
        }
    } catch (err) {
        console.warn("Could not fetch /api/config:", err);
    }
}

// =============================================================================
// OCR Service Logic
// =============================================================================
function setupOcrEventListeners() {
    btnPickFiles.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.value = "";
        fileInput.click();
    });
    btnPickFolder.addEventListener("click", (e) => {
        e.stopPropagation();
        folderInput.value = "";
        folderInput.click();
    });

    fileInput.addEventListener("change", (e) => handleOcrFileSelection(e.target.files));
    folderInput.addEventListener("change", (e) => handleOcrFileSelection(e.target.files));

    // Drag & Drop
    dropZone.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("input")) return;
        fileInput.value = "";
        fileInput.click();
    });

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");

        if (e.dataTransfer.items) {
            const files = [];
            const items = Array.from(e.dataTransfer.items);
            for (const item of items) {
                const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                if (entry) {
                    await traverseFileTree(entry, files);
                } else if (item.kind === "file") {
                    const f = item.getAsFile();
                    if (f) files.push(f);
                }
            }
            handleOcrFileSelection(files);
        } else if (e.dataTransfer.files) {
            handleOcrFileSelection(e.dataTransfer.files);
        }
    });

    btnClearFiles.addEventListener("click", () => {
        selectedFiles = [];
        fileInput.value = "";
        folderInput.value = "";
        updateSelectedFilesUI();
    });

    batchSizeInput.addEventListener("input", (e) => {
        batchSizeVal.textContent = e.target.value;
    });

    btnResetPrompt.addEventListener("click", () => {
        promptInput.value = defaultPrompt;
        showToast("Prompt reset to default instructions", "info");
    });

    btnRunOCR.addEventListener("click", runOcrPipeline);
    btnCopyAll.addEventListener("click", copyAllExtractedText);
    btnToggleRawJSON.addEventListener("click", () => {
        rawJsonBox.classList.toggle("hidden");
    });
    btnCopyJSON.addEventListener("click", () => {
        if (latestOcrResponse) {
            navigator.clipboard.writeText(JSON.stringify(latestOcrResponse, null, 2));
            showToast("JSON copied to clipboard!", "success");
        }
    });

    btnRefreshHistory.addEventListener("click", loadHistory);
}

async function traverseFileTree(item, fileList) {
    if (item.isFile) {
        return new Promise((resolve) => {
            item.file((file) => {
                if (!file.webkitRelativePath && item.fullPath) {
                    const cleanPath = item.fullPath.startsWith("/") ? item.fullPath.slice(1) : item.fullPath;
                    Object.defineProperty(file, "webkitRelativePath", {
                        value: cleanPath,
                        writable: true,
                    });
                }
                fileList.push(file);
                resolve();
            });
        });
    } else if (item.isDirectory) {
        const dirReader = item.createReader();
        const readAllEntries = async () => {
            const all = [];
            while (true) {
                const batch = await new Promise((resolve) => {
                    dirReader.readEntries((entries) => resolve(entries || []));
                });
                if (!batch || batch.length === 0) break;
                all.push(...batch);
            }
            return all;
        };
        const entries = await readAllEntries();
        for (const child of entries) {
            await traverseFileTree(child, fileList);
        }
    }
}

function handleOcrFileSelection(files) {
    if (!files || !files.length) return;

    for (const f of Array.from(files)) {
        const ext = "." + f.name.split(".").pop().toLowerCase();
        if (SUPPORTED_OCR_EXTS.includes(ext)) {
            if (!selectedFiles.some(existing => existing.name === f.name && existing.size === f.size)) {
                selectedFiles.push(f);
            }
        }
    }
    updateSelectedFilesUI();
}

function updateSelectedFilesUI() {
    filesBadgeContainer.innerHTML = "";
    if (selectedFiles.length === 0) {
        selectedFilesSection.classList.add("hidden");
        btnRunOCR.disabled = true;
        return;
    }

    selectedFilesSection.classList.remove("hidden");
    btnRunOCR.disabled = false;
    selectedCountBadge.textContent = `${selectedFiles.length} file(s) selected`;

    selectedFiles.forEach((file, index) => {
        const badge = document.createElement("div");
        badge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300";
        badge.innerHTML = `
            <i data-lucide="image" class="w-3.5 h-3.5 text-indigo-400"></i>
            <span class="max-w-[150px] truncate" title="${file.name}">${file.name}</span>
            <span class="text-[10px] text-slate-500">(${formatFileSize(file.size)})</span>
            <button type="button" class="text-slate-400 hover:text-rose-400 ml-1 transition" onclick="removeOcrFile(${index})">
                &times;
            </button>
        `;
        filesBadgeContainer.appendChild(badge);
    });
    lucide.createIcons();
}

window.removeOcrFile = function(index) {
    selectedFiles.splice(index, 1);
    updateSelectedFilesUI();
};

async function runOcrPipeline() {
    if (!selectedFiles.length) {
        showToast("Please select at least one image.", "warning");
        return;
    }

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append("files", f));
    formData.append("content", promptInput.value);
    formData.append("file_per_batch", batchSizeInput.value);
    formData.append("mock", mockModeCheck.checked ? "true" : "false");

    btnRunOCR.disabled = true;
    loadingSection.classList.remove("hidden");
    resultsSection.classList.add("hidden");

    try {
        const response = await fetch("/api/ocr", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server error (${response.status})`);
        }

        const data = await response.json();
        latestOcrResponse = data;
        renderOcrResults(data);
        showToast(`Successfully processed ${data.total_files} file(s)!`, "success");
    } catch (err) {
        console.error("OCR execution error:", err);
        showToast(err.message || "An error occurred during OCR execution", "error");
    } finally {
        btnRunOCR.disabled = false;
        loadingSection.classList.add("hidden");
    }
}

function renderOcrResults(data) {
    resultsSection.classList.remove("hidden");
    resultsCountBadge.textContent = `${data.total_files} item(s) processed`;
    rawJsonContent.textContent = JSON.stringify(data, null, 2);
    resultCardsContainer.innerHTML = "";

    data.results.forEach((item, idx) => {
        const card = document.createElement("div");
        card.className = "glass-panel rounded-2xl p-5 border border-slate-800 flex flex-col md:flex-row gap-6 shadow-lg";

        const textOutput = item.text || item.raw_response || "";

        card.innerHTML = `
            <div class="w-full md:w-56 shrink-0 flex flex-col items-center gap-2">
                <div class="relative w-full aspect-square rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center group cursor-pointer" onclick="openImageModal('${item.url}')">
                    <img src="${item.url}" alt="${item.basename}" class="w-full h-full object-contain transition duration-200 group-hover:scale-105">
                    <div class="absolute inset-0 bg-indigo-950/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition">
                        <span class="text-xs px-2.5 py-1 rounded bg-black/70 text-white font-medium flex items-center gap-1">
                            <i data-lucide="zoom-in" class="w-3.5 h-3.5"></i> Click to Zoom
                        </span>
                    </div>
                </div>
                <span class="text-xs text-slate-400 font-mono text-center truncate max-w-full" title="${item.basename}">
                    ${item.basename}
                </span>
            </div>

            <div class="flex-1 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-semibold text-indigo-400 font-mono">#${idx + 1}</span>
                            <span class="text-xs font-medium text-slate-300">Extracted Text</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition flex items-center gap-1" onclick="copyCardText(${idx})">
                                <i data-lucide="copy" class="w-3 h-3"></i> Copy
                            </button>
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition flex items-center gap-1" onclick="downloadCardText('${item.basename}', ${idx})">
                                <i data-lucide="download" class="w-3 h-3"></i> .txt
                            </button>
                        </div>
                    </div>

                    <div id="cardText-${idx}" class="myanmar-text text-sm leading-relaxed text-slate-200 whitespace-pre-wrap bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 min-h-[140px] max-h-96 overflow-y-auto selection:bg-indigo-500 selection:text-white">
                        ${escapeHtml(textOutput) || '<span class="text-slate-500 italic">No text recognized</span>'}
                    </div>
                </div>

                <div class="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500">
                    <span>Format: UTF-8 Unicode</span>
                    <span class="font-mono">Status: OK</span>
                </div>
            </div>
        `;
        resultCardsContainer.appendChild(card);
    });

    lucide.createIcons();
    resultsSection.scrollIntoView({ behavior: "smooth" });
}

window.copyCardText = function(idx) {
    const el = document.getElementById(`cardText-${idx}`);
    if (el) {
        navigator.clipboard.writeText(el.innerText.trim());
        showToast("Extracted text copied to clipboard!", "success");
    }
};

window.downloadCardText = function(basename, idx) {
    const el = document.getElementById(`cardText-${idx}`);
    if (el) {
        const text = el.innerText.trim();
        const baseNameWithoutExt = basename.replace(/\.[^/.]+$/, "");
        downloadTextFile(`${baseNameWithoutExt}_ocr.txt`, text);
        showToast(`Downloaded ${baseNameWithoutExt}_ocr.txt`, "info");
    }
};

function copyAllExtractedText() {
    if (!latestOcrResponse || !latestOcrResponse.results) return;
    const combined = latestOcrResponse.results.map((r, i) => {
        const text = r.text || r.raw_response || "";
        return `=== [${i + 1}] ${r.basename} ===\n${text}\n`;
    }).join("\n\n");

    navigator.clipboard.writeText(combined);
    showToast("All extracted text copied to clipboard!", "success");
}

async function loadHistory() {
    historyListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">Fetching logs...</p>`;
    try {
        const res = await fetch("/api/history");
        if (!res.ok) throw new Error("Failed to load history");
        const logs = await res.json();

        if (!logs.length) {
            historyListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No previous OCR history found.</p>`;
            return;
        }

        historyListContainer.innerHTML = "";
        logs.forEach((logEntry, index) => {
            const item = document.createElement("div");
            item.className = "bg-slate-900/80 rounded-xl p-4 border border-slate-800 flex flex-col gap-2";

            const timestamp = logEntry.timestamp || "Unknown time";
            const total = logEntry.total_files || (logEntry.results ? logEntry.results.length : 0);
            const promptUsed = logEntry.prompt || "Default Prompt";

            item.innerHTML = `
                <div class="flex items-center justify-between cursor-pointer" onclick="toggleHistoryItem(${index})">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-indigo-400"></span>
                        <span class="text-xs font-mono text-slate-300 font-semibold">${timestamp}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">${total} file(s)</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-indigo-400 hover:underline">View Details</span>
                        <i data-lucide="chevron-down" id="histChevron-${index}" class="w-4 h-4 text-slate-400 transition-transform"></i>
                    </div>
                </div>

                <div id="histContent-${index}" class="hidden mt-3 pt-3 border-t border-slate-800 flex flex-col gap-3">
                    <div class="text-[11px] text-slate-400">
                        <span class="text-slate-500 font-medium">Prompt:</span>
                        <span class="italic font-mono">${escapeHtml(promptUsed)}</span>
                    </div>

                    <div class="flex flex-col gap-2 max-h-60 overflow-y-auto">
                        ${renderHistoryItems(logEntry.results)}
                    </div>

                    <div class="flex justify-end pt-2">
                        <button class="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1" onclick="copyHistoryJson(${index})">
                            <i data-lucide="copy" class="w-3.5 h-3.5"></i> Copy Raw Log Entry
                        </button>
                    </div>
                    <pre id="histJson-${index}" class="hidden">${JSON.stringify(logEntry, null, 2)}</pre>
                </div>
            `;
            historyListContainer.appendChild(item);
        });

        lucide.createIcons();
    } catch (err) {
        historyListContainer.innerHTML = `<p class="text-xs text-rose-400 text-center py-6">Could not load history: ${err.message}</p>`;
    }
}

function renderHistoryItems(items) {
    if (!items || !items.length) return `<span class="text-xs text-slate-500 italic">No responses recorded.</span>`;
    return items.map((it, i) => `
        <div class="bg-slate-950/60 p-2.5 rounded border border-slate-800 text-xs">
            <span class="font-semibold text-slate-300 font-mono">${it.filename || `Item #${i+1}`}</span>
            <p class="myanmar-text text-slate-300 mt-1 whitespace-pre-wrap">${escapeHtml(it.text || it.raw_response || '')}</p>
        </div>
    `).join("");
}

window.toggleHistoryItem = function(idx) {
    const content = document.getElementById(`histContent-${idx}`);
    const chevron = document.getElementById(`histChevron-${idx}`);
    if (content) {
        content.classList.toggle("hidden");
        if (chevron) {
            chevron.classList.toggle("rotate-180");
        }
    }
};

window.copyHistoryJson = function(idx) {
    const el = document.getElementById(`histJson-${idx}`);
    if (el) {
        navigator.clipboard.writeText(el.textContent);
        showToast("History JSON copied!", "success");
    }
};

// =============================================================================
// Telegram Parser Service Logic & Image Staging
// =============================================================================
function setupTelegramEventListeners() {
    btnPickTgFile.addEventListener("click", (e) => {
        e.stopPropagation();
        tgFileInput.value = "";
        tgFileInput.click();
    });
    btnPickTgFolder.addEventListener("click", (e) => {
        e.stopPropagation();
        tgFolderInput.value = "";
        tgFolderInput.click();
    });
    btnAttachTgPhotos.addEventListener("click", (e) => {
        e.stopPropagation();
        tgPhotosInput.value = "";
        tgPhotosInput.click();
    });

    tgFileInput.addEventListener("change", (e) => handleTelegramFileSelection(e.target.files));
    tgFolderInput.addEventListener("change", (e) => handleTelegramFileSelection(e.target.files));
    tgPhotosInput.addEventListener("change", (e) => handleTelegramPhotosAttachment(e.target.files));

    // Telegram Drag & Drop
    tgDropZone.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("input")) {
            return;
        }
        tgFileInput.value = "";
        tgFileInput.click();
    });

    tgDropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        tgDropZone.classList.add("dragover");
    });

    tgDropZone.addEventListener("dragleave", () => {
        tgDropZone.classList.remove("dragover");
    });

    tgDropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        tgDropZone.classList.remove("dragover");

        if (e.dataTransfer.items) {
            const files = [];
            const items = Array.from(e.dataTransfer.items);
            for (const item of items) {
                const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                if (entry) {
                    await traverseFileTree(entry, files);
                } else if (item.kind === "file") {
                    const f = item.getAsFile();
                    if (f) files.push(f);
                }
            }
            handleTelegramFileSelection(files);
        } else if (e.dataTransfer.files) {
            handleTelegramFileSelection(e.dataTransfer.files);
        }
    });

    btnRemoveTgFile.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedTgFile = null;
        selectedTgPhotos = [];
        tgFileInput.value = "";
        tgFolderInput.value = "";
        tgPhotosInput.value = "";
        tgSelectedFileContainer.classList.add("hidden");
        tgSelectedPhotosBadge.classList.add("hidden");
        btnConvertTelegram.disabled = true;
    });

    btnConvertTelegram.addEventListener("click", convertTelegramChat);

    // Search filter
    tgSearchInput.addEventListener("input", (e) => {
        filterTelegramMessages(e.target.value);
    });

    // Copy & Download
    btnCopyTgJSON.addEventListener("click", () => {
        if (telegramChatData) {
            navigator.clipboard.writeText(JSON.stringify(telegramChatData, null, 2));
            showToast("Telegram JSON copied to clipboard!", "success");
        }
    });

    btnDownloadTgJSON.addEventListener("click", () => {
        if (telegramChatData) {
            const fileName = (telegramChatData.chat_title ? telegramChatData.chat_title.replace(/[^\w-]/g, "_") : "telegram") + "_messages.json";
            downloadTextFile(fileName, JSON.stringify(telegramChatData, null, 2));
            showToast(`Downloaded ${fileName}`, "info");
        }
    });

    btnToggleTgRawJSON.addEventListener("click", () => {
        tgRawJsonBox.classList.toggle("hidden");
    });

    btnRefreshTgHistory.addEventListener("click", loadTgHistory);
}

function handleTelegramFileSelection(files) {
    if (!files || !files.length) return;

    let foundHtml = null;
    const photos = [];
    let folderName = "";

    const fileArray = Array.from(files);

    for (const f of fileArray) {
        const lower = f.name.toLowerCase();

        // Extract folder name from webkitRelativePath if present
        if (!folderName && f.webkitRelativePath) {
            const parts = f.webkitRelativePath.split("/");
            if (parts.length > 1) {
                folderName = parts[0];
            }
        }

        if (lower.endsWith(".html") || lower.endsWith(".htm")) {
            // Prioritize messages.html if multiple html files exist
            if (!foundHtml || lower === "messages.html") {
                foundHtml = f;
            }
        } else {
            const ext = "." + lower.split(".").pop();
            if (SUPPORTED_PHOTO_EXTS.includes(ext)) {
                photos.push(f);
            }
        }
    }

    if (foundHtml) {
        selectedTgFile = foundHtml;
        selectedTgPhotos = photos;

        if (folderName) {
            tgSelectedFileName.innerHTML = `<span class="text-indigo-400 font-semibold flex items-center gap-1"><i data-lucide="folder" class="w-3.5 h-3.5 inline"></i> ${escapeHtml(folderName)}</span> <span class="text-slate-400 font-mono text-[11px]">/ ${escapeHtml(foundHtml.name)}</span>`;
        } else {
            tgSelectedFileName.textContent = foundHtml.name;
        }

        tgSelectedFileSize.textContent = `(${formatFileSize(foundHtml.size)})`;

        if (photos.length > 0) {
            tgSelectedPhotosBadge.textContent = `+ ${photos.length} photo(s) attached`;
            tgSelectedPhotosBadge.classList.remove("hidden");
        } else {
            tgSelectedPhotosBadge.classList.add("hidden");
        }

        tgSelectedFileContainer.classList.remove("hidden");
        btnConvertTelegram.disabled = false;
        lucide.createIcons();

        const toastMsg = folderName
            ? `Export folder loaded: "${folderName}" (${foundHtml.name} found, ${photos.length} photos)`
            : `Loaded ${foundHtml.name} (${photos.length} photos attached)`;
        showToast(toastMsg, "success");
    } else {
        if (photos.length > 0) {
            showToast(`Found ${photos.length} photo(s), but no messages.html. Please select the main export folder containing messages.html`, "warning");
        } else {
            showToast("No messages.html found in the selection. Please select a valid Telegram export folder.", "error");
        }
    }
}

async function handleTelegramPhotosAttachment(files) {
    if (!files || !files.length) return;

    const photos = Array.from(files).filter(f => {
        const ext = "." + f.name.toLowerCase().split(".").pop();
        return SUPPORTED_PHOTO_EXTS.includes(ext);
    });

    if (!photos.length) {
        showToast("No valid image files found in selection.", "warning");
        return;
    }

    if (activeTgSessionId) {
        const formData = new FormData();
        formData.append("session_id", activeTgSessionId);
        photos.forEach(p => formData.append("photos", p));

        try {
            showToast(`Uploading and attaching ${photos.length} photo(s)...`, "info");
            const res = await fetch("/api/telegram/attach-photos", {
                method: "POST",
                body: formData,
            });
            if (!res.ok) throw new Error("Failed to attach photos.");
            const data = await res.json();

            if (telegramChatData && data.messages) {
                telegramChatData.messages = data.messages;
                renderTelegramMessages(data.messages, telegramChatData.chat_title);
            }
            showToast(`Successfully loaded ${data.attached_count} photos!`, "success");
        } catch (err) {
            console.error("Error attaching photos:", err);
            showToast(err.message || "Failed to attach photos", "error");
        }
    } else {
        selectedTgPhotos = photos;
        tgSelectedPhotosBadge.textContent = `+ ${photos.length} photo(s) attached`;
        tgSelectedPhotosBadge.classList.remove("hidden");
        showToast(`Queued ${photos.length} photos for conversion.`, "info");
    }
}

window.triggerAttachPhotoPrompt = function() {
    tgPhotosInput.click();
};

async function convertTelegramChat() {
    if (!selectedTgFile) {
        showToast("Please choose a messages.html file first.", "warning");
        return;
    }

    const formData = new FormData();
    formData.append("file", selectedTgFile);
    selectedTgPhotos.forEach(p => formData.append("photos", p));
    formData.append("include_service", tgIncludeServiceCheck.checked ? "true" : "false");

    btnConvertTelegram.disabled = true;
    tgLoadingSection.classList.remove("hidden");
    tgResultsSection.classList.add("hidden");

    try {
        const response = await fetch("/api/telegram/convert", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || errData.message || `Server error (${response.status})`);
        }

        const data = await response.json();
        activeTgSessionId = data.session_id;
        telegramChatData = data;
        renderTelegramResults(data);
        showToast(`Successfully converted ${data.total_messages} messages!`, "success");
    } catch (err) {
        console.error("Telegram parse error:", err);
        showToast(err.message || "Failed to parse Telegram HTML file", "error");
    } finally {
        btnConvertTelegram.disabled = false;
        tgLoadingSection.classList.add("hidden");
    }
}

function renderTelegramResults(chat) {
    tgResultsSection.classList.remove("hidden");

    // Chat Header / Stats
    const title = chat.chat_title || "Telegram Chat";
    tgChatTitle.textContent = title;
    tgChatAvatar.textContent = title.charAt(0).toUpperCase();
    tgExportSource.textContent = `Source: ${selectedTgFile ? selectedTgFile.name : chat.export_source || "messages.html"}`;

    const total = chat.total_messages || 0;
    const mediaCount = (chat.messages || []).filter(m => m.media !== null).length;
    const repliesCount = (chat.messages || []).filter(m => m.reply_to_message_id !== null).length;
    const reactionsCount = (chat.messages || []).reduce((acc, m) => acc + (m.reaction_count || 0), 0);

    tgStatTotal.textContent = total;
    tgStatMedia.textContent = mediaCount;
    tgStatReplies.textContent = repliesCount;
    tgStatReactions.textContent = reactionsCount;

    // Raw JSON Content
    tgRawJsonContent.textContent = JSON.stringify(chat, null, 2);

    // Messages Feed
    renderTelegramMessages(chat.messages || [], title);

    tgResultsSection.scrollIntoView({ behavior: "smooth" });
}

function renderTelegramMessages(messages, chatContactTitle) {
    tgMessageFeedContainer.innerHTML = "";

    if (!messages.length) {
        tgMessageFeedContainer.innerHTML = `
            <div class="text-center py-12 text-slate-500 text-xs">
                No messages found in this chat export.
            </div>
        `;
        return;
    }

    messages.forEach((msg) => {
        if (msg.type === "service") {
            const serviceDiv = document.createElement("div");
            serviceDiv.className = "tg-msg-item flex items-center justify-center my-3";
            serviceDiv.setAttribute("data-searchable", (msg.text || "").toLowerCase());
            serviceDiv.innerHTML = `
                <div class="px-3.5 py-1 rounded-full text-[11px] font-medium bg-slate-900/90 text-slate-400 border border-slate-800 shadow-sm flex items-center gap-1.5">
                    <i data-lucide="calendar" class="w-3 h-3 text-indigo-400"></i>
                    <span>${escapeHtml(msg.text || "Service Notice")}</span>
                </div>
            `;
            tgMessageFeedContainer.appendChild(serviceDiv);
            return;
        }

        const sender = msg.from_name || "Unknown";
        const isPeer = (sender === chatContactTitle);
        const card = document.createElement("div");
        card.className = "tg-msg-item flex flex-col";
        card.setAttribute("data-searchable", `${sender} ${msg.text || ""} ${msg.media ? msg.media.file_path : ""}`.toLowerCase());

        const bubbleWrapper = document.createElement("div");
        bubbleWrapper.className = `flex ${isPeer ? 'justify-start' : 'justify-end'}`;

        const bubble = document.createElement("div");
        bubble.className = `max-w-[85%] sm:max-w-[70%] rounded-2xl p-4 shadow-md transition duration-150 ${
            isPeer
                ? 'chat-bubble-peer bg-slate-900/80 border border-slate-800 text-slate-100 rounded-tl-sm'
                : 'chat-bubble-user bg-indigo-950/40 border border-indigo-500/30 text-slate-100 rounded-tr-sm'
        }`;

        const topRow = document.createElement("div");
        topRow.className = "flex items-center justify-between gap-3 pb-1 mb-1 border-b border-slate-800/60";
        topRow.innerHTML = `
            <div class="flex items-center gap-1.5">
                <span class="font-bold text-xs ${isPeer ? 'text-indigo-400' : 'text-emerald-400'}">
                    ${escapeHtml(sender)}
                </span>
            </div>
            <div class="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                <span>${escapeHtml(msg.time || formatTime(msg.date))}</span>
                <span class="text-slate-600">#${msg.id}</span>
            </div>
        `;
        bubble.appendChild(topRow);

        if (msg.reply_to_message_id) {
            const replyBox = document.createElement("div");
            replyBox.className = "mt-1.5 mb-2 px-2.5 py-1 rounded bg-slate-950/60 border-l-2 border-indigo-400 text-xs text-slate-400 flex items-center gap-1.5";
            replyBox.innerHTML = `
                <i data-lucide="reply" class="w-3 h-3 text-indigo-400"></i>
                <span>Replying to <span class="text-indigo-300 font-mono font-medium">#${msg.reply_to_message_id}</span></span>
            `;
            bubble.appendChild(replyBox);
        }

        if (msg.media) {
            const mediaBox = document.createElement("div");
            mediaBox.className = "mt-2 mb-2 p-2 rounded-xl bg-slate-950/70 border border-slate-800 flex flex-col gap-2 text-xs";

            const photoUrl = msg.media.url || msg.media.thumb_url;
            if (photoUrl) {
                mediaBox.innerHTML = `
                    <div class="relative max-w-sm rounded-lg overflow-hidden bg-slate-900 border border-slate-700/60 cursor-pointer group" onclick="openImageModal('${msg.media.url || photoUrl}')">
                        <img src="${photoUrl}" alt="${escapeHtml(msg.media.file_path || 'Telegram Photo')}" class="w-full max-h-72 object-contain transition duration-200 group-hover:scale-[1.02]">
                        <div class="absolute inset-0 bg-indigo-950/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition">
                            <span class="text-xs px-2.5 py-1 rounded bg-black/75 text-white font-medium flex items-center gap-1 shadow">
                                <i data-lucide="zoom-in" class="w-3.5 h-3.5"></i> Click to Zoom
                            </span>
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                        <span class="truncate max-w-[200px]" title="${escapeHtml(msg.media.file_path || '')}">${escapeHtml(msg.media.file_path || '')}</span>
                        <span>${msg.media.width || 0} &times; ${msg.media.height || 0}</span>
                    </div>
                `;
            } else {
                mediaBox.innerHTML = `
                    <div class="flex items-center justify-between gap-2.5">
                        <div class="flex items-center gap-2.5 min-w-0">
                            <div class="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400 shrink-0">
                                <i data-lucide="image" class="w-4 h-4"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <span class="text-slate-300 font-mono text-[11px] truncate block" title="${escapeHtml(msg.media.file_path || '')}">
                                    ${escapeHtml(msg.media.file_path || 'Photo')}
                                </span>
                                <span class="text-[10px] text-slate-500 uppercase font-mono">${msg.media.type || 'Photo'} &bull; ${msg.media.width || 0}&times;${msg.media.height || 0}</span>
                            </div>
                        </div>
                        <button type="button" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-medium transition flex items-center gap-1 shrink-0" onclick="triggerAttachPhotoPrompt()">
                            <i data-lucide="upload" class="w-3 h-3 text-indigo-400"></i> Load Photo
                        </button>
                    </div>
                `;
            }
            bubble.appendChild(mediaBox);
        }

        if (msg.text) {
            const textP = document.createElement("p");
            textP.className = "myanmar-text text-xs leading-relaxed text-slate-200 mt-1 whitespace-pre-wrap selection:bg-indigo-500 selection:text-white";
            textP.textContent = msg.text;
            bubble.appendChild(textP);
        }

        if (msg.reactions && msg.reactions.length > 0) {
            const rxContainer = document.createElement("div");
            rxContainer.className = "mt-2.5 pt-2 border-t border-slate-800/70 flex flex-wrap items-center gap-1.5";

            msg.reactions.forEach((rx) => {
                const pill = document.createElement("span");
                const userList = (rx.users && rx.users.length) ? rx.users.join(", ") : "User";
                pill.className = "reaction-pill inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-slate-950/80 border border-slate-700/80 hover:border-pink-500/60 transition cursor-default shadow-sm";
                pill.title = `Reacted by: ${userList}`;
                pill.innerHTML = `
                    <span class="text-sm select-none">${rx.emoji}</span>
                    <span class="text-[11px] font-semibold text-slate-300">${rx.count}</span>
                `;
                rxContainer.appendChild(pill);
            });

            if (msg.reaction_count > 1) {
                const totalRxBadge = document.createElement("span");
                totalRxBadge.className = "text-[10px] text-slate-500 ml-1 font-mono";
                totalRxBadge.textContent = `${msg.reaction_count} total`;
                rxContainer.appendChild(totalRxBadge);
            }

            bubble.appendChild(rxContainer);
        }

        bubbleWrapper.appendChild(bubble);
        card.appendChild(bubbleWrapper);
        tgMessageFeedContainer.appendChild(card);
    });

    lucide.createIcons();
}

function filterTelegramMessages(query) {
    const q = (query || "").trim().toLowerCase();
    const items = tgMessageFeedContainer.querySelectorAll(".tg-msg-item");
    items.forEach((item) => {
        if (!q) {
            item.classList.remove("hidden");
            return;
        }
        const searchable = item.getAttribute("data-searchable") || "";
        if (searchable.includes(q)) {
            item.classList.remove("hidden");
        } else {
            item.classList.add("hidden");
        }
    });
}

// =============================================================================
// Telegram History Operations
// =============================================================================
async function loadTgHistory() {
    tgHistoryListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">Fetching Telegram conversion logs...</p>`;
    try {
        const res = await fetch("/api/telegram/history");
        if (!res.ok) throw new Error("Failed to load Telegram history");
        const logs = await res.json();

        if (!logs.length) {
            tgHistoryListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No previous Telegram conversions found in logs/telegram_parser_log.jsonl.</p>`;
            return;
        }

        tgHistoryListContainer.innerHTML = "";
        logs.forEach((logEntry, index) => {
            const item = document.createElement("div");
            item.className = "bg-slate-900/80 rounded-xl p-4 border border-slate-800 flex flex-col gap-2";

            const timestamp = logEntry.timestamp || "Unknown time";
            const title = logEntry.chat_title || "Telegram Chat";
            const total = logEntry.total_messages || (logEntry.messages ? logEntry.messages.length : 0);
            const mediaCount = logEntry.media_count || 0;
            const reactionCount = logEntry.reaction_count || 0;

            item.innerHTML = `
                <div class="flex items-center justify-between cursor-pointer" onclick="toggleTgHistoryItem(${index})">
                    <div class="flex items-center gap-2.5 flex-wrap">
                        <span class="w-2.5 h-2.5 rounded-full bg-violet-400"></span>
                        <span class="text-xs font-bold text-white">${escapeHtml(title)}</span>
                        <span class="text-xs font-mono text-slate-400">${escapeHtml(timestamp)}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">${total} msgs</span>
                        ${mediaCount > 0 ? `<span class="text-xs px-2 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/20">${mediaCount} media</span>` : ''}
                        ${reactionCount > 0 ? `<span class="text-xs px-2 py-0.5 rounded bg-pink-500/10 text-pink-300 border border-pink-500/20">${reactionCount} reactions</span>` : ''}
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-indigo-400 hover:underline">View</span>
                        <i data-lucide="chevron-down" id="tgHistChevron-${index}" class="w-4 h-4 text-slate-400 transition-transform"></i>
                    </div>
                </div>

                <div id="tgHistContent-${index}" class="hidden mt-3 pt-3 border-t border-slate-800 flex flex-col gap-3">
                    <div class="flex items-center justify-between flex-wrap gap-2 text-xs">
                        <span class="text-slate-400 font-mono text-[11px]">Source: ${escapeHtml(logEntry.export_source || 'messages.html')}</span>
                        <div class="flex items-center gap-2">
                            <button class="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition flex items-center gap-1 text-xs" onclick="reloadTgHistoryToViewer(${index})">
                                <i data-lucide="external-link" class="w-3.5 h-3.5"></i> Load in Viewer
                            </button>
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition flex items-center gap-1 text-xs" onclick="copyTgHistoryJson(${index})">
                                <i data-lucide="copy" class="w-3.5 h-3.5"></i> Copy JSON
                            </button>
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition flex items-center gap-1 text-xs" onclick="downloadTgHistoryJson(${index})">
                                <i data-lucide="download" class="w-3.5 h-3.5"></i> Download
                            </button>
                        </div>
                    </div>

                    <pre id="tgHistJson-${index}" class="hidden">${JSON.stringify(logEntry, null, 2)}</pre>
                </div>
            `;
            tgHistoryListContainer.appendChild(item);
        });

        lucide.createIcons();
    } catch (err) {
        tgHistoryListContainer.innerHTML = `<p class="text-xs text-rose-400 text-center py-6">Could not load Telegram history: ${err.message}</p>`;
    }
}

window.toggleTgHistoryItem = function(idx) {
    const content = document.getElementById(`tgHistContent-${idx}`);
    const chevron = document.getElementById(`tgHistChevron-${idx}`);
    if (content) {
        content.classList.toggle("hidden");
        if (chevron) {
            chevron.classList.toggle("rotate-180");
        }
    }
};

window.reloadTgHistoryToViewer = async function(idx) {
    const el = document.getElementById(`tgHistJson-${idx}`);
    if (!el) return;
    try {
        const record = JSON.parse(el.textContent);
        activeTgSessionId = record.session_id;
        telegramChatData = record;
        renderTelegramResults(record);
        showToast(`Loaded "${record.chat_title}" into viewer!`, "success");
    } catch (err) {
        showToast("Could not load history record: " + err.message, "error");
    }
};

window.copyTgHistoryJson = function(idx) {
    const el = document.getElementById(`tgHistJson-${idx}`);
    if (el) {
        navigator.clipboard.writeText(el.textContent);
        showToast("History JSON copied!", "success");
    }
};

window.downloadTgHistoryJson = function(idx) {
    const el = document.getElementById(`tgHistJson-${idx}`);
    if (el) {
        const record = JSON.parse(el.textContent);
        const fileName = (record.chat_title ? record.chat_title.replace(/[^\w-]/g, "_") : "telegram") + "_history.json";
        downloadTextFile(fileName, el.textContent);
        showToast(`Downloaded ${fileName}`, "info");
    }
};

// =============================================================================
// Database Converter Service Logic
// =============================================================================
function setupDatabaseEventListeners() {
    btnPickDbFile.addEventListener("click", (e) => {
        e.stopPropagation();
        dbFileInput.value = "";
        dbFileInput.click();
    });

    dbFileInput.addEventListener("change", (e) => handleDbFileSelection(e.target.files));

    // Database Drag & Drop
    dbDropZone.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("input")) return;
        dbFileInput.value = "";
        dbFileInput.click();
    });

    dbDropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dbDropZone.classList.add("dragover");
    });

    dbDropZone.addEventListener("dragleave", () => {
        dbDropZone.classList.remove("dragover");
    });

    dbDropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dbDropZone.classList.remove("dragover");
        if (e.dataTransfer.files && e.dataTransfer.files.length) {
            handleDbFileSelection(e.dataTransfer.files);
        }
    });

    btnRemoveDbFile.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedDbFile = null;
        dbFileInput.value = "";
        dbSelectedFileContainer.classList.add("hidden");
        btnConvertDatabase.disabled = true;
    });

    btnConvertDatabase.addEventListener("click", convertDatabaseExport);

    // Search and Page controls
    dbSearchInput.addEventListener("input", (e) => {
        dbSearchQuery = (e.target.value || "").trim().toLowerCase();
        dbCurrentPage = 1;
        renderActiveTable();
    });

    dbPageSizeSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        dbPageSize = val === "all" ? "all" : parseInt(val, 10);
        dbCurrentPage = 1;
        renderActiveTable();
    });

    btnDbPrevPage.addEventListener("click", () => {
        if (dbCurrentPage > 1) {
            dbCurrentPage--;
            renderActiveTable();
        }
    });

    btnDbNextPage.addEventListener("click", () => {
        dbCurrentPage++;
        renderActiveTable();
    });

    // JSON export buttons
    btnCopyTableJSON.addEventListener("click", () => {
        if (databaseData && activeTableName && databaseData.tables[activeTableName]) {
            const rows = databaseData.tables[activeTableName].rows;
            navigator.clipboard.writeText(JSON.stringify(rows, null, 2));
            showToast(`Copied ${rows.length} rows from "${activeTableName}"!`, "success");
        }
    });

    btnDownloadTableJSON.addEventListener("click", () => {
        if (databaseData && activeTableName && databaseData.tables[activeTableName]) {
            const tableData = databaseData.tables[activeTableName];
            downloadTextFile(`${activeTableName}.json`, JSON.stringify(tableData, null, 2));
            showToast(`Downloaded ${activeTableName}.json`, "info");
        }
    });

    btnCopyDbJSON.addEventListener("click", () => {
        if (databaseData) {
            navigator.clipboard.writeText(JSON.stringify(databaseData, null, 2));
            showToast("Complete database JSON copied to clipboard!", "success");
        }
    });

    btnDownloadDbJSON.addEventListener("click", () => {
        if (databaseData) {
            const dbNameStr = databaseData.database_name || "database";
            downloadTextFile(`${dbNameStr}.json`, JSON.stringify(databaseData, null, 2));
            showToast(`Downloaded ${dbNameStr}.json`, "info");
        }
    });

    btnToggleDbRawJSON.addEventListener("click", () => {
        dbRawJsonBox.classList.toggle("hidden");
    });

    btnRefreshDbHistory.addEventListener("click", loadDbHistory);
}

function handleDbFileSelection(files) {
    if (!files || !files.length) return;
    const file = files[0];
    const ext = "." + file.name.split(".").pop().toLowerCase();

    if (!SUPPORTED_DB_EXTS.includes(ext)) {
        showToast(`Unsupported format "${ext}". Supported: ${SUPPORTED_DB_EXTS.join(", ")}`, "warning");
        return;
    }

    selectedDbFile = file;
    dbSelectedFileName.textContent = file.name;
    dbSelectedFileSize.textContent = `(${formatFileSize(file.size)})`;
    dbSelectedFileContainer.classList.remove("hidden");
    btnConvertDatabase.disabled = false;
    showToast(`Loaded database export: ${file.name}`, "info");
}

async function convertDatabaseExport() {
    if (!selectedDbFile) {
        showToast("Please choose a database export file first.", "warning");
        return;
    }

    const formData = new FormData();
    formData.append("file", selectedDbFile);

    btnConvertDatabase.disabled = true;
    dbLoadingSection.classList.remove("hidden");
    dbResultsSection.classList.add("hidden");

    try {
        const response = await fetch("/api/database/convert", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || errData.message || `Server error (${response.status})`);
        }

        const data = await response.json();
        databaseData = data;
        renderDatabaseResults(data);
        showToast(`Successfully converted ${data.total_tables} table(s) and ${data.total_rows} row(s)!`, "success");
    } catch (err) {
        console.error("Database conversion error:", err);
        showToast(err.message || "Failed to parse database export file", "error");
    } finally {
        btnConvertDatabase.disabled = false;
        dbLoadingSection.classList.add("hidden");
    }
}

function renderDatabaseResults(data) {
    dbResultsSection.classList.remove("hidden");

    // Overview Stats
    dbName.textContent = data.database_name || "database";
    dbSource.textContent = `Source: ${selectedDbFile ? selectedDbFile.name : data.export_source || "export"}`;
    dbFormatBadge.textContent = (data.format || "db").toUpperCase();
    dbStatTables.textContent = data.total_tables || 0;
    dbStatRows.textContent = data.total_rows || 0;

    // Raw JSON Content
    dbRawJsonContent.textContent = JSON.stringify(data, null, 2);

    // Build Table Tabs
    dbTableTabsContainer.innerHTML = "";
    const tableKeys = Object.keys(data.tables || {});

    if (tableKeys.length === 0) {
        dbTableContainer.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">No tables found in this database.</div>`;
        return;
    }

    tableKeys.forEach((tblName, idx) => {
        const tbl = data.tables[tblName];
        const tabBtn = document.createElement("button");
        tabBtn.type = "button";
        tabBtn.className = `db-tab-btn flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition border ${
            idx === 0
                ? 'bg-cyan-600/30 text-cyan-300 border-cyan-500/50 shadow-sm'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 border-slate-800'
        }`;
        tabBtn.innerHTML = `
            <span>${escapeHtml(tblName)}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 font-mono text-slate-300 border border-slate-700">${tbl.row_count}</span>
        `;
        tabBtn.addEventListener("click", () => {
            document.querySelectorAll(".db-tab-btn").forEach(b => {
                b.className = "db-tab-btn flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition border bg-slate-900/80 text-slate-400 hover:text-slate-200 border-slate-800";
            });
            tabBtn.className = "db-tab-btn flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition border bg-cyan-600/30 text-cyan-300 border-cyan-500/50 shadow-sm";
            activeTableName = tblName;
            dbSearchQuery = "";
            dbSearchInput.value = "";
            dbCurrentPage = 1;
            renderActiveTable();
        });
        dbTableTabsContainer.appendChild(tabBtn);
    });

    // Default to first table
    activeTableName = tableKeys[0];
    dbSearchQuery = "";
    dbSearchInput.value = "";
    dbCurrentPage = 1;
    renderActiveTable();

    dbResultsSection.scrollIntoView({ behavior: "smooth" });
}

function renderActiveTable() {
    if (!databaseData || !activeTableName || !databaseData.tables[activeTableName]) {
        dbTableContainer.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">No active table selected.</div>`;
        return;
    }

    const tableObj = databaseData.tables[activeTableName];
    dbActiveTableName.textContent = tableObj.table_name;
    dbActiveTableRowCount.textContent = `${tableObj.row_count} total row(s)`;

    // Filter rows
    let filteredRows = tableObj.rows || [];
    if (dbSearchQuery) {
        filteredRows = filteredRows.filter(row => {
            return Object.values(row).some(val => {
                if (val === null || val === undefined) return false;
                return String(val).toLowerCase().includes(dbSearchQuery);
            });
        });
    }

    const totalFiltered = filteredRows.length;

    // Pagination
    let pageRows = filteredRows;
    let maxPage = 1;
    let startIdx = 0;
    let endIdx = totalFiltered;

    if (dbPageSize !== "all" && totalFiltered > 0) {
        maxPage = Math.max(1, Math.ceil(totalFiltered / dbPageSize));
        if (dbCurrentPage > maxPage) dbCurrentPage = maxPage;
        if (dbCurrentPage < 1) dbCurrentPage = 1;
        startIdx = (dbCurrentPage - 1) * dbPageSize;
        endIdx = Math.min(startIdx + dbPageSize, totalFiltered);
        pageRows = filteredRows.slice(startIdx, endIdx);
    }

    // Update pagination controls
    if (totalFiltered === 0) {
        dbPaginationInfo.textContent = "Showing 0 rows";
        dbPageIndicator.textContent = "0 / 0";
        btnDbPrevPage.disabled = true;
        btnDbNextPage.disabled = true;
    } else {
        dbPaginationInfo.textContent = `Showing rows ${startIdx + 1} - ${endIdx} of ${totalFiltered} ${totalFiltered !== tableObj.row_count ? `(filtered from ${tableObj.row_count})` : ''}`;
        dbPageIndicator.textContent = `${dbCurrentPage} / ${maxPage}`;
        btnDbPrevPage.disabled = (dbCurrentPage <= 1);
        btnDbNextPage.disabled = (dbCurrentPage >= maxPage);
    }

    // Generate columns
    const columns = tableObj.columns && tableObj.columns.length > 0
        ? tableObj.columns
        : (tableObj.rows[0] ? Object.keys(tableObj.rows[0]).map(k => ({ name: k, type: "TEXT", primary_key: false })) : []);

    if (columns.length === 0 || totalFiltered === 0) {
        dbTableContainer.innerHTML = `
            <div class="p-8 text-center text-xs text-slate-500">
                ${totalFiltered === 0 && tableObj.row_count > 0 ? 'No rows match your search query.' : 'Table is empty.'}
            </div>
        `;
        return;
    }

    let html = `
        <table class="w-full text-left text-xs border-collapse">
            <thead class="bg-slate-900/90 border-b border-slate-800 text-[11px] font-mono text-slate-400 sticky top-0 z-10">
                <tr>
                    <th class="p-3 w-12 text-center text-slate-600 border-r border-slate-800/80">#</th>
    `;

    columns.forEach(col => {
        html += `
            <th class="p-3 font-semibold text-slate-200 border-r border-slate-800/60 whitespace-nowrap">
                <div class="flex items-center gap-1.5">
                    <span>${escapeHtml(col.name)}</span>
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700 uppercase">${escapeHtml(col.type || 'TEXT')}</span>
                    ${col.primary_key ? `<span class="text-[9px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">PK</span>` : ''}
                </div>
            </th>
        `;
    });

    html += `
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60 text-slate-300 font-mono">
    `;

    pageRows.forEach((row, i) => {
        const rowNum = startIdx + i + 1;
        html += `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="p-2.5 text-center text-slate-600 border-r border-slate-800/60 select-none">${rowNum}</td>
        `;

        columns.forEach(col => {
            const rawVal = row[col.name];
            let cellContent = "";

            if (rawVal === null || rawVal === undefined) {
                cellContent = `<span class="text-slate-600 italic">NULL</span>`;
            } else if (typeof rawVal === "boolean") {
                cellContent = rawVal
                    ? `<span class="text-emerald-400 font-bold">TRUE</span>`
                    : `<span class="text-rose-400 font-bold">FALSE</span>`;
            } else if (typeof rawVal === "number") {
                cellContent = `<span class="text-amber-300">${rawVal}</span>`;
            } else {
                cellContent = `<span class="text-slate-200 whitespace-pre-wrap">${escapeHtml(String(rawVal))}</span>`;
            }

            html += `<td class="p-2.5 border-r border-slate-800/60 max-w-xs truncate" title="${escapeHtml(String(rawVal || ''))}">${cellContent}</td>`;
        });

        html += `</tr>`;
    });

    html += `
            </tbody>
        </table>
    `;

    dbTableContainer.innerHTML = html;
}

// =============================================================================
// Database History Operations
// =============================================================================
async function loadDbHistory() {
    dbHistoryListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">Fetching Database conversion logs...</p>`;
    try {
        const res = await fetch("/api/database/history");
        if (!res.ok) throw new Error("Failed to load Database history");
        const logs = await res.json();

        if (!logs.length) {
            dbHistoryListContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No previous database conversions found in logs/database_parser_log.jsonl.</p>`;
            return;
        }

        dbHistoryListContainer.innerHTML = "";
        logs.forEach((logEntry, index) => {
            const item = document.createElement("div");
            item.className = "bg-slate-900/80 rounded-xl p-4 border border-slate-800 flex flex-col gap-2";

            const timestamp = logEntry.timestamp || "Unknown time";
            const title = logEntry.database_name || "Database";
            const fmt = (logEntry.format || "db").toUpperCase();
            const totalTables = logEntry.total_tables || 0;
            const totalRows = logEntry.total_rows || 0;

            item.innerHTML = `
                <div class="flex items-center justify-between cursor-pointer" onclick="toggleDbHistoryItem(${index})">
                    <div class="flex items-center gap-2.5 flex-wrap">
                        <span class="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
                        <span class="text-xs font-bold text-white">${escapeHtml(title)}</span>
                        <span class="text-xs font-mono text-slate-400">${escapeHtml(timestamp)}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono">${fmt}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">${totalTables} table(s)</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">${totalRows} rows</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-cyan-400 hover:underline">View</span>
                        <i data-lucide="chevron-down" id="dbHistChevron-${index}" class="w-4 h-4 text-slate-400 transition-transform"></i>
                    </div>
                </div>

                <div id="dbHistContent-${index}" class="hidden mt-3 pt-3 border-t border-slate-800 flex flex-col gap-3">
                    <div class="flex items-center justify-between flex-wrap gap-2 text-xs">
                        <span class="text-slate-400 font-mono text-[11px]">Source: ${escapeHtml(logEntry.export_source || 'database')}</span>
                        <div class="flex items-center gap-2">
                            <button class="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-medium transition flex items-center gap-1 text-xs" onclick="reloadDbHistoryToViewer(${index})">
                                <i data-lucide="external-link" class="w-3.5 h-3.5"></i> Load in Viewer
                            </button>
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition flex items-center gap-1 text-xs" onclick="copyDbHistoryJson(${index})">
                                <i data-lucide="copy" class="w-3.5 h-3.5"></i> Copy JSON
                            </button>
                            <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition flex items-center gap-1 text-xs" onclick="downloadDbHistoryJson(${index})">
                                <i data-lucide="download" class="w-3.5 h-3.5"></i> Download
                            </button>
                        </div>
                    </div>

                    <pre id="dbHistJson-${index}" class="hidden">${JSON.stringify(logEntry.data || logEntry, null, 2)}</pre>
                </div>
            `;
            dbHistoryListContainer.appendChild(item);
        });

        lucide.createIcons();
    } catch (err) {
        dbHistoryListContainer.innerHTML = `<p class="text-xs text-rose-400 text-center py-6">Could not load Database history: ${err.message}</p>`;
    }
}

window.toggleDbHistoryItem = function(idx) {
    const content = document.getElementById(`dbHistContent-${idx}`);
    const chevron = document.getElementById(`dbHistChevron-${idx}`);
    if (content) {
        content.classList.toggle("hidden");
        if (chevron) {
            chevron.classList.toggle("rotate-180");
        }
    }
};

window.reloadDbHistoryToViewer = async function(idx) {
    const el = document.getElementById(`dbHistJson-${idx}`);
    if (!el) return;
    try {
        const fullData = JSON.parse(el.textContent);
        databaseData = fullData;
        renderDatabaseResults(fullData);
        showToast(`Loaded "${fullData.database_name || 'database'}" into table viewer!`, "success");
    } catch (err) {
        showToast("Could not load history record: " + err.message, "error");
    }
};

window.copyDbHistoryJson = function(idx) {
    const el = document.getElementById(`dbHistJson-${idx}`);
    if (el) {
        navigator.clipboard.writeText(el.textContent);
        showToast("Database history JSON copied!", "success");
    }
};

window.downloadDbHistoryJson = function(idx) {
    const el = document.getElementById(`dbHistJson-${idx}`);
    if (el) {
        const fullData = JSON.parse(el.textContent);
        const fileName = (fullData.database_name ? fullData.database_name.replace(/[^\w-]/g, "_") : "database") + "_history.json";
        downloadTextFile(fileName, el.textContent);
        showToast(`Downloaded ${fileName}`, "info");
    }
};

// =============================================================================
// SERVICE 4: YouTube Channel Data to JSON Logic
// =============================================================================
function setupYouTubeEventListeners() {
    const ytQueryInput = document.getElementById("ytQueryInput");
    const btnFetchYouTube = document.getElementById("btnFetchYouTube");
    const btnLoadYtSample = document.getElementById("btnLoadYtSample");

    const ytDropZone = document.getElementById("ytDropZone");
    const ytFileInput = document.getElementById("ytFileInput");
    const btnPickYtFile = document.getElementById("btnPickYtFile");
    const btnRemoveYtFile = document.getElementById("btnRemoveYtFile");

    // Fetch Query
    btnFetchYouTube?.addEventListener("click", () => {
        const q = ytQueryInput.value.trim();
        if (selectedYtFile) {
            fetchYouTubeChannel(null, selectedYtFile);
        } else if (q) {
            fetchYouTubeChannel(q);
        } else {
            showToast("Please enter a YouTube channel handle/URL or select a file.", "warning");
        }
    });

    ytQueryInput?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            btnFetchYouTube.click();
        }
    });

    // Sample Load
    btnLoadYtSample?.addEventListener("click", loadYouTubeSample);

    // File pick
    btnPickYtFile?.addEventListener("click", (e) => {
        e.stopPropagation();
        ytFileInput.click();
    });

    ytFileInput?.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleYtFileSelect(e.target.files[0]);
        }
    });

    // Dropzone
    ytDropZone?.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("input")) return;
        ytFileInput.click();
    });

    ytDropZone?.addEventListener("dragover", (e) => {
        e.preventDefault();
        ytDropZone.classList.add("dragover");
    });

    ytDropZone?.addEventListener("dragleave", (e) => {
        e.preventDefault();
        ytDropZone.classList.remove("dragover");
    });

    ytDropZone?.addEventListener("drop", (e) => {
        e.preventDefault();
        ytDropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleYtFileSelect(e.dataTransfer.files[0]);
        }
    });

    btnRemoveYtFile?.addEventListener("click", () => {
        selectedYtFile = null;
        ytFileInput.value = "";
        document.getElementById("ytSelectedFileContainer").classList.add("hidden");
    });

    // Toolbar controls
    document.getElementById("ytSearchInput")?.addEventListener("input", (e) => {
        ytSearchQuery = e.target.value.trim();
        ytCurrentPage = 1;
        renderYouTubeVideos();
    });

    document.getElementById("ytSortSelect")?.addEventListener("change", (e) => {
        ytSortBy = e.target.value;
        ytCurrentPage = 1;
        renderYouTubeVideos();
    });

    document.getElementById("btnYtViewGrid")?.addEventListener("click", () => {
        ytViewMode = "grid";
        document.getElementById("btnYtViewGrid").className = "p-1.5 rounded text-white bg-slate-800 transition";
        document.getElementById("btnYtViewTable").className = "p-1.5 rounded text-slate-400 hover:text-slate-200 transition";
        document.getElementById("ytVideoGridContainer").classList.remove("hidden");
        document.getElementById("ytVideoTableContainer").classList.add("hidden");
        renderYouTubeVideos();
    });

    document.getElementById("btnYtViewTable")?.addEventListener("click", () => {
        ytViewMode = "table";
        document.getElementById("btnYtViewTable").className = "p-1.5 rounded text-white bg-slate-800 transition";
        document.getElementById("btnYtViewGrid").className = "p-1.5 rounded text-slate-400 hover:text-slate-200 transition";
        document.getElementById("ytVideoTableContainer").classList.remove("hidden");
        document.getElementById("ytVideoGridContainer").classList.add("hidden");
        renderYouTubeVideos();
    });

    // Description toggle
    document.getElementById("btnToggleYtDesc")?.addEventListener("click", () => {
        const text = document.getElementById("ytDescriptionText");
        const btn = document.getElementById("btnToggleYtDesc");
        if (text.classList.contains("line-clamp-3")) {
            text.classList.remove("line-clamp-3");
            btn.textContent = "Show less";
        } else {
            text.classList.add("line-clamp-3");
            btn.textContent = "Show more";
        }
    });

    // Copy & Download
    document.getElementById("btnCopyYtJSON")?.addEventListener("click", () => {
        if (!youtubeChannelData) return;
        navigator.clipboard.writeText(JSON.stringify(youtubeChannelData, null, 2));
        showToast("YouTube channel JSON copied to clipboard!", "success");
    });

    document.getElementById("btnDownloadYtJSON")?.addEventListener("click", () => {
        if (!youtubeChannelData) return;
        const handle = youtubeChannelData.channel_info?.handle || "youtube_channel";
        const fname = `${handle.replace(/[^\w-]/g, "_")}.json`;
        downloadTextFile(fname, JSON.stringify(youtubeChannelData, null, 2));
        showToast(`Downloaded ${fname}`, "info");
    });

    // Raw JSON Toggle
    document.getElementById("btnToggleYtRawJSON")?.addEventListener("click", () => {
        const box = document.getElementById("ytRawJsonBox");
        box.classList.toggle("hidden");
    });

    document.getElementById("btnCopyRawYtJSON")?.addEventListener("click", () => {
        const pre = document.getElementById("ytRawJsonContent");
        navigator.clipboard.writeText(pre.textContent);
        showToast("Raw JSON copied to clipboard!", "success");
    });

    // Pagination
    document.getElementById("btnYtPrevPage")?.addEventListener("click", () => {
        if (ytCurrentPage > 1) {
            ytCurrentPage--;
            renderYouTubeVideos();
        }
    });

    document.getElementById("btnYtNextPage")?.addEventListener("click", () => {
        const total = getFilteredAndSortedVideos().length;
        const maxPage = Math.ceil(total / ytPageSize);
        if (ytCurrentPage < maxPage) {
            ytCurrentPage++;
            renderYouTubeVideos();
        }
    });

    document.getElementById("btnRefreshYtHistory")?.addEventListener("click", loadYtHistory);
}

function handleYtFileSelect(file) {
    selectedYtFile = file;
    const nameEl = document.getElementById("ytSelectedFileName");
    const sizeEl = document.getElementById("ytSelectedFileSize");
    const cont = document.getElementById("ytSelectedFileContainer");
    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `(${formatFileSize(file.size)})`;
    if (cont) cont.classList.remove("hidden");
    showToast(`Loaded file: ${file.name}. Click "Fetch Channel" to process.`, "info");
}

async function fetchYouTubeChannel(query, file = null) {
    const loading = document.getElementById("ytLoadingSection");
    const results = document.getElementById("ytResultsSection");
    loading.classList.remove("hidden");
    results.classList.add("hidden");

    try {
        const formData = new FormData();
        if (file) {
            formData.append("file", file);
        } else if (query) {
            formData.append("query", query);
        }

        const res = await fetch("/api/youtube/fetch", {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ message: res.statusText }));
            throw new Error(err.message || `Server returned ${res.status}`);
        }

        const data = await res.json();
        youtubeChannelData = data;
        renderYouTubeResults();
        showToast(`Successfully extracted channel: ${data.channel_info?.channel_name || 'Channel'}`, "success");
    } catch (err) {
        showToast(`Error: ${err.message}`, "error");
    } finally {
        loading.classList.add("hidden");
    }
}

async function loadYouTubeSample() {
    const loading = document.getElementById("ytLoadingSection");
    const results = document.getElementById("ytResultsSection");
    loading.classList.remove("hidden");
    results.classList.add("hidden");

    try {
        const res = await fetch("/api/youtube/sample", { method: "POST" });
        if (!res.ok) {
            throw new Error("Failed to load sample channel");
        }
        const data = await res.json();
        youtubeChannelData = data;
        renderYouTubeResults();
        showToast("Loaded sample YouTube channel dataset!", "success");
    } catch (err) {
        showToast(`Error: ${err.message}`, "error");
    } finally {
        loading.classList.add("hidden");
    }
}

function renderYouTubeResults() {
    if (!youtubeChannelData) return;
    const info = youtubeChannelData.channel_info || {};
    const results = document.getElementById("ytResultsSection");
    results.classList.remove("hidden");

    // Banner
    const bannerEl = document.getElementById("ytHeroBanner");
    if (info.banner_url) {
        bannerEl.style.backgroundImage = `url('${info.banner_url}')`;
    } else {
        bannerEl.style.backgroundImage = "linear-gradient(135deg, #1e1b4b 0%, #311042 100%)";
    }

    // Avatar
    const avatarEl = document.getElementById("ytAvatarImg");
    avatarEl.src = info.avatar_url || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150";

    // Channel Name & Handle
    document.getElementById("ytChannelName").textContent = info.channel_name || "Unknown Channel";
    document.getElementById("ytChannelHandle").textContent = info.handle || "";

    // Verified badge
    const badgeEl = document.getElementById("ytVerifiedBadge");
    if (info.is_verified) {
        badgeEl.classList.remove("hidden");
        badgeEl.classList.add("flex");
    } else {
        badgeEl.classList.add("hidden");
        badgeEl.classList.remove("flex");
    }

    // Stats
    document.getElementById("ytStatSubscribers").textContent = info.subscriber_count_text || (info.subscriber_count ? info.subscriber_count.toLocaleString() : "N/A");
    document.getElementById("ytStatVideos").textContent = youtubeChannelData.total_videos || (info.total_videos_text || "0");
    document.getElementById("ytCatalogBadge").textContent = `${youtubeChannelData.total_videos || 0} videos`;

    // External link
    const linkEl = document.getElementById("ytExternalLink");
    if (info.custom_url) {
        linkEl.href = info.custom_url;
        linkEl.classList.remove("hidden");
    } else {
        linkEl.classList.add("hidden");
    }

    // Description
    const descText = document.getElementById("ytDescriptionText");
    const descContainer = document.getElementById("ytDescContainer");
    if (info.description) {
        descText.textContent = info.description;
        descContainer.classList.remove("hidden");
    } else {
        descContainer.classList.add("hidden");
    }

    // Raw JSON
    const rawPre = document.getElementById("ytRawJsonContent");
    if (rawPre) {
        rawPre.textContent = JSON.stringify(youtubeChannelData, null, 2);
    }

    ytCurrentPage = 1;
    renderYouTubeVideos();
    lucide.createIcons();
    results.scrollIntoView({ behavior: "smooth" });
}

function getFilteredAndSortedVideos() {
    if (!youtubeChannelData || !youtubeChannelData.videos) return [];
    let list = [...youtubeChannelData.videos];

    // Filter
    if (ytSearchQuery) {
        const q = ytSearchQuery.toLowerCase();
        list = list.filter(v => v.title && v.title.toLowerCase().includes(q));
    }

    // Sort
    if (ytSortBy === "views") {
        list.sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
    } else if (ytSortBy === "duration") {
        list.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
    }

    return list;
}

function renderYouTubeVideos() {
    const allFiltered = getFilteredAndSortedVideos();
    const total = allFiltered.length;
    const maxPage = Math.max(1, Math.ceil(total / ytPageSize));
    if (ytCurrentPage > maxPage) ytCurrentPage = maxPage;

    const startIdx = (ytCurrentPage - 1) * ytPageSize;
    const pageItems = allFiltered.slice(startIdx, startIdx + ytPageSize);

    // Update pagination info
    const infoEl = document.getElementById("ytPaginationInfo");
    const indicatorEl = document.getElementById("ytPageIndicator");
    const btnPrev = document.getElementById("btnYtPrevPage");
    const btnNext = document.getElementById("btnYtNextPage");

    if (infoEl) infoEl.textContent = total > 0 ? `Showing ${startIdx + 1} - ${Math.min(startIdx + ytPageSize, total)} of ${total} videos` : "No videos match search";
    if (indicatorEl) indicatorEl.textContent = `${ytCurrentPage} / ${maxPage}`;
    if (btnPrev) btnPrev.disabled = ytCurrentPage <= 1;
    if (btnNext) btnNext.disabled = ytCurrentPage >= maxPage;

    // Render Cards Grid
    const gridContainer = document.getElementById("ytVideoGridContainer");
    if (gridContainer && ytViewMode === "grid") {
        if (pageItems.length === 0) {
            gridContainer.innerHTML = `<div class="col-span-full py-12 text-center text-xs text-slate-500">No videos found matching "${escapeHtml(ytSearchQuery)}"</div>`;
        } else {
            gridContainer.innerHTML = pageItems.map((v) => {
                const thumb = v.thumbnail_url || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500";
                const isShort = v.is_short;
                const durationPill = v.duration_text ? `<span class="yt-duration-badge absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-[11px] font-mono text-white font-medium">${v.duration_text}</span>` : "";
                const shortBadge = isShort ? `<span class="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-red-600/90 text-white text-[10px] font-bold uppercase tracking-wider">#Shorts</span>` : "";

                return `
                <div class="yt-video-card glass-panel rounded-xl overflow-hidden border border-slate-800 flex flex-col group">
                    <div class="relative aspect-video bg-slate-900 overflow-hidden">
                        <img src="${thumb}" alt="${escapeHtml(v.title)}" class="w-full h-full object-cover group-hover:scale-105 transition duration-300">
                        ${durationPill}
                        ${shortBadge}
                    </div>
                    <div class="p-3.5 flex-1 flex flex-col justify-between gap-2.5">
                        <div>
                            <a href="${v.url}" target="_blank" rel="noopener noreferrer" class="text-xs font-semibold text-slate-100 hover:text-red-400 line-clamp-2 leading-snug transition" title="${escapeHtml(v.title)}">
                                ${escapeHtml(v.title)}
                            </a>
                        </div>
                        <div class="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/80">
                            <div class="flex items-center gap-1.5">
                                <span>${v.view_count_text || (v.view_count ? v.view_count.toLocaleString() + ' views' : '0 views')}</span>
                                ${v.published_time_text ? `<span class="text-slate-600">&bull;</span><span>${v.published_time_text}</span>` : ''}
                            </div>
                            <button onclick="copySingleVideoJson('${v.video_id}')" class="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition" title="Copy video JSON">
                                <i data-lucide="copy" class="w-3 h-3"></i>
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join("");
        }
    }

    // Render Table View
    const tableContainer = document.getElementById("ytVideoTableContainer");
    if (tableContainer && ytViewMode === "table") {
        if (pageItems.length === 0) {
            tableContainer.innerHTML = `<div class="py-12 text-center text-xs text-slate-500">No videos found matching "${escapeHtml(ytSearchQuery)}"</div>`;
        } else {
            tableContainer.innerHTML = `
            <table class="w-full text-left text-xs border-collapse">
                <thead class="bg-slate-900 text-slate-400 font-mono text-[11px] sticky top-0 z-10 border-b border-slate-800">
                    <tr>
                        <th class="py-2.5 px-3 w-12">#</th>
                        <th class="py-2.5 px-3">Video Title</th>
                        <th class="py-2.5 px-3">Views</th>
                        <th class="py-2.5 px-3">Duration</th>
                        <th class="py-2.5 px-3">Published</th>
                        <th class="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60 font-sans">
                    ${pageItems.map((v, i) => `
                        <tr class="hover:bg-slate-900/50 transition">
                            <td class="py-2 px-3 text-slate-500 font-mono">${startIdx + i + 1}</td>
                            <td class="py-2 px-3">
                                <a href="${v.url}" target="_blank" rel="noopener noreferrer" class="font-medium text-slate-200 hover:text-red-400 transition">
                                    ${escapeHtml(v.title)}
                                </a>
                                ${v.is_short ? '<span class="ml-1 text-[10px] px-1 py-0.2 rounded bg-red-600/20 text-red-400 border border-red-500/30">#Short</span>' : ''}
                            </td>
                            <td class="py-2 px-3 font-mono text-slate-300">${v.view_count_text || (v.view_count ? v.view_count.toLocaleString() : '-')}</td>
                            <td class="py-2 px-3 font-mono text-slate-300">${v.duration_text || '-'}</td>
                            <td class="py-2 px-3 text-slate-400">${v.published_time_text || '-'}</td>
                            <td class="py-2 px-3 text-right">
                                <button onclick="copySingleVideoJson('${v.video_id}')" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono transition">
                                    Copy
                                </button>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
            `;
        }
    }

    lucide.createIcons();
}

window.copySingleVideoJson = function(videoId) {
    if (!youtubeChannelData || !youtubeChannelData.videos) return;
    const v = youtubeChannelData.videos.find(x => x.video_id === videoId);
    if (v) {
        navigator.clipboard.writeText(JSON.stringify(v, null, 2));
        showToast(`Copied JSON for: "${v.title}"`, "success");
    }
};

// --- YouTube History ---
async function loadYtHistory() {
    const container = document.getElementById("ytHistoryListContainer");
    if (!container) return;
    container.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">Loading YouTube conversion history...</p>`;

    try {
        const res = await fetch("/api/youtube/history?limit=30");
        if (!res.ok) throw new Error("Failed to load history");
        const list = await res.json();

        if (list.length === 0) {
            container.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No YouTube conversion history found.</p>`;
            return;
        }

        container.innerHTML = list.map((item, idx) => {
            const time = item.timestamp ? new Date(item.timestamp).toLocaleString() : "";
            const chName = escapeHtml(item.channel_name || "Unknown Channel");
            const handle = escapeHtml(item.handle || "");
            const subs = escapeHtml(item.subscriber_count_text || "");
            const total = item.total_videos || 0;
            const fullJson = escapeHtml(JSON.stringify(item.data || item, null, 2));

            return `
            <div class="p-4 bg-slate-900/60 rounded-xl border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 flex-shrink-0">
                        <i data-lucide="youtube" class="w-5 h-5"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h4 class="text-xs font-bold text-slate-100">${chName}</h4>
                            <span class="text-[11px] text-slate-400 font-mono">${handle}</span>
                        </div>
                        <p class="text-[11px] text-slate-500 mt-0.5">${time} &bull; ${subs} &bull; ${total} videos</p>
                    </div>
                </div>

                <div class="flex items-center gap-2 flex-wrap">
                    <button onclick="reloadYtHistorySession(${idx})" class="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 flex items-center gap-1 transition">
                        <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                        <span>Load in Viewer</span>
                    </button>
                    <button onclick="copyYtHistoryJson(${idx})" class="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1 transition">
                        <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                        <span>Copy</span>
                    </button>
                    <button onclick="downloadYtHistoryJson(${idx})" class="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1 transition">
                        <i data-lucide="download" class="w-3.5 h-3.5"></i>
                        <span>Download</span>
                    </button>
                </div>
                <pre id="ytHistJson-${idx}" class="hidden">${fullJson}</pre>
            </div>
            `;
        }).join("");

        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<p class="text-xs text-rose-400 text-center py-6">Error loading history: ${err.message}</p>`;
    }
}

window.reloadYtHistorySession = function(idx) {
    const el = document.getElementById(`ytHistJson-${idx}`);
    if (el) {
        youtubeChannelData = JSON.parse(el.textContent);
        renderYouTubeResults();
        showToast("Reloaded channel in viewer!", "success");
    }
};

window.copyYtHistoryJson = function(idx) {
    const el = document.getElementById(`ytHistJson-${idx}`);
    if (el) {
        navigator.clipboard.writeText(el.textContent);
        showToast("YouTube history JSON copied!", "success");
    }
};

window.downloadYtHistoryJson = function(idx) {
    const el = document.getElementById(`ytHistJson-${idx}`);
    if (el) {
        const fullData = JSON.parse(el.textContent);
        const name = fullData.channel_info?.handle || "youtube_channel";
        const fname = `${name.replace(/[^\w-]/g, "_")}_history.json`;
        downloadTextFile(fname, el.textContent);
        showToast(`Downloaded ${fname}`, "info");
    }
};

// =============================================================================
// Global Modals & Utilities
// =============================================================================
window.openImageModal = function(url) {
    if (!url) return;
    const modal = document.getElementById("imageModal");
    const img = document.getElementById("modalImage");
    img.src = url;
    modal.classList.remove("hidden");
};

window.closeImageModal = function() {
    const modal = document.getElementById("imageModal");
    modal.classList.add("hidden");
};

function formatTime(isoString) {
    if (!isoString) return "";
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return isoString;
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return isoString;
    }
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    const colorClasses = {
        success: "bg-emerald-600 text-white border-emerald-500",
        error: "bg-rose-600 text-white border-rose-500",
        warning: "bg-amber-600 text-white border-amber-500",
        info: "bg-slate-800 text-slate-100 border-slate-700",
    }[type] || "bg-slate-800 text-slate-100 border-slate-700";

    toast.className = `toast-animate px-4 py-2.5 rounded-xl shadow-2xl border text-xs font-medium flex items-center gap-2 pointer-events-auto transition ${colorClasses}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translate(-50%, -10px)";
        setTimeout(() => toast.remove(), 250);
    }, 3200);
}
