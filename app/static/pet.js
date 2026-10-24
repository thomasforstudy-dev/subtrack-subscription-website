// Subby the pet (templates/_pet.html): the little mascot on the chat button
// comes alive. It blinks and breathes, its eyes follow the pointer (a gentle
// 2.5D tilt), it reacts to what Subby is doing (listening / thinking / talking /
// happy), it dozes off when the page is idle, and now and then it pops a short,
// page-aware tip in its speech bubble. All of it is optional eye-candy: if this
// script does nothing, the chat button still works.
(function () {
  "use strict";
  var fab = document.querySelector("[data-pet]");
  var pet = fab && fab.querySelector(".pet");
  if (!fab || !pet) return;

  var root = document.querySelector("[data-subby]");
  var bubble = root && root.querySelector("[data-teaser]");
  var tipEl = bubble && bubble.querySelector("[data-pet-tip]");
  var EN = document.documentElement.getAttribute("lang") === "en";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function tr(vi, en) { return EN ? en : vi; }

  // ---- Mood: one class on the pet at a time ----
  var MOODS = ["idle", "look", "listening", "thinking", "talking", "happy", "sleeping"];
  var mood = "idle";
  var holdUntil = 0; // a short-lived mood (happy) is kept until this time

  function setMood(next, holdMs) {
    if (Date.now() < holdUntil && next !== "happy" && next !== "talking") return;
    mood = next;
    holdUntil = holdMs ? Date.now() + holdMs : 0;
    MOODS.forEach(function (m) { pet.classList.toggle("is-" + m, m === next); });
  }
  setMood("idle");

  // Subby tells us how it feels (static/subby.js dispatches "subby:mood").
  document.addEventListener("subby:mood", function (e) {
    var m = e.detail && e.detail.mood;
    if (m === "thinking") setMood("thinking");
    else if (m === "speaking") setMood("talking");
    else if (m === "listening") setMood("listening");
    else if (m === "open") { hideBubble(); setMood("happy", 1200); }
    else if (m === "idle") {
      // A reply just landed: a quick happy wiggle, then back to calm.
      if (mood === "thinking" || mood === "talking") setMood("happy", 1300);
      else setMood("idle");
    }
  });

  // ---- Eyes follow the pointer; the head tilts a little (the 2.5D feel) ----
  var lastMove = Date.now();
  function aim(x, y) {
    var box = fab.getBoundingClientRect();
    var dx = (x - (box.left + box.width / 2)) / window.innerWidth;
    var dy = (y - (box.top + box.height / 2)) / window.innerHeight;
    dx = Math.max(-1, Math.min(1, dx * 2.2));
    dy = Math.max(-1, Math.min(1, dy * 2.2));
    pet.style.setProperty("--look-x", dx.toFixed(3));
    pet.style.setProperty("--look-y", dy.toFixed(3));
  }
  if (!reduce) {
    window.addEventListener("pointermove", function (e) {
      lastMove = Date.now();
      if (mood === "sleeping") setMood("idle");
      if (mood === "idle" || mood === "look") {
        setMood("look");
        aim(e.clientX, e.clientY);
      }
    }, { passive: true });
  }

  // Doze off after a while of no movement (only when calm).
  if (!reduce) {
    setInterval(function () {
      if ((mood === "idle" || mood === "look") && Date.now() - lastMove > 45000) {
        pet.style.removeProperty("--look-x");
        pet.style.removeProperty("--look-y");
        setMood("sleeping");
      } else if (mood === "look" && Date.now() - lastMove > 2500) {
        setMood("idle"); // stop staring, go back to a neutral face
      }
    }, 2500);
  }

  // ---- Page-aware tips in the speech bubble ----
  function tipFor(path) {
    if (/\/dashboard/.test(path)) return tr("Mẹo: bấm một ô số để xem chi tiết.", "Tip: tap a number tile to dig in.");
    if (/\/subscriptions\/new/.test(path)) return tr("Chọn một dịch vụ để điền sẵn giúp bạn!", "Pick a service and I'll fill it in!");
    if (/\/subscriptions/.test(path)) return tr("Mình nhắc bạn trước mỗi lần gia hạn nhé.", "I'll nudge you before each renewal.");
    if (/\/bills/.test(path)) return tr("Tải hóa đơn lên, mình đọc giúp cho.", "Upload a bill and I'll read it for you.");
    if (/\/links/.test(path)) return tr("Lưu trang hủy gói ở đây cho khỏi quên.", "Keep your cancel pages here.");
    if (/\/calendar/.test(path)) return tr("Thêm ngày gia hạn vào lịch của bạn.", "Add renewal dates to your calendar.");
    if (/\/tools\/forecast/.test(path)) return tr("Mình đoán bạn sắp mua gì đấy. 🔮", "I can guess what you'll buy next. 🔮");
    if (/\/tools\/read-aloud/.test(path)) return tr("Đưa mình tệp, mình đọc to cho nghe.", "Give me a file and I'll read it aloud.");
    if (/\/tools\/food-roulette/.test(path)) return tr("Không biết ăn gì? Quay thử nào!", "Can't decide where to eat? Spin!");
    if (/\/tools/.test(path)) return tr("Ba công cụ AI đang đợi bạn thử. ✨", "Three AI tools waiting for you. ✨");
    if (/\/settings/.test(path)) return tr("Nhớ bật email nhắc nhé!", "Don't forget to turn on email reminders!");
    if (/\/guide/.test(path)) return tr("Bấm 'Chỉ cho tôi' để mình dẫn đường.", "Hit 'Show me' and I'll walk you through.");
    if (path === "/" || /\/(login|register)/.test(path)) return tr("Chào bạn! Cần dẫn đi một vòng không? 👋", "Hi! Want a quick tour? 👋");
    return null;
  }

  function showBubble(text) {
    if (!bubble || !tipEl || root.classList.contains("open")) return;
    tipEl.textContent = text;
    bubble.classList.add("show");
  }
  function hideBubble() {
    if (bubble) bubble.classList.remove("show");
  }
  var dismiss = bubble && bubble.querySelector("[data-pet-dismiss]");
  if (dismiss) {
    dismiss.addEventListener("click", function (e) {
      e.stopPropagation();
      hideBubble();
      try { sessionStorage.setItem("pet-bubble-off", "1"); } catch (err) { /* ignore */ }
    });
  }

  // Wave hello and show one tip a few seconds after the page settles — once per
  // page per browsing session, and never while the chat is open or dismissed.
  var muted = false;
  try { muted = sessionStorage.getItem("pet-bubble-off") === "1"; } catch (e) { muted = false; }
  var seenKey = "pet-tip:" + location.pathname;
  var seen = false;
  try { seen = sessionStorage.getItem(seenKey) === "1"; } catch (e) { seen = false; }

  if (!reduce) setMood("happy", 1600); // a little wave on arrival
  if (!muted && !seen) {
    setTimeout(function () {
      var tip = tipFor(location.pathname);
      if (tip && !root.classList.contains("open")) {
        showBubble(tip);
        try { sessionStorage.setItem(seenKey, "1"); } catch (e) { /* ignore */ }
        setTimeout(hideBubble, 7000);
      }
    }, 3500);
  }

  // Random slow blink is pure CSS; a rare "look around" keeps it lively.
  if (!reduce) {
    setInterval(function () {
      if (mood === "idle" && Math.random() < 0.3) setMood("look", 900);
    }, 6000);
  }
})();
