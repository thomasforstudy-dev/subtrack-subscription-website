// When a link is pasted, ask the server for the page's title and fill the
// Title box (only if it's still empty, so we never overwrite what you typed).
document.querySelectorAll("form[data-link-preview]").forEach((form) => {
  const urlInput = form.querySelector("[name=url]");
  const titleInput = form.querySelector("[name=title]");
  const notesInput = form.querySelector("[name=notes]");
  const endpoint = form.dataset.linkPreview;
  let lastUrl = "";
  let timer;

  async function lookUp() {
    const url = urlInput.value.trim();
    if (!url || url === lastUrl || titleInput.value.trim()) return;
    lastUrl = url;

    const placeholder = titleInput.placeholder;
    titleInput.placeholder = "Finding the page title…";
    form.classList.add("looking-up");
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          // The server refuses POSTs without this (CSRF protection).
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || "",
        },
        body: new URLSearchParams({ url }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (urlInput.value.trim() !== url) return; // link changed while we waited
      if (data.title && !titleInput.value.trim()) titleInput.value = data.title;
      if (notesInput && data.description && !notesInput.value.trim()) {
        notesInput.value = data.description;
      }
    } catch (err) {
      // Lookup failed: no problem, the server uses the domain name instead.
    } finally {
      titleInput.placeholder = placeholder;
      form.classList.remove("looking-up");
    }
  }

  urlInput.addEventListener("paste", () => setTimeout(lookUp, 0));
  urlInput.addEventListener("change", lookUp);
  urlInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(lookUp, 800);
  });
});
