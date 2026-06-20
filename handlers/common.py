"""أوامر عامة: /start /help والقائمة ولوحة الشرف والنقاط."""
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import keyboards
import settings
import store

router = Router()
_RANK = ["🥇", "🥈", "🥉"]


def _display_name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


@router.message(Command("start"))
async def cmd_start(message: Message):
    store.ensure_user(message.from_user.id, _display_name(message.from_user))
    await message.answer(settings.get("text_welcome"), reply_markup=keyboards.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = ("📖 الأوامر:\n/start — القائمة الرئيسية\n/xo — بدء لعبة في المجموعة\n"
            "/top — لوحة الشرف\n/me — نقاطي\n\n"
            "وفي أي محادثة اكتب اسم البوت ثم مسافة لبدء لعبة إنلاين.")
    await message.answer(text)


@router.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer(_leaderboard_text(message.from_user.id),
                         reply_markup=keyboards.leaderboard_menu())


@router.message(Command("me"))
async def cmd_me(message: Message):
    await message.answer(_user_text(message.from_user))


async def _safe_edit(call, text, kb):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "board:show")
async def cb_board(call: CallbackQuery):
    await _safe_edit(call, _leaderboard_text(call.from_user.id),
                     keyboards.leaderboard_menu())
    await call.answer()


@router.callback_query(F.data == "board:last")
async def cb_board_last(call: CallbackQuery):
    await _safe_edit(call, _last_season_text(), keyboards.back_to_board())
    await call.answer()


@router.callback_query(F.data == "board:back")
async def cb_board_back(call: CallbackQuery):
    await _safe_edit(call, settings.get("text_welcome"), keyboards.main_menu())
    await call.answer()


@router.callback_query(F.data == "me:show")
async def cb_me(call: CallbackQuery):
    store.ensure_user(call.from_user.id, _display_name(call.from_user))
    await call.message.answer(_user_text(call.from_user))
    await call.answer()


def _fmt_remaining(seconds):
    seconds = max(0, int(seconds))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days:
        return f"{days} يوم {hours} ساعة"
    if hours:
        return f"{hours} ساعة {mins} دقيقة"
    return f"{mins} دقيقة"


def _leaderboard_text(viewer_id=None):
    store.maybe_rollover_season()
    season = store.get_season()
    size = int(settings.get("leaderboard_size") or 5)
    top = store.top_users(size)
    prizes = settings.get("reward_prizes") or []
    remaining = _fmt_remaining(int(season.get("end", 0)) - int(time.time()))

    lines = [f"🏆 لوحة الشرف (الموسم {season.get('number', 1)}) — أعلى {size}",
             f"⏳ التصفير خلال: {remaining}"]

    if any(prizes[:3]):
        parts = [f"{_RANK[i]} {prizes[i]}" for i in range(3)
                 if i < len(prizes) and prizes[i]]
        lines += ["", "🎁 الجوائز:", "   ".join(parts)]

    lines.append("")
    if not top:
        lines.append("لا يوجد لاعبون بعد. كن الأول! 🎮")
    else:
        ids = set()
        for i, u in enumerate(top):
            ids.add(str(u["id"]))
            pos = _RANK[i] if i < 3 else f"{i + 1}."
            mark = "  👈 أنت" if str(u["id"]) == str(viewer_id) else ""
            lines.append(f"{pos} {u['name']} ({store.tier_name(u['points'])}) "
                         f"⭐{u['points']}{mark}")
        if viewer_id is not None and str(viewer_id) not in ids:
            r = store.user_rank(viewer_id)
            lines.append("➖➖➖➖➖")
            if r:
                lines.append(f"📍 ترتيبك: #{r[0]} | ⭐{r[1]}")
            else:
                lines.append("📍 العب مباراة لتدخل التصنيف!")
    return "\n".join(lines)


def _last_season_text():
    ls = store.last_season()
    if not ls or not ls.get("top"):
        return "لا يوجد موسم سابق بعد. سيظهر هنا أبطال أول موسم منتهٍ."
    lines = [f"🏅 أبطال الموسم {ls.get('number', '؟')}:\n"]
    for i, c in enumerate(ls["top"][:5]):
        pos = _RANK[i] if i < 3 else f"{i + 1}."
        prize = f" — 🎁 {c['prize']}" if c.get("prize") else ""
        lines.append(f"{pos} {c.get('name', '?')} ⭐{c.get('points', 0)}{prize}")
    return "\n".join(lines)


def _user_text(user):
    u = store.get_user(user.id)
    if not u:
        return "لا توجد بيانات بعد. العب أولاً!"
    return (f"📊 إحصائياتك يا {u.get('name')}\n\n"
            f"⭐ النقاط: {u.get('points', 0)} ({store.tier_name(u.get('points', 0))})\n"
            f"فوز: {u.get('wins', 0)} | خسارة: {u.get('losses', 0)} | "
            f"تعادل: {u.get('draws', 0)}")
