// Food roulette (templates/roulette.html).
// 1. Draw the wheel: each place is a slice, its size = its weight for the chosen
//    mode ("usual" = visits, "different" = days since the last visit).
// 2. Spin: pick the winner first (a weighted random pick), then turn the wheel so
//    the pointer at the top lands inside the winner's slice. CSS animates the turn.
(function () {
  "use strict";
  var root = document.querySelector("[data-roulette]");
  var dataTag = document.getElementById("roulette-data");
  if (!root || !dataTag) return;

  var data = JSON.parse(dataTag.textContent);
  var places = data.places;
  var words = data.words;
  var wheel = root.querySelector("[data-wheel]");
  var button = root.querySelector("[data-spin]");
  var result = root.querySelector("[data-result]");
  var COLORS = ["#7c5cff", "#f26b3a", "#22b07d", "#f5b82e", "#3a8df2", "#e0507a", "#9b6bd6", "#16a3a3"];
  var rotation = 0;
  var slices = []; // [{start, end}] in degrees, clockwise from the top

  function mode() {
    var checked = root.querySelector('input[name="mode"]:checked');
    return checked ? checked.value : "usual";
  }

  function draw() {
    var weights = places.map(function (p) { return p[mode()]; });
    var total = weights.reduce(function (a, b) { return a + b; }, 0);
    var angle = 0;
    var stops = [];
    slices = [];
    wheel.innerHTML = "";
    places.forEach(function (place, i) {
      var size = 360 * weights[i] / total;
      var color = COLORS[i % COLORS.length];
      stops.push(color + " " + angle + "deg " + (angle + size) + "deg");
      slices.push({ start: angle, end: angle + size });
      if (size >= 12) { // a name doesn't fit in a thinner slice
        var label = document.createElement("span");
        label.className = "wheel-label";
        label.textContent = place.name;
        label.style.transform = "rotate(" + (angle + size / 2 - 90) + "deg)";
        wheel.appendChild(label);
      }
      angle += size;
    });
    wheel.style.background = "conic-gradient(" + stops.join(", ") + ")";
  }

  function pickWinner() {
    var weights = places.map(function (p) { return p[mode()]; });
    var total = weights.reduce(function (a, b) { return a + b; }, 0);
    var r = Math.random() * total;
    for (var i = 0; i < weights.length; i++) {
      r -= weights[i];
      if (r < 0) return i;
    }
    return weights.length - 1;
  }

  function show(i) {
    var p = places[i];
    var details = [p.visits + " " + words.visits];
    if (p.days_ago !== null) details.push(words.last + " " + p.days_ago + " " + words.daysAgo);
    if (p.average_text) details.push(words.about + " " + p.currency + " " + p.average_text);
    result.innerHTML = "";
    var title = document.createElement("strong");
    title.textContent = words.go + " " + p.name + "! 🍜";
    var small = document.createElement("small");
    small.textContent = details.join(" · ");
    result.appendChild(title);
    result.appendChild(small);
    result.classList.remove("pop");
    void result.offsetWidth; // restart the pop animation
    result.classList.add("pop");
  }

  button.addEventListener("click", function () {
    var winner = pickWinner();
    var slice = slices[winner];
    // Land somewhere inside the slice, not always dead centre (looks more real).
    var landAt = slice.start + (slice.end - slice.start) * (0.2 + Math.random() * 0.6);
    var now = ((rotation % 360) + 360) % 360;
    rotation += 5 * 360 + ((360 - landAt - now) % 360 + 360) % 360;
    button.disabled = true;
    result.textContent = "";
    wheel.style.transform = "rotate(" + rotation + "deg)";
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(function () {
      button.disabled = false;
      show(winner);
    }, reduce ? 50 : 4600); // the CSS turn lasts 4.5 s
  });

  root.querySelectorAll('input[name="mode"]').forEach(function (input) {
    input.addEventListener("change", draw);
  });
  draw();
})();
