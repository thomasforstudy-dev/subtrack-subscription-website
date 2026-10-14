// Scroll story for the landing page. Plain JavaScript, no libraries.
// The moving parts are in landing.css; this file only decides *when*.
(function () {
  const body = document.body;
  const chapters = document.querySelectorAll(".chapter");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1. Play a chapter's animation once, when its top passes 70% of the screen.
  const appear = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in-view");
        entry.target.querySelectorAll("[data-count]").forEach(countUp);
        appear.unobserve(entry.target);
      });
    },
    { rootMargin: "0px 0px -30% 0px" }
  );
  chapters.forEach((chapter) => appear.observe(chapter));

  // 2. Whichever chapter crosses the middle of the screen is "current":
  //    light up its dot on the rail and switch the top bar dark/light.
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
    { rootMargin: "-50% 0px -50% 0px" }
  );
  chapters.forEach((chapter) => current.observe(chapter));
  body.dataset.theme = "dark";

  // 3. While scrolling: fill the phone progress bar, and let the rush cards
  //    drift up at different speeds (feels like they're rushing past).
  const rush = document.querySelector("[data-rush]");
  let ticking = false;

  function onScroll() {
    const page = document.documentElement;
    const progress = page.scrollTop / (page.scrollHeight - page.clientHeight || 1);
    page.style.setProperty("--progress", progress.toFixed(4));
    if (rush && !reduceMotion) {
      rush.style.setProperty("--drift", Math.min(window.scrollY, 1200).toFixed(0));
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

  // 4. Numbers count up (or down, with data-from) to their real value.
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
    const duration = 1400;
    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // fast at first, then slows down
      el.textContent = show(from + (to - from) * eased);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // 5. Chapter 4: pick when the reminder email arrives.
  const daysText = document.querySelector("[data-days-text]");
  document.querySelectorAll(".when[data-days]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".when[data-days]").forEach((b) => b.classList.remove("on"));
      button.classList.add("on");
      daysText.textContent = button.dataset.days + " days";
    });
  });
})();
