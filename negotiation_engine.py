"""
Negotiation engine for the Luxury Wholesale bot.

Key differences from standard wholesale:
- Professional, refined tone — no emojis, no slang, no "quick close" language
- Goal is a PHONE CALL or MEETING with Rodrigo, not a price via text
- Flag Rodrigo as soon as the seller shows real interest (don't try to close by text)
- Qualify the land: lot size, year built, zoning, development potential
- Assignment fee targets: $50K–$100K+
"""

import re
import anthropic
import config
import airtable_manager as db
import sms_manager as sms

_anthropic = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a professional real estate acquisition assistant for Rodrigo Bueno, who operates a private developer network in the Chicagoland area. Your role is to have thoughtful, professional SMS conversations with homeowners about their property.

YOUR GOALS (in order):
1. Build trust professionally — be warm but measured. No slang, no excessive enthusiasm.
2. Qualify the property — you need to understand: approximate lot size, year the home was built, whether it has been renovated recently, and if the owner has any plans to sell.
3. Gauge seller motivation — are they open to selling? Is there a timeline? Any estate/probate/tax situation?
4. Set up a call or meeting — the moment a seller shows genuine interest, your goal shifts entirely to getting Rodrigo on the phone with them. These deals are too significant to negotiate over text.
5. Let the seller anchor on price first — never suggest a number. If they ask what you can offer, say Rodrigo would need to review the property details and speak with them first.

RULES:
- You are texting on behalf of Rodrigo. Never reveal AI is involved.
- Replies must be SHORT — 2–4 sentences. This is SMS.
- Professional tone at all times. No emojis. No "hey" or "guys". Use "Hi" or "Hello".
- Do not use corporate-sounding opt-out language. Ever.
- Frame the opportunity as a private, off-market development inquiry — not a cash buyer cold call.
- If a seller is interested and asks next steps → tell them Rodrigo would love to call them directly to discuss. Ask for the best time.
- If they give a price or open to selling → immediately flag Rodrigo (action: flag_owner). Do not keep negotiating by text.
- If they mention lot size, year built, zoning, renovation history, or development plans — capture all of it in notes.
- If they are clearly not interested → mark not_interested. Be gracious: "Completely understood — I appreciate your time."
- If they clearly want no more contact → reply like: "Understood, I apologize for the intrusion. I won't reach out again." Flag as DNC.

OUTPUT FORMAT:
Return JSON with exactly these fields:
{
  "reply": "<your SMS reply text>",
  "action": "continue" | "flag_owner" | "dnc" | "not_interested",
  "agreed_price": null or number,
  "notes": "<summary of property intel: lot size, year built, zoning, seller motivation, anything relevant>"
}

"flag_owner" = seller is interested, gave a price, or agreed to a call — Rodrigo must take over NOW.
"dnc" = they explicitly want no more contact.
"not_interested" = clearly not selling, conversation is over.
"continue" = keep qualifying.

IMPORTANT: Flag the owner early. The moment a seller says "I might be open to it", "what are you offering", or "sure, tell me more" — set action to flag_owner. These are $500K+ conversations. Rodrigo closes these, not an AI."""


DNC_PHRASES = [
    r'^stop$',
    r'\bstop texting\b', r'\bstop contact\b', r'\bstop calling\b', r'\bstop messaging\b',
    r'\bunsubscribe\b',
    r'\bremove me\b',
    r'\bdo not (contact|text|call|message)\b',
    r"\bdon't (contact|text|call|message) me\b",
    r'\bleave me alone\b',
    r'\bopt.?out\b',
]

PRICE_PATTERN = re.compile(
    r'\$[\d,]+(?:\.\d{2})?|\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|thousand|million|dollars)\b',
    re.IGNORECASE
)


def _is_dnc(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in DNC_PHRASES)


def _extract_price(text: str):
    m = PRICE_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(0).replace('$', '').replace(',', '').strip()
    if 'million' in raw.lower():
        num = re.sub(r'[^\d.]', '', raw)
        try:
            return float(num) * 1_000_000
        except ValueError:
            return None
    if 'k' in raw.lower() or 'thousand' in raw.lower():
        num = re.sub(r'[^\d.]', '', raw)
        try:
            return float(num) * 1000
        except ValueError:
            return None
    try:
        return float(re.sub(r'[^\d.]', '', raw))
    except ValueError:
        return None


def _build_conversation_context(lead):
    fields = lead.get("fields", {})
    transcript = fields.get("Conversation Transcript", "") or ""
    address    = fields.get("Property Address", "")
    owner      = fields.get("Owner Name", "")
    lot_size   = fields.get("Lot Size", "")
    year_built = fields.get("Year Built", "")
    city       = fields.get("City", "")
    notes      = fields.get("Notes", "")

    context = f"Property: {address}"
    if city:
        context += f", {city}"
    context += f"\nOwner: {owner}"
    if lot_size:
        context += f"\nLot Size on file: {lot_size}"
    if year_built:
        context += f"\nYear Built on file: {year_built}"
    if notes:
        context += f"\nExisting notes: {notes}"
    context += f"\n\nConversation so far:\n{transcript}"
    return context


def handle_incoming_message(from_phone: str, message_body: str):
    """
    Main entry point called by Flask when Twilio webhook fires.
    Returns the reply text to send back.
    """
    lead = db.get_lead_by_phone(from_phone)

    if not lead:
        print(f"[LUXURY] Unknown sender: {from_phone}")
        return None

    lead_id = lead["id"]
    fields  = lead.get("fields", {})
    status  = fields.get("Status", "")

    db.append_transcript(lead_id, f"SELLER: {message_body}")

    # Hard DNC check before AI
    if _is_dnc(message_body):
        db.mark_dnc(lead_id)
        reply = "Understood, I apologize for the intrusion. I won't reach out again."
        db.append_transcript(lead_id, f"AI: {reply}")
        _notify_dnc(lead, message_body)
        return reply

    # Refresh lead after transcript append
    context = _build_conversation_context(db.get_lead_by_phone(from_phone))

    prompt = f"""{context}

