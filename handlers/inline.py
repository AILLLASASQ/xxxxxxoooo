"""وضع الإنلاين + الضيف: لعب إكس أو عبر يوزر البوت في أي محادثة."""
import logging
import re
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent,
                           Message)

import render
import settings
import store

router = Router()

_GUEST_COOLDOWN = 10  # ثوانٍ
_last_guest = {}      # user_id -> monotonic timestamp


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


def _guest_throttled(user_id):
    now = time.monotonic()
    last = _last_guest.get(user_id, 0.0)
    if now - last < _GUEST_COOLDOWN:
        return True
    _last_guest[user_id] = now
    if len(_last_guest) > 5000:
        cutoff = now - _GUEST_COOLDOWN
        for uid in [u for u, t in _last_guest.items() if t < cutoff]:
            _last_guest.pop(uid, None)
    return False


# سيمانتك موحّد: الرمز في الـcallback = الرمز الذي يأخذه الضاغط (المنضم).
# والـts = وقت إنشاء البطاقة لفحص انتهاء الصلاحية.
def _join_kb(gid, creator_id, joiner_sym, ts):
    emoji = "❌" if joiner_sym == "X" else "⭕"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=f"🎮 انضم كـ {emoji}",
        callback_data=f"ij:{gid}:{creator_id}:{joiner_sym}:{ts}")]])


def _choose_kb(gid, creator_id, ts):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌", callback_data=f"ij:{gid}:{creator_id}:X:{ts}"),
        InlineKeyboardButton(text="⭕", callback_data=f"ij:{gid}:{creator_id}:O:{ts}"),
    ]])


def _invite_text(creator_name, creator_sym):
    c = "❌" if creator_sym == "X" else "⭕"
    o = "⭕" if creator_sym == "X" else "❌"
    return (
        "⭕❌ إكس أو\n"
        f"{c} {creator_name}  ضد  {o} ⏳ بانتظار لاعب\n\n"
        f"اضغط (انضم كـ {o}) لبدء المباراة."
    )


def _guest_text(caller_name):
    return (
        "⭕❌ إكس أو\n"
        f"{caller_name} يدعوك للعب!\n\n"
        "اختر رمزك للانضمام: ❌ أو ⭕"
    )


_USERNAME_RE = re.compile(r"@([A-Za-z0-9_]{5,32})")


def _parse_target(q):
    if not q:
        return None
    m = _USERNAME_RE.search(q)
    return m.group(1).lower() if m else None


def _targeted_kb(gid, creator_id, target):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌", callback_data=f"tc:{gid}:{creator_id}:X:{target}"),
        InlineKeyboardButton(text="⭕", callback_data=f"tc:{gid}:{creator_id}:O:{target}"),
    ]])


def _targeted_text(creator_name, target, x_slot=None, o_slot=None):
    def who(slot):
        return slot["name"] if slot else "بانتظار…"
    return (
        "🎯 تحدٍّ موجّه!\n"
        f"{creator_name} يتحدّى @{target} ⚔️\n\n"
        f"❌: {who(x_slot)}\n⭕: {who(o_slot)}\n\n"
        "الطرفان فقط يمكنهما الاختيار — اختر رمزك:"
    )


def _targeted_text_from_doc(creator_id, target, d):
    cname = (store.get_user(creator_id) or {}).get("name", "المنشئ")
    return _targeted_text(cname, target, d.get("x"), d.get("o"))


@router.inline_query()
async def inline_xo(query: InlineQuery):
    if not settings.get("enable_inline"):
        await query.answer([], cache_time=1, is_personal=True)
        return

    store.ensure_user(query.from_user.id, _name(query.from_user))
    gid = store.new_game_id()
    cid = query.from_user.id
    cname = _name(query.from_user)
    ts = int(time.time())

    target = _parse_target(query.query)
    if target:
        result = InlineQueryResultArticle(
            id=f"tc-{gid}",
            title=f"🎯 تحدِّ @{target}",
            description="تحدٍّ موجّه — هو وحده من يقبل",
            input_message_content=InputTextMessageContent(
                message_text=_targeted_text(cname, target)),
            reply_markup=_targeted_kb(gid, cid, target),
        )
        await query.answer([result], cache_time=1, is_personal=True)
        return

    results = [
        InlineQueryResultArticle(
            id=f"{gid}-X",
            title="🎮 العب كـ ❌ (تبدأ أنت)",
            description="ترسل التحدي وتلعب بالرمز ❌",
            input_message_content=InputTextMessageContent(
                message_text=_invite_text(cname, "X")),
            reply_markup=_join_kb(gid, cid, "O", ts),
        ),
        InlineQueryResultArticle(
            id=f"{gid}-O",
            title="🎮 العب كـ ⭕ (يبدأ خصمك)",
            description="ترسل التحدي وتلعب بالرمز ⭕",
            input_message_content=InputTextMessageContent(
                message_text=_invite_text(cname, "O")),
            reply_markup=_join_kb(gid, cid, "X", ts),
        ),
    ]
    await query.answer(results, cache_time=1, is_personal=True)


