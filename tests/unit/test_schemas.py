"""Unit tests for WhatsApp webhook Pydantic models."""
import json
import pytest
from app.services.whatsapp.schemas import WhatsAppWebhookPayload


def test_parse_text_message_payload():
    payload_json = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456789012345",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Shubham"},
                                    "wa_id": "919876543210",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.HBgLOTE5ODc2NTQzMjEwFQIAEhgUM0FF",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Hello TutorBot"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    parsed = WhatsAppWebhookPayload.model_validate(payload_json)
    assert parsed.object == "whatsapp_business_account"
    assert len(parsed.entry) == 1
    assert len(parsed.entry[0].changes) == 1
    change = parsed.entry[0].changes[0]
    assert change.value.contacts[0].profile.name == "Shubham"
    assert change.value.messages[0].text.body == "Hello TutorBot"
    assert change.value.messages[0].id == "wamid.HBgLOTE5ODc2NTQzMjEwFQIAEhgUM0FF"


def test_parse_status_update_payload():
    payload_json = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456789012345",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgLOTE5ODc2NTQzMjEwFQIAEhgUM0FF",
                                    "status": "delivered",
                                    "timestamp": "1710000005",
                                    "recipient_id": "919876543210",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    parsed = WhatsAppWebhookPayload.model_validate(payload_json)
    assert parsed.entry[0].changes[0].value.messages is None
    assert len(parsed.entry[0].changes[0].value.statuses) == 1
    assert parsed.entry[0].changes[0].value.statuses[0].status == "delivered"
