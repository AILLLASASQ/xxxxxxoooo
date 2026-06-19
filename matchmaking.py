"""طابور المطابقة العشوائية — مطابقة ذرّية عبر Firestore transaction."""
import time

from google.cloud.firestore_v1 import transactional

from firebase_db import db


def queue_add(user_id, name, chat_id, msg_id):
    db().collection("queue").document(str(user_id)).set({
        "user_id": int(user_id),
        "name": name or "لاعب",
        "chat_id": int(chat_id),
        "msg_id": int(msg_id),
        "joined_at": int(time.time()),
    })


def queue_remove(user_id):
    try:
        db().collection("queue").document(str(user_id)).delete()
    except Exception:
        pass


def queue_in(user_id):
    return db().collection("queue").document(str(user_id)).get().exists


def queue_get(user_id):
    """يعيد بيانات إدخال اللاعب في الطابور أو None."""
    snap = db().collection("queue").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else None


def queue_size():
    try:
        return int(db().collection("queue").count().get()[0][0].value)
    except Exception:
        return sum(1 for _ in db().collection("queue").limit(500).stream())


def queue_try_match(new_user_id, new_name, new_chat_id, new_msg_id):
    """مطابقة ذرّية:
      - إن وُجد منتظر غيرك → احذفه وأرجِع بياناته (مباراة).
      - وإلا → أضفك للطابور وأرجِع None (انتظار).
    """
    qref = db().collection("queue")

    @transactional
    def _txn(txn):
        docs = list(qref.order_by("joined_at").limit(5).stream(transaction=txn))
        opp = None
        for d in docs:
            if d.id != str(new_user_id):
                opp = d
                break
        if opp is not None:
            txn.delete(opp.reference)
            return {"id": opp.id, **opp.to_dict()}
        txn.set(qref.document(str(new_user_id)), {
            "user_id": int(new_user_id),
            "name": new_name or "لاعب",
            "chat_id": int(new_chat_id),
            "msg_id": int(new_msg_id),
            "joined_at": int(time.time()),
        })
        return None

    return _txn(db().transaction())


def stale_searchers(timeout_seconds):
    """يعيد المنتظرين الذين تجاوزوا المهلة (للتنظيف والإشعار)."""
    now = int(time.time())
    out = []
    for d in db().collection("queue").limit(500).stream():
        data = d.to_dict()
        if now - int(data.get("joined_at", now)) >= timeout_seconds:
            out.append(data)
    return out

