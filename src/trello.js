import { API_BASE_URL } from './config.js';
export async function fetchMeetingNotes({ boardName, listName, since, until }) {
  const url = `${API_BASE_URL}/api/trello/meeting-notes`;
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ boardName, listName, since, until })
  });
  if (!r.ok) { const t = await r.text(); throw new Error(`Backend /trello/meeting-notes HTTP ${r.status} ${t}`); }
  const data = await r.json();
  // Support both shapes: raw array or { notes: [] }
  return Array.isArray(data) ? data : (Array.isArray(data?.notes) ? data.notes : []);
}

export async function fetchBoardActions({ boardName, since, until, types = 'all', inProgressList, completedList }) {
  const url = `${API_BASE_URL}/api/trello/board-actions`;
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ boardName, since, until, types, inProgressList, completedList })
  });
  if (!r.ok) { const t = await r.text(); throw new Error(`Backend /trello/board-actions HTTP ${r.status} ${t}`); }
  const data = await r.json();
  return Array.isArray(data?.groups) ? data.groups : [];
}