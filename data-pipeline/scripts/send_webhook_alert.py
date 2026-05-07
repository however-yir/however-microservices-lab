#!/usr/bin/env python3
"""Send custom alerts to Feishu/DingTalk webhook."""

import json
import os
import sys

import requests


WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")


def main() -> int:
    if not WEBHOOK_URL:
        print("ALERT_WEBHOOK_URL is not set")
        return 1

    text = " ".join(sys.argv[1:]).strip() or "Realtime pipeline test alert"
    payload = {"msg_type": "text", "content": {"text": text}}

    response = requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=10)
    print(response.status_code, response.text)
    return 0 if response.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
