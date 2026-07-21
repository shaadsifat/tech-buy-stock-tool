document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input[data-dynamic-search]").forEach(function (input) {
        const tableId = input.getAttribute("data-table-target");
        if (!tableId) return;

        let timer = null;
        input.addEventListener("input", function () {
            clearTimeout(timer);
            timer = setTimeout(function () {
                const form = input.closest("form");
                if (!form) return;
                const params = new URLSearchParams(new FormData(form));
                const url = form.getAttribute("action") + "?" + params.toString();
                swapTable(url, tableId);
            }, 350);
        });
    });

    function swapTable(url, tableId) {
        fetch(url)
            .then(function (r) { return r.text(); })
            .then(function (html) {
                const doc = new DOMParser().parseFromString(html, "text/html");

                const newTable = doc.getElementById(tableId);
                const curTable = document.getElementById(tableId);
                if (newTable && curTable) {
                    const newBody = newTable.querySelector("tbody");
                    const curBody = curTable.querySelector("tbody");
                    if (newBody && curBody) curBody.innerHTML = newBody.innerHTML;
                }

                const newPagination = doc.querySelector(".pagination");
                const curPagination = document.querySelector(".pagination");
                if (newPagination && curPagination) curPagination.innerHTML = newPagination.innerHTML;

                history.pushState(null, "", url);

                if (window.__reapplyColumnConfig) window.__reapplyColumnConfig();
                if (window.__reapplyVariantColumnConfig) window.__reapplyVariantColumnConfig();
                if (window.__resetBulkBar) window.__resetBulkBar();
            })
            .catch(function () {
                // network hiccup — fall back to a normal navigation so the search still works
                window.location.href = url;
            });
    }

    // Without this, hitting Back after a dynamic search restores the old URL in the
    // address bar but leaves the table showing whatever was last fetched — a plain
    // reload keeps the two in sync.
    window.addEventListener("popstate", function () {
        window.location.reload();
    });
});
