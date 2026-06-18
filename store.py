"""طبقة البيانات: ألعاب ومستخدمون ونقاط — كل العمليات الحسّاسة داخل transaction."""
import secrets
import time

from google.cloud.firestore_v1 import Increment, transactional

import game
import settings
from firebase_db import db

_pending_inline = {}


def new_game_id():
    return secrets.token_urlsafe(6)


def create_game(mode, player_x, name_x, chat_id=None, message_id=None,
                inline_message_id=None):
    gid = new_game_id()
    data = {
        "mode": mode,
        "board": game.board_to_str(game.new_board()),
        "turn": "X",
        "player_x": player_x,
        "name_x": name_x,
        "player_o": None,
        "name_o": None,
        "chat_id": chat_id,
        "message_id": message_id,
        "inline_message_id": inline_message_id,
        "winner": None,
        "finalized": False,
        "created_at": int(time.time()),
    }
    db().collection("games").document(gid).set(data)
    data["_gid"] = gid
    return gid, data


def get_game(gid):
    snap = db().collection("games").document(gid).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    d["_gid"] = gid
    return d


def join_game(gid, player_o, name_o):
    ref = db().collection("games").document(gid)

    @transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return False, None, "اللعبة غير موجودة."
        d = snap.to_dict()
        if d.get("player_o"):
            return False, d, "اللعبة مكتملة بالفعل."
        if d.get("player_x") == player_o:
            return False, d, "لا يمكنك اللعب ضد نفسك."
        txn.update(ref, {"player_o": player_o, "name_o": name_o})
        d["player_o"] = player_o
        d["name_o"] = name_o
        d["_gid"] = gid
        return True, d, ""

    return _txn(db().transaction())


def apply_move(gid, user_id, cell):
    ref = db().collection("games").document(gid)

    @transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return False, None, "اللعبة غير موجودة."
        d = snap.to_dict()
        if d.get("finalized"):
            return False, d, "انتهت اللعبة."
        board = game.board_from_str(d["board"])
        turn = d["turn"]
        expected = d["player_x"] if turn == "X" else d["player_o"]
        if expected is None:
            return False, d, "ننتظر انضمام لاعب ثانٍ."
        if user_id != expected:
            return False, d, "ليس دورك."
        if cell < 0 or cell > 8 or board[cell]:
            return False, d, "خانة غير صالحة."
        board[cell] = turn
        result = game.winner(board)
        next_turn = "O" if turn == "X" else "X"
        update = {"board": game.board_to_str(board), "turn": next_turn}
        if result:
            update["winner"] = result
            update["finalized"] = True
        txn.update(ref, update)
        d.update(update)
        d["_gid"] = gid
        return True, d, ""

    return _txn(db().transaction())


def bot_move(gid):
    ref = db().collection("games").document(gid)
    d = get_game(gid)
    if not d or d.get("finalized"):
        return d
    board = game.board_from_str(d["board"])
    move = game.best_move(board, "O", "X", settings.get("bot_difficulty"))
    if move is None:
        return d
    board[move] = "O"
    result = game.winner(board)
    update = {"board": game.board_to_str(board), "turn": "X"}
    if result:
        update["winner"] = result
        update["finalized"] = True
    ref.update(update)
    d.update(update)
    return d


def ensure_user(user_id, name):
    ref = db().collection("users").document(str(user_id))
    if not ref.get().exists:
        ref.set({"name": name, "points": 0, "wins": 0,
                 "losses": 0, "draws": 0, "last_daily": 0})


def award_result(gid):
    gref = db().collection("games").document(gid)

    @transactional
    def _txn(txn):
        snap = gref.get(transaction=txn)
        if not snap.exists:
            return
        d = snap.to_dict()
        if not d.get("finalized") or d.get("points_awarded"):
            return
        if d.get("mode") == "bot":
            _apply_points(txn, d["player_x"], d["winner"], human_mark="X")
        else:
            _apply_points(txn, d["player_x"], d["winner"], human_mark="X")
            if d.get("player_o"):
                _apply_points(txn, d["player_o"], d["winner"], human_mark="O")
        txn.update(gref, {"points_awarded": True})

    _txn(db().transaction())


def _apply_points(txn, user_id, result, human_mark):
    ref = db().collection("users").document(str(user_id))
    if result == "draw":
        pts, field = settings.get("points_draw"), "draws"
    elif result == human_mark:
        pts, field = settings.get("points_win"), "wins"
    else:
        pts, field = settings.get("points_loss"), "losses"
    txn.set(ref, {"points": Increment(pts), field: Increment(1)}, merge=True)


def leaderboard(limit=10):
    q = (db().collection("users")
         .order_by("points", direction="DESCENDING").limit(limit))
    return [(s.to_dict().get("name", "?"), s.to_dict().get("points", 0))
            for s in q.stream()]


def get_user(user_id):
    snap = db().collection("users").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else None
