// Subby, the help bot. Questions go to the server, which asks Gemini
// (app/subby.py). If that fails, Subby uses the small answer list below.
(function () {
  const root = document.querySelector("[data-subby]");
  if (!root) return;

  const panel = root.querySelector("#subby-panel");
  const openBtn = root.querySelector("[data-open]");
  const log = root.querySelector("[data-log]");
  const form = root.querySelector("[data-form]");
  const input = form.querySelector("[name=q]");
  const funBox = root.querySelector("[data-fun]");
  const handoff = root.querySelector("[data-handoff]");

  // Each answer: words to look for, a funny reply and a plain reply.
  const ANSWERS = [
    {
      words: ["remind", "email", "notify", "warn", "before"],
      fun: "I email you before a renewal. You pick how early: 14 days, 7 days or 3–5 days. Or all three, if you trust yourself as much as I trust my Wi-Fi.",
      plain: "SubTrack emails you before each renewal. You choose how many days before, for example 14, 7 or 3.",
    },
    {
      words: ["add", "netflix", "spotify", "new subscription"],
      fun: "Log in, tap Add, type the name, price and next renewal date. Done. Faster than finding Netflix's cancel button.",
      plain: "Log in, click Add, then enter the name, price and next renewal date, and save.",
    },
    {
      words: ["pin", "link", "bookmark"],
      fun: "Pinned links are your 'I'll need this later' drawer. Paste a link, I grab the page title, you pin it to the top. Cancel pages love it here.",
      plain: "Pinned links save pages you need later. Paste a link, the title fills in automatically, and you can pin it to the top.",
    },
    {
      words: ["cancel", "unsubscribe", "stop"],
      fun: "I can't cancel things for you (no hands 🙃). But save the cancel page as a pinned link and it's one tap away when my reminder lands.",
      plain: "SubTrack can't cancel for you, but you can save each service's cancel page as a pinned link so it's ready when the reminder arrives.",
    },
    {
      words: ["credit", "card", "payment", "bill"],
      fun: "Add your card's payment due date like any subscription and I'll nag you before it's due. Lovingly.",
      plain: "Add your credit card payment due date like a subscription, and you'll get a reminder before it's due.",
    },
    {
      words: ["sign up", "signup", "register", "account", "password"],
      fun: "Hit Sign up, type your email and a password (8+ characters, not 'password123', I'm begging).",
      plain: "Click Sign up and enter your email and a password with at least 8 characters.",
    },
    {
      words: ["hello", "hi ", "hey ", "chào"],
      fun: "Hey! I'm Subby. I know a lot about subscriptions and nothing about your ex. Ask away.",
      plain: "Hi! I'm Subby. Ask me anything about SubTrack.",
    },
  ];

  // Money questions always go to the owner, even if they mention "Netflix".
  const ASK_OWNER = ["refund", "money back", "charged", "price", "free", "cost", "pay you"];

  function findAnswer(question) {
    // Keep letters/numbers only and pad with spaces, so " add" matches the
    // word "add" but not "address" or "padding".
    const q = " " + question.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ") + " ";
    const has = (w) => q.includes(" " + w);
    if (ASK_OWNER.some(has)) return null;
    const hit = ANSWERS.find((a) => a.words.some(has));
    if (!hit) return null;
    return funBox.checked ? hit.fun : hit.plain;
  }

  // textContent (not innerHTML) so nothing the user types can run as code.
  function say(text, who) {
    const p = document.createElement("p");
    p.className = "msg " + who;
    p.textContent = text;
    log.append(p);
    log.scrollTop = log.scrollHeight;
    return p;
  }

  // Earlier messages, so Gemini understands follow-up questions.
  const history = [];

  function showHandoff(text) {
    say(text, "bot");
    log.append(handoff.content.cloneNode(true));
    log.scrollTop = log.scrollHeight;
  }

  // Ask the server (Gemini). Returns {answer, handoff} or null if it failed.
  async function askServer(question) {
    try {
      const res = await fetch(root.dataset.askUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, fun: funBox.checked, history: history.slice(-6) }),
      });
      const data = await res.json();
      return data.answer ? data : null;
    } catch (err) {
      return null; // offline or server error: use the built-in answers
    }
  }

  async function reply(question) {
    const typing = say("Subby is thinking…", "bot typing");
    const data = await askServer(question);
    typing.remove();

    if (data) {
      if (data.handoff) showHandoff(data.answer);
      else say(data.answer, "bot");
      history.push({ role: "user", text: question }, { role: "bot", text: data.answer });
      return;
    }

    // Gemini isn't available: fall back to the small list above.
    const answer = findAnswer(question);
    if (answer) {
      say(answer, "bot");
      return;
    }
    showHandoff(
      funBox.checked
        ? "That one is above my pay grade 😅 Let me get the human."
        : "I don't know that one yet. You can ask the owner directly:"
    );
  }

  function ask(question) {
    question = question.trim();
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
        say("Hi, I'm Subby! Ask me about reminders, pinned links or anything SubTrack. 👋", "bot");
      }
      input.focus();
    }
  }

  openBtn.addEventListener("click", () => setOpen(panel.hidden));
  root.querySelector("[data-close]").addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) setOpen(false);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    ask(input.value);
    input.value = "";
  });

  root.querySelectorAll("[data-ask]").forEach((chip) => {
    chip.addEventListener("click", () => ask(chip.textContent));
  });

  root.querySelector("[data-mic]").addEventListener("click", () => {
    say("Voice chat is coming very soon. For now my ears are just decorative. 👂", "bot");
  });
})();
