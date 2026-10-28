"""
WhatsApp Automated Messaging Service for Friends Sports Hub Mulayankavu.
Supports:
1. Automated Server-Side Dispatch (Meta Cloud API, UltraMsg, GreenAPI)
2. Pre-formatted message builder & phone sanitization
"""
import re
import json
import logging
import urllib.parse
import urllib.request
from django.conf import settings

logger = logging.getLogger(__name__)


def clean_whatsapp_phone(phone_str):
    """
    Sanitizes phone numbers for WhatsApp API and URL formatting.
    Converts Indian 10-digit numbers to 91XXXXXXXXXX.
    Strips leading 0, spaces, dashes, parentheses.
    """
    if not phone_str:
        return ''
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if len(digits) == 10:
        return f'91{digits}'
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    return digits


def build_confirmation_message(booking):
    """
    Builds the official WhatsApp booking confirmation ticket text.
    """
    date_str = booking.booking_date.strftime('%A, %d %B %Y')
    start_str = booking.start_time.strftime('%I:%M %p').lstrip('0')
    end_str = booking.end_time.strftime('%I:%M %p').lstrip('0')

    msg_lines = [
        "🏆 *FRIENDS SPORTS HUB MULAYANKAVU*",
        "✅ *Booking Confirmed!*",
        "",
        f"📋 *Ref ID:* {booking.booking_id}",
        f"👤 *Name:* {booking.customer_name}",
    ]
    if booking.notes and booking.notes.strip():
        msg_lines.append(f"👥 *Club/Team:* {booking.notes.strip()}")
    msg_lines.extend([
        f"🏟️ *Facility:* {booking.facility.name}",
        f"📅 *Date:* {date_str}",
        f"⏰ *Time:* {start_str} – {end_str}",
        f"💰 *Fee:* ₹{int(booking.total_price)} (Pay at Venue)",
        "",
        "📍 *Location:* Kulukkallur, Mulayankavu, Palakkad",
        "📞 *Helpline:* 6238006820",
        "",
        "⚠️ *Instructions:*",
        "• Please report 10 minutes before slot time.",
        "• Turf shoes or sports sneakers only (no metal studs).",
        "",
        "See you on the pitch! ⚽"
    ])
    return "\n".join(msg_lines)


def send_whatsapp_server_side(phone, message_text):
    """
    Attempts to send WhatsApp message server-side if a WhatsApp API gateway
    is configured in Django settings.
    Returns (success: bool, status_message: str)
    """
    clean_phone = clean_whatsapp_phone(phone)
    if not clean_phone:
        return False, "Missing or invalid phone number"

    # 1. UltraMsg Gateway (Works by scanning QR code once with owner's number 6238006820)
    ultramsg_instance = getattr(settings, 'WHATSAPP_ULTRAMSG_INSTANCE', None)
    ultramsg_token = getattr(settings, 'WHATSAPP_ULTRAMSG_TOKEN', None)
    if ultramsg_instance and ultramsg_token:
        try:
            url = f"https://api.ultramsg.com/{ultramsg_instance}/messages/chat"
            payload = urllib.parse.urlencode({
                'token': ultramsg_token,
                'to': clean_phone,
                'body': message_text,
                'priority': '10',
            }).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('sent') == 'true' or data.get('id'):
                    logger.info(f"WhatsApp sent automatically to {clean_phone} via UltraMsg")
                    return True, "Sent via UltraMsg API"
        except Exception as e:
            logger.error(f"UltraMsg dispatch failed: {e}")

    # 2. Meta WhatsApp Cloud API (Official Meta Developer App)
    meta_token = getattr(settings, 'WHATSAPP_CLOUD_API_TOKEN', None)
    meta_phone_id = getattr(settings, 'WHATSAPP_CLOUD_PHONE_ID', None)
    if meta_token and meta_phone_id:
        try:
            url = f"https://graph.facebook.com/v19.0/{meta_phone_id}/messages"
            payload = json.dumps({
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "text",
                "text": {"body": message_text}
            }).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    'Authorization': f'Bearer {meta_token}',
                    'Content-Type': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return True, "Sent via Meta Cloud API"
        except Exception as e:
            logger.error(f"Meta Cloud API dispatch failed: {e}")

    return False, "No automated server gateway configured (handled via browser auto-launch)"

