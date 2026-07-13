document.addEventListener("DOMContentLoaded", function () {
    const STORAGE_KEY = "productListColumnsV1";

    const COLUMN_LABELS = {
        name: "Product Name",
        category: "Category",
        techbuy_link: "Tech Buy Link",
        other_link: "Other Link",
        techbuy_stock: "Stock Status (Tech Buy)",
        other_stock: "Stock Status (Other)",
        techbuy_regular: "Regular Price",
        techbuy_sale: "Sale Price",
        other_regular: "Regular Price (Other)",
        other_sale: "Sale Price (Other)",
        regular_diff: "Regular Price Diff",
        sale_diff: "Sale Price Diff",
        need_action: "Need Action",
        fetched_status: "Fetched Status",
    };

    const DEFAULT_ORDER = [
        "name", "category", "techbuy_link", "other_link",
        "techbuy_stock", "other_stock",
        "techbuy_regular", "techbuy_sale", "other_regular", "other_sale",
        "regular_diff", "sale_diff",
        "need_action", "fetched_status",
    ];
    const DEFAULT_HIDDEN = ["techbuy_link", "other_link", "techbuy_stock", "regular_diff", "sale_diff"];

    const table = document.getElementById("product-table");
    if (!table) return;

    const headRow = table.querySelector("thead tr");

    function bodyRows() {
        return table.querySelectorAll("tbody tr[data-product-row]");
    }

    function loadConfig() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return { order: DEFAULT_ORDER.slice(), hidden: DEFAULT_HIDDEN.slice() };
            const parsed = JSON.parse(raw);
            let order = Array.isArray(parsed.order) ? parsed.order.filter((id) => COLUMN_LABELS[id]) : DEFAULT_ORDER.slice();
            DEFAULT_ORDER.forEach((id) => {
                if (!order.includes(id)) order.push(id);
            });
            const hidden = Array.isArray(parsed.hidden) ? parsed.hidden.filter((id) => COLUMN_LABELS[id]) : DEFAULT_HIDDEN.slice();
            return { order: order, hidden: hidden };
        } catch (e) {
            return { order: DEFAULT_ORDER.slice(), hidden: DEFAULT_HIDDEN.slice() };
        }
    }

    function saveConfig(config) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    }

    function reorderRow(row, fullOrder) {
        const cellsByCol = {};
        row.querySelectorAll("[data-col]").forEach((cell) => {
            cellsByCol[cell.getAttribute("data-col")] = cell;
        });
        const fragment = document.createDocumentFragment();
        fullOrder.forEach((id) => {
            const cell = cellsByCol[id];
            if (cell) fragment.appendChild(cell);
        });
        row.appendChild(fragment);
    }

    function applyConfig(config) {
        const fullOrder = config.order.concat(["reviewed", "actions"]);

        reorderRow(headRow, fullOrder);
        bodyRows().forEach((row) => reorderRow(row, fullOrder));

        const emptyCell = table.querySelector("tbody tr[data-empty-row] td");
        if (emptyCell) emptyCell.setAttribute("colspan", fullOrder.length);

        const hiddenSet = new Set(config.hidden);
        table.querySelectorAll("[data-col]").forEach((cell) => {
            const id = cell.getAttribute("data-col");
            if (id === "actions" || id === "reviewed") return;
            cell.style.display = hiddenSet.has(id) ? "none" : "";
        });
    }

    let currentConfig = loadConfig();
    applyConfig(currentConfig);

    // ---- customize modal ----
    const btn = document.getElementById("customize-columns-btn");
    const backdrop = document.getElementById("columns-modal-backdrop");
    const list = document.getElementById("columns-list");
    const closeBtn = document.getElementById("columns-modal-close");
    const cancelBtn = document.getElementById("columns-cancel-btn");
    const saveBtn = document.getElementById("columns-save-btn");
    const resetBtn = document.getElementById("columns-reset-btn");

    let dragEl = null;

    function buildList(config) {
        list.innerHTML = "";
        config.order.forEach((id) => {
            const li = document.createElement("li");
            li.className = "column-item";
            li.draggable = true;
            li.dataset.col = id;

            const handle = document.createElement("span");
            handle.className = "drag-handle";
            handle.textContent = "⋮⋮";

            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = config.hidden.indexOf(id) === -1;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(" " + COLUMN_LABELS[id]));

            li.appendChild(handle);
            li.appendChild(label);
            list.appendChild(li);

            li.addEventListener("dragstart", function () {
                dragEl = li;
                li.classList.add("dragging");
            });
            li.addEventListener("dragend", function () {
                li.classList.remove("dragging");
                dragEl = null;
            });
        });
    }

    list.addEventListener("dragover", function (e) {
        e.preventDefault();
        if (!dragEl) return;
        const items = Array.prototype.slice.call(list.querySelectorAll(".column-item:not(.dragging)"));
        let afterEl = null;
        for (let i = 0; i < items.length; i++) {
            const rect = items[i].getBoundingClientRect();
            if (e.clientY < rect.top + rect.height / 2) {
                afterEl = items[i];
                break;
            }
        }
        if (afterEl) {
            list.insertBefore(dragEl, afterEl);
        } else {
            list.appendChild(dragEl);
        }
    });

    function openModal() {
        buildList(currentConfig);
        backdrop.style.display = "flex";
    }

    function closeModal() {
        backdrop.style.display = "none";
    }

    btn.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);
    backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) closeModal();
    });

    saveBtn.addEventListener("click", function () {
        const items = Array.prototype.slice.call(list.querySelectorAll(".column-item"));
        const order = items.map((li) => li.dataset.col);
        const hidden = items
            .filter((li) => !li.querySelector("input").checked)
            .map((li) => li.dataset.col);
        currentConfig = { order: order, hidden: hidden };
        saveConfig(currentConfig);
        applyConfig(currentConfig);
        closeModal();
    });

    resetBtn.addEventListener("click", function () {
        currentConfig = { order: DEFAULT_ORDER.slice(), hidden: DEFAULT_HIDDEN.slice() };
        localStorage.removeItem(STORAGE_KEY);
        applyConfig(currentConfig);
        buildList(currentConfig);
    });

    // ---- click-to-copy cells ----
    const NO_COPY_COLUMNS = ["actions", "reviewed", "techbuy_link", "other_link"];
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
        void copyToast.offsetWidth; // restart animation if clicked again quickly
        copyToast.classList.add("show");
        clearTimeout(copyToastTimer);
        copyToastTimer = setTimeout(function () {
            copyToast.classList.remove("show");
        }, 900);
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

    // ---- reviewed checkbox ----
    table.addEventListener("change", function (e) {
        const checkbox = e.target.closest(".reviewed-checkbox");
        if (!checkbox) return;

        const productId = checkbox.getAttribute("data-product-id");
        const reviewed = checkbox.checked;
        const row = checkbox.closest("tr[data-product-row]");
        if (row) row.classList.toggle("row-reviewed", reviewed);

        fetch("/products/" + productId + "/reviewed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewed: reviewed }),
        }).catch(function () {
            // revert on failure so the UI doesn't lie about saved state
            checkbox.checked = !reviewed;
            if (row) row.classList.toggle("row-reviewed", !reviewed);
        });
    });
});
