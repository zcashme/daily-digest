import os
import sys
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
import argparse

# Add src to sys.path to import digest_core
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
try:
    from digest_core import fetch_trello_notes, fetch_org_commits, fetch_trello_actions, fetch_github_commits, load_env_file
except ImportError:
    # Fallback if running from root
    sys.path.append(os.path.join(os.getcwd(), 'src'))
    from digest_core import fetch_trello_notes, fetch_org_commits, fetch_trello_actions, fetch_github_commits, load_env_file

# Constants
SGT_OFFSET = timedelta(hours=8)
MEMBER_ID = "6374510bf2aa0e0071120277"
LABEL_ID = "6924d2b9e964c12aa4cb9c9a"
TARGET_LIST_ID = "694006049b61581da80fcd5f"
BOARD_NAME = "Zcash Me"
GITHUB_ORG = "zcashme"

def get_sgt_time_range():
    # Current time in UTC (when script runs)
    now_utc = datetime.now(timezone.utc)
    # Convert to SGT
    now_sgt = now_utc + SGT_OFFSET
    
    # Target End: Today 9:00 AM SGT
    end_sgt = now_sgt.replace(hour=9, minute=0, second=0, microsecond=0)
    
    start_sgt = end_sgt - timedelta(days=1)
    
    # Convert back to UTC for API
    start_utc = start_sgt - SGT_OFFSET
    end_utc = end_sgt - SGT_OFFSET
    
    return start_utc, end_utc, start_sgt, end_sgt

def trello_post_file(url: str, file_path: str, data: dict = None) -> dict:
    import requests
    key = os.environ.get("TRELLO_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise RuntimeError("Missing TRELLO_KEY/TRELLO_TOKEN")
    
    qp = {"key": key, "token": token}
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'text/markdown')}
        r = requests.post(url, params=qp, data=data, files=files, timeout=120)
        r.raise_for_status()
        return r.json()

