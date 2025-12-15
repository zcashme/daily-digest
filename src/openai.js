import { API_BASE_URL } from './config.js';
export async function callOpenAI({ systemPrompt, input }) {
  const url = `${API_BASE_URL}/api/openai/summarize`;
  const userContent = buildUserContent(input);
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify({ systemPrompt, input: { ...input, userContent } }) });
  if (!r.ok) { const t = await r.text(); throw new Error(`Backend /openai/summarize HTTP ${r.status} ${t}`); }
  const data = await r.json();
  return String(data?.text || '');
}
function buildUserContent(input) {
  const { week, transcripts = [], github = [], trello = [] } = input || {};
  const header = `Generate a daily digest (WDWDY) covering ${week?.startDate} → ${week?.endDate}.\nIntegrate: transcripts, GitHub commits (main), Trello Meeting Notes.\nUse precise, audit-friendly Markdown.`;
  const tx = transcripts.map(t => `- ${t.filename}${t.dateGuess ? ` (${t.dateGuess})` : ''}\n${slice(t.text, 2000)}`).join('\n\n');
  const gh = github.map(c => `- ${c.date} ${c.author}: ${firstLine(c.message)} (${c.url})`).join('\n');
  const tr = trello.map(c => { const comments = (c.comments || []).map(cm => `  * ${cm.date} ${cm.member}: ${cm.text}`).join('\n'); const atts = (c.attachments || []).map(a => `  * [${a.name}](${a.url})`).join('\n'); return `- ${c.dateLastActivity} ${c.name} (${c.url})\n  Desc: ${slice(c.desc, 500)}\n${comments ? comments + '\n' : ''}${atts ? atts + '\n' : ''}`; }).join('\n\n');
  return `${header}\n\n== Transcripts ==\n${tx}\n\n== GitHub Commits ==\n${gh}\n\n== Trello Meeting Notes ==\n${tr}`;
}
function firstLine(s) { return String(s || '').split('\n')[0].trim() }
function slice(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n) + '…' : s }