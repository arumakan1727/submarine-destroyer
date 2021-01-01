from random import randint
from typing import List, Optional

import numpy as np

from . import io
from .model import OpInfo, AttackInfo, Response, BattleData
from .traits import Pos
from .traits import ROW, COL, INITIAL_HP, INITIAL_SUBMARINE_COUNT
from .traits import listup_around_cells


def apply_my_op(data: BattleData, op_info: OpInfo) -> None:
    """
    自軍の操作を data に適用する
    """
    data.my_history.append(op_info)

    if op_info.is_move():
        row, col = op_info.detail.fromPos
        dirY = op_info.detail.dirY
        dirX = op_info.detail.dirX
        assert data.my_grid[row, col] > 0
        assert data.my_grid[row + dirY, col + dirX] == 0
        data.my_grid[row + dirY, col + dirX] = data.my_grid[row, col]
        data.my_grid[row, col] = 0


def apply_attack_response(data: BattleData, resp: Response) -> None:
    """
    自軍からの攻撃に対する敵軍の反応を data に適用する
    """
    assert data.my_history[-1].is_attack()
    data.my_history[-1].detail.resp = resp

    # TODO data.potential の更新

    if resp is Response.Dead:
        data.opponent_alive_count -= 1


def apply_opponent_op(data: BattleData, op: OpInfo) -> Optional[Response]:
    """
    敵軍の操作を data に適用する
    """
    data.opponent_history.append(op)

    if op.is_attack():
        ay, ax = op.detail.attack_pos

        # 敵が攻撃した位置に自軍が存在していたなら、 HP を減算して Hit または Dead の適切な方を返す。
        if data.my_grid[ay, ax] > 0:
            data.my_grid[ay, ax] -= 1
            if data.my_grid[ay, ax] <= 0:
                return Response.Dead
            else:
                return Response.Hit
        # 敵が攻撃した位置の周囲に自軍が一隻以上存在していたなら Near。
        elif any(data.my_grid[i, j] > 0 for i, j in listup_around_cells(Pos(ay, ax))):
            return Response.Near
        # 反応なし。
        else:
            return Response.Nothing

    elif op.is_move():
        return None


def suggest_my_op(data: BattleData) -> OpInfo:
    """
    対戦データをもとに自軍の操作を提案して返す。
    この関数は data に一切書込をしない。
    """
    return OpInfo(AttackInfo(attack_pos=Pos(3, 5)))


def initialize_my_placement(data: BattleData) -> None:
    """
    自軍の初期配置を決定して data に書き込む。
    """
    X = INITIAL_HP
    candidates = [
        # 案1
        [
            [0, 0, 0, 0, 0],
            [0, X, 0, X, 0],
            [0, 0, 0, 0, 0],
            [0, X, 0, X, 0],
            [0, 0, 0, 0, 0],
        ],

        # 案2
        [
            [X, 0, 0, 0, 0],
            [0, 0, 0, X, 0],
            [0, 0, 0, 0, 0],
            [0, X, 0, 0, 0],
            [0, 0, 0, 0, X],
        ],
    ]

    def validate(matrix: List[List[int]]) -> None:
        assert len(matrix) == ROW
        assert all(len(row) == COL for row in matrix)
        hp_sum = 0
        for row in matrix:
            for cell in row:
                assert cell == 0 or cell == INITIAL_HP
                hp_sum += cell
        assert hp_sum == (INITIAL_HP * INITIAL_SUBMARINE_COUNT)

    io.info("Validating initial placement candidates...")
    for mat in candidates:
        validate(mat)
    io.success("All candidates are OK.")

    # TODO selectID は乱数にするか定数にするか
    candidate_id = randint(0, len(candidates) - 1)

    io.info("Candidate ID is: %d" % candidate_id)
    data.my_grid = np.array(candidates[candidate_id])
