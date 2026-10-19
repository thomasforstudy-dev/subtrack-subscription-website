// Subby, the help bot. Provider-agnostic UI: talks to /subby/ask on the server.
// Handles thinking, timeout, rate limit (429), offline/FAQ fallback, voice input
// (review transcript before send), optional read-aloud (TTS), and action confirmation cards.
(function () {
  const root = document.querySelector("[data-subby]");
  if (!root) return;

  const panel = root.querySelector("#subby-panel");
  const openBtn = root.querySelector("[data-open]");
  const closeBtn = root.querySelector("[data-close]");
  const log = root.querySelector("[data-log]");
  const form = root.querySelector("[data-form]");
  const input = form.querySelector("[name=q]");
  const funBox = root.querySelector("[data-fun]");
  const ttsAutoBox = root.querySelector("[data-tts-auto]");
  const ttsStopBtn = root.querySelector("[data-tts-stop]");
  const statusEl = root.querySelector("[data-subby-status]");
  const providerBadge = root.querySelector("[data-provider-badge]");
  const handoff = root.querySelector("[data-handoff]");
  const actionCardTpl = root.querySelector("[data-action-card]");
  const micBtn = root.querySelector("[data-mic]");
  const voiceBar = root.querySelector("[data-voice-bar]");
  const voiceState = root.querySelector("[data-voice-state]");
  const voicePreview = root.querySelector("[data-voice-preview]");
  const voiceStopBtn = root.querySelector("[data-voice-stop]");
  const voiceCancelBtn = root.querySelector("[data-voice-cancel]");

  const ANSWERS = [
    {
      words: ["remind", "email", "notify", "warn", "before", "nhắc", "lời nhắc", "thông báo"],
      fun: "Bạn chọn số ngày muốn được nhắc trước (ví dụ 14, 7 hoặc 3 ngày) cho từng gói. Lưu ý: tính năng gửi email định kỳ tự động đang được hoàn thiện trên máy chủ — ít nhất thì mình không bao giờ nói dối là 'đã gửi' khi chưa gửi thật!",
      plain: "Mỗi gói đăng ký có mốc ngày nhắc trước riêng (ví dụ 14, 7 hoặc 3 ngày). Tác vụ gửi email tự động định kỳ đang được hoàn thiện trên máy chủ.",
    },
    {
      words: ["add", "netflix", "spotify", "new subscription", "thêm gói", "thêm"],
      fun: "Đăng nhập, bấm '+ Thêm gói', điền tên dịch vụ, số tiền và ngày gia hạn dự kiến rồi lưu lại. Nhanh hơn cả lúc tìm nút hủy của Netflix!",
      plain: "Sau khi đăng nhập, bạn bấm '+ Thêm gói', nhập tên dịch vụ, giá tiền, chu kỳ và ngày gia hạn dự kiến rồi bấm Lưu.",
    },
    {
      words: ["pin", "link", "bookmark", "ghim", "đường dẫn"],
      fun: "Mục 'Link đã lưu' là ngăn kéo cất sẵn trang hủy gói và trang thanh toán. Dán URL vào, mình tự lấy tiêu đề trang, bạn ghim lên đầu để lúc cần là mở ngay.",
      plain: "Link đã lưu giúp bạn cất các trang web cần dùng lại. Dán đường dẫn vào, tiêu đề sẽ tự động điền và bạn có thể ghim lên đầu danh sách.",
    },
    {
      words: ["cancel", "unsubscribe", "stop", "hủy gói", "tự hủy", "hủy"],
      fun: "Mình không có tay để bấm hủy dịch vụ bên ngoài giúp bạn đâu 🙃! Nhưng bạn có thể lưu sẵn link trang hủy gói vào 'Link đã lưu' để tự hủy chỉ với 1 chạm.",
      plain: "SubTrack không thể tự hủy dịch vụ bên ngoài thay bạn, nhưng bạn có thể lưu sẵn đường dẫn trang hủy gói để mở nhanh khi tới hạn.",
    },
    {
      words: ["credit", "card", "payment", "bill", "thẻ tín dụng", "sao kê", "hóa đơn"],
      fun: "Bạn có thể theo dõi hạn thanh toán thẻ tín dụng và tải hóa đơn PDF/Ảnh lên mục Hóa đơn để đối chiếu từng khoản thu trước khi xác nhận.",
      plain: "Bạn có thể thêm ngày đến hạn thanh toán thẻ tín dụng để nhắc lịch và kiểm tra chứng từ tại mục Hóa đơn / Giao dịch.",
    },
    {
      words: ["sign up", "signup", "register", "account", "password", "đăng ký", "mật khẩu"],
      fun: "Bấm Đăng ký, chọn tên đăng nhập (3–30 ký tự), email và mật khẩu mạnh (12+ ký tự có chữ hoa, số và ký tự đặc biệt).",
      plain: "Bấm Đăng ký và nhập tên đăng nhập, email cùng mật khẩu từ 12–128 ký tự (gồm chữ hoa, chữ số và ký tự đặc biệt).",
    },
    {
      words: ["hello", "hi ", "hey ", "chào", "xin chào"],
      fun: "Chào bạn! Mình là Subby 👋 Mình rành chuyện gói đăng ký, hạn thẻ và link đã lưu. Bạn muốn hỏi gì nào?",
      plain: "Xin chào! Mình là Subby. Bạn có thể hỏi mình về cách dùng SubTrack.",
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

  // Safe text-to-speech (never auto-plays unless user explicitly checks data-tts-auto)
  function speakText(text) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(text)
      ? "vi-VN"
      : "en-US";
    if (ttsStopBtn) ttsStopBtn.hidden = false;
    utter.onend = () => {
      if (ttsStopBtn) ttsStopBtn.hidden = true;
    };
    utter.onerror = () => {
      if (ttsStopBtn) ttsStopBtn.hidden = true;
    };
    window.speechSynthesis.speak(utter);
  }

  if (ttsStopBtn) {
    ttsStopBtn.addEventListener("click", () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      ttsStopBtn.hidden = true;
    });
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

    if (who.includes("bot") && !who.includes("typing") && "speechSynthesis" in window) {
      const footer = document.createElement("div");
      footer.className = "msg-tools";
      const speakBtn = document.createElement("button");
      speakBtn.type = "button";
      speakBtn.className = "msg-tool-btn";
      speakBtn.textContent = "🔊 Đọc";
      speakBtn.setAttribute("aria-label", "Đọc to câu trả lời này");
      speakBtn.addEventListener("click", () => speakText(text));
      footer.append(speakBtn);

      if (metaOption && metaOption.retryQuestion) {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "msg-tool-btn retry";
        retryBtn.textContent = "↻ Thử lại với máy chủ";
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
      retryBtn.textContent = "↻ Thử lại";
      retryBtn.addEventListener("click", () => reply(metaOption.retryQuestion));
      footer.append(retryBtn);
      wrap.append(footer);
    }

    log.append(wrap);
    log.scrollTop = log.scrollHeight;

    if (who === "bot" && ttsAutoBox && ttsAutoBox.checked) {
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
      detail.textContent = 'Yêu cầu của bạn: "' + question + '" — Đối tượng: Gói đăng ký / Lịch nhắc.';
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
            "⏳ Bạn đã hỏi khá nhanh (tối đa 30 câu/giờ). Cho Subby nghỉ lấy hơi ít phút rồi bấm Thử lại nhé!",
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
      };
    } catch (err) {
      clearTimeout(timer);
      if (err && err.name === "AbortError") {
        return { status: "timeout" };
      }
      return { status: "offline", reason: "network-error" };
    }
  }

  async function reply(question) {
    const typing = say("Subby đang suy nghĩ…", "bot typing");
    const result = await askServer(question);
    typing.remove();

    if (result.status === "ok") {
      const prov = String(result.provider || "gemini");
      const isFake = prov.toLowerCase() === "fake";
      const isFallback = Boolean(result.fallback);

      let badgeLabel = "AI · " + prov;
      let statusLabel = "Trực tuyến · Phản hồi từ " + prov;
      if (isFake) {
        badgeLabel = "🧪 Mô hình giả lập kiểm thử (fake model)";
        statusLabel = "Chế độ kiểm thử · fake model";
      }
      if (isFallback) {
        badgeLabel = "☁ Dự phòng đám mây (" + prov + " · answered by a cloud model)";
        statusLabel = "Dự phòng đám mây · answered by a cloud model (" + prov + ")";
      }

      updateProviderStatus(isFallback ? "cloud-fallback" : "online", statusLabel, prov);
      const msgOption = {
        badge: badgeLabel,
        provider: prov,
        fallback: isFallback,
      };
      const renderedWrap = result.handoff
        ? showHandoff(result.answer, msgOption)
        : say(result.answer, "bot", msgOption);

      if (isFallback && renderedWrap) {
        const fbNote = document.createElement("small");
        fbNote.className = "msg-fallback-note muted block-small";
        fbNote.setAttribute("data-cloud-fallback-note", "true");
        fbNote.textContent =
          "☁ Lưu ý: Mô hình nội bộ hiện không khả dụng; câu trả lời này được tạo bởi mô hình đám mây dự phòng (answered by a cloud model).";
        renderedWrap.append(fbNote);
      }

      if (isMutationIntent(question)) {
        showActionConfirmation(question);
      }
      history.push({ role: "user", text: question }, { role: "bot", text: result.answer });
      return;
    }

    if (result.status === "rate-limit") {
      updateProviderStatus("rate-limit", "Tạm giới hạn lượt hỏi (429)", "Rate limit");
      say(result.answer, "bot", {
        badge: "⏳ Giới hạn lượt hỏi — Chờ ít phút",
        retryQuestion: question,
      });
      return;
    }

    if (result.status === "timeout") {
      updateProviderStatus("timeout", "Quá thời gian chờ phản hồi máy chủ", "Timeout");
      say(
        "⏱ Máy chủ AI phản hồi lâu hơn dự kiến (Timeout). Bạn có thể bấm '↻ Thử lại' hoặc xem câu trả lời hướng dẫn có sẵn bên dưới.",
        "bot",
        { badge: "⏱ Timeout máy chủ", retryQuestion: question }
      );
    } else if (result.status === "not-configured") {
      updateProviderStatus(
        "not-configured",
        "AI chưa cấu hình (not-set-up) · Đang dùng FAQ có sẵn",
        "FAQ Fallback"
      );
    } else {
      const reasonText = result.reason === "model-offline" ? "Mô hình AI ngoại tuyến (model-offline)" : "AI tạm nghỉ (" + (result.reason || "offline") + ")";
      updateProviderStatus(
        "fallback",
        reasonText + " · Đang dùng bộ câu trả lời có sẵn (FAQ Fallback)",
        "FAQ Fallback"
      );
    }

    const answer = findAnswer(question);
    if (answer) {
      say(answer, "bot", {
        badge: "📋 Câu trả lời hướng dẫn có sẵn (FAQ Fallback — máy chủ AI chưa kết nối)",
        retryQuestion: question,
      });
      if (isMutationIntent(question)) {
        showActionConfirmation(question);
      }
      return;
    }

    showHandoff(
      funBox && funBox.checked
        ? "Máy chủ AI hiện chưa phản hồi và câu này cũng nằm ngoài sổ tay FAQ có sẵn của mình 😅 Bạn có thể thử lại hoặc nhắn trực tiếp cho chủ sở hữu:"
        : "Hiện máy chủ AI chưa phản hồi cho câu hỏi này. Bạn có thể bấm Thử lại hoặc liên hệ trực tiếp với chủ sở hữu:",
      {
        badge: "📋 Chế độ FAQ Fallback (Không giả lập câu trả lời AI động)",
        retryQuestion: question,
      }
    );
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    say(question, "user");
    reply(question);
  }

  function setOpen(open) {
    panel.hidden = !open;
    root.classList.toggle("open", open);
    openBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      if (!log.children.length) {
        say(
          "Chào bạn, mình là Subby! Bạn có thể hỏi về lời nhắc gia hạn, link đã ghim, hóa đơn hoặc cách dùng SubTrack. 👋",
          "bot"
        );
      }
      setTimeout(() => input.focus(), 20);
    } else {
      stopVoiceRecognition(true);
      openBtn.focus();
    }
  }

  openBtn.addEventListener("click", () => setOpen(panel.hidden));
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) {
      e.preventDefault();
      setOpen(false);
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    ask(input.value);
    input.value = "";
  });

  root.querySelectorAll("[data-ask]").forEach((chip) => {
    chip.addEventListener("click", () => ask(chip.textContent));
  });

  // ---------- Voice Input (SpeechRecognition — requests mic ONLY when clicked) ----------
  let recognition = null;
  let heardTranscript = "";

  function stopVoiceRecognition(cancelled) {
    if (recognition) {
      try {
        recognition.onresult = null;
        recognition.onend = null;
        recognition.onerror = null;
        recognition.stop();
      } catch (e) {
        // ignore
      }
      recognition = null;
    }
    if (micBtn) {
      micBtn.classList.remove("listening");
      micBtn.setAttribute("aria-pressed", "false");
    }
    if (voiceBar) voiceBar.hidden = true;
    if (!cancelled && heardTranscript.trim()) {
      input.value = (input.value ? input.value + " " : "") + heardTranscript.trim();
      input.focus();
    }
    heardTranscript = "";
  }

  if (micBtn) {
    micBtn.addEventListener("click", () => {
      if (recognition) {
        stopVoiceRecognition(false);
        return;
      }
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        say(
          "🎤 Trình duyệt hiện tại chưa hỗ trợ nhận diện giọng nói (Web Speech API). Bạn hãy nhập câu hỏi bằng bàn phím vào ô bên dưới nhé!",
          "bot",
          { badge: "Thông báo trình duyệt" }
        );
        input.focus();
        return;
      }

      heardTranscript = "";
      recognition = new SpeechRec();
      recognition.lang = document.documentElement.lang === "en" ? "en-US" : "vi-VN";
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      micBtn.classList.add("listening");
      micBtn.setAttribute("aria-pressed", "true");
      if (voiceBar) voiceBar.hidden = false;
      if (voiceState) voiceState.textContent = "🎤 Đang nghe… (Bấm Dừng để xem lại chữ trước khi gửi)";
      if (voicePreview) voicePreview.textContent = "Hãy nói câu hỏi của bạn…";

      recognition.onresult = (event) => {
        let text = "";
        for (let i = 0; i < event.results.length; i++) {
          text += event.results[i][0].transcript;
        }
        heardTranscript = text;
        if (voicePreview) {
          voicePreview.textContent = 'Bản nháp: "' + text + '" (Bấm Dừng & Xem chữ để chỉnh sửa trước khi gửi)';
        }
      };

      recognition.onerror = (event) => {
        const reason =
          event.error === "not-allowed"
            ? "Bạn đã từ chối quyền micro hoặc trình duyệt chặn micro. Hãy nhập câu hỏi bằng văn bản nhé."
            : "Không nhận diện được giọng nói (" + event.error + "). Bạn có thể thử lại hoặc nhập văn bản.";
        stopVoiceRecognition(true);
        say("🎤 " + reason, "bot", { badge: "Trạng thái Micro" });
        input.focus();
      };

      recognition.onend = () => {
        if (recognition) {
          stopVoiceRecognition(false);
        }
      };

      try {
        recognition.start();
      } catch (e) {
        stopVoiceRecognition(true);
      }
    });
  }

  if (voiceStopBtn) {
    voiceStopBtn.addEventListener("click", () => stopVoiceRecognition(false));
  }
  if (voiceCancelBtn) {
    voiceCancelBtn.addEventListener("click", () => stopVoiceRecognition(true));
  }

  // Keep chat panel comfortable when mobile virtual keyboard opens
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      if (!panel.hidden) {
        panel.style.maxHeight = Math.max(260, window.visualViewport.height - 90) + "px";
      }
    });
  }
})();
