// Header and menu behaviour. Everything still works without this file:
// it only adds the animations and small conveniences.
(function () {
    "use strict";

    // 1. The highlight that slides under the menu link you point at,
    //    and goes back to the current page's link when the mouse leaves.
    function initSlidingHighlight() {
        var nav = document.querySelector("[data-nav-pills]");
        var marker = document.querySelector("[data-nav-indicator]");
        if (!nav || !marker) return;
        var current = nav.querySelector(".nav-pill.is-active");
        // Without JavaScript the current link is simply painted dark (CSS);
        // "js-nav" hands that job to the sliding highlight instead.
        nav.classList.add("js-nav");

        function moveTo(link) {
            if (!link) {
                marker.style.opacity = "0";
                return;
            }
            marker.style.opacity = "1";
            marker.style.width = link.offsetWidth + "px";
            marker.style.transform = "translateX(" + link.offsetLeft + "px)";
            nav.querySelectorAll(".nav-pill").forEach(function (pill) {
                pill.classList.toggle("is-lit", pill === link);
            });
        }

        // First placement without animation, so it doesn't fly in on every page load.
        marker.classList.add("no-anim");
        moveTo(current);
        marker.getBoundingClientRect(); // apply the position before turning animation back on
        marker.classList.remove("no-anim");

        nav.querySelectorAll(".nav-pill").forEach(function (pill) {
            pill.addEventListener("mouseenter", function () { moveTo(pill); });
            pill.addEventListener("focus", function () { moveTo(pill); });
        });
        nav.addEventListener("mouseleave", function () { moveTo(current); });
        nav.addEventListener("focusout", function (event) {
            if (!nav.contains(event.relatedTarget)) moveTo(current);
        });
        // Fonts loading late, resizing and switching VI/EN all change the link
        // widths: measure again then.
        window.addEventListener("resize", function () { moveTo(current); });
        var langButton = document.querySelector("[data-lang-toggle]");
        if (langButton) {
            langButton.addEventListener("click", function () {
                window.requestAnimationFrame(function () { moveTo(current); });
            });
        }
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(function () { moveTo(current); });
        }
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

    document.addEventListener("DOMContentLoaded", function () {
        initSlidingHighlight();
        initScrollShadow();
        initUserMenu();
        initSubbyLinks();
    });
})();
