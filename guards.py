"""حارس: حظر + اشتراك إجباري + اشتراط @username (المالك مستثنى)."""
from aiogram import BaseMiddleware

import config
import moderation
import subs

_MSG = ("🚫 لاستخدام البوت يجب أن يكون لديك اسم مستخدم (@username) في تيليجرام.\n"
        "الإعدادات ‹ اسم المستخدم، عيّنه ثم أعد المحاولة.")


def _extract(update):
    for attr in ("message", "edited_message", "callback_query",
                 "inline_query", "chosen_inline_result"):
        obj = getattr(update, attr, None)
        if obj is not None:
            return getattr(obj, "from_user", None), attr, obj
    return None, None, None


async def _block(kind, obj, text, markup=None):
    try:
        if kind == "callback_query":
            await obj.answer(text, show_alert=True)
        elif kind == "inline_query":
            await obj.answer([], cache_time=1, is_personal=True)
        elif kind in ("message", "edited_message"):
            if not getattr(obj, "guest_query_id", None):
                await obj.answer(text, reply_markup=markup)
    except Exception:
        pass


class RequireUsernameMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user, kind, obj = _extract(event)
        if user is not None and not user.is_bot and user.id != config.OWNER_ID:
            # 1) الحظر — يمنع من كل شيء حتى /start
            if moderation.is_banned(user.id):
                reason = moderation.ban_reason(user.id)
                msg = "🚫 أنت محظور من استخدام البوت."
                if reason:
                    msg += f"\nالسبب: {reason}"
                await _block(kind, obj, msg)
                return
            # 2) اشتراط @username
            if not user.username:
                await _block(kind, obj, _MSG)
                return
            # 3) الاشتراك الإجباري (مع استثناء زر التحقّق نفسه لتفادي القفل)
            is_check = (kind == "callback_query"
                        and getattr(obj, "data", "") == "fsub:check")
            if not is_check and subs.enabled():
                bot = data.get("bot")
                if bot is not None and not await subs.is_subscribed(bot, user.id):
                    await _block(kind, obj, subs.gate_text(), subs.gate_markup())
                    return
        return await handler(event, data)
