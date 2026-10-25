// Coin flip game (templates/tools/coin_flip.html). Call heads or tails, or
// flip many times at once, and watch the percentages settle near 50%.
// Everything stays in the browser; nothing is sent to the server.
(function () {
  "use strict";
  var root = document.querySelector("[data-coin-game]");
  var dataTag = document.getElementById("coin-data");
  if (!root || !dataTag) return;
  var words = JSON.parse(dataTag.textContent).words;

  var coin = root.querySelector("[data-coin]");
  var result = root.querySelector("[data-coin-result]");
  var tip = root.querySelector("[data-coin-tip]");
  var historyList = root.querySelector("[data-coin-history]");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var state = { heads: 0, tails: 0, calls: 0, right: 0, streakSide: null, streak: 0, longest: 0, history: [], turns: 0 };
  var busy = false;

  // crypto gives a fair random bit; Math.random is the fallback for old browsers.
  function flipOnce() {
    if (window.crypto && window.crypto.getRandomValues) {
      var buf = new Uint8Array(1);
      window.crypto.getRandomValues(buf);
      return buf[0] % 2 === 0 ? "heads" : "tails";
    }
    return Math.random() < 0.5 ? "heads" : "tails";
  }

  function record(side) {
    state[side] += 1;
    if (state.streakSide === side) state.streak += 1;
    else { state.streakSide = side; state.streak = 1; }
    state.longest = Math.max(state.longest, state.streak);
    state.history.unshift(side);
    state.history = state.history.slice(0, 20);
  }

  function pct(n, total) {
    return total ? (n / total * 100).toFixed(1) + "%" : "0%";
  }

  function render() {
    var total = state.heads + state.tails;
    root.querySelector('[data-stat="heads"]').textContent = pct(state.heads, total);
    root.querySelector('[data-stat="tails"]').textContent = pct(state.tails, total);
    root.querySelector('[data-stat="flips"]').textContent = total.toLocaleString();
    root.querySelector('[data-stat="calls"]').textContent = state.calls ? pct(state.right, state.calls) + " (" + state.right + "/" + state.calls + ")" : "–";
    root.querySelector('[data-stat="streak"]').textContent = state.streak ? state.streak + " × " + words[state.streakSide] : "–";
    root.querySelector('[data-stat="longest"]').textContent = state.longest || "–";
    var headsShare = total ? state.heads / total * 100 : 50;
    root.querySelector("[data-bar-heads]").style.width = headsShare + "%";
    root.querySelector("[data-bar-tails]").style.width = (100 - headsShare) + "%";
    if (total < 10) tip.textContent = words.tip_start;
    else tip.textContent = Math.abs(headsShare - 50) < 3 ? words.tip_close : words.tip_far;
    historyList.innerHTML = "";
    state.history.forEach(function (side) {
      var li = document.createElement("li");
      li.className = "coin-dot " + side;
      li.textContent = words[side].charAt(0);
      li.title = words[side];
      historyList.appendChild(li);
    });
  }

  // Spin the coin so it lands showing `side` (CSS turns it with rotateY).
  function animate(side, done) {
    if (reduceMotion) { coin.dataset.side = side; done(); return; }
    state.turns += 5; // five full turns per flip, then the face we landed on
    var angle = state.turns * 360 + (side === "tails" ? 180 : 0);
    coin.classList.add("flipping");
    coin.style.transform = "rotateY(" + angle + "deg)";
    setTimeout(function () { coin.classList.remove("flipping"); done(); }, 900);
  }

  function setButtons(disabled) {
    root.querySelectorAll("button").forEach(function (b) { b.disabled = disabled; });
  }

  root.addEventListener("click", function (e) {
    var callBtn = e.target.closest("[data-call]");
    var manyBtn = e.target.closest("[data-many]");
    if (busy) return;
    if (callBtn) {
      var call = callBtn.dataset.call;
      var side = flipOnce();
      busy = true; setButtons(true);
      animate(side, function () {
        record(side);
        state.calls += 1;
        if (side === call) state.right += 1;
        result.textContent = words.landed + " " + words[side] + ". " + (side === call ? words.win : words.lose);
        result.classList.toggle("is-win", side === call);
        result.classList.toggle("is-lose", side !== call);
        render();
        busy = false; setButtons(false);
      });
    } else if (manyBtn) {
      var n = parseInt(manyBtn.dataset.many, 10);
      var last = "heads";
      for (var i = 0; i < n; i++) { last = flipOnce(); record(last); }
      animate(last, function () {});
      result.classList.remove("is-win", "is-lose");
      result.textContent = words.flipped + " " + n.toLocaleString() + " " + words.times + ".";
      render();
    } else if (e.target.closest("[data-coin-reset]")) {
      state = { heads: 0, tails: 0, calls: 0, right: 0, streakSide: null, streak: 0, longest: 0, history: [], turns: state.turns };
      result.classList.remove("is-win", "is-lose");
      result.textContent = words.start;
      render();
    }
  });

  render();
})();
