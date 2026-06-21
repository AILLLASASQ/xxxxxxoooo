"""لوحة تحكم المالك — تعديل كل شيء حياً من داخل تيليجرام."""
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import cleanup
import config
import moderation
import settings
import store

router = Router()
_MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def is_owner(user_id):
    return user_id == config.OWNER_ID


class EditState(StatesGroup):
    waiting_value = State()


NUMERIC = {
    "points_win": "نقاط الفوز",
    "points_draw": "نقاط التعادل",
    "points_loss": "نقاط الخسارة",
    "points_floor": "أدنى رصيد (أرضية)",
    "daily_limit": "الحد اليومي للمباريات",
    "pair_points_limit": "حد نقاط نفس الخصم/يوم",
    "stale_timeout": "مهلة حذف اللعبة (ث)",
    "turn_timeout": "مهلة الدور (ث، 0=إيقاف)",
    "turn_check_interval": "تردد فحص المهلة (ث)",
    "leaderboard_size": "عدد المعروضين",
    "season_days": "مدة الموسم (أيام)",
    "tier_silver": "عتبة الفضة",
    "tier_gold": "عتبة الذهب",
    "tier_diamond": "عتبة الماس",
}
TEXTS = {
    "text_welcome": "نص الترحيب",
    "text_win": "نص الفوز ({name})",
    "text_draw": "نص التعادل",
    "text_your_turn": "نص الدور ({name})",
    "text_expired": "نص انتهاء اللعبة",
    "text_timeout_win": "نص الفوز بالوقت ({name})",
}
TOGGLES = {
    "enable_pvp": "وضع المجموعات",
    "enable_vs_bot": "وضع البوت",
    "enable_inline": "وضع الإنلاين",
    "enable_guest": "وضع الضيف (Guest)",
}
BOT_POINTS = {
    "bot_win_easy": "فوز سهل",
    "bot_win_medium": "فوز متوسط",
    "bot_win_hard": "فوز صعب",
}


