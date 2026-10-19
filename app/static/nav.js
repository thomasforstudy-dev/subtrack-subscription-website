// Header and menu behaviour. Everything still works without this file:
// it only adds the hover highlight and small conveniences.
// (Moving the dark pill between pages is done by the browser: see
// "Page changes" in style.css.)
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

    document.addEventListener("DOMContentLoaded", function () {
        initHoverHighlight();
        initScrollShadow();
        initUserMenu();
        initSubbyLinks();
        initSubbyTeaserOnce();
    });
})();
