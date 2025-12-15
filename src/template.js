export function buildWDWDY({ week, transcripts = [], github = [], trello = [] }) {
  const start = safeDate(week?.startDate); const end = safeDate(week?.endDate);
  const lines = [];
  lines.push(`# WDWDY – ${start} → ${end}`);
  lines.push('');
  lines.push('## Overview');
  lines.push('- Locally generated draft without model.');
  lines.push('- Includes transcripts, GitHub commits (main), and Trello Meeting Notes.');
  lines.push('');
  lines.push('## Daily Log');
  lines.push(formatTranscripts(transcripts));
  lines.push('');
  lines.push('## GitHub Commits (main)');
  lines.push(formatCommits(github));
  lines.push('');
  lines.push('## Trello – Meeting Notes');
  lines.push(formatTrello(trello));
  lines.push('');
  lines.push('## Cross-Day');
  lines.push('- Carryover tasks and threads noted from Trello and commits.');
  lines.push('');
  lines.push('## References');
  lines.push('- Links to commits and Trello cards included above.');
  return lines.join('\n');
}
function formatTranscripts(items){ if(!items.length) return '- No transcripts uploaded.'; return items.map(t=>`- ${t.filename}${t.dateGuess?` (${t.dateGuess})`:''}\n\n${clip(t.text,800)}`).join('\n\n'); }
function formatCommits(commits){ if(!commits.length) return '- No commits found in range.'; return commits.map(c=>`- ${c.date} ${c.author}: ${firstLine(c.message)} (${c.url})`).join('\n'); }
function formatTrello(cards){ if(!cards.length) return '- No Meeting Notes cards in range.'; return cards.map(c=>{ const cm=(c.comments||[]).map(x=>`  * ${x.date} ${x.member}: ${clip(x.text,160)}`).join('\n'); const at=(c.attachments||[]).map(a=>`  * [${a.name}](${a.url})`).join('\n'); return `- ${c.dateLastActivity} ${c.name} (${c.url})\n  Desc: ${clip(c.desc,300)}\n${cm}${cm?'\n':''}${at}`; }).join('\n\n'); }
function safeDate(s){try{return new Date(s).toISOString().slice(0,10)}catch{return String(s||'')}}
function firstLine(s){return String(s||'').split('\n')[0].trim()}
function clip(s,n){s=String(s||'');return s.length>n?s.slice(0,n)+'…':s}