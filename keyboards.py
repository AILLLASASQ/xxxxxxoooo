"""بناء لوحات الأزرار."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SYMBOLS = {"X": "❌", "O": "⭕", "": "·"}


def board_keyboard(board, game_id):
    """لوح اللعب كأزرار. callback: m:{game_id}:{cell}"""
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            row.append(
                InlineKeyboardButton(
                    text=SYMBOLS[board[i]],
                    callback_data=f"m:{game_id}:{i}",
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def join_keyboard(game_id):
    """زر الانضمام للاعب الثاني (مجموعات / إنلاين). callback: j:{game_id}"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 انضم للعب", callback_data=f"j:{game_id}")]
        ]
    )


def bot_difficulty_menu():
    """اختيار مستوى صعوبة البوت قبل بدء اللعب."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 سهل", callback_data="bot:easy")],
        [InlineKeyboardButton(text="🟡 متوسط", callback_data="bot:medium")],
        [InlineKeyboardButton(text="🔴 صعب", callback_data="bot:hard")],
    ])


def main_menu():
    """قائمة اختيار الوضع في الخاص."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 خصم عشوائي", callback_data="mm:find")],
            [InlineKeyboardButton(text="🤖 العب ضد البوت", callback_data="mode:bot")],
            [InlineKeyboardButton(text="🏆 لوحة الصدارة", callback_data="board:show")],
            [InlineKeyboardButton(text="📊 نقاطي", callback_data="me:show")],
        ]
    )