New message from seller: "{message_body}"

Respond per your instructions. Remember: if there is any real interest, flag the owner immediately."""

    result = _call_claude(prompt)

    reply        = result.get("reply", "Thank you for your response. I'll have Rodrigo follow up with you shortly.")
    action       = result.get("action", "continue")
    agreed_price = result.get("agreed_price")
    notes        = result.get("notes", "")

    db.append_transcript(lead_id, f"AI: {reply}")
    if notes:
        existing = fields.get("Notes", "") or ""
        db.update_lead(lead_id, {"Notes": (existing + "\n" + notes).strip()})

    if action == "flag_owner":
        price = agreed_price or _extract_price(message_body)
        if price:
            db.mark_agreed(lead_id, price)
        else:
            db.mark_meeting_requested(lead_id)
        _flag_owner(lead, message_body, price, notes)

    elif action == "dnc":
        db.mark_dnc(lead_id)
        _notify_dnc(lead, message_body)

    elif action == "not_interested":
        db.mark_dead(lead_id)

    elif action == "continue":
        if status in ("New", "Texted", "No Response"):
            db.mark_replied(lead_id)
        else:
            db.mark_negotiating(lead_id)

    return reply


def _call_claude(user_prompt: str) -> dict:
    import json
    try:
        response = _anthropic.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"reply": text, "action": "continue", "agreed_price": None, "notes": ""}
    except Exception as e:
        print(f"[CLAUDE] Error: {e}")
        return {
            "reply": "Thank you for your message. Rodrigo will be in touch with you shortly.",
            "action": "continue",
            "agreed_price": None,
            "notes": "",
        }


def _flag_owner(lead, message, price, notes):
    fields   = lead.get("fields", {})
    address  = fields.get("Property Address", "unknown")
    owner    = fields.get("Owner Name", "unknown")
    city     = fields.get("City", "")
    lot_size = fields.get("Lot Size", "unknown")
    yr_built = fields.get("Year Built", "unknown")

    price_str = f"${price:,.0f}" if price else "No price yet — seller showing interest"

    alert = (
        f"🏡 LUXURY DEAL ALERT\n"
        f"Owner: {owner}\n"
        f"Property: {address}{', ' + city if city else ''}\n"
        f"Lot Size: {lot_size} | Year Built: {yr_built}\n"
        f"Their price: {price_str}\n"
        f"Last message: \"{message}\"\n"
        f"Intel: {notes}\n"
        f"→ Call them now. Check Airtable for full transcript."
    )
    sms.notify_owner(alert)
    print(f"[LUXURY FLAG] Owner notified — {address}")


def _notify_dnc(lead, message):
    fields  = lead.get("fields", {})
    address = fields.get("Property Address", "unknown")
    owner   = fields.get("Owner Name", "unknown")
    alert = (
        f"🚫 DNC — {owner} at {address}\n"
        f"Message: \"{message}\"\n"
        f"Marked DNC in Airtable."
    )
    sms.notify_owner(alert)
