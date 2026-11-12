// Talks to the FastAPI backend. Same origin, so no CORS or keys in the browser.
async function call(url, opt) {
  const r = await fetch(url, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.statusText);
  return j;
}
const post = (url, body) => call(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  sample: () => call('/api/sample'),
  upload: (file) => { const fd = new FormData(); fd.append('file', file); return call('/api/upload', { method: 'POST', body: fd }); },
  chat: (dataset, history, lang) => post('/api/chat', { dataset, history, lang }),
  summary: (dataset, history, lang) => post('/api/summary', { dataset, history, lang }),
};
