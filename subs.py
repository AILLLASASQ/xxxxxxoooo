"""الاشتراك الإجباري في قناة المالك: فحص العضوية + كاش + معالجات."""
import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, ChatMemberUpdated,
                           InlineKeyboardButton, InlineKeyboardMarkup)

import config
import settings

router = Router()

_TTL = 300
_cache = {}  # uid -> (bool, expiry_monotonic)


def enabled():
    return bool(settings.get("enable_force_sub"))


def channel():
    return (settings.get("force_sub_channel") or "").strip()


def clear_cache(uid):
    _cache.pop(int(uid), None)


async def is_subscribed(bot, uid):
    if not enabled():
        return True
    ch = channel()
    if not ch:
        return True
    uid = int(uid)
    now = time.monotonic()
    hit = _cache.get(uid)
    if hit and hit[1] > now:
        return hit[0]
    ok = True
    try:
        m = await bot.get_chat_member(ch, uid)
        ok = m.status in ("creator", "administrator", "member", "restricted")
    except Exception:
        logging.exception("force-sub check failed (%s)", uid)
        ok = True  # fail-open: لا نقفل البوت كله لو فشل الفحص
    _cache[uid] = (ok, now + _TTL)
    if len(_cache) > 10000:
        _cache.clear()
    return ok


def gate_text():
    return (settings.get("force_sub_text")
            or "🚪 للّعب، اشترك في قناتنا أولاً ثم اضغط «✅ تحقّقت».")


def gate_markup():
    url = "https://t.me/" + channel().lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 اشترك في القناة", url=url)],
        [InlineKeyboardButton(text="✅ تحقّقت", callback_data="fsub:check")],
    ])


@router.callback_query(F.data == "fsub:check")
async def fsub_check(call: CallbackQuery, bot: Bot):
    clear_cache(call.from_user.id)
    if await is_subscribed(bot, call.from_user.id):
        await call.answer("✅ تم التحقق! يمكنك اللعب الآن.", show_alert=True)
        try:
            await call.message.edit_text("✅ أنت مشترك. اكتب /start للبدء.")
        except Exception:
            pass
    else:
        await call.answer("لم تشترك بعد ❌ اشترك ثم أعد المحاولة.", show_alert=True)


@router.my_chat_member()
async def on_bot_status(update: ChatMemberUpdated, bot: Bot):
    ch = channel().lstrip("@").lower()
    if not ch or (update.chat.username or "").lower() != ch:
        return
    if update.new_chat_member.status == "administrator":
        settings.update("enable_force_sub", True)
        try:
            await bot.send_message(
                config.OWNER_ID,
                f"✅ تم إضافة البوت مشرفاً في @{update.chat.username}، "
                f"وفُعّل الاشتراك الإجباري.")
        except Exception:
            logging.exception("fsub admin-added notify failed")


@router.chat_member()
async def on_member(update: ChatMemberUpdated, bot: Bot):
    ch = channel().lstrip("@").lower()
    if not ch or (update.chat.username or "").lower() != ch:
        return
    user = update.new_chat_member.user
    if user.is_bot:
        return
    old = update.old_chat_member.status
    new = update.new_chat_member.status
    if new in ("member", "administrator", "creator") and old in ("left", "kicked"):
        clear_cache(user.id)
        try:
            await bot.send_message(
                user.id, "✅ تم! أنت الآن مشترك ويمكنك اللعب. اكتب /start.")
        except Exception:
            pass  # المستخدم لم يبدأ البوت بعد