@router.callback_query(F.data.startswith("ij:"))
async def inline_join(call: CallbackQuery, bot: Bot):
    try:
        _, gid, creator_id, sym, ts = call.data.split(":")
        creator_id = int(creator_id)
        ts = int(ts)
    except Exception:
        await call.answer("بيانات غير صالحة.", show_alert=True)
        return
    if sym not in ("X", "O"):
        await call.answer("بيانات غير صالحة.", show_alert=True)
        return

    # انتهاء صلاحية الدعوة (سقف صارم منذ إنشاء البطاقة)
    timeout = int(settings.get("stale_timeout") or 0)
    if timeout > 0 and int(time.time()) - ts > timeout:
        await call.answer("انتهت صلاحية هذه الدعوة.", show_alert=True)
        try:
            await bot.edit_message_text(
                text=f"⭕❌ إكس أو\n\n{settings.get('text_expired')}",
                inline_message_id=call.inline_message_id)
        except Exception:
            logging.exception("expire invite edit failed")
        return

    joiner = call.from_user
    if joiner.id == creator_id:
        await call.answer("لا يمكنك اللعب ضد نفسك، انتظر خصماً 🙂", show_alert=True)
        return

    existing = store.get_game(gid)
    if existing and existing.get("player_o"):
        await call.answer("اللعبة بدأت بالفعل.", show_alert=True)
        return

    store.ensure_user(joiner.id, _name(joiner))
    joiner_name = _name(joiner)
    creator = store.get_user(creator_id) or {}
    creator_name = creator.get("name", "اللاعب")

    # sym = رمز الضاغط (المنضم)؛ الطرف الآخر يأخذ المعاكس.
    # create_inline_game: الوسيط الأول = X، والثاني = O
    if sym == "X":
        data = store.create_inline_game(
            gid, joiner.id, joiner_name, creator_id, creator_name,
            call.inline_message_id)
    else:  # sym == "O"
        data = store.create_inline_game(
            gid, creator_id, creator_name, joiner.id, joiner_name,
            call.inline_message_id)

    text, kb = render.render(data)
    try:
        await bot.edit_message_text(
            text=text, inline_message_id=call.inline_message_id, reply_markup=kb)
    except Exception:
        logging.exception("inline_join edit failed")
    await call.answer("بدأت اللعبة!")


@router.callback_query(F.data.startswith("tc:"))
async def targeted_claim(call: CallbackQuery, bot: Bot):
    try:
        _, gid, creator_id, sym, target = call.data.split(":")
        creator_id = int(creator_id)
    except Exception:
        await call.answer("بيانات غير صالحة.", show_alert=True)
        return
    if sym not in ("X", "O"):
        await call.answer("بيانات غير صالحة.", show_alert=True)
        return

    p = call.from_user
    uname = (p.username or "").lower()
    if not (p.id == creator_id or (uname and uname == target)):
        await call.answer("هذا التحدي ليس لك ⛔", show_alert=True)
        return

    store.ensure_user(p.id, _name(p))
    status, d = store.claim_challenge_symbol(
        gid, sym, p.id, _name(p), call.inline_message_id)

    if status == "already":
        await call.answer("اخترت هذا الرمز بالفعل ✅")
        return
    if status == "taken":
        await call.answer("هذا الرمز محجوز، اختر الآخر 🔁", show_alert=True)
        return
    if status == "ready":
        x, o = d["x"], d["o"]
        data = store.create_inline_game(
            gid, x["id"], x["name"], o["id"], o["name"], call.inline_message_id)
        store.delete_challenge(gid)
        text, kb = render.render(data)
        try:
            await bot.edit_message_text(
                text=text, inline_message_id=call.inline_message_id, reply_markup=kb)
        except Exception:
            logging.exception("targeted start edit failed")
        await call.answer("بدأت اللعبة! 🎮")
        return
    try:
        await bot.edit_message_text(
            text=_targeted_text_from_doc(creator_id, target, d),
            inline_message_id=call.inline_message_id,
            reply_markup=_targeted_kb(gid, creator_id, target))
    except Exception:
        logging.exception("targeted waiting edit failed")
    await call.answer("تم اختيار رمزك ✅")


# ===== Guest Mode: الرد عند ذكر يوزر البوت دون عضوية (خاص + مجموعات) =====
@router.guest_message()
async def guest_xo(message: Message):
    if not settings.get("enable_guest"):
        return
    caller = message.from_user
    if caller is None or not message.guest_query_id:
        return
    if caller.is_bot:
        return
    if not caller.username:
        return
    if _guest_throttled(caller.id):
        return

    store.ensure_user(caller.id, _name(caller))
    gid = store.new_game_id()
    ts = int(time.time())
    result = InlineQueryResultArticle(
        id=gid,
        title="🎮 ابدأ لعبة إكس أو",
        description="العب ضد من ذكر البوت — اختر ❌ أو ⭕",
        input_message_content=InputTextMessageContent(
            message_text=_guest_text(_name(caller))),
        reply_markup=_choose_kb(gid, caller.id, ts),
    )
    try:
        await message.answer_guest_query(result=result)
    except Exception:
        logging.exception("guest_xo answer failed")
