from typing import Any

import numpy as np

from .model import OpInfo, AttackInfo, MoveInfo, Response, BattleData
from .traits import Pos
from .traits import ROW, COL


class Color:
    HEADER = '\033[95m'
    OK_BLUE = '\033[94m'
    OK_CYAN = '\033[96m'
    OK_GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def info(msg: Any, end='\n'):
    print(Color.OK_CYAN + Color.BOLD + "[Info] " + Color.END + str(msg), end=end)


def success(msg: Any, end='\n'):
    print(Color.OK_GREEN + Color.BOLD + "[Success] " + Color.END + str(msg), end=end)


def warn(msg: Any, end='\n'):
    print(Color.WARNING + Color.BOLD + "[Warn] " + Color.END + str(msg), end=end)


def fail(msg: Any, end='\n'):
    print(Color.FAIL + Color.BOLD + "[Fail] " + Color.END + str(msg), end=end)


def ask_yesno(message: str) -> bool:
    """
    `message` を出力して一行入力する。
    入力値が "yes" の prefix なら True を、
    入力値が "no" の prefix なら False を、
    それ以外なら再度入力を促す。
    yes/no の比較は大文字小文字を区別しない。
    """
    while True:
        print(message, end='')
        s = input().strip().lower()

        if s in ["y", "ye", "yes"]:
            info("Your input: yes")
            return True
        elif s in ["n", "no"]:
            info("Your input: no")
            return False
        else:
            fail("Cannot parse to yes/no.")


def newline():
    print()


def show_grid(grid: np.ndarray):
    print(Color.HEADER + "   1  2  3  4  5" + Color.END)
    for row in range(ROW):
        print(Color.HEADER + chr(ord('A') + row) + Color.END, end='')
        for col in range(COL):
            print(" ", (grid[row, col] if grid[row, col] > 0 else "."), end="")
        newline()


def dump_my_grid(data: BattleData):
    newline()
    show_grid(data.my_grid)
    print(Color.OK_CYAN + "Positions: " + Color.END, end='')
    for pos in data.listup_my_submarine_positions():
        print(pos.code(), end=' ')
    newline()


def read_response() -> Response:
    while True:
        print("How was the response of attack? [hit/dead/near/none]: ", end='')
        s = input().strip().lower()
        if s == "hit":
            return Response.Hit
        if s == "dead":
            return Response.Dead
        if s == "near":
            return Response.Near
        if s == "none":
            return Response.Nothing
        fail("Invalid input.")


def read_cell_code(message: str) -> Pos:
    """
    "A1" "e6" のような形式で入力して Posで返す。 アルファベットの大文字小文字は区別しない。
    5x5 の範囲外の入力が合った場合は再度入力を促す。
    """

    while True:
        print(message, end='')
        s = input().strip().lower()
        if len(s) != 2:
            fail("String length must be 2.  Input again.")
            continue

        row_code = s[0]
        col_code = s[1]
        if row_code not in "abcde":
            fail("Row code must be one of 'ABCDE'.  Input again.")
            continue

        if col_code not in "12345":
            fail("Column code must be one of '12345'.  Input again.")
            continue

        row = ord(row_code) - ord('a')
        col = int(col_code) - 1
        return Pos(row=row, col=col)


def read_attack_info():
    p = read_cell_code("Opponent's attack target cell (ex: `E2`): ")
    return OpInfo(AttackInfo(attack_pos=p))


def read_move_info() -> OpInfo:
    while True:
        print("Opponent's moving direction[U/D/L/R] and distance (ex: `L 1`): ", end='')

        try:
            direction, distance = input().split()
        except ValueError:
            fail("Please split with WHITE_SPACE.")
            continue

        if direction not in ['L', 'U', 'D', 'R']:
            fail("Direction must be one of [U/D/L/R]: " + direction)
            continue
        if distance not in ['1', '2']:
            fail("Invalid distance: " + distance)
            continue

        distance = int(distance)

        if direction == 'L':
            return OpInfo(MoveInfo(fromPos=None, dirY=0, dirX=(-distance)))
        if direction == 'R':
            return OpInfo(MoveInfo(fromPos=None, dirY=0, dirX=(+distance)))
        if direction == 'U':
            return OpInfo(MoveInfo(fromPos=None, dirY=(-distance), dirX=0))
        if direction == 'D':
            return OpInfo(MoveInfo(fromPos=None, dirY=(+distance), dirX=0))


def read_opponent_op() -> OpInfo:
    while True:
        print("Which is the opponent's action? [attack/move]: ", end='')
        s = input().strip().lower()
        if s == "attack":
            return read_attack_info()
        if s == "move":
            return read_move_info()
        fail("Invalid input")
