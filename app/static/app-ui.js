// SubTrack UI controller (Antigravity UI lane):
// - VI / EN lightweight client-side language toggle
// - Show / hide password button on auth forms
// - Topbar Subby trigger & workspace tab highlight
// - Dashboard 5-block state preview switcher (real / loading / error / demo) + Credit card demo toggle
// - Subscriptions client-side search, cycle filter, status filter, sort & archive confirmation dialog
// - Links delete confirmation dialog
// - Bills / Document review 4-step flow, 2-column / mobile tab toggle, page switcher, field-to-source highlight & transaction filter
// - Settings preferences persistence, PWA guide dismiss & client-side JSON/CSV export

(function () {
    "use strict";

    // --- 1. Password Show / Hide Toggle ---
    function initPasswordToggles() {
        var toggles = document.querySelectorAll("[data-pw-toggle], [data-toggle-password]");
        toggles.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var targetId = btn.getAttribute("data-pw-toggle") || btn.getAttribute("data-toggle-password");
                var input = targetId ? document.getElementById(targetId) : btn.parentElement.querySelector("input");
                if (!input) return;
                var isPassword = input.type === "password";
                input.type = isPassword ? "text" : "password";
                btn.setAttribute("aria-pressed", isPassword ? "true" : "false");
                btn.textContent = isPassword ? "Ẩn" : "Hiện";
            });
        });
    }

    // --- 2. Generic <dialog> close buttons & backdrop click ---
    function initDialogs() {
        document.querySelectorAll("[data-close-dialog]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var dialogId = btn.getAttribute("data-close-dialog");
                var dialog = dialogId ? document.getElementById(dialogId) : btn.closest("dialog");
                if (dialog && typeof dialog.close === "function") {
                    dialog.close();
                }
            });
        });

        document.querySelectorAll("dialog").forEach(function (dialog) {
            dialog.addEventListener("click", function (event) {
                var rect = dialog.getBoundingClientRect();
                var clickedOutside =
                    event.clientX < rect.left ||
                    event.clientX > rect.right ||
                    event.clientY < rect.top ||
                    event.clientY > rect.bottom;
                if (clickedOutside && typeof dialog.close === "function") {
                    dialog.close();
                }
            });
        });
    }

    // --- 3. Topbar Subby Trigger & Form Double-Submit Protection ---
    function initTopbarAndForms() {
        document.querySelectorAll("[data-open-subby]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var fab = document.querySelector("[data-subby-fab]");
                if (fab) fab.click();
            });
        });

        document.querySelectorAll("form[data-submitting-text]").forEach(function (form) {
            form.addEventListener("submit", function () {
                var submitBtn = form.querySelector('button[type="submit"]');
                if (!submitBtn || submitBtn.disabled) return;
                submitBtn.disabled = true;
                submitBtn.textContent = form.getAttribute("data-submitting-text") || "Đang xử lý…";
            });
        });
    }

    // --- 4. Dashboard 5-Block State Switcher & Credit Card Demo Toggle ---
    function initDashboardStateSwitcher() {
        var stateBtns = document.querySelectorAll("[data-dash-state]");
        var views = document.querySelectorAll("[data-dash-view]");
        if (stateBtns.length && views.length) {
            stateBtns.forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var targetState = btn.getAttribute("data-dash-state") || "real";
                    stateBtns.forEach(function (b) {
                        b.classList.toggle("on", b === btn);
                    });
                    views.forEach(function (view) {
                        view.hidden = view.getAttribute("data-dash-view") !== targetState;
                    });
                });
            });
        }

        var ccToggleBtn = document.querySelector("[data-toggle-card-demo]");
        var ccDemoGrid = document.getElementById("cc-demo-grid");
        var ccRealEmpty = document.getElementById("cc-real-empty");
        if (ccToggleBtn && ccDemoGrid) {
            ccToggleBtn.addEventListener("click", function () {
                var showingDemo = !ccDemoGrid.hidden;
                ccDemoGrid.hidden = showingDemo;
                if (ccRealEmpty) ccRealEmpty.hidden = !showingDemo;
                ccToggleBtn.classList.toggle("on", !showingDemo);
                ccToggleBtn.setAttribute("aria-pressed", !showingDemo ? "true" : "false");
            });
        }
    }

    // --- 5. Subscriptions Search, Filter, Sort & Archive Confirmation ---
    function initSubscriptionsControls() {
        var searchInput = document.getElementById("sub-search");
        var cycleFilter = document.getElementById("sub-cycle-filter");
        var statusFilter = document.getElementById("sub-status-filter");
        var sortSelect = document.getElementById("sub-sort");
        var tbody = document.getElementById("subs-tbody");
        var emptyMsg = document.getElementById("subs-filter-empty");

        function applySubFilters() {
            if (!tbody) return;
            var q = searchInput ? searchInput.value.trim().toLowerCase() : "";
            var cycle = cycleFilter ? cycleFilter.value : "all";
            var status = statusFilter ? statusFilter.value : "all";
            var sortBy = sortSelect ? sortSelect.value : "date-asc";

            var rows = Array.prototype.slice.call(tbody.querySelectorAll("[data-sub-row]"));
            var visible = 0;

            rows.forEach(function (row) {
                var name = row.getAttribute("data-name") || "";
                var notes = row.getAttribute("data-notes") || "";
                var currency = (row.getAttribute("data-currency") || "").toLowerCase();
                var rowCycle = row.getAttribute("data-cycle") || "";
                var days = parseInt(row.getAttribute("data-days") || "999", 10);

                var okQuery = !q || name.indexOf(q) !== -1 || notes.indexOf(q) !== -1 || currency.indexOf(q) !== -1;
                var okCycle = cycle === "all" || rowCycle === cycle;
                var okStatus =
                    status === "all" ||
                    (status === "due" && days <= 0) ||
                    (status === "soon" && days >= 0 && days <= 7);

                var show = okQuery && okCycle && okStatus;
                row.hidden = !show;
                if (show) visible += 1;
            });

            rows.sort(function (a, b) {
                if (sortBy === "amount-desc") {
                    return (parseFloat(b.getAttribute("data-amount")) || 0) -
                           (parseFloat(a.getAttribute("data-amount")) || 0);
                }
                if (sortBy === "name-asc") {
                    return (a.getAttribute("data-name") || "").localeCompare(b.getAttribute("data-name") || "");
                }
                return (a.getAttribute("data-date") || "").localeCompare(b.getAttribute("data-date") || "");
            });

            rows.forEach(function (row) {
                tbody.appendChild(row);
            });

            if (emptyMsg) {
                emptyMsg.hidden = visible > 0;
            }
        }

        if (searchInput) searchInput.addEventListener("input", applySubFilters);
        if (cycleFilter) cycleFilter.addEventListener("change", applySubFilters);
        if (statusFilter) statusFilter.addEventListener("change", applySubFilters);
        if (sortSelect) sortSelect.addEventListener("change", applySubFilters);

        // Archive confirmation dialog
        var archiveDialog = document.getElementById("dialog-confirm-archive");
        var archiveTargetName = document.getElementById("archive-target-name");
        var confirmArchiveBtn = document.getElementById("confirm-archive-btn");
        var pendingArchiveForm = null;

        document.querySelectorAll(".archive-form").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (form.getAttribute("data-confirmed") === "true") return;
                if (!archiveDialog || typeof archiveDialog.showModal !== "function") return;
                event.preventDefault();
                pendingArchiveForm = form;
                if (archiveTargetName) {
                    archiveTargetName.textContent = form.getAttribute("data-sub-title") || "gói đăng ký này";
                }
                archiveDialog.showModal();
            });
        });

        if (confirmArchiveBtn) {
            confirmArchiveBtn.addEventListener("click", function () {
                if (archiveDialog && typeof archiveDialog.close === "function") {
                    archiveDialog.close();
                }
                if (pendingArchiveForm) {
                    pendingArchiveForm.setAttribute("data-confirmed", "true");
                    pendingArchiveForm.submit();
                }
            });
        }
    }

    // --- 5b. Account-Wide Decimal Totals Summary (/dashboard.json) ---
    function initAccountWideSummary() {
        var box = document.getElementById("account-wide-summary");
        var body = document.getElementById("account-wide-totals-body");
        if (!box || !body) return;
        var url = box.getAttribute("data-summary-url");
        if (!url) return;

        fetch(url, { headers: { "Accept": "application/json" } })
            .then(function (res) {
                if (!res.ok) throw new Error("status-" + res.status);
                return res.json();
            })
            .then(function (data) {
                if (!data || !Array.isArray(data.totals)) {
                    throw new Error("invalid-payload");
                }
                body.textContent = "";
                if (data.totals.length === 0) {
                    var emptyP = document.createElement("p");
                    emptyP.className = "hint";
                    emptyP.style.margin = "0.35rem 0 0";
                    emptyP.textContent = "Chưa có gói đăng ký đang hoạt động để tính tổng toàn tài khoản.";
                    body.appendChild(emptyP);
                    return;
                }
                var grid = document.createElement("div");
                grid.className = "summary-grid";
                grid.style.marginTop = "0.55rem";
                data.totals.forEach(function (t) {
                    var card = document.createElement("div");
                    card.className = "stat-card";

                    var label = document.createElement("span");
                    label.className = "stat-label";
                    label.textContent = "Tổng quy đổi (" + String(t.currency || "") + ")";

                    var val = document.createElement("strong");
                    val.className = "stat-value";
                    val.textContent = String(t.currency || "") + " " + String(t.monthly || "0.00") + " / tháng";

                    var sub = document.createElement("span");
                    sub.className = "stat-sub";
                    sub.textContent =
                        String(t.currency || "") +
                        " " +
                        String(t.yearly || "0.00") +
                        " / năm · " +
                        String(t.count || 0) +
                        " gói đang hoạt động";

                    card.appendChild(label);
                    card.appendChild(val);
                    card.appendChild(sub);
                    grid.appendChild(card);
                });
                body.appendChild(grid);
            })
            .catch(function () {
                body.textContent = "";
                var fallbackP = document.createElement("p");
                fallbackP.className = "hint";
                fallbackP.style.margin = "0.35rem 0 0";
                fallbackP.textContent =
                    "Mở trang Bảng điều khiển (/dashboard) để xem tổng chi phí Decimal toàn tài khoản theo từng loại tiền tệ.";
                body.appendChild(fallbackP);
            });
    }

    // --- 5c. Subscription Form Presets & Lead Days Chips ---
    function initSubscriptionFormHelpers() {
        document.querySelectorAll("[data-preset-sub]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var raw = btn.getAttribute("data-preset-sub");
                if (!raw) return;
                var parts = raw.split("|");
                var nameEl = document.getElementById("name");
                var amountEl = document.getElementById("amount");
                var currencyEl = document.getElementById("currency");
                var cycleEl = document.getElementById("cycle");
                var urlEl = document.getElementById("manage_url");
                if (nameEl && parts[0]) nameEl.value = parts[0];
                if (amountEl && parts[1]) amountEl.value = parts[1];
                if (currencyEl && parts[2]) currencyEl.value = parts[2];
                if (cycleEl && parts[3]) cycleEl.value = parts[3];
                if (urlEl && parts[4]) urlEl.value = parts[4];
            });
        });

        document.querySelectorAll("[data-set-remind]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var val = btn.getAttribute("data-set-remind") || "7,1";
                var input = document.getElementById("lead_days");
                if (input) input.value = val;
            });
        });

        document.querySelectorAll("[data-clear-input]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var id = btn.getAttribute("data-clear-input");
                var input = id ? document.getElementById(id) : null;
                if (input) input.value = "";
            });
        });
    }

    // --- 6. Links Delete Confirmation Dialog & Favicon Fallback ---
    function initLinksDeleteDialog() {
        document.querySelectorAll("img[data-favicon-img]").forEach(function (img) {
            img.addEventListener("error", function () {
                img.hidden = true;
                var wrap = img.parentElement;
                if (!wrap) return;
                var fb = wrap.querySelector("[data-favicon-fallback]");
                if (fb) fb.hidden = false;
            });
        });

        var deleteDialog = document.getElementById("dialog-confirm-delete-link");
        var deleteTargetName = document.getElementById("delete-link-target-name");
        var confirmDeleteBtn = document.getElementById("confirm-delete-link-btn");
        var pendingDeleteForm = null;

        document.querySelectorAll(".delete-link-form").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (form.getAttribute("data-confirmed") === "true") return;
                if (!deleteDialog || typeof deleteDialog.showModal !== "function") return;
                event.preventDefault();
                pendingDeleteForm = form;
                if (deleteTargetName) {
                    deleteTargetName.textContent = form.getAttribute("data-link-title") || "đường dẫn này";
                }
                deleteDialog.showModal();
            });
        });

        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener("click", function () {
                if (deleteDialog && typeof deleteDialog.close === "function") {
                    deleteDialog.close();
                }
                if (pendingDeleteForm) {
                    pendingDeleteForm.setAttribute("data-confirmed", "true");
                    pendingDeleteForm.submit();
                }
            });
        }
    }

    // --- 7. Bills / Document Review Interactive Demo ---
    function initBillsSection() {
        var stepBtns = document.querySelectorAll("[data-bill-step]");
        var stepItems = document.querySelectorAll("[data-step-item]");
        var errorBanner = document.getElementById("bill-step-error");
        var retryBtn = document.querySelector("[data-bill-retry]");
        var fileInput = document.getElementById("bill-file-input");
        var fileNameEl = document.getElementById("bill-file-name");

        function setBillStep(step) {
            stepBtns.forEach(function (btn) {
                btn.classList.toggle("on", btn.getAttribute("data-bill-step") === step);
            });
            if (errorBanner) {
                errorBanner.hidden = step !== "error";
            }
            var activeIdx = step === "upload" ? 0 : step === "ocr" ? 1 : 3;
            stepItems.forEach(function (li, idx) {
                li.classList.toggle("done", idx < activeIdx);
                li.classList.toggle("current", idx === activeIdx);
            });
        }

        stepBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                setBillStep(btn.getAttribute("data-bill-step") || "review");
            });
        });

        if (retryBtn) {
            retryBtn.addEventListener("click", function () {
                setBillStep("upload");
                if (fileInput) fileInput.click();
            });
        }

        if (fileInput) {
            fileInput.addEventListener("change", function () {
                if (!fileInput.files || !fileInput.files.length) return;
                var file = fileInput.files[0];
                var ext = (file.name.split(".").pop() || "").toLowerCase();
                if (["doc", "docx", "xls", "xlsx"].indexOf(ext) !== -1 || file.size > 10 * 1024 * 1024) {
                    setBillStep("error");
                    return;
                }
                if (fileNameEl) {
                    fileNameEl.textContent = "Đã chọn: " + file.name + " (" + Math.max(1, Math.round(file.size / 1024)) + " KB)";
                }
                setBillStep("review");
            });
        }

        // Document Page Switcher (Page 1 / Page 2)
        var pageBtns = document.querySelectorAll("[data-doc-page]");
        var pageContents = document.querySelectorAll("[data-page-content]");

        function switchDocPage(pageNum) {
            pageBtns.forEach(function (btn) {
                btn.classList.toggle("on", btn.getAttribute("data-doc-page") === String(pageNum));
            });
            pageContents.forEach(function (page) {
                page.hidden = page.getAttribute("data-page-content") !== String(pageNum);
            });
        }

        pageBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                switchDocPage(btn.getAttribute("data-doc-page") || "1");
            });
        });

        // Field focus -> highlight source block & auto-switch page
        var focusInputs = document.querySelectorAll("[data-focus-source]");
        var sourceBlocks = document.querySelectorAll("[data-source-anchor]");

        function highlightSource(anchorName, pageNum) {
            if (pageNum) switchDocPage(pageNum);
            sourceBlocks.forEach(function (block) {
                block.classList.toggle("is-highlighted", block.getAttribute("data-source-anchor") === anchorName);
            });
        }

        focusInputs.forEach(function (el) {
            el.addEventListener("focusin", function () {
                highlightSource(el.getAttribute("data-focus-source"), el.getAttribute("data-focus-page"));
            });
            el.addEventListener("click", function () {
                highlightSource(el.getAttribute("data-focus-source"), el.getAttribute("data-focus-page"));
            });
        });

        // Right column mode switch (Form vs Markdown)
        var rightModeBtns = document.querySelectorAll("[data-right-mode]");
        var rightContents = document.querySelectorAll("[data-right-content]");

        rightModeBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var mode = btn.getAttribute("data-right-mode") || "form";
                rightModeBtns.forEach(function (b) {
                    b.classList.toggle("on", b === btn);
                });
                rightContents.forEach(function (pane) {
                    pane.hidden = pane.getAttribute("data-right-content") !== mode;
                });
            });
        });

        // Mobile tabs for Review Workspace (fields / source / markdown)
        var mobileTabs = document.querySelectorAll("[data-review-tab]");
        var sourcePane = document.querySelector('[data-review-pane="source"]');
        var fieldsPane = document.querySelector('[data-review-pane="fields"]');

        mobileTabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                var mode = tab.getAttribute("data-review-tab") || "fields";
                mobileTabs.forEach(function (t) {
                    var active = t === tab;
                    t.classList.toggle("on", active);
                    t.setAttribute("aria-selected", active ? "true" : "false");
                });
                if (sourcePane && fieldsPane) {
                    sourcePane.classList.toggle("mobile-hidden", mode !== "source");
                    fieldsPane.classList.toggle("mobile-hidden", mode === "source");
                }
                if (mode === "markdown") {
                    rightContents.forEach(function (pane) {
                        pane.hidden = pane.getAttribute("data-right-content") !== "md";
                    });
                } else if (mode === "fields") {
                    rightContents.forEach(function (pane) {
                        pane.hidden = pane.getAttribute("data-right-content") !== "form";
                    });
                }
            });
        });

        // Transactions Filter
        var txStatusFilter = document.getElementById("tx-status-filter");
        var txCatFilter = document.getElementById("tx-category-filter");
        var txRows = document.querySelectorAll("[data-tx-row]");

        function filterTxRows() {
            var st = txStatusFilter ? txStatusFilter.value : "all";
            var cat = txCatFilter ? txCatFilter.value : "all";
            txRows.forEach(function (row) {
                var okSt = st === "all" || row.getAttribute("data-tx-status") === st;
                var okCat = cat === "all" || row.getAttribute("data-tx-category") === cat;
                row.hidden = !(okSt && okCat);
            });
        }

        if (txStatusFilter) txStatusFilter.addEventListener("change", filterTxRows);
        if (txCatFilter) txCatFilter.addEventListener("change", filterTxRows);
    }

    // --- 8. Settings Preferences, PWA Banner Dismissal & Formula-Safe JSON/CSV Export ---
    function sanitizeCsvCell(value) {
        var str = String(value == null ? "" : value);
        if (/^[=+\-@\t\r]/.test(str)) {
            str = "'" + str;
        }
        return '"' + str.replace(/"/g, '""') + '"';
    }

    function initSettingsControls() {
        var regForm = document.getElementById("regional-settings-form");
        var regStatus = document.getElementById("regional-save-status");
        if (regForm) {
            regForm.addEventListener("submit", function (event) {
                event.preventDefault();
                try {
                    var tz = (document.getElementById("pref-timezone") || {}).value || "Asia/Ho_Chi_Minh";
                    var cur = (document.getElementById("pref-currency") || {}).value || "VND";
                    localStorage.setItem("subtrack_regional_prefs", JSON.stringify({ timezone: tz, currency: cur }));
                } catch (e) {
                    // ignore storage error
                }
                if (regStatus) {
                    regStatus.hidden = false;
                    regStatus.textContent = "✓ Đã lưu tùy chọn hiển thị cục bộ trên trình duyệt này.";
                }
            });
        }

        var dismissPwaBtn = document.querySelector("[data-dismiss-pwa]");
        var pwaBanner = document.getElementById("pwa-install-banner");
        if (dismissPwaBtn && pwaBanner) {
            dismissPwaBtn.addEventListener("click", function () {
                pwaBanner.hidden = true;
            });
        }

        function collectSubscriptions() {
            var list = [];
            document.querySelectorAll("[data-sub-row]").forEach(function (row) {
                if (row.hidden) return;
                var nameEl = row.querySelector(".service-name");
                list.push({
                    name: nameEl ? nameEl.textContent.trim() : row.getAttribute("data-name") || "",
                    amount: String(row.getAttribute("data-amount") || "0.00"),
                    currency: row.getAttribute("data-currency") || "USD",
                    cycle: row.getAttribute("data-cycle") || "monthly",
                    next_renewal_at: row.getAttribute("data-date") || "",
                    status: row.getAttribute("data-status") || "active"
                });
            });
            return list;
        }

        function downloadBlob(filename, content, mimeType) {
            var blob = new Blob([content], { type: mimeType });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        var exportStatus = document.getElementById("export-subs-status");
        document.querySelectorAll("[data-export-subs]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var fmt = btn.getAttribute("data-export-subs");
                var subs = collectSubscriptions();
                if (fmt === "json") {
                    downloadBlob(
                        "subtrack-current-page-subscriptions.json",
                        JSON.stringify(
                            {
                                exported_at: new Date().toISOString(),
                                scope: "current_page_filtered_rows",
                                count: subs.length,
                                subscriptions: subs
                            },
                            null,
                            2
                        ),
                        "application/json;charset=utf-8"
                    );
                } else {
                    var lines = ["name,amount,currency,cycle,next_renewal_at,status"];
                    subs.forEach(function (s) {
                        lines.push(
                            [
                                sanitizeCsvCell(s.name),
                                sanitizeCsvCell(s.amount),
                                sanitizeCsvCell(s.currency),
                                sanitizeCsvCell(s.cycle),
                                sanitizeCsvCell(s.next_renewal_at),
                                sanitizeCsvCell(s.status)
                            ].join(",")
                        );
                    });
                    downloadBlob("subtrack-current-page-subscriptions.csv", lines.join("\n"), "text/csv;charset=utf-8");
                }
                if (exportStatus) {
                    exportStatus.hidden = false;
                    exportStatus.textContent =
                        "✓ Đã xuất " +
                        subs.length +
                        " dòng đang hiển thị trên trang hiện tại ra tệp ." +
                        fmt.toUpperCase() +
                        " (đã bảo vệ chống CSV formula injection).";
                }
            });
        });
    }

    // --- 9. Lightweight VI / EN Language Switcher ---
    function initLanguageToggle() {
        var toggleBtn = document.querySelector("[data-lang-toggle]");
        if (!toggleBtn) return;

        function applyLang(lang) {
            document.documentElement.setAttribute("data-ui-lang", lang);
            toggleBtn.textContent = lang === "en" ? "EN · VI" : "VI · EN";
            document.querySelectorAll("[data-vi][data-en]").forEach(function (el) {
                var text = el.getAttribute(lang === "en" ? "data-en" : "data-vi");
                if (text) el.textContent = text;
            });
        }

        var savedLang = "vi";
        try {
            savedLang = localStorage.getItem("subtrack_ui_lang") || "vi";
        } catch (e) {
            savedLang = "vi";
        }
        if (savedLang === "en") {
            applyLang("en");
        }

        toggleBtn.addEventListener("click", function () {
            var current = document.documentElement.getAttribute("data-ui-lang") || "vi";
            var next = current === "vi" ? "en" : "vi";
            try {
                localStorage.setItem("subtrack_ui_lang", next);
            } catch (e) {
                // ignore
            }
            applyLang(next);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initPasswordToggles();
        initDialogs();
        initTopbarAndForms();
        initDashboardStateSwitcher();
        initSubscriptionsControls();
        initAccountWideSummary();
        initSubscriptionFormHelpers();
        initLinksDeleteDialog();
        initBillsSection();
        initSettingsControls();
        initLanguageToggle();
    });
})();

