/**
 * DuckLake Medallion UI controller (isolated from app.js).
 * Uses textContent DOM construction to prevent XSS from ingested payloads.
 */

(function () {
    let _initialized = false;
    let _martOffset = 0;
    const _martLimit = 50;
    let _martTotal = 0;
    let _silverOffset = 0;
    const _silverLimit = 50;
    let _silverTotal = 0;

    function _setBadge(statusText) {
        const badge = document.getElementById("ducklakeStatusBadge");
        if (!badge) return;
        badge.textContent = statusText || "NOT RUN";
        badge.classList.remove("dl-badge-passed", "dl-badge-warn", "dl-badge-blocked");
        if (statusText === "PASSED") badge.classList.add("dl-badge-passed");
        else if (statusText === "BLOCKED") badge.classList.add("dl-badge-blocked");
        else badge.classList.add("dl-badge-warn");
    }

    function _renderTable(container, columns, rows, emptyMessage) {
        if (!container) return;
        container.replaceChildren();
        if (!rows || rows.length === 0) {
            const p = document.createElement("p");
            p.className = "text-xs text-slate-500 text-center py-8";
            p.textContent = emptyMessage;
            container.appendChild(p);
            return;
        }
        const table = document.createElement("table");
        table.className = "w-full text-left border-collapse text-xs";
        const thead = document.createElement("thead");
        thead.className = "bg-slate-950/90 text-slate-400 uppercase tracking-wider sticky top-0";
        const headRow = document.createElement("tr");
        columns.forEach(col => {
            const th = document.createElement("th");
            th.className = "px-4 py-2.5 border-b border-slate-800 font-semibold";
            th.textContent = col;
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach(row => {
            const tr = document.createElement("tr");
            tr.className = "border-b border-slate-800/60 hover:bg-slate-800/30";
            columns.forEach(col => {
                const td = document.createElement("td");
                td.className = "px-4 py-2 text-slate-200 font-mono whitespace-nowrap max-w-xs truncate";
                const val = row[col];
                td.textContent = val === null || val === undefined ? "NULL" : String(val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        container.appendChild(table);
    }

    function _renderLayerCards(counts) {
        const container = document.getElementById("ducklakeLayerCards");
        if (!container) return;
        container.replaceChildren();
        const sumDict = d => Object.values(d || {}).reduce((a, b) => a + Number(b || 0), 0);
        const cards = [
            { label: "Bronze Records", value: sumDict(counts.bronze_by_source) },
            { label: "Silver Entities", value: sumDict(counts.silver_by_entity) },
            { label: "Quarantined", value: sumDict(counts.quarantine_by_entity) },
            { label: "Gold Mart Rows", value: sumDict(counts.gold_by_mart) },
        ];
        cards.forEach(item => {
            const div = document.createElement("div");
            div.className = "bg-slate-950/70 border border-slate-800 rounded-2xl p-4";
            const lbl = document.createElement("div");
            lbl.className = "text-xs text-slate-400";
            lbl.textContent = item.label;
            const val = document.createElement("div");
            val.className = "text-2xl font-black text-white mt-1";
            val.textContent = String(item.value);
            div.appendChild(lbl);
            div.appendChild(val);
            container.appendChild(div);
        });
    }

    async function loadStatus() {
        const res = await fetch("/api/lakehouse/status");
        if (!res.ok) return;
        const data = await res.json();
        _renderLayerCards(data.layer_counts || {});
        if (data.latest_batch_id) {
            if (data.latest_status) {
                _setBadge(data.latest_status);
            } else {
                const qTotal = Object.values((data.layer_counts && data.layer_counts.quarantine_by_entity) || {}).reduce((a, b) => a + b, 0);
                _setBadge(qTotal > 0 ? "PASSED_WITH_QUARANTINE" : "PASSED");
            }
        } else {
            _setBadge("NOT RUN");
        }
    }

    async function loadMart() {
        const sel = document.getElementById("ducklakeMartSelect");
        const martName = sel ? sel.value : "gold_ingestion_overview";
        const res = await fetch(`/api/lakehouse/marts/${encodeURIComponent(martName)}?limit=${_martLimit}&offset=${_martOffset}`);
        if (!res.ok) return;
        const data = await res.json();
        _martTotal = data.total || 0;
        const info = document.getElementById("ducklakeMartPageInfo");
        if (info) info.textContent = `${data.total} rows (offset ${_martOffset})`;
        _renderTable(
            document.getElementById("ducklakeMartTable"),
            data.columns || [],
            data.rows || [],
            "No Gold Mart rows committed yet. Run an Ingestion Batch above."
        );
    }

    async function loadSilver() {
        const sel = document.getElementById("ducklakeSilverSelect");
        const entity = sel ? sel.value : "ocr_extractions";
        const res = await fetch(`/api/lakehouse/silver/${encodeURIComponent(entity)}?limit=${_silverLimit}&offset=${_silverOffset}`);
        if (!res.ok) return;
        const data = await res.json();
        _silverTotal = data.total || 0;
        const info = document.getElementById("ducklakeSilverPageInfo");
        if (info) info.textContent = `${data.total} rows (offset ${_silverOffset})`;
        _renderTable(
            document.getElementById("ducklakeSilverTable"),
            data.columns || [],
            data.rows || [],
            "No Silver rows committed yet. Run an Ingestion Batch above."
        );
    }

    async function loadQuarantine() {
        const sel = document.getElementById("ducklakeQuarantineEntity");
        const entity = sel ? sel.value : "";
        const qs = entity ? `?entity=${encodeURIComponent(entity)}&limit=50&offset=0` : "?limit=50&offset=0";
        const res = await fetch(`/api/lakehouse/quarantine${qs}`);
        if (!res.ok) return;
        const data = await res.json();
        const cols = data.rows && data.rows.length > 0 ? Object.keys(data.rows[0]) : [];
        _renderTable(
            document.getElementById("ducklakeQuarantineTable"),
            cols,
            data.rows || [],
            "No quarantined rows recorded."
        );
    }

    async function loadRunsHistory() {
        const container = document.getElementById("ducklakeHistoryList");
        if (!container) return;
        const res = await fetch("/api/lakehouse/runs?limit=20&offset=0");
        if (!res.ok) return;
        const runs = await res.json();
        container.replaceChildren();
        if (!runs.length) {
            const p = document.createElement("p");
            p.className = "text-xs text-slate-500 text-center py-4";
            p.textContent = "No Ingestion Batches recorded yet.";
            container.appendChild(p);
            return;
        }
        runs.forEach(run => {
            const row = document.createElement("div");
            row.className = "flex flex-wrap items-center justify-between gap-2 bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-2.5 text-xs";
            const left = document.createElement("span");
            left.className = "font-mono text-slate-200";
            left.textContent = `${run.batch_id} • ${run.overall_status}`;
            const right = document.createElement("span");
            right.className = "text-slate-400";
            right.textContent = `Quarantined: ${(run.quality && run.quality.total_quarantined) || 0}`;
            row.appendChild(left);
            row.appendChild(right);
            container.appendChild(row);
        });
    }

    async function triggerRun() {
        const btn = document.getElementById("ducklakeRunBtn");
        const fullRefresh = Boolean(document.getElementById("ducklakeFullRefreshCheck")?.checked);
        const exportDuckdb = Boolean(document.getElementById("ducklakeExportCheck")?.checked);
        if (btn) btn.disabled = true;
        try {
            const res = await fetch("/api/lakehouse/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ full_refresh: fullRefresh, export_duckdb: exportDuckdb }),
            });
            const data = await res.json();
            if (!res.ok) {
                if (typeof showToast === "function") showToast(data.detail || "Batch failed", "error");
                return;
            }
            _setBadge(data.overall_status);
            _renderLayerCards(data.layer_counts || {});
            _martOffset = 0;
            _silverOffset = 0;
            await Promise.all([loadMart(), loadSilver(), loadQuarantine(), loadRunsHistory()]);
            if (typeof showToast === "function") showToast(`Batch ${data.batch_id}: ${data.overall_status}`, "success");
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    window.initDuckLakeTab = function () {
        if (!_initialized) {
            _initialized = true;
            document.getElementById("ducklakeRunBtn")?.addEventListener("click", triggerRun);
            document.getElementById("ducklakeMartSelect")?.addEventListener("change", () => {
                _martOffset = 0;
                loadMart();
            });
            document.getElementById("ducklakeMartPrev")?.addEventListener("click", () => {
                _martOffset = Math.max(0, _martOffset - _martLimit);
                loadMart();
            });
            document.getElementById("ducklakeMartNext")?.addEventListener("click", () => {
                if (_martOffset + _martLimit < _martTotal) {
                    _martOffset += _martLimit;
                    loadMart();
                }
            });
            document.getElementById("ducklakeSilverSelect")?.addEventListener("change", () => {
                _silverOffset = 0;
                loadSilver();
            });
            document.getElementById("ducklakeSilverPrev")?.addEventListener("click", () => {
                _silverOffset = Math.max(0, _silverOffset - _silverLimit);
                loadSilver();
            });
            document.getElementById("ducklakeSilverNext")?.addEventListener("click", () => {
                if (_silverOffset + _silverLimit < _silverTotal) {
                    _silverOffset += _silverLimit;
                    loadSilver();
                }
            });
            document.getElementById("ducklakeQuarantineEntity")?.addEventListener("change", loadQuarantine);
            document.getElementById("btnRefreshDuckLakeHistory")?.addEventListener("click", loadRunsHistory);
        }
        loadStatus();
        loadMart();
        loadSilver();
        loadQuarantine();
    };

    window.toggleDuckLakeHistory = function () {
        loadRunsHistory();
    };
})();
