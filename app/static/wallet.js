// Bills page (templates/bills/list.html): the card holder and the upload drop zone.
//
// Card holder: the cards sit in a stack. Swipe the front card sideways (or use
// the ‹ › buttons or arrow keys) and it slides off, then tucks in at the back.
// Without this script the cards simply sit in a row that scrolls sideways.
//
// Drop zone: drag a file onto it, or click it; the chosen file's name shows.
(function () {
  "use strict";
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- card holder ----------
  var stack = document.querySelector("[data-wallet]");
  var cards = stack ? Array.prototype.slice.call(stack.querySelectorAll("[data-wallet-card]")) : [];
  if (stack && cards.length > 1) {
    var dotsBox = document.querySelector("[data-wallet-dots]");
    var active = 0;
    var busy = false;
    stack.classList.add("is-stacked");
    stack.tabIndex = 0;

    var dots = cards.map(function () {
      var dot = document.createElement("i");
      if (dotsBox) dotsBox.appendChild(dot);
      return dot;
    });

    // pos 0 = the front card; 1, 2 peek out behind it; the rest wait hidden.
    function layout() {
      cards.forEach(function (card, i) {
        var pos = (i - active + cards.length) % cards.length;
        card.dataset.pos = Math.min(pos, 3);
        card.setAttribute("aria-hidden", pos === 0 ? "false" : "true");
        card.querySelectorAll("button").forEach(function (b) { b.tabIndex = pos === 0 ? 0 : -1; });
        card.style.transform = "";
      });
      dots.forEach(function (dot, i) { dot.classList.toggle("on", i === active); });
    }

    // Slide the front card off to one side, then bring the next one forward.
    function move(dir) {
      if (busy) return;
      var front = cards[active];
      var done = function () {
        front.classList.remove("swipe-left", "swipe-right");
        active = (active + (dir > 0 ? 1 : cards.length - 1)) % cards.length;
        layout();
        busy = false;
      };
      if (reduceMotion) { done(); return; }
      busy = true;
      front.classList.add(dir > 0 ? "swipe-left" : "swipe-right");
      setTimeout(done, 320);
    }

    var prev = document.querySelector("[data-wallet-prev]");
    var next = document.querySelector("[data-wallet-next]");
    if (prev) prev.addEventListener("click", function () { move(-1); });
    if (next) next.addEventListener("click", function () { move(1); });
    stack.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); move(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); move(-1); }
    });

    // Swipe: the front card follows the finger; let go far enough and it flies off.
    var drag = null;
    stack.addEventListener("pointerdown", function (e) {
      var front = cards[active];
      if (busy || !front.contains(e.target) || e.target.closest("button, form")) return;
      drag = { x: e.clientX, id: e.pointerId, card: front, dx: 0 };
      front.classList.add("dragging");
      try { front.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    });
    stack.addEventListener("pointermove", function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      drag.dx = e.clientX - drag.x;
      drag.card.style.transform = "translateX(" + drag.dx + "px) rotate(" + (drag.dx / 18) + "deg)";
    });
    function endDrag(e) {
      if (!drag || e.pointerId !== drag.id) return;
      var dx = drag.dx;
      drag.card.classList.remove("dragging");
      drag.card.style.transform = "";
      drag = null;
      if (Math.abs(dx) > 60) move(dx < 0 ? 1 : -1);
    }
    stack.addEventListener("pointerup", endDrag);
    stack.addEventListener("pointercancel", endDrag);

    layout();
  }

  // ---------- upload drop zone ----------
  var zone = document.querySelector("[data-drop]");
  var input = zone && zone.querySelector("input[type=file]");
  var nameEl = zone && zone.querySelector("[data-drop-name]");
  if (zone && input && nameEl) {
    var showName = function () {
      if (input.files && input.files[0]) {
        nameEl.textContent = "📎 " + input.files[0].name;
        zone.classList.add("has-file");
      }
    };
    input.addEventListener("change", showName);
    ["dragenter", "dragover"].forEach(function (type) {
      zone.addEventListener(type, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (type) {
      zone.addEventListener(type, function () { zone.classList.remove("is-over"); });
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        showName();
      }
    });
  }

  // "Remove this card?" before the form is sent.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
})();
