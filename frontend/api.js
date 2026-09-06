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
  runCheckpoint: (lesson_id, code, revealed = false) =>
    req('/api/checkpoint/run', { method: 'POST', body: JSON.stringify({ lesson_id, code, revealed }) }),
  solution: (lesson_id) => req(`/api/lesson/${lesson_id}/solution`),
  followupAnswer: (token, choice) =>
    req('/api/followup/answer', { method: 'POST', body: JSON.stringify({ token, choice }) }),
  hint: (payload) => req('/api/hint', { method: 'POST', body: JSON.stringify(payload) }),
};
