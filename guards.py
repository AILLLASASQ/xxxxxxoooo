"""حارس: يمنع من لا يملك @username من استخدام البوت (المالك مستثنى)."""
from aiogram import BaseMiddleware

import config

_MSG = ("🚫 لاستخدام البوت يجب أن يكون لديك اسم مستخدم (@username) في تيليجرام.\n"
        "الإعدادات ‹ اسم المستخدم، عيّنه ثم أعد المحاولة.")


def _extract(update):
    for attr in ("message", "edited_message", "callback_query",
                 "inline_query", "chosen_inline_result"):
        obj = getattr(update, attr, None)
        if obj is not None:
            return getattr(obj, "from_user", None), attr, obj
    return None, None, None


class RequireUsernameMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user, kind, obj = _extract(event)
        if (user is not None and not user.is_bot and not user.username
                and user.id != config.OWNER_ID):
            try:
                if kind == "callback_query":
                    await obj.answer(_MSG, show_alert=True)
                elif kind == "inline_query":
                    await obj.answer([], cache_time=1, is_personal=True)
                elif kind in ("message", "edited_message"):
                    if not getattr(obj, "guest_query_id", None):
                        await obj.answer(_MSG)
            except Exception:
                pass
            return
        return await handler(event, data)
