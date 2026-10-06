"""Yoté —— 西非双人跳吃棋.

规则 (常见版本):
- 5x6 棋盘, 每方 12 枚棋子, 轮流先布子 (每次放 1 枚到空格).
- 布完进入走子阶段: 每轮走 1 枚, 正交走一格到空格.
- 跳吃: 跳过相邻敌子落到其后空格, 吃掉被跳过的子;
  跳吃成功后还可再额外移除对方场上任意 1 枚子 ("买一送一").
- 吃光对方全部棋子获胜; 走子阶段无合法走法判负.

纯标准库, Python 3.10+.
"""
from __future__ import annotations

import argparse
import copy
import random
import sys

ROWS, COLS = 5, 6
PIECES_PER_SIDE = 12
EMPTY = 0
P0, P1 = 1, 2
DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def other(p: int) -> int:
    return P1 if p == P0 else P0


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < ROWS and 0 <= c < COLS


class Yote:
    """可测试的游戏核心."""

    def __init__(self) -> None:
        self.board = [[EMPTY] * COLS for _ in range(ROWS)]
        self.phase = "place"          # place / move
        self.to_place = {P0: PIECES_PER_SIDE, P1: PIECES_PER_SIDE}
        self.counts = {P0: 0, P1: 0}  # 场上子数
        self.turn = P0

    # ---------- 布子 ----------

    def legal_places(self) -> list[tuple[int, int]]:
        return [(r, c) for r in range(ROWS) for c in range(COLS)
                if self.board[r][c] == EMPTY]

    def place(self, player: int, r: int, c: int) -> None:
        if self.phase != "place":
            raise ValueError("当前不是布子阶段")
        if player != self.turn:
            raise ValueError("还没轮到你")
        if not in_bounds(r, c):
            raise ValueError("坐标越界")
        if self.board[r][c] != EMPTY:
            raise ValueError("格子已被占")
        self.board[r][c] = player
        self.to_place[player] -= 1
        self.counts[player] += 1
        if self.to_place[P0] == 0 and self.to_place[P1] == 0:
            self.phase = "move"
        self.turn = other(player)

    # ---------- 走子 ----------

    def _jumps_from(self, r: int, c: int, player: int):
        """从 (r,c) 出发的跳吃: (落点, 被吃坐标) 列表."""
        foe = other(player)
        res = []
        for dr, dc in DIRS:
            mr, mc = r + dr, c + dc
            lr, lc = r + 2 * dr, c + 2 * dc
            if (in_bounds(mr, mc) and in_bounds(lr, lc)
                    and self.board[mr][mc] == foe
                    and self.board[lr][lc] == EMPTY):
                res.append(((lr, lc), (mr, mc)))
        return res

    def legal_moves(self, player: int):
        """走子阶段走法: ('move', 起点, 落点) / ('jump', 起点, 落点, 被吃)."""
        moves = []
        for r in range(ROWS):
            for c in range(COLS):
                if self.board[r][c] != player:
                    continue
                for dr, dc in DIRS:
                    nr, nc = r + dr, c + dc
                    if in_bounds(nr, nc) and self.board[nr][nc] == EMPTY:
                        moves.append(("move", (r, c), (nr, nc)))
                for (lr, lc), (mr, mc) in self._jumps_from(r, c, player):
                    moves.append(("jump", (r, c), (lr, lc), (mr, mc)))
        return moves

    def apply_move(self, player: int, move) -> tuple[int, int] | None:
        """执行走法, 返回 (被跳吃子坐标, 额外移除子坐标|None).

        跳吃后额外移除由 bonus 参数控制 AI/玩家选择; 这里返回候选,
        调用方再决定移除哪一枚.
        """
        if self.phase != "move":
            raise ValueError("当前不是走子阶段")
        if player != self.turn:
            raise ValueError("还没轮到你")
        kind = move[0]
        if kind == "move":
            _, (fr, fc), (tr, tc) = move
            if not (in_bounds(fr, fc) and in_bounds(tr, tc)):
                raise ValueError("坐标越界")
            if self.board[fr][fc] != player:
                raise ValueError("起点不是你的子")
            if abs(fr - tr) + abs(fc - tc) != 1:
                raise ValueError("只能走一格")
            if self.board[tr][tc] != EMPTY:
                raise ValueError("落点被占")
            self.board[fr][fc] = EMPTY
            self.board[tr][tc] = player
            captured = None
        elif kind == "jump":
            _, (fr, fc), (tr, tc), (mr, mc) = move
            if not (in_bounds(fr, fc) and in_bounds(tr, tc)):
                raise ValueError("坐标越界")
            if self.board[fr][fc] != player:
                raise ValueError("起点不是你的子")
            if self.board[tr][tc] != EMPTY:
                raise ValueError("落点被占")
            if self.board[mr][mc] != other(player):
                raise ValueError("中间不是敌子")
            if abs(fr - tr) + abs(fc - tc) != 2:
                raise ValueError("跳吃必须跳两格")
            if (mr, mc) != ((fr + tr) // 2, (fc + tc) // 2):
                raise ValueError("被跳子必须在起点落点正中间")
            if (fr != tr and fc != tc):
                raise ValueError("只能正交跳吃")
            self.board[fr][fc] = EMPTY
            self.board[mr][mc] = EMPTY
            self.board[tr][tc] = player
            self.counts[other(player)] -= 1
            captured = (mr, mc)
        else:
            raise ValueError("未知走法类型")
        self.turn = other(player)
        return captured

    def bonus_remove(self, player: int, r: int, c: int) -> None:
        """跳吃后的额外移除: 拿掉对方场上任意一枚子."""
        if not in_bounds(r, c):
            raise ValueError("坐标越界")
        if self.board[r][c] != other(player):
            raise ValueError("只能移除对方的棋子")
        self.board[r][c] = EMPTY
        self.counts[other(player)] -= 1

    # ---------- 终局 ----------

    def winner(self) -> int | None:
        if self.counts[P0] == 0 and self.phase == "move":
            return P1
        if self.counts[P1] == 0 and self.phase == "move":
            return P0
        if self.phase == "move" and not self.legal_moves(self.turn):
            return other(self.turn)
        return None

    def is_over(self) -> bool:
        return self.winner() is not None


# ---------- AI ----------

def ai_place(game: Yote, rng: random.Random) -> tuple[int, int]:
    empt = game.legal_places()
    # 优先占中心附近
    empt.sort(key=lambda rc: (abs(rc[0] - 2) + abs(rc[1] - 2.5), rng.random()))
    return empt[0]


def ai_move(game: Yote, player: int, rng: random.Random):
    moves = game.legal_moves(player)
    jumps = [m for m in moves if m[0] == "jump"]
    if jumps:
        return rng.choice(jumps)
    return rng.choice(moves)


def ai_bonus(game: Yote, player: int, rng: random.Random) -> tuple[int, int]:
    foes = [(r, c) for r in range(ROWS) for c in range(COLS)
            if game.board[r][c] == other(player)]
    return rng.choice(foes)


# ---------- 自动对局 ----------

def play_auto(seed: int, verbose: bool = False) -> dict:
    rng = random.Random(seed)
    g = Yote()
    jumps = 0
    while g.phase == "place":
        r, c = ai_place(g, rng)
        g.place(g.turn, r, c)
    steps = 0
    while not g.is_over() and steps < 600:
        mv = ai_move(g, g.turn, rng)
        player = g.turn
        captured = g.apply_move(player, mv)
        if captured:
            jumps += 1
            # 额外移除
            if g.counts[other(player)] > 0:
                br, bc = ai_bonus(g, player, rng)
                g.bonus_remove(player, br, bc)
        steps += 1
        if verbose:
            print(render(g.board), f"\n走 {steps}: {mv}\n")
    w = g.winner()
    return {"winner": w, "steps": steps, "jumps": jumps,
            "counts": dict(g.counts), "draw": w is None}


# ---------- 渲染 / 交互 ----------

GLYPH = {EMPTY: "·", P0: "●", P1: "○"}


def render(board) -> str:
    head = "  " + " ".join(str(c) for c in range(COLS))
    rows = [head]
    for r in range(ROWS):
        rows.append(f"{r} " + " ".join(GLYPH[board[r][c]] for c in range(COLS)))
    return "\n".join(rows)


def parse_coord(s: str) -> tuple[int, int]:
    parts = s.replace(",", " ").split()
    if len(parts) != 2:
        raise ValueError("坐标格式: 行 列, 如 2 3")
    r, c = int(parts[0]), int(parts[1])
    if not in_bounds(r, c):
        raise ValueError("坐标越界")
    return r, c


def play_interactive(seed: int | None) -> int:
    if not sys.stdin.isatty():
        print("交互模式需要终端; 无头演示请用 --auto", file=sys.stderr)
        return 2
    rng = random.Random(seed)
    g = Yote()
    human = P0
    print("Yoté —— 你是 ●(先手), AI 是 ○")
    print("布子: 输入 '行 列'; 走子: 输入 '起行 起列 落行 落列'")
    print("跳吃后可额外移除对方一枚子, 输入其坐标. q 退出.")
    while not g.is_over():
        print()
        print(render(g.board))
        who = "你" if g.turn == human else "AI"
        if g.phase == "place":
            print(f"[布子] {who}, 剩余 {g.to_place[g.turn]}")
            if g.turn == human:
                s = input("> ").strip()
                if s == "q":
                    return 0
                try:
                    r, c = parse_coord(s)
                    g.place(human, r, c)
                except ValueError as e:
                    print("非法:", e)
            else:
                r, c = ai_place(g, rng)
                g.place(g.turn, r, c)
                print(f"AI 布子 {r} {c}")
        else:
            print(f"[走子] {who}")
            if g.turn == human:
                s = input("> ").strip()
                if s == "q":
                    return 0
                try:
                    p = s.replace(",", " ").split()
                    if len(p) != 4:
                        raise ValueError("格式: 起行 起列 落行 落列")
                    fr, fc, tr, tc = map(int, p)
                    # 找匹配的合法走法
                    cand = [m for m in g.legal_moves(human)
                            if m[1] == (fr, fc) and m[2] == (tr, tc)]
                    if not cand:
                        raise ValueError("非法走法")
                    captured = g.apply_move(human, cand[0])
                    if captured and g.counts[P1] > 0:
                        print(f"跳吃! 额外移除对方一枚子, 输入坐标:")
                        print(render(g.board))
                        r, c = parse_coord(input("移除> ").strip())
                        g.bonus_remove(human, r, c)
                except ValueError as e:
                    print("非法:", e)
            else:
                mv = ai_move(g, g.turn, rng)
                player = g.turn
                captured = g.apply_move(player, mv)
                extra = ""
                if captured and g.counts[other(player)] > 0:
                    br, bc = ai_bonus(g, player, rng)
                    g.bonus_remove(player, br, bc)
                    extra = f" 额外移除 {br} {bc}"
                print(f"AI 走 {mv[1]} -> {mv[2]}{extra}")
    print()
    print(render(g.board))
    w = g.winner()
    print("你赢了!" if w == human else "AI 赢了!" if w is not None else "和棋!")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Yoté —— 西非跳吃棋")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.auto:
        w0 = w1 = dr = 0
        for i in range(args.games):
            r = play_auto(args.seed + i, verbose=args.verbose)
            if r["winner"] == P0:
                w0 += 1
            elif r["winner"] == P1:
                w1 += 1
            else:
                dr += 1
            print(f"第 {i+1}/{args.games} 局: "
                  f"{'甲胜' if r['winner'] == P0 else '乙胜' if r['winner'] == P1 else '和棋'}"
                  f" (步数 {r['steps']}, 跳吃 {r['jumps']})")
        print(f"总计: 甲胜 {w0}, 乙胜 {w1}, 和棋 {dr}")
        return 0
    return play_interactive(args.seed)


if __name__ == "__main__":
    sys.exit(main())
