import json
import logging
from fastapi import APIRouter, Request, Response, Header, Query, HTTPException, status
from app.config import settings
from app.database import redis_client, AsyncSessionLocal
from app.models.schema import User, Device
from app.services.whatsapp_service import whatsapp_service
from app.services.analytics_service import analytics_service
from sqlalchemy import select

logger = logging.getLogger("WhatsAppWebhook")
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Meta Cloud API Webhook Handshake Verification.
    """
    logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verification challenge successful!")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    logger.warning("Webhook verification token mismatch or invalid mode.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")

@router.post("/webhook")
async def receive_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    """
    Handles incoming user messages, status receipts, and conversational inquiries.
    """
    raw_body = await request.body()

    # Validate HMAC signature
    if settings.WHATSAPP_APP_SECRET and settings.WHATSAPP_APP_SECRET != "meta_app_secret_hex":
        if not whatsapp_service.verify_webhook_signature(raw_body, x_hub_signature_256):
            logger.warning("Rejected webhook due to invalid HMAC SHA256 signature!")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to decode webhook JSON: {e}")
        return {"status": "ignored"}

    # Extract entry items
    entry_list = payload.get("entry", [])
    for entry in entry_list:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                sender_phone = msg.get("from")
                msg_type = msg.get("type")

                if msg_type == "text":
                    text_body = msg.get("text", {}).get("body", "")
                    logger.info(f"Received WhatsApp message from +{sender_phone}: '{text_body}'")

                    # Look up user & associated device
                    normalized_phone = "+" + sender_phone if not sender_phone.startswith("+") else sender_phone
                    device_id = None
                    device_meta = None

                    async with AsyncSessionLocal() as session:
                        stmt = select(User, Device).outerjoin(Device, Device.user_id == User.id).where(
                            (User.phone_number == normalized_phone) | 
                            (User.phone_number == sender_phone) |
                            (User.phone_number.like(f"%{sender_phone[-10:]}"))
                        )
                        res = await session.execute(stmt)
                        row = res.first()
                        if row:
                            usr, dev = row
                            if dev:
                                device_id = dev.device_id
                                device_meta = {
                                    "site_name": dev.site_name,
                                    "battery_type": dev.battery_type,
                                    "battery_capacity_wh": dev.battery_capacity_wh
                                }

                    # Fallback device if testing
                    if not device_id:
                        device_id = "NG-INV-00124"
                        device_meta = {
                            "site_name": "Demo Lekki Solar System",
                            "battery_type": "LiFePO4 (48V 200Ah)",
                            "battery_capacity_wh": 10000.0
                        }

                    # Fetch real-time telemetry from Redis
                    latest_telemetry = None
                    raw_telemetry = await redis_client.get(f"device:{device_id}:latest")
                    if raw_telemetry:
                        try:
                            latest_telemetry = json.loads(raw_telemetry)
                        except Exception:
                            pass

                    # Fetch savings analytics
                    analytics_summary = await analytics_service.get_daily_energy_summary(device_id)

                    # Generate contextual response
                    response_text = await whatsapp_service.handle_conversational_query(
                        sender_phone=sender_phone,
                        message_body=text_body,
                        latest_telemetry=latest_telemetry,
                        device_info=device_meta,
                        analytics_summary=analytics_summary
                    )

                    # Send reply back to user
                    await whatsapp_service.send_text_message(sender_phone, response_text)

    return {"status": "ok"}
