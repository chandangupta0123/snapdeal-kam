// Browser speech: free Web Speech API (speech-to-text + text-to-speech). Chrome/Edge recommended.
export const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

const spoken = (t) => String(t).replace(/₹/g, 'rupees ').replace(/→/g, ' to ').replace(/%/g, ' percent');

function pickVoice(lang) {
  const vs = speechSynthesis.getVoices(), l = lang.toLowerCase(), pre = l.split('-')[0];
  return vs.find(v => v.lang.toLowerCase() === l && /google|natural|neural/i.test(v.name))
    || vs.find(v => v.lang.toLowerCase() === l)
    || vs.find(v => v.lang.toLowerCase().startsWith(pre)) || null;
}

export function speak(text, lang) {
  return new Promise(res => {
    speechSynthesis.cancel();
    const parts = (spoken(text).match(/[^.!?।]+[.!?।]*\s*/g) || [text]).filter(p => p.trim());
    if (!parts.length) return res();
    let left = parts.length; const v = pickVoice(lang);
    parts.forEach(p => {
      const u = new SpeechSynthesisUtterance(p.trim());
      u.lang = lang; u.rate = 1.02; if (v) u.voice = v;
      u.onend = u.onerror = () => { if (--left === 0) res(); };
      speechSynthesis.speak(u);
    });
  });
}
export const stopSpeaking = () => speechSynthesis.cancel();

// cb: {onInterim(text), onFinal(text), onRetry(), onDenied()}  -> returns {stop()} or null
export function listen(lang, cb) {
  if (!SR) return null;
  const r = new SR(); let got = false, dead = false, stopped = false;
  r.lang = lang; r.interimResults = true; r.continuous = false;
  r.onresult = e => {
    let it = '', fin = '';
    for (let i = e.resultIndex; i < e.results.length; i++) { const t = e.results[i][0].transcript; e.results[i].isFinal ? fin += t : it += t; }
    cb.onInterim(it || fin);
    if (fin.trim()) { got = true; cb.onFinal(fin.trim()); }
  };
  r.onerror = e => { if (['not-allowed', 'service-not-allowed'].includes(e.error)) { dead = true; cb.onDenied(); } };
  r.onend = () => { if (!dead && !got && !stopped) cb.onRetry(); };
  try { r.start(); } catch (e) { /* already started */ }
  return { stop() { stopped = true; r.onend = null; try { r.abort(); } catch (e) { } } };
}
