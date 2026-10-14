"""Unit tests for structured logging and PII redactor."""
from app.config.logging_config import mask_phone_number, pii_redactor


def test_mask_phone_number():
    assert mask_phone_number("+919876543210") == "+91*****3210"
    assert mask_phone_number("1234567890") == "123*****7890"
    assert mask_phone_number("123") == "****"


def test_pii_redactor_event_dict():
    event_dict = {
        "event": "Incoming message",
        "sender_phone": "+919876543210",
        "recipient": "+15551234567",
        "unrelated_key": "some_value",
    }
    redacted = pii_redactor(None, "info", event_dict)
    assert redacted["sender_phone"] == "+91*****3210"
    assert redacted["recipient"] == "+15*****4567"
    assert redacted["unrelated_key"] == "some_value"
