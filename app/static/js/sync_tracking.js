document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("sync-tracking-table");
    if (!table) return;

    // ---- page size + category dropdowns ----
    const STORAGE_KEY = "syncTrackingPageSizeV1";
    const url = new URL(window.location.href);

    if (!url.searchParams.has("size")) {
        let stored = null;
        try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
        if (stored) {
            url.searchParams.set("size", stored);
            window.location.href = url.toString();
            return;
        }
    } else {
        try { localStorage.setItem(STORAGE_KEY, url.searchParams.get("size")); } catch (e) {}
    }

    const pageSizeSelect = document.getElementById("page-size-select");
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener("change", function () {
            try { localStorage.setItem(STORAGE_KEY, this.value); } catch (e) {}
            const u = new URL(window.location.href);
            u.searchParams.set("size", this.value);
            u.searchParams.set("page", "1");
            window.location.href = u.toString();
        });
    }

    const categorySelect = document.getElementById("category-select");
    if (categorySelect) {
        categorySelect.addEventListener("change", function () {
            const u = new URL(window.location.href);
            u.searchParams.set("category", this.value);
            u.searchParams.set("page", "1");
            window.location.href = u.toString();
        });
    }

    // ---- column filter popover (Stock (Tech Buy) only) ----
    const optionsDataEl = document.getElementById("filter-options-data");
    const activeDataEl = document.getElementById("filter-active-data");
    if (optionsDataEl && activeDataEl) {
        const FILTER_OPTIONS = JSON.parse(optionsDataEl.textContent || "{}");
        const ACTIVE_FILTERS = JSON.parse(activeDataEl.textContent || "{}");
        const NULL_VALUE = "__NULL__";
        const COLUMN_LABELS = { techbuy_stock: "Stock (Tech Buy)" };

        const popover = document.getElementById("filter-popover");
        const popoverTitle = document.getElementById("filter-popover-title");
        const popoverBody = document.getElementById("filter-popover-body");
        const applyBtn = document.getElementById("filter-apply-btn");
        const clearBtn = document.getElementById("filter-clear-btn");
        const resetAllBtn = document.getElementById("reset-filters-btn");
        const filterSearchInput = document.getElementById("filter-search-input");
        const selectAllBtn = document.getElementById("filter-select-all-btn");
        const deselectAllBtn = document.getElementById("filter-deselect-all-btn");

        let activeCol = null;

        function currentFilters() {
            const copy = {};
            Object.keys(ACTIVE_FILTERS).forEach(function (k) { copy[k] = ACTIVE_FILTERS[k].slice(); });
            return copy;
        }

        function navigateWithFilters(filters) {
            const target = new URL(window.location.href);
            const nonEmpty = {};
            Object.keys(filters).forEach(function (k) {
                if (filters[k] && filters[k].length) nonEmpty[k] = filters[k];
            });
            if (Object.keys(nonEmpty).length) {
                target.searchParams.set("filters", JSON.stringify(nonEmpty));
            } else {
                target.searchParams.delete("filters");
            }
            target.searchParams.set("page", "1");
            window.location.href = target.toString();
        }

        function filterPopoverOptions(searchText) {
            const filter = (searchText || "").toLowerCase().trim();
            popoverBody.querySelectorAll(".filter-option").forEach(function (label) {
                const text = label.textContent.toLowerCase();
                label.classList.toggle("filter-option-hidden", !!filter && text.indexOf(filter) === -1);
            });
        }

        function openPopover(col, btn) {
            const opt = FILTER_OPTIONS[col];
            if (!opt) return;
            activeCol = col;

            popoverTitle.textContent = "Filter: " + (COLUMN_LABELS[col] || col);
            popoverBody.innerHTML = "";
            if (filterSearchInput) filterSearchInput.value = "";

            const active = ACTIVE_FILTERS[col];
            const allValues = opt.values.slice();
            if (opt.has_null) allValues.push(NULL_VALUE);

            const showSearch = allValues.length > 8;
            if (filterSearchInput) filterSearchInput.parentElement.style.display = showSearch ? "block" : "none";

            allValues.forEach(function (val) {
                const label = document.createElement("label");
                label.className = "filter-option";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = val;
                cb.checked = !active || active.indexOf(val) !== -1;
                label.appendChild(cb);
                const span = document.createElement("span");
                span.textContent = val === NULL_VALUE ? "(Not fetched)" : val;
                label.appendChild(span);
                popoverBody.appendChild(label);
            });

            popover.style.display = "block";
            popover.style.top = "0px";
            popover.style.left = "0px";

            const rect = btn.getBoundingClientRect();
            const popoverWidth = 240;
            const popoverHeight = popover.offsetHeight;

            let left = rect.left + window.scrollX;
            if (rect.left + popoverWidth > window.innerWidth) left = rect.right + window.scrollX - popoverWidth;

            let top = rect.bottom + window.scrollY + 6;
            if (rect.bottom + popoverHeight + 6 > window.innerHeight) top = rect.top + window.scrollY - popoverHeight - 6;

            popover.style.top = top + "px";
            popover.style.left = left + "px";
        }

        function closePopover() {
            popover.style.display = "none";
            activeCol = null;
        }

        if (filterSearchInput) {
            filterSearchInput.addEventListener("input", function () {
                filterPopoverOptions(filterSearchInput.value);
            });
        }

        function visibleCheckboxes() {
            return Array.prototype.slice
                .call(popoverBody.querySelectorAll(".filter-option"))
                .filter(function (label) { return !label.classList.contains("filter-option-hidden"); })
                .map(function (label) { return label.querySelector("input[type=checkbox]"); });
        }

        if (selectAllBtn) selectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = true; });
        });
        if (deselectAllBtn) deselectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = false; });
        });

        document.querySelectorAll(".filter-btn").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                const col = btn.getAttribute("data-filter-col");
                if (activeCol === col && popover.style.display === "block") {
                    closePopover();
                } else {
                    openPopover(col, btn);
                }
            });
        });

        document.addEventListener("click", function (e) {
            if (popover.style.display === "block" && !popover.contains(e.target) && !e.target.closest(".filter-btn")) {
                closePopover();
            }
        });

        if (applyBtn) applyBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const items = Array.prototype.slice.call(popoverBody.querySelectorAll("input[type=checkbox]"));
            const checked = items.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
            const filters = currentFilters();
            if (checked.length === 0 || checked.length === items.length) {
                delete filters[activeCol];
            } else {
                filters[activeCol] = checked;
            }
            navigateWithFilters(filters);
        });

        if (clearBtn) clearBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const filters = currentFilters();
            delete filters[activeCol];
            navigateWithFilters(filters);
        });

        if (resetAllBtn) resetAllBtn.addEventListener("click", function () {
            navigateWithFilters({});
        });
    }

    // ---- click-to-copy cells ----
    const NO_COPY_COLUMNS = ["techbuy_link", "other_link", "actions"];
    let copyToast = null;
    let copyToastTimer = null;

    function showCopyToast(x, y) {
        if (!copyToast) {
            copyToast = document.createElement("div");
            copyToast.className = "copy-toast";
            copyToast.textContent = "Copied!";
            document.body.appendChild(copyToast);
        }
        copyToast.style.left = x + "px";
        copyToast.style.top = y + "px";
        copyToast.classList.remove("show");
        void copyToast.offsetWidth;
        copyToast.classList.add("show");
        clearTimeout(copyToastTimer);
        copyToastTimer = setTimeout(function () { copyToast.classList.remove("show"); }, 900);
    }

    table.addEventListener("click", function (e) {
        const td = e.target.closest("td[data-col]");
        if (!td || !table.contains(td)) return;

        const col = td.getAttribute("data-col");
        if (NO_COPY_COLUMNS.indexOf(col) !== -1) return;

        const text = (td.getAttribute("data-full-text") || td.innerText).trim();
        if (!text || text === "—") return;

        if (!navigator.clipboard) return;

        navigator.clipboard.writeText(text).then(function () {
            showCopyToast(e.clientX, e.clientY);
            td.classList.remove("copy-flash");
            void td.offsetWidth;
            td.classList.add("copy-flash");
        }).catch(function () {
            // clipboard unavailable (e.g. non-secure context) — fail silently
        });
    });
});