def trello_post(url: str, data: dict) -> dict:
    key = os.environ.get("TRELLO_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise RuntimeError("Missing TRELLO_KEY/TRELLO_TOKEN")
    
    qp = {"key": key, "token": token}
    full = url + "?" + urllib.parse.urlencode(qp)
    
    req = urllib.request.Request(full, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print card content instead of posting to Trello")
    args = parser.parse_args()

    load_env_file()

    start_utc, end_utc, start_sgt, end_sgt = get_sgt_time_range()
    
    since_iso = start_utc.isoformat().replace("+00:00", "Z")
    before_iso = end_utc.isoformat().replace("+00:00", "Z")
    
    print(f"Time Range (UTC): {since_iso} to {before_iso}")
    print(f"Time Range (SGT): {start_sgt} to {end_sgt}")

    # 1. Fetch Meeting Notes (Transcripts)
    print("Fetching Meeting Notes...")
    try:
        notes = fetch_trello_notes(BOARD_NAME, "Meeting Notes", since_iso, before_iso)
    except Exception as e:
        print(f"Error fetching notes: {e}")
        notes = []

    # 2. Fetch GitHub Commits
    print("Fetching GitHub Commits...")
    commit_groups = []
    
    # Fetch from zcashme org
    try:
        org_groups = fetch_org_commits(GITHUB_ORG, since_iso, before_iso)
        if org_groups:
            commit_groups.extend(org_groups)
    except Exception as e:
        print(f"Error fetching org commits: {e}")
        
    # Fetch from ZcashUsersGroup/zcashme (User requested coverage)
    try:
        # Check if we already have it (unlikely if GITHUB_ORG is diff)
        zcashme_commits = fetch_github_commits("ZcashUsersGroup", "zcashme", "main", since_iso, before_iso)
        if zcashme_commits:
            commit_groups.append({
                'repo': 'zcashme',
                'url': 'https://github.com/ZcashUsersGroup/zcashme',
                'branch': 'main',
                'commits': zcashme_commits
            })
    except Exception as e:
        print(f"Error fetching ZcashUsersGroup/zcashme: {e}")

    # 3. Fetch Trello Activity
    print("Fetching Trello Activity...")
    try:
        activity_groups = fetch_trello_actions(BOARD_NAME, since_iso, before_iso, in_progress_list="In Progress", completed_list="Completed")
    except Exception as e:
        print(f"Error fetching activity: {e}")
        activity_groups = []

    # --- Generate Markdown Report ---
    
    date_lcd = start_sgt.strftime("%b %d")
    if start_sgt.month != end_sgt.month:
        date_lcd += f" - {end_sgt.strftime('%b %d')}"
    else:
        date_lcd += f"-{end_sgt.day}"
    
    # Title Format: Update to include Date Time Range as requested
    # User Request: "add date time range to the title"
    # Format: YYYY-MM-DDTHH:MM am SGT to YYYY-MM-DDTHH:MM am SGT
    fmt = "%Y-%m-%dT%I:%M %p SGT"
    title_start = start_sgt.strftime(fmt).replace("PM", "pm").replace("AM", "am")
    title_end = end_sgt.strftime(fmt).replace("PM", "pm").replace("AM", "am")
    card_title = f"{title_start} to {title_end}"
    
    # Report Header matches Title
    lines = []
    lines.append(f"# Daily Digest ({title_start} to {title_end})")
    lines.append("")
    
    # Transcripts
    if notes:
        lines.append("## Transcripts Summary")
        for n in notes:
            d = n.get('titleDate') or n.get('dateLastActivity') or ''
            lines.append(f"- {d} **{n.get('name')}** [link]({n.get('url')})")
            if n.get('desc'):
                lines.append(f"  > {n.get('desc').replace(chr(10), ' ')}")
        lines.append("")
    
    # Commits
    if commit_groups:
        lines.append("## GitHub Commits")
        for g in commit_groups:
            lines.append(f"### {g['repo']} ({g['branch']})")
            for c in g['commits']:
                msg = (c.get('message') or '').split('\n')[0]
                lines.append(f"- {c['date'][:10]} **{c.get('author')}**: {msg} [link]({c.get('url')})")
            lines.append("")
    
    # Activity
    if activity_groups:
        lines.append("## Trello Activity")
        for g in activity_groups:
            col = g.get('column')
            lines.append(f"### {col}")
            for card_entry in g.get('cards', []):
                lines.append(f"#### {card_entry.get('name')}")
                for a in card_entry.get('actions', []):
                    # - {date} · {member} · {type} · {text}
                    dt = (a.get('date') or '')[:10]
                    mem = a.get('member') or 'Unknown'
                    act_type = a.get('type')
                    txt = (a.get('text') or '').replace('\n', ' ')
                    lines.append(f"- {dt} · {mem} · {act_type} · {txt}")
            lines.append("")
            
    report_md = "\n".join(lines)
    
    # Trello Card Fields
    
    # Title Format: YYYY-MM-DDTHH:MM am SGT to YYYY-MM-DDTHH:MM am SGT (Retaining user's preferred title format from previous context if they want it, but they asked for "same stuff as weekly")
    # Weekly Title: "Weekly Digest: 2024-01-01 - 2024-01-07"
    # Let's match Weekly Digest Title format as requested.
    # Title is already set above
    # card_title = f"{title_start} to {title_end}"
    
    # Due Date: Today 1 PM SGT
    due_sgt = end_sgt.replace(hour=13, minute=0, second=0, microsecond=0)
    due_utc = due_sgt - SGT_OFFSET
    due_iso = due_utc.isoformat().replace("+00:00", "Z")
    
    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Title: {card_title}")
        print(f"Due:   {due_iso}")
        print(f"List:  {TARGET_LIST_ID}")
        print("--- Report Content ---")
        print(report_md)
        print("----------------------\n")
        return

    # Check for temporary file
    temp_filename = f"daily-digest-{start_sgt.strftime('%Y-%m-%d')}.md"
    
    # Create Card
    try:
        # Create card first with truncated desc
        card_data = trello_post("https://api.trello.com/1/cards", {
            "idList": TARGET_LIST_ID,
            "name": card_title,
            "desc": report_md[:16000],
            "idMembers": [MEMBER_ID],
            "idLabels": [LABEL_ID],
            "due": due_iso,
            "pos": "top"
        })
        print(f"Successfully created card: {card_title} ({card_data.get('id')})")
        
        # Write markdown to file
        with open(temp_filename, 'w', encoding='utf-8') as f:
            f.write(report_md)
            
        # Attach file
        try:
            print(f"Uploading attachment: {temp_filename}")
            trello_post_file(f"https://api.trello.com/1/cards/{card_data.get('id')}/attachments", temp_filename)
            print("Attachment uploaded successfully.")
        except Exception as att_err:
            print(f"Failed to upload attachment: {att_err}")
            
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
    except Exception as e:
        print(f"Failed to create card: {e}")

if __name__ == "__main__":
    main()
