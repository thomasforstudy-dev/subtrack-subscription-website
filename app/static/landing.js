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

  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Chapter 4 interactive reminder day picker: the line fills up to the chosen
  // day, and the email preview updates with a short fade (CSS .mail.swap).
  const daysText = document.querySelector("[data-days-text]");
  const timeline = document.querySelector(".timeline");
  const mail = document.querySelector(".remind .mail");
  const whens = Array.from(document.querySelectorAll(".when[data-days]"));
  function pick(button) {
    whens.forEach((b) => b.classList.toggle("on", b === button));
    if (timeline) timeline.style.setProperty("--pick", String(whens.indexOf(button)));
    const lang = document.documentElement.lang === "en" ? "en" : "vi";
    if (daysText) {
      daysText.textContent =
        lang === "en"
          ? button.dataset.daysLabelEn || button.dataset.days + " days"
          : button.dataset.daysLabelVi || button.dataset.days + " ngày";
    }
    if (mail && !calm) {
      mail.classList.remove("swap");
      void mail.offsetWidth; // restart the CSS animation
      mail.classList.add("swap");
    }
  }
  whens.forEach((button) => button.addEventListener("click", () => pick(button)));
  const startWhen = whens.find((b) => b.classList.contains("on"));
  if (timeline && startWhen) timeline.style.setProperty("--pick", String(whens.indexOf(startWhen)));

  // Chapter 3 demo list: sort by due date, price or name. Each row slides from
  // where it was to its new place ("FLIP": measure, move, then animate back).
  const ledger = document.querySelector("[data-ledger]");
  document.querySelectorAll(".sort-chip[data-sort]").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (!ledger) return;
      const key = chip.dataset.sort;
      document.querySelectorAll(".sort-chip").forEach((c) => {
        c.classList.toggle("on", c === chip);
        c.setAttribute("aria-pressed", c === chip ? "true" : "false");
      });
      const rows = Array.from(ledger.children);
      const before = new Map(rows.map((row) => [row, row.getBoundingClientRect().top]));
      rows.sort((a, b) => {
        if (key === "name") return a.dataset.name.localeCompare(b.dataset.name);
        if (key === "vnd") return Number(b.dataset.vnd) - Number(a.dataset.vnd);
        return Number(a.dataset.days) - Number(b.dataset.days);
      });
      rows.forEach((row) => ledger.appendChild(row));
      if (calm) return;
      rows.forEach((row) => {
        const shift = before.get(row) - row.getBoundingClientRect().top;
        if (!shift) return;
        row.animate(
          [{ transform: `translateY(${shift}px)` }, { transform: "translateY(0)" }],
          { duration: 520, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
        );
      });
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
