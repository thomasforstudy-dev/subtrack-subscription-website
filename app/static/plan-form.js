// Add / edit a plan (templates/subscriptions/form.html): service tiles fill the
// form, chips set the currency and reminder days, and a preview card shows the
// plan as it will look in the list. The form still posts the same fields.
(function () {
  "use strict";
  var form = document.getElementById("subscription-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var name = $("sub-name"), amount = $("sub-amount"), currency = $("sub-currency");
  var renewal = $("sub-renewal"), remind = $("sub-remind"), manage = $("sub-manage-url");

  // 1. Service tiles: one tap fills name, price, currency, cycle, reminders and cancel page.
  document.querySelectorAll("[data-preset-plan]").forEach(function (tile) {
    tile.addEventListener("click", function () {
      var p = JSON.parse(tile.dataset.presetPlan || "{}");
      document.querySelectorAll("[data-preset-plan]").forEach(function (t) {
        t.setAttribute("aria-pressed", String(t === tile));
      });
      name.value = p.name || "";
      if (!p.name) {
        // "Other": start clean, so a custom plan never keeps the last service's
        // price, reminders or cancel page.
        amount.value = "0";
        if (remind) remind.value = "7,3";
        if (manage) manage.value = "";
      }
      if (p.amount) amount.value = p.amount;
      if (p.currency) currency.value = p.currency;
      if (p.cycle) {
        var radio = form.querySelector('input[name="cycle"][value="' + p.cycle + '"]');
        if (radio) radio.checked = true;
      }
      if (p.remind && remind) remind.value = p.remind;
      if (p.manage_url && manage) manage.value = p.manage_url;
      name.focus();
      update();
    });
  });

  // 2. Currency chips.
  document.querySelectorAll("[data-set-currency]").forEach(function (chip) {
    chip.addEventListener("click", function () { currency.value = chip.dataset.setCurrency; update(); });
  });

  // 3. Reminder chips <-> the "14,7,3" box (at most 3 days; the server checks too).
  function days() {
    return (remind.value || "").split(",").map(function (d) { return parseInt(d, 10); })
      .filter(function (d) { return !isNaN(d); });
  }
  document.querySelectorAll("[data-remind-day]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var d = parseInt(chip.dataset.remindDay, 10);
      var list = days();
      var at = list.indexOf(d);
      if (at >= 0) list.splice(at, 1);
      else if (list.length < 3) list.push(d);
      list.sort(function (a, b) { return b - a; });
      remind.value = list.join(",");
      update();
    });
  });

  // 4. The preview card.
  var preview = document.querySelector("[data-plan-preview]");
  var words = preview ? JSON.parse(preview.dataset.words) : {};
  var VND_LIKE = { VND: 1, JPY: 1, KRW: 1, IDR: 1 }; // no cents

  function money(value, code) {
    var n = parseFloat(value) || 0;
    var cents = VND_LIKE[code] ? 0 : 2;
    return n.toLocaleString("en-US", { minimumFractionDigits: cents, maximumFractionDigits: cents });
  }

  function update() {
    var code = (currency.value || "").toUpperCase();
    document.querySelectorAll("[data-set-currency]").forEach(function (chip) {
      chip.classList.toggle("on", chip.dataset.setCurrency === code);
    });
    var chosen = days();
    document.querySelectorAll("[data-remind-day]").forEach(function (chip) {
      var on = chosen.indexOf(parseInt(chip.dataset.remindDay, 10)) >= 0;
      chip.classList.toggle("on", on);
      chip.setAttribute("aria-pressed", String(on));
    });
    if (!preview) return;
    var label = name.value.trim() || words.name;
    preview.querySelector("[data-preview-name]").textContent = label;
    preview.querySelector("[data-preview-logo]").textContent = label.charAt(0).toUpperCase();
    preview.querySelector("[data-preview-price]").textContent = money(amount.value, code) + " " + code;
    var cycle = form.querySelector('input[name="cycle"]:checked');
    var per = { weekly: words.week, monthly: words.month, yearly: words.year }[cycle ? cycle.value : "monthly"];
    preview.querySelector("[data-preview-cycle]").textContent = "/ " + per;
    var when = "";
    if (renewal.value) {
      var today = new Date(); today.setHours(0, 0, 0, 0);
      var left = Math.round((new Date(renewal.value + "T00:00:00") - today) / 86400000);
      when = left <= 0 ? words.today : words.in + " " + left + " " + words.days;
    }
    preview.querySelector("[data-preview-when]").textContent = when;
    preview.querySelector("[data-preview-remind]").textContent = chosen.length ? "🔔 " + words.remind + ": " + chosen.join(" · ") + " " + words.days : "";
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
