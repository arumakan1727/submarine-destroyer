from typing import Any

from .model import OpInfo, AttackInfo, MoveInfo, Response, BattleData
from .rule import Pos
from .rule import ROW, COL


class Color:
    HEADER = '\033[95m'
    OK_BLUE = '\033[94m'
    INFO_CYAN = '\033[96m'
    OK_GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def magenta(s: Any) -> str:
        return Color.HEADER + str(s) + Color.END

    @staticmethod
    def cyan(s: Any) -> str:
        return Color.INFO_CYAN + str(s) + Color.END

    @staticmethod
    def green(s: Any) -> str:
        return Color.OK_GREEN + str(s) + Color.END

    @staticmethod
    def yellow(s: Any) -> str:
        return Color.WARNING + str(s) + Color.END

    @staticmethod
    def red(s: Any) -> str:
        return Color.FAIL + str(s) + Color.END


def info(msg: Any, end='\n'):
    print(Color.INFO_CYAN + Color.BOLD + "[Info] " + Color.END + str(msg), end=end)


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


def dump_my_grid(data: BattleData):
    grid = data.my_grid
    print(Color.HEADER + "   1  2  3  4  5" + Color.END)
    for row in range(ROW):
        print(Color.HEADER + chr(ord('A') + row) + Color.END, end='')
        for col in range(COL):
            print(" ", (grid[row, col] if grid[row, col] > 0 else "."), end="")
        newline()


def dump_my_submarine_pos_codes(data: BattleData):
    print(Color.INFO_CYAN + "自軍の潜水艦の位置: " + Color.END, end='')
    for pos in data.set_of_my_submarine_positions():
        print(pos.code(), end=' ')
    newline()


def dump_battle_data(data: BattleData, should_show_my_positions: bool):
    newline()
    print("--------- Battle Data ---------")
    # 確率グリッドの表示
    print(data.prob)

    if should_show_my_positions:
        # 自軍の配置グリッドの表示
        dump_my_grid(data)

        # 自軍の潜水艦の位置の表示
        dump_my_submarine_pos_codes(data)

    # tracking_cell の表示
    print(Color.INFO_CYAN + "位置が明らかな敵艦:" + Color.END,
          "None" if (data.tracking_cell is None) else data.tracking_cell.code())

    # 敵軍の生きている潜水艦数と自軍の生きている潜水艦数 の表示
    print(Color.INFO_CYAN + "自軍の生き残り艦数:" + Color.END, data.my_alive_count)
    print(Color.INFO_CYAN + "敵軍の生き残り艦数:" + Color.END, data.opponent_alive_count)


def read_response() -> Response:
    while True:
        print("自軍が攻撃しました。敵軍からのレスポンスを入力してください [Dead/Hit/Near/X]: ", end='')
        s = input().strip().lower()
        if "hit".startswith(s):
            return Response.Hit
        if "dead".startswith(s):
            return Response.Dead
        if "near".startswith(s):
            return Response.Near
        if s == "x":
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


def read_attack_info(cur_turn_count: int):
    p = read_cell_code("敵が攻撃した位置 (ex: `E2`): ")
    return OpInfo(AttackInfo(attack_pos=p), turn_count=cur_turn_count)


def read_move_info(cur_turn_count: int) -> OpInfo:
    while True:
        print("敵の移動方向 [U/D/L/R] と移動距離を空白区切りで (ex: `L 1`): ", end='')

        try:
            direction, distance = input().split()
        except ValueError:
            fail("Please split with WHITE_SPACE.")
            continue

        direction = direction.upper()

        if direction not in ['L', 'U', 'D', 'R']:
            fail("Direction must be one of [U/D/L/R]: " + direction)
            continue
        if distance not in ['1', '2']:
            fail("Invalid distance: " + distance)
            continue

        distance = int(distance)

        if direction == 'L':
            return OpInfo(MoveInfo(fromPos=None, dirY=0, dirX=(-distance)), turn_count=cur_turn_count)
        if direction == 'R':
            return OpInfo(MoveInfo(fromPos=None, dirY=0, dirX=(+distance)), turn_count=cur_turn_count)
        if direction == 'U':
            return OpInfo(MoveInfo(fromPos=None, dirY=(-distance), dirX=0), turn_count=cur_turn_count)
        if direction == 'D':
            return OpInfo(MoveInfo(fromPos=None, dirY=(+distance), dirX=0), turn_count=cur_turn_count)


def read_opponent_op(cur_turn_count: int) -> OpInfo:
    while True:
        print("敵の行動を入力してください [Attack/Move]: ", end='')
        s = input().strip().lower()
        if "attack".startswith(s):
            return read_attack_info(cur_turn_count)
        if "move".startswith(s):
            return read_move_info(cur_turn_count)
        fail("Invalid input")


def print_title():
    print(r"""
 ____        _                          _
/ ___| _   _| |__  _ __ ___   __ _ _ __(_)_ __   ___
\___ \| | | | '_ \| '_ ` _ \ / _` | '__| | '_ \ / _ \
 ___) | |_| | |_) | | | | | | (_| | |  | | | | |  __/
|____/ \__,_|_.__/|_| |_| |_|\__,_|_|  |_|_| |_|\___|

 ____            _
|  _ \  ___  ___| |_ _ __ ___  _   _  ___ _ __
| | | |/ _ \/ __| __| '__/ _ \| | | |/ _ \ '__|
| |_| |  __/\__ \ |_| | | (_) | |_| |  __/ |
|____/ \___||___/\__|_|  \___/ \__, |\___|_|
                               |___/
""")
