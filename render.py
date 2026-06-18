"""بناء نص اللعبة ولوحتها — مشترك بين كل الأوضاع."""
import game
import keyboards
import settings


def render(data):
    board = game.board_from_str(data["board"])
    gid_kb = keyboards.board_keyboard(board, data["_gid"])
    if data.get("finalized"):
        result = data.get("winner")
        if result == "draw":
            text = settings.get("text_draw")
        else:
            win_name = data["name_x"] if result == "X" else data.get("name_o", "البوت")
            text = settings.get("text_win").format(name=win_name)
        return f"⭕❌ إكس أو\n\n{text}", gid_kb
    turn = data["turn"]
    cur_name = data["name_x"] if turn == "X" else (data.get("name_o") or "—")
    header = "⭕❌ إكس أو\n"
    players = f"❌ {data['name_x']}  ضد  ⭕ {data.get('name_o') or '⏳ بانتظار لاعب'}\n"
    turn_line = settings.get("text_your_turn").format(name=cur_name)
    return f"{header}{players}\n{turn_line}", gid_kb
