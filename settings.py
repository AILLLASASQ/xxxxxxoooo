"""الإعدادات الديناميكية — يعدّلها المالك من داخل تيليجرام دون إعادة نشر."""
from firebase_db import db

DEFAULTS = {
    "points_win": 3,
    "points_draw": 1,
    "points_loss": -1,
    "points_floor": -50,
    "bot_win_easy": 1,
    "bot_win_medium": 2,
    "bot_win_hard": 3,
    "daily_bonus": 5,
    "daily_limit": 150,
    "pair_points_limit": 9,
    "stale_timeout": 120,
    "text_expired": "⌛ انتهت المباراة",
    "turn_timeout": 15,
    "turn_check_interval": 3,
    "text_timeout_win": "⏱️ فاز {name} (انتهى وقت الخصم)",
    "reward_prizes": ["", "", "", "", ""],
    # لوحة الشرف والمواسم
    "leaderboard_size": 5,
    "season_days": 7,
    "tier_silver": 50,
    "tier_gold": 150,
    "tier_diamond": 300,
    "enable_pvp": True,
    "enable_vs_bot": True,
    "enable_inline": True,
    "enable_guest": True,
    "enable_force_sub": False,
    "force_sub_channel": "",
    "force_sub_text": "🚪 للّعب، اشترك في قناتنا أولاً ثم اضغط «✅ تحقّقت».",
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
