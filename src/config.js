// Unified config adapter for web/weekly-digest
// Supports multiple API base URLs with environment-aware selection.
// Priority: window.CONFIG.API_BASE_URL → localhost → Render

const RENDER_BASE = 'https://weekly-digest-3rb8.onrender.com';
const LOCAL_BASE = 'http://127.0.0.1:8001';

function isLocalHost() {
  const h = String(window.location.hostname || '').toLowerCase();
  return h === 'localhost' || h === '127.0.0.1' || h.startsWith('10.') || h.endsWith('.local');
}

export const API_BASE_URLS = [
  (window.CONFIG && window.CONFIG.API_BASE_URL) || null,
  isLocalHost() ? LOCAL_BASE : RENDER_BASE,
  // Final fallback if above selection fails for any reason
  isLocalHost() ? RENDER_BASE : LOCAL_BASE,
].filter(Boolean);

export const API_BASE_URL = API_BASE_URLS[0];