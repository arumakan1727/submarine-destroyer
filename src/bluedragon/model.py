import enum
from dataclasses import dataclass
from typing import NamedTuple, Union, Optional, List, Set

import numpy as np

from .rule import Pos
from .rule import ROW, COL, INITIAL_SUBMARINE_COUNT
from .rule import is_within_area


class Response(enum.Enum):
    Hit = enum.auto()
    Dead = enum.auto()
    Near = enum.auto()
    Nothing = enum.auto()


@dataclass
class AttackInfo:
    attack_pos: Pos
    resp: Optional[Response] = None


class MoveInfo(NamedTuple):
    fromPos: Optional[Pos]
    dirY: int
    dirX: int

    def dir_str(self) -> str:
        assert self.dirY == 0 or self.dirX == 0

        if self.dirY > 0:
            return "Down(South)"
        if self.dirY < 0:
            return "Up(North)"
        if self.dirX > 0:
            return "Right(East)"
        if self.dirX < 0:
            return "Left(West)"
        return "-unknown-"

    def moving_distance(self) -> int:
        assert self.dirY == 0 or self.dirX == 0
        return abs(self.dirX) + abs(self.dirY)


class OpInfo(NamedTuple):
    """
    OpInfo(AttackInfo(...)) または OpInfo(MoveInfo(...)) のようにして生成する
    """
    detail: Union[AttackInfo, MoveInfo]

    def is_attack(self) -> bool:
        return isinstance(self.detail, AttackInfo)

    def is_move(self) -> bool:
        return isinstance(self.detail, MoveInfo)

    def __str__(self) -> str:
        if self.is_attack():
            return "Attack(to: %s)" % self.detail.attack_pos.code()

        if self.is_move():
            info = self.detail
            return "Move(from: %s, dir: %s, dist: %d)" % (
                info.fromPos.code() if info.fromPos is not None else "None",
                info.dir_str(),
                info.moving_distance())

        raise Exception("type of `detail` is illegal")


class BattleData:
    """

    Attributes
    ----------
    my_alive_count: int
        自軍のいきている潜水艦数

    opponent_alive_count: int
        敵軍のいきている数

    my_grid: np.ndarray [np.int32]
        my_grid[row, col] := (row, col) マスの自軍の潜水艦のHP。
        潜水艦が存在しない場合は 0。
        0 <= row < 5, 0 <= col < 5

    opponent_grid: np.ndarray [np.int32]
        my_grid[row, col] := (row, col) マスの敵軍の潜水艦のHP。
        潜水艦が存在しない場合は 0。
        位置が確定している敵軍の潜水艦はこのフィールドに記録される。
        0 <= row < 5, 0 <= col < 5

    prob: np.ndarray [np.float64]
        そのマスに敵軍が存在する確率を保持するための2次元配列 (probability の略)。
        各セルの初期値は 4/25 。

    my_history: List[OpInfo]
        自軍の操作の歴史。
        初手の操作はリストの先頭 [0] に格納され、最後の操作の情報はリストの末尾 [-1] に格納される。

    opponent_history: List[OpInfo]
        敵軍の操作の歴史。
        初手の操作はリストの先頭 [0] に格納され、最後の操作の情報はリストの末尾 [-1] に格納される。

    tracking_cell: Optional[Pos]
        攻撃をし続ける対象のセル位置。
        自軍の攻撃がヒットしたときに 非None になる。
        敵の移動情報 と 移動後に攻撃が当たったかどうか によって変動する。見失った場合は None になる。
    """

    def __init__(self):
        self.my_alive_count: int = INITIAL_SUBMARINE_COUNT
        self.opponent_alive_count: int = INITIAL_SUBMARINE_COUNT
        self.my_grid: np.ndarray = np.zeros((ROW, COL), dtype=np.int32)
        self.opponent_grid: np.ndarray = np.zeros((ROW, COL), dtype=np.int32)
        self.prob: np.ndarray = np.full((ROW, COL), fill_value=INITIAL_SUBMARINE_COUNT / (ROW * COL), dtype=np.float64)
        self.my_history: List[OpInfo] = list()
        self.opponent_history: List[OpInfo] = list()
        self.tracking_cell: Optional[Pos] = None

    def set_of_my_submarine_positions(self) -> Set[Pos]:
        grid = self.my_grid
        return set(
            Pos(row, col)
            for row in range(ROW) for col in range(COL)
            if grid[row, col] > 0
        )

    def has_game_finished(self) -> bool:
        return self.my_alive_count <= 0 or self.opponent_alive_count <= 0

    def set_of_my_attackable_cells(self) -> Set[Pos]:
        """
        自軍が攻撃可能なマスを列挙して set として返す。
        """
        attackable_cells: Set[Pos] = set()
        submarine_poses = self.set_of_my_submarine_positions()

        # 各潜水艦の周囲8マスを集合に追加 (dy=dx=0 の場合も追加してしまうけど後で取り除くのでOK)
        for p in submarine_poses:
            for dy in [-1, 0, +1]:
                for dx in [-1, 0, +1]:
                    attack_to = Pos(row=p.row + dy, col=p.col + dx)
                    if is_within_area(attack_to):
                        attackable_cells.add(attack_to)

        # 自軍の潜水艦マスには攻撃できないので除く
        return attackable_cells.difference(set(submarine_poses))

    def set_of_my_movable_cells(self, from_pos: Pos) -> Set[Pos]:
        """
        指定した位置から移動可能なマスを列挙する。
        """
        assert self.my_grid[from_pos.row, from_pos.col] > 0
        my_submarine_poses = self.set_of_my_submarine_positions()
        movable_cells: Set[Pos] = set()
        for d in [-2, -1, +1, +2]:
            for dy, dx in [(d, 0), (0, d)]:
                to = Pos(row=from_pos.row + dy, col=from_pos.col + dx)
                if is_within_area(to) and (to not in my_submarine_poses):
                    movable_cells.add(to)
        return movable_cells
