"""منطق اللعب الأساسي عبر كل الأوضاع."""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import keyboards
import moderation
import render
import settings
import store

router = Router()


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


async def _edit_both(bot: Bot, data):
    text, kb = render.render(data)
    for ck, mk in (("x_chat_id", "x_msg_id"), ("o_chat_id", "o_msg_id")):
        try:
            await bot.edit_message_text(
                text=text, chat_id=data[ck], message_id=data[mk], reply_markup=kb)
        except Exception:
            pass


async def _update_view(bot: Bot, call: CallbackQuery, data):
    if data.get("mode") == "random":
        await _edit_both(bot, data)
        return
    text, kb = render.render(data)
    if call.inline_message_id:
        await bot.edit_message_text(
            text=text, inline_message_id=call.inline_message_id, reply_markup=kb)
    else:
        await call.message.edit_text(text, reply_markup=kb)


def _finalize_points(gid, data):
    """احتساب النقاط مع حدّ تجميع النقاط من نفس الخصم (اتجاهي، انتصارات فقط).

    يرجع (allowed, capped_user): capped_user هو من بلغ حدّه (لتنبيهه) أو None.
    """
    if data.get("mode") == "bot":
        store.award_result(gid)
        return True, None

    px, po = data.get("player_x"), data.get("player_o")
    winner = data.get("winner")
    cap = int(settings.get("pair_points_limit") or 0)

    # لا حدّ، أو ليس فوزاً (تعادل) → احتساب عادي
    if not cap or winner not in ("X", "O"):
        store.award_result(gid, allow_points=True)
        return True, None

    earner, opp = (px, po) if winner == "X" else (po, px)

    if earner and opp and moderation.pair_points(earner, opp) >= cap:
        store.award_result(gid, allow_points=False)
        return False, earner

    store.award_result(gid, allow_points=True)
    moderation.add_pair_points(earner, opp, settings.get("points_win"))
    return True, None


@router.message(Command("xo"))
async def cmd_xo(message: Message):
    if not settings.get("enable_pvp"):
        await message.answer("وضع المجموعات معطّل حالياً.")
        return
    store.ensure_user(message.from_user.id, _name(message.from_user))
    gid, data = store.create_game(
        mode="pvp", player_x=message.from_user.id, name_x=_name(message.from_user),
        chat_id=message.chat.id)
    text, _ = render.render(data)
    sent = await message.answer(text, reply_markup=keyboards.join_keyboard(gid))
    store.db().collection("games").document(gid).update({"message_id": sent.message_id})


@router.callback_query(F.data == "mode:bot")
async def cb_vs_bot(call: CallbackQuery):
    if not settings.get("enable_vs_bot"):
        await call.answer("وضع البوت معطّل حالياً.", show_alert=True)
        return
    store.ensure_user(call.from_user.id, _name(call.from_user))
    gid, data = store.create_game(
        mode="bot", player_x=call.from_user.id, name_x=_name(call.from_user),
        chat_id=call.message.chat.id)
    data["player_o"] = 0
    data["name_o"] = "🤖 البوت"
    store.db().collection("games").document(gid).update(
        {"player_o": 0, "name_o": "🤖 البوت"})
    text, kb = render.render(data)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("j:"))
async def cb_join(call: CallbackQuery, bot: Bot):
    gid = call.data.split(":", 1)[1]
    store.ensure_user(call.from_user.id, _name(call.from_user))
    ok, data, reason = store.join_game(gid, call.from_user.id, _name(call.from_user))
    if not ok:
        await call.answer(reason, show_alert=True)
        return
    await _update_view(bot, call, data)
    await call.answer("انضممت! ابدأ اللعب.")


@router.callback_query(F.data.startswith("m:"))
async def cb_move(call: CallbackQuery, bot: Bot):
    _, gid, cell = call.data.split(":")
    ok, data, reason = store.apply_move(gid, call.from_user.id, int(cell))
    if not ok:
        await call.answer(reason, show_alert=True)
        return

    if data.get("mode") == "bot" and not data.get("finalized") and data["turn"] == "O":
        data = store.bot_move(gid)

    await _update_view(bot, call, data)

    if data.get("finalized"):
        allowed, capped_user = _finalize_points(gid, data)
        if not allowed and capped_user == call.from_user.id:
            await call.answer(
                "انتهت اللعبة 🎯\n\nبلغت الحد الأقصى من النقاط ضد هذا الخصم اليوم.\n"
                "العب مع أشخاص آخرين! 🔁",
                show_alert=True)
        else:
            await call.answer("انتهت اللعبة 🎯")
    else:
        await call.answer()
