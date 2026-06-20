"""منطق لعبة إكس أو — دوال نقية."""
import random

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def new_board():
    return ["" for _ in range(9)]


def board_from_str(s):
    return [c if c in ("X", "O") else "" for c in s]


def board_to_str(board):
    return "".join(c if c else " " for c in board)


def winner(board):
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None


def available_moves(board):
    return [i for i, c in enumerate(board) if not c]


def _minimax(board, ai, human, is_ai_turn):
    result = winner(board)
    if result == ai:
        return 1
    if result == human:
        return -1
    if result == "draw":
        return 0
    scores = []
    mark = ai if is_ai_turn else human
    for move in available_moves(board):
        board[move] = mark
        scores.append(_minimax(board, ai, human, not is_ai_turn))
        board[move] = ""
    return max(scores) if is_ai_turn else min(scores)


# نسبة الحركة العشوائية لكل مستوى (الباقي = حركة مثالية minimax)
_RANDOM_CHANCE = {"easy": 0.6, "medium": 0.25, "hard": 0.0}


def best_move(board, ai_mark, human_mark, difficulty="hard"):
    moves = available_moves(board)
    if not moves:
        return None
    chance = _RANDOM_CHANCE.get(difficulty, 0.0)
    if chance and random.random() < chance:
        return random.choice(moves)
    best_score = -2
    chosen = moves[0]
    for move in moves:
        board[move] = ai_mark
        score = _minimax(board, ai_mark, human_mark, is_ai_turn=False)
        board[move] = ""
        if score > best_score:
            best_score = score
            chosen = move
    return chosen
