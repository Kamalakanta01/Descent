import { h, icon, esc, toast, quizCard, xpFly } from './dom.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

export async function renderReview(root) {
  root.innerHTML = '';
  const { due } = await api.reviewQueue();
  const page = h('div', { class: 'review-page' });
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
    const card = h('div', { class: 'panel review-card' }, [
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
      const rerun = h('button', { class: 'ghost-btn small' }, [icon('code'), ' Re-run checkpoint']);
      rerun.addEventListener('click', async () => {
        rerun.disabled = true; rerun.textContent = 'Running…';
        try {
          const res = await api.runCheckpoint(item.lesson_id, item.checkpoint.starter_code);
          rerun.replaceWith(h('span', { class: `rerun-res ${res.passed ? 'ok' : 'bad'}` }, [
            res.passed ? [icon('check'), ' still passes — that memory is solid'] : [icon('skull'), ' fails now — re-open the lesson'],
          ]));
          if (res.passed && res.xp) toast(`+${res.xp} XP`, 'success');
        } catch (e) {
          toast(e.message, 'error');
          rerun.disabled = false;
          rerun.innerHTML = ''; rerun.append(icon('code'), ' Re-run checkpoint');
        }
        refreshHud();
      });
      actions.append(rerun);
    }
    card.append(actions);
    page.append(card);
  }
  root.append(page);
}