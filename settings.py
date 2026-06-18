"""الإعدادات الديناميكية — يعدّلها المالك من داخل تيليجرام دون إعادة نشر.

تُخزَّن في مستند واحد: settings/config
تُحمَّل في الذاكرة عند الإقلاع، وتُحدَّث فوراً عند أي تعديل من لوحة التحكم.
"""
from firebase_db import db

# القيم الافتراضية — تُكتب في Firestore أول مرة فقط
DEFAULTS = {
    # النقاط
    "points_win": 3,
    "points_draw": 1,
    "points_loss": 0,
    "daily_bonus": 5,
    # حماية ضد الـfarming
    "daily_limit": 150,   # حد أقصى لمباريات اللاعب يومياً (0 = بلا حد)
    "pair_limit": 3,      # حد مباريات نفس الخصم يومياً قبل إيقاف النقاط (0 = بلا حد)
    # تفعيل/تعطيل الأوضاع
    "enable_pvp": True,
    "enable_vs_bot": True,
    "enable_inline": True,
    # صعوبة البوت: "easy" | "hard"
    "bot_difficulty": "hard",
    # النصوص القابلة للتعديل بالعربي
    "text_welcome": "أهلاً بك في لعبة إكس أو! ⭕❌\nاختر وضع اللعب من الأزرار.",
    "text_win": "🎉 فاز اللاعب {name}!",
    "text_draw": "🤝 تعادل!",
    "text_your_turn": "دور: {name}",
}

_cache = dict(DEFAULTS)


def _doc_ref():
    return db().collection("settings").document("config")


def load_settings():
    """تحميل الإعدادات من Firestore إلى الذاكرة. تُنشئ المستند إن لم يوجد."""
    global _cache
    snap = _doc_ref().get()
    if snap.exists:
        data = snap.to_dict() or {}
        # دمج: أي مفتاح جديد في DEFAULTS يُضاف تلقائياً
        merged = dict(DEFAULTS)
        merged.update(data)
        _cache = merged
        # كتابة المفاتيح الناقصة فقط
        missing = {k: v for k, v in DEFAULTS.items() if k not in data}
        if missing:
            _doc_ref().set(missing, merge=True)
    else:
        _doc_ref().set(DEFAULTS)
        _cache = dict(DEFAULTS)
    return _cache


def get(key):
    return _cache.get(key, DEFAULTS.get(key))


def all_settings():
    return dict(_cache)


def update(key, value):
    """تحديث إعداد واحد في Firestore والذاكرة معاً."""
    _doc_ref().set({key: value}, merge=True)
    _cache[key] = value

