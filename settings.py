"""الإعدادات الديناميكية — يعدّلها المالك من تيليجرام دون إعادة نشر."""
from firebase_db import db

DEFAULTS = {
    "points_win": 3,
    "points_draw": 1,
    "points_loss": 0,
    "daily_bonus": 5,
    "enable_pvp": True,
    "enable_vs_bot": True,
    "enable_inline": True,
    "bot_difficulty": "hard",
    "text_welcome": "أهلاً بك في لعبة إكس أو! ⭕❌\nاختر وضع اللعب من الأزرار.",
    "text_win": "🎉 فاز اللاعب {name}!",
    "text_draw": "🤝 تعادل!",
    "text_your_turn": "دور: {name}",
}

_cache = dict(DEFAULTS)


def _doc_ref():
    return db().collection("settings").document("config")


def load_settings():
    global _cache
    snap = _doc_ref().get()
    if snap.exists:
        data = snap.to_dict() or {}
        merged = dict(DEFAULTS)
        merged.update(data)
        _cache = merged
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
    _doc_ref().set({key: value}, merge=True)
    _cache[key] = value
