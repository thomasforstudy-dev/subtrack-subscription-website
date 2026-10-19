// Subby: trợ lý trò chuyện hướng dẫn & tra cứu tài khoản.
// - Hỏi máy chủ trước (POST /subby/ask -> Gemini hoặc Phi-3.5-mini trên máy chủ).
// - Hiển thị trung thực provider (gemini / phi / fake) và cảnh báo rõ khi fallback sang mô hình đám mây (fallback: true).
// - Hiển thị an toàn kết quả Account Tools (list_upcoming_renewals, search_saved_links, summarize_transactions, create_reminder_draft) bằng DOM API (textContent), không bao giờ dùng innerHTML và không gửi dữ liệu riêng tư vào lịch sử hội thoại.
// - Chế độ Giọng nói (Web Speech API — SpeechRecognition & speechSynthesis):
//   + Chỉ xin quyền micro sau khi người dùng chủ động bấm nút Mic ([data-mic] hoặc [data-voice-orb]).
//   + Hỗ trợ đầy đủ 4 trạng thái (idle / listening / thinking / speaking), xem/chỉnh bản nháp lời nói trước khi gửi, đọc câu trả lời (TTS) theo ngôn ngữ VI/EN, và luôn giữ ô nhập bàn phím hoạt động song song.

(function () {
  "use strict";

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
      fun: "Bạn chọn số ngày muốn được nhắc trước ngày gia hạn dự kiến (tối đa 3 mốc như 14, 7, 3 ngày) và giờ nhận trong Cài đặt. Khi công việc nhắc lịch chạy trên máy chủ và email đã xác thực, hệ thống sẽ gửi thông báo để bạn chủ động giữ hoặc hủy gói!",
      plain: "Bạn có thể đặt tối đa 3 mốc nhắc trước ngày gia hạn dự kiến (ví dụ: 14,7,3 ngày) và cấu hình múi giờ/giờ nhắc trong Cài đặt.",
    },
    {
      words: ["add", "new", "netflix", "spotify", "track", "how do i", "start", "thêm", "tạo", "mới", "bắt đầu"],
      fun: "Bấm '+ Thêm gói', điền tên dịch vụ (như Netflix), số tiền, chu kỳ thanh toán, ngày gia hạn dự kiến tiếp theo và các mốc nhắc (ví dụ 14,7,3). Chưa đầy 20 giây là xong!",
      plain: "Bấm '+ Thêm gói đăng ký', nhập tên dịch vụ, giá tiền, chu kỳ, ngày gia hạn tiếp theo, các mốc ngày nhắc và bấm Lưu.",
    },
    {
      words: ["pin", "pinned", "link", "links", "bookmark", "save a link", "ghim", "đường dẫn", "lưu link"],
      fun: "Link đã ghim là nơi cất giữ các trang quản lý/hủy gói khó tìm (như trang hủy Adobe hay Netflix). Khi dán URL, máy chủ tự lấy tiêu đề và biểu tượng trang web; tới kỳ gia hạn chỉ cần 1 cú nhấp là mở đúng chỗ!",
      plain: "Link đã ghim giúp lưu lại URL trang quản lý hoặc hủy dịch vụ, tự động lấy tiêu đề và biểu tượng trang, hỗ trợ tìm kiếm theo thẻ.",
    },
    {
      words: ["cancel", "unsubscribe", "stop a subscription", "hủy", "tự hủy"],
      fun: "Mình không tự bấm nút hủy thay bạn (vì SubTrack không bao giờ giữ mật khẩu Netflix hay thẻ ngân hàng của bạn). Thay vào đó, mình giữ sẵn đường dẫn hủy đã ghim để bạn tự hủy ngay khi nhận lời nhắc!",
      plain: "SubTrack không đăng nhập vào tài khoản dịch vụ của bạn. Bạn hãy lưu URL hủy vào mục Link đã lưu hoặc ô đường dẫn quản lý để mở nhanh khi cần.",
    },
    {
      words: ["bill", "bills", "ocr", "receipt", "statement", "hóa đơn", "sao kê", "chứng từ"],
      fun: "Khu vực Hóa đơn & Chứng từ hỗ trợ xem đối chiếu tài liệu 2 cột (Tài liệu gốc & Trường trích xuất). Hiện tại giao diện này đang ở chế độ xem mẫu (Demo) chờ kết nối bộ đọc OCR trên máy chủ!",
      plain: "Mục Hóa đơn & Chứng từ minh họa quy trình đối chiếu hóa đơn 2 cột trước khi lưu. Tính năng OCR máy chủ đang được phát triển.",
    },
    {
      words: ["password", "login", "account", "sign up", "mật khẩu", "đăng nhập", "tài khoản", "đăng ký"],
      fun: "Mật khẩu được băm bảo mật (tối thiểu 12 ký tự gồm chữ hoa, chữ thường, số và ký tự đặc biệt). Mỗi tài khoản chỉ nhìn thấy dữ liệu của chính mình!",
      plain: "Đăng ký bằng tên người dùng, email và mật khẩu từ 12 ký tự trở lên. Dữ liệu của mỗi người dùng được cách ly hoàn toàn.",
    },
    {
      words: ["hello", "hi ", "hey ", "chào", "xin chào"],
      fun: "Chào bạn! Mình là Subby 👋 Mình rành chuyện gói đăng ký, lịch gia hạn và link đã lưu. Bạn muốn hỏi bằng chữ hay thử bấm Mic nói chuyện nào?",
      plain: "Xin chào! Mình là Subby. Bạn có thể nhập câu hỏi hoặc bấm nút Mic để hỏi bằng giọng nói.",
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

  function setVoiceStageState(state, customLabel) {
    if (voiceStage) {
      voiceStage.dataset.stageState = state;
    }
    if (voiceDetectorLabel) {
      if (customLabel) {
        voiceDetectorLabel.textContent = customLabel;
      } else if (state === "listening") {
        voiceDetectorLabel.textContent = "🎤 Active Speech Detected · Đang nghe (Nhấn Mic để dừng)";
      } else if (state === "thinking") {
        voiceDetectorLabel.textContent = "🤔 Subby đang suy nghĩ câu trả lời…";
      } else if (state === "speaking") {
        voiceDetectorLabel.textContent = "🔊 Subby đang đọc câu trả lời…";
      } else {
        voiceDetectorLabel.textContent = "Nhấn biểu tượng Mic ở giữa để bắt đầu nói";
      }
    }
    if (voiceLiveBadge) {
      if (state === "listening") {
        voiceLiveBadge.textContent = "● Live audio";
        voiceLiveBadge.classList.add("is-live");
      } else if (state === "thinking") {
        voiceLiveBadge.textContent = "● Đang gửi…";
        voiceLiveBadge.classList.remove("is-live");
      } else {
        voiceLiveBadge.textContent = "● Chờ giọng nói";
        voiceLiveBadge.classList.remove("is-live");
      }
    }
    if (voiceSpeakPill) {
      if (state === "speaking") {
        voiceSpeakPill.textContent = "🔊 Speaking…";
        voiceSpeakPill.classList.add("is-speaking");
      } else if (voiceMuted) {
        voiceSpeakPill.textContent = "🔇 Đã tắt tiếng";
        voiceSpeakPill.classList.remove("is-speaking");
      } else {
        voiceSpeakPill.textContent = "🔈 Sẵn sàng";
        voiceSpeakPill.classList.remove("is-speaking");
      }
    }
  }

  function resetActiveSpeakBtn() {
    if (activeSpeakBtn) {
      activeSpeakBtn.textContent = "🔊 Đọc";
      activeSpeakBtn.classList.remove("is-speaking");
      activeSpeakBtn.setAttribute("aria-pressed", "false");
      activeSpeakBtn = null;
    }
  }

  function stopSpeaking() {
    if ("speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {
        // ignore
      }
    }
    if (ttsStopBtn) ttsStopBtn.hidden = true;
    resetActiveSpeakBtn();
    if (voiceStage && voiceStage.dataset.stageState === "speaking") {
      setVoiceStageState("idle");
    }
  }

  function pickPreferredVoice(langCode) {
    if (!("speechSynthesis" in window) || typeof window.speechSynthesis.getVoices !== "function") {
      return null;
    }
    const voices = window.speechSynthesis.getVoices() || [];
    const prefix = langCode.slice(0, 2).toLowerCase();
    return (
      voices.find((v) => v.lang && v.lang.toLowerCase() === langCode.toLowerCase()) ||
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(prefix)) ||
      null
    );
  }

  function speakText(text, triggerBtn) {
    if (!("speechSynthesis" in window) || !text) return;
    if (triggerBtn && triggerBtn === activeSpeakBtn) {
      stopSpeaking();
      return;
    }
    stopSpeaking();
    const utter = new SpeechSynthesisUtterance(text);
    const isVi = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(text);
    utter.lang = isVi ? "vi-VN" : "en-US";
    const matchedVoice = pickPreferredVoice(utter.lang);
    if (matchedVoice) utter.voice = matchedVoice;

    if (ttsStopBtn) ttsStopBtn.hidden = false;
    if (triggerBtn) {
      activeSpeakBtn = triggerBtn;
      triggerBtn.textContent = "⏹ Dừng đọc";
      triggerBtn.classList.add("is-speaking");
      triggerBtn.setAttribute("aria-pressed", "true");
    }
    setVoiceStageState("speaking");

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

    if (who.includes("bot") && !who.includes("typing") && "speechSynthesis" in window) {
      const footer = document.createElement("div");
      footer.className = "msg-tools";
      const speakBtn = document.createElement("button");
      speakBtn.type = "button";
      speakBtn.className = "msg-tool-btn";
      speakBtn.textContent = "🔊 Đọc";
      speakBtn.setAttribute("aria-label", "Đọc to câu trả lời này");
      speakBtn.setAttribute("aria-pressed", "false");
      speakBtn.addEventListener("click", () => speakText(text, speakBtn));
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
          button.textContent = "Kiểm tra và lưu / Check and save";
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
          "☁ Lưu ý: Mô hình nội bộ hiện không khả dụng; câu trả lời này được tạo bởi mô hình đám mây dự phòng (answered by a cloud model).";
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
      updateProviderStatus("rate-limit", "Tạm giới hạn lượt hỏi (429)", "Rate limit");
      updateVoiceReplyCard(result.answer, true);
      say(result.answer, "bot", {
        badge: "⏳ Giới hạn lượt hỏi — Chờ ít phút",
        retryQuestion: question,
      });
      setVoiceStageState("idle");
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
      const reasonText =
        result.reason === "model-offline"
          ? "Mô hình AI ngoại tuyến (model-offline)"
          : "AI tạm nghỉ (" + (result.reason || "offline") + ")";
      updateProviderStatus(
        "fallback",
        reasonText + " · Đang dùng bộ câu trả lời có sẵn (FAQ Fallback)",
        "FAQ Fallback"
      );
    }

    const answer = findAnswer(question);
    if (answer) {
      updateVoiceReplyCard(answer, true);
      say(answer, "bot", {
        badge: "📋 Câu trả lời hướng dẫn có sẵn (FAQ Fallback — máy chủ AI chưa kết nối)",
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
        ? "Máy chủ AI hiện chưa phản hồi và câu này cũng nằm ngoài sổ tay FAQ có sẵn của mình 😅 Bạn có thể thử lại hoặc nhắn trực tiếp cho chủ sở hữu:"
        : "Hiện máy chủ AI chưa phản hồi cho câu hỏi này. Bạn có thể bấm Thử lại hoặc liên hệ trực tiếp với chủ sở hữu:";
    updateVoiceReplyCard(handoffMsg, true);
    showHandoff(handoffMsg, {
      badge: "📋 Chế độ FAQ Fallback (Không giả lập câu trả lời AI động)",
      retryQuestion: question,
    });
    setVoiceStageState("idle");
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question) return;
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
    }
  }

  function setOpen(open) {
    panel.hidden = !open;
    root.classList.toggle("open", open);
    openBtn.setAttribute("aria-expanded", String(open));
    if (teaser) teaser.hidden = true;
    if (open) {
      if (!log.children.length) {
        say(
          "Chào bạn, mình là Subby! Bạn có thể hỏi về lời nhắc gia hạn, link đã ghim, hóa đơn hoặc bấm 🎙️ Voice để nói chuyện trực tiếp. 👋",
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
    ask(input.value);
    input.value = "";
  });

  root.querySelectorAll("[data-ask]").forEach((chip) => {
    chip.addEventListener("click", () => ask(chip.getAttribute("data-en") && document.documentElement.getAttribute("data-ui-lang") === "en" ? chip.getAttribute("data-en") : chip.textContent));
  });

  // ---------- Voice Input (SpeechRecognition — requests mic ONLY when clicked) ----------
  let recognition = null;
  let heardTranscript = "";

  function syncMicButtons(isListening) {
    [micBtn, voiceOrbBtn].forEach((btn) => {
      if (!btn) return;
      btn.classList.toggle("listening", isListening);
      btn.setAttribute("aria-pressed", String(isListening));
    });
  }

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
    syncMicButtons(false);
    if (voiceBar) voiceBar.hidden = true;

    const cleanText = heardTranscript.trim();
    if (!cancelled && cleanText) {
      input.value = cleanText;
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = "“" + cleanText + "”";
      }
      if (voiceTranscriptActions) {
        voiceTranscriptActions.hidden = false;
      }
      setVoiceStageState(
        "idle",
        "✓ Đã ghi nhận câu hỏi — Bấm '🚀 Gửi câu hỏi này' hoặc chỉnh dưới ô chữ"
      );
      input.focus();
    } else if (cancelled) {
      heardTranscript = "";
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
    if (recognition) {
      stopVoiceRecognition(false);
      return;
    }
    stopSpeaking();

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      setVoiceStageState(
        "idle",
        "🔇 Trình duyệt này chưa hỗ trợ Web Speech API — Hãy nhập câu hỏi bằng bàn phím bên dưới"
      );
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
    const uiLang = document.documentElement.getAttribute("data-ui-lang") || document.documentElement.lang || "vi";
    recognition.lang = uiLang === "en" ? "en-US" : "vi-VN";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    syncMicButtons(true);
    setVoiceStageState("listening");
    if (voiceBar && (!voiceStage || voiceStage.hidden)) {
      voiceBar.hidden = false;
    }
    if (voiceState) {
      voiceState.textContent = "🎤 Đang nghe… (Bấm Dừng để xem lại chữ trước khi gửi)";
    }
    if (voicePreview) {
      voicePreview.textContent = "Hãy nói câu hỏi của bạn…";
    }
    if (voiceTranscriptEl) {
      voiceTranscriptEl.textContent = "“Đang lắng nghe giọng nói của bạn…”";
    }
    if (voiceTranscriptActions) {
      voiceTranscriptActions.hidden = true;
    }

    recognition.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      heardTranscript = text;
      const trimmed = text.trim();
      if (voicePreview) {
        voicePreview.textContent =
          'Bản nháp: "' + trimmed + '" (Bấm Dừng & Xem chữ để chỉnh sửa trước khi gửi)';
      }
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = "“" + trimmed + "”";
      }
      if (voiceTranscriptActions && trimmed) {
        voiceTranscriptActions.hidden = false;
      }
    };

    recognition.onerror = (event) => {
      const reason =
        event.error === "not-allowed"
          ? "Bạn đã từ chối quyền micro hoặc trình duyệt chặn micro. Hãy nhập câu hỏi bằng bàn phím nhé."
          : "Không nhận diện được giọng nói (" + event.error + "). Bạn có thể thử lại hoặc nhập văn bản.";
      stopVoiceRecognition(true);
      setVoiceStageState("idle", "⚠ " + reason);
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
      const textToSend = (heardTranscript || input.value || "").trim();
      if (recognition) stopVoiceRecognition(true);
      heardTranscript = "";
      input.value = "";
      if (textToSend) ask(textToSend);
    });
  }

  if (voiceToInputBtn) {
    voiceToInputBtn.addEventListener("click", () => {
      const textToEdit = (heardTranscript || input.value || "").trim();
      if (recognition) stopVoiceRecognition(false);
      if (textToEdit) input.value = textToEdit;
      input.focus();
    });
  }

  if (voiceClearDraftBtn) {
    voiceClearDraftBtn.addEventListener("click", () => {
      stopVoiceRecognition(true);
      input.value = "";
      if (voiceTranscriptEl) {
        voiceTranscriptEl.textContent = "“Nhấn Mic để nói câu hỏi hoặc dùng bàn phím bên dưới…”";
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
        voiceMuteLabel.textContent = voiceMuted ? "Đã tắt tiếng" : "Đọc tiếng";
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
      stopVoiceRecognition(false);
      setVoiceModeOpen(false);
      input.focus();
    });
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
