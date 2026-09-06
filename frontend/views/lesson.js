import { h, icon, esc, md, highlightC, toast, quizCard, xpFly } from './dom.js';
import { checkpointEditor } from './editor.js';
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

  cpPanel.append(checkpointEditor({ lessonId: lesson.id, starterCode: cp.starter_code, hasSolution: lesson.has_solution }).el);
  page.append(cpPanel);

  root.append(page);
  window.scrollTo(0, 0);
}
