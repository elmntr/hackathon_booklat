const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const script = html.split('<script>')[1].split('</script>')[0];

function harness() {
  const nodes = new Map();
  const element = () => ({textContent: '', hidden: false, disabled: false, children: [],
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    focus() { context.focused = this; }});
  const $ = id => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  const word = element();
  const context = vm.createContext({$, console, clearTimeout, setTimeout,
    document: {createElement: element, querySelector: selector => {
      assert.equal(selector, '#results-passage .w[data-idx="0"]'); return word;
    }},
    session: {id: 'test', learner: 'Test fixture', passage: {id: 'test', tokens: ['word']},
      marks: [{status: 'correct', repeats: 0}], locked: new Set(), first_t: 0, last_t: 10},
    passages: [], revision: 0, scoreRequest: 0, scoreTimeout: null,
    selected: 0, screen: 'results', paint() {}, toast() {}, api: async () => []});
  for (const [start, end] of [
    ['function badge(', 'function startState('],
    ['async function recent(', 'function drawPassage('],
    ['function closeEditor(', 'function merge('],
    ['function resetScore(', 'async function newReading('],
  ]) vm.runInContext(script.slice(script.indexOf(start), script.indexOf(end)), context);
  return {context, $, word};
}

const score = {reading_time_s: 10, wpm: 60, accuracy_pct: 100, level: 'independent',
  words_attempted: 10, words_total: 10, substitutions: 0, omissions: 0, repetitions: 0, partial: false};

test('inline script parses and interface has no em dashes', () => {
  new vm.Script(script);
  assert.ok(!html.includes('\u2014'));
});

test('recent readings clears old data, shows loading, and recovers from an error', async () => {
  const {context: c, $} = harness();
  let reject;
  c.api = () => new Promise((resolve, fail) => { reject = fail; });
  const pending = c.recent();
  assert.equal($('recent-table').hidden, true);
  assert.equal($('recent-empty').textContent, 'Loading readings…');
  reject(Error('Unavailable'));
  await pending;
  assert.equal($('recent-empty').textContent, 'Unavailable');
  c.api = async () => [];
  await c.recent();
  assert.equal($('recent-empty').textContent, 'No readings saved yet.');
  assert.equal($('recent-empty').hidden, false);
  c.api = async () => [{learner: 'Test fixture', passage_id: 'test', level: 'independent'}];
  await c.recent();
  assert.equal($('recent-table').hidden, false);
  assert.equal($('recent-empty').hidden, true);
  assert.equal($('recent-body').children.length, 1);
});

test('startup still loads recent readings when passage loading fails', async () => {
  const {context: c, $} = harness();
  let calls = 0;
  c.pollHealth = () => {};
  c.api = async () => { throw Error('Passages unavailable'); };
  c.recent = async () => { calls++; };
  await vm.runInContext(script.slice(script.lastIndexOf('(async()=>{pollHealth();')), c);
  assert.equal(calls, 1);
  assert.equal($('setup-error').hidden, false);
});

test('new score clears prior learner values on pending and failed requests, then retries', async () => {
  const {context: c, $} = harness();
  for (const id of ['result-time', 'result-wpm', 'result-accuracy', 'result-level', 'breakdown']) {
    $(id).textContent = 'Previous learner';
  }
  let reject;
  c.api = () => new Promise((resolve, fail) => { reject = fail; });
  const pending = c.updateScore(false);
  assert.equal($('score-status').textContent, 'Calculating score…');
  for (const id of ['result-time', 'result-wpm', 'result-accuracy', 'result-level']) {
    assert.equal($(id).textContent, 'n/a');
  }
  assert.equal($('breakdown').textContent, '');
  assert.equal($('partial').hidden, true);
  assert.equal($('no-speech').hidden, true);
  reject(Error('Unavailable'));
  await assert.rejects(pending, /Unavailable/);
  assert.equal($('score-status').textContent, 'Score unavailable.');
  assert.equal($('score-error').hidden, false);
  assert.equal($('result-accuracy').textContent, 'n/a');
  c.api = async () => score;
  await c.updateScore(false);
  assert.equal($('result-accuracy').textContent, '100.0%');
  assert.equal($('score-error').hidden, true);
  assert.equal($('score-status').textContent, '');
});

test('late failures cannot overwrite a newer score or another session', async () => {
  const {context: c, $} = harness();
  let reject;
  c.api = () => new Promise((resolve, fail) => { reject = fail; });
  const old = c.updateScore(false);
  c.api = async () => score;
  await c.updateScore(false);
  reject(Error('Old failure'));
  await old;
  assert.equal($('score-error').hidden, true);
  assert.equal($('result-accuracy').textContent, '100.0%');
  c.api = () => new Promise((resolve, fail) => { reject = fail; });
  const departed = c.updateScore(false);
  c.session = null;
  $('score-status').textContent = 'New session';
  reject(Error('Departed session'));
  await departed;
  assert.equal($('score-status').textContent, 'New session');
});

test('editing hides stale scores during debounce and ignores failures from old marks', async () => {
  const {context: c, $} = harness();
  let reject;
  c.api = () => new Promise((resolve, fail) => { reject = fail; });
  const pending = c.updateScore(false);
  $('result-accuracy').textContent = '100.0%';
  c.edit('omission');
  clearTimeout(c.scoreTimeout);
  assert.equal($('result-accuracy').textContent, 'n/a');
  assert.equal($('score-status').textContent, 'Calculating score…');
  reject(Error('Previous marks'));
  await pending;
  assert.equal($('score-error').hidden, true);
});

test('save failure permits retry and successful save keeps the Saved label', async () => {
  const {context: c, $} = harness();
  c.api = async () => { throw Error('Disk full'); };
  await assert.rejects(c.updateScore(true), /Disk full/);
  assert.equal($('save').disabled, false);
  c.api = async () => score;
  await c.updateScore(true);
  assert.equal($('save').textContent, 'Saved ✓');
  assert.equal(c.session.saved, true);
  assert.equal($('save').disabled, false);
});

test('Escape restores focus to the selected word; other dismissals do not steal focus', () => {
  const {context: c, $, word} = harness();
  let keydown;
  c.document.addEventListener = (event, handler) => { keydown = handler; };
  vm.runInContext(script.split('\n').find(line => line.startsWith("document.addEventListener('keydown'")), c);
  keydown({key: 'Escape', target: {classList: {contains: () => false}}});
  assert.equal(c.focused, word);
  assert.equal($('editor').hidden, true);
  assert.equal(c.selected, null);
  c.focused = null; c.selected = 0;
  c.closeEditor();
  assert.equal(c.focused, null);
  c.closeEditor(true);
  assert.equal(c.focused, null);
});
