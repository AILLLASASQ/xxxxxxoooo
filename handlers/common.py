"""أوامر عامة: /start /help والقائمة ولوحة الصدارة والنقاط."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import keyboards
import settings
import store

router = Router()
_MEDALS = ["🥇", "🥈", "🥉"]


def _display_name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


@router.message(Command("start"))
async def cmd_start(message: Message):
    store.ensure_user(message.from_user.id, _display_name(message.from_user))
    await message.answer(settings.get("text_welcome"), reply_markup=keyboards.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = ("📖 الأوامر:\n/start — القائمة الرئيسية\n/xo — بدء لعبة في المجموعة\n"
            "/top — لوحة الصدارة\n/me — نقاطي\n\n"
            "وفي أي محادثة اكتب اسم البوت ثم مسافة لبدء لعبة إنلاين.")
    await message.answer(text)


@router.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer(_leaderboard_text(message.from_user.id))


@router.message(Command("me"))
async def cmd_me(message: Message):
    await message.answer(_user_text(message.from_user))


@router.callback_query(F.data == "board:show")
async def cb_board(call: CallbackQuery):
    await call.message.answer(_leaderboard_text(call.from_user.id))
    await call.answer()


@router.callback_query(F.data == "me:show")
async def cb_me(call: CallbackQuery):
    store.ensure_user(call.from_user.id, _display_name(call.from_user))
    await call.message.answer(_user_text(call.from_user))
    await call.answer()


def _leaderboard_text(viewer_id=None):
    top = store.top_users(3)
    prizes = settings.get("reward_prizes") or []
    if not top:
        active = [p for p in prizes[:3] if p]
        if active:
            lines = ["🏆 لوحة الصدارة", "لا يوجد لاعبون بعد.", "", "🎁 الجوائز بانتظار الفائزين:"]
            for i, p in enumerate(prizes[:3]):
                if p:
                    lines.append(f"{_MEDALS[i]} {p}")
            return "\n".join(lines)
        return "لا يوجد لاعبون بعد."

    lines = ["🏆 لوحة الصدارة — أعلى 3\n"]
    top_ids = set()
    for i, u in enumerate(top):
        top_ids.add(str(u["id"]))
        line = f"{_MEDALS[i]} {u['name']} — {u['points']} نقطة"
        if i < len(prizes) and prizes[i]:
            line += f"  🎁 {prizes[i]}"
        lines.append(line)

    if viewer_id is not None and str(viewer_id) not in top_ids:
        r = store.user_rank(viewer_id)
        lines.append("➖➖➖➖➖")
        if r:
            rank, pts = r
            lines.append(f"📍 ترتيبك: #{rank} — {pts} نقطة")
        else:
            lines.append("📍 العب مباراة لتدخل التصنيف!")
    return "\n".join(lines)


def _user_text(user):
    u = store.get_user(user.id)
    if not u:
        return "لا توجد بيانات بعد. العب أولاً!"
    return (f"📊 إحصائياتك يا {u.get('name')}\n\nالنقاط: {u.get('points', 0)}\n"
            f"فوز: {u.get('wins', 0)} | خسارة: {u.get('losses', 0)} | "
            f"تعادل: {u.get('draws', 0)}")
