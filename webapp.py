import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, make_response
import requests

# --- simple .env loader (no external deps) ---
def load_env_file(path='.env'):
    try:
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if '=' not in s:
                    continue
                k, v = s.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (k not in os.environ or not os.environ.get(k)):
                    os.environ[k] = v
    except Exception:
        # ignore .env parse errors to avoid blocking server
        pass

# Load env from local .env if present
load_env_file()

app = Flask(__name__)

# Simple CORS for local dev and GitHub Pages
# You can restrict origins via env: ALLOWED_ORIGINS="https://xiang-suc.github.io,https://localhost:8022"
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')

@app.after_request
def add_cors(resp):
    origin = (request.headers.get('Origin') or '').strip()
    allowed = ALLOWED_ORIGINS.strip()
    # Allow specific origins list or wildcard
    if allowed == '*' or not allowed:
        resp.headers['Access-Control-Allow-Origin'] = origin or '*'
    else:
        allowed_set = {o.strip() for o in allowed.split(',') if o.strip()}
        if origin and origin in allowed_set:
            resp.headers['Access-Control-Allow-Origin'] = origin
    # Ensure essential CORS headers for preflight
    req_headers = request.headers.get('Access-Control-Request-Headers', '')
    resp.headers['Access-Control-Allow-Headers'] = req_headers or 'Content-Type, Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Vary'] = 'Origin'
    return resp

@app.route('/api/github/commits', methods=['GET', 'OPTIONS'])
def github_commits():
    if request.method == 'OPTIONS':
        return make_response('', 204)

    owner = request.args.get('owner', '').strip()
    repo = request.args.get('repo', '').strip()
    branch = request.args.get('branch', 'main').strip()
    since = request.args.get('since', '').strip()
    until = request.args.get('until', '').strip()

    if not owner or not repo or not since or not until:
        return jsonify({ 'error': 'Missing required params: owner, repo, since, until' }), 400

    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {
        'Accept': 'application/vnd.github+json',
        **({ 'Authorization': f'Bearer {token}' } if token else {})
    }

    commits = []
    page = 1
    try:
        while page < 10:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&since={since}&until={until}&per_page=100&page={page}"
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code >= 400:
                return jsonify({ 'error': f'GitHub HTTP {r.status_code}', 'details': r.text }), r.status_code
            batch = r.json()
            commits.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    except requests.RequestException as e:
        return jsonify({ 'error': 'GitHub request failed', 'details': str(e) }), 502

    def to_utc_iso(s):
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone().isoformat().replace('+00:00', 'Z')
        except Exception:
            try:
                return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z').astimezone().isoformat().replace('+00:00', 'Z')
            except Exception:
                return s or ''

    normalized = []
    for c in commits:
        msg = (c.get('commit') or {}).get('message', '')
        author_name = ((c.get('commit') or {}).get('author') or {}).get('name') or (c.get('author') or {}).get('login') or ''
        author_date = ((c.get('commit') or {}).get('author') or {}).get('date') or ''
        normalized.append({
            'sha': c.get('sha'),
            'url': c.get('html_url'),
            'message': msg,
            'author': author_name,
            'date': to_utc_iso(author_date)
        })

    return jsonify(normalized)

