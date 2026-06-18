"""وضع الإنلاين: لعب إكس أو في أي محادثة."""
from aiogram import Router
from aiogram.types import (ChosenInlineResult, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent)

import game
import keyboards
import settings
import store

router = Router()


def _name(user):
    return user.full_name or (user.username and f"@{user.username}") or str(user.id)


@router.inline_query()
async def inline_xo(query: InlineQuery):
    if not settings.get("enable_inline"):
        await query.answer([], cache_time=1, is_personal=True)
        return
    gid = store.new_game_id()
    empty = game.board_to_str(game.new_board())
    preview = (f"⭕❌ إكس أو\n❌ {_name(query.from_user)}  ضد  ⏳ بانتظار لاعب\n\n"
               "اضغط (انضم للعب) لبدء المباراة.")
    result = InlineQueryResultArticle(
        id=gid, title="🎮 ابدأ لعبة إكس أو",
        description="العب ضد أي شخص في هذه المحادثة",
        input_message_content=InputTextMessageContent(message_text=preview),
        reply_markup=keyboards.join_keyboard(gid))
    store._pending_inline[gid] = (query.from_user.id, _name(query.from_user), empty)
    await query.answer([result], cache_time=1, is_personal=True)


@router.chosen_inline_result()
async def chosen_inline(chosen: ChosenInlineResult):
    gid = chosen.result_id
    pending = store._pending_inline.pop(gid, None)
    if not pending:
        return
    creator_id, creator_name, _ = pending
    store.ensure_user(creator_id, creator_name)
    data = {
        "mode": "inline",
        "board": game.board_to_str(game.new_board()),
        "turn": "X",
        "player_x": creator_id,
        "name_x": creator_name,
        "player_o": None,
        "name_o": None,
        "inline_message_id": chosen.inline_message_id,
        "winner": None,
        "finalized": False,
        "points_awarded": False,
    }
    store.db().collection("games").document(gid).set(data)
