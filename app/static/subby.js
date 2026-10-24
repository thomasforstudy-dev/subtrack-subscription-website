// Subby: trợ lý trò chuyện hướng dẫn & tra cứu tài khoản.
// - Hỏi máy chủ trước (POST /subby/ask -> Gemini hoặc Phi-3.5-mini trên máy chủ).
// - Hiển thị trung thực provider (gemini / phi / fake) và cảnh báo rõ khi fallback sang mô hình đám mây (fallback: true).
// - Hiển thị an toàn kết quả Account Tools (list_upcoming_renewals, search_saved_links, summarize_transactions, create_reminder_draft) bằng DOM API (textContent), không bao giờ dùng innerHTML và không gửi dữ liệu riêng tư vào lịch sử hội thoại.
// - Chế độ Giọng nói (Web Speech API — SpeechRecognition & speechSynthesis):
//   + Chỉ xin quyền micro sau khi người dùng chủ động bấm nút Mic ([data-mic] hoặc [data-voice-orb]).
//   + Hỗ trợ đầy đủ 4 trạng thái (idle / listening / thinking / speaking), xem/chỉnh bản nháp lời nói trước khi gửi, đọc câu trả lời (TTS) theo ngôn ngữ VI/EN, và luôn giữ ô nhập bàn phím hoạt động song song.

