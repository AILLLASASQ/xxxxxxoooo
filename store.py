"""طبقة البيانات: الألعاب والمستخدمون والنقاط.

كل العمليات الحسّاسة (تطبيق حركة، احتساب النقاط) تتم داخل Firestore transaction
لتفادي race conditions و double-counting — وهي المشاكل اللي تكررت سابقاً.
"""
import secrets
import time

from google.cloud.firestore_v1 import Increment, transactional

import game
import moderation
import settings
from firebase_db import db

# حالة مؤقتة لألعاب الإنلاين بين inline_query و chosen_inline_result
_pending_inline = {}


def new_game_id():
    return secrets.token_urlsafe(6)


def _turn_deadline():
    tt = int(settings.get("turn_timeout") or 0)
    return (int(time.time()) + tt) if tt > 0 else None


def create_game(mode, player_x, name_x, chat_id=None, message_id=None,
                inline_message_id=None, difficulty=None):
    """إنشاء مستند لعبة جديدة وإرجاع (game_id, data)."""
    gid = new_game_id()
    data = {
        "mode": mode,                 # "pvp" | "bot" | "inline"
        "difficulty": difficulty,
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


def create_random_game(x, o):
    """إنشاء لعبة عشوائية بين لاعبَين في محادثتين منفصلتين.

    x و o قاموسان فيهما: id, name, chat_id, msg_id.
    """
    gid = new_game_id()
    data = {
        "mode": "random",
        "board": game.board_to_str(game.new_board()),
        "turn": "X",
        "turn_deadline": _turn_deadline(),
        "player_x": int(x["id"]), "name_x": x["name"],
        "player_o": int(o["id"]), "name_o": o["name"],
        "x_chat_id": int(x["chat_id"]), "x_msg_id": int(x["msg_id"]),
        "o_chat_id": int(o["chat_id"]), "o_msg_id": int(o["msg_id"]),
        "winner": None,
        "finalized": False,
        "points_awarded": False,
        "created_at": int(time.time()),
    }
    db().collection("games").document(gid).set(data)
    data["_gid"] = gid
    return gid, data


def create_inline_game(gid, x_id, x_name, o_id, o_name, inline_message_id):
    """إنشاء لعبة إنلاين لحظة انضمام الخصم."""
    data = {
        "mode": "inline",
        "board": game.board_to_str(game.new_board()),
        "turn": "X",
        "turn_deadline": _turn_deadline(),
        "player_x": int(x_id), "name_x": x_name,
        "player_o": int(o_id), "name_o": o_name,
        "inline_message_id": inline_message_id,
        "winner": None,
        "finalized": False,
        "points_awarded": False,
        "created_at": int(time.time()),
    }
    db().collection("games").document(gid).set(data)
    data["_gid"] = gid
    return data


def get_game(gid):
    snap = db().collection("games").document(gid).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    d["_gid"] = gid
    return d


# ---------- الانضمام (transaction) ----------
def join_game(gid, player_o, name_o):
    """انضمام اللاعب الثاني. يرجع (ok, data, reason)."""
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
        _dl = _turn_deadline()
        txn.update(ref, {"player_o": player_o, "name_o": name_o, "turn_deadline": _dl})
        d["player_o"] = player_o
        d["name_o"] = name_o
        d["turn_deadline"] = _dl
        d["_gid"] = gid
        return True, d, ""

    return _txn(db().transaction())


# ---------- تطبيق حركة (transaction) ----------
def apply_move(gid, user_id, cell):
    """تطبيق حركة بأمان. يرجع (ok, data, reason).

    يتحقق من: وجود اللعبة، عدم إنهائها، صحة الدور، فراغ الخانة.
    """
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

        # من صاحب الدور؟
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

        update = {
            "board": game.board_to_str(board),
            "turn": next_turn,
        }
        if result:
            update["winner"] = result
            update["finalized"] = True
        else:
            update["turn_deadline"] = _turn_deadline()
        txn.update(ref, update)

        d.update(update)
        d["_gid"] = gid
        return True, d, ""

    return _txn(db().transaction())


def bot_move(gid):
    """حركة البوت في وضع vs-bot. يرجع data بعد التحديث."""
    ref = db().collection("games").document(gid)
    d = get_game(gid)
    if not d or d.get("finalized"):
        return d

    board = game.board_from_str(d["board"])
    move = game.best_move(board, "O", "X", d.get("difficulty") or "hard")
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


# ---------- النقاط (transaction آمن من الازدواج) ----------
def ensure_user(user_id, name):
    ref = db().collection("users").document(str(user_id))
    if not ref.get().exists:
        ref.set({
            "name": name, "points": 0,
            "wins": 0, "losses": 0, "draws": 0,
            "last_daily": 0,
        })


def award_result(gid, allow_points=True):
    """احتساب نقاط نتيجة اللعبة مرة واحدة فقط (idempotent).

    - يطبّق سقف نقاط الخصم (pair_points_limit) على كل مسارات الفوز
      (حركة عادية أو فوز بالوقت) — انتصارات فقط، اتجاهي.
    - allow_points=False يختم اللعبة بلا نقاط (تجاوز خارجي).
    يرجع dict: {"awarded": bool, "capped_user": id|None}.
    """
    gref = db().collection("games").document(gid)
    info = {"awarded": False, "capped_user": None}

    d0 = get_game(gid)
    if not d0 or not d0.get("finalized"):
        return info
    mode = d0.get("mode")
    winner = d0.get("winner")
    earner = opp = None
    capped = not allow_points
    if allow_points and mode != "bot" and winner in ("X", "O"):
        cap = int(settings.get("pair_points_limit") or 0)
        px, po = d0.get("player_x"), d0.get("player_o")
        earner, opp = (px, po) if winner == "X" else (po, px)
        if cap and earner and opp and moderation.pair_points(earner, opp) >= cap:
            capped = True
            info["capped_user"] = earner

    @transactional
    def _txn(txn):
        info["awarded"] = False
        snap = gref.get(transaction=txn)
        if not snap.exists:
            return
        d = snap.to_dict()
        if not d.get("finalized") or d.get("points_awarded"):
            return
        if capped:
            txn.update(gref, {"points_awarded": True})
            return
        if d.get("mode") == "bot":
            diff = d.get("difficulty") or "hard"
            wp = settings.get(f"bot_win_{diff}")
            wp = int(wp) if wp is not None else settings.get("points_win")
            _apply_points(txn, d["player_x"], d["winner"], human_mark="X", win_pts=wp)
        else:
            _apply_points(txn, d["player_x"], d["winner"], human_mark="X")
            if d.get("player_o"):
                _apply_points(txn, d["player_o"], d["winner"], human_mark="O")
        txn.update(gref, {"points_awarded": True})
        info["awarded"] = True

    _txn(db().transaction())
    if info["awarded"]:
        _apply_floor(gid)
        if mode != "bot" and winner in ("X", "O") and earner and opp:
            moderation.add_pair_points(earner, opp, settings.get("points_win"))
    return info


def _apply_points(txn, user_id, result, human_mark, win_pts=None):
    ref = db().collection("users").document(str(user_id))
    if result == "draw":
        pts, field = settings.get("points_draw"), "draws"
    elif result == human_mark:
        pts = win_pts if win_pts is not None else settings.get("points_win")
        field = "wins"
    else:
        pts, field = settings.get("points_loss"), "losses"
    txn.set(ref, {
        "points": Increment(pts),
        field: Increment(1),
    }, merge=True)


def leaderboard(limit=10):
    q = (db().collection("users")
         .order_by("points", direction="DESCENDING")
         .limit(limit))
    return [(s.to_dict().get("name", "?"), s.to_dict().get("points", 0))
            for s in q.stream()]


def get_user(user_id):
    snap = db().collection("users").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else None



# ---------- تنظيف الألعاب العالقة (سقف صارم منذ الإنشاء) ----------
def fetch_stale_games(max_age, limit=50):
    """يرجع الألعاب غير المنتهية التي مضى على إنشائها أكثر من max_age ثانية.

    استعلام بسيط (finalized == False) ثم تصفية created_at في الكود
    لتفادي الحاجة لفهرس مركّب في Firestore.
    """
    from google.cloud.firestore_v1 import FieldFilter
    now = int(time.time())
    cutoff = now - int(max_age)
    out = []
    q = (db().collection("games")
         .where(filter=FieldFilter("finalized", "==", False))
         .limit(int(limit)))
    for s in q.stream():
        d = s.to_dict() or {}
        if int(d.get("created_at", now)) <= cutoff:
            d["_gid"] = s.id
            out.append(d)
    return out


def delete_game(gid):
    try:
        db().collection("games").document(gid).delete()
    except Exception:
        pass


# ---------- مهلة الدور (timeout) ----------
def finalize_timeout(gid):
    """ينهي مباراة بشرية لانتهاء وقت صاحب الدور (transactional, آمن من السباق).

    يرجع (ok, data). ok=True فقط إذا أُنهيت فعلاً بسبب التايم آوت.
    """
    ref = db().collection("games").document(gid)

    @transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return False, None
        d = snap.to_dict()
        if d.get("finalized") or d.get("mode") == "bot" or not d.get("player_o"):
            return False, d
        deadline = d.get("turn_deadline")
        if not deadline or int(time.time()) <= int(deadline):
            return False, d
        win = "O" if d.get("turn") == "X" else "X"
        txn.update(ref, {"winner": win, "finalized": True, "win_by_timeout": True})
        d["winner"] = win
        d["finalized"] = True
        d["win_by_timeout"] = True
        d["_gid"] = gid
        return True, d

    return _txn(db().transaction())


def fetch_timed_out_games(limit=50):
    """يرجع المباريات البشرية غير المنتهية التي تجاوزت مهلة الدور (للمراقب)."""
    from google.cloud.firestore_v1 import FieldFilter
    now = int(time.time())
    out = []
    q = (db().collection("games")
         .where(filter=FieldFilter("finalized", "==", False))
         .limit(int(limit)))
    for s in q.stream():
        d = s.to_dict() or {}
        if d.get("mode") == "bot" or not d.get("player_o"):
            continue
        dl = d.get("turn_deadline")
        if dl and now > int(dl):
            d["_gid"] = s.id
            out.append(d)
    return out


# ---------- مكافأة المتصدّرين ----------
def top_users(n=3):
    """يرجع أعلى n لاعبين مع معرّفاتهم وأسمائهم ونقاطهم."""
    q = (db().collection("users")
         .order_by("points", direction="DESCENDING")
         .limit(int(n)))
    out = []
    for s in q.stream():
        d = s.to_dict() or {}
        out.append({"id": s.id, "name": d.get("name", "?"),
                    "points": int(d.get("points", 0) or 0)})
    return out


def add_bonus(user_id, pts):
    """يضيف نقاطاً لمستخدم (مكافأة)."""
    db().collection("users").document(str(user_id)).set(
        {"points": Increment(int(pts))}, merge=True)


def _apply_floor(gid):
    """يمنع نزول نقاط أي لاعب في اللعبة تحت points_floor (أرضية الرصيد)."""
    floor = settings.get("points_floor")
    if floor is None:
        return
    floor = int(floor)
    d = get_game(gid)
    if not d:
        return
    ids = [d.get("player_x")]
    if d.get("mode") != "bot" and d.get("player_o"):
        ids.append(d.get("player_o"))
    for uid in ids:
        if not uid:
            continue
        ref = db().collection("users").document(str(uid))
        snap = ref.get()
        if snap.exists and int(snap.to_dict().get("points", 0) or 0) < floor:
            ref.update({"points": floor})


def user_rank(user_id):
    """يرجع (الترتيب, النقاط) للمستخدم، أو None إن لم يلعب بعد."""
    from google.cloud.firestore_v1 import FieldFilter
    snap = db().collection("users").document(str(user_id)).get()
    if not snap.exists:
        return None
    pts = int(snap.to_dict().get("points", 0) or 0)
    try:
        agg = db().collection("users").where(
            filter=FieldFilter("points", ">", pts)).count().get()
        higher = agg[0][0].value if agg else 0
    except Exception:
        higher = 0
    return higher + 1, pts


# ---------- المواسم والرُتب ----------
def _season_days():
    return max(1, int(settings.get("season_days") or 7))


def get_season():
    ref = db().collection("meta").document("season")
    snap = ref.get()
    if snap.exists:
        return snap.to_dict()
    data = {"number": 1, "end": int(time.time()) + _season_days() * 86400}
    ref.set(data)
    return data


def maybe_rollover_season():
    """يصفّر الموسم إن انتهى (آمن من الازدواج). يرجع True عند التصفير."""
    ref = db().collection("meta").document("season")
    now = int(time.time())

    @transactional
    def _claim(txn):
        snap = ref.get(transaction=txn)
        d = snap.to_dict() if snap.exists else None
        if not d:
            txn.set(ref, {"number": 1, "end": now + _season_days() * 86400})
            return None
        if now < int(d.get("end", 0)):
            return None
        old = int(d.get("number", 1))
        txn.update(ref, {"number": old + 1, "end": now + _season_days() * 86400})
        return old

    old_num = _claim(db().transaction())
    if old_num is None:
        return False
    _archive_and_reset(old_num)
    return True


def _archive_and_reset(old_num):
    prizes = settings.get("reward_prizes") or []
    size = int(settings.get("leaderboard_size") or 5)
    champs = []
    for i, u in enumerate(top_users(size)):
        champs.append({
            "id": u["id"], "name": u["name"], "points": u["points"],
            "prize": prizes[i] if i < len(prizes) and prizes[i] else "",
        })
    now_ts = int(time.time())
    db().collection("meta").document("last_season").set({
        "number": old_num, "ended_at": now_ts, "top": champs})
    db().collection("meta").document("pending_coronation").set({
        "number": old_num, "ended_at": now_ts, "top": champs})

    batch = db().batch()
    n = 0
    for snap in db().collection("users").stream():
        batch.update(snap.reference,
                     {"points": 0, "wins": 0, "losses": 0, "draws": 0})
        n += 1
        if n % 400 == 0:
            batch.commit()
            batch = db().batch()
    if n % 400:
        batch.commit()


def last_season():
    snap = db().collection("meta").document("last_season").get()
    return snap.to_dict() if snap.exists else None


def tier_name(points):
    p = int(points or 0)
    if p >= int(settings.get("tier_diamond") or 300):
        return "ماسي"
    if p >= int(settings.get("tier_gold") or 150):
        return "ذهب"
    if p >= int(settings.get("tier_silver") or 50):
        return "فضة"
    return "برونز"


def pop_pending_coronation():
    """يقرأ ويحذف تتويجاً معلّقاً (atomic). يرجع dict أو None."""
    ref = db().collection("meta").document("pending_coronation")

    @transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return None
        d = snap.to_dict()
        txn.delete(ref)
        return d

    return _txn(db().transaction())


def force_end_season():
    """ينهي الموسم الحالي فوراً (يؤرشف + يصفّر + يبدأ موسماً جديداً).

    يرجع رقم الموسم المنتهي. التتويج (pending_coronation) يُضبط داخل _archive_and_reset.
    """
    ref = db().collection("meta").document("season")
    now = int(time.time())

    @transactional
    def _claim(txn):
        snap = ref.get(transaction=txn)
        d = snap.to_dict() if snap.exists else None
        old = int(d.get("number", 1)) if d else 1
        txn.set(ref, {"number": old + 1, "end": now + _season_days() * 86400})
        return old

    old_num = _claim(db().transaction())
    _archive_and_reset(old_num)
    return old_num


# ---------- التحدي الموجّه (حجز رمز حصري) ----------
def claim_challenge_symbol(gid, sym, uid, name, imid):
    """يحجز رمزاً في تحدٍّ موجّه (transactional، يدعم التبديل).

    sym: "X" أو "O". يرجع (status, doc) حيث status ∈
    {"already","taken","waiting","ready"}.
    """
    key = "x" if sym == "X" else "o"
    other = "o" if key == "x" else "x"
    ref = db().collection("challenges").document(gid)

    @transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        d = snap.to_dict() if snap.exists else None
        if not d:
            d = {"x": None, "o": None, "imid": imid,
                 "created_at": int(time.time())}
        cur = d.get(key)
        if cur and int(cur.get("id")) == int(uid):
            return "already", d
        if cur:
            return "taken", d
        d[key] = {"id": int(uid), "name": name}
        if d.get(other) and int(d[other].get("id")) == int(uid):
            d[other] = None
        ready = bool(d.get("x") and d.get("o"))
        txn.set(ref, d)
        return ("ready" if ready else "waiting"), d

    return _txn(db().transaction())


def delete_challenge(gid):
    try:
        db().collection("challenges").document(gid).delete()
    except Exception:
        pass
