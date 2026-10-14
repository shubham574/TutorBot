"""Pydantic schemas for WhatsApp incoming webhooks and normalized messages."""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Incoming Meta Webhook DTOs
# -----------------------------------------------------------------------------

class WebhookProfile(BaseModel):
    name: Optional[str] = None


class WebhookContact(BaseModel):
    profile: Optional[WebhookProfile] = None
    wa_id: str


class WebhookText(BaseModel):
    body: str


class WebhookButtonReply(BaseModel):
    id: str
    title: str


class WebhookInteractive(BaseModel):
    type: str  # e.g., button_reply, list_reply
    button_reply: Optional[WebhookButtonReply] = None


class WebhookDocument(BaseModel):
    id: str
    caption: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    sha256: Optional[str] = None


class WebhookAudio(BaseModel):
    id: str
    mime_type: Optional[str] = None
    voice: Optional[bool] = False


class WebhookImage(BaseModel):
    id: str
    caption: Optional[str] = None
    mime_type: Optional[str] = None


class WebhookMessage(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: Optional[WebhookText] = None
    interactive: Optional[WebhookInteractive] = None
    document: Optional[WebhookDocument] = None
    image: Optional[WebhookImage] = None
    audio: Optional[WebhookAudio] = None


class WebhookStatus(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str


class WebhookMetadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class WebhookValue(BaseModel):
    messaging_product: str
    metadata: Optional[WebhookMetadata] = None
    contacts: Optional[List[WebhookContact]] = None
    messages: Optional[List[WebhookMessage]] = None
    statuses: Optional[List[WebhookStatus]] = None


class WebhookChange(BaseModel):
    value: WebhookValue
    field: str


class WebhookEntry(BaseModel):
    id: str
    changes: List[WebhookChange]


class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: List[WebhookEntry]


# -----------------------------------------------------------------------------
# Internal Normalized Message DTO
# -----------------------------------------------------------------------------

class NormalizedIncomingMessage(BaseModel):
    """Clean, normalized representation of an inbound WhatsApp message."""
    wamid: str
    sender_phone: str
    sender_name: Optional[str] = None
    message_type: str  # text, interactive, document, audio, image, unsupported
    text_content: Optional[str] = None
    interactive_button_id: Optional[str] = None
    interactive_title: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_filename: Optional[str] = None
    raw_payload: Dict[str, Any]


# -----------------------------------------------------------------------------
# Outgoing WhatsApp Message DTOs
# -----------------------------------------------------------------------------

class OutgoingReplyButton(BaseModel):
    id: str
    title: str = Field(..., max_length=20)


class OutgoingInteractiveButtons(BaseModel):
    body_text: str = Field(..., max_length=1024)
    buttons: List[OutgoingReplyButton] = Field(..., max_length=3)
    header_text: Optional[str] = Field(None, max_length=60)
    footer_text: Optional[str] = Field(None, max_length=60)
