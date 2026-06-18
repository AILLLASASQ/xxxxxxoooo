"""تهيئة Firestore — تدعم الملف السري على Render و base64 معاً."""
import base64
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

import config

_db = None

_FILE_PATHS = ("serviceAccount.json", "/etc/secrets/serviceAccount.json")


def _build_credential():
    err = None
    b64 = "".join(config.FIREBASE_CREDENTIALS_B64.split())
    if b64:
        try:
            raw = base64.b64decode(b64)
            return credentials.Certificate(json.loads(raw.decode("utf-8")))
        except Exception as e:
            err = e

    for path in _FILE_PATHS:
        if os.path.exists(path):
            return credentials.Certificate(path)

    if err:
        raise RuntimeError(
            "قيمة FIREBASE_CREDENTIALS_B64 غير صالحة ولا يوجد ملف serviceAccount.json "
            f"سري على Render: {err}")
    raise RuntimeError(
        "لم يتم العثور على مفتاح Firebase. ارفع serviceAccount.json كـ Secret File "
        "على Render، أو ضع FIREBASE_CREDENTIALS_B64 صحيحاً.")


def init_db():
    global _db
    if _db is not None:
        return _db
    firebase_admin.initialize_app(_build_credential())
    _db = firestore.client()
    return _db


def db():
    if _db is None:
        return init_db()
    return _db
