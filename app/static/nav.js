// Header and menu behaviour. Everything still works without this file:
// it only adds the hover highlight and small conveniences.
// The dark "current page" pill glides from the link you clicked on the last
// page to this page's link (initCurrentPill).
(function () {
    "use strict";

    // 1. A soft lilac pill slides behind the menu link you point at.
    //    The current page already has its own dark pill, so it gets none.
    function initHoverHighlight() {
        var nav = document.querySelector("[data-nav-pills]");
        var marker = document.querySelector("[data-nav-indicator]");
        if (!nav || !marker) return;

        function show(link) {
            if (!link || link.classList.contains("is-active")) {
                marker.style.opacity = "0";
                return;
            }
            var hidden = marker.style.opacity !== "1";
            if (hidden) marker.classList.add("no-anim"); // appear in place, don't fly in
            marker.style.width = link.offsetWidth + "px";
            marker.style.transform = "translateX(" + link.offsetLeft + "px)";
            if (hidden) {
                marker.getBoundingClientRect(); // apply the jump before animating again
                marker.classList.remove("no-anim");
            }
            marker.style.opacity = "1";
        }

        nav.querySelectorAll(".nav-pill").forEach(function (pill) {
            pill.addEventListener("mouseenter", function () { show(pill); });
            pill.addEventListener("focus", function () { show(pill); });
        });
        nav.addEventListener("mouseleave", function () { show(null); });
        nav.addEventListener("focusout", function (event) {
            if (!nav.contains(event.relatedTarget)) show(null);
        });
    }

    // 2. A soft shadow under the header once the page is scrolled.
    function initScrollShadow() {
        var bar = document.querySelector("[data-topbar]");
        if (!bar) return;
        function update() {
            bar.classList.toggle("is-scrolled", window.scrollY > 8);
        }
        window.addEventListener("scroll", update, { passive: true });
        update();
    }

    // 3. The account menu (<details>) closes on a click outside it or on Escape.
    function initUserMenu() {
        var menu = document.querySelector("[data-user-menu]");
        if (!menu) return;
        document.addEventListener("click", function (event) {
            if (menu.open && !menu.contains(event.target)) menu.open = false;
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && menu.open) {
                menu.open = false;
                menu.querySelector("summary").focus();
            }
        });
    }

    // 4. "Ask Subby" in the footer opens the same chat as the round Subby button.
    function initSubbyLinks() {
        document.querySelectorAll("[data-open-subby]").forEach(function (button) {
            button.addEventListener("click", function () {
                var fab = document.querySelector(".subby-fab");
                if (fab) fab.click();
            });
        });
    }

    // 5. Subby's "need help?" bubble pops up on the first page of a visit only,
    //    not on every page you open. (Private windows may block storage: then
    //    it simply shows as before.)
    function initSubbyTeaserOnce() {
        var teaser = document.querySelector("[data-teaser]");
        if (!teaser) return;
        try {
            if (sessionStorage.getItem("subtrack_teased")) {
                teaser.hidden = true;
            } else {
                sessionStorage.setItem("subtrack_teased", "1");
            }
        } catch (e) {
            /* storage blocked: keep the default */
        }
    }


    // 6. The dark pill under the current page glides over from the link you
    //    clicked on the previous page. Only the pill moves; the words stay sharp
    //    (the browser's page-change morph used to stretch the text with it).
    function initCurrentPill() {
        var nav = document.querySelector("[data-nav-pills]");
        var pill = document.querySelector("[data-nav-current]");
        var active = nav && nav.querySelector(".nav-pill.is-active");
        if (!nav || !pill || !active) return;
        var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        function place(left, width, animate) {
            pill.classList.toggle("no-anim", !animate);
            pill.style.width = width + "px";
            pill.style.transform = "translateX(" + left + "px)";
        }

        var from = null;
        try {
            from = JSON.parse(sessionStorage.getItem("nav-from") || "null");
            sessionStorage.removeItem("nav-from");
        } catch (e) {
            from = null;
        }

        nav.classList.add("has-current-pill");
        if (from && !reduce && Math.abs(from.left - active.offsetLeft) > 2) {
            place(from.left, from.width, false); // start under the old page's link...
            nav.classList.add("is-sliding");
            pill.getBoundingClientRect();
            requestAnimationFrame(function () {
                place(active.offsetLeft, active.offsetWidth, true); // ...and glide to this one
                setTimeout(function () { nav.classList.remove("is-sliding"); }, 280);
            });
        } else {
            place(active.offsetLeft, active.offsetWidth, false);
        }

        nav.querySelectorAll(".nav-pill").forEach(function (link) {
            link.addEventListener("click", function () {
                try {
                    sessionStorage.setItem("nav-from", JSON.stringify({ left: active.offsetLeft, width: active.offsetWidth }));
                } catch (e) { /* storage blocked: the pill just appears in place */ }
            });
        });
        // The web font can arrive after this runs and change the link widths.
        var again = function () { if (!nav.classList.contains("is-sliding")) place(active.offsetLeft, active.offsetWidth, false); };
        window.addEventListener("resize", again);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(again);
    }

    document.addEventListener("DOMContentLoaded", function () {
        initCurrentPill();
        initHoverHighlight();
        initScrollShadow();
        initUserMenu();
        initSubbyLinks();
        initSubbyTeaserOnce();
    });
})();
