"""تنظيف الألعاب العالقة عبر Piggyback على التحديثات الواردة.

سقف صارم: أي لعبة غير منتهية مضى على إنشائها أكثر من stale_timeout تُمسح،
وتُعدَّل رسالتها إلى text_expired (حتى لو كانت نشطة).
يعمل بالـPiggyback لأن خدمة Render المجانية تنام، فلا يُعوَّل على لوب خلفي.
"""
import asyncio
import logging
import time

from aiogram import BaseMiddleware

import settings
import store

_MIN_INTERVAL = 30   # أقصى تردّد لتمريرة التنظيف (ثوانٍ)
_BATCH = 20          # حدّ الألعاب لكل تمريرة
_last_run = 0.0
_tasks = set()


async def _expire_one(bot, d, full_text):
    mode = d.get("mode")
    imid = d.get("inline_message_id")
    if imid:
        await bot.edit_message_text(text=full_text, inline_message_id=imid)
        return
    if mode == "random":
        for chat_id, msg_id in ((d.get("x_chat_id"), d.get("x_msg_id")),
                                (d.get("o_chat_id"), d.get("o_msg_id"))):
            if chat_id and msg_id:
                try:
                    await bot.edit_message_text(
                        text=full_text, chat_id=chat_id, message_id=msg_id)
                except Exception:
                    logging.exception("expire random msg failed")
        return
    if d.get("chat_id") and d.get("message_id"):
        await bot.edit_message_text(
            text=full_text, chat_id=d["chat_id"], message_id=d["message_id"])


async def cleanup_stale_games(bot):
    timeout = int(settings.get("stale_timeout") or 0)
    if timeout <= 0:
        return
    stale = store.fetch_stale_games(timeout, limit=50)[:_BATCH]
    if not stale:
        return
    full_text = f"⭕❌ إكس أو\n\n{settings.get('text_expired')}"
    n = 0
    for d in stale:
        try:
            await _expire_one(bot, d, full_text)
        except Exception:
            logging.exception("expire game %s failed", d.get("_gid"))
        finally:
            store.delete_game(d["_gid"])
            n += 1
    logging.info("cleanup: expired %d stale game(s)", n)


class StaleGameCleanupMiddleware(BaseMiddleware):
    """يشغّل التنظيف انتهازياً (fire-and-forget) عند وصول تحديث، مع خنق."""

    async def __call__(self, handler, event, data):
        global _last_run
        now = time.monotonic()
        if now - _last_run >= _MIN_INTERVAL:
            _last_run = now
            bot = data.get("bot")
            if bot is not None:
                t = asyncio.create_task(cleanup_stale_games(bot))
                _tasks.add(t)
                t.add_done_callback(_tasks.discard)
        return await handler(event, data)
