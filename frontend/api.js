const BASE = '';

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || data.error || `HTTP ${r.status}`);
  return data;
}

export const api = {
  state: () => req('/api/state'),
  curriculum: () => req('/api/curriculum'),
  lesson: (id) => req(`/api/lesson/${id}`),
  reviewQueue: () => req('/api/review-queue'),
  answer: (lesson_id, q_index, choice) =>
    req('/api/answer', { method: 'POST', body: JSON.stringify({ lesson_id, q_index, choice }) }),
  runCheckpoint: (lesson_id, code) =>
    req('/api/checkpoint/run', { method: 'POST', body: JSON.stringify({ lesson_id, code }) }),
  hint: (payload) => req('/api/hint', { method: 'POST', body: JSON.stringify(payload) }),
};
