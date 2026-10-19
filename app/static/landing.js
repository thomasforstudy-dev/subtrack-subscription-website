// Scroll story for the landing page. Plain JavaScript, no libraries.
// Respects prefers-reduced-motion and remains readable if JS fails.
(function () {
  const body = document.body;
  const chapters = document.querySelectorAll(".chapter");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Ensure Chapter 1 is immediately marked in-view on load
  const ch1 = document.getElementById("ch1");
  if (ch1) ch1.classList.add("in-view");

  if ("IntersectionObserver" in window && !reduceMotion) {
    const appear = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in-view");
          entry.target.querySelectorAll("[data-count]").forEach(countUp);
          appear.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -20% 0px" }
    );
    chapters.forEach((chapter) => appear.observe(chapter));

    const railDots = document.querySelectorAll("[data-rail]");
    const current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          body.dataset.theme = entry.target.dataset.theme;
          railDots.forEach((dot) => {
            dot.classList.toggle("on", dot.dataset.rail === entry.target.id);
          });
        });
      },
      { rootMargin: "-45% 0px -45% 0px" }
    );
    chapters.forEach((chapter) => current.observe(chapter));
  } else {
    chapters.forEach((chapter) => chapter.classList.add("in-view"));
  }
  body.dataset.theme = "dark";

  // Fill progress bar & drift cards gently while scrolling
  const rush = document.querySelector("[data-rush]");
  let ticking = false;

  function onScroll() {
    const page = document.documentElement;
    const progress = page.scrollTop / (page.scrollHeight - page.clientHeight || 1);
    page.style.setProperty("--progress", progress.toFixed(4));
    if (rush && !reduceMotion) {
      rush.style.setProperty("--drift", Math.min(window.scrollY, 900).toFixed(0));
    }
    ticking = false;
  }

  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(onScroll);
      }
    },
    { passive: true }
  );
  onScroll();

  function countUp(el) {
    const to = parseFloat(el.dataset.count);
    const from = parseFloat(el.dataset.from || "0");
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    const show = (n) =>
      n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

    if (reduceMotion) {
      el.textContent = show(to);
      return;
    }
    const start = performance.now();
    const duration = 1100;
    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = show(from + (to - from) * eased);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // Chapter 4 interactive reminder day picker
  const daysText = document.querySelector("[data-days-text]");
  document.querySelectorAll(".when[data-days]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".when[data-days]").forEach((b) => b.classList.remove("on"));
      button.classList.add("on");
      const lang = document.documentElement.lang === "en" ? "en" : "vi";
      if (daysText) {
        daysText.textContent =
          lang === "en"
            ? button.dataset.daysLabelEn || button.dataset.days + " days"
            : button.dataset.daysLabelVi || button.dataset.days + " ngày";
      }
    });
  });

  // Footer legal dialogs (About, Privacy, Terms)
  document.querySelectorAll("[data-open-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dialog = document.getElementById(btn.dataset.openDialog);
      if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
      }
    });
  });

  document.querySelectorAll("[data-close-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dialog = btn.closest("dialog");
      if (dialog) dialog.close();
    });
  });

  document.querySelectorAll("dialog.legal-dialog").forEach((dialog) => {
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
  });
})();
