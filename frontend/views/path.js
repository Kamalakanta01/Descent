import { h, icon, esc, fmtXp } from './dom.js';
import { api } from '../api.js';
import { refreshHud } from '../app.js';

const WORLD_COLORS = ['#58cc02', '#1cb0f6', '#ce82ff', '#ff9600', '#ff4b4b', '#ffc800', '#14d4b0', '#3c8bff'];

function lessonNode(lesson, unitState, idx) {
  const isBoss = lesson.kind === 'program';
  const state = lesson.status;
  const node = h('div', {
    class: `node node-${state}${lesson.due ? ' due' : ''}${isBoss ? ' boss' : ''}`,
    style: `--i:${idx}`,
  });
  const btn = h('button', {
    class: 'node-btn',
    disabled: state === 'locked',
    title: lesson.title,
  });
  if (state === 'done') btn.append(icon('check'));
  else if (state === 'locked') btn.append(icon('lock'));
  else if (isBoss) btn.append(icon('skull'));
  else btn.append(icon('star'));
  node.append(btn);
  const label = h('div', { class: 'node-label' }, [esc(lesson.title)]);
  node.append(label);
  if (lesson.due) node.append(h('span', { class: 'due-pip', title: 'Review due' }));
  if (state !== 'locked') {
    btn.addEventListener('click', () => { location.hash = `#/lesson/${lesson.id}`; });
  }
  return node;
}

function unitCard(unit, worldId) {
  const color = WORLD_COLORS[worldId % WORLD_COLORS.length];
  const isBoss = unit.kind === 'boss';
  const card = h('div', {
    class: `unit-card ${unit.state}${isBoss ? ' boss-unit' : ''}`,
    style: `--unit-color:${color}`,
  });
  const head = h('div', { class: 'unit-head' }, [
    h('div', { class: 'unit-badge' }, [
      isBoss ? icon('skull') : h('span', { class: 'unit-num' }, [esc(unit.id.replace(/^w\d+u?/, '').toUpperCase() || '•')]),
    ]),
    h('div', { class: 'unit-title-wrap' }, [
      h('div', { class: 'unit-title' }, [esc(unit.title)]),
      h('div', { class: 'unit-sub' }, [isBoss ? 'Boss battle' : `${unit.lessons.length} lessons`]),
    ]),
    unit.state === 'done' ? h('div', { class: 'crown-mini' }, [icon('crown')]) : null,
  ]);
  const path = h('div', { class: 'lesson-path' });
  unit.lessons.forEach((l, i) => path.append(lessonNode(l, unit.state, i)));
  card.append(head, path);
  const anyClickable = unit.lessons.some(l => l.status !== 'locked');
  if (unit.state === 'locked' && !anyClickable && unit.lessons.length) {
    card.append(h('div', { class: 'unit-lock-overlay' }, [icon('lock'), h('span', {}, 'Complete the previous unit to unlock') ]));
  }
  return card;
}

export async function renderPath(root) {
  root.innerHTML = '';
  const [data] = await Promise.all([api.curriculum()]);
  const page = h('div', { class: 'path-page' });

  for (const world of data.worlds) {
    const color = WORLD_COLORS[world.id % WORLD_COLORS.length];
    const progressed = world.units.some(u => u.state !== 'locked');
    const section = h('section', { class: `world ${progressed ? '' : 'world-locked'}` });
    section.append(
      h('header', { class: 'world-head', style: `--world-color:${color}` }, [
        h('div', { class: 'world-num' }, [`WORLD ${world.id}`]),
        h('h2', {}, [esc(world.title)]),
        h('p', { class: 'world-sub' }, [esc(world.subtitle || '')]),
      ])
    );
    const grid = h('div', { class: 'unit-grid' });
    for (const u of world.units) grid.append(unitCard(u, world.id));
    section.append(grid);
    page.append(section);
  }
  root.append(page);
  refreshHud();
}
