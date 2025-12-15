// Runtime configuration for the static site (flattened at repo root)
// Environment-aware selection:
// - Local hosts → http://127.0.0.1:8001
// - Non-local hosts → https://weekly-digest-3rb8.onrender.com (Production Backend)

(function () {
  const RENDER_BASE = 'https://weekly-digest-3rb8.onrender.com';
  const LOCAL_BASE = 'http://127.0.0.1:8001';
  const host = String(window.location.hostname || '').toLowerCase();
  const isLocal = host === 'localhost' || host === '127.0.0.1' || host.startsWith('10.') || host.endsWith('.local');
  const selected = isLocal ? LOCAL_BASE : RENDER_BASE;
  window.CONFIG = {
    API_BASE_URL: selected,
  };
})();