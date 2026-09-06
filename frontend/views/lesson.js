import { h, icon, esc, md, highlightC, toast, quizCard, xpFly } from './dom.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

export async function renderLesson(root, lessonId) {
  root.innerHTML = '';
  const lesson = await api.lesson(lessonId);
  const page = h('div', { class: 'lesson-page' });

  /* ---------- header ---------- */
  page.append(
    h('div', { class: 'lesson-head' }, [
      h('a', { class: 'back-link', href: '#/' }, ['‹ path']),
      h('h1', {}, [esc(lesson.title)]),
      h('div', { class: 'lesson-meta' }, [
        h('span', { class: 'meta-pill' }, [icon('book'), ' Theory']),
        h('span', { class: 'meta-pill' }, [icon('spark'), ' Practice']),
        h('span', { class: 'meta-pill meta-pill-code' }, [icon('code'), ' Checkpoint']),
      ]),
    ])
  );

  /* ---------- warm-up (inline due review) ---------- */
  const review = await api.reviewQueue().catch(() => null);
  if (review && review.due.length) {
    const first = review.due[0];
    const warm = h('section', { class: 'panel warmup-panel' }, [
      h('div', { class: 'warmup-head' }, [
        h('div', { class: 'warmup-title' }, [
          icon('crown'),
          h('b', {}, [' Warm-up']),
          h('span', { class: 'dim small' }, [` ${first.title} · ${Math.round(first.p_recall * 100)}% recall`]),
        ]),
        h('a', { class: 'ghost-btn small', href: '#/review' }, [`${review.due.length} due →`]),
      ]),
    ]);
    const generated = first.generated;
    const q = generated ? { q: generated.q, choices: generated.choices } : first.practice[0];
    const { card } = quizCard(q, generated ? `w:${generated.token}` : `warmup:${first.lesson_id}:p0`, async (origIdx) => {
      const res = generated
        ? await api.followupAnswer(generated.token, origIdx)
        : await api.answer(first.lesson_id, 0, origIdx);
      if (res.correct && res.xp) xpFly(res.xp);
      refreshHud();
      return res;
    });
    warm.append(card);
    page.append(warm);
  }

  /* ---------- theory ---------- */
  const theory = h('section', { class: 'panel theory-panel' }, [
    h('h2', {}, [icon('book'), ' Theory']),
    h('div', { class: 'theory-body', html: md(lesson.theory) }),
  ]);
  page.append(theory);

  /* ---------- worked example ---------- */
  const we = lesson.worked_example;
  const weBlock = h('section', { class: 'panel we-panel' }, [
    h('h2', {}, [icon('spark'), ' Worked example']),
    h('h3', { class: 'we-title' }, [esc(we.title)]),
    h('pre', { class: 'code-block' }, [h('code', { html: highlightC(we.code) })]),
    h('p', { class: 'we-expl' }, [esc(we.explanation)]),
  ]);
  page.append(weBlock);

  /* ---------- practice ---------- */
  const practicePanel = h('section', { class: 'panel practice-panel' }, [
    h('h2', {}, [icon('spark'), ' Guided practice']),
  ]);
  lesson.practice.forEach((q, qi) => {
    const { card } = quizCard(q, `${lesson.id}:p${qi}`, async (origIdx) => {
      const res = await api.answer(lesson.id, qi, origIdx);
      if (!res.correct) {
        const hintBtn = h('button', { class: 'ghost-btn small' }, [icon('spark'), ' Ask for a hint']);
        hintBtn.addEventListener('click', async () => {
          hintBtn.disabled = true; hintBtn.textContent = 'Thinking…';
          try {
            const qh = await api.hint({
              lesson_id: lesson.id, q_index: qi,
              wrong_answer: q.choices[origIdx],  // what they actually clicked
            });
            card.append(h('div', { class: 'hint-box' }, [
              h('div', { class: 'hint-src' }, [qh.source === 'static' ? 'authored hint' : `tutor · ${qh.source.replace('llm:', '')}`]),
              h('div', {}, [esc(qh.hint)]),
            ]));
          } catch (e) { toast(e.message, 'error'); }
          hintBtn.remove();
        });
        card.append(hintBtn);
        if (res.followup) renderFollowup(card, res.followup);
      } else if (res.xp) {
        xpFly(res.xp);
      }
      refreshHud();
      return res;
    });
    practicePanel.append(card);
  });

  function renderFollowup(card, fu) {
    const box = h('div', { class: 'followup-box' }, [
      h('div', { class: 'followup-head' }, [icon('spark'), ' One more, at the right level']),
    ]);
    const { card: fc } = quizCard({ q: fu.q, choices: fu.choices }, `f:${fu.token}`, async (origIdx) => {
      const res = await api.followupAnswer(fu.token, origIdx);
      refreshHud();
      return res;
    });
    box.append(fc);
    card.append(box);
  }
  page.append(practicePanel);

  /* ---------- checkpoint ---------- */
  const cp = lesson.checkpoint;
  const cpPanel = h('section', { class: 'panel cp-panel' });
  cpPanel.append(h('h2', {}, [icon('code'), ` Checkpoint — ${esc(cp.title)}`]));
  cpPanel.append(h('div', { class: 'cp-instructions', html: md(cp.instructions) }));
  if (lesson.passed) cpPanel.append(h('div', { class: 'passed-banner' }, [icon('crown'), ` Already passed${lesson.attempts === 1 ? ' on your first try' : ''}!`]));

  const edWrap = h('div', { class: 'editor-wrap' });
  const gutter = h('div', { class: 'gutter' });
  const ta = h('textarea', {
    class: 'editor', spellcheck: 'false', wrap: 'off', autocapitalize: 'off', autocorrect: 'off',
  });
  ta.value = cp.starter_code;
  edWrap.append(gutter, ta);
  cpPanel.append(edWrap);

  const syncGutter = () => {
    const n = ta.value.split('\n').length;
    gutter.innerHTML = Array.from({ length: n }, (_, i) => `<div>${i + 1}</div>`).join('');
    gutter.scrollTop = ta.scrollTop;
  };
  syncGutter();
  ta.addEventListener('input', syncGutter);
  ta.addEventListener('scroll', () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const s = ta.selectionStart, t = ta.selectionEnd;
      ta.value = ta.value.slice(0, s) + '    ' + ta.value.slice(t);
      ta.selectionStart = ta.selectionEnd = s + 4;
      syncGutter();
    }
  });

  const statusRow = h('div', { class: 'cp-status' });
  const runBtn = h('button', { class: 'primary-btn run-btn' }, [icon('play'), ' Run checkpoint']);
  const hintBtn2 = h('button', { class: 'ghost-btn' }, [icon('spark'), ' Hint']);
  const resultBox = h('div', { class: 'result-box hidden' });

  runBtn.addEventListener('click', async () => {
    runBtn.disabled = true; runBtn.textContent = 'Compiling…';
    try {
      const res = await api.runCheckpoint(lesson.id, ta.value);
      showResult(res);
    } catch (e) { toast(e.message, 'error'); }
    runBtn.disabled = false;
    runBtn.innerHTML = ''; runBtn.append(icon('play'), ' Run checkpoint');
  });

  hintBtn2.addEventListener('click', async () => {
    hintBtn2.disabled = true; hintBtn2.textContent = 'Thinking…';
    try {
      const qh = await api.hint({
        lesson_id: lesson.id,
        wrong_answer: ta.value.slice(-600),
        compile_errors: resultBox.dataset.lastErrors || '',
      });
      resultBox.classList.remove('hidden');
      resultBox.append(h('div', { class: 'hint-box' }, [
        h('div', { class: 'hint-src' }, [qh.source === 'static' ? 'authored hint' : `tutor · ${qh.source.replace('llm:', '')}`]),
        h('div', {}, [esc(qh.hint)]),
      ]));
      resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (e) { toast(e.message, 'error'); }
    hintBtn2.disabled = false; hintBtn2.textContent = ''; hintBtn2.append(icon('spark'), ' Hint');
  });

  function showResult(res) {
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = '';
    resultBox.dataset.lastErrors = res.errors || '';
    const head = h('div', { class: `result-head ${res.passed ? 'ok' : 'bad'}` }, [
      res.passed
        ? [icon('check'), h('b', {}, ' Checkpoint passed'), res.xp ? h('span', { class: 'xp-tag' }, [`+${res.xp} XP`]) : null]
        : [icon('skull'), h('b', {}, res.timed_out ? ' Timed out' : res.compiled ? ' Tests failed' : ' Compile error')],
    ]);
    resultBox.append(head);
    if (res.errors) resultBox.append(h('pre', { class: 'console console-err' }, [esc(res.errors)]));
    if (res.warnings) resultBox.append(h('pre', { class: 'console console-warn' }, [esc('warnings:\n' + res.warnings)]));
    if (res.stdout && !res.passed) resultBox.append(h('pre', { class: 'console' }, [esc(res.stdout.slice(0, 4000))]));
    if (res.checks && res.checks.length) {
      const list = h('div', { class: 'checks' });
      for (const c of res.checks) {
        list.append(h('div', { class: `check-row ${c.ok ? 'check-ok' : 'check-bad'}` }, [
          h('span', { class: 'check-dot' }),
          h('b', {}, [esc(c.name)]),
          h('span', { class: 'check-detail' }, [esc(c.detail || '')]),
        ]));
      }
      resultBox.append(list);
    }
    if (res.passed) {
      if (res.xp) xpFly(res.xp);
      if (res.newly_unlocked && res.newly_unlocked.length) {
        toast(`Unlocked: ${res.newly_unlocked.join(', ')}`, 'success');
      }
      const done = h('div', { class: 'done-row' }, [
        h('a', { class: 'primary-btn', href: '#/' }, ['Continue →']),
      ]);
      resultBox.append(done);
      refreshHud();
    }
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  const btnRow = h('div', { class: 'btn-row' }, [runBtn, hintBtn2]);
  cpPanel.append(btnRow, statusRow, resultBox);
  page.append(cpPanel);

  root.append(page);
  window.scrollTo(0, 0);
}
