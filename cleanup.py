"""تنظيف الألعاب العالقة + تدوير المواسم + تتويج الفائزين — عبر Piggyback."""
import asyncio
import logging
import time

from aiogram import BaseMiddleware

import config
import settings
import store

_MIN_INTERVAL = 30
_BATCH = 20
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


def _mention(uid, name):
    safe = (name or str(uid)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={uid}">{safe}</a>'


async def process_coronation(bot):
    """عند انتهاء موسم: يرسل الفائزين (أسماء + يوزرات + روابط) للمالك فقط."""
    pending = store.pop_pending_coronation()
    if not pending or not pending.get("top"):
        return
    medals = ["🥇 المركز الأول", "🥈 المركز الثاني", "🥉 المركز الثالث",
              "4️⃣ المركز الرابع", "5️⃣ المركز الخامس"]
    lines = [f"🏆 انتهى الموسم {pending.get('number', '؟')}! الفائزون:\n"]
    for i, c in enumerate(pending["top"][:5]):
        uid = c.get("id")
        uname = ""
        try:
            chat = await bot.get_chat(uid)
            if getattr(chat, "username", None):
                uname = f" @{chat.username}"
        except Exception:
            pass
        prize = f" — 🎁 {c['prize']}" if c.get("prize") else ""
        lines.append(f"{medals[i]}: {_mention(uid, c.get('name', '?'))}{uname} "
                     f"⭐{c.get('points', 0)}{prize}")
        lines.append(f"   <code>{uid}</code>")
    try:
        await bot.send_message(config.OWNER_ID, "\n".join(lines))
        logging.info("coronation sent to owner: season %s", pending.get("number"))
    except Exception:
        logging.exception("coronation announce failed")


async def _piggyback(bot):
    try:
        store.maybe_rollover_season()
    except Exception:
        logging.exception("season rollover failed")
    try:
        await process_coronation(bot)
    except Exception:
        logging.exception("coronation failed")
    try:
        await cleanup_stale_games(bot)
    except Exception:
        logging.exception("stale cleanup failed")


class StaleGameCleanupMiddleware(BaseMiddleware):
    """يشغّل (تنظيف + تدوير موسم + تتويج) انتهازياً عند وصول تحديث، مع خنق."""

    async def __call__(self, handler, event, data):
        global _last_run
        now = time.monotonic()
        if now - _last_run >= _MIN_INTERVAL:
            _last_run = now
            bot = data.get("bot")
            if bot is not None:
                t = asyncio.create_task(_piggyback(bot))
                _tasks.add(t)
                t.add_done_callback(_tasks.discard)
        return await handler(event, data)
