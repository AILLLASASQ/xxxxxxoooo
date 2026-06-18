"""لوحة تحكم المالك — تعديل كل شيء حياً من داخل تيليجرام."""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import settings
import store

router = Router()


def is_owner(user_id):
    return user_id == config.OWNER_ID


class EditState(StatesGroup):
    waiting_value = State()


# المفاتيح القابلة للتعديل كرقم
NUMERIC = {
    "points_win": "نقاط الفوز",
    "points_draw": "نقاط التعادل",
    "points_loss": "نقاط الخسارة",
    "daily_bonus": "مكافأة يومية",
    "daily_limit": "الحد اليومي للمباريات",
    "pair_limit": "حد مباريات نفس الخصم",
}
# المفاتيح النصية
TEXTS = {
    "text_welcome": "نص الترحيب",
    "text_win": "نص الفوز (استخدم {name})",
    "text_draw": "نص التعادل",
}
TOGGLES = {
    "enable_pvp": "وضع المجموعات",
    "enable_vs_bot": "وضع البوت",
    "enable_inline": "وضع الإنلاين",
}


def panel():
    rows = [
        [InlineKeyboardButton(text="🔢 تعديل النقاط", callback_data="a:points")],
        [InlineKeyboardButton(text="📝 تعديل النصوص", callback_data="a:texts")],
        [InlineKeyboardButton(text="🎚️ تفعيل/تعطيل الأوضاع", callback_data="a:toggles")],
        [InlineKeyboardButton(text="🤖 صعوبة البوت", callback_data="a:diff")],
        [InlineKeyboardButton(text="📈 إحصائيات", callback_data="a:stats")],
        [InlineKeyboardButton(text="♻️ تصفير لوحة الصدارة", callback_data="a:reset")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    rows.append([InlineKeyboardButton(text="« رجوع", callback_data="a:back")])
    await call.message.edit_text(
        "اختر القيمة لتعديلها:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "a:texts")
async def a_texts(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    rows = [[InlineKeyboardButton(text=label, callback_data=f"set:{key}")]
            for key, label in TEXTS.items()]
    rows.append([InlineKeyboardButton(text="« رجوع", callback_data="a:back")])
    await call.message.edit_text(
        "اختر النص لتعديله:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
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
    rows.append([InlineKeyboardButton(text="« رجوع", callback_data="a:back")])
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


@router.callback_query(F.data == "a:diff")
async def a_diff(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer()
    cur = settings.get("bot_difficulty")
    new = "easy" if cur == "hard" else "hard"
    settings.update("bot_difficulty", new)
    await call.answer(f"صعوبة البوت الآن: {new}", show_alert=True)


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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="« رجوع", callback_data="a:back")]]))
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


# ---------- إدخال قيمة جديدة عبر FSM ----------
@router.callback_query(F.data.startswith("set:"))
async def a_set_start(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer()
    key = call.data.split(":", 1)[1]
    await state.update_data(key=key)
    await state.set_state(EditState.waiting_value)
    label = NUMERIC.get(key) or TEXTS.get(key) or key
    await call.message.answer(f"أرسل القيمة الجديدة لـ: {label}")
    await call.answer()


@router.message(EditState.waiting_value)
async def a_set_value(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    key = data["key"]
    value = message.text
    if key in NUMERIC:
        try:
            value = int(value)
        except ValueError:
            await message.answer("أرسل رقماً صحيحاً.")
            return
    settings.update(key, value)
    await state.clear()
    await message.answer(f"✅ تم التحديث: {key} = {value}", reply_markup=panel())

