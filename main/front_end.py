"""
Streamlit Manager Dashboard — simple, manual refresh with flag toggle
--------------------------------------------------------------------
Local-first setup with a plain service-account file.

Firestore collection: `workerstatus`
Fields per document:
  ID (str) · role (str) · lastflagged (timestamp) · Review (str) · link (str)
  flag (bool) · action (str in {block,warn,accept} or empty)

Run locally:
1) pip install streamlit google-cloud-firestore google-auth
2) Download Firebase Admin SDK JSON -> save as firebase_key.json (or set GOOGLE_APPLICATION_CREDENTIALS)
3) streamlit run streamlit_manager_dashboard.py
"""

import os
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
from urllib.parse import urlparse
from streamlit_autorefresh import st_autorefresh

# --- Config ---
COLLECTION_NAME = os.getenv("CONTENTCHECK_COLLECTION", "workerstatus")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase_key.json")

# --- Firestore client ---
def get_db() -> firestore.Client:
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        st.stop()
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    return firestore.Client(credentials=creds, project=creds.project_id)


def fmt_ts(ts) -> str:
    if ts is None:
        return ""
    try:
        dt = ts.to_datetime() if hasattr(ts, "to_datetime") else ts
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def elapsed_str(ts) -> str:
    """Return human-friendly age like '(2 minutes ago)'."""
    if ts is None:
        return ""
    try:
        dt = ts.to_datetime() if hasattr(ts, "to_datetime") else ts
        now = datetime.now(dt.tzinfo) if getattr(dt, 'tzinfo', None) else datetime.now()
        delta = now - dt
        secs = int(max(delta.total_seconds(), 0))
        if secs < 60:
            n = secs
            unit = "second" if n == 1 else "seconds"
        elif secs < 3600:
            n = secs // 60
            unit = "minute" if n == 1 else "minutes"
        elif secs < 86400:
            n = secs // 3600
            unit = "hour" if n == 1 else "hours"
        else:
            n = secs // 86400
            unit = "day" if n == 1 else "days"
        return f"({n} {unit} ago)"
    except Exception:
        return ""


def fetch_rows(db: firestore.Client) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for d in db.collection(COLLECTION_NAME).stream():
        x = d.to_dict() or {}
        rows.append({
            "_id": d.id,
            "ID": x.get("ID", ""),
            "role": x.get("role", x.get("team role", "")),
            "last flagged": x.get("last flagged", x.get("last flagged")),
            "Review": x.get("Review", x.get("content review", "")),
            "link": x.get("link", ""),
            "flag": bool(x.get("flag", False)),
            "action": x.get("action", ""),
        })
    rows.sort(key=lambda r: r.get("last flagged") or datetime.fromtimestamp(0), reverse=True)
    return rows


def write_action(db: firestore.Client, doc_id: str, value: str) -> None:
    db.collection(COLLECTION_NAME).document(doc_id).update({
        "action": value,
        "flag": False,
        "action_timestamp": firestore.SERVER_TIMESTAMP,
    })


def toggle_flag_true(db: firestore.Client, doc_id: str) -> None:
    """Set flag True and copy action_timestamp into last flagged.
    If action_timestamp is missing, we also set both to SERVER_TIMESTAMP so they match.
    We write both variants: 'last flagged' and 'last flagged' for compatibility.
    """
    ref = db.collection(COLLECTION_NAME).document(doc_id)
    snap = ref.get()
    act_ts = None
    if snap.exists:
        data = snap.to_dict() or {}
        act_ts = data.get("action_timestamp")
    payload = {"flag": True}
    if act_ts is not None:
        payload.update({
            "last flagged": act_ts,
        })
    else:
        payload.update({
            "last flagged": firestore.SERVER_TIMESTAMP,
        })
    ref.update(payload)


# --- UI ---
st.set_page_config(page_title="Manager Dashboard", layout="wide")
st.title("Manager Dashboard")
st.caption(f"Team status collection: `{COLLECTION_NAME}` · Auto refresh (1s)")

