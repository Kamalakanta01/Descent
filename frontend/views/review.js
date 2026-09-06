import { h, icon, esc, quizCard, xpFly } from './dom.js';
import { checkpointEditor } from './editor.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

export async function renderReview(root) {
  root.innerHTML = '';
  const { due } = await api.reviewQueue();
  const page = h('div');
  page.append(h('div', { class: 'lesson-head' }, [
    h('a', { class: 'back-link', href: '#/' }, ['‹ path']),
    h('h1', {}, ['Spaced review']),
    h('p', { class: 'dim' }, ['Recall probability below 85% — memory strengthens each time you retrieve it.']),
  ]));
  if (!due.length) {
    page.append(h('div', { class: 'panel empty-panel' }, [
      h('div', { class: 'empty-icon' }, [icon('check')]),
      h('h2', {}, ['Queue is empty']),
      h('p', { class: 'dim' }, ['Everything you have practiced is still fresh. New content unlocks as you finish units.']),
      h('a', { class: 'primary-btn', href: '#/' }, ['Back to path']),
    ]));
    root.append(page); return;
  }
  for (const item of due) {
    const card = h('div', { class: 'panel' }, [
      h('div', { class: 'review-head' }, [
        h('div', {}, [
          h('h3', {}, [esc(item.title)]),
          h('div', { class: 'dim small' }, [item.lesson_id]),
        ]),
        h('div', { class: 'p-badge' }, [icon('bolt'), ` ${Math.round(item.p_recall * 100)}% recall`]),
      ]),
    ]);
    if (item.generated) {
      const { card: gc } = quizCard(
        { q: item.generated.q, choices: item.generated.choices },
        `g:${item.generated.token}`, async (origIdx) => {
          const res = await api.followupAnswer(item.generated.token, origIdx);
          refreshHud();
          return res;
        });
      card.append(gc);
    }
    item.practice.forEach((q, qi) => {
      const { card: qc } = quizCard(q, `${item.lesson_id}:p${qi}`, async (origIdx) => {
        const res = await api.answer(item.lesson_id, qi, origIdx);
        if (res.correct && res.xp) xpFly(res.xp);
        refreshHud();
        return res;
      });
      card.append(qc);
    });
    const actions = h('div', { class: 'btn-row' }, [
      h('a', { class: 'ghost-btn small', href: `#/lesson/${item.lesson_id}` }, ['Re-open lesson →']),
    ]);
    if (item.checkpoint) {
      let editorSlot = null;
      const retry = h('button', { class: 'ghost-btn small' }, [icon('code'), ' Re-attempt from memory']);
      retry.addEventListener('click', async () => {
        if (editorSlot) { editorSlot.classList.toggle('hidden'); return; }
        const ed = checkpointEditor({
          lessonId: item.lesson_id,
          starterCode: item.checkpoint.starter_code,
          hasSolution: item.checkpoint.has_solution,
        });
        editorSlot = h('div', { class: 'review-retry' }, [ed.el]);
        card.append(editorSlot);
        retry.textContent = 'Hide editor';
        ed.el.querySelector('.run-btn')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
      actions.append(retry);
    }
    card.append(actions);
    page.append(card);
  }
  root.append(page);
}