import { h, icon, esc, toast, xpFly, fmtXp } from './dom.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

export function checkpointEditor({ lessonId, starterCode, hasSolution = false }) {
  let revealed = false;

  const edWrap = h('div', { class: 'editor-wrap' });
  const gutter = h('div', { class: 'gutter' });
  const ta = h('textarea', {
    class: 'editor', spellcheck: 'false', wrap: 'off', autocapitalize: 'off', autocorrect: 'off',
  });
  ta.value = starterCode;
  edWrap.append(gutter, ta);

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

  const resultBox = h('div', { class: 'result-box hidden' });
  const clickedNote = h('div', { class: 'editor-note hidden' }, [
    icon('book'), ' Old solution loaded — running it won\'t count toward progress.',
  ]);

  const runBtn = h('button', { class: 'primary-btn run-btn' }, [icon('play'), ' Run checkpoint']);
  const hintBtn = h('button', { class: 'ghost-btn' }, [icon('spark'), ' Hint']);
  const revealBtn = h('button', { class: 'ghost-btn small' }, [icon('book'), ' Show old solution']);

  async function revealSolution() {
    try {
      const { code } = await api.solution(lessonId);
      ta.value = code;
      revealed = true;
      syncGutter();
      clickedNote.classList.remove('hidden');
      toast('Old solution loaded; runs won\'t score.', 'info');
    } catch (e) {
      toast(e.message, 'error');
    }
  }
  if (hasSolution) revealBtn.addEventListener('click', revealSolution);

  function showResult(res) {
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = '';
    resultBox.dataset.lastErrors = res.errors || '';
    const head = h('div', { class: `result-head ${res.passed ? 'ok' : 'bad'}` }, [
      res.passed
        ? [icon('check'), h('b', {}, ' Checkpoint passed'), res.xp ? h('span', { class: 'xp-tag' }, [`+${fmtXp(res.xp)} XP`]) : null]
        : [icon('skull'), h('b', {}, res.timed_out ? ' Timed out' : res.compiled ? ' Tests failed' : ' Compile error')],
    ]);
    resultBox.append(head);
    if (res.errors) resultBox.append(h('pre', { class: 'console console-err' }, [esc(res.errors)]));
    if (res.warnings) resultBox.append(h('pre', { class: 'console console-warn' }, [esc('warnings:\n' + res.warnings)]));
    if (res.stdout && !res.passed) resultBox.append(h('pre', { class: 'console' }, [esc(res.stdout.slice(0, 4000))]));
    if (res.runtime_stderr) resultBox.append(h('pre', { class: 'console console-warn' }, [esc('runtime:\n' + res.runtime_stderr.slice(0, 4000))]));
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

  runBtn.addEventListener('click', async () => {
    runBtn.disabled = true; runBtn.textContent = 'Compiling…';
    try {
      const res = await api.runCheckpoint(lessonId, ta.value, revealed);
      showResult(res);
    } catch (e) { toast(e.message, 'error'); }
    runBtn.disabled = false;
    runBtn.innerHTML = ''; runBtn.append(icon('play'), ' Run checkpoint');
  });

  hintBtn.addEventListener('click', async () => {
    hintBtn.disabled = true; hintBtn.textContent = 'Thinking…';
    try {
      const qh = await api.hint({
        lesson_id: lessonId,
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
    hintBtn.disabled = false; hintBtn.textContent = ''; hintBtn.append(icon('spark'), ' Hint');
  });

  const btnRow = h('div', { class: 'btn-row' }, [
    runBtn, hintBtn,
    hasSolution ? revealBtn : null,
  ]);
  return {
    el: h('div', {}, [edWrap, clickedNote, btnRow, resultBox]),
    get revealed() { return revealed; },
  };
}