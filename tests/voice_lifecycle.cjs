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
const sent = [];
const context = { ...buttons, window: { SpeechRecognition: Speech },
  document: { documentElement: { lang: 'en', getAttribute() { return 'en'; } },
    addEventListener(name, cb) { this[name] = cb; } },
  input: { value: '', focus() {}, addEventListener(name, cb) { this[name] = cb; } }, voiceBar: {}, voiceStage: { hidden: false },
  voiceState: {}, voicePreview: {}, voiceTranscriptEl: {}, voiceTranscriptActions: {},
  setVoiceModeOpen() {}, setVoiceStageState() {}, stopSpeaking() {}, say() {},
  root: { classList: { toggle() {} } }, voiceModeToggleBtn: null, panel: { hidden: false },
  openBtn: { setAttribute() {}, focus() {} }, teaser: null, log: { children: [1] },
  ask(text) { sent.push(text); } };
vm.runInNewContext(modeFunctions + section + escapeHandler, context);
assert.equal(starts, 0, 'opening page must not request microphone');
const result = text => active.onresult({ results: [[{ transcript: text }]] });
buttons.micBtn.click();
result('original recognized question');
assert.equal(sent.length, 0, 'speech must be reviewed before submission');
buttons.voiceStopBtn.click();
assert.equal(context.input.value, 'original recognized question');
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
assert.equal(context.input.value, 'natural end question');
buttons.voiceClearDraftBtn.click();
assert.equal(context.input.value, '');
buttons.micBtn.click();
active.onerror({ error: 'not-allowed' });
context.input.value = 'keyboard after permission refusal';
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'keyboard after permission refusal');
buttons.micBtn.click();
result('interim question');
active.stop = () => {}; // browser final recognition arrives after Stop
buttons.voiceStopBtn.click();
result('final question after stop');
active.onend();
assert.equal(context.input.value, 'final question after stop');
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'final question after stop');
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
context.window.SpeechRecognition = undefined;
buttons.micBtn.click();
context.input.value = 'keyboard on unsupported browser';
buttons.voiceSendNowBtn.click();
assert.equal(sent.at(-1), 'keyboard on unsupported browser');
console.log('voice lifecycle: edit/send/stop/cancel/end/error/duplicate passed');
