// Execute the shipped voice callbacks with synthetic speech events; no microphone.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('app/static/subby.js', 'utf8');
const section = source.slice(source.indexOf('  let recognition = null;'), source.indexOf('  if (voiceMuteBtn)'));
const modeFunctions = source.slice(source.indexOf('  function setVoiceModeOpen('), source.indexOf('  openBtn.addEventListener('));
const escapeHandler = source.slice(source.indexOf('  document.addEventListener("keydown"'), source.indexOf('  form.addEventListener("submit"'));
assert.ok(section.includes('recognition.onresult'));
function button() {
  return { handlers: {}, classList: { toggle() {} }, setAttribute() {},
    addEventListener(name, callback) { this.handlers[name] = callback; },
    click() { this.handlers.click(); } };
}
const buttons = Object.fromEntries(['micBtn', 'voiceOrbBtn', 'voiceStopBtn', 'voiceCancelBtn',
  'voiceSendNowBtn', 'voiceToInputBtn', 'voiceClearDraftBtn'].map(name => [name, button()]));
let active, starts = 0;
class Speech {
  constructor() { active = this; }
  start() { starts++; }
  stop() { if (this.onend) this.onend(); }
  abort() {}
}
const timers = [];  // fake setTimeout: the test decides when the pause is over
const langBtn = { textContent: '', title: '', handlers: {},
  addEventListener(name, callback) { this.handlers[name] = callback; }, click() { this.handlers.click(); } };
const sent = [];
const spokenLog = [];
let currentUiLang = 'en';
const context = { ...buttons, window: { SpeechRecognition: Speech, VoiceTidy: require('../app/static/voice-tidy.js') },
  setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; },
  clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cleared = true; },
  document: { documentElement: { lang: 'en', getAttribute() { return currentUiLang; } },
    addEventListener(name, cb) { this[name] = cb; },
    createElement() { return {}; }, createTextNode(text) { return text; } },
  input: { value: '', focus() {}, addEventListener(name, cb) { this[name] = cb; } }, voiceBar: {}, voiceStage: { hidden: false },
  voiceState: {}, voicePreview: {}, voiceTranscriptEl: { appendChild() {} }, voiceTranscriptActions: {},
  setVoiceModeOpen() {}, setVoiceStageState() {}, stopSpeaking() {}, petSignal() {},
  say(text) { spokenLog.push(text); },
  tr(vi, en) { return currentUiLang === 'en' ? en : vi; },  // subby.js's language helper
  root: { classList: { toggle() {} }, querySelector(sel) { return sel === '[data-voice-lang]' ? langBtn : null; } }, voiceModeToggleBtn: null, panel: { hidden: false },
  openBtn: { setAttribute() {}, focus() {} }, teaser: null, log: { children: [1] },
  ask(text) { sent.push(text); } };
vm.runInNewContext(modeFunctions + section + escapeHandler, context);
assert.equal(starts, 0, 'opening page must not request microphone');
const result = text => active.onresult({ results: [[{ transcript: text }]] });
buttons.micBtn.click();
assert.equal(active.lang, 'en-US', 'English UI should select en-US recognition');
result('original recognized question');
assert.equal(sent.length, 0, 'speech must be reviewed before submission');
buttons.voiceStopBtn.click();
assert.equal(context.input.value, 'Original recognized question.');
context.input.value = 'edited approved question';
buttons.voiceSendNowBtn.click();
assert.deepEqual(sent, ['edited approved question'], 'send must use reviewed input');
buttons.voiceSendNowBtn.click();
assert.equal(sent.length, 1, 'double click must not resubmit stale recognition');
buttons.micBtn.click();
result('cancel this draft');
const lateResult = active.onresult;
const lateEnd = active.onend;
buttons.voiceCancelBtn.click();
lateResult({ results: [[{ transcript: 'late cancelled result' }]] });
lateEnd();
buttons.voiceSendNowBtn.click();
assert.equal(sent.length, 1, 'cancelled draft must not submit');
buttons.micBtn.click();
result('natural end question');
active.onend();
assert.equal(context.input.value, 'Natural end question.');
buttons.voiceClearDraftBtn.click();
assert.equal(context.input.value, '');
buttons.micBtn.click();
active.onerror({ error: 'not-allowed' });
assert.ok(spokenLog.at(-1).includes('not-allowed') && spokenLog.at(-1).includes('permission'), 'denied permission message');
buttons.micBtn.click();
active.onerror({ error: 'no-speech' });
assert.ok(spokenLog.at(-1).includes('no-speech') && spokenLog.at(-1).includes('No speech'), 'no-speech message');
buttons.micBtn.click();
active.onerror({ error: 'network' });
assert.ok(spokenLog.at(-1).includes('network') && spokenLog.at(-1).includes('Network'), 'network error message');
currentUiLang = 'vi';
buttons.micBtn.click();
assert.equal(active.lang, 'vi-VN', 'Vietnamese UI should select vi-VN recognition');
active.onerror({ error: 'no-speech' });
assert.ok(spokenLog.at(-1).includes('Chưa nghe thấy giọng nói'), 'Vietnamese no-speech message');
buttons.micBtn.click();
active.onerror({ error: 'network' });
assert.ok(spokenLog.at(-1).includes('Lỗi kết nối mạng'), 'Vietnamese network message');
context.input.value = 'keyboard after permission refusal';
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'keyboard after permission refusal');
buttons.micBtn.click();
result('interim question');
active.stop = () => {}; // browser final recognition arrives after Stop
buttons.voiceStopBtn.click();
result('final question after stop');
active.onend();
assert.equal(context.input.value, 'Final question after stop.');
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'Final question after stop.');
buttons.micBtn.click();
result('interim draft');
context.input.value = 'edited during recognition';
context.input.input();
result('late final must not replace edit');
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'edited during recognition');
buttons.micBtn.click();
result('must clear on Escape');
context.document.keydown({ key: 'Escape', preventDefault() {} });
assert.equal(context.panel.hidden, true);
assert.equal(context.input.value, '');
// Vietnamese: keeps listening through pauses, merges Android repeats, stops after 3 s of quiet, tidies.
const sentBeforePause = sent.length;
buttons.micBtn.click();
assert.equal(active.lang, 'vi-VN');
assert.equal(active.continuous, true, 'must keep listening through pauses');
active.onresult({ results: ['thêm nét phích', 'thêm nét phích 260 nghìn'].map(t => Object.assign([{ transcript: t }], { isFinal: true })) });
assert.equal(context.input.value, 'thêm nét phích 260 nghìn', 'Android repeats must be merged');
timers.filter(t => t.ms === 3000 && !t.cleared).at(-1).fn();
assert.equal(context.input.value, 'Thêm Netflix 260.000.', 'stops after the pause and tidies');
assert.equal(sent.length, sentBeforePause, 'a pause must not send by itself');
// The language switch overrides the page language.
langBtn.click();
assert.equal(langBtn.textContent, '🎙 Nói: English');
buttons.micBtn.click();
assert.equal(active.lang, 'en-US', 'mic language switch must win over the page language');
buttons.voiceCancelBtn.click();
context.window.SpeechRecognition = undefined;
buttons.micBtn.click();
context.input.value = 'keyboard on unsupported browser';
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'keyboard on unsupported browser');
console.log('voice lifecycle: edit/send/stop/cancel/end/error/duplicate passed');
