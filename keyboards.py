"""بناء لوحات الأزرار."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SYMBOLS = {"X": "❌", "O": "⭕", "": "·"}


def board_keyboard(board, game_id):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            row.append(InlineKeyboardButton(
                text=SYMBOLS[board[i]], callback_data=f"m:{game_id}:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def join_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 انضم للعب", callback_data=f"j:{game_id}")]])


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 العب ضد البوت", callback_data="mode:bot")],
        [InlineKeyboardButton(text="🏆 لوحة الصدارة", callback_data="board:show")],
        [InlineKeyboardButton(text="📊 نقاطي", callback_data="me:show")],
    ])
