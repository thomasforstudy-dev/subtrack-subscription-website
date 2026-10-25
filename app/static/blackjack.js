// Blackjack vs an AI dealer (templates/tools/blackjack.html).
// One 52-card deck. The dealer follows house rules (draws to 16, stands on 17)
// and the odds panel shows, for every rank, the chance it's the next card,
// counted over all cards the player hasn't seen yet. Points only, all in the browser.
(function () {
  "use strict";
  var root = document.querySelector("[data-blackjack]");
  var dataTag = document.getElementById("bj-data");
  if (!root || !dataTag) return;
  var W = JSON.parse(dataTag.textContent).words;

  var RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
  var SUITS = ["♠", "♥", "♦", "♣"];
  var $ = function (sel) { return root.querySelector(sel); };

  var deck = [], player = [], dealer = [], holeHidden = true;
  var bank = 1000, bet = 100, stake = 0, playing = false; // stake = points riding on this hand

  function rankValue(rank) {
    if (rank === "A") return 11;
    if (rank === "J" || rank === "Q" || rank === "K") return 10;
    return parseInt(rank, 10);
  }

  // Best total for a hand: aces count 11 unless that would bust, then 1.
  function handValue(cards) {
    var total = 0, aces = 0;
    cards.forEach(function (c) { total += rankValue(c.rank); if (c.rank === "A") aces += 1; });
    while (total > 21 && aces > 0) { total -= 10; aces -= 1; }
    return { total: total, soft: aces > 0 };
  }

  function newDeck() {
    deck = [];
    SUITS.forEach(function (s) { RANKS.forEach(function (r) { deck.push({ rank: r, suit: s }); }); });
    for (var i = deck.length - 1; i > 0; i--) { // Fisher–Yates shuffle
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = deck[i]; deck[i] = deck[j]; deck[j] = tmp;
    }
  }

  function talk(text) { $("[data-talk]").textContent = text; }

  function cardEl(card, hidden) {
    var el = document.createElement("div");
    el.className = "playing-card" + (hidden ? " is-back" : "") + (card.suit === "♥" || card.suit === "♦" ? " is-red" : "");
    if (!hidden) {
      el.innerHTML = '<span class="pc-rank"></span><span class="pc-suit"></span>';
      el.querySelector(".pc-rank").textContent = card.rank;
      el.querySelector(".pc-suit").textContent = card.suit;
      el.setAttribute("aria-label", card.rank + card.suit);
    } else {
      el.setAttribute("aria-label", "?");
    }
    return el;
  }

  function renderHands() {
    var ph = $("[data-player-hand]"), dh = $("[data-dealer-hand]");
    ph.innerHTML = ""; dh.innerHTML = "";
    player.forEach(function (c) { ph.appendChild(cardEl(c, false)); });
    dealer.forEach(function (c, i) { dh.appendChild(cardEl(c, i === 1 && holeHidden)); });
    var pv = handValue(player);
    $("[data-player-total]").textContent = player.length ? pv.total + (pv.soft && pv.total < 21 ? " (soft)" : "") : "";
    var shown = holeHidden ? dealer.slice(0, 1) : dealer;
    $("[data-dealer-total]").textContent = dealer.length ? handValue(shown).total + (holeHidden ? " + ?" : "") : "";
    $("[data-bank]").textContent = bank;
    $("[data-bet-now]").textContent = playing ? stake : bet;
    $("[data-deck-left]").textContent = deck.length;
    renderOdds();
  }

  // The cards the player can't see: what's left in the deck plus the dealer's hole card.
  function unseenCards() {
    var unseen = deck.slice();
    if (holeHidden && dealer[1]) unseen.push(dealer[1]);
    return unseen;
  }

  // Simple "basic strategy" for one deck: what a careful player would do here.
  function advice() {
    var pv = handValue(player);
    var up = rankValue(dealer[0].rank);
    if (pv.total >= 21) return W.stand;
    if (pv.soft) {
      if (pv.total >= 19) return W.stand;
      if (pv.total === 18) return up >= 9 ? W.hit : W.stand;
      return W.hit;
    }
    if (pv.total >= 17) return W.stand;
    if (pv.total >= 13) return up <= 6 ? W.stand : W.hit;
    if (pv.total === 12) return up >= 4 && up <= 6 ? W.stand : W.hit;
    if ((pv.total === 10 || pv.total === 11) && player.length === 2 && up < pv.total) return W.double + " (" + W.or + " " + W.hit + ")";
    return W.hit;
  }

  function renderOdds() {
    var body = $("[data-odds-rows]");
    body.innerHTML = "";
    var unseen = unseenCards();
    var counts = {};
    unseen.forEach(function (c) { counts[c.rank] = (counts[c.rank] || 0) + 1; });
    var bust = 0, hit21 = 0;
    RANKS.forEach(function (rank) {
      var n = counts[rank] || 0;
      var share = unseen.length ? n / unseen.length : 0;
      var row = document.createElement("tr");
      var after = "";
      if (playing && player.length) {
        var next = handValue(player.concat([{ rank: rank, suit: "♠" }])).total;
        if (next > 21) { bust += n; after = W.bust; row.className = "is-bust"; }
        else { after = String(next); if (next === 21) { hit21 += n; row.className = "is-21"; } }
      }
      var bar = '<span class="odds-mini" style="width:' + Math.round(share * 100) + '%"></span>';
      row.innerHTML = "<td><strong></strong></td><td></td><td>" + bar + "<span></span></td><td></td>";
      row.cells[0].firstChild.textContent = rank;
      row.cells[1].textContent = n;
      row.cells[2].lastChild.textContent = (share * 100).toFixed(1) + "%";
      row.cells[3].textContent = after;
      body.appendChild(row);
    });
    var live = playing && player.length && unseen.length;
    $("[data-bust]").textContent = live ? (bust / unseen.length * 100).toFixed(1) + "%" : "–";
    $("[data-hit21]").textContent = live ? (hit21 / unseen.length * 100).toFixed(1) + "%" : "–";
    $("[data-advice]").textContent = live ? advice() : "–";
  }

  function draw(hand) {
    hand.push(deck.pop());
  }

  function setPhase(isPlaying) {
    playing = isPlaying;
    $("[data-bet-area]").hidden = isPlaying;
    $("[data-play-area]").hidden = !isPlaying;
    $("[data-double]").disabled = !(isPlaying && player.length === 2 && bank >= stake);
  }

  function settle(message, payout) {
    bank += payout;
    holeHidden = false;
    setPhase(false);
    talk(message);
    if (bank < 50) { bank = 1000; talk(message + " " + W.broke); }
    renderHands();
  }

  function deal() {
    if (bank < bet) bet = Math.max(50, Math.floor(bank / 50) * 50);
    if (deck.length < 15) { newDeck(); talk(W.shuffle); }
    bank -= bet;
    stake = bet;
    player = []; dealer = []; holeHidden = true;
    draw(player); draw(dealer); draw(player); draw(dealer);
    setPhase(true);
    renderHands();
    var pv = handValue(player).total, dv = handValue(dealer).total;
    if (pv === 21 || dv === 21) {
      if (pv === 21 && dv === 21) settle(W.push, stake);
      else if (pv === 21) settle(W.bj_win, Math.floor(stake * 2.5));
      else settle(W.lose + " (" + W.blackjack + ")", 0);
      return;
    }
    talk(W.your_turn);
  }

  // The AI dealer's turn: show the hole card, then draw one card at a time.
  function dealerPlay() {
    holeHidden = false;
    setPhase(false);
    $("[data-bet-area]").hidden = true;
    renderHands();
    var step = function () {
      var dv = handValue(dealer).total;
      if (dv < 17) {
        talk(W.dealer_draws);
        draw(dealer);
        renderHands();
        setTimeout(step, 650);
        return;
      }
      var pv = handValue(player).total;
      if (dv > 21) settle(W.dealer_bust + " " + W.win + "!", stake * 2);
      else if (pv > dv) settle(W.dealer_stands + " " + dv + ". " + W.win + "!", stake * 2);
      else if (pv < dv) settle(W.dealer_stands + " " + dv + ". " + W.lose + ".", 0);
      else settle(W.dealer_stands + " " + dv + ". " + W.push + ".", stake);
    };
    setTimeout(step, 500);
  }

  root.addEventListener("click", function (e) {
    var chip = e.target.closest("[data-bet]");
    if (chip && !playing) {
      bet = parseInt(chip.dataset.bet, 10);
      root.querySelectorAll("[data-bet]").forEach(function (b) { b.classList.toggle("on", b === chip); });
      renderHands();
    } else if (e.target.closest("[data-deal]") && !playing) {
      deal();
    } else if (e.target.closest("[data-hit]") && playing) {
      draw(player);
      renderHands();
      $("[data-double]").disabled = true;
      var pv = handValue(player).total;
      if (pv > 21) settle(W.bust + "! " + W.lose + ".", 0);
      else if (pv === 21) dealerPlay();
    } else if (e.target.closest("[data-stand]") && playing) {
      dealerPlay();
    } else if (e.target.closest("[data-double]") && playing && bank >= stake) {
      // Double: put the same stake in again, take exactly one more card, then the dealer plays.
      bank -= stake; stake *= 2;
      draw(player);
      renderHands();
      if (handValue(player).total > 21) settle(W.bust + "! " + W.lose + ".", 0);
      else dealerPlay();
    }
  });

  $("[data-show-odds]").addEventListener("change", function (e) {
    $("[data-odds-body]").hidden = !e.target.checked;
  });

  newDeck();
  root.querySelector('[data-bet="100"]').classList.add("on");
  talk(W.hello);
  renderHands();
})();
