import { h, icon, esc, fmtXp, toast } from './views/dom.js';
import { api } from './api.js';
import { renderPath } from './views/path.js';
import { renderLesson } from './views/lesson.js';
import { renderReview } from './views/review.js';

const appRoot = document.getElementById('app');
const hudState = { xp: 0, streak: 0, due: 0 };

export async function refreshHud() {
  try {
    const s = await api.state();
    hudState.xp = s.xp; hudState.streak = s.streak; hudState.due = s.due_reviews;
    const hud = document.getElementById('hud');
    hud.innerHTML = '';
    hud.append(
      h('span', { class: 'hud-pill hud-xp' }, [icon('bolt'), fmtXp(s.xp) + ' XP']),
      h('span', { class: 'hud-pill hud-streak' + (s.streak > 0 ? ' lit' : '') }, [icon('flame'), String(s.streak)]),
      h('a', { class: 'hud-pill hud-review' + (s.due_reviews ? ' due' : ''), href: '#/review' }, [
        icon('crown'), s.due_reviews ? `${s.due_reviews} due` : 'review',
      ]),
    );
  } catch (e) { /* keep old hud on error */ }
}

async function route() {
  const hash = location.hash || '#/';
  const m = hash.match(/^#\/lesson\/([\w-]+)/);
  appRoot.innerHTML = '';
  try {
    if (m) await renderLesson(appRoot, m[1]);
    else if (hash.startsWith('#/review')) { await renderReview(appRoot); await refreshHud(); }
    else await renderPath(appRoot);
  } catch (e) {
    console.error(e);
    appRoot.append(h('div', { class: 'panel error-panel' }, [
      h('h2', {}, ['Something broke']),
      h('pre', { class: 'console' }, [esc(String(e.stack || e))]),
      h('a', { class: 'primary-btn', href: '#/' }, ['Back to path']),
    ]));
    toast(e.message || 'error', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.addEventListener('hashchange', route);
  refreshHud();
  route();
});
