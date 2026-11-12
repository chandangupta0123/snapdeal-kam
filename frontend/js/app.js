import { api } from './api.js';
import { SR, speak, stopSpeaking, listen } from './voice.js';

const $ = s => document.querySelector(s);
let DS = null, history = [], callActive = false, state = 'idle', ear = null, LANG = 'en-IN';

function toast(t, ms = 4500) { const e = $('#toast'); e.textContent = t; e.style.display = 'block'; clearTimeout(toast.t); toast.t = setTimeout(() => e.style.display = 'none', ms); }
const showErr = t => { const e = $('#err'); e.textContent = t || ''; e.style.display = t ? 'block' : 'none'; };
const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

/* ---------- Screen 1: data ---------- */
function loadDS(ds) {
  DS = ds; showErr('');
  $('#pvTitle').textContent = ds.source; $('#pvSub').textContent = `${ds.periods[0]} → ${ds.periods[1]}`;
  $('#pvTable').innerHTML = `<tr><th>Metric</th><th class="n">${esc(ds.periods[0])}</th><th class="n">${esc(ds.periods[1])}</th><th class="n">Change</th></tr>` +
    ds.rows.map(r => `<tr><td>${r.label}${r.assumed ? '<span class="assumed">assumed</span>' : ''}</td><td class="n">${r.prev}</td><td class="n">${r.cur}</td><td class="n">${r.chg}</td></tr>`).join('');
  $('#preview').style.display = 'block'; $('#startBtn').disabled = false; $('#hint').textContent = '';
}
async function handleFile(f) {
  if (!f) return; showErr('');
  try { loadDS(await api.upload(f)); } catch (e) { showErr('⚠️ ' + e.message); }
}
$('#file').addEventListener('change', e => handleFile(e.target.files[0]));
const drop = $('#drop');
['dragover', 'dragenter'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => handleFile(e.dataTransfer.files[0]));
$('#sampleBtn').onclick = async () => { try { loadDS(await api.sample()); } catch (e) { showErr('⚠️ Backend not reachable: ' + e.message); } };
$('#tplBtn').onclick = () => {
  const csv = 'Metric,Last Month,This Month\nSales,200000,135000\nOrders,400,270\nCancellation rate,8%,14%\nAverage selling price,500,500\nOut-of-stock products,5,18\nProfit,36000,16200\nMargin,18%,12%\nProduct views,52000,47000\n';
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'seller_data_template.csv'; a.click();
};

/* ---------- Screen 2: call ---------- */
$('#startBtn').onclick = () => {
  LANG = $('#lang').value;
  $('#s-data').hidden = true; $('#s-call').hidden = false;
  $('#srcLabel').textContent = `${DS.source} · ${DS.periods[0]} vs ${DS.periods[1]}`;
  $('#kpis').innerHTML = DS.rows.map(r => `<div class="kpi"><div>${r.label}<small>${r.prev} → <b>${r.cur}</b></small></div><span class="chip ${r.cls}">${r.chg}</span></div>`).join('');
  $('#modeNote').textContent = DS.ai ? `🧠 ${DS.model}` : '🧠 Offline mode (set GEMINI_API_KEY on server)';
  if (!SR) toast('Voice input needs Chrome or Edge. You can still type below.', 8000);
  setState('idle');
};
$('#backBtn').onclick = () => { hangup(); $('#s-call').hidden = true; $('#s-data').hidden = false; };
$('#closeBtn').onclick = () => $('#modal').hidden = true;
$('#againBtn').onclick = () => { $('#modal').hidden = true; $('#log').innerHTML = ''; startCall(); };

const LABEL = { idle: 'Ready to call', listening: 'Listening… speak now', thinking: 'Thinking…', speaking: 'KAM is speaking' };
function setState(s) {
  state = s; $('#status').textContent = LABEL[s] || s;
  $('#orb').className = 'orb ' + s; $('#orb').textContent = s === 'speaking' ? '🔊' : s === 'thinking' ? '💭' : '🎙️';
  $('#skipBtn').hidden = !(callActive && s === 'speaking');
  $('#callBtn').hidden = callActive; $('#endBtn').hidden = !callActive;
  if (s !== 'listening') $('#interim').textContent = '';
}
function bubble(who, text) { const d = document.createElement('div'); d.className = 'b ' + who; d.textContent = text; $('#log').appendChild(d); $('#log').scrollTop = 1e9; }

async function botSay(text) {
  bubble('bot', text); history.push({ role: 'model', text });
  setState('speaking'); await speak(text, LANG);
  if (callActive) listenNow();
}
function stopEar() { if (ear) { ear.stop(); ear = null; } }
function listenNow() {
  if (!callActive) return; stopEar(); setState('listening');
  if (!SR) { $('#status').textContent = 'Type your reply below (voice input needs Chrome/Edge)'; return; }
  ear = listen(LANG, {
    onInterim: t => $('#interim').textContent = t,
    onFinal: handleUser,
    onRetry: () => { if (callActive && state === 'listening') setTimeout(listenNow, 200); },
    onDenied: () => { callActive = false; setState('idle'); toast('Microphone is blocked. Allow mic access in the address bar and try again (open via http://localhost).', 9000); },
  });
}
async function handleUser(text) {
  if (!callActive || state === 'thinking') return;
  stopEar(); stopSpeaking();
  bubble('me', text); history.push({ role: 'user', text }); setState('thinking');
  let rep;
  try { rep = await api.chat(DS, history, LANG); } catch (e) { rep = { text: 'Sorry, I had a connection problem. Could you say that again?', mode: 'error' }; }
  if (!callActive) return;
  if (rep.mode === 'offline') { $('#modeNote').textContent = '🧠 Offline mode'; if (rep.error) toast('Gemini unavailable, using offline mode. ' + rep.error, 7000); }
  if (rep.wrap) return wrapUp();
  botSay(rep.text);
}
function startCall() {
  history = []; callActive = true; setState('speaking');
  botSay(LANG === 'hi-IN' ? 'नमस्ते! मैं स्नैपडील की वर्चुअल की अकाउंट मैनेजर प्रिया बोल रही हूँ। आज मैं आपकी क्या मदद कर सकती हूँ?'
    : 'Namaste! This is Priya, your Snapdeal Virtual Key Account Manager. How can I help you today?');
}
function hangup() { callActive = false; stopEar(); stopSpeaking(); setState('idle'); }
async function wrapUp() {
  stopEar(); setState('thinking');
  let s;
  try { s = await api.summary(DS, history, LANG); } catch (e) { toast('Could not build summary: ' + e.message); return hangup(); }
  const fill = (id, a) => $(id).innerHTML = a.map(x => `<li>${esc(x)}</li>`).join('');
  fill('#sumIssues', s.issues); fill('#sumActions', s.actions); fill('#sumNext', s.next_steps);
  bubble('bot', s.spoken); $('#modal').hidden = false;
  setState('speaking'); await speak(s.spoken, LANG);
  callActive = false; setState('idle');
}
$('#callBtn').onclick = startCall;
$('#endBtn').onclick = () => { if (callActive) { stopSpeaking(); wrapUp(); } };
$('#skipBtn').onclick = stopSpeaking;
const sendTyped = () => { const v = $('#typed').value.trim(); if (!v) return; $('#typed').value = ''; if (!callActive) return toast('Press “Start call” first.'); handleUser(v); };
$('#sendBtn').onclick = sendTyped; $('#typed').addEventListener('keydown', e => { if (e.key === 'Enter') sendTyped(); });
