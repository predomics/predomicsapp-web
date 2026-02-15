"""Webhook delivery service with HMAC-SHA256 signing."""

import hashlib
import hmac
import json
import logging
import time

import httpx

_log = logging.getLogger(__name__)


def _sign_payload(payload_json: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()


def send_webhook_sync(url: str, payload: dict, secret: str, retries: int = 3) -> bool:
    """Send webhook with retries. Runs in sync context."""
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    signature = _sign_payload(payload_json, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "User-Agent": "PredomicsApp-Webhook/1.0",
    }

    for attempt in range(retries):
        try:
            resp = httpx.post(url, content=payload_json, headers=headers, timeout=10)
            if resp.status_code < 400:
                _log.info("Webhook delivered to %s (status %d)", url, resp.status_code)
                return True
            _log.warning("Webhook to %s returned %d", url, resp.status_code)
        except Exception as e:
            _log.warning("Webhook to %s failed (attempt %d): %s", url, attempt + 1, e)
        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    return False
