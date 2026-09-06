/* DOM helpers */
export function h(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function')
      el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  }
  const kids = Array.isArray(children) ? children : [children];
  for (const c of kids) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const ICONS = {
  flame: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22c5 0 8-3.5 8-8.5C20 8 14 2 12 2S4 8 4 13.5C4 18.5 7 22 12 22z"/><path d="M12 22c2.8 0 5-2.2 5-5 0-2.2-1.8-4.5-3-6-1 1.2-2.7 3.1-2.7 5.5 0 1.4 1 2.5 2.7 2.5z"/></svg>`,
  bolt: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/></svg>`,
  crown: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 8l4 4 5-6 5 6 4-4v9H3V8z"/></svg>`,
  lock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M4 12.5l5 5L20 6.5"/></svg>`,
  star: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.6.7-5 4.4 1.5 6.6L12 16.6 5.9 20l1.5-6.6-5-4.4 6.6-.7L12 2z"/></svg>`,
  skull: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C7 2 3 6 3 11c0 2.5 1 4.7 2.6 6.2L6 20l2 1 1.5-2L12 20l2.5-1 1.5 2 2-1 .4-2.8C20 15.7 21 13.5 21 11c0-5-4-9-9-9z"/><circle cx="9" cy="11" r="1.6" fill="currentColor"/><circle cx="15" cy="11" r="1.6" fill="currentColor"/><path d="M10 16h.01M14 16h.01"/></svg>`,
  book: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20V4H6.5A2.5 2.5 0 004 6.5v13z"/><path d="M20 17v3H6.5a2.5 2.5 0 010-5"/></svg>`,
  code: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6l-6 6 6 6M16 6l6 6-6 6"/></svg>`,
  play: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 4l14 8-14 8V4z"/></svg>`,
  spark: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 1l2.4 7.2H22l-6 4.6 2.3 7.2-6.3-4.5-6.3 4.5L8 12.8 2 8.2h7.6L12 1z"/></svg>`,
};

export function icon(name, cls = '') {
  const span = document.createElement('span');
  span.className = `icon ${cls}`;
  span.innerHTML = ICONS[name] || '';
  return span;
}

/* Escape text before injecting into innerHTML */
export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* Super-light C syntax highlighter (keyword/type/comment/string/number).
   Input code is escaped first, then wrapped in spans. */
const KW = /\b(if|else|for|while|do|return|break|continue|switch|case|default|struct|typedef|enum|union|static|const|void|int|float|double|char|size_t|uint32_t|uint64_t|int32_t|int64_t|unsigned|long|short|sizeof|extern|volatile|register|inline)\b/g;

export function highlightC(code) {
  let s = esc(code);
  s = s.replace(/(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g, '<span class="c-com">$1</span>');
  s = s.replace(/(&quot;[^&]*?&quot;|'[^'\n]*')/g, '<span class="c-str">$1</span>');
  s = s.replace(KW, '<span class="c-kw">$1</span>');
  s = s.replace(/\b(\d+\.?\d*f?u?)\b/g, '<span class="c-num">$1</span>');
  s = s.replace(/^(\s*#\w+)/gm, '<span class="c-pre">$1</span>');
  return s;
}

/* Minimal markdown-ish: paragraphs, inline code, - bullets, ``` blocks */
export function md(src) {
  const out = [];
  let inCode = false;
  let codeBuf = [];
  for (const raw of src.split('\n')) {
    if (raw.trim().startsWith('````') || raw.trim().startsWith('```')) {
      if (inCode) { out.push('<pre class="md-code"><code>' + highlightC(codeBuf.join('\n')) + '</code></pre>'); codeBuf = []; inCode = false; }
      else inCode = true;
      continue;
    }
    if (inCode) { codeBuf.push(raw); continue; }
    const line = raw.trim();
    if (!line) continue;
    const inline = esc(line).replace(/`([^`]+)`/g, '<code>$1</code>');
    if (line.startsWith('- ')) out.push(`<li>${inline.slice(2)}</li>`);
    else out.push(`<p>${inline}</p>`);
  }
  if (inCode) out.push('<pre class="md-code"><code>' + highlightC(codeBuf.join('\n')) + '</code></pre>');
  let html = out.join('');
  html = html.replace(/(<li>[\s\S]*?<\/li>)(?=\s*<li>)/g, '$1');
  html = html.replace(/((?:<li>[\s\S]*?<\/li>\s*)+)/g, '<ul>$1</ul>');
  return html;
}

export function toast(msg, kind = 'info') {
  let wrap = document.querySelector('.toasts');
  if (!wrap) { wrap = h('div', { class: 'toasts' }); document.body.append(wrap); }
  const t = h('div', { class: `toast toast-${kind}` }, [esc(String(msg))]);
  wrap.append(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 400); }, 3600);
}

/* Shuffle a copy of arr, but pin the permutation per key for the session:
   the displayed order stays identical across re-renders, so the correct
   answer never moves between attempts/spoils position. Returns [{value, index}]
   pairs so callers can map back to the original choice index. */
const stableOrder = new Map();
export function shuffleStable(key, arr) {
  if (!stableOrder.has(key)) {
    const idx = arr.map((_, i) => i);
    for (let i = idx.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [idx[i], idx[j]] = [idx[j], idx[i]];
    }
    stableOrder.set(key, idx);
  }
  return stableOrder.get(key).map(i => ({ value: arr[i], index: i }));
}

/* Reusable multiple-choice card: shuffled choices (stable per key), locks after
   answering, highlights the correct choice (via res.answer_index) and the wrong
   pick, shows the explanation, then calls onAnswered for page-specific extras. */
export function quizCard(question, key, grade, onAnswered) {
  const card = h('div', { class: 'q-card' });
  card.append(h('p', { class: 'q-text' }, [esc(question.q)]));
  const choices = h('div', { class: 'choices' });
  for (const { value, index } of shuffleStable(key, question.choices)) {
    const btn = h('button', { class: 'choice', 'data-orig': index }, [esc(value)]);
    btn.addEventListener('click', async () => {
      if (card.dataset.locked === '1') return;
      card.dataset.locked = '1';
      try {
        const res = await grade(index);
        card.classList.add(res.correct ? 'q-correct' : 'q-wrong');
        for (const b of choices.querySelectorAll('.choice')) {
          b.disabled = true;
          const orig = +b.dataset.orig;
          if (orig === res.answer_index) b.classList.add('choice-correct');
          else if (orig === index && !res.correct) b.classList.add('choice-wrong');
        }
        card.append(h('div', { class: 'q-expl' }, [esc(res.explanation || '')]));
        if (onAnswered) onAnswered(card, res);
      } catch (e) {
        card.dataset.locked = '';
        toast(e.message, 'error');
      }
    });
    choices.append(btn);
  }
  card.append(choices);
  return { card, choices };
}

export function xpFly(xp) {
  const el = h('div', { class: 'xp-fly' }, [`+${xp} XP`]);
  document.body.append(el);
  setTimeout(() => el.remove(), 1400);
}

export function fmtXp(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
