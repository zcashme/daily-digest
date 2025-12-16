import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# Constants
SGT_OFFSET = timedelta(hours=8)
MEMBER_ID = "6374510bf2aa0e0071120277"
LABEL_ID = "6924d2b9e964c12aa4cb9c9a"
TARGET_LIST_ID = "694006049b61581da80fcd5f"
BOARD_NAME = "Zcash Me"

def trello_get(url: str, qp: dict) -> dict:
    key = os.environ.get("TRELLO_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise RuntimeError("Missing TRELLO_KEY/TRELLO_TOKEN")
    qp = dict(qp or {})
    qp.update({"key": key, "token": token})
    full = url + "?" + urllib.parse.urlencode(qp)
    with urllib.request.urlopen(full, timeout=60) as r:
        return json.loads(r.read())

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

def get_sgt_time_range():
    # Current time in UTC (when script runs)
    now_utc = datetime.now(timezone.utc)
    # Convert to SGT
    now_sgt = now_utc + SGT_OFFSET
    
    # We want the window ending at 9:00 AM SGT today (or yesterday if running early?)
    # Assuming script runs at 9:00 AM SGT (01:00 UTC)
    
    # Target End: Today 9:00 AM SGT
    end_sgt = now_sgt.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # If script runs slightly after 9 AM, we still want the 9 AM anchor.
    # If script runs slightly before, we might want the *previous* 9 AM? 
    # Let's assume cron runs on time.
    
    start_sgt = end_sgt - timedelta(days=1)
    
    # Convert back to UTC for API
    start_utc = start_sgt - SGT_OFFSET
    end_utc = end_sgt - SGT_OFFSET
    
    return start_utc, end_utc, start_sgt, end_sgt

def summarize_actions(actions: list) -> dict:
    by_type = {}
    for a in actions:
        t = a.get("type") or "unknown"
        by_type[t] = by_type.get(t, 0) + 1

    def pick(a):
        data = a.get("data") or {}
        card = (data.get("card") or {}).get("name")
        text = data.get("text")
        list_name = (data.get("list") or {}).get("name") or (
            (data.get("listAfter") or {}).get("name")
        )
        return {
            "date": a.get("date"),
            "type": a.get("type"),
            "member": (a.get("memberCreator") or {}).get("fullName"),
            "card": card,
            "list": list_name,
            "text": text,
        }

    return {
        "total": len(actions),
        "byType": by_type,
        "sample": [pick(x) for x in actions[:10]],
    }

def main():
    start_utc, end_utc, start_sgt, end_sgt = get_sgt_time_range()
    
    since_iso = start_utc.isoformat().replace("+00:00", "Z")
    before_iso = end_utc.isoformat().replace("+00:00", "Z")
    
    print(f"Time Range (UTC): {since_iso} to {before_iso}")
    print(f"Time Range (SGT): {start_sgt} to {end_sgt}")

    # Fetch Board Data
    boards = trello_get("https://api.trello.com/1/members/me/boards", {"fields": "name"})
    board = next((b for b in boards if (b.get("name") or "") == BOARD_NAME), None)
    if not board:
        raise RuntimeError(f"Board not found: {BOARD_NAME}")

    bid = board.get("id")
    actions = trello_get(
        f"https://api.trello.com/1/boards/{bid}/actions",
        {"filter": "all", "limit": 1000, "since": since_iso, "before": before_iso},
    )

    summary = summarize_actions(actions)
    json_summary = json.dumps({"range": {"since": since_iso, "before": before_iso}, **summary}, indent=2)
    
    # Card Details
    # Title Format: YYYY-MM-DDTHH:MM am SGT to YYYY-MM-DDTHH:MM am SGT
    fmt = "%Y-%m-%dT%I:%M %p SGT"
    title_start = start_sgt.strftime(fmt).replace("PM", "pm").replace("AM", "am")
    title_end = end_sgt.strftime(fmt).replace("PM", "pm").replace("AM", "am")
    card_title = f"{title_start} to {title_end}"
    
    # Due Date: Today 1 PM SGT
    due_sgt = end_sgt.replace(hour=13, minute=0, second=0, microsecond=0)
    due_utc = due_sgt - SGT_OFFSET
    due_iso = due_utc.isoformat().replace("+00:00", "Z")
    
    card_desc = f"**Daily Digest (WDWDY)**\nRange (SGT): {start_sgt} to {end_sgt}\n\n```json\n{json_summary}\n```"
    
    try:
        trello_post("https://api.trello.com/1/cards", {
            "idList": TARGET_LIST_ID,
            "name": card_title,
            "desc": card_desc[:16000],
            "idMembers": [MEMBER_ID],
            "idLabels": [LABEL_ID],
            "due": due_iso
        })
        print(f"Successfully created card: {card_title}")
    except Exception as e:
        print(f"Failed to create card: {e}")

if __name__ == "__main__":
    main()
