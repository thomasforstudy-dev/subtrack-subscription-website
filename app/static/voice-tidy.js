// Tidies what Subby's mic heard before it goes in the question box.
// Browser speech recognition writes Vietnamese with no punctuation or capitals,
// spells brand names the way they sound ("nét phích") and mixes how it writes
// money ("260 nghìn", "1 triệu rưỡi"). Gemini's transcripts go through here too.
// Plain functions, so tests/test_voice_tidy.py can run them in Node.

(function (global) {
  "use strict";

  // A whole-word match that works with Vietnamese letters (JS's \b only knows a-z).
  function words(source) {
    return new RegExp("(?<![\\p{L}\\p{N}])(?:" + source + ")(?![\\p{L}\\p{N}])", "giu");
  }

  // [correct spelling, how it is written or misheard]. Longer names come first
  // so "YouTube Premium" wins over "YouTube".
  const TERMS = [
    ["YouTube Premium", "(?:you ?tube|du ?túp|diu ?túp|giu ?túp) ?(?:premium|pri ?mi ?um|pờ ?ri ?mi ?ầm)"],
    ["YouTube", "you ?tube|du ?túp|diu ?túp|giu ?túp"],
    ["Netflix", "net ?flix|nét ?(?:phích|phlích|flích|flix|phờ ?lích|phờ ?líc)|nẹt ?phích"],
    ["Spotify", "spotify|spo ?ti ?(?:fy|phai)|(?:sờ ?)?pô ?ti ?phai|xpo ?ti ?phai"],
    ["ChatGPT", "chat ?gpt|chát ?(?:gpt|gi ?pi ?ti|giê ?pi ?ti)|chat ?gi ?pi ?ti"],
    ["iCloud", "i ?cloud|ai ?(?:cloud|clao|cờ ?lao)"],
    ["Google One", "(?:google|gu ?gồ|gu ?gô) ?(?:one|oan)"],
    ["Google", "google|gu ?gồ|gu ?gô"],
    ["Gemini", "gemini|giê ?mi ?nai"],
    ["Apple Music", "apple ?music|(?:áp|ép) ?pồ ?(?:music|miu ?dích|miu ?dic)"],
    ["Disney+", "disney ?(?:plus|\\+)|đít ?ni ?(?:plus|cộng)"],
    ["Canva", "canva|can ?va"],
    ["Gmail", "gmail|gờ ?meo|gi ?meo"],
    ["Shopee", "shopee|sốp ?pi|shop ?pi"],
    ["VNPay", "vn ?pay|vê ?en ?pay|vê ?nờ ?pây"],
    ["MoMo", "momo"],
    ["Zalo", "zalo|za ?lô"],
    ["Subby", "subby|sub ?bi|sáp ?bi|xáp ?bi"],
  ].map(([name, heard]) => [name, words(heard)]);

  const FILLERS = words("ừm+|ờm+|ưm+|uhm+|umm*|uh+|hmm+");
  const LEADING_FILLER = /^(?:ờ|ơ|à|ừ)[\s,]+/iu;

  // Vietnamese questions end or start with one of these words.
  const VI_QUESTION_END = /(?:không|hông|chưa|gì|nào|sao|đâu|bao nhiêu|mấy|hả|hở|nhỉ|chứ|chăng|à|ư|bao giờ|khi nào)$/iu;
  const VI_QUESTION_START = /^(?:bao giờ|khi nào|lúc nào|tại sao|vì sao|sao|làm sao|làm thế nào|như thế nào|thế nào|ai|cái gì|ở đâu|bao nhiêu|mấy|có phải|liệu)(?![\p{L}])/iu;
  // ...or ask in the middle: "Netflix bao giờ gia hạn" (but "chưa bao giờ" means "never").
  const VI_QUESTION_MID = /(?<![\p{L}])(?:(?<!(?:chưa|không|chẳng) )bao giờ|bao nhiêu|tại sao|vì sao|như thế nào|ở đâu|mấy giờ)(?![\p{L}])/iu;
  const EN_QUESTION_START = /^(?:what|when|where|why|who|whose|which|how|can|could|would|will|should|do|does|did|is|are|am|was|were|have|has|may)\b/i;

  function thousands(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  // "1 triệu 2" means 1.200.000, "1 triệu 25" 1.250.000: the digits after
  // "triệu" are the next hundreds of thousands.
  function afterMillion(digits) {
    return Number((digits + "00").slice(0, 3)) * 1000;
  }

  const NUM = "(?<![\\d.,])(\\d{1,3})";
  const MONEY = [
    // 1 triệu 250 nghìn -> 1.250.000
    [new RegExp(NUM + " ?triệu (\\d{1,3}) ?(?:nghìn|ngàn|k)(?![\\p{L}])", "giu"), (m, a, b) => thousands(a * 1e6 + b * 1e3)],
    // 1 triệu rưỡi -> 1.500.000
    [new RegExp(NUM + " ?triệu rưỡi", "giu"), (m, a) => thousands(a * 1e6 + 5e5)],
    // 1,5 triệu / 1.5 triệu -> 1.500.000
    [new RegExp(NUM + "[,.](\\d{1,2}) ?triệu", "giu"), (m, a, b) => thousands(a * 1e6 + afterMillion(b))],
    // 1 triệu 2 -> 1.200.000 (a lone number right after "triệu"; not "1 triệu 2 tháng")
    [new RegExp(NUM + " ?triệu (\\d{1,3})(?![\\d.,\\p{L}])(?! ?(?:tháng|năm|ngày|tuần|lần|gói|người|tài khoản))", "giu"),
      (m, a, b) => thousands(a * 1e6 + afterMillion(b))],
    // 2 triệu -> 2.000.000
    [new RegExp(NUM + " ?triệu", "giu"), (m, a) => thousands(a * 1e6)],
    // 2 trăm nghìn -> 200.000
    [new RegExp(NUM + " trăm (?:nghìn|ngàn)", "giu"), (m, a) => thousands(a * 1e5)],
    // 50 nghìn rưỡi -> 50.500
    [new RegExp(NUM + " ?(?:nghìn|ngàn) rưỡi", "giu"), (m, a) => thousands(a * 1e3 + 500)],
    // 260 nghìn / 260k -> 260.000
    [new RegExp(NUM + " ?(?:nghìn|ngàn|k)(?![\\p{L}])", "giu"), (m, a) => thousands(a * 1e3)],
    // 10 đô (la) -> 10 USD, but not "đô thị" (city)
    [/(\d[\d.,]*) ?(?:đô la|đô-la|đô(?! ?thị))(?![\p{L}])/giu, (m, a) => a + " USD"],
  ];

  function isQuestion(text, lang) {
    const bare = text.replace(/[\s.,!?…]+$/u, "");
    if (lang === "en") return EN_QUESTION_START.test(bare);
    return VI_QUESTION_END.test(bare) || VI_QUESTION_START.test(bare) || VI_QUESTION_MID.test(bare);
  }

  // Android Chrome repeats the whole sentence so far in each new result
  // ("thêm", "thêm Netflix", "thêm Netflix 260 nghìn"): keep the longest.
  function joinSegments(parts) {
    let text = "";
    parts.forEach((part) => {
      const piece = String(part || "").trim();
      if (!piece) return;
      if (text && piece.toLowerCase().startsWith(text.toLowerCase())) text = piece;
      else text = text ? text + " " + piece : piece;
    });
    return text;
  }

  function tidy(raw, lang) {
    // NFC: the same letter "ế" can arrive as one or as three code points,
    // and only one of them matches when Subby searches the question.
    let text = String(raw || "").normalize("NFC").replace(/\s+/g, " ").trim();
    if (!text) return "";

    text = text.replace(FILLERS, " ").replace(LEADING_FILLER, "");
    TERMS.forEach(([name, pattern]) => { text = text.replace(pattern, name); });
    if (lang !== "en") MONEY.forEach(([pattern, fix]) => { text = text.replace(pattern, fix); });

    text = text.replace(/\s+([.,!?…])/g, "$1").replace(/\s+/g, " ").trim();
    if (!text) return "";
    text = text.charAt(0).toLocaleUpperCase(lang === "en" ? "en" : "vi") + text.slice(1);
    if (!/[.!?…]$/.test(text)) text += isQuestion(text, lang) ? "?" : ".";
    return text;
  }

  const VoiceTidy = { tidy, joinSegments, isQuestion };
  if (typeof module !== "undefined" && module.exports) module.exports = VoiceTidy;
  else global.VoiceTidy = VoiceTidy;
})(typeof window !== "undefined" ? window : globalThis);
