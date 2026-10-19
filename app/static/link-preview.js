// When a link is pasted, ask the server for the page's title and fill the
// Title box (only if it's still empty, so we never overwrite what you typed).
// Also checks if the URL is already saved on the page to warn about duplicates.
(function () {
  function normalizeForCompare(raw) {
    let u = (raw || "").trim();
    if (!u) return "";
    if (!/^[a-z][a-z0-9+.-]*:/i.test(u)) {
      u = "https://" + u;
    }
    try {
      const parsed = new URL(u);
      return (parsed.origin + parsed.pathname).replace(/\/+$/, "").toLowerCase() + parsed.search;
    } catch (e) {
      return u.toLowerCase();
    }
  }

  document.querySelectorAll("form[data-link-preview]").forEach((form) => {
    const urlInput = form.querySelector("[name=url]");
    const titleInput = form.querySelector("[name=title]");
    const notesInput = form.querySelector("[name=notes]");
    const endpoint = form.dataset.linkPreview;
    const container = form.closest(".card") || form.parentElement;
    const statusEl = container ? container.querySelector("[data-preview-status]") : null;
    const dupBanner = container ? container.querySelector("[data-duplicate-banner]") : null;
    const dupTitle = dupBanner ? dupBanner.querySelector("[data-duplicate-title]") : null;
    const dupEditLink = dupBanner ? dupBanner.querySelector("[data-duplicate-edit-link]") : null;

    let lastUrl = "";
    let timer;

    function setStatus(text, stateClass) {
      if (!statusEl) return;
      if (!text) {
        statusEl.hidden = true;
        statusEl.textContent = "";
        statusEl.className = "preview-status muted small-text";
        return;
      }
      statusEl.hidden = false;
      statusEl.textContent = text;
      statusEl.className = "preview-status small-text " + (stateClass || "muted");
    }

    function checkDuplicate() {
      if (!dupBanner || !urlInput) return;
      const candidate = normalizeForCompare(urlInput.value);
      if (!candidate) {
        dupBanner.hidden = true;
        return;
      }
      const existingItems = document.querySelectorAll("[data-saved-url]");
      let match = null;
      existingItems.forEach((li) => {
        if (normalizeForCompare(li.dataset.savedUrl) === candidate) {
          match = li;
        }
      });
      if (match) {
        dupBanner.hidden = false;
        if (dupTitle) dupTitle.textContent = '"' + (match.dataset.savedTitle || match.dataset.savedUrl) + '"';
        if (dupEditLink && match.dataset.editUrl) {
          dupEditLink.setAttribute("href", match.dataset.editUrl);
        }
      } else {
        dupBanner.hidden = true;
      }
    }

    async function lookUp() {
      const url = urlInput.value.trim();
      checkDuplicate();
      if (!url || url === lastUrl || titleInput.value.trim()) return;
      lastUrl = url;

      const placeholder = titleInput.placeholder;
      titleInput.placeholder = "Đang lấy tiêu đề trang…";
      form.classList.add("looking-up");
      setStatus("⏳ Đang tự động lấy tiêu đề từ trang đích…", "status-loading");

      try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const headers = { "Content-Type": "application/x-www-form-urlencoded" };
        if (csrfMeta && csrfMeta.content) {
          headers["X-CSRF-Token"] = csrfMeta.content;
        }
        const res = await fetch(endpoint, {
          method: "POST",
          headers,
          body: new URLSearchParams({ url }),
        });
        if (!res.ok) {
          setStatus(
            "ℹ Không lấy được tiêu đề tự động — bạn có thể tự nhập hoặc hệ thống sẽ dùng tên miền.",
            "status-fallback"
          );
          return;
        }
        const data = await res.json();
        if (urlInput.value.trim() !== url) return;
        if (data.title && !titleInput.value.trim()) {
          titleInput.value = data.title;
          setStatus("✓ Đã tự động điền tiêu đề trang web.", "status-ok");
        } else if (!titleInput.value.trim()) {
          setStatus(
            "ℹ Trang này không cung cấp tiêu đề công khai — hãy tự nhập tiêu đề hoặc lưu để dùng tên miền.",
            "status-fallback"
          );
        }
        if (notesInput && data.description && !notesInput.value.trim()) {
          notesInput.value = data.description;
        }
      } catch (err) {
        setStatus(
          "ℹ Không kết nối được xem trước tiêu đề — bạn có thể tự nhập tiêu đề và lưu bình thường.",
          "status-fallback"
        );
      } finally {
        titleInput.placeholder = placeholder;
        form.classList.remove("looking-up");
      }
    }

    urlInput.addEventListener("paste", () => setTimeout(lookUp, 0));
    urlInput.addEventListener("change", lookUp);
    urlInput.addEventListener("input", () => {
      checkDuplicate();
      clearTimeout(timer);
      timer = setTimeout(lookUp, 700);
    });
  });
})();
