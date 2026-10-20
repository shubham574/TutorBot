"""Integration tests for WhatsApp Webhook endpoints."""
import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient
from app.config.settings import settings


def compute_signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"

SAMPLE_MESSAGE_PAYLOAD = {
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
                                "profile": {"name": "Test Student"},
                                "wa_id": "919876543210",
                            }
                        ],
                        "messages": [
                            {
                                "from": "919876543210",
                                "id": "wamid.TEST_ID_001",
                                "timestamp": "1710000000",
                                "type": "text",
                                "text": {"body": "/ping"},
                            }
                        ],
                    },
                }
            ],
        }
    ],
}


@pytest.mark.asyncio
async def test_webhook_get_verification_success(app_client: AsyncClient):
    """Verifies that Meta's webhook challenge responds with 200 and the challenge string."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "random_challenge_string_abc123",
    }
    response = await app_client.get("/api/v1/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "random_challenge_string_abc123"


@pytest.mark.asyncio
async def test_webhook_get_verification_wrong_token(app_client: AsyncClient):
    """Verifies that invalid verify_token is rejected with 403."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "random_challenge_string_abc123",
    }
    response = await app_client.get("/api/v1/webhook", params=params)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_missing_signature(app_client: AsyncClient):
    """Rejects incoming webhook without X-Hub-Signature-256 header with 401."""
    body_bytes = json.dumps(SAMPLE_MESSAGE_PAYLOAD).encode("utf-8")
    response = await app_client.post(
        "/api/v1/webhook",
        content=body_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_post_invalid_signature(app_client: AsyncClient):
    """Rejects incoming webhook with incorrect HMAC signature."""
    body_bytes = json.dumps(SAMPLE_MESSAGE_PAYLOAD).encode("utf-8")
    response = await app_client.post(
        "/api/v1/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalidhex00000000000000000000000000",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_post_success_and_deduplication(app_client: AsyncClient, mock_arq_pool):
    """Tests intake, queuing, and fast Redis deduplication of incoming messages."""
    body_bytes = json.dumps(SAMPLE_MESSAGE_PAYLOAD).encode("utf-8")
    valid_signature = compute_signature(body_bytes, settings.WHATSAPP_APP_SECRET)

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": valid_signature,
    }

    # 1. First delivery: Should enqueue message
    response = await app_client.post("/api/v1/webhook", content=body_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["enqueued"] == 1
    assert len(mock_arq_pool.enqueued_jobs) == 1
    job = mock_arq_pool.enqueued_jobs[0]
    assert job["function"] == "process_whatsapp_message"
    assert job["args"][0]["wamid"] == "wamid.TEST_ID_001"
    assert job["args"][0]["text_content"] == "/ping"

    # 2. Duplicate delivery (Meta retry with same wamid): Should drop via Redis
    response_dup = await app_client.post("/api/v1/webhook", content=body_bytes, headers=headers)
    assert response_dup.status_code == 200
    assert response_dup.json()["status"] == "ok"
    assert response_dup.json()["enqueued"] == 0  # Dropped!
    assert len(mock_arq_pool.enqueued_jobs) == 1  # Queue size unchanged
