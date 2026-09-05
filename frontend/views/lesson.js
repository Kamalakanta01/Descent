import { h, icon, esc, md, highlightC, toast } from './dom.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

const XP_FLY = (xp) => {
  const el = h('div', { class: 'xp-fly' }, [`+${xp} XP`]);
  document.body.append(el);
  setTimeout(() => el.remove(), 1400);
};

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
  let firstWrong = null;
  lesson.practice.forEach((q, qi) => {
    const cardEl = h('div', { class: 'q-card' });
    cardEl.append(h('p', { class: 'q-text' }, [esc(q.q)]));
    const choices = h('div', { class: 'choices' });
    q.choices.forEach((c, ci) => {
      const btn = h('button', { class: 'choice' }, [esc(c)]);
      btn.addEventListener('click', async () => {
        if (cardEl.dataset.locked === '1') return;
        cardEl.dataset.locked = '1';
        try {
          const res = await api.answer(lesson.id, qi, ci);
          feedback(cardEl, choices, res, qi);
        } catch (e) { toast(e.message, 'error'); cardEl.dataset.locked = ''; }
      });
      choices.append(btn);
    });
    cardEl.append(choices);
    practicePanel.append(cardEl);
  });
  page.append(practicePanel);

  function feedback(cardEl, choicesEl, res, qi) {
    const btns = choicesEl.querySelectorAll('.choice');
    btns.forEach((b, i) => {
      const correctIdx = res.correct ? undefined : undefined;
      b.disabled = true;
    });
    if (res.correct) {
      cardEl.classList.add('q-correct');
      if (res.xp) XP_FLY(res.xp);
    } else {
      cardEl.classList.add('q-wrong');
      firstWrong = qi;
    }
    const ex = h('div', { class: 'q-expl' }, [esc(res.explanation || '')]);
    cardEl.append(ex);
    if (!res.correct) {
      const hintBtn = h('button', { class: 'ghost-btn small' }, [icon('spark'), ' Ask for a hint']);
      hintBtn.addEventListener('click', async () => {
        hintBtn.disabled = true; hintBtn.textContent = 'Thinking…';
        try {
          const qh = await api.hint({ lesson_id: lesson.id, q_index: qi, wrong_answer: lesson.practice[qi].choices[0] });
          cardEl.append(h('div', { class: 'hint-box' }, [
            h('div', { class: 'hint-src' }, [qh.source === 'static' ? 'authored hint' : `tutor · ${qh.source.replace('llm:', '')}`]),
            h('div', {}, [esc(qh.hint)]),
          ]));
        } catch (e) { toast(e.message, 'error'); }
        hintBtn.remove();
      });
      cardEl.append(hintBtn);
    }
    refreshHud();
  }

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
      if (res.xp) XP_FLY(res.xp);
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
