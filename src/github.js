import { API_BASE_URL } from './config.js';
export async function fetchCommits({ owner, repo, branch = 'main', since, until }) {
  const qs = new URLSearchParams({ owner, repo, branch, since, until }).toString();
  const url = `${API_BASE_URL}/api/github/commits?${qs}`;
  const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!r.ok) { const t = await r.text(); throw new Error(`Backend /commits HTTP ${r.status} ${t}`); }
  const data = await r.json();
  // Support both shapes: raw array or { commits: [] }
  return Array.isArray(data) ? data : (Array.isArray(data?.commits) ? data.commits : []);
}

export async function fetchOrgCommits({ org, since, until, repos = [], maxRepos = 50 }) {
  const params = new URLSearchParams({ org, since, until, maxRepos });
  if (Array.isArray(repos) && repos.length) params.set('repos', repos.join(','));
  const url = `${API_BASE_URL}/api/github/org-commits?${params.toString()}`;
  const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!r.ok) { const t = await r.text(); throw new Error(`Backend /org-commits HTTP ${r.status} ${t}`); }
  const data = await r.json();
  return Array.isArray(data?.groups) ? data.groups : [];
}