import enum
import numpy as np
from typing import NamedTuple, Union, Optional, List
from random import shuffle, randint, choice
from dataclasses import dataclass

ROW = 5
COL = 5
INITIAL_SUBMARINE_COUNT = 4
INITIAL_HP = 3


class Pos(NamedTuple):
    row: int
    col: int

    def code(self) -> str:
        return chr(ord('A') + self.row) + str(self.col + 1)


class Response(enum.Enum):
    Hit = enum.auto()
    Dead = enum.auto()
    Near = enum.auto()
    Nothing = enum.auto()


@dataclass
class AttackInfo:
    pos: Pos
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
            return "Attack(to: %s)" % self.detail.pos.code()

        if self.is_move():
            info = self.detail
            return "Move(from: %s, dir: %s, dist: %d)" % (
                info.fromPos.code() if info.fromPos is not None else "-None-",
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

    potential: np.ndarray [np.int32]
        そのマスに敵軍が存在する可能性を記録するための2次元配列。
        各セルの初期値は 0 。

    my_history: List[OpInfo]
        自軍の操作の歴史。
        初手の操作はリストの先頭 [0] に格納され、最後の操作の情報はリストの末尾 [-1] に格納される。

    opponent_history: List[OpInfo]
        敵軍の操作の歴史。
        初手の操作はリストの先頭 [0] に格納され、最後の操作の情報はリストの末尾 [-1] に格納される。
    """

    def __init__(self):
        self.my_alive_count: int = INITIAL_SUBMARINE_COUNT
        self.opponent_alive_count: int = INITIAL_SUBMARINE_COUNT
        self.my_grid: np.ndarray = np.zeros((ROW, COL), dtype=np.int32)
        self.opponent_grid: np.ndarray = np.zeros((ROW, COL), dtype=np.int32)
        self.potential: np.ndarray = np.zeros((ROW, COL), dtype=np.int32)
        self.my_history: List[OpInfo] = list()
        self.opponent_history: List[OpInfo] = list()

    def listup_my_submarine_positions(self) -> List[Pos]:
        grid = self.my_grid
        return [
            Pos(row, col)
            for row in range(ROW) for col in range(COL)
            if grid[row, col] > 0
        ]

    def has_game_finished(self) -> bool:
        return self.my_alive_count <= 0 or self.opponent_alive_count <= 0