COLLECTION_NAME = 'workerstatus'


try:
    db = get_db()
    rows = fetch_rows(db)
    if not rows:
        st.info(f"No documents found in collection '{COLLECTION_NAME}'.")
except Exception as e:
    st.error(f"Failed to read Firestore collection '{COLLECTION_NAME}': {e}")
    rows = []

st.subheader("Team status")
st.dataframe([
    {
        "ID": r["ID"],
        "role": r["role"],
        "last flagged": (fmt_ts(r["last flagged"]) + " " + elapsed_str(r["last flagged"])) .strip(),
        "flag": r["flag"],
        "action": r["action"],
        "link": r["link"] or "—",
        "review": (r["Review"] or "")[:60] + ("…" if len(r.get("Review", "")) > 60 else ""),
    }
    for r in rows
], use_container_width=True, hide_index=True)

st.divider()

if rows:
    r = rows[0]
    flagged = r['flag']
    if flagged:
        title = f"{r['ID']} ({r['role']}) has a ticket"
    else:
        title = f"All tickets resolved"
    with st.expander(title, expanded=flagged):
        if r["link"]:
            st.markdown(f"[Open link]({r['link']})")
        st.write(f"**Review:** {r['Review'] or '—'}")
        st.write(f"**Last action:** {r['action'] or '—'}")

        if r["flag"]:
            choice = st.radio("Action", ["block", "warn", "accept"], key=f"act_{r['_id']}", horizontal=True)
            if st.button("Submit", key=f"submit_{r['_id']}"):
                write_action(db, r["_id"], choice)
                st.success(f"Saved '{choice}' and reset flag.")
                st.rerun()
        else:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.caption("Flag is False.")
            with c2:
                if st.button("Set Flag True", key=f"flag_{r['_id']}"):
                    toggle_flag_true(db, r["_id"])
                    st.success("Flag set to True.")
                    st.rerun()

# --- seed categories + starter block list ---
DEFAULT_BLOCKS = {
    "Gambling": [
        "https://www.bet365.com",
        "https://www.draftkings.com",
        "https://www.fanduel.com",
    ],
    "Adult Content": [
        "https://www.pornhub.com",
        "https://www.xvideos.com",
        "https://www.xnxx.com",
    ],
    "Social Media": [
        "https://www.facebook.com",
        "https://www.instagram.com",
        "https://www.tiktok.com",
        "https://www.snapchat.com",
        "https://www.reddit.com",
        "https://www.x.com",
        "https://www.twitter.com",
    ],
    "Shopping": [
        "https://www.amazon.com",
        "https://www.ebay.com",
        "https://www.alibaba.com",
        "https://www.shein.com",
        "https://www.temu.com",
    ],
}

if "block_lists" not in st.session_state:
    # deep copy the defaults
    st.session_state.block_lists = {k: list(v) for k, v in DEFAULT_BLOCKS.items()}

CATEGORIES = list(st.session_state.block_lists.keys())

def normalize_url(u: str) -> str:
    """Force scheme, lowercase host, strip trailing slash."""
    if not u.strip():
        return ""
    u = u.strip()
    if "://" not in u:
        u = "https://" + u
    try:
        p = urlparse(u)
        # ensure we at least have a hostname
        if not p.netloc:
            return ""
        host = p.netloc.lower()
        path = (p.path or "").rstrip("/")
        norm = f"{p.scheme}://{host}{path}"
        return norm
    except Exception:
        return ""

def already_exists(url: str) -> bool:
    for urls in st.session_state.block_lists.values():
        if url in urls:
            return True
    return False

