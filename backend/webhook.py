"""
Compatibility launcher for WhatsApp webhook service.

Webhook handling is unified in FastAPI at:
  backend.main -> GET/POST /whatsapp/webhook

Use this file only as a convenience entrypoint:
  python backend/webhook.py
"""

import os
import uvicorn


def main():
    port = int(os.getenv("WEBHOOK_PORT", "5000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
