"""مكافأة أصحاب أعلى النقاط — أمر للمالك فقط: /reward"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import settings
import store

router = Router()
_MEDALS = ["🥇", "🥈", "🥉"]


@router.message(Command("reward"), F.from_user.id == config.OWNER_ID)
async def reward_top(message: Message):
    rewards = settings.get("reward_top") or []
    if not rewards:
        await message.answer("لا توجد مكافآت معرّفة (reward_top فارغ).")
        return
    top = store.top_users(len(rewards))
    if not top:
        await message.answer("لا يوجد لاعبون بعد.")
        return
    lines = ["🏆 تم توزيع المكافآت:"]
    for i, u in enumerate(top):
        pts = int(rewards[i])
        store.add_bonus(u["id"], pts)
        medal = _MEDALS[i] if i < len(_MEDALS) else f"#{i + 1}"
        lines.append(f"{medal} {u['name']}: +{pts} (كان {u['points']})")
    await message.answer("\n".join(lines))
    logging.info("reward_top distributed by owner %s", message.from_user.id)