(function () {
  "use strict";

  // The page language comes from the server (<html data-ui-lang>, app/i18n.py).
  // It is read on every call, so Subby always answers in the language shown.
  function tr(vi, en) {
    return document.documentElement.getAttribute("data-ui-lang") === "en" ? en : vi;
  }

  const root = document.querySelector("[data-subby]");
  if (!root) return;

  const panel = root.querySelector("#subby-panel");
  const openBtn = root.querySelector("[data-open]");
  const closeBtn = root.querySelector("[data-close]");
  const log = root.querySelector("[data-log]");
  const form = root.querySelector("[data-form]");
  const input = form.querySelector("input[name='q']");
  const funBox = root.querySelector("[data-fun]");
  const ttsAutoBox = root.querySelector("[data-tts-auto]");
  const ttsStopBtn = root.querySelector("[data-tts-stop]");
  const teaser = root.querySelector("[data-teaser]");
  const handoff = root.querySelector("[data-handoff]");
  const actionCardTpl = root.querySelector("[data-action-card]");
  const statusEl = root.querySelector("[data-subby-status]");
  const providerBadge = root.querySelector("[data-provider-badge]");

  // Inline voice bar & Mic button
  const micBtn = root.querySelector("[data-mic]");
  const voiceBar = root.querySelector("[data-voice-bar]");
  const voiceState = root.querySelector("[data-voice-state]");
  const voicePreview = root.querySelector("[data-voice-preview]");
  const voiceStopBtn = root.querySelector("[data-voice-stop]");
  const voiceCancelBtn = root.querySelector("[data-voice-cancel]");

  // Stitch Voice Mode Stage controls
  const voiceModeToggleBtn = root.querySelector("[data-voice-mode-toggle]");
  const voiceStage = root.querySelector("[data-voice-stage]");
  const voiceOrbBtn = root.querySelector("[data-voice-orb]");
  const voiceDetectorLabel = root.querySelector("[data-voice-detector-label]");
  const voiceLiveBadge = root.querySelector("[data-voice-live-badge]");
  const voiceTranscriptEl = root.querySelector("[data-voice-transcript]");
  const voiceTranscriptActions = root.querySelector("[data-voice-transcript-actions]");
  const voiceSendNowBtn = root.querySelector("[data-voice-send-now]");
  const voiceToInputBtn = root.querySelector("[data-voice-to-input]");
  const voiceClearDraftBtn = root.querySelector("[data-voice-clear-draft]");
  const voiceReplyTextEl = root.querySelector("[data-voice-reply-text]");
  const voiceSpeakPill = root.querySelector("[data-voice-speak-pill]");
  const voiceToolSlot = root.querySelector("[data-voice-tool-slot]");
  const voiceMuteBtn = root.querySelector("[data-voice-mute]");
  const voiceMuteLabel = root.querySelector("[data-voice-mute-label]");
  const voiceEndBtn = root.querySelector("[data-voice-end]");
  const voiceKeyboardBtn = root.querySelector("[data-voice-keyboard]");

  // Built-in FAQ answers used ONLY when the AI server is offline/unconfigured (honestly labelled)
  const ANSWERS = [
    {
      words: ["remind", "reminder", "email", "before", "when", "nhắc", "lời nhắc", "gia hạn", "trước"],
      fun: tr("Bạn chọn số ngày muốn được nhắc trước ngày gia hạn dự kiến (tối đa 3 mốc như 14, 7, 3 ngày) và giờ nhận trong Cài đặt. Khi công việc nhắc lịch chạy trên máy chủ và email đã xác thực, hệ thống sẽ gửi thông báo để bạn chủ động giữ hoặc hủy gói!", 'You pick how many days before each renewal to be reminded (up to 3, like 14, 7, 3) and the hour in Settings. AllOutFree emails you then, so you can keep or cancel in time!'),
      plain: tr("Bạn có thể đặt tối đa 3 mốc nhắc trước ngày gia hạn dự kiến (ví dụ: 14,7,3 ngày) và cấu hình múi giờ/giờ nhắc trong Cài đặt.", 'Set up to 3 reminder days before each renewal (like 14, 7, 3) and pick your time zone and hour in Settings.'),
    },
    {
      words: ["add", "new", "netflix", "spotify", "track", "how do i", "start", "thêm", "tạo", "mới", "bắt đầu"],
      fun: tr("Bấm '+ Thêm gói', điền tên dịch vụ (như Netflix), số tiền, chu kỳ thanh toán, ngày gia hạn dự kiến tiếp theo và các mốc nhắc (ví dụ 14,7,3). Chưa đầy 20 giây là xong!", "Press '+ Add plan', type the service (like Netflix), price, cycle, next renewal date and reminder days (like 14,7,3). Done in 20 seconds!"),
      plain: tr("Bấm '+ Thêm gói đăng ký', nhập tên dịch vụ, giá tiền, chu kỳ, ngày gia hạn tiếp theo, các mốc ngày nhắc và bấm Lưu.", "Press '+ Add plan', type the service, price, cycle, next renewal date and reminder days, then Save."),
    },
    {
      words: ["pin", "pinned", "link", "links", "bookmark", "save a link", "ghim", "đường dẫn", "lưu link"],
      fun: tr("Link đã ghim là nơi cất giữ các trang quản lý/hủy gói khó tìm (như trang hủy Adobe hay Netflix). Khi dán URL, máy chủ tự lấy tiêu đề và biểu tượng trang web; tới kỳ gia hạn chỉ cần 1 cú nhấp là mở đúng chỗ!", "Pinned links keep those hard-to-find manage and cancel pages (like Adobe's or Netflix's). Paste a link and the title fills in by itself; at renewal time it's one click away!"),
      plain: tr("Link đã ghim giúp lưu lại URL trang quản lý hoặc hủy dịch vụ, tự động lấy tiêu đề và biểu tượng trang, hỗ trợ tìm kiếm theo thẻ.", 'Pinned links save the manage or cancel page of a service, with its title and icon, and you can search them by tag.'),
    },
    {
      words: ["cancel", "unsubscribe", "stop a subscription", "hủy", "tự hủy"],
      fun: tr("Mình không tự bấm nút hủy thay bạn (vì AllOutFree không bao giờ giữ mật khẩu Netflix hay thẻ ngân hàng của bạn). Thay vào đó, mình giữ sẵn đường dẫn hủy đã ghim để bạn tự hủy ngay khi nhận lời nhắc!", "I can't press cancel for you (AllOutFree never holds your Netflix password or bank card). But I keep your saved cancel link ready, so you can cancel the moment the reminder arrives!"),
      plain: tr("AllOutFree không đăng nhập vào tài khoản dịch vụ của bạn. Bạn hãy lưu URL hủy vào mục Link đã lưu hoặc ô đường dẫn quản lý để mở nhanh khi cần.", "AllOutFree doesn't log in to your services. Save the cancel page in Links or in the plan's manage link to open it fast."),
    },
    {
      words: ["bill", "bills", "ocr", "receipt", "statement", "hóa đơn", "sao kê", "chứng từ"],
      fun: tr("Bạn có thể lưu tệp riêng tư, nhập và sửa hóa đơn tại mục Hóa đơn, rồi xuất JSON, CSV hoặc Markdown. OCR tự điền vẫn chưa hoạt động — bạn kiểm tra và nhập những gì có trên hóa đơn nhé!", 'Keep your files private, type in or edit bills in Bills, and export JSON, CSV or Markdown. PDFs and Word files can be read for you; photos still need typing in.'),
      plain: tr("Mục Hóa đơn hỗ trợ nhập tay, lưu tệp riêng tư và xuất dữ liệu. OCR tự trích xuất chưa hoạt động. Thống kê giao dịch của Subby hiện chỉ gồm các khoản gia hạn gói, không phải hóa đơn đã lưu.", 'Bills: type them in or upload a file, keep it private, and export your data. PDFs and Word files can be read for you.'),
    },
    {
      words: ["password", "login", "account", "sign up", "mật khẩu", "đăng nhập", "tài khoản", "đăng ký"],
      fun: tr("Mật khẩu được băm bảo mật (tối thiểu 12 ký tự gồm chữ hoa, chữ thường, số và ký tự đặc biệt). Mỗi tài khoản chỉ nhìn thấy dữ liệu của chính mình!", 'Passwords are stored hashed (at least 12 characters with a capital, a number and a symbol). Every account only ever sees its own data!'),
      plain: tr("Đăng ký bằng tên người dùng, email và mật khẩu từ 12 ký tự trở lên. Dữ liệu của mỗi người dùng được cách ly hoàn toàn.", "Sign up with a username, email and a password of 12+ characters. Each account's data is kept apart."),
    },
    {
      words: ["hello", "hi ", "hey ", "chào", "xin chào"],
      fun: tr("Chào bạn! Mình là Subby 👋 Mình rành chuyện gói đăng ký, lịch gia hạn và link đã lưu. Bạn muốn hỏi bằng chữ hay thử bấm Mic nói chuyện nào?", "Hi! I'm Subby 👋 I know all about subscriptions, renewal dates and saved links. Type a question or press the mic to talk!"),
      plain: tr("Xin chào! Mình là Subby. Bạn có thể nhập câu hỏi hoặc bấm nút Mic để hỏi bằng giọng nói.", "Hello! I'm Subby. Type a question or press the mic to ask by voice."),
    },
  ];

  const ASK_OWNER = ["refund", "money back", "charged", "price", "free", "cost", "pay you", "hoàn tiền", "mất tiền", "lỗi tài khoản"];
  const MUTATION_WORDS = ["thêm nhắc", "đặt nhắc", "tạo gói", "sửa gói", "xóa gói", "add reminder", "create subscription", "set reminder", "update subscription"];

  function findAnswer(question) {
    const q = " " + question.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ") + " ";
    const has = (w) => q.includes(" " + w);
    if (ASK_OWNER.some(has)) return null;
    const hit = ANSWERS.find((a) => a.words.some(has));
    if (!hit) return null;
    return funBox && funBox.checked ? hit.fun : hit.plain;
  }

  function isMutationIntent(question) {
    const q = question.toLowerCase();
    return MUTATION_WORDS.some((w) => q.includes(w));
  }

  function updateProviderStatus(state, labelText, badgeText) {
    if (statusEl && labelText) statusEl.textContent = labelText;
    if (providerBadge && badgeText) providerBadge.textContent = badgeText;
    root.dataset.connectionState = state;
  }

  // ---------- Voice State & Speech Synthesis (TTS) ----------
  let voiceMuted = false;
  let activeSpeakBtn = null;

  // Tell the pet (static/pet.js) how Subby feels, so it can react. Harmless if no pet.
  function petSignal(mood) {
    try {
      document.dispatchEvent(new CustomEvent("subby:mood", { detail: { mood: mood } }));
    } catch (e) {
      // very old browser: the pet just stays idle
    }
  }

  function setVoiceStageState(state, customLabel) {
    petSignal(state);  // "listening" | "thinking" | "speaking" | "idle"
    if (voiceStage) {
      voiceStage.dataset.stageState = state;
    }
    if (voiceDetectorLabel) {
      if (customLabel) {
        voiceDetectorLabel.textContent = customLabel;
      } else if (state === "listening") {
        voiceDetectorLabel.textContent = tr("🎤 Đang nghe (nhấn Mic để dừng)", "🎤 Listening (press the mic to stop)");
      } else if (state === "thinking") {
        voiceDetectorLabel.textContent = tr("🤔 Subby đang suy nghĩ…", "🤔 Subby is thinking…");
      } else if (state === "speaking") {
        voiceDetectorLabel.textContent = tr("🔊 Subby đang đọc câu trả lời…", "🔊 Subby is reading the answer…");
      } else {
        voiceDetectorLabel.textContent = tr("Nhấn biểu tượng Mic ở giữa để bắt đầu nói", "Press the mic in the middle to start talking");
      }
    }
    if (voiceLiveBadge) {
      if (state === "listening") {
        voiceLiveBadge.textContent = tr("● Đang nghe", "● Listening");
        voiceLiveBadge.classList.add("is-live");
      } else if (state === "thinking") {
        voiceLiveBadge.textContent = tr("● Đang gửi…", "● Sending…");
        voiceLiveBadge.classList.remove("is-live");
      } else {
        voiceLiveBadge.textContent = tr("● Chờ giọng nói", "● Waiting");
        voiceLiveBadge.classList.remove("is-live");
      }
    }
    if (voiceSpeakPill) {
      if (state === "speaking") {
        voiceSpeakPill.textContent = tr("🔊 Đang đọc…", "🔊 Speaking…");
        voiceSpeakPill.classList.add("is-speaking");
      } else if (voiceMuted) {
        voiceSpeakPill.textContent = tr("🔇 Đã tắt tiếng", "🔇 Muted");
        voiceSpeakPill.classList.remove("is-speaking");
      } else {
        voiceSpeakPill.textContent = tr("🔈 Sẵn sàng", "🔈 Ready");
        voiceSpeakPill.classList.remove("is-speaking");
      }
    }
  }

  function resetActiveSpeakBtn() {
    if (activeSpeakBtn) {
      activeSpeakBtn.textContent = tr("🔊 Đọc", "🔊 Read");
      activeSpeakBtn.classList.remove("is-speaking");
      activeSpeakBtn.setAttribute("aria-pressed", "false");
      activeSpeakBtn = null;
    }
  }

  // Gemini's voice (/subby/speak) is tried first; the browser's voice is the backup.
  let geminiAudio = null;
  let speakRun = 0; // bumps on every start/stop, so a late Gemini answer is ignored
  let geminiVoiceOff = false; // after Gemini fails once, this page uses the browser voice

  function csrfHeaders(extra) {
    const headers = Object.assign({}, extra || {});
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) headers["X-CSRF-Token"] = meta.content;
    return headers;
  }

  function finishSpeaking() {
    if (ttsStopBtn) ttsStopBtn.hidden = true;
    resetActiveSpeakBtn();
    if (voiceStage && voiceStage.dataset.stageState === "speaking") {
      setVoiceStageState("idle");
    }
  }

  function stopSpeaking() {
    speakRun += 1;
    if (geminiAudio) {
      geminiAudio.pause();
      geminiAudio = null;
    }
    if ("speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {
        // ignore
      }
    }
    finishSpeaking();
  }

  let cachedVoices = [];
  if ("speechSynthesis" in window && typeof window.speechSynthesis.getVoices === "function") {
    try {
      cachedVoices = window.speechSynthesis.getVoices() || [];
      if ("onvoiceschanged" in window.speechSynthesis) {
        window.speechSynthesis.addEventListener("voiceschanged", () => {
          try {
            cachedVoices = window.speechSynthesis.getVoices() || [];
          } catch (e) {
            // ignore
          }
        });
      }
    } catch (e) {
      // ignore
    }
  }

  function pickPreferredVoice(langCode) {
    if (!("speechSynthesis" in window) || typeof window.speechSynthesis.getVoices !== "function") {
      return null;
    }
    const voices = (window.speechSynthesis.getVoices() || []).length
      ? window.speechSynthesis.getVoices()
      : cachedVoices;
    const prefix = langCode.slice(0, 2).toLowerCase();
    return (
      voices.find((v) => v.lang && v.lang.toLowerCase() === langCode.toLowerCase()) ||
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(prefix)) ||
      null
    );
  }

  function speakText(text, triggerBtn) {
    if (!text) return;
    if (triggerBtn && triggerBtn === activeSpeakBtn) {
      stopSpeaking();
      return;
    }
    stopSpeaking();
    if (!root.dataset.speakUrl || geminiVoiceOff || !window.fetch) {
      speakWithBrowser(text, triggerBtn);
      return;
    }
    const run = speakRun;
    if (ttsStopBtn) ttsStopBtn.hidden = false;
    if (triggerBtn) {
      activeSpeakBtn = triggerBtn;
      triggerBtn.textContent = tr("⏹ Dừng đọc", "⏹ Stop");
      triggerBtn.classList.add("is-speaking");
      triggerBtn.setAttribute("aria-pressed", "true");
    }
    setVoiceStageState("speaking");
    if (voiceSpeakPill) voiceSpeakPill.textContent = tr("🔊 Gemini đang chuẩn bị giọng…", "🔊 Gemini is getting the voice ready…");
    fetch(root.dataset.speakUrl, {
      method: "POST",
      headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text: text }),
    })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(String(res.status)))))
      .then((blob) => {
        if (run !== speakRun) return;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        geminiAudio = audio;
        audio.onended = () => {
          URL.revokeObjectURL(url);
          if (run === speakRun) {
            geminiAudio = null;
            finishSpeaking();
          }
        };
        if (voiceSpeakPill) voiceSpeakPill.textContent = tr("🔊 Đang đọc (giọng Gemini)", "🔊 Speaking (Gemini voice)");
        return audio.play();
      })
      .catch((error) => {
        if (run !== speakRun) return;
        // A number = the server said no (busy, quota, limit): stop asking Gemini on this page.
        if (error && /^\d+$/.test(error.message)) geminiVoiceOff = true;
        speakWithBrowser(text, triggerBtn);
      });
  }

  function speakWithBrowser(text, triggerBtn) {
    if (!("speechSynthesis" in window)) {
      finishSpeaking();
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    const uiLang = String(
      document.documentElement.getAttribute("data-ui-lang") || document.documentElement.lang || "vi"
    ).toLowerCase();
    const hasViChars = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(text);
    const hasEnWords = /\b(the|your|subscription|renewal|bill|remind|please|days|month|year|next)\b/i.test(text);
    utter.lang = hasViChars ? "vi-VN" : hasEnWords || uiLang.startsWith("en") ? "en-US" : "vi-VN";
    const matchedVoice = pickPreferredVoice(utter.lang);
    if (matchedVoice) utter.voice = matchedVoice;
    const voiceSourceNote =
      matchedVoice && matchedVoice.localService === false
        ? tr("🔊 Đang đọc (", "🔊 Reading (") + utter.lang + " · online voice)"
        : tr("🔊 Đang đọc (", "🔊 Reading (") + utter.lang + ")";

    if (ttsStopBtn) ttsStopBtn.hidden = false;
    if (triggerBtn) {
      activeSpeakBtn = triggerBtn;
      triggerBtn.textContent = tr("⏹ Dừng đọc", "⏹ Stop");
      triggerBtn.classList.add("is-speaking");
      triggerBtn.setAttribute("aria-pressed", "true");
    }
    setVoiceStageState("speaking");
    if (voiceSpeakPill) {
      voiceSpeakPill.textContent = voiceSourceNote;
      voiceSpeakPill.classList.add("is-speaking");
    }

    utter.onend = () => {
      if (ttsStopBtn) ttsStopBtn.hidden = true;
      resetActiveSpeakBtn();
      if (voiceStage && voiceStage.dataset.stageState === "speaking") {
        setVoiceStageState("idle");
      }
    };
    utter.onerror = () => {
      if (ttsStopBtn) ttsStopBtn.hidden = true;
      resetActiveSpeakBtn();
      if (voiceStage && voiceStage.dataset.stageState === "speaking") {
        setVoiceStageState("idle");
      }
    };
    try {
      window.speechSynthesis.speak(utter);
    } catch (e) {
      stopSpeaking();
    }
  }

  if (ttsStopBtn) {
    ttsStopBtn.addEventListener("click", () => stopSpeaking());
  }

  // Uses textContent so user or bot text never executes as raw HTML
  function say(text, who, metaOption) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + who;

    if (metaOption && metaOption.badge) {
      const badge = document.createElement("span");
      badge.className = "msg-source-badge";
      badge.textContent = metaOption.badge;
      wrap.append(badge);
    }

    const p = document.createElement("p");
    p.className = "msg-text";
    p.textContent = text;
    wrap.append(p);

    if (who.includes("bot") && !who.includes("typing") && ("speechSynthesis" in window || root.dataset.speakUrl)) {
      const footer = document.createElement("div");
      footer.className = "msg-tools";
      const speakBtn = document.createElement("button");
      speakBtn.type = "button";
      speakBtn.className = "msg-tool-btn";
      speakBtn.textContent = tr("🔊 Đọc", "🔊 Read");
      speakBtn.setAttribute("aria-label", tr("Đọc to câu trả lời này", "Read this answer aloud"));
      speakBtn.setAttribute("aria-pressed", "false");
      speakBtn.addEventListener("click", () => speakText(text, speakBtn));
      footer.append(speakBtn);

      if (metaOption && metaOption.retryQuestion) {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "msg-tool-btn retry";
        retryBtn.textContent = tr(tr("↻ Thử lại", "↻ Try again"), "↻ Try again");
        retryBtn.addEventListener("click", () => reply(metaOption.retryQuestion));
        footer.append(retryBtn);
      }
      wrap.append(footer);
    } else if (metaOption && metaOption.retryQuestion) {
      const footer = document.createElement("div");
      footer.className = "msg-tools";
      const retryBtn = document.createElement("button");
      retryBtn.type = "button";
      retryBtn.className = "msg-tool-btn retry";
      retryBtn.textContent = tr("↻ Thử lại", "↻ Try again");
      retryBtn.addEventListener("click", () => reply(metaOption.retryQuestion));
      footer.append(retryBtn);
      wrap.append(footer);
    }

    log.append(wrap);
    log.scrollTop = log.scrollHeight;

    const shouldSpeak =
      who === "bot" &&
      ((ttsAutoBox && ttsAutoBox.checked) || (voiceStage && !voiceStage.hidden && !voiceMuted));
    if (shouldSpeak) {
      speakText(text);
    }
    return wrap;
  }

  const history = [];

  function showHandoff(text, metaOption) {
    const wrap = say(text, "bot", metaOption);
    if (handoff) {
      log.append(handoff.content.cloneNode(true));
      log.scrollTop = log.scrollHeight;
    }
    return wrap;
  }

  function showActionConfirmation(question) {
    if (!actionCardTpl) return;
    const frag = actionCardTpl.content.cloneNode(true);
    const detail = frag.querySelector("[data-action-detail]");
    if (detail) {
      detail.textContent = tr('Yêu cầu của bạn: "', 'You asked: "') + question + tr('" — về gói đăng ký / lời nhắc.', '" — about a plan / reminder.');
    }
    const dismissBtn = frag.querySelector("[data-action-dismiss]");
    const cardEl = frag.querySelector(".subby-action-card");
    if (dismissBtn && cardEl) {
      dismissBtn.addEventListener("click", () => cardEl.remove());
    }
    log.append(frag);
    log.scrollTop = log.scrollHeight;
  }

  // Ask server with timeout & status discrimination
  async function askServer(question) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 14000);
    try {
      const res = await fetch(root.dataset.askUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          fun: funBox ? funBox.checked : true,
          history: history.slice(-6),
        }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      const data = await res.json().catch(() => ({}));
      if (res.status === 429) {
        return {
          status: "rate-limit",
          answer:
            data.answer ||
            tr("⏳ Bạn đã hỏi khá nhanh (tối đa 30 câu/giờ). Cho Subby nghỉ ít phút rồi bấm Thử lại nhé!", "⏳ That was a lot of questions (30 an hour at most). Give Subby a few minutes, then press Try again!"),
        };
      }
      if (res.status === 503 || data.reason === "not-set-up") {
        return {
          status: "not-configured",
          reason: data.reason || "not-set-up",
          provider: data.provider || null,
        };
      }
      if (!res.ok || !data.answer) {
        return {
          status: "offline",
          reason: data.reason || "server-error",
          provider: data.provider || null,
        };
      }
      return {
        status: "ok",
        answer: data.answer,
        handoff: Boolean(data.handoff),
        provider: data.provider || "gemini",
        fallback: Boolean(data.fallback),
        tool: typeof data.tool === "string" ? data.tool : null,
        toolData: data.data && typeof data.data === "object" ? data.data : null,
        confirmUrl: typeof data.confirm_url === "string" ? data.confirm_url : null,
      };
    } catch (err) {
      clearTimeout(timer);
      if (err && err.name === "AbortError") {
        return { status: "timeout" };
      }
      return { status: "offline", reason: "network-error" };
    }
  }

  function buildToolElements(result) {
    const container = document.createDocumentFragment();
    if (!result.tool || !result.toolData) return container;
    const items = Array.isArray(result.toolData.items) ? result.toolData.items.slice(0, 10) : [];
    if (items.length) {
      const list = document.createElement("ul");
      list.className = "subby-tool-list";
      list.setAttribute("data-tool-result", result.tool);
      items.forEach((item) => {
        if (!item || typeof item !== "object") return;
        const line = document.createElement("li");
        line.className = "subby-tool-item";
        if (result.tool === "search_saved_links") {
          try {
            const url = new URL(item.url);
            if (!["http:", "https:"].includes(url.protocol)) return;
            const link = document.createElement("a");
            link.href = url.href;
            link.rel = "noopener noreferrer";
            link.target = "_blank";
            link.textContent = String(item.title || item.url);
            line.append(link);
          } catch (err) {
            return;
          }
        } else {
          line.textContent = [
            item.name,
            item.amount,
            item.currency,
            item.next_renewal_at,
            item.status,
            item.total,
          ]
            .filter((value) => value !== undefined && value !== null)
            .join(" · ");
        }
        list.append(line);
      });
      container.append(list);
    }
    if (result.tool === "create_reminder_draft" && result.confirmUrl) {
      try {
        const url = new URL(result.confirmUrl, window.location.origin);
        if (url.origin === window.location.origin && url.pathname === "/subscriptions/new") {
          const button = document.createElement("a");
          button.className = "button secondary btn-sm subby-draft-btn";
          button.href = url.pathname + url.search;
          button.textContent = tr("Kiểm tra và lưu", "Check and save");
          container.append(button);
        }
      } catch (err) {
        /* An invalid draft link is never clickable. */
      }
    }
    return container;
  }

  function showToolResult(result, wrap) {
    if (!wrap || !result.tool || !result.toolData) return;
    wrap.append(buildToolElements(result));
    if (voiceToolSlot) {
      voiceToolSlot.textContent = "";
      voiceToolSlot.append(buildToolElements(result));
    }
    log.scrollTop = log.scrollHeight;
  }

  function updateVoiceReplyCard(answerText, clearTools) {
    if (voiceReplyTextEl && answerText) {
      voiceReplyTextEl.textContent = answerText;
    }
    if (clearTools && voiceToolSlot) {
      voiceToolSlot.textContent = "";
    }
  }

  async function reply(question) {
    setVoiceStageState("thinking");
    const typing = say(tr("Subby đang suy nghĩ…", "Subby is thinking…"), "bot typing");
    const result = await askServer(question);
    typing.remove();

    if (result.status === "ok") {
      const prov = String(result.provider || "gemini");
      const isFake = prov.toLowerCase() === "fake";
      const isFallback = Boolean(result.fallback);

      let badgeLabel = "AI · " + prov;
      let statusLabel = tr("Trực tuyến · Trả lời bởi ", "Online · Answered by ") + prov;
      if (isFake) {
        badgeLabel = tr("🧪 Câu trả lời thử nghiệm", "🧪 Test answers");
        statusLabel = tr("Chế độ thử nghiệm", "Test mode");
      }
      if (isFallback) {
        badgeLabel = tr("☁ Dự phòng đám mây (", "☁ Cloud backup (") + prov + ")";
        statusLabel = tr("Dự phòng đám mây (", "Cloud backup (") + prov + ")";
      }

      updateProviderStatus(isFallback ? "cloud-fallback" : "online", statusLabel, prov);
      updateVoiceReplyCard(result.answer, !result.tool);
      const msgOption = {
        badge: badgeLabel,
        provider: prov,
        fallback: isFallback,
      };
      const renderedWrap = result.handoff
        ? showHandoff(result.answer, msgOption)
        : say(result.answer, "bot", msgOption);
      showToolResult(result, renderedWrap);

      if (isFallback && renderedWrap) {
        const fbNote = document.createElement("small");
        fbNote.className = "msg-fallback-note muted block-small";
        fbNote.setAttribute("data-cloud-fallback-note", "true");
        fbNote.textContent =
          tr("☁ Lưu ý: mô hình trên máy chủ đang tắt; câu trả lời này đến từ mô hình đám mây dự phòng.", "☁ Note: the local model is off; this answer came from the backup cloud model.");
        renderedWrap.append(fbNote);
      }

      if (!result.tool && isMutationIntent(question)) {
        showActionConfirmation(question);
      }
      if (voiceStage && voiceStage.dataset.stageState === "thinking") {
        setVoiceStageState("idle");
      }
      history.push({ role: "user", text: question });
      // Tool answers contain private account data; never send them back to a model.
      if (!result.tool) history.push({ role: "bot", text: result.answer });
      return;
    }

    if (result.status === "rate-limit") {
      updateProviderStatus("rate-limit", tr("Tạm giới hạn lượt hỏi", "Too many questions for now"), "Rate limit");
      updateVoiceReplyCard(result.answer, true);
      say(result.answer, "bot", {
        badge: tr("⏳ Chờ ít phút", "⏳ Wait a few minutes"),
        retryQuestion: question,
      });
      setVoiceStageState("idle");
      return;
    }

    if (result.status === "timeout") {
      updateProviderStatus("timeout", tr("Máy chủ trả lời quá lâu", "The server took too long"), "Timeout");
      say(
        tr("⏱ Máy chủ AI trả lời lâu hơn dự kiến. Hãy bấm '↻ Thử lại' hoặc xem câu trả lời có sẵn bên dưới.", "⏱ The AI server took too long. Press '↻ Try again' or read the built-in answer below."),
        "bot",
        { badge: tr("⏱ Quá thời gian", "⏱ Timed out"), retryQuestion: question }
      );
    } else if (result.status === "not-configured") {
      updateProviderStatus(
        "not-configured",
        tr("AI chưa bật · Đang dùng câu trả lời có sẵn", "AI is off · Using built-in answers"),
        tr("Trả lời có sẵn", "Built-in answers")
      );
    } else {
      const reasonText =
        result.reason === "model-offline"
          ? tr("AI đang ngoại tuyến", "The AI is offline")
          : tr("AI tạm nghỉ (", "AI is resting (") + (result.reason || "offline") + ")";
      updateProviderStatus(
        "fallback",
        reasonText + tr(" · Đang dùng câu trả lời có sẵn", " · Using built-in answers"),
        tr("Trả lời có sẵn", "Built-in answers")
      );
    }

    const answer = findAnswer(question);
    if (answer) {
      updateVoiceReplyCard(answer, true);
      say(answer, "bot", {
        badge: tr("📋 Câu trả lời có sẵn (AI chưa kết nối)", "📋 Built-in answer (the AI isn't connected)"),
        retryQuestion: question,
      });
      if (isMutationIntent(question)) {
        showActionConfirmation(question);
      }
      setVoiceStageState("idle");
      return;
    }

    const handoffMsg =
      funBox && funBox.checked
        ? tr("Máy chủ AI hiện chưa phản hồi và câu này cũng nằm ngoài sổ tay FAQ có sẵn của mình 😅 Bạn có thể thử lại hoặc nhắn trực tiếp cho chủ sở hữu:", "The AI server isn't answering and this one isn't in my little FAQ book 😅 Try again, or message the owner directly:")
        : tr("Hiện máy chủ AI chưa trả lời câu này. Bạn có thể bấm Thử lại hoặc liên hệ trực tiếp với chủ sở hữu:", "The AI server hasn't answered this one. Press Try again or contact the owner directly:");
    updateVoiceReplyCard(handoffMsg, true);
    showHandoff(handoffMsg, {
      badge: tr("📋 Câu trả lời có sẵn", "📋 Built-in answers"),
      retryQuestion: question,
    });
    setVoiceStageState("idle");
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    stopSpeaking();
    if (voiceTranscriptEl) {
      voiceTranscriptEl.textContent = "“" + question + "”";
    }
    if (voiceTranscriptActions) {
      voiceTranscriptActions.hidden = true;
    }
    say(question, "user");
    reply(question);
  }

  function setVoiceModeOpen(open) {
    if (!voiceStage) return;
    voiceStage.hidden = !open;
    root.classList.toggle("voice-mode-open", open);
    if (voiceModeToggleBtn) {
      voiceModeToggleBtn.classList.toggle("on", open);
      voiceModeToggleBtn.setAttribute("aria-pressed", String(open));
    }
    if (!open) {
      stopVoiceRecognition(true);
      stopSpeaking();
    }
  }

  function setOpen(open) {
    panel.hidden = !open;
    root.classList.toggle("open", open);
    openBtn.setAttribute("aria-expanded", String(open));
    if (teaser) teaser.hidden = true;
    petSignal(open ? "open" : "idle");
    if (open) {
      if (!log.children.length) {
        say(
          tr("Chào bạn, mình là Subby! Bạn có thể hỏi về lời nhắc gia hạn, link đã ghim, hóa đơn hoặc bấm 🎙️ Giọng nói để nói chuyện trực tiếp. 👋", "Hi, I'm Subby! Ask me about renewal reminders, pinned links or bills, or press 🎙️ Voice to talk. 👋"),
          "bot"
        );
      }
      setTimeout(() => input.focus(), 20);
    } else {
      stopVoiceRecognition(true);
      stopSpeaking();
      openBtn.focus();
    }
  }

  openBtn.addEventListener("click", () => setOpen(panel.hidden));
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));
  if (voiceModeToggleBtn) {
    voiceModeToggleBtn.addEventListener("click", () => {
      setVoiceModeOpen(voiceStage ? voiceStage.hidden : false);
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) {
      e.preventDefault();
      setOpen(false);
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const reviewedText = input.value;
    stopVoiceRecognition(true);
    ask(reviewedText);
  });

  root.querySelectorAll("[data-ask]").forEach((chip) => {
    chip.addEventListener("click", () => ask(chip.getAttribute("data-en") && document.documentElement.getAttribute("data-ui-lang") === "en" ? chip.getAttribute("data-en") : chip.textContent));
  });

  // ---------- Voice Input (SpeechRecognition — requests mic ONLY when clicked) ----------
  let recognition = null;
  let heardTranscript = "";
  let draftEdited = false;
  input.addEventListener("input", () => { draftEdited = true; });

  function syncMicButtons(isListening) {
    [micBtn, voiceOrbBtn].forEach((btn) => {
      if (!btn) return;
      btn.classList.toggle("listening", isListening);
      btn.setAttribute("aria-pressed", String(isListening));
    });
  }

  // ---------- Recording for Gemini (browsers without speech recognition, like Firefox) ----------
  let recorder = null;
  let recordTimer = null;
  const RECORD_SECONDS = 30;

  function canRecord() {
    return Boolean(
      root.dataset && root.dataset.listenUrl &&
      typeof navigator !== "undefined" && navigator.mediaDevices && navigator.mediaDevices.getUserMedia &&
      typeof MediaRecorder !== "undefined"
    );
  }

  function pickRecordingType() {
    const types = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg"];
    return types.find((type) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(type)) || "";
  }

  function stopRecording(cancel) {
    if (!recorder) return;
    const active = recorder;
    recorder = null;
    active.cancelled = Boolean(cancel);
    clearTimeout(recordTimer);
    try {
      active.stop();
    } catch (e) {
      // ignore
    }
  }

  async function startRecording() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const reason = tr("Micro bị chặn hoặc không có. Hãy cho phép micro, hoặc nhập câu hỏi nhé.", "The microphone is blocked or missing. Allow it, or type your question.");
      setVoiceStageState("idle", "⚠ " + reason);
      say("🎤 " + reason, "bot", { badge: tr("Trạng thái Micro", "Microphone status") });
      return;
    }
    const type = pickRecordingType();
    const chunks = [];
    const active = type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream);
    recorder = active;
    active.ondataavailable = (event) => {
      if (event.data && event.data.size) chunks.push(event.data);
    };
    active.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      syncMicButtons(false);
      if (voiceBar) voiceBar.hidden = true;
      if (active.cancelled || !chunks.length) {
        setVoiceStageState("idle");
        return;
      }
      const mime = (active.mimeType || type || "audio/webm").split(";")[0];
      sendRecording(new Blob(chunks, { type: mime }), mime);
    };
    active.start();
    syncMicButtons(true);
    setVoiceStageState("listening", tr("🎤 Đang ghi âm… bấm Mic lần nữa để dừng", "🎤 Recording… press the mic again to stop"));
    if (voiceBar && (!voiceStage || voiceStage.hidden)) voiceBar.hidden = false;
    if (voiceState) voiceState.textContent = tr("🎤 Đang ghi âm… bấm Dừng khi nói xong", "🎤 Recording… press Stop when you're done");
    if (voicePreview) voicePreview.textContent = tr("Gemini sẽ viết lại câu bạn nói sau khi bạn dừng.", "Gemini writes down what you said after you stop.");
    if (voiceTranscriptActions) voiceTranscriptActions.hidden = true;
    recordTimer = setTimeout(() => stopRecording(false), RECORD_SECONDS * 1000);
  }

  function sendRecording(blob, mime) {
    setVoiceStageState("thinking", tr("✍️ Gemini đang viết lại câu bạn nói…", "✍️ Gemini is writing down what you said…"));
    fetch(root.dataset.listenUrl, { method: "POST", headers: csrfHeaders({ "Content-Type": mime }), body: blob })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data) => {
        const text = String((data && data.text) || "").trim();
        if (!text) {
          setVoiceStageState("idle", "⚠ " + tr("Chưa nghe rõ, bạn nói lại nhé.", "I couldn't hear anything, please try again."));
          return;
        }
        input.value = text;
        draftEdited = false;
        stopVoiceRecognition(false); // shows the words with the "Send" button, like speech recognition
      })
      .catch(() => {
        setVoiceStageState("idle", "⚠ " + tr("Không chuyển được giọng nói thành chữ. Hãy nhập câu hỏi nhé.", "Couldn't turn your voice into text. Please type your question."));
        input.focus();
      });
  }

  function stopVoiceRecognition(cancelled) {
    if (recorder) stopRecording(cancelled);
    if (recognition) {
      const active = recognition;
      try {
        if (cancelled) {
          recognition = null;
          active.onresult = null;
          active.onend = null;
          active.onerror = null;
          if (active.abort) active.abort();
          else active.stop();
        } else {
          // Keep callbacks until onend so the browser's final result survives.
          active.stop();
        }
      } catch (e) {
        // ignore
      }
    }
    syncMicButtons(false);
    if (voiceBar) voiceBar.hidden = true;

    const cleanText = input.value.trim();
    if (!cancelled && cleanText) {
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = "“" + cleanText + "”";
      }
      if (voiceTranscriptActions) {
        voiceTranscriptActions.hidden = false;
      }
      setVoiceStageState(
        "idle",
        tr("✓ Đã ghi nhận câu hỏi — bấm '🚀 Gửi câu hỏi này' hoặc sửa trong ô chữ", "✓ Got it — press '🚀 Send question' or edit it in the text box")
      );
      input.focus();
    } else if (cancelled) {
      heardTranscript = "";
      input.value = "";
      if (voiceTranscriptActions) voiceTranscriptActions.hidden = true;
      setVoiceStageState("idle");
    } else {
      setVoiceStageState("idle");
    }
  }

  function startOrToggleMic(openStageToo) {
    if (openStageToo && voiceStage && voiceStage.hidden) {
      setVoiceModeOpen(true);
    }
    if (recognition || recorder) {
      stopVoiceRecognition(false);
      return;
    }
    stopSpeaking();

    const uiLang = String(
      document.documentElement.getAttribute("data-ui-lang") || document.documentElement.lang || "vi"
    ).toLowerCase();
    const isEn = uiLang.startsWith("en");

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec && canRecord()) {
      startRecording();
      return;
    }
    if (!SpeechRec) {
      const unsupportedMsg = isEn
        ? "🔇 This browser does not support Web Speech API — please type your question in the box below."
        : "🔇 Trình duyệt này chưa hỗ trợ Web Speech API — Hãy nhập câu hỏi bằng bàn phím bên dưới";
      setVoiceStageState("idle", unsupportedMsg);
      say(
        isEn
          ? "🎤 Speech recognition (Web Speech API) is not supported in this browser. Please type your question below!"
          : "🎤 Trình duyệt hiện tại chưa hỗ trợ nhận diện giọng nói (Web Speech API). Bạn hãy nhập câu hỏi bằng bàn phím vào ô bên dưới nhé!",
        "bot",
        { badge: isEn ? "Browser notice" : "Thông báo trình duyệt" }
      );
      input.focus();
      return;
    }

    heardTranscript = "";
    draftEdited = false;
    input.value = "";
    recognition = new SpeechRec();
    const active = recognition;
    recognition.lang = isEn ? "en-US" : "vi-VN";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    syncMicButtons(true);
    setVoiceStageState("listening");
    if (voiceBar && (!voiceStage || voiceStage.hidden)) {
      voiceBar.hidden = false;
    }
    if (voiceState) {
      voiceState.textContent = isEn
        ? "🎤 Listening… (Click Stop to review text before sending)"
        : "🎤 Đang nghe… (Bấm Dừng để xem lại chữ trước khi gửi)";
    }
    if (voicePreview) {
      voicePreview.textContent = isEn
        ? "Speak your question… (Browser speech recognition may use an external service)"
        : "Hãy nói câu hỏi của bạn… (Trình duyệt có thể dùng dịch vụ nhận diện bên ngoài)";
    }
    if (voiceTranscriptEl) {
      voiceTranscriptEl.textContent = isEn
        ? "“Listening to your voice…”"
        : "“Đang lắng nghe giọng nói của bạn…”";
    }
    if (voiceTranscriptActions) {
      voiceTranscriptActions.hidden = true;
    }

    recognition.onresult = (event) => {
      if (recognition !== active) return;
      let text = "";
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      heardTranscript = text;
      if (!draftEdited) input.value = text;
      const trimmed = input.value.trim();
      if (voicePreview) {
        voicePreview.textContent = isEn
          ? 'Draft: "' + trimmed + '" (Click Stop & Review to edit before sending)'
          : 'Bản nháp: "' + trimmed + '" (Bấm Dừng & Xem chữ để chỉnh sửa trước khi gửi)';
      }
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = "“" + trimmed + "”";
      }
      if (voiceTranscriptActions && trimmed) {
        voiceTranscriptActions.hidden = false;
      }
    };

    recognition.onerror = (event) => {
      if (recognition !== active) return;
      const code = event && event.error ? String(event.error) : "unknown";
      let reason = "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        reason = isEn
          ? "Microphone permission was denied or blocked (not-allowed). Please allow microphone access or type your question below."
          : "Bạn đã từ chối quyền micro hoặc trình duyệt chặn micro (not-allowed). Hãy cấp quyền hoặc nhập câu hỏi bằng bàn phím nhé.";
      } else if (code === "no-speech") {
        reason = isEn
          ? "No speech was detected (no-speech). Tap the microphone to try again or type your question below."
          : "Chưa nghe thấy giọng nói nào (no-speech). Bạn hãy nhấn Mic thử lại hoặc nhập câu hỏi bằng bàn phím nhé.";
      } else if (code === "network") {
        reason = isEn
          ? "Network problem reaching the browser's speech recognition service (network). Please check your connection or type your question below."
          : "Lỗi kết nối mạng tới dịch vụ nhận diện giọng nói của trình duyệt (network). Vui lòng kiểm tra mạng hoặc nhập câu hỏi bằng bàn phím nhé.";
      } else if (code === "audio-capture") {
        reason = isEn
          ? "No working microphone was found (audio-capture). Please check your microphone device or type your question below."
          : "Không tìm thấy thiết bị thu âm (audio-capture). Vui lòng kiểm tra micro hoặc nhập câu hỏi bằng bàn phím nhé.";
      } else {
        reason = isEn
          ? "Could not recognize speech (" + code + "). You can try again or type your question below."
          : "Không nhận diện được giọng nói (" + code + "). Bạn có thể thử lại hoặc nhập văn bản.";
      }
      const preservedTypedDraft = draftEdited ? input.value : "";
      stopVoiceRecognition(true);
      if (preservedTypedDraft) {
        input.value = preservedTypedDraft;
        draftEdited = true;
      }
      setVoiceStageState("idle", "⚠ " + reason);
      say("🎤 " + reason, "bot", { badge: isEn ? "Microphone status" : "Trạng thái Micro" });
      input.focus();
    };

    recognition.onend = () => {
      if (recognition === active) {
        recognition = null;
        stopVoiceRecognition(false);
      }
    };

    try {
      recognition.start();
    } catch (e) {
      stopVoiceRecognition(true);
    }
  }

  if (micBtn) {
    micBtn.addEventListener("click", () => startOrToggleMic(true));
  }
  if (voiceOrbBtn) {
    voiceOrbBtn.addEventListener("click", () => startOrToggleMic(false));
  }
  if (voiceStopBtn) {
    voiceStopBtn.addEventListener("click", () => stopVoiceRecognition(false));
  }
  if (voiceCancelBtn) {
    voiceCancelBtn.addEventListener("click", () => stopVoiceRecognition(true));
  }

  if (voiceSendNowBtn) {
    voiceSendNowBtn.addEventListener("click", () => {
      const textToSend = (input.value || "").trim();
      stopVoiceRecognition(true);
      if (textToSend) ask(textToSend);
    });
  }

  if (voiceToInputBtn) {
    voiceToInputBtn.addEventListener("click", () => {
      if (recognition) stopVoiceRecognition(false);
      input.focus();
    });
  }

  if (voiceClearDraftBtn) {
    voiceClearDraftBtn.addEventListener("click", () => {
      stopVoiceRecognition(true);
      input.value = "";
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = tr("“Nhấn Mic để nói câu hỏi hoặc dùng bàn phím bên dưới…”", "“Press the mic to ask, or type below…”");
      }
      input.focus();
    });
  }

  if (voiceMuteBtn) {
    voiceMuteBtn.addEventListener("click", () => {
      voiceMuted = !voiceMuted;
      voiceMuteBtn.setAttribute("aria-pressed", String(voiceMuted));
      voiceMuteBtn.classList.toggle("is-muted", voiceMuted);
      if (voiceMuteLabel) {
        voiceMuteLabel.textContent = voiceMuted ? tr("Đã tắt tiếng", "Muted") : tr("Đọc tiếng", "Read aloud");
      }
      if (voiceMuted) {
        stopSpeaking();
      }
      setVoiceStageState(voiceStage ? voiceStage.dataset.stageState || "idle" : "idle");
    });
  }

  if (voiceEndBtn) {
    voiceEndBtn.addEventListener("click", () => {
      stopVoiceRecognition(true);
      stopSpeaking();
      setVoiceModeOpen(false);
      input.focus();
    });
  }

  if (voiceKeyboardBtn) {
    voiceKeyboardBtn.addEventListener("click", () => {
      const reviewedText = input.value;
      setVoiceModeOpen(false);
      input.value = reviewedText;
      input.focus();
    });
  }

  window.addEventListener("pagehide", () => {
    stopVoiceRecognition(true);
    stopSpeaking();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopVoiceRecognition(true);
      stopSpeaking();
    }
  });

  // Keep chat panel comfortable when mobile virtual keyboard opens
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      if (!panel.hidden) {
        panel.style.maxHeight = Math.max(260, window.visualViewport.height - 90) + "px";
      }
    });
  }
})();
