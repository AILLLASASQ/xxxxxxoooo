"""لوحة تحكم المالك — تعديل كل شيء حياً من داخل تيليجرام."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import settings
import store

router = Router()
_MEDALS = ["🥇", "🥈", "🥉"]


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
        [InlineKeyboardButton(text="🔢 الأرقام (نقاط ومهلات)", callback_data="a:points")],
        [InlineKeyboardButton(text="📝 تعديل النصوص", callback_data="a:texts")],
        [InlineKeyboardButton(text="🎁 الجوائز", callback_data="a:rewards")],
        [InlineKeyboardButton(text="🤖 نقاط البوت", callback_data="a:botpts")],
        [InlineKeyboardButton(text="🎚️ تفعيل/تعطيل الأوضاع", callback_data="a:toggles")],
        [InlineKeyboardButton(text="📈 إحصائيات", callback_data="a:stats")],
        [InlineKeyboardButton(text="♻️ تصفير لوحة الصدارة", callback_data="a:reset")],
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
    for i in range(3):
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


@router.callback_query(F.data == "a:reset")
async def a_reset(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    batch = store.db().batch()
    for snap in store.db().collection("users").stream():
        batch.update(snap.reference, {"points": 0, "wins": 0, "losses": 0, "draws": 0})
    batch.commit()
    await call.answer("تم تصفير لوحة الصدارة ✅", show_alert=True)


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
        while len(prizes) < 3:
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
