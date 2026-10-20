// AllOutFree motion (after the owner's "Dashboard V14" video). Every page works
// without this file: the numbers are already written by the server, and the
// theme can still be changed (it just switches without the circle).
(function () {
    "use strict";

    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---------- 1. Light / dark with a circle that grows from the button --------
    function currentTheme() {
        return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    }

    function saveTheme(theme) {
        try {
            localStorage.setItem("alloutfree_theme", theme);
        } catch (e) {
            /* private window: the choice just isn't remembered */
        }
    }

    function applyTheme(theme) {
        if (theme === "dark") document.documentElement.dataset.theme = "dark";
        else delete document.documentElement.dataset.theme;
        document.querySelectorAll("[data-theme-set]").forEach(function (button) {
            button.classList.toggle("is-active", button.dataset.themeSet === theme);
            button.setAttribute("aria-pressed", String(button.dataset.themeSet === theme));
        });
        saveTheme(theme);
    }

    function switchTheme(theme, button) {
        if (theme === currentTheme()) return;
        if (!document.startViewTransition || reduceMotion) {
            applyTheme(theme);
            return;
        }
        // The new colours are revealed inside a circle that grows from the button
        // to the farthest corner of the window.
        var box = button.getBoundingClientRect();
        var x = box.left + box.width / 2;
        var y = box.top + box.height / 2;
        var radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
        var root = document.documentElement;
        root.classList.add("theme-switching"); // see "Theme switch" in style.css
        var transition = document.startViewTransition(function () { applyTheme(theme); });
        transition.ready.then(function () {
            root.animate(
                { clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + radius + "px at " + x + "px " + y + "px)"] },
                { duration: 650, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" }
            );
        });
        transition.finished.finally(function () { root.classList.remove("theme-switching"); });
    }

    function initTheme() {
        applyTheme(currentTheme()); // mark the right sun/moon button
        document.querySelectorAll("[data-theme-set]").forEach(function (button) {
            button.addEventListener("click", function () { switchTheme(button.dataset.themeSet, button); });
        });
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            button.addEventListener("click", function () {
                switchTheme(currentTheme() === "dark" ? "light" : "dark", button);
            });
        });
    }

    // ---------- 2. Numbers count up from 0 (dashboard) --------------------------
    // Same format as the server's "money" filter: 398,000 (VND) / 20.00 (USD).
    var WHOLE = ["BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"];

    function countUp(element) {
        var target = parseFloat(element.dataset.count);
        if (!isFinite(target) || target <= 0) return;
        var currency = element.dataset.currency;
        var decimals = currency && WHOLE.indexOf(currency) === -1 ? 2 : 0;
        var format = new Intl.NumberFormat("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
        var finalText = element.textContent;
        var start = null;
        var duration = 1100;
        var done = false;
        function step(now) {
            if (done) return;
            if (start === null) start = now;
            var t = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - t, 3); // fast at first, gently landing
            element.textContent = t < 1 ? format.format(target * eased) : finalText;
            if (t < 1) requestAnimationFrame(step);
            else done = true;
        }
        requestAnimationFrame(step);
        // Safety net: browsers pause animation frames in background tabs. Whatever
        // happens, the real number (written by the server) is back on screen.
        setTimeout(function () {
            done = true;
            element.textContent = finalText;
        }, duration + 400);
    }

    function initCountUp() {
        if (reduceMotion || document.hidden) return;
        document.querySelectorAll("[data-count]").forEach(function (element, index) {
            setTimeout(function () { countUp(element); }, 250 + index * 60);
        });
    }

    // ---------- 3. Search inside the recent-activity table --------------------
    function initActivitySearch() {
        var input = document.querySelector("[data-activity-search]");
        if (!input) return;
        var rows = document.querySelectorAll("[data-activity-row]");
        var empty = document.querySelector("[data-activity-empty]");
        input.addEventListener("input", function () {
            var words = input.value.trim().toLowerCase();
            var shown = 0;
            rows.forEach(function (row) {
                var match = !words || row.textContent.toLowerCase().indexOf(words) !== -1;
                row.hidden = !match;
                if (match) shown += 1;
            });
            if (empty) empty.hidden = shown !== 0;
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        initCountUp();
        initActivitySearch();
    });
})();
