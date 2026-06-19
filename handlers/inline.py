"""وضع الإنلاين: لعب إكس أو أونلاين عبر يوزر البوت في أي محادثة."""
from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent)

import render
import settings
import store
from aiogram.types import Message

router = Router()


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


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
        pass
    await call.answer("بدأت اللعبة!")



# ===== Guest Mode: الرد عند ذكر يوزر البوت دون عضوية =====
@router.guest_message()
async def guest_xo(message: Message):
    """عند ذكر @البوت في أي محادثة، نرد ببطاقة لعبة (نفس بطاقة الإنلاين)."""
    if not settings.get("enable_guest"):
        return
    caller = message.guest_bot_caller_user
    if caller is None:
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
        pass