@app.route('/api/github/org-commits', methods=['GET', 'OPTIONS'])
def github_org_commits():
    if request.method == 'OPTIONS':
        return make_response('', 204)

    org = (request.args.get('org') or '').strip()
    since = (request.args.get('since') or '').strip()
    until = (request.args.get('until') or '').strip()
    repos_filter = (request.args.get('repos') or '').strip()  # optional comma-separated repo names
    max_repos = int(request.args.get('maxRepos') or '50')

    if not org or not since or not until:
        return jsonify({'error': 'Missing required params: org, since, until'}), 400

    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {
        'Accept': 'application/vnd.github+json',
        **({ 'Authorization': f'Bearer {token}' } if token else {})
    }

    # List repos in the organization (paginate, up to max_repos)
    repos = []
    page = 1
    try:
        while len(repos) < max_repos and page < 10:
            url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}&type=all&sort=updated"
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code >= 400:
                return jsonify({ 'error': f'GitHub HTTP {r.status_code}', 'details': r.text }), r.status_code
            batch = r.json() or []
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    except requests.RequestException as e:
        return jsonify({ 'error': 'GitHub list repos failed', 'details': str(e) }), 502

    # Optional filter by repo names
    filter_set = {n.strip().lower() for n in repos_filter.split(',') if n.strip()} if repos_filter else None
    selected = []
    for r in repos:
        name = (r.get('name') or '').strip()
        if not name:
            continue
        if filter_set and name.lower() not in filter_set:
            continue
        selected.append({
            'name': name,
            'full_name': r.get('full_name') or name,
            'html_url': r.get('html_url') or '',
            'default_branch': r.get('default_branch') or 'main',
            'pushed_at': r.get('pushed_at') or ''
        })
        if len(selected) >= max_repos:
            break

    def to_utc_iso(s):
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone().isoformat().replace('+00:00', 'Z')
        except Exception:
            try:
                return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z').astimezone().isoformat().replace('+00:00', 'Z')
            except Exception:
                return s or ''

    # For each repo, fetch commits in range
    groups = []
    for repo in selected:
        commits = []
        page = 1
        try:
            while page < 10:
                url = (
                    f"https://api.github.com/repos/{org}/{repo['name']}/commits"
                    f"?sha={repo['default_branch']}&since={since}&until={until}&per_page=100&page={page}"
                )
                r = requests.get(url, headers=headers, timeout=30)
                if r.status_code >= 400:
                    # If commits endpoint fails (e.g., archived), skip repo but continue
                    break
                batch = r.json() or []
                commits.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
        except requests.RequestException:
            # Skip on error for this repo
            commits = []

        normalized = []
        for c in commits:
            msg = (c.get('commit') or {}).get('message', '')
            author_name = ((c.get('commit') or {}).get('author') or {}).get('name') or (c.get('author') or {}).get('login') or ''
            author_date = ((c.get('commit') or {}).get('author') or {}).get('date') or ''
            normalized.append({
                'sha': c.get('sha'),
                'url': c.get('html_url'),
                'message': msg,
                'author': author_name,
                'date': to_utc_iso(author_date)
            })

        if normalized:
            groups.append({
                'repo': repo['name'],
                'url': repo['html_url'],
                'branch': repo['default_branch'],
                'commits': normalized
            })

    return jsonify({'groups': groups})

# --- Trello proxy ---

def trello_get(url, params=None):
    key = os.getenv('TRELLO_KEY', '').strip()
    token = os.getenv('TRELLO_TOKEN', '').strip()
    if not key or not token:
        raise ValueError('Missing TRELLO_KEY/TRELLO_TOKEN')
    params = params or {}
    params.update({'key': key, 'token': token})
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

