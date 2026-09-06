import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div><div id="hud"></div></body></html>', { url: 'http://localhost/#/' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.location = dom.window.location;
globalThis.HTMLElement = dom.window.HTMLElement;
dom.window.scrollTo = () => {};
dom.window.HTMLElement.prototype.scrollIntoView = () => {};

const { h, esc, icon, md, highlightC, shuffleStable } = await import('../views/dom.js');

test('esc escapes HTML', () => {
  assert.equal(esc('<b>&"\'</b>'), '&lt;b&gt;&amp;&quot;&#39;&lt;/b&gt;');
});

test('highlightC does not double-escape', () => {
  const out = highlightC('int x = 1 < 2; // ok');
  assert.ok(out.includes('c-kw'));
  assert.ok(!out.includes('&amp;lt;'));
});

test('md renders fenced code block as pre', () => {
  const out = md('Para one\n```\nint a;\n```\n- bullet');
  assert.ok(out.includes('<pre class="md-code"><code>'));
  assert.ok(out.includes('<ul><li>bullet</li></ul>'));
});

test('shuffleStable shuffles copy, pins order per key, keeps original indices', () => {
  const a = ['x', 'y', 'z'];
  const s1 = shuffleStable('k', a);
  assert.deepEqual(new Set(s1.map(p => p.value)), new Set(a)); // same multiset
  assert.deepEqual(s1.map(p => a[p.index]), s1.map(p => p.value)); // value-label sounds right
  // pinned: twice same key → identical order
  const s2 = shuffleStable('k', a);
  assert.deepEqual(s1, s2);
  // different key → not *necessarily* equal, but distribution is fine; just assert it works
  assert.equal(shuffleStable('j', a).length, 3);
  assert.deepEqual(a, ['x', 'y', 'z']); // original untouched
});

test('h builds elements with attrs and text children', () => {
  const el = h('button', { class: 'x', 'data-orig': 2, disabled: true }, ['hi']);
  assert.equal(el.className, 'x');
  assert.equal(el.dataset.orig, '2');
  assert.ok(el.disabled);
  assert.equal(el.textContent, 'hi');
});

test('icon returns an svg-bearing span', () => {
  const el = icon('check');
  assert.ok(el.querySelector('svg'));
});