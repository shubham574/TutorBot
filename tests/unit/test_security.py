"""Unit tests for WhatsApp HMAC-SHA256 signature verification."""
import hashlib
import hmac
import pytest
from app.services.whatsapp.security import verify_whatsapp_signature

TEST_SECRET = "fb_app_secret_super_secure_987654"


def compute_signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_valid_signature():
    payload = b'{"object": "whatsapp_business_account"}'
    sig = compute_signature(payload, TEST_SECRET)
    assert verify_whatsapp_signature(payload, sig, TEST_SECRET) is True


def test_verify_tampered_payload():
    payload = b'{"object": "whatsapp_business_account"}'
    sig = compute_signature(payload, TEST_SECRET)
    tampered = b'{"object": "whatsapp_business_account", "hack": true}'
    assert verify_whatsapp_signature(tampered, sig, TEST_SECRET) is False


def test_verify_wrong_secret():
    payload = b'{"object": "whatsapp_business_account"}'
    sig = compute_signature(payload, "wrong_secret")
    assert verify_whatsapp_signature(payload, sig, TEST_SECRET) is False


def test_verify_missing_header():
    payload = b'{"object": "whatsapp_business_account"}'
    assert verify_whatsapp_signature(payload, None, TEST_SECRET) is False
    assert verify_whatsapp_signature(payload, "", TEST_SECRET) is False


def test_verify_missing_secret():
    payload = b'{"object": "whatsapp_business_account"}'
    sig = compute_signature(payload, TEST_SECRET)
    assert verify_whatsapp_signature(payload, sig, "") is False


def test_verify_invalid_prefix():
    payload = b'{"object": "whatsapp_business_account"}'
    digest = hmac.new(TEST_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    invalid_header = f"sha1={digest}"
    assert verify_whatsapp_signature(payload, invalid_header, TEST_SECRET) is False
