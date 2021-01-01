from typing import NamedTuple, List

ROW = 5
COL = 5
INITIAL_SUBMARINE_COUNT = 4
INITIAL_HP = 3


class Pos(NamedTuple):
    row: int
    col: int

    def code(self) -> str:
        """
        自分のセル位置を、'A2' 'E5' といった形式で文字列として返す。
        row は (0,1,2,3,4) が (A,B,C,D,E) に対応し、
        col は (0,1,2,3,4) が (1,2,3,4,5) に対応する。
        """
        return chr(ord('A') + self.row) + str(self.col + 1)


def is_within_area(p: Pos) -> bool:
    """
    (row, col) が範囲内かどうか判定する。
    row ∈ [0, ROW) && col ∈ [0, COL) なら True。
    """
    return (p.row in range(0, ROW)) and (p.col in range(0, COL))


def listup_around_cells(center_pos: Pos) -> List[Pos]:
    """
    center_pos の上下左右斜め1マスのマス位置を list として返す。
    領域外のマスは除く。
    すなわち y not in [0, ROW) || x not in [0, COL) であるような (y, x) は list に含めない。
    center_pos は list に含めない。
    """

    around_cells = [
        Pos(center_pos.row + dy, center_pos.col + dx)
        for dy in [-1, 0, +1] for dx in [-1, 0, +1]
        if (dy, dx) != (0, 0) and is_within_area(Pos(center_pos.row + dy, center_pos.col + dx))
    ]

    return around_cells
