import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { setTimeout as sleep } from 'node:timers/promises';

const tick = () => sleep(15); // let async handlers + fetch settle

function makeDom() {
  const dom = new JSDOM(
    '<!doctype html><html><body><header class="topbar"><a class="brand" href="#/"></a><div class="hud" id="hud"></div></header><main id="app" class="app"></main></body></html>',
    { url: 'http://localhost/#/' });
  dom.window.scrollTo = () => {};
  dom.window.HTMLElement.prototype.scrollIntoView = () => {};
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.location = dom.window.location;
  globalThis.HTMLElement = dom.window.HTMLElement;
  return dom;
}

const LESSON = {
  id: 'w0u0l1', title: 'Gravity',
  theory: 'Bodies accelerate downward.\n```\nfloat g = 9.8f;\n```',
  worked_example: { title: 'A fall', code: 'int x = 0;', explanation: 'Start at zero.' },
  practice: [
    { q: 'Which way does gravity pull?', choices: ['Up', 'Down', 'Sideways'] },
  ],
  checkpoint: {
    id: 'w0u0l1c', title: 'Integrate the fall', instructions: 'Write integrate().',
    starter_code: '// TODO\n', kind: 'function', static_hints: [],
  },
  passed: false, attempts: 0,
};

const CURRICULUM = {
  worlds: [{
    id: 0, title: 'World 0 — Foundations', subtitle: 'Start here.',
    units: [{
      id: 'w0u0', title: 'Unit 0', state: 'available', kind: 'unit',
      lessons: [
        { id: 'w0u0l1', title: 'Gravity', status: 'available', kind: 'function', due: false },
        { id: 'w0u0l2', title: 'Refactor', status: 'locked', kind: 'function', due: false },
      ],
    }],
  }],
};

/* Mock fetch: routes map "METHOD /api/path" → payload. Dynamic handlers get the
   parsed request body. Every request is recorded in the returned log. */
