"""WhatsApp Webhook verification and intake endpoints."""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from app.config.settings import settings
from app.config.logging_config import logger
from app.services.whatsapp.security import verify_whatsapp_signature
from app.services.whatsapp.schemas import WhatsAppWebhookPayload, NormalizedIncomingMessage

router = APIRouter(prefix="/webhook")


@router.get("", response_class=PlainTextResponse)
async def verify_webhook(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> Response:
    """
    Handles Meta WhatsApp Cloud API verification requests (hub.challenge).
    Meta calls this endpoint when you register or edit the Webhook URL in Developer Portal.
    """
    logger.info(
        "Received webhook verification challenge",
        mode=mode,
        token_matched=(verify_token == settings.WHATSAPP_VERIFY_TOKEN),
    )

    if mode == "subscribe" and verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        if challenge:
            return PlainTextResponse(content=challenge, status_code=status.HTTP_200_OK)

    logger.warning("Webhook verification challenge failed")
    return Response(content="Forbidden", status_code=status.HTTP_403_FORBIDDEN)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
) -> dict:
    """
    Handles incoming WhatsApp webhook events:
    1. Validates HMAC-SHA256 signature against Meta App Secret.
    2. Parses incoming messages.
    3. Fast-deduplicates via Redis by wamid.
    4. Enqueues message into ARQ worker queue.
    5. Returns 200 OK immediately (<200ms).
    """
    raw_body = await request.body()

    # 1. Signature Verification
    if not verify_whatsapp_signature(raw_body, x_hub_signature_256, settings.WHATSAPP_APP_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # 2. Parse Webhook Payload
    try:
        payload = WhatsAppWebhookPayload.model_validate_json(raw_body)
    except ValidationError as e:
        logger.warning("Unrecognized webhook schema or malformed payload", errors=e.errors())
        return {"status": "ok", "detail": "unrecognized_schema"}

    redis = getattr(request.app.state, "redis", None)
    arq_pool = getattr(request.app.state, "arq_pool", None)

    enqueued_count = 0

    # 3. Process Entries and Messages
    for entry in payload.entry:
        for change in entry.changes:
            value = change.value

            # Ignore delivery/read status updates
            if not value.messages:
                continue

            # Build contacts map for sender names
            contacts_map = {
                contact.wa_id: (contact.profile.name if contact.profile else None)
                for contact in (value.contacts or [])
            }

            for msg in value.messages:
                wamid = msg.id
                sender_phone = msg.from_

                # Fast Redis Deduplication
                if redis:
                    dedupe_key = f"dedupe:wamid:{wamid}"
                    # setnx with 24 hours (86400s) TTL
                    is_new = await redis.set(dedupe_key, "1", ex=86400, nx=True)
                    if not is_new:
                        logger.info("Dropping duplicate webhook message via Redis", wamid=wamid)
                        continue

                # Normalize message data
                text_content = None
                button_id = None
                button_title = None
                media_id = None
                media_mime_type = None
                media_filename = None

                if msg.type == "text" and msg.text:
                    text_content = msg.text.body
                elif msg.type == "interactive" and msg.interactive:
                    if msg.interactive.button_reply:
                        button_id = msg.interactive.button_reply.id
                        button_title = msg.interactive.button_reply.title
                        text_content = button_title
                elif msg.type == "document" and msg.document:
                    media_id = msg.document.id
                    media_mime_type = msg.document.mime_type
                    media_filename = msg.document.filename
                    text_content = msg.document.caption
                elif msg.type == "image" and msg.image:
                    media_id = msg.image.id
                    media_mime_type = msg.image.mime_type
                    text_content = msg.image.caption
                elif msg.type == "audio" and msg.audio:
                    media_id = msg.audio.id
                    media_mime_type = msg.audio.mime_type

                normalized = NormalizedIncomingMessage(
                    wamid=wamid,
                    sender_phone=sender_phone,
                    sender_name=contacts_map.get(sender_phone),
                    message_type=msg.type,
                    text_content=text_content,
                    interactive_button_id=button_id,
                    interactive_title=button_title,
                    media_id=media_id,
                    media_mime_type=media_mime_type,
                    media_filename=media_filename,
                    raw_payload=msg.model_dump(),
                )

                # Enqueue into ARQ queue
                if arq_pool:
                    await arq_pool.enqueue_job(
                        "process_whatsapp_message",
                        normalized.model_dump(),
                    )
                    enqueued_count += 1
                else:
                    logger.warning("ARQ pool not initialized, message not enqueued", wamid=wamid)

    return {"status": "ok", "enqueued": enqueued_count}
