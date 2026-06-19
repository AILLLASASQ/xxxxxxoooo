"""وضع الإنلاين: لعب إكس أو أونلاين عبر يوزر البوت في أي محادثة."""
import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent,
                           Message)

import render
import settings
import store

router = Router()

# مكافحة السبام لبطاقات الضيف: بطاقة واحدة لكل مستخدم خلال فترة التهدئة
_GUEST_COOLDOWN = 10  # ثوانٍ
_last_guest = {}      # user_id -> monotonic timestamp


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


def _guest_throttled(user_id):
    """True إذا كان المستخدم ضمن فترة التهدئة (يُكتم الرد)."""
    now = time.monotonic()
    last = _last_guest.get(user_id, 0.0)
    if now - last < _GUEST_COOLDOWN:
        return True
    _last_guest[user_id] = now
    # تنظيف خفيف لمنع تضخّم الذاكرة مع الوقت
    if len(_last_guest) > 5000:
        cutoff = now - _GUEST_COOLDOWN
        for uid in [u for u, t in _last_guest.items() if t < cutoff]:
            _last_guest.pop(uid, None)
    return False


def _join_kb(gid, creator_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🎮 انضم للعب", callback_data=f"ij:{gid}:{creator_id}")]])


@router.inline_query()
async def inline_xo(query: InlineQuery):
    if not settings.get("enable_inline"):
        await query.answer([], cache_time=1, is_personal=True)
        return

    store.ensure_user(query.from_user.id, _name(query.from_user))
    gid = store.new_game_id()
    preview = (
        "⭕❌ إكس أو\n"
        f"❌ {_name(query.from_user)}  ضد  ⏳ بانتظار لاعب\n\n"
        "اضغط (انضم للعب) لبدء المباراة."
    )
    result = InlineQueryResultArticle(
        id=gid,
        title="🎮 ابدأ لعبة إكس أو",
        description="العب ضد أي شخص في هذه المحادثة",
        input_message_content=InputTextMessageContent(message_text=preview),
        reply_markup=_join_kb(gid, query.from_user.id),
    )
    await query.answer([result], cache_time=1, is_personal=True)


@router.callback_query(F.data.startswith("ij:"))
async def inline_join(call: CallbackQuery, bot: Bot):
    try:
        _, gid, creator_id = call.data.split(":")
        creator_id = int(creator_id)
    except Exception:
        await call.answer("بيانات غير صالحة.", show_alert=True)
        return

    joiner = call.from_user
    if joiner.id == creator_id:
        await call.answer("لا يمكنك اللعب ضد نفسك، انتظر صديقاً 🙂", show_alert=True)
        return

    existing = store.get_game(gid)
    if existing and existing.get("player_o"):
        await call.answer("اللعبة بدأت بالفعل.", show_alert=True)
        return

    store.ensure_user(joiner.id, _name(joiner))
    creator = store.get_user(creator_id) or {}
    creator_name = creator.get("name", "اللاعب")

    data = store.create_inline_game(
        gid, creator_id, creator_name, joiner.id, _name(joiner),
        call.inline_message_id)

    text, kb = render.render(data)
    try:
        await bot.edit_message_text(
            text=text, inline_message_id=call.inline_message_id, reply_markup=kb)
    except Exception:
        logging.exception("inline_join edit failed")
    await call.answer("بدأت اللعبة!")


# ===== Guest Mode: الرد عند ذكر يوزر البوت دون عضوية (خاص + مجموعات) =====
@router.guest_message()
async def guest_xo(message: Message):
    """عند ذكر @البوت في أي محادثة، نرد ببطاقة لعبة (نفس بطاقة الإنلاين)."""
    if not settings.get("enable_guest"):
        return

    # في تحديث guest_message: المُستدعي هو from_user، والرد عبر guest_query_id
    caller = message.from_user
    if caller is None or not message.guest_query_id:
        return

    # تجاهل استدعاء البوتات الأخرى
    if caller.is_bot:
        return

    # مكافحة السبام: بطاقة واحدة لكل مستخدم خلال فترة التهدئة
    if _guest_throttled(caller.id):
        return

    store.ensure_user(caller.id, _name(caller))
    gid = store.new_game_id()
    preview = (
        "⭕❌ إكس أو\n"
        f"❌ {_name(caller)}  ضد  ⏳ بانتظار لاعب\n\n"
        "اضغط (انضم للعب) لبدء المباراة."
    )
    result = InlineQueryResultArticle(
        id=gid,
        title="🎮 ابدأ لعبة إكس أو",
        description="العب ضد من ذكر البوت في هذه المحادثة",
        input_message_content=InputTextMessageContent(message_text=preview),
        reply_markup=_join_kb(gid, caller.id),
    )
    try:
        await message.answer_guest_query(result=result)
    except Exception:
        logging.exception("guest_xo answer failed")
