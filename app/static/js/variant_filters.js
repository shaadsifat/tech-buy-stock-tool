document.addEventListener("DOMContentLoaded", function () {
    const optionsDataEl = document.getElementById("filter-options-data");
    const activeDataEl = document.getElementById("filter-active-data");
    if (!optionsDataEl || !activeDataEl) return;

    const FILTER_OPTIONS = JSON.parse(optionsDataEl.textContent || "{}");
    const ACTIVE_FILTERS = JSON.parse(activeDataEl.textContent || "{}");

    // Separate storage keys from the Single Product List page's filters/page size —
    // the two pages have different filterable columns, so sharing a key would restore
    // filters that don't even apply here.
    const FILTERS_STORAGE_KEY = "variantProductsFiltersV1";
    const PAGE_SIZE_STORAGE_KEY = "variantProductsPageSizeV1";

    function loadStoredFilters() {
        try {
            const raw = localStorage.getItem(FILTERS_STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    }

    function saveStoredFilters(filters) {
        try {
            localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters));
        } catch (e) {}
    }

    function loadStoredPageSize() {
        try {
            return localStorage.getItem(PAGE_SIZE_STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function saveStoredPageSize(size) {
        try {
            localStorage.setItem(PAGE_SIZE_STORAGE_KEY, size);
        } catch (e) {}
    }

    const restoreUrl = new URL(window.location.href);
    let needsRestore = false;

    if (!restoreUrl.searchParams.has("filters")) {
        const stored = loadStoredFilters();
        if (Object.keys(stored).length) {
            restoreUrl.searchParams.set("filters", JSON.stringify(stored));
            needsRestore = true;
        }
    } else {
        saveStoredFilters(ACTIVE_FILTERS);
    }

    if (!restoreUrl.searchParams.has("size")) {
        const storedSize = loadStoredPageSize();
        if (storedSize) {
            restoreUrl.searchParams.set("size", storedSize);
            needsRestore = true;
        }
    } else {
        saveStoredPageSize(restoreUrl.searchParams.get("size"));
    }

    if (needsRestore) {
        window.location.href = restoreUrl.toString();
        return;
    }

    const COLUMN_LABELS = {
        need_action: "Need Action",
        reviewed: "Reviewed",
        shopify_status: "Shopify Status",
        fetched_status: "Fetched Status",
        other_link: "Other Link",
    };

    const NULL_VALUE = "__NULL__";

    const popover = document.getElementById("filter-popover");
    const popoverTitle = document.getElementById("filter-popover-title");
    const popoverBody = document.getElementById("filter-popover-body");
    const applyBtn = document.getElementById("filter-apply-btn");
    const clearBtn = document.getElementById("filter-clear-btn");
    const resetAllBtn = document.getElementById("reset-filters-btn");
    const filterSearchInput = document.getElementById("filter-search-input");
    const selectAllBtn = document.getElementById("filter-select-all-btn");
    const deselectAllBtn = document.getElementById("filter-deselect-all-btn");
    if (!popover) return;

    let activeCol = null;

    function currentFilters() {
        const copy = {};
        Object.keys(ACTIVE_FILTERS).forEach(function (k) {
            copy[k] = ACTIVE_FILTERS[k].slice();
        });
        return copy;
    }

    function navigateWithFilters(filters) {
        const url = new URL(window.location.href);
        const nonEmpty = {};
        Object.keys(filters).forEach(function (k) {
            if (filters[k] && filters[k].length) nonEmpty[k] = filters[k];
        });
        saveStoredFilters(nonEmpty);
        if (Object.keys(nonEmpty).length) {
            url.searchParams.set("filters", JSON.stringify(nonEmpty));
        } else {
            url.searchParams.delete("filters");
        }
        url.searchParams.set("page", "1");
        window.location.href = url.toString();
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
        if (filterSearchInput) {
            filterSearchInput.parentElement.style.display = showSearch ? "block" : "none";
        }

        if (allValues.length === 0) {
            const empty = document.createElement("p");
            empty.className = "muted";
            empty.textContent = "No values yet.";
            popoverBody.appendChild(empty);
        }

        allValues.forEach(function (val) {
            const label = document.createElement("label");
            label.className = "filter-option";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = val;
            cb.checked = !active || active.indexOf(val) !== -1;
            label.appendChild(cb);
            const span = document.createElement("span");
            span.textContent = val === NULL_VALUE ? "(No other-site data yet)" : val;
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
        if (rect.left + popoverWidth > window.innerWidth) {
            left = rect.right + window.scrollX - popoverWidth;
        }

        let top = rect.bottom + window.scrollY + 6;
        if (rect.bottom + popoverHeight + 6 > window.innerHeight) {
            top = rect.top + window.scrollY - popoverHeight - 6;
        }

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

    if (selectAllBtn) {
        selectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = true; });
        });
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = false; });
        });
    }

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

    if (applyBtn) {
        applyBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const checkboxes = popoverBody.querySelectorAll("input[type=checkbox]");
            const items = Array.prototype.slice.call(checkboxes);
            const checked = items.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });

            const filters = currentFilters();
            if (checked.length === 0 || checked.length === items.length) {
                delete filters[activeCol];
            } else {
                filters[activeCol] = checked;
            }
            navigateWithFilters(filters);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const filters = currentFilters();
            delete filters[activeCol];
            navigateWithFilters(filters);
        });
    }

    if (resetAllBtn) {
        resetAllBtn.addEventListener("click", function () {
            navigateWithFilters({});
        });
    }

    // ---- page size dropdown (category dropdown + expand/copy handled in variant_products.js) ----
    const pageSizeSelect = document.getElementById("page-size-select");
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener("change", function () {
            saveStoredPageSize(pageSizeSelect.value);
            const url = new URL(window.location.href);
            url.searchParams.set("size", pageSizeSelect.value);
            url.searchParams.set("page", "1");
            window.location.href = url.toString();
        });
    }
});
