"""حماية ضد الـfarming والتواطؤ: حد يومي للمباريات + سقف مباريات نفس الخصم.

البيانات تُخزَّن ضمن مستند المستخدم وفي meta/pair_counts (تصفير يومي تلقائي).
"""
from datetime import datetime, timezone

from firebase_db import db


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _user_ref(uid):
    return db().collection("users").document(str(uid))


def is_banned(uid):
    snap = _user_ref(uid).get()
    return bool(snap.exists and snap.to_dict().get("banned"))


def at_daily_limit(uid, limit):
    """هل بلغ اللاعب حده اليومي؟ limit=0 => لا حد."""
    if not limit:
        return False
    snap = _user_ref(uid).get()
    u = snap.to_dict() if snap.exists else {}
    cnt = int(u.get("matches_today", 0) or 0)
    if u.get("matches_today_date") != _today():
        cnt = 0
    return cnt >= int(limit)


def bump_daily_match(uid):
    """يزيد عدّاد مباريات اليوم بواحد."""
    snap = _user_ref(uid).get()
    u = snap.to_dict() if snap.exists else {}
    today = _today()
    cnt = int(u.get("matches_today", 0) or 0)
    if u.get("matches_today_date") != today:
        cnt = 0
    _user_ref(uid).set(
        {"matches_today": cnt + 1, "matches_today_date": today}, merge=True)


def record_pair_match(uid1, uid2):
    """يسجّل مباراة بين زوج لاعبَين ويعيد عددها اليوم (لمنع win-trading)."""
    if not (uid1 and uid2) or int(uid1) == int(uid2):
        return 0
    a, b = sorted([str(uid1), str(uid2)])
    key = f"{a}_{b}"
    today = _today()
    ref = db().collection("meta").document("pair_counts")
    try:
        snap = ref.get()
        data = snap.to_dict() if snap.exists else {}
        if data.get("_date") != today:
            data = {"_date": today}
        cnt = int(data.get(key, 0) or 0) + 1
        data[key] = cnt
        data["_date"] = today
        ref.set(data)
        return cnt
    except Exception as e:
        print(f"record_pair_match: {e}")
        return 0

