"""تهيئة Firestore."""
import base64
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

import config

_db = None


def init_db():
    global _db
    if _db is not None:
        return _db
    if config.FIREBASE_CREDENTIALS_B64:
        raw = base64.b64decode(config.FIREBASE_CREDENTIALS_B64).decode("utf-8")
        cred = credentials.Certificate(json.loads(raw))
    elif os.path.exists("serviceAccount.json"):
        cred = credentials.Certificate("serviceAccount.json")
    else:
        raise RuntimeError("لم يتم العثور على مفتاح Firebase.")
    firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def db():
    if _db is None:
        return init_db()
    return _db
