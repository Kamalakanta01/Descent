import { h, icon, esc, toast } from './dom.js';
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
    item.practice.forEach((q, qi) => {
      const qc = h('div', { class: 'q-card' }, [h('p', { class: 'q-text' }, [esc(q.q)])]);
      const choices = h('div', { class: 'choices' });
      q.choices.forEach((c, ci) => {
        const b = h('button', { class: 'choice' }, [esc(c)]);
        b.addEventListener('click', async () => {
          if (qc.dataset.locked === '1') return;
          qc.dataset.locked = '1';
          try {
            const res = await api.answer(item.lesson_id, qi, ci);
            qc.classList.add(res.correct ? 'q-correct' : 'q-wrong');
            qc.append(h('div', { class: 'q-expl' }, [esc(res.explanation || '')]));
            refreshHud();
          } catch (e) { toast(e.message, 'error'); qc.dataset.locked = ''; }
        });
        choices.append(b);
      });
      qc.append(choices);
      card.append(qc);
    });
    card.append(h('a', { class: 'ghost-btn small', href: `#/lesson/${item.lesson_id}` }, ['Re-open lesson →']));
    page.append(card);
  }
  root.append(page);
}
