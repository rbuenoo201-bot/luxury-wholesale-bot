"""
Airtable manager for the Luxury Wholesale bot.
Fields differ from the standard wholesale base — includes lot size, year built,
zoning, estimated land value, and assignment fee target.
"""

import requests
import config

HEADERS = {
    "Authorization": f"Bearer {config.AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://api.airtable.com/v0/{config.AIRTABLE_BASE_ID}/{config.AIRTABLE_TABLE_NAME}"


def _get(params=None):
    r = requests.get(BASE_URL, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def _patch(record_id, fields):
    r = requests.patch(
        f"{BASE_URL}/{record_id}",
        headers=HEADERS,
        json={"fields": fields},
    )
    r.raise_for_status()
    return r.json()


# ── Read ──────────────────────────────────────────────────────────────────────

def get_lead_by_phone(phone: str):
    """Return the Airtable record whose Owner Phone matches, or None."""
    data = _get(params={"filterByFormula": f"{{Owner Phone}}='{phone}'"})
    records = data.get("records", [])
    return records[0] if records else None


def get_all_leads():
    records = []
    offset = None
    while True:
        params = {}
        if offset:
            params["offset"] = offset
        data = _get(params=params)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


# ── Write ─────────────────────────────────────────────────────────────────────

def append_transcript(record_id: str, line: str):
    record = requests.get(f"{BASE_URL}/{record_id}", headers=HEADERS).json()
    existing = record.get("fields", {}).get("Conversation Transcript", "") or ""
    updated = (existing + "\n" + line).strip()
    _patch(record_id, {"Conversation Transcript": updated})


def update_lead(record_id: str, fields: dict):
    _patch(record_id, fields)


def mark_replied(record_id: str):
    _patch(record_id, {"Status": "Replied"})


def mark_negotiating(record_id: str):
    _patch(record_id, {"Status": "Negotiating"})


def mark_agreed(record_id: str, price: float):
    _patch(record_id, {"Status": "Agreed", "Agreed Price": price})


def mark_dnc(record_id: str):
    _patch(record_id, {"Status": "DNC"})


def mark_dead(record_id: str):
    _patch(record_id, {"Status": "Not Interested"})


def mark_meeting_requested(record_id: str):
    """Seller agreed to a call/meeting — Rodrigo needs to take over immediately."""
    _patch(record_id, {"Status": "Meeting Requested"})
