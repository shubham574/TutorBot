"""WhatsApp Webhook security and HMAC-SHA256 signature verification."""
import hashlib
import hmac
from typing import Optional
from app.config.logging_config import logger


def verify_whatsapp_signature(
    raw_payload: bytes,
    signature_header: Optional[str],
    app_secret: str,
) -> bool:
    """
    Validates Meta WhatsApp Cloud API HMAC-SHA256 signature.

    Meta sends the signature in the `X-Hub-Signature-256` header formatted as:
    `sha256=<hex_encoded_hmac>`

    Args:
        raw_payload: The raw, unparsed request body in bytes.
        signature_header: The value of the X-Hub-Signature-256 HTTP header.
        app_secret: The Meta App Secret.

    Returns:
        bool: True if signature matches, False otherwise.
    """
    if not signature_header or not app_secret:
        logger.warning(
            "Webhook signature verification failed: Missing header or secret",
            has_header=bool(signature_header),
            has_secret=bool(app_secret),
        )
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        logger.warning(
            "Webhook signature verification failed: Invalid signature format prefix",
            signature_header=signature_header[:15],
        )
        return False

    received_signature = signature_header[len(prefix):]

    expected_signature = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(received_signature, expected_signature)
    if not is_valid:
        logger.warning("Webhook signature verification failed: Hash mismatch")
    return is_valid
