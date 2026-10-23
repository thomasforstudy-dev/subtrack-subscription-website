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
  var pageSelect = root.querySelector("[data-reader-page]");
  var progress = root.querySelector("[data-reader-progress]");
  var resumeBtn = root.querySelector("[data-reader-resume]");
  var saveKey = "read-aloud:" + (root.dataset.docKey || "");
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

  function where(i) {
    var page = parts[i].dataset.page;
    return tr("đoạn ", "part ") + (i + 1) + "/" + parts.length + (page ? " · " + tr("trang ", "page ") + page : "");
  }

  function mark(i) {
    var old = root.querySelector(".is-reading");
    if (old) old.classList.remove("is-reading");
    parts[i].classList.add("is-reading");
    parts[i].scrollIntoView({ block: "center", behavior: "smooth" });
    if (progress) progress.style.width = (100 * (i + 1) / parts.length) + "%";
    if (pageSelect) {
      // The page menu shows the page being read: the last page that starts at or before i.
      for (var k = pageSelect.options.length - 1; k >= 0; k--) {
        if (parseInt(pageSelect.options[k].value, 10) <= i) { pageSelect.selectedIndex = k; break; }
      }
    }
    try { localStorage.setItem(saveKey, String(i)); } catch (e) { /* private mode: no resume */ }
  }

  function forgetOldAudio(i) {
    // A long book has hundreds of parts: free the audio of parts already read.
    Object.keys(cache).forEach(function (k) {
      if (Number(k) < i - 1) {
        cache[k].then(function (url) { URL.revokeObjectURL(url); }, function () {});
        delete cache[k];
      }
    });
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
      try { localStorage.removeItem(saveKey); } catch (e) { /* ignore */ }
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
    say(tr("Đang đọc bằng giọng trình duyệt: ", "Reading with the browser voice: ") + where(i));
  }

  function playFrom(i) {
    run += 1;
    var myRun = run;
    index = i;
    state = "playing";
    setButton();
    mark(i);
    if (resumeBtn) resumeBtn.hidden = true;
    audio.pause();
    if (browserPicked()) {
      speakWithBrowser(i, myRun);
      return;
    }
    forgetOldAudio(i);
    say(tr("Gemini đang tạo giọng đọc: ", "Gemini is making the voice: ") + where(i) + "…");
    fetchAudio(i).then(function (url) {
      if (myRun !== run) return;
      audio.src = url;
      audio.playbackRate = speed();
      audio.onended = function () { finished(myRun); };
      return audio.play().then(function () {
        say(tr("Gemini đang đọc: ", "Gemini is reading: ") + where(i));
        // Get the next two parts ready, so there is no pause between them.
        for (var n = i + 1; n <= i + 2 && n < parts.length; n++) fetchAudio(n).catch(function () {});
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
  if (pageSelect) {
    pageSelect.addEventListener("change", function () { playFrom(parseInt(pageSelect.value, 10) || 0); });
  }

  // "Continue where you stopped": the last part started on this browser, for this file.
  var saved = null;
  try { saved = parseInt(localStorage.getItem(saveKey), 10); } catch (e) { saved = null; }
  if (resumeBtn && saved > 0 && saved < parts.length) {
    resumeBtn.textContent = "↻ " + tr("Đọc tiếp từ ", "Continue from ") + where(saved);
    resumeBtn.hidden = false;
    resumeBtn.addEventListener("click", function () { playFrom(saved); });
  }

  speedSelect.addEventListener("change", function () {
    audio.playbackRate = speed();
    if (state === "playing" && browserPicked()) playFrom(index); // the browser voice can't change speed mid-sentence
  });
  setButton();
})();
