"""حماية ضد الـfarming والتواطؤ: حد يومي للمباريات + حدّ نقاط من نفس الخصم.

البيانات تُخزَّن في مستند المستخدم وفي meta (تصفير يومي تلقائي).
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
    """هل بلغ اللاعب حده اليومي للمباريات؟ limit=0 => لا حد."""
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


# ---------- حدّ تجميع النقاط من نفس الخصم (اتجاهي، تصفير يومي) ----------
def pair_points(earner, opponent):
    """نقاط earner المكتسبة من opponent اليوم (اتجاهي)."""
    if not (earner and opponent) or int(earner) == int(opponent):
        return 0
    today = _today()
    snap = db().collection("meta").document("pair_points").get()
    data = snap.to_dict() if snap.exists else {}
    if data.get("_date") != today:
        return 0
    return int(data.get(f"{earner}>{opponent}", 0) or 0)


def add_pair_points(earner, opponent, pts):
    """يضيف pts إلى نقاط earner المكتسبة من opponent اليوم."""
    if not (earner and opponent) or int(earner) == int(opponent) or int(pts) <= 0:
        return
    today = _today()
    ref = db().collection("meta").document("pair_points")
    try:
        snap = ref.get()
        data = snap.to_dict() if snap.exists else {}
        if data.get("_date") != today:
            data = {"_date": today}
        key = f"{earner}>{opponent}"
        data[key] = int(data.get(key, 0) or 0) + int(pts)
        data["_date"] = today
        ref.set(data)
    except Exception as e:
        print(f"add_pair_points: {e}")
