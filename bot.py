"""نقطة الدخول — يشغّل البوت عبر webhook على Render."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
import settings
from firebase_db import init_db
from handlers import admin, common, inline, matchmaking, play

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin.router)
dp.include_router(common.router)
dp.include_router(matchmaking.router)
dp.include_router(play.router)
dp.include_router(inline.router)

# تنظيف عابر للطابور كل عدد من التحديثات (Piggyback)
dp.update.outer_middleware(matchmaking.QueueCleanupMiddleware())


async def on_startup(app: web.Application):
    init_db()
    settings.load_settings()
    await bot.set_webhook(url=config.WEBHOOK_URL, drop_pending_updates=True,
                          allowed_updates=dp.resolve_used_update_types())
    # نخزّن مرجعاً قوياً للمهمة حتى لا يجمعها جامع المهملات فتتوقف
    app["timeout_task"] = asyncio.create_task(matchmaking.search_timeout_loop(bot))
    logging.info("Webhook set: %s", config.WEBHOOK_URL)


async def on_shutdown(app: web.Application):
    # لا نحذف الويب هوك حتى يبقى ثابتاً وتُوقظ الرسائلُ الخدمةَ
    task = app.get("timeout_task")
    if task:
        task.cancel()
    await bot.session.close()


async def health(request):
    return web.Response(text="ok")


def main():
    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