@app.route('/api/trello/meeting-notes', methods=['GET', 'POST', 'OPTIONS'])
def trello_meeting_notes():
    if request.method == 'OPTIONS':
        return make_response('', 204)
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        board_name = (data.get('boardName') or '').strip()
        list_name = (data.get('listName') or '').strip()
        since = (data.get('since') or '').strip()
        until = (data.get('until') or '').strip()
    else:
        board_name = (request.args.get('boardName') or '').strip()
        list_name = (request.args.get('listName') or '').strip()
        since = (request.args.get('since') or '').strip()
        until = (request.args.get('until') or '').strip()
    if not board_name or not list_name or not since or not until:
        return jsonify({'error': 'Missing required params: boardName, listName, since, until'}), 400

    try:
        boards = trello_get('https://api.trello.com/1/members/me/boards')
        board = next((b for b in boards if (b.get('name') or '').lower() == board_name.lower()), None)
        if not board:
            return jsonify({'error': f'Board not found: {board_name}'}), 404
        lists = trello_get(f'https://api.trello.com/1/boards/{board.get("id")}/lists')
        lst = next((l for l in lists if (l.get('name') or '').lower() == list_name.lower()), None)
        if not lst:
            return jsonify({'error': f'List not found: {list_name}'}), 404
        cards = trello_get(f'https://api.trello.com/1/lists/{lst.get("id")}/cards', params={'fields': 'name,desc,dateLastActivity,shortUrl'})

        since_t = datetime.fromisoformat(since.replace('Z', '+00:00')).timestamp()
        until_t = datetime.fromisoformat(until.replace('Z', '+00:00')).timestamp()

        def to_utc_iso(s):
            try:
                return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone().isoformat().replace('+00:00', 'Z')
            except Exception:
                try:
                    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z').astimezone().isoformat().replace('+00:00', 'Z')
                except Exception:
                    return s or ''

        def to_date_str(iso_s):
            try:
                return datetime.fromisoformat(iso_s.replace('Z', '+00:00')).date().isoformat()
            except Exception:
                return ''

        def parse_title_date(name, fallback_year):
            s = (name or '').strip()
            # Prefer full year format like YYYY-MM-DD or YYYY/MM/DD
            m = re.search(r'(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})', s)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
                except Exception:
                    pass
            # Fallback: MM-DD or MM/DD, infer year from since
            m2 = re.search(r'(\d{1,2})[\-/](\d{1,2})', s)
            if m2:
                mo, d = int(m2.group(1)), int(m2.group(2))
                try:
                    return f"{fallback_year:04d}-{mo:02d}-{d:02d}"
                except Exception:
                    pass
            return ''

        results = []
        since_date = to_date_str(since)
        until_date = to_date_str(until)
        fallback_year = 0
        try:
            fallback_year = datetime.fromisoformat(since.replace('Z', '+00:00')).year
        except Exception:
            fallback_year = datetime.utcnow().year
        for c in cards:
            # Determine title date from card name for classification
            title_date = parse_title_date(c.get('name') or '', fallback_year)
            # If title date exists, use it to decide range; otherwise fallback to activity window
            if title_date:
                # Include end date (<= until_date) so 11-20 falls within 11/17–11/20
                if not (since_date <= title_date <= until_date):
                    continue
            else:
                act_str = c.get('dateLastActivity') or c.get('date') or ''
                try:
                    act_ts = datetime.fromisoformat(act_str.replace('Z', '+00:00')).timestamp()
                except Exception:
                    act_ts = 0
                # Include end timestamp (<= until_t)
                if not act_ts or act_ts < since_t or act_ts > until_t:
                    continue
            comments = trello_get(f'https://api.trello.com/1/cards/{c.get("id")}/actions', params={'filter': 'commentCard', 'limit': 1000, 'since': since, 'before': until})
            attachments = trello_get(f'https://api.trello.com/1/cards/{c.get("id")}/attachments')
            # Added date: earliest create/copy action if available
            added_date_iso = ''
            try:
                add_actions = trello_get(f'https://api.trello.com/1/cards/{c.get("id")}/actions', params={'filter': 'all', 'limit': 100})
                created_events = [a for a in (add_actions or []) if (a.get('type') or '') in {'createCard', 'copyCard'}]
                if created_events:
                    earliest = sorted(created_events, key=lambda a: (a.get('date') or ''))[0]
                    added_date_iso = to_utc_iso(earliest.get('date') or '')
            except Exception:
                added_date_iso = ''
            results.append({
                'cardId': c.get('id'),
                'name': c.get('name'),
                'url': c.get('shortUrl'),
                'dateLastActivity': to_utc_iso(c.get('dateLastActivity') or ''),
                'titleDate': title_date,
                'addedDate': added_date_iso,
                'desc': c.get('desc') or '',
                'comments': [
                    {
                        'text': (a.get('data') or {}).get('text') or '',
                        'date': to_utc_iso(a.get('date') or ''),
                        'member': ((a.get('memberCreator') or {}).get('fullName') or '')
                    }
                    for a in comments
                ],
                'attachments': [
                    {
                        'name': att.get('name'),
                        'url': att.get('url') or att.get('downloadUrl') or '',
                        'mimeType': att.get('mimeType') or ''
                    }
                    for att in attachments
                ],
            })
        return jsonify(results)
    except requests.HTTPError as e:
        return jsonify({'error': 'Trello HTTP error', 'details': str(e)}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Unexpected trello error', 'details': str(e)}), 500

# --- OpenAI proxy ---

def build_user_content(input_obj):
    week = (input_obj or {}).get('week') or {}
    transcripts = (input_obj or {}).get('transcripts') or []
    github = (input_obj or {}).get('github') or []
    trello = (input_obj or {}).get('trello') or []
    header = (
        f"Generate a daily digest (WDWDY) covering {week.get('startDate')} → {week.get('endDate')}\n"
        "Integrate: transcripts, GitHub commits (main), Trello Meeting Notes.\n"
        "Use precise, audit-friendly Markdown. Keep sections: Day Range, Overview, Daily Log, Cross-Day, References."
    )
    def slice_text(s, n):
        s = str(s or '')
        return (s[:n] + '…') if len(s) > n else s
    def first_line(s):
        return str(s or '').split('\n')[0].strip()
    tx = '\n\n'.join([f"- {t.get('filename')}{(' (' + t.get('dateGuess') + ')') if t.get('dateGuess') else ''}\n{slice_text(t.get('text'), 2000)}" for t in transcripts])
    gh = '\n'.join([f"- {c.get('date')} {c.get('author')}: {first_line(c.get('message'))} ({c.get('url')})" for c in github])
    def trello_block(c):
        comments = '\n'.join([f"  * {cm.get('date')} {cm.get('member')}: {cm.get('text')}" for cm in (c.get('comments') or [])])
        atts = '\n'.join([f"  * [{a.get('name')}]({a.get('url')})" for a in (c.get('attachments') or [])])
        return f"- {c.get('dateLastActivity')} {c.get('name')} ({c.get('url')})\n  Desc: {slice_text(c.get('desc'), 500)}\n" + (comments + '\n' if comments else '') + (atts + '\n' if atts else '')
    tr = '\n\n'.join([trello_block(c) for c in trello])
    return f"{header}\n\n== Transcripts ==\n{tx}\n\n== GitHub Commits ==\n{gh}\n\n== Trello Meeting Notes ==\n{tr}"

@app.route('/api/trello/board-actions', methods=['GET', 'POST', 'OPTIONS'])
def trello_board_actions():
    if request.method == 'OPTIONS':
        return make_response('', 204)
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        board_name = (data.get('boardName') or '').strip()
        since = (data.get('since') or '').strip()
        until = (data.get('until') or '').strip()
        types = (data.get('types') or '').strip()  # comma-separated action types or 'all'
    else:
        board_name = (request.args.get('boardName') or '').strip()
        since = (request.args.get('since') or '').strip()
        until = (request.args.get('until') or '').strip()
        types = (request.args.get('types') or '').strip()
    in_progress_list = None
    completed_list = None
    if request.method == 'POST':
        in_progress_list = (data.get('inProgressList') or '').strip() or None
        completed_list = (data.get('completedList') or '').strip() or None
    else:
        in_progress_list = (request.args.get('inProgressList') or '').strip() or None
        completed_list = (request.args.get('completedList') or '').strip() or None

    if not board_name or not since or not until:
        return jsonify({'error': 'Missing required params: boardName, since, until'}), 400

    try:
        boards = trello_get('https://api.trello.com/1/members/me/boards')
        board = next((b for b in boards if (b.get('name') or '').lower() == board_name.lower()), None)
        if not board:
            return jsonify({'error': f'Board not found: {board_name}'}), 404

        # Build Trello actions request
        params = {
            'limit': 1000,
            'since': since,
            'before': until,
        }
        if types and types.lower() != 'all':
            params['filter'] = types
        else:
            params['filter'] = 'all'

        actions = trello_get(f'https://api.trello.com/1/boards/{board.get("id")}/actions', params=params) or []

        # Normalize list names and target columns
        def norm(s):
            return (s or '').strip().lower()
        # Always include common aliases even when explicit names are provided
        base_in_progress = {'in progress', 'in-progress', 'doing'}
        base_completed = {'completed', 'complete', 'done'}
        target_in_progress = (base_in_progress | ({norm(in_progress_list)} if in_progress_list else set()))
        target_completed = (base_completed | ({norm(completed_list)} if completed_list else set()))

        def action_card_id(a):
            return ((a.get('data') or {}).get('card') or {}).get('id')

        def action_list_after(a):
            d = a.get('data') or {}
            return ((d.get('listAfter') or {}).get('name')) or ((d.get('list') or {}).get('name'))

        # Filter relevant actions: moved/created into target columns; comments with links; checklist complete; attachments added
        def is_move_or_create_into_target(a):
            t = (a.get('type') or '').strip()
            la = norm(action_list_after(a))
            return ((t == 'updateCard' and la in target_in_progress.union(target_completed)) or
                    (t == 'createCard' and la in target_in_progress.union(target_completed)) or
                    (t == 'copyCard' and la in target_in_progress.union(target_completed)) or
                    (t == 'moveCardToBoard' and la in target_in_progress.union(target_completed)))

        def is_comment_with_link(a):
            t = (a.get('type') or '').strip()
            txt = ((a.get('data') or {}).get('text') or '')
            return t == 'commentCard' and ('http://' in txt or 'https://' in txt)

        def is_checklist_complete(a):
            t = (a.get('type') or '').strip()
            d = (a.get('data') or {})
            state = ((d.get('checkItem') or {}).get('state') or '').strip().lower()
            return t == 'updateCheckItemStateOnCard' and state == 'complete'

        def is_attachment_added(a):
            t = (a.get('type') or '').strip()
            return t == 'addAttachmentToCard'

        # Build card -> target column map based on move/create/copy/add to target columns
        def column_key_from_action(a):
            name = action_list_after(a)
            n = norm(name)
            if n in target_in_progress:
                return 'In Progress'
            if n in target_completed:
                return 'Completed'
            return None

        card_target_map = {}
        for a in actions:
            if is_move_or_create_into_target(a):
                cid = action_card_id(a)
                col = column_key_from_action(a)
                if cid and col:
                    prev = card_target_map.get(cid)
                    # Prefer Completed when conflicting; otherwise use latest seen
                    if prev != 'Completed':
                        card_target_map[cid] = col

        # Now filter actions strictly to target cards; always include the qualifying move/create actions
        filtered = []
        for a in actions:
            if is_move_or_create_into_target(a):
                filtered.append(a)
                continue
            cid = action_card_id(a)
            if cid in card_target_map and (is_comment_with_link(a) or is_checklist_complete(a) or is_attachment_added(a)):
                filtered.append(a)

        # Group by target column and card
        # Build a map: { column_key: { cardId: { meta, actions: [] } } }
        groups_map = {}

        # Fetch minimal list map for board to resolve list names by id
        lists = trello_get(f'https://api.trello.com/1/boards/{board.get("id")}/lists')
        list_id_to_name = {l.get('id'): (l.get('name') or '') for l in (lists or [])}

        # Group strictly by target column using card_target_map

        # Cache for card metadata
        card_meta_cache = {}

        def get_card_meta(card_id):
            if not card_id:
                return None
            if card_id in card_meta_cache:
                return card_meta_cache[card_id]
            try:
                info = trello_get(
                    f'https://api.trello.com/1/cards/{card_id}',
                    params={
                        'fields': 'name,shortUrl,idList,labels',
                        'members': 'true',
                        'member_fields': 'fullName,username',
                        'checklists': 'all'
                    }
                )
                # Compute completion status
                total = 0
                completed = 0
                for cl in (info.get('checklists') or []):
                    for item in (cl.get('checkItems') or []):
                        total += 1
                        if (item.get('state') or '').strip().lower() == 'complete':
                            completed += 1
                owners = [{'fullName': m.get('fullName'), 'username': m.get('username')} for m in (info.get('members') or [])]
                labels = [{'name': lb.get('name'), 'color': lb.get('color')} for lb in (info.get('labels') or [])]
                meta = {
                    'cardId': card_id,
                    'name': info.get('name'),
                    'url': info.get('shortUrl'),
                    'listName': list_id_to_name.get(info.get('idList') or '') or '',
                    'owners': owners,
                    'labels': labels,
                    'completion': {'completed': completed, 'total': total}
                }
                card_meta_cache[card_id] = meta
                return meta
            except Exception:
                return None

        def pick_action(a):
            data = a.get('data') or {}
            card = data.get('card') or {}
            list_name = (data.get('list') or {}).get('name') or ((data.get('listAfter') or {}).get('name'))
            return {
                'date': a.get('date'),
                'type': a.get('type'),
                'member': (a.get('memberCreator') or {}).get('fullName'),
                'cardId': card.get('id'),
                'card': card.get('name'),
                'list': list_name,
                'text': data.get('text'),
                'attachment': (data.get('attachment') or {}),
                'checkItemName': ((data.get('checkItem') or {}).get('name'))
            }

        for a in filtered:
            cid_for_group = action_card_id(a)
            col_key = card_target_map.get(cid_for_group) or column_key_from_action(a)
            if col_key not in groups_map:
                groups_map[col_key] = {}
            pa = pick_action(a)
            cid = pa.get('cardId')
            if cid not in groups_map[col_key]:
                meta = get_card_meta(cid) or {'cardId': cid, 'name': pa.get('card'), 'url': '', 'owners': [], 'labels': [], 'completion': {'completed': 0, 'total': 0}}
                groups_map[col_key][cid] = { 'meta': meta, 'actions': [] }
            groups_map[col_key][cid]['actions'].append(pa)

        # Convert map to array
        result_groups = []
        for col, cards_map in groups_map.items():
            cards = []
            for _, entry in cards_map.items():
                cards.append({ **entry['meta'], 'actions': entry['actions'] })
            # Sort cards by name for stable output
            cards.sort(key=lambda x: (x.get('name') or '').lower())
            result_groups.append({ 'column': col, 'cards': cards })

        # Sort groups by desired order
        # Ensure only the two target columns are present and ordered
        order = {'In Progress': 0, 'Completed': 1}
        result_groups = [g for g in result_groups if g['column'] in order]
        result_groups.sort(key=lambda g: order.get(g['column'], 99))

        return jsonify({'groups': result_groups})
    except requests.HTTPError as e:
        return jsonify({'error': 'Trello HTTP error', 'details': str(e)}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Unexpected trello error', 'details': str(e)}), 500

@app.route('/api/openai/summarize', methods=['POST', 'OPTIONS'])
def openai_summarize():
    if request.method == 'OPTIONS':
        return make_response('', 204)
    try:
        data = request.get_json(force=True) or {}
        system_prompt = (data.get('systemPrompt') or '').strip()
        input_obj = data.get('input') or {}
        if not system_prompt:
            return jsonify({'error': 'Missing systemPrompt'}), 400
        api_key = os.getenv('OPENAI_API_KEY', '').strip()
        if not api_key:
            return jsonify({'error': 'Missing OPENAI_API_KEY'}), 400
        user_content = build_user_content(input_obj)
        body = {
            'model': 'gpt-4o-mini',
            'messages': [
                { 'role': 'system', 'content': system_prompt },
                { 'role': 'user', 'content': user_content }
            ],
            'temperature': 0.2,
        }
        r = requests.post('https://api.openai.com/v1/chat/completions', json=body, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }, timeout=60)
        if r.status_code >= 400:
            return jsonify({'error': f'OpenAI HTTP {r.status_code}', 'details': r.text}), r.status_code
        data = r.json()
        text = (((data.get('choices') or [{}])[0]).get('message') or {}).get('content') or ''
        return jsonify({'text': text})
    except Exception as e:
        return jsonify({'error': 'Unexpected openai error', 'details': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)