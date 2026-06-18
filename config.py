"""إعدادات البيئة — تُقرأ من environment variables على Render."""
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
WEBHOOK_BASE = os.environ["WEBHOOK_BASE"].rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "xo-secret-path")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = WEBHOOK_BASE + WEBHOOK_PATH
PORT = int(os.environ.get("PORT", 10000))
FIREBASE_CREDENTIALS_B64 = os.environ.get("FIREBASE_CREDENTIALS_B64", "")
