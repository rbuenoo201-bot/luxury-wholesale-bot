"""
Flask webhook receiver for the Luxury Wholesale SMS bot.
Twilio sends POST requests here when a seller replies.
"""

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import negotiation_engine as engine

app = Flask(__name__)


@app.route("/sms", methods=["POST"])
def sms_webhook():
    from_phone   = request.form.get("From", "")
    message_body = request.form.get("Body", "").strip()

    print(f"[SMS IN] {from_phone}: {message_body}")

    reply_text = engine.handle_incoming_message(from_phone, message_body)

    resp = MessagingResponse()
    if reply_text:
        resp.message(reply_text)
    return Response(str(resp), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "bot": "luxury-wholesale"}, 200


if __name__ == "__main__":
    app.run(debug=False, port=5000)
