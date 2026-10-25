// Food case spin (templates/tools/case_spin.html): like opening a game case.
// A long strip of item cards slides past a marker and slows to a stop on the
// winner. The user's food and drink lists live in this browser (localStorage).
(function () {
  "use strict";
  var root = document.querySelector("[data-case-game]");
  var dataTag = document.getElementById("case-data");
  if (!root || !dataTag) return;
  var data = JSON.parse(dataTag.textContent);
  var W = data.words;
  var KEY = "case-spin-lists";
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Rarity is only for looks, like the colours in a game case: rarer = less likely.
  var RARITY = [
    { name: "blue", weight: 60 },
    { name: "purple", weight: 24 },
    { name: "pink", weight: 10 },
    { name: "red", weight: 5 },
    { name: "gold", weight: 1 },
  ];
  var TILE_COUNT = 56, WIN_AT = 48; // the winner sits near the end of the strip

  var lists = load();
  var spinning = false;

  function load() {
    try {
      var saved = JSON.parse(localStorage.getItem(KEY) || "null");
      if (saved && Array.isArray(saved.food) && Array.isArray(saved.drink)) return saved;
    } catch (e) { /* private mode or bad data: use the samples */ }
    return { food: data.defaults.food.slice(), drink: data.defaults.drink.slice() };
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(lists)); } catch (e) { /* not saved, still works */ }
  }

  function randomInt(n) { return Math.floor(Math.random() * n); }
  function pickRarity() {
    var roll = Math.random() * 100;
    for (var i = 0; i < RARITY.length; i++) { roll -= RARITY[i].weight; if (roll < 0) return RARITY[i].name; }
    return "blue";
  }

  function renderLists() {
    ["food", "drink"].forEach(function (cat) {
      var ul = root.querySelector('[data-list="' + cat + '"]');
      ul.innerHTML = "";
      lists[cat].forEach(function (item, i) {
        var li = document.createElement("li");
        var span = document.createElement("span");
        span.textContent = item;
        var x = document.createElement("button");
        x.type = "button";
        x.className = "chip-x";
        x.textContent = "×";
        x.setAttribute("aria-label", W.remove + " " + item);
        x.dataset.remove = cat + ":" + i;
        li.appendChild(span); li.appendChild(x);
        ul.appendChild(li);
      });
      root.querySelector('[data-count="' + cat + '"]').textContent = lists[cat].length;
    });
  }

  function mode() {
    var checked = root.querySelector('input[name="case-mode"]:checked');
    return checked ? checked.value : "food";
  }

  // One reel = a strip of random tiles with the (already chosen) winner at WIN_AT.
  function buildReel(items, winner) {
    var reel = document.createElement("div");
    reel.className = "case-reel";
    reel.innerHTML = '<span class="case-marker" aria-hidden="true"></span><div class="case-strip"></div>';
    var strip = reel.querySelector(".case-strip");
    var winRarity = pickRarity();
    for (var i = 0; i < TILE_COUNT; i++) {
      var tile = document.createElement("div");
      var rarity = i === WIN_AT ? winRarity : pickRarity();
      tile.className = "case-tile r-" + rarity;
      tile.textContent = i === WIN_AT ? winner : items[randomInt(items.length)];
      strip.appendChild(tile);
    }
    return { el: reel, strip: strip, rarity: winRarity };
  }

  function preview() {
    // A still strip before the first spin, so the stage isn't empty.
    var reels = root.querySelector("[data-reels]");
    reels.innerHTML = "";
    var cats = mode() === "combo" ? ["food", "drink"] : [mode()];
    cats.forEach(function (cat) {
      var items = lists[cat].length ? lists[cat] : ["?"];
      reels.appendChild(buildReel(items, items[0]).el);
    });
  }

  function spin() {
    if (spinning) return;
    var cats = mode() === "combo" ? ["food", "drink"] : [mode()];
    for (var c = 0; c < cats.length; c++) {
      if (lists[cats[c]].length < 2) { root.querySelector("[data-case-result]").textContent = W.need; return; }
    }
    spinning = true;
    root.querySelector("[data-open-case]").disabled = true;
    var result = root.querySelector("[data-case-result]");
    result.textContent = ""; result.className = "case-result";
    var reelsBox = root.querySelector("[data-reels]");
    reelsBox.innerHTML = "";
    var winners = [], rare = false, built = [];
    cats.forEach(function (cat) {
      var winner = lists[cat][randomInt(lists[cat].length)];
      winners.push(winner);
      var reel = buildReel(lists[cat], winner);
      if (reel.rarity === "gold" || reel.rarity === "red") rare = true;
      reelsBox.appendChild(reel.el);
      built.push(reel);
    });
    var duration = reduceMotion ? 0 : 5200;
    requestAnimationFrame(function () {
      built.forEach(function (reel, n) {
        var tile = reel.strip.children[WIN_AT];
        var box = reel.el.getBoundingClientRect();
        // Stop somewhere inside the winning tile, not always dead centre (feels less rigged).
        var jitter = (Math.random() - 0.5) * tile.offsetWidth * 0.6;
        var offset = tile.offsetLeft + tile.offsetWidth / 2 - box.width / 2 + jitter;
        reel.strip.style.transition = duration ? "transform " + (duration + n * 600) + "ms cubic-bezier(0.12, 0.8, 0.2, 1)" : "none";
        reel.strip.style.transform = "translateX(" + (-offset) + "px)";
      });
      setTimeout(function () {
        built.forEach(function (reel) { reel.strip.children[WIN_AT].classList.add("is-winner"); });
        result.textContent = W.pick + ": " + winners.join(" " + W.and + " ") + (rare ? " ✨ " + W.rare : "") + " 🎉";
        result.classList.add("show");
        spinning = false;
        root.querySelector("[data-open-case]").disabled = false;
      }, duration ? duration + (built.length - 1) * 600 + 100 : 0);
    });
  }

  root.addEventListener("click", function (e) {
    var rm = e.target.closest("[data-remove]");
    if (rm) {
      var parts = rm.dataset.remove.split(":");
      lists[parts[0]].splice(parseInt(parts[1], 10), 1);
      save(); renderLists(); if (!spinning) preview();
    } else if (e.target.closest("[data-open-case]")) {
      spin();
    } else if (e.target.closest("[data-case-defaults]")) {
      lists = { food: data.defaults.food.slice(), drink: data.defaults.drink.slice() };
      save(); renderLists(); if (!spinning) preview();
    }
  });

  root.querySelector("[data-case-add]").addEventListener("submit", function (e) {
    e.preventDefault();
    var input = root.querySelector("#case-item");
    var cat = root.querySelector("#case-cat").value;
    var name = input.value.trim().slice(0, 40);
    if (!name) return;
    var exists = lists[cat].some(function (x) { return x.toLowerCase() === name.toLowerCase(); });
    if (exists) { root.querySelector("[data-case-result]").textContent = W.dup; return; }
    lists[cat].push(name);
    input.value = "";
    save(); renderLists(); if (!spinning) preview();
  });

  root.querySelectorAll('input[name="case-mode"]').forEach(function (r) {
    r.addEventListener("change", function () { if (!spinning) preview(); });
  });

  renderLists();
  preview();
})();