with st.expander("🧱 Block list", expanded=True):
    st.caption("Append and categorize domains/URLs that should be blocked.")

    # --- Add new entry ---
    with st.form("add_block_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            new_url = st.text_input("URL or domain", placeholder="e.g. youtube.com or https://youtube.com")
        with col2:
            tag = st.selectbox("Category", CATEGORIES, index=2)  # default to Social Media
        with col3:
            submitted = st.form_submit_button("Add")
        if submitted:
            norm = normalize_url(new_url)
            if not norm:
                st.error("Enter a valid URL or domain.")
            elif already_exists(norm):
                st.warning("That URL is already in the block list.")
            else:
                st.session_state.block_lists[tag].append(norm)
                st.success(f"Added to {tag}: {norm}")

    st.divider()

    # --- Manage by category (tabs) ---
    tabs = st.tabs([f"{c} ({len(st.session_state.block_lists[c])})" for c in CATEGORIES])

    for i, cat in enumerate(CATEGORIES):
        with tabs[i]:
            urls = st.session_state.block_lists[cat]

            if urls:
                # Allow quick removals
                for j, u in enumerate(list(urls)):
                    cols = st.columns([6, 1])
                    cols[0].write(u)
                    if cols[1].button("Remove", key=f"rm_{cat}_{j}"):
                        st.session_state.block_lists[cat].remove(u)
                        st.toast(f"Removed from {cat}: {u}")
                        st.rerun()
            else:
                st.info("No entries yet.")

            # Move items to another category (optional small control)
            if st.toggle("Show bulk move tools", key=f"mv_toggle_{cat}", value=False):
                if urls:
                    pick = st.multiselect("Select URLs to move", urls, key=f"mv_select_{cat}")
                    target = st.selectbox("Move to category", [c for c in CATEGORIES if c != cat], key=f"mv_target_{cat}")
                    if st.button("Move selected", key=f"mv_btn_{cat}") and pick:
                        for u in pick:
                            st.session_state.block_lists[cat].remove(u)
                            if u not in st.session_state.block_lists[target]:
                                st.session_state.block_lists[target].append(u)
                        st.success(f"Moved {len(pick)} item(s) to {target}")
                        st.rerun()

    st.divider()

    # --- Utilities ---
    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        if st.button("Reset to defaults"):
            st.session_state.block_lists = {k: list(v) for k, v in DEFAULT_BLOCKS.items()}
            st.success("Restored default block lists.")
            st.rerun()
    with colB:
        if st.download_button(
            "Export JSON",
            data=__import__("json").dumps(st.session_state.block_lists, indent=2),
            file_name="block_lists.json",
            mime="application/json",
        ):
            pass
    with colC:
        uploaded = st.file_uploader("Import JSON (overwrites current lists)", type=["json"])
        if uploaded is not None:
            try:
                import json
                data = json.loads(uploaded.read().decode("utf-8"))
                # basic shape check
                assert isinstance(data, dict) and all(isinstance(v, list) for v in data.values())
                # ensure all known categories exist
                for c in CATEGORIES:
                    data.setdefault(c, [])
                st.session_state.block_lists = {k: list(set(map(normalize_url, v))) for k, v in data.items()}
                st.success("Imported block lists.")
                st.rerun()
            except Exception:
                st.error("Invalid JSON format.")

# --- Utilities / Admin actions ---
st.subheader("Team Controls")
col_admin1, col_admin2 = st.columns([2, 3])
with col_admin1:
    new_id = st.text_input("New person in the team?", value="workerstatus2", help="The ID is required")
    if st.button("Add"):
        try:
            col = db.collection(COLLECTION_NAME)
            src_ref = col.document("workerstatus")
            src_snap = src_ref.get()
            if not src_snap.exists:
                raise ValueError(f"Source document 'workerstatus' not found in '{COLLECTION_NAME}'.")
            data = src_snap.to_dict() or {}
            col.document(new_id.strip()).set(data)
            st.rerun()
        except Exception as e:
            st.error(f"Duplicate failed: {e}")

st.divider()

enable_auto = st.checkbox("Auto refresh", value=True)
interval_sec = st.number_input("Interval (sec)", min_value=2, max_value=3600, value=5, step=1)
st.button("Manually Refresh")
if enable_auto:
    _ = st_autorefresh(interval=int(interval_sec * 1000), limit=None, debounce=True, key="auto_refresher")