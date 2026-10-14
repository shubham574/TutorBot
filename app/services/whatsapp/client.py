"""Meta WhatsApp Cloud API async client with DRY_RUN support."""
import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.config.settings import settings
from app.config.logging_config import logger
from app.services.whatsapp.formatter import (
    clean_latex_for_whatsapp,
    split_message_for_whatsapp,
)
from app.services.whatsapp.schemas import OutgoingReplyButton


class WhatsAppClient:
    """Async client for sending WhatsApp messages via Meta Cloud API."""

    def __init__(
        self,
        api_version: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        dry_run: Optional[bool] = None,
    ):
        self.api_version = api_version or settings.WHATSAPP_API_VERSION
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self,
        recipient_phone: str,
        text: str,
        preview_url: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Sends text message(s) to recipient. Automatically cleans LaTeX and
        splits into <= 4096 character messages if needed.
        """
        cleaned_text = clean_latex_for_whatsapp(text)
        chunks = split_message_for_whatsapp(cleaned_text)
        results: List[Dict[str, Any]] = []

        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_phone,
                "type": "text",
                "text": {
                    "preview_url": preview_url,
                    "body": chunk,
                },
            }
            res = await self._post_message(payload, recipient_phone, "text")
            results.append(res)

        return results

    async def send_interactive_buttons(
        self,
        recipient_phone: str,
        body_text: str,
        buttons: List[OutgoingReplyButton],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends an interactive button message (up to 3 reply buttons).
        """
        cleaned_body = clean_latex_for_whatsapp(body_text)[:1024]
        button_payload = [
            {
                "type": "reply",
                "reply": {
                    "id": btn.id,
                    "title": btn.title[:20],
                },
            }
            for btn in buttons[:3]
        ]

        action_data: Dict[str, Any] = {"buttons": button_payload}
        interactive_data: Dict[str, Any] = {
            "type": "button",
            "body": {"text": cleaned_body},
            "action": action_data,
        }

        if header_text:
            interactive_data["header"] = {
                "type": "text",
                "text": header_text[:60],
            }
        if footer_text:
            interactive_data["footer"] = {"text": footer_text[:60]}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": interactive_data,
        }

        return await self._post_message(payload, recipient_phone, "interactive")

    async def send_document(
        self,
        recipient_phone: str,
        document_url: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends a document (PDF, etc.) to the recipient."""
        doc_data: Dict[str, Any] = {"link": document_url}
        if caption:
            doc_data["caption"] = caption
        if filename:
            doc_data["filename"] = filename

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "document",
            "document": doc_data,
        }
        return await self._post_message(payload, recipient_phone, "document")

    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Marks an inbound message as read."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if self.dry_run:
            logger.info("DRY_RUN: Marked message as read", message_id=message_id)
            return {"success": True, "dry_run": True}

        url = f"{self.base_url}/messages"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=self._get_headers())
            return resp.json()

    async def _post_message(
        self,
        payload: Dict[str, Any],
        recipient_phone: str,
        msg_type: str,
    ) -> Dict[str, Any]:
        """Internal dispatcher honoring DRY_RUN."""
        if self.dry_run:
            synthetic_wamid = f"wamid.DRY_RUN_{uuid.uuid4().hex[:16]}"
            logger.info(
                "DRY_RUN outbound WhatsApp message",
                recipient=recipient_phone,
                message_type=msg_type,
                synthetic_wamid=synthetic_wamid,
                payload=payload,
            )
            return {
                "messaging_product": "whatsapp",
                "contacts": [{"input": recipient_phone, "wa_id": recipient_phone}],
                "messages": [{"id": synthetic_wamid}],
                "dry_run": True,
            }

        url = f"{self.base_url}/messages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            if response.status_code >= 400:
                logger.error(
                    "WhatsApp API error",
                    status_code=response.status_code,
                    response_text=response.text,
                    recipient=recipient_phone,
                )
                response.raise_for_status()
            return response.json()


whatsapp_client = WhatsAppClient()
