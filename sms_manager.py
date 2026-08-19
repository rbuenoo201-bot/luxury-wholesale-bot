"""
SMS manager for the Luxury Wholesale bot.

Tone is professional and refined — no "quick close / no hassle" language.
We're representing a private developer network, not a cash-buyer operation.
"""

import random
from twilio.rest import Client
import config

_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

# ── Outreach templates ─────────────────────────────────────────────────────────
# Goal: intrigue, not pressure. Reference land/development, not "cash offer."
# No opt-out disclaimers, no corporate language.

INITIAL_TEMPLATES = [
    "Hi {first_name}, my name is Rodrigo. I work with a private group of developers "
    "who are actively looking for properties in {city} with strong land value — "
    "particularly older homes on larger lots. Would you be open to a brief, confidential "
    "conversation about your property at {address}?",

    "Hello {first_name}, I'm Rodrigo — I represent a network of developers and builders "
    "focused on the {city} area. Your property at {address} caught our attention for a "
    "potential development opportunity. Is this something you'd be open to discussing?",

    "Hi {first_name}, this is Rodrigo. Our development group has been quietly acquiring "
    "select properties in {city} and I believe {address} may be a strong fit. "
    "Would you have a few minutes to connect?",
]

FOLLOW_UP_1_TEMPLATES = [
    "Hi {first_name}, just following up on my earlier message about {address}. "
    "I understand timing matters — if you'd ever consider your options, "
    "I'd love to have a private conversation. No pressure either way.",

    "Hello {first_name}, Rodrigo again. Still interested in {address} if the timing "
    "ever makes sense for you. Happy to answer any questions confidentially.",
]

FOLLOW_UP_2_TEMPLATES = [
    "Hi {first_name} — one final note from me about {address}. "
    "If you ever reconsider or want to explore your options, feel free to reach back out. "
    "Wishing you well.",

    "Hello {first_name}, last message from me regarding {address}. "
    "If circumstances change, I'm happy to reconnect. "
    "Take care and have a great day.",
]


def _pick(templates: list, **kwargs) -> str:
    return random.choice(templates).format(**kwargs)


def send_initial(to_phone: str, first_name: str, address: str, city: str = "your area") -> str:
    body = _pick(INITIAL_TEMPLATES, first_name=first_name, address=address, city=city)
    _client.messages.create(to=to_phone, from_=config.TWILIO_FROM_PHONE, body=body)
    return body


def send_follow_up_1(to_phone: str, first_name: str, address: str) -> str:
    body = _pick(FOLLOW_UP_1_TEMPLATES, first_name=first_name, address=address)
    _client.messages.create(to=to_phone, from_=config.TWILIO_FROM_PHONE, body=body)
    return body


def send_follow_up_2(to_phone: str, first_name: str, address: str) -> str:
    body = _pick(FOLLOW_UP_2_TEMPLATES, first_name=first_name, address=address)
    _client.messages.create(to=to_phone, from_=config.TWILIO_FROM_PHONE, body=body)
    return body


def send_reply(to_phone: str, body: str):
    _client.messages.create(to=to_phone, from_=config.TWILIO_FROM_PHONE, body=body)


def notify_owner(message: str):
    """Send an alert to Rodrigo's personal number."""
    _client.messages.create(
        to=config.OWNER_PHONE,
        from_=config.TWILIO_FROM_PHONE,
        body=message,
    )
