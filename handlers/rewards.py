"""جوائز المتصدّرين (هدايا حقيقية). أوامر للمالك فقط:
  /setreward <المركز 1-3> <نص الجائزة>   — تعيين/مسح جائزة مركز
  /rewards                                — عرض الجوائز الحالية
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import config
import settings

router = Router()
_RANKS = 3
_MEDALS = ["🥇", "🥈", "🥉"]


@router.message(Command("setreward"), F.from_user.id == config.OWNER_ID)
async def set_reward(message: Message, command: CommandObject):
    args = (command.args or "").strip()
    parts = args.split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        await message.answer(
            "الصيغة:\n/setreward <المركز 1-3> <نص الجائزة>\n\n"
            "أمثلة:\n"
            "/setreward 1 بطاقة جوجل بلاي 20$\n"
            "/setreward 2 بطاقة 10$\n"
            "/setreward 1   (بلا نص = مسح جائزة المركز)")
        return
    rank = int(parts[0])
    if rank < 1 or rank > _RANKS:
        await message.answer(f"المركز يجب أن يكون بين 1 و {_RANKS}.")
        return
    text = parts[1].strip() if len(parts) > 1 else ""

    prizes = list(settings.get("reward_prizes") or [])
    while len(prizes) < _RANKS:
        prizes.append("")
    prizes[rank - 1] = text
    settings.update("reward_prizes", prizes)

    if text:
        await message.answer(f"✅ جائزة المركز {rank}: {text}")
    else:
        await message.answer(f"🗑️ تم مسح جائزة المركز {rank}.")
    logging.info("prize set rank=%s by owner", rank)


@router.message(Command("rewards"), F.from_user.id == config.OWNER_ID)
async def show_rewards(message: Message):
    prizes = settings.get("reward_prizes") or []
    lines = ["🎁 الجوائز الحالية:"]
    for i in range(_RANKS):
        p = prizes[i] if i < len(prizes) and prizes[i] else "— (غير محددة)"
        lines.append(f"{_MEDALS[i]} {p}")
    lines.append("\nلتعديل: /setreward <المركز> <النص>")
    await message.answer("\n".join(lines))
