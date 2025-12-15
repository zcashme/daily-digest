import os
import requests
import re
from datetime import datetime

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
        pass

def fetch_github_commits(owner, repo, branch, since, until):
    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {
        'Accept': 'application/vnd.github+json',
        **({ 'Authorization': f'Bearer {token}' } if token else {})
    }
    commits = []
    page = 1
    while page < 10:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&since={since}&until={until}&per_page=100&page={page}"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code >= 400:
            break
        batch = r.json()
        commits.extend(batch)
        if len(batch) < 100:
            break
        page += 1

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
    return normalized

def fetch_org_commits(org, since, until, repos_filter=None, max_repos=50):
    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {
        'Accept': 'application/vnd.github+json',
        **({ 'Authorization': f'Bearer {token}' } if token else {})
    }
    
    # List repos
    repos = []
    page = 1
    while len(repos) < max_repos and page < 10:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}&type=all&sort=updated"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code >= 400:
            break
        batch = r.json() or []
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

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

    groups = []
    for repo in selected:
        commits = fetch_github_commits(org, repo['name'], repo['default_branch'], since, until)
        if commits:
            groups.append({
                'repo': repo['name'],
                'url': repo['html_url'],
                'branch': repo['default_branch'],
                'commits': commits
            })
    return groups

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

def trello_post(url, data=None, params=None):
    key = os.getenv('TRELLO_KEY', '').strip()
    token = os.getenv('TRELLO_TOKEN', '').strip()
    if not key or not token:
        raise ValueError('Missing TRELLO_KEY/TRELLO_TOKEN')
    params = params or {}
    params.update({'key': key, 'token': token})
    r = requests.post(url, json=data, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_trello_notes(board_name, list_name, since, until):
    boards = trello_get('https://api.trello.com/1/members/me/boards')
    board = next((b for b in boards if (b.get('name') or '').lower() == board_name.lower()), None)
    if not board:
        raise ValueError(f'Board not found: {board_name}')
    
    lists = trello_get(f'https://api.trello.com/1/boards/{board.get("id")}/lists')
    lst = next((l for l in lists if (l.get('name') or '').lower() == list_name.lower()), None)
    if not lst:
        raise ValueError(f'List not found: {list_name}')
        
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
        m = re.search(r'(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})', s)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return f"{y:04d}-{mo:02d}-{d:02d}"
            except Exception:
                pass
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
        title_date = parse_title_date(c.get('name') or '', fallback_year)
        if title_date:
            if not (since_date <= title_date <= until_date):
                continue
        else:
            act_str = c.get('dateLastActivity') or c.get('date') or ''
            try:
                act_ts = datetime.fromisoformat(act_str.replace('Z', '+00:00')).timestamp()
            except Exception:
                act_ts = 0
            if not act_ts or act_ts < since_t or act_ts > until_t:
                continue
                
        results.append({
            'cardId': c.get('id'),
            'name': c.get('name'),
            'url': c.get('shortUrl'),
            'dateLastActivity': to_utc_iso(c.get('dateLastActivity') or ''),
            'titleDate': title_date,
            'desc': c.get('desc') or ''
        })
    return results

def fetch_trello_actions(board_name, since, until, types=None, in_progress_list=None, completed_list=None):
    boards = trello_get('https://api.trello.com/1/members/me/boards')
    board = next((b for b in boards if (b.get('name') or '').lower() == board_name.lower()), None)
    if not board:
        raise ValueError(f'Board not found: {board_name}')

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

    def norm(s):
        return (s or '').strip().lower()
    
    base_in_progress = {'in progress', 'in-progress', 'doing'}
    base_completed = {'completed', 'complete', 'done'}
    target_in_progress = (base_in_progress | ({norm(in_progress_list)} if in_progress_list else set()))
    target_completed = (base_completed | ({norm(completed_list)} if completed_list else set()))

    def action_card_id(a):
        return ((a.get('data') or {}).get('card') or {}).get('id')

    def action_list_after(a):
        d = a.get('data') or {}
        return ((d.get('listAfter') or {}).get('name')) or ((d.get('list') or {}).get('name'))

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
                if prev != 'Completed':
                    card_target_map[cid] = col

    filtered = []
    for a in actions:
        if is_move_or_create_into_target(a):
            filtered.append(a)
            continue
        cid = action_card_id(a)
        if cid in card_target_map and (is_comment_with_link(a) or is_checklist_complete(a) or is_attachment_added(a)):
            filtered.append(a)

    groups_map = {}
    
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
            groups_map[col_key][cid] = { 'name': pa.get('card'), 'actions': [] }
        groups_map[col_key][cid]['actions'].append(pa)

    result_groups = []
    for col, cards_map in groups_map.items():
        cards = []
        for _, entry in cards_map.items():
            cards.append(entry)
        cards.sort(key=lambda x: (x.get('name') or '').lower())
        result_groups.append({ 'column': col, 'cards': cards })

    order = {'In Progress': 0, 'Completed': 1}
    result_groups = [g for g in result_groups if g['column'] in order]
    result_groups.sort(key=lambda g: order.get(g['column'], 99))

    return result_groups