def panel():
    rows = [
        [InlineKeyboardButton(text="🔢 الأرقام", callback_data="a:points"),
         InlineKeyboardButton(text="📝 النصوص", callback_data="a:texts")],
        [InlineKeyboardButton(text="🎁 الجوائز", callback_data="a:rewards"),
         InlineKeyboardButton(text="🤖 نقاط البوت", callback_data="a:botpts")],
        [InlineKeyboardButton(text="🎚️ الأوضاع", callback_data="a:toggles"),
         InlineKeyboardButton(text="📈 إحصائيات", callback_data="a:stats")],
        [InlineKeyboardButton(text="🛡️ الإشراف", callback_data="a:mod")],
        [InlineKeyboardButton(text="🏁 إنهاء الموسم الآن", callback_data="a:endseason")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_row():
    return [InlineKeyboardButton(text="« رجوع", callback_data="a:back")]


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_owner(message.from_user.id):
        return
    await message.answer("⚙️ لوحة تحكم المالك:", reply_markup=panel())


@router.callback_query(F.data == "a:points")
async def a_points(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rows = [[InlineKeyboardButton(
        text=f"{label}: {settings.get(key)}", callback_data=f"set:{key}")]
        for key, label in NUMERIC.items()]
    rows.append(_back_row())
    await call.message.edit_text(
        "اختر القيمة لتعديلها:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "a:texts")
async def a_texts(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rows = [[InlineKeyboardButton(text=label, callback_data=f"set:{key}")]
            for key, label in TEXTS.items()]
    rows.append(_back_row())
    await call.message.edit_text(
        "اختر النص لتعديله:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "a:rewards")
async def a_rewards(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    prizes = settings.get("reward_prizes") or []
    rows = []
    for i in range(5):
        cur = prizes[i] if i < len(prizes) and prizes[i] else "غير محددة"
        rows.append([InlineKeyboardButton(
            text=f"{_MEDALS[i]} {cur}", callback_data=f"setprize:{i + 1}")])
    rows.append(_back_row())
    await call.message.edit_text(
        "🎁 اضغط مركزاً لتعديل جائزته:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("setprize:"))
async def a_setprize(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rank = call.data.split(":", 1)[1]
    await state.update_data(key=f"__prize_{rank}")
    await state.set_state(EditState.waiting_value)
    await call.message.answer(
        f"أرسل نص جائزة المركز {rank} (أو أرسل - للحذف):")
    await call.answer()


@router.callback_query(F.data == "a:botpts")
async def a_botpts(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rows = [[InlineKeyboardButton(
        text=f"{label}: {settings.get(key)}", callback_data=f"set:{key}")]
        for key, label in BOT_POINTS.items()]
    rows.append(_back_row())
    await call.message.edit_text(
        "نقاط الفوز حسب مستوى البوت:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "a:toggles")
async def a_toggles(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rows = []
    for key, label in TOGGLES.items():
        state = "✅" if settings.get(key) else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{state} {label}", callback_data=f"tg:{key}")])
    rows.append(_back_row())
    await call.message.edit_text(
        "اضغط للتبديل:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("tg:"))
async def a_toggle_set(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    key = call.data.split(":", 1)[1]
    settings.update(key, not settings.get(key))
    await a_toggles(call)


@router.callback_query(F.data == "a:stats")
async def a_stats(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    users = store.db().collection("users").count().get()
    games = store.db().collection("games").count().get()
    n_users = users[0][0].value if users else 0
    n_games = games[0][0].value if games else 0
    await call.message.edit_text(
        f"📈 إحصائيات:\n\nاللاعبون: {n_users}\nالألعاب: {n_games}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[_back_row()]))
    await call.answer()


@router.callback_query(F.data == "a:endseason")
async def a_end_season(call: CallbackQuery, bot: Bot):
    if not is_owner(call.from_user.id):
        return await call.answer()
    old = store.force_end_season()
    try:
        await cleanup.process_coronation(bot)
    except Exception:
        pass
    await call.answer(f"✅ أُنهي الموسم {old} وبدأ موسم جديد.", show_alert=True)
    await call.message.edit_text("⚙️ لوحة تحكم المالك:", reply_markup=panel())


@router.callback_query(F.data == "a:back")
async def a_back(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    await call.message.edit_text("⚙️ لوحة تحكم المالك:", reply_markup=panel())
    await call.answer()


@router.callback_query(F.data.startswith("set:"))
async def a_set_start(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer()
    key = call.data.split(":", 1)[1]
    await state.update_data(key=key)
    await state.set_state(EditState.waiting_value)
    label = NUMERIC.get(key) or TEXTS.get(key) or BOT_POINTS.get(key) or key
    await call.message.answer(f"أرسل القيمة الجديدة لـ: {label}")
    await call.answer()


@router.message(EditState.waiting_value)
async def a_set_value(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    key = data.get("key", "")
    value = message.text or ""

    if key.startswith("__prize_"):
        rank = int(key.rsplit("_", 1)[-1])
        prizes = list(settings.get("reward_prizes") or [])
        while len(prizes) < 5:
            prizes.append("")
        prizes[rank - 1] = "" if value.strip() in ("-", "") else value.strip()
        settings.update("reward_prizes", prizes)
        await state.clear()
        shown = prizes[rank - 1] or "(محذوفة)"
        await message.answer(f"✅ جائزة المركز {rank}: {shown}", reply_markup=panel())
        return

    if key in NUMERIC or key in BOT_POINTS:
        try:
            value = int(value)
        except ValueError:
            await message.answer("أرسل رقماً صحيحاً.")
            return
    settings.update(key, value)
    await state.clear()
    await message.answer(f"✅ تم التحديث: {key} = {value}", reply_markup=panel())


# ===== الإشراف: حظر / رفع حظر / قائمة =====
async def _resolve_target(message, command, bot):
    """يرجع (uid, name, rest) من رد على رسالة أو @يوزر أو آيدي."""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.full_name, (command.args or "").strip()
    args = (command.args or "").split(maxsplit=1)
    if not args:
        return None, None, ""
    tok = args[0]
    rest = args[1].strip() if len(args) > 1 else ""
    if tok.lstrip("-").isdigit():
        return int(tok), None, rest
    uname = tok.lstrip("@")
    try:
        chat = await bot.get_chat(f"@{uname}")
        return chat.id, getattr(chat, "full_name", None) or uname, rest
    except Exception:
        return None, None, rest


def _banned_view():
    banned = moderation.list_banned(50)
    if not banned:
        return "🛡️ لا يوجد محظورون حالياً.", InlineKeyboardMarkup(
            inline_keyboard=[_back_row()])
    lines = ["🛡️ المحظورون:\n"]
    rows = []
    for b in banned:
        r = f" — {b['reason']}" if b.get("reason") else ""
        lines.append(f"• {b['name']} ({b['id']}){r}")
        rows.append([InlineKeyboardButton(
            text=f"✅ رفع حظر {b['name']}", callback_data=f"unban:{b['id']}")])
    rows.append(_back_row())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


_MOD_HELP = ("\n\n— الأوامر —\n/ban (رد/@يوزر/آيدي) [سبب]\n"
             "/unban (رد/@يوزر/آيدي)\n/banned")


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, bot: Bot):
    if not is_owner(message.from_user.id):
        return
    uid, name, reason = await _resolve_target(message, command, bot)
    if uid is None:
        await message.answer(
            "الصيغة:\n/ban <آيدي أو @يوزر> [سبب]\n"
            "أو رُدّ على رسالة المخالف بـ /ban [سبب]")
        return
    if uid == config.OWNER_ID:
        await message.answer("لا يمكنك حظر المالك 🙂")
        return
    if not name:
        name = (store.get_user(uid) or {}).get("name", str(uid))
    moderation.ban_user(uid, name, reason)
    txt = f"🚫 حُظر {name} ({uid})."
    if reason:
        txt += f"\nالسبب: {reason}"
    await message.answer(txt)


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, bot: Bot):
    if not is_owner(message.from_user.id):
        return
    uid, _, _ = await _resolve_target(message, command, bot)
    if uid is None:
        await message.answer("الصيغة: /unban <آيدي أو @يوزر> أو رُدّ بـ /unban")
        return
    moderation.unban_user(uid)
    await message.answer(f"✅ رُفع الحظر عن {uid}.")


@router.message(Command("banned"))
async def cmd_banned(message: Message):
    if not is_owner(message.from_user.id):
        return
    text, kb = _banned_view()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "a:mod")
async def a_mod(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    text, kb = _banned_view()
    await call.message.edit_text(text + _MOD_HELP, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("unban:"))
async def a_unban(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    try:
        moderation.unban_user(int(call.data.split(":", 1)[1]))
    except Exception:
        pass
    await call.answer("✅ رُفع الحظر", show_alert=True)
    text, kb = _banned_view()
    try:
        await call.message.edit_text(text + _MOD_HELP, reply_markup=kb)
    except Exception:
        pass
