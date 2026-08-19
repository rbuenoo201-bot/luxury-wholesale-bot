import os

# Twilio — luxury wholesale dedicated number
TWILIO_ACCOUNT_SID  = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_PHONE   = os.environ["TWILIO_FROM_PHONE"]   # separate number for luxury
OWNER_PHONE         = os.environ["OWNER_PHONE"]         # +12244369323 — Rodrigo's cell

# Anthropic
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]

# Airtable — separate base for luxury leads
AIRTABLE_API_KEY    = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID    = os.environ["AIRTABLE_LUXURY_BASE_ID"]  # different from standard wholesale
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Luxury Leads")
