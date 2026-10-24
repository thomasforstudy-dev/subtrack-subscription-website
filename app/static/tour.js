// Guided tour (templates/_tour.html): a spotlight on one button or area at a
// time, with a small card that says what it is. Steps can live on different
// pages: the tour remembers where it is (localStorage) and continues after the
// page changes. Keyboard: → / Enter = next, ← = back, Esc = close.
(function () {
  "use strict";
  var dataTag = document.getElementById("tour-data");
  if (!dataTag) return;
  var data = JSON.parse(dataTag.textContent);
  var steps = data.steps;
  var words = data.words;
  var KEY = "aof-tour:" + data.name; // which step, while a tour is running
  var SEEN = "aof-tour-seen:" + data.name + ":" + (data.user || "guest");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var layer, spot, card, index = 0, current = null, lastFocus = null;

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
    } catch (e) { /* private mode: the tour still works on this page */ }
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  function onThisPage(step) {
    return !step.path || location.pathname.indexOf(step.path) === 0;
  }

  // The first matching element that is actually visible (phone and desktop
  // can show different buttons for the same thing).
  function findTarget(step) {
    if (!step.target) return null;
    var all = document.querySelectorAll(step.target);
    for (var i = 0; i < all.length; i++) {
      var r = all[i].getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && getComputedStyle(all[i]).visibility !== "hidden") return all[i];
    }
    return null;
  }

  function build() {
    layer = document.createElement("div");
    layer.className = "tour-layer";
    layer.innerHTML =
      '<div class="tour-spot" aria-hidden="true"></div>' +
      '<div class="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title" tabindex="-1">' +
      '<p class="tour-count"></p>' +
      '<h2 id="tour-title" class="tour-title"></h2>' +
      '<p class="tour-text"></p>' +
      '<div class="tour-dots" aria-hidden="true"></div>' +
      '<div class="tour-actions">' +
      '<button type="button" class="tour-skip link"></button>' +
      '<span class="tour-spacer"></span>' +
      '<button type="button" class="button secondary btn-sm tour-back"></button>' +
      '<button type="button" class="button btn-sm tour-next"></button>' +
      "</div></div>";
    document.body.appendChild(layer);
    spot = layer.querySelector(".tour-spot");
    card = layer.querySelector(".tour-card");
    layer.querySelector(".tour-skip").textContent = words.skip;
    layer.querySelector(".tour-back").textContent = "← " + words.back;
    layer.querySelector(".tour-skip").addEventListener("click", function () { finish(); });
    layer.querySelector(".tour-back").addEventListener("click", function () { go(index - 1, -1); });
    layer.querySelector(".tour-next").addEventListener("click", function () { go(index + 1, 1); });
    // A click on the dark part does nothing: the tour only moves with its buttons.
    layer.addEventListener("click", function (e) { if (e.target === layer) card.focus(); });
    var dots = layer.querySelector(".tour-dots");
    steps.forEach(function () { dots.appendChild(document.createElement("i")); });
  }

  function place() {
    if (!layer) return;
    var pad = 8;
    var wide = window.innerWidth > 640;
    if (current) {
      var r = current.getBoundingClientRect();
      spot.style.opacity = "1";
      spot.style.top = (r.top - pad) + "px";
      spot.style.left = (r.left - pad) + "px";
      spot.style.width = (r.width + pad * 2) + "px";
      spot.style.height = (r.height + pad * 2) + "px";
      layer.classList.remove("no-target");
      if (!wide) {
        // Phone: the card is a sheet at the top or bottom, whichever side
        // the highlighted thing is NOT on, so it never covers it.
        card.removeAttribute("style");
        card.dataset.dock = (r.top + r.height / 2) > window.innerHeight * 0.5 ? "top" : "bottom";
        return;
      }
      var cw = card.offsetWidth, ch = card.offsetHeight, gap = 16;
      var below = r.bottom + pad + gap + ch < window.innerHeight;
      var top = below ? r.bottom + pad + gap : Math.max(12, r.top - pad - gap - ch);
      var left = Math.min(Math.max(12, r.left + r.width / 2 - cw / 2), window.innerWidth - cw - 12);
      card.style.top = top + "px";
      card.style.left = left + "px";
      card.dataset.side = below ? "below" : "above";
      card.style.setProperty("--arrow-x", Math.min(Math.max(24, r.left + r.width / 2 - left), cw - 24) + "px");
    } else {
      // Nothing to point at (a welcome step, or the button is hidden): centre the card.
      spot.style.opacity = "0";
      layer.classList.add("no-target");
      card.removeAttribute("style");
      card.dataset.side = "";
      card.dataset.dock = "";
    }
  }

  function show(i) {
    index = i;
    var step = steps[i];
    store(KEY, i + "|" + Date.now());
    current = findTarget(step);
    card.querySelector(".tour-count").textContent = words.step + " " + (i + 1) + " / " + steps.length;
    card.querySelector(".tour-title").textContent = step.title;
    card.querySelector(".tour-text").textContent = step.text;
    layer.querySelectorAll(".tour-dots i").forEach(function (dot, n) { dot.classList.toggle("on", n === i); dot.classList.toggle("done", n < i); });
    layer.querySelector(".tour-back").hidden = i === 0;
    var next = steps[i + 1];
    var nextBtn = layer.querySelector(".tour-next");
    nextBtn.textContent = !next ? words.done + " ✓" : (onThisPage(next) ? words.next + " →" : words.go + " " + next.page + " →");
    card.classList.remove("tour-pop");
    void card.offsetWidth;
    card.classList.add("tour-pop");
    if (current) {
      current.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
      setTimeout(place, reduceMotion ? 0 : 380); // after the scroll settles
    }
    place();
    card.focus({ preventScroll: true });
  }

  function go(i, dir) {
    dir = dir || (i >= index ? 1 : -1); // which way we're moving
    if (i < 0) { if (dir < 0) go(0, 1); return; } // backed off the start: show the first real step
    if (i >= steps.length) { finish(); return; }
    var step = steps[i];
    // An optional step whose button isn't on the page (e.g. Google sign-in is off): skip it,
    // in the same direction we were going.
    if (step.optional && onThisPage(step) && !findTarget(step)) {
      go(i + dir, dir);
      return;
    }
    if (!onThisPage(step)) {
      store(KEY, i + "|" + Date.now()); // continue there after the page loads
      location.href = step.path;
      return;
    }
    show(i);
  }

  function start(at) {
    if (!layer) build();
    lastFocus = document.activeElement;
    layer.classList.add("open");
    document.documentElement.classList.add("tour-open");
    index = at || 0;
    go(at || 0, 1);
  }

  function finish() {
    store(KEY, null);
    store(SEEN, "1");
    if (layer) layer.classList.remove("open");
    document.documentElement.classList.remove("tour-open");
    current = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener("keydown", function (e) {
    if (!layer || !layer.classList.contains("open")) return;
    if (e.key === "Escape") { e.preventDefault(); finish(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); go(index + 1, 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(index - 1, -1); }
    else if (e.key === "Tab") {
      // Keep the keyboard inside the card while the tour is open.
      var items = card.querySelectorAll("button:not([hidden])");
      var first = items[0], last = items[items.length - 1];
      var inside = Array.prototype.indexOf.call(items, document.activeElement) >= 0;
      if (!inside) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
      else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener("resize", place);
  window.addEventListener("scroll", place, { passive: true });

  // Buttons anywhere on the site: <button data-tour-start> or data-tour-start="3" (a step number).
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-tour-start]");
    if (!trigger || trigger.dataset.tourName && trigger.dataset.tourName !== data.name) return;
    e.preventDefault();
    start(parseInt(trigger.dataset.tourStart, 10) || 0);
  });

  // Continue a tour that moved to this page, or start it once for a new account.
  // A tour left half-way only comes back within 10 minutes, not days later.
  var parts = (read(KEY) || "").split("|");
  var saved = parseInt(parts[0], 10);
  var fresh = Date.now() - (parseInt(parts[1], 10) || 0) < 10 * 60 * 1000;
  if (!isNaN(saved) && fresh && steps[saved] && onThisPage(steps[saved])) {
    start(saved);
  } else if (/[?&]tour=1\b/.test(location.search)) {
    start(0); // a "Show me how" link from the guide page
  } else if (document.querySelector("[data-tour-autostart]") && !read(SEEN)) {
    store(SEEN, "1"); // once: if they leave half-way, it waits in the menu instead of popping up again
    start(0);
  }
})();