function routes(overrides = {}) {
  const log = [];
  const base = {
    'GET /api/state': { xp: 42, streak: 1, due_reviews: 1 },
    'GET /api/curriculum': CURRICULUM,
    'GET /api/lesson/w0u0l1': LESSON,
    'GET /api/review-queue': { due: [] },
    'POST /api/hint': { source: 'static', hint: 'think of falling' },
    'POST /api/checkpoint/run': { passed: true, xp: 3, attempts: 1, newly_unlocked: [], warnings: 'reserved', errors: '' },
  };
  const handlers = { ...base, ...overrides };
  handlers['POST /api/answer'] = (b) => b.choice === 1
    ? { correct: true, xp: 5, explanation: 'because gravity', h_days: 1, answer_index: 1 }
    : { correct: false, xp: 0, explanation: 'gravity says no', h_days: 1, answer_index: 1,
        followup: { token: 'fu1', q: 'Pick the lighter of two?', choices: ['Heavy', 'Light'] } };
  handlers['POST /api/followup/answer'] = () => ({ correct: true, explanation: 'followup explained', answer_index: 0 });

  globalThis.fetch = async (url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase();
    const body = opts.body ? JSON.parse(opts.body) : null;
    const key = `${method} ${url}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`unmocked: ${key}`);
    log.push({ url: key, body });
    const payload = typeof handler === 'function' ? handler(body) : handler;
    return { ok: true, json: async () => payload };
  };
  return log;
}

test('path renders worlds, units and HUD', async () => {
  makeDom();
  routes();
  await import('../app.js?path_a');
  document.dispatchEvent(new window.Event('DOMContentLoaded')); // app boots here
  await tick();
  assert.ok(document.querySelector('.unit-title'));
  assert.match(document.querySelector('.unit-title').textContent, /Unit 0/);
  assert.match(document.getElementById('hud').textContent, /42 XP/);
});

test('lesson page: warm-up, shuffled practice, correct-highlight, follow-up, hint fix', async () => {
  makeDom();
  const log = routes({
    'GET /api/review-queue': { due: [{
      lesson_id: 'w0u0l1', title: 'Gravity', p_recall: 0.5,
      practice: [{ q: 'Warm Q', choices: ['W1', 'W2'] }], generated: null, checkpoint: null,
    }] },
  });
  const lessonView = await import('../views/lesson.js?lv_a');
  await lessonView.renderLesson(document.getElementById('app'), 'w0u0l1');

  assert.ok(document.querySelector('.warmup-panel'), 'warm-up panel present');
  const practice = document.querySelector('.practice-panel');
  const btns = practice.querySelectorAll('.choice');
  assert.equal(btns.length, 3);

  const wrongBtn = [...btns].find(b => b.textContent === 'Up');
  wrongBtn.click();
  await tick();
  const card = practice.querySelector('.q-card');
  assert.ok(card.classList.contains('q-wrong'));
  assert.ok(card.querySelector('.choice-correct'), 'correct choice highlighted');
  assert.ok(card.querySelector('.choice-wrong'), 'wrong pick highlighted');
  assert.ok(card.querySelector('.q-expl'));
  assert.ok(practice.querySelector('.followup-box'), 'adaptive follow-up rendered');
  assert.ok(card.querySelector('.choice').disabled, 'choices locked after answer');

  const hintBtn = practice.querySelector('.ghost-btn');
  assert.match(hintBtn.textContent, /hint/i);
  hintBtn.click();
  await tick();
  const hintReq = log.find(l => l.url === 'POST /api/hint');
  assert.ok(hintReq, 'hint request made');
  assert.equal(hintReq.body.wrong_answer, 'Up', 'sends the clicked text, not choices[0]');

  const fuCard = practice.querySelector('.followup-box .q-card');
  const light = [...fuCard.querySelectorAll('.choice')].find(b => b.textContent === 'Light');
  light.click();
  await tick();
  assert.ok(fuCard.classList.contains('q-correct'));
  assert.ok(fuCard.querySelector('.choice-correct'));
});

test('lesson page: runtime_stderr (sanitizer crash) is rendered on failed run', async () => {
  makeDom();
  const log = routes({
    'POST /api/checkpoint/run': {
      passed: false, xp: 0, attempts: 1, newly_unlocked: [],
      errors: '', warnings: '',
      runtime_stderr: 'AddressSanitizer: heap-buffer-overflow',
    },
  });
  const lessonView = await import('../views/lesson.js?lv_c');
  await lessonView.renderLesson(document.getElementById('app'), 'w0u0l1');

  const runBtn = document.querySelector('.run-btn');
  runBtn.click();
  await tick();

  const run = log.find(l => l.url === 'POST /api/checkpoint/run');
  assert.ok(run, 'checkpoint run issued');
  const resultBox = document.querySelector('.result-box:not(.hidden)');
  assert.ok(resultBox, 'result box shown');
  assert.match(resultBox.textContent, /runtime:/);
  assert.match(resultBox.textContent, /heap-buffer-overflow/);
});

test('lesson page without due reviews shows no warm-up panel', async () => {
  makeDom();
  routes();
  const lessonView = await import('../views/lesson.js?lv_b');
  await lessonView.renderLesson(document.getElementById('app'), 'w0u0l1');
  assert.ok(!document.querySelector('.warmup-panel'));
});

test('review page: generated question via followup token + checkpoint re-run', async () => {
  makeDom();
  const log = routes({
    'GET /api/review-queue': { due: [{
      lesson_id: 'w0u0l1', title: 'Gravity', p_recall: 0.4,
      practice: [{ q: 'Static Q', choices: ['S1', 'S2'] }],
      generated: { token: 'gtok', q: 'Generated Q', choices: ['A', 'B', 'C'] },
      checkpoint: { title: 'Integrate the fall', kind: 'function', starter_code: '// TODO' },
    }] },
  });
  const reviewView = await import('../views/review.js?rv_a');
  await reviewView.renderReview(document.getElementById('app'));

  const cards = document.querySelectorAll('.panel');
  assert.equal(cards.length, 1);
  assert.match(cards[0].textContent, /Generated Q/);

  const genCard = cards[0].querySelector('.q-card');
  const a = [...genCard.querySelectorAll('.choice')].find(b => b.textContent === 'A');
  a.click();
  await tick();
  assert.ok(genCard.querySelector('.choice-correct'));
  assert.ok(log.find(l => l.url === 'POST /api/followup/answer' && l.body.token === 'gtok'));

  const retry = [...cards[0].querySelectorAll('button')].find(b => /Re-attempt from memory/.test(b.textContent));
  retry.click();
  await tick();
  const editor = document.querySelector('.review-retry .editor');
  assert.ok(editor, 'inline editor expanded');
  assert.equal(editor.value, '// TODO', 'prefilled with the blank starter');
  editor.value = editor.value + '\nvy -= 9.8f * dt;';
  document.querySelector('.review-retry .run-btn').click();
  await tick();
  const run = log.find(l => l.url === 'POST /api/checkpoint/run');
  assert.ok(run, 'checkpoint run issued');
  assert.equal(run.body.code, '// TODO\nvy -= 9.8f * dt;', 'posts the edited code, not the starter stub');
  assert.ok(document.querySelector('.review-retry .result-head.ok'), 'passing result rendered');
  assert.ok(!document.querySelector('.review-retry .run-btn').disabled, 'run button re-enabled');
});

test('review page: show old solution loads it and marks the run revealed', async () => {
  makeDom();
  const log = routes({
    'GET /api/review-queue': { due: [{
      lesson_id: 'w0u0l1', title: 'Gravity', p_recall: 0.4,
      practice: [], generated: null,
      checkpoint: { title: 'Integrate the fall', kind: 'function', starter_code: '// TODO', has_solution: true },
    }] },
    'GET /api/lesson/w0u0l1/solution': { code: 'SOLUTION' },
  });
  const reviewView = await import('../views/review.js?rv_b');
  await reviewView.renderReview(document.getElementById('app'));

  const retry = [...document.querySelectorAll('button')].find(b => /Re-attempt from memory/.test(b.textContent));
  retry.click();
  await tick();
  const editor = document.querySelector('.review-retry .editor');
  assert.equal(editor.value, '// TODO');

  const reveal = [...document.querySelectorAll('button')].find(b => /Show old solution/.test(b.textContent));
  reveal.click();
  await tick();
  assert.ok(log.find(l => l.url === 'GET /api/lesson/w0u0l1/solution'), 'solution fetched');
  assert.equal(editor.value, 'SOLUTION', 'old solution loaded into the editor');
  assert.ok(!document.querySelector('.editor-note').classList.contains('hidden'), 'won\'t-count note visible');

  document.querySelector('.review-retry .run-btn').click();
  await tick();
  const run = log.find(l => l.url === 'POST /api/checkpoint/run');
  assert.equal(run.body.code, 'SOLUTION');
  assert.equal(run.body.revealed, true, 'run marked revealed so it never scores');
});