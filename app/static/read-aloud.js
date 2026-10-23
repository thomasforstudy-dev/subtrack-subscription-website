// Read aloud (templates/read_aloud.html): plays the text one paragraph at a time.
// Gemini voice: each paragraph is sent to /tools/read-aloud/speak and comes back as
// a .wav; the next one is fetched while the current one plays, so there is no gap.
// If Gemini is busy or out of free quota, it switches to the browser's own voice.
(function () {
  "use strict";
  var root = document.querySelector("[data-reader]");
  if (!root) return;

  var EN = document.documentElement.getAttribute("lang") === "en";
  function tr(vi, en) { return EN ? en : vi; }

  var parts = Array.prototype.slice.call(root.querySelectorAll("[data-reader-part]"));
  var playBtn = root.querySelector("[data-reader-play]");
  var status = root.querySelector("[data-reader-status]");
  var voiceSelect = root.querySelector("[data-reader-voice]");
  var speedSelect = root.querySelector("[data-reader-speed]");
  var csrf = document.querySelector('meta[name="csrf-token"]');
  var audio = new Audio();
  var cache = {}; // paragraph number -> Promise of an audio URL
  var index = 0;
  var state = "stopped"; // "stopped" | "playing" | "paused"
  var useBrowser = false; // true after Gemini failed, or when picked
  var run = 0; // bumps on every start/stop, so late answers from an old run are ignored

  var VI_LETTERS = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;

  function say(text) { status.textContent = text; }
  function speed() { return parseFloat(speedSelect.value) || 1; }
  function browserPicked() { return useBrowser || voiceSelect.value === "browser"; }

  function setButton() {
    playBtn.textContent = state === "playing" ? "⏸ " + tr("Tạm dừng", "Pause") : "▶ " + tr("Nghe", "Play");
  }

  function mark(i) {
    parts.forEach(function (p, n) { p.classList.toggle("is-reading", n === i); });
    parts[i].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function fetchAudio(i) {
    if (!cache[i]) {
      var headers = { "Content-Type": "application/json" };
      if (csrf) headers["X-CSRF-Token"] = csrf.content;
      cache[i] = fetch(root.dataset.speakUrl, {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ text: parts[i].textContent, voice: voiceSelect.value }),
      }).then(function (res) {
        if (!res.ok) throw new Error(String(res.status));
        return res.blob();
      }).then(function (blob) { return URL.createObjectURL(blob); });
      cache[i].catch(function () { delete cache[i]; });
    }
    return cache[i];
  }

  function clearCache() {
    Object.keys(cache).forEach(function (k) {
      cache[k].then(function (url) { URL.revokeObjectURL(url); }, function () {});
    });
    cache = {};
  }

  function finished(myRun) {
    if (myRun !== run) return;
    if (index + 1 < parts.length) {
      playFrom(index + 1);
    } else {
      stop();
      say(tr("Đã đọc xong.", "Finished reading."));
    }
  }

  function speakWithBrowser(i, myRun) {
    if (!("speechSynthesis" in window)) {
      stop();
      say(tr("Trình duyệt này không có giọng đọc.", "This browser has no voice."));
      return;
    }
    var text = parts[i].textContent;
    var u = new SpeechSynthesisUtterance(text);
    u.lang = VI_LETTERS.test(text) ? "vi-VN" : "en-US";
    u.rate = speed();
    u.onend = function () { finished(myRun); };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
    say(tr("Đang đọc bằng giọng trình duyệt: đoạn ", "Reading with the browser voice: paragraph ") + (i + 1) + "/" + parts.length);
  }

  function playFrom(i) {
    run += 1;
    var myRun = run;
    index = i;
    state = "playing";
    setButton();
    mark(i);
    audio.pause();
    if (browserPicked()) {
      speakWithBrowser(i, myRun);
      return;
    }
    say(tr("Gemini đang tạo giọng đọc cho đoạn ", "Gemini is making the voice for paragraph ") + (i + 1) + "…");
    fetchAudio(i).then(function (url) {
      if (myRun !== run) return;
      audio.src = url;
      audio.playbackRate = speed();
      audio.onended = function () { finished(myRun); };
      return audio.play().then(function () {
        say(tr("Gemini đang đọc: đoạn ", "Gemini is reading: paragraph ") + (i + 1) + "/" + parts.length);
        if (i + 1 < parts.length) fetchAudio(i + 1).catch(function () {}); // get the next one ready
      });
    }).catch(function (error) {
      if (myRun !== run) return;
      if (error && error.name === "NotAllowedError") {
        // The browser blocked sound until the user clicks; wait for Play.
        state = "paused";
        setButton();
        say(tr("Bấm Nghe để bắt đầu.", "Press Play to start."));
        return;
      }
      useBrowser = true; // Gemini busy, out of quota or offline
      say(tr("Gemini đang bận, chuyển sang giọng của trình duyệt.", "Gemini is busy, switching to the browser voice."));
      speakWithBrowser(i, myRun);
    });
  }

  function stop() {
    run += 1;
    state = "stopped";
    audio.pause();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    parts.forEach(function (p) { p.classList.remove("is-reading"); });
    setButton();
  }

  playBtn.addEventListener("click", function () {
    if (state === "playing") {
      state = "paused";
      if (browserPicked()) window.speechSynthesis.pause(); else audio.pause();
      say(tr("Đã tạm dừng.", "Paused."));
    } else if (state === "paused") {
      state = "playing";
      if (browserPicked()) window.speechSynthesis.resume(); else audio.play().catch(function () { playFrom(index); });
      say(tr("Đang đọc tiếp.", "Reading on."));
    } else {
      playFrom(index);
    }
    setButton();
  });
  root.querySelector("[data-reader-stop]").addEventListener("click", function () {
    stop();
    index = 0;
    say(tr("Đã dừng.", "Stopped."));
  });
  root.querySelector("[data-reader-prev]").addEventListener("click", function () { playFrom(Math.max(index - 1, 0)); });
  root.querySelector("[data-reader-next]").addEventListener("click", function () { playFrom(Math.min(index + 1, parts.length - 1)); });

  parts.forEach(function (p, i) {
    p.addEventListener("click", function () { playFrom(i); });
    p.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); playFrom(i); }
    });
  });

  voiceSelect.addEventListener("change", function () {
    useBrowser = false; // a new pick gets a fresh try
    clearCache();
    if (state === "playing") playFrom(index);
  });
  speedSelect.addEventListener("change", function () {
    audio.playbackRate = speed();
    if (state === "playing" && browserPicked()) playFrom(index); // the browser voice can't change speed mid-sentence
  });
  setButton();
})();
