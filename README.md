# Daily Digest (WDWDY)

Automated **Daily Digest** tool for Zcash Me. It aggregates:

1. **GitHub Commits** (from `zcashme` organization)
2. **Trello Activity** (Meeting Notes & Board Actions)
3. **Meeting Transcripts** (uploaded via Web UI)

## How It Works

### Daily Automation

- Runs every day at **09:00 UTC** via GitHub Actions.
- Fetches the previous 24 hours of Trello activity (actions, moves, comments).
- Generates a summary JSON.
- **Posts a Trello Card** to the Inbox list with the summary.

### Manual Web App

- Run locally (`python webapp.py`) to generate a full Markdown report using OpenAI.
- Select "Start Date" and "End Date" (defaults to Yesterday).
- Click **Load Daily Data**.

## Structure

```
.
├── assets/
│   └── styles.css
├── prompts/
│   └── summary_system_prompt.md
├── src/
│   ├── config.js
│   ├── dragdrop.js
│   ├── github.js
│   ├── openai.js
│   ├── template.js
│   └── trello.js
├── config.js            # Runtime frontend config (window.CONFIG.API_BASE_URL)
├── index.html           # Single-page Daily Digest (repo root)
├── scripts/
│   └── trello_activity.py
├── webapp.py            # Flask backend API
├── requirements.txt
└── .env.example
```

## Local Development

1) Install dependencies and start the backend (port 8001):

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys and tokens
PORT=8001 .venv/bin/python webapp.py
```

2) Start the static frontend server (repo root):

```
python3 -m http.server 8012
# open: http://localhost:8012/
```

> `src/config.js` reads `window.CONFIG.API_BASE_URL`. If not set, it falls back to `http://127.0.0.1:8001` for local development.

## Credentials

- Trello (required): `TRELLO_KEY`, `TRELLO_TOKEN`
- GitHub (optional): `GITHUB_TOKEN` (to improve rate limits)
- OpenAI (optional): `OPENAI_API_KEY` (for summarization)

Set these in `.env`; `webapp.py` will auto-load them.

## GitHub Pages (Frontend Only)

- Settings → Pages → Deploy from branch → `main / root`
- Point `config.js` `API_BASE_URL` to your public backend (HTTPS), or set `window.CONFIG.API_BASE_URL` inline.

## Backend API Routes

- `GET /api/github/commits`: `owner, repo, branch, since, until`
- `GET /api/github/org-commits`: `org, since, until, repos(optional comma-list), maxRepos(optional)`
- `GET|POST /api/trello/meeting-notes`: `boardName, listName, since, until`
- `GET|POST /api/trello/board-actions`: `boardName, since, until, types, inProgressList(optional), completedList(optional)`
- `POST /api/openai/summarize`: `systemPrompt, input`

### Response Shapes

- `/api/github/org-commits` → `{ groups: [{ repo, url, branch, commits: [{ sha, url, message, author, date }] }] }`
- `/api/trello/board-actions` → `{ groups: [{ column: 'In Progress'|'Completed'|..., cards: [{ cardId, name, url, labels: [{name,color}], owners: [{fullName,username}], completion: {completed,total}, actions: [{ date, type, member, text, attachment }] }] }] }`
- `/api/trello/meeting-notes` → `[{ cardId, name, url, titleDate, addedDate, dateLastActivity, desc, comments: [{ text, date, member }], attachments: [{ name, url, mimeType }] }]`

Notes:

- Meeting Notes classification uses the date in the card title when available. Supported formats: `YYYY-MM-DD`, `YYYY/MM/DD`, `MM-DD`, `MM/DD`. The end date in the filter range is inclusive. If no parsable title date exists, `dateLastActivity` is used as a fallback.
- Frontend Meeting Notes are displayed in descending order by date (newest first). The entry shows `titleDate` followed by `(Added Date: ISO)` in parentheses.
- Trello actions are filtered to: moves/creates into target columns, comments that include links, checklist items marked complete, and attachments added (not removed).
- Trello results are grouped strictly under two columns: `In Progress` and `Completed`. If `inProgressList` / `completedList` are provided, only those are used. Matching is case-insensitive and recognizes common aliases (e.g., `complete`, `done` for Completed; `in progress`, `doing` for In Progress). If a card appears in both, `Completed` takes precedence.

## Notes

- Use HTTPS for backend in production; the frontend points to it via `window.CONFIG.API_BASE_URL`.
- This is a monorepo: GitHub Pages publishes only the static frontend; the backend must be deployed separately.
