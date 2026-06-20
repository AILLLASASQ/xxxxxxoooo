"""مراقب مهلة الدور: من لا يتحرّك خلال turn_timeout يخسر، والخصم يفوز.

لوب خلفي كل turn_check_interval ثانية. يعمل بدقّة لأن المؤقّت يبدأ دائماً
بعد حركة (طلب وارد يُبقي Render مستيقظاً). وضع البوت مستثنى.
"""
import asyncio
import logging

import render
import settings
import store


async def _announce(bot, data):
    text, kb = render.render(data)
    imid = data.get("inline_message_id")
    if imid:
        await bot.edit_message_text(text=text, inline_message_id=imid, reply_markup=kb)
        return
    if data.get("mode") == "random":
        for chat_id, msg_id in ((data.get("x_chat_id"), data.get("x_msg_id")),
                                (data.get("o_chat_id"), data.get("o_msg_id"))):
            if chat_id and msg_id:
                try:
                    await bot.edit_message_text(
                        text=text, chat_id=chat_id, message_id=msg_id, reply_markup=kb)
                except Exception:
                    logging.exception("timeout announce random failed")
        return
    if data.get("chat_id") and data.get("message_id"):
        await bot.edit_message_text(
            text=text, chat_id=data["chat_id"], message_id=data["message_id"],
            reply_markup=kb)


async def check_turn_timeouts(bot):
    if int(settings.get("turn_timeout") or 0) <= 0:
        return
    games = store.fetch_timed_out_games(limit=50)[:20]
    for g in games:
        gid = g.get("_gid")
        try:
            ok, _ = store.finalize_timeout(gid)
            if not ok:
                continue
            store.award_result(gid, allow_points=True)
            fresh = store.get_game(gid)
            if fresh:
                await _announce(bot, fresh)
                logging.info("turn timeout: game %s won by %s",
                             gid, fresh.get("winner"))
        except Exception:
            logging.exception("turn timeout handling failed: %s", gid)


async def turn_watch_loop(bot):
    while True:
        try:
            await check_turn_timeouts(bot)
        except Exception:
            logging.exception("turn_watch_loop iteration failed")
        interval = max(1, int(settings.get("turn_check_interval") or 3))
        await asyncio.sleep(interval)
