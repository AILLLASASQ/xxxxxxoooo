"""المطابقة العشوائية: زر "خصم عشوائي" + بحث/إلغاء + مصالحة الطابور.

طبقات إلغاء البحث المنتهي (يكفي أن تعمل واحدة):
  1) مهمة خلفية دورية (وقت اليقظة).
  2) middleware يُنظّف كل عدد من التحديثات الواردة (Piggyback).
الكل يستدعي دالة واحدة: reconcile_queue.
"""
import asyncio
import logging
import time

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, TelegramObject)

import keyboards
import matchmaking
import moderation
import render
import settings
import store

router = Router()

SEARCH_TIMEOUT = 60          # ثانية قبل إلغاء البحث تلقائياً
PIGGYBACK_EVERY = 20         # كل كم تحديث وارد نُنظّف الطابور


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


def _cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء البحث", callback_data="mm:cancel")]])


# ===== الأساس المشترك: دالة المصالحة (#7) =====
async def reconcile_queue(bot: Bot):
    """تُنهي وتُبلّغ كل من تجاوز مهلة البحث. يستدعيها كل المُشغّلات."""
    for s in matchmaking.stale_searchers(SEARCH_TIMEOUT):
        matchmaking.queue_remove(s["user_id"])
        try:
            await bot.edit_message_text(
                "😔 لم نجد لك خصماً الآن. حاول لاحقاً.",
                chat_id=s["chat_id"], message_id=s["msg_id"],
                reply_markup=keyboards.main_menu())
        except Exception:
            pass


# ===== Piggyback: تنظيف عابر على التحديثات الواردة (#10) =====
class QueueCleanupMiddleware(BaseMiddleware):
    """كل PIGGYBACK_EVERY تحديث، يُشغّل مصالحة الطابور في الخلفية."""

    def __init__(self, every=PIGGYBACK_EVERY):
        self.every = every
        self.count = 0

    async def __call__(self, handler, event: TelegramObject, data):
        self.count += 1
        if self.count % self.every == 0:
            bot = data.get("bot")
            if bot is not None:
                asyncio.create_task(reconcile_queue(bot))
        return await handler(event, data)


async def _send_both(bot: Bot, data):
    """عرض اللوح لدى اللاعبَين بتعديل رسالة كل واحد في محادثته."""
    text, kb = render.render(data)
    for ck, mk in (("x_chat_id", "x_msg_id"), ("o_chat_id", "o_msg_id")):
        try:
            await bot.edit_message_text(
                text=text, chat_id=data[ck], message_id=data[mk], reply_markup=kb)
        except Exception:
            try:
                sent = await bot.send_message(data[ck], text, reply_markup=kb)
                store.db().collection("games").document(data["_gid"]).update(
                    {mk: sent.message_id})
                data[mk] = sent.message_id
            except Exception as e:
                logging.warning("send_both: %s", e)


@router.callback_query(F.data == "mm:find")
async def mm_find(call: CallbackQuery, bot: Bot):
    uid = call.from_user.id
    name = _name(call.from_user)
    store.ensure_user(uid, name)

    if moderation.is_banned(uid):
        await call.answer("أنت محظور من اللعب.", show_alert=True)
        return

    # === حارس الضغط المزدوج (#8) ===
    existing = matchmaking.queue_get(uid)
    if existing:
        fresh = int(time.time()) - int(existing.get("joined_at", 0)) < SEARCH_TIMEOUT
        if fresh:
            await call.answer("أنت بالفعل في قائمة البحث ⏳", show_alert=True)
            return
        matchmaking.queue_remove(uid)  # إدخال قديم منتهٍ → اسمح ببحث جديد

    limit = settings.get("daily_limit")
    if moderation.at_daily_limit(uid, limit):
        await call.answer(f"وصلت الحد اليومي ({limit} مباراة).", show_alert=True)
        return

    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    opp = matchmaking.queue_try_match(uid, name, chat_id, msg_id)

    if opp is None:
        qsz = matchmaking.queue_size()
        await call.message.edit_text(
            f"🔍 جارٍ البحث عن خصم...\n\n👥 في الطابور: {qsz}\n\n"
            f"⏳ يُلغى تلقائياً بعد {SEARCH_TIMEOUT} ثانية.",
            reply_markup=_cancel_kb())
        await call.answer("يبحث عن خصم...")
        return

    # وُجد خصم → أنشئ لعبة (المنتظِر = X، الداخل = O)
    moderation.bump_daily_match(uid)
    moderation.bump_daily_match(opp["user_id"])
    x = {"id": opp["user_id"], "name": opp["name"],
         "chat_id": opp["chat_id"], "msg_id": opp["msg_id"]}
    o = {"id": uid, "name": name, "chat_id": chat_id, "msg_id": msg_id}
    _, data = store.create_random_game(x, o)
    await _send_both(bot, data)
    await call.answer("✅ وُجد خصم!")


@router.callback_query(F.data == "mm:cancel")
async def mm_cancel(call: CallbackQuery):
    matchmaking.queue_remove(call.from_user.id)
    await call.message.edit_text("✅ تم إلغاء البحث.", reply_markup=keyboards.main_menu())
    await call.answer()


# ===== مهمة خلفية دورية (تستدعي نفس دالة المصالحة) =====
async def search_timeout_loop(bot: Bot):
    while True:
        try:
            await reconcile_queue(bot)
        except Exception as e:
            logging.warning("search_timeout_loop: %s", e)
        await asyncio.sleep(5)

