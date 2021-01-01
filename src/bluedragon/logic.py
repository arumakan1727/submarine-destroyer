import math
from random import randint
from typing import List, Optional, Set

import numpy as np

from . import io
from .model import OpInfo, AttackInfo, Response, BattleData
from .traits import Pos
from .traits import ROW, COL, INITIAL_HP, INITIAL_SUBMARINE_COUNT
from .traits import set_of_around_cells, all_cell_set


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
    attacked_pos = data.my_history[-1].detail.attack_pos

    # 確率グリッドの更新
    if resp is Response.Hit:
        _update_prob_for_my_attack_hit(data.prob, attacked_pos, data.opponent_alive_count)
    elif resp is Response.Dead:
        _update_prob_for_my_attack_dead(data.prob, attacked_pos, data.opponent_alive_count)
    elif resp is Response.Near:
        _update_prob_for_my_attack_near(data.prob, attacked_pos, data.opponent_alive_count)
    elif resp is Response.Nothing:
        _update_prob_for_my_attack_nothing(data.prob, attacked_pos)

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
        elif any(data.my_grid[i, j] > 0 for i, j in set_of_around_cells(Pos(ay, ax))):
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
    return OpInfo(AttackInfo(attack_pos=Pos(2, 2)))


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


def _distribute_prob(prob: np.ndarray, value: float, destinations: Set[Pos]) -> None:
    """
    destinations に含まれるマスそれぞれに、(value / len(destinations)) を加算する。
    """
    value /= len(destinations)
    for y, x in destinations:
        prob[y, x] += value


def _set_of_zero_cells(prob: np.ndarray) -> Set[Pos]:
    return set(
        Pos(y, x)
        for y in range(0, ROW) for x in range(0, COL)
        if math.isclose(prob[y, x], 0, abs_tol=1e-10)
    )


def _set_of_cells_greater_eq_one(prob: np.ndarray) -> Set[Pos]:
    return set(
        Pos(y, x)
        for y in range(0, ROW) for x in range(0, COL)
        if prob[y, x] >= (1.0 - 1e-10)
    )


def _set_of_zero_union_greater_eq_one(prob: np.ndarray) -> Set[Pos]:
    return _set_of_zero_cells(prob) | _set_of_cells_greater_eq_one(prob)


def _suck_spot_and_distribute_prob(prob: np.ndarray, src_pos: Pos) -> None:
    """
    prob[src_pos] の確率をゼロにしてそれ以外のマスに分散させる。
    ただし、確率が 0 のマスと 1 のマスには分散させない。
    """
    destinations = all_cell_set()
    destinations.discard(src_pos)
    destinations = destinations - _set_of_zero_union_greater_eq_one(prob)

    sy, sx = src_pos
    _distribute_prob(prob, prob[sy, sx], destinations)
    prob[sy, sx] = 0


def _suck_one_submarine_prob(prob: np.ndarray, source_candidates: Set[Pos], opponent_alive_count: int) -> float:
    """
    「source_candidate のうち 確率0のマスと確率1以上のマスを除いたマス群」から合計一隻分の確率 (=1.0) を減算して返す。
    すなわち戻り値は理論上は1.0に等しいはず (浮動小数点誤差はある)。
    各マスから減算する量は、そのマスの値を p とすると p * (1 / (N - k)) である。
    ただし、N は敵の残機数、k は 全マスの中での確率1の個数(すなわち位置が明らかな敵艦の個数)
    """
    N = opponent_alive_count
    k = len(_set_of_cells_greater_eq_one(prob))
    sources = source_candidates - _set_of_zero_union_greater_eq_one(prob)
    prob_sum = 0
    for y, x in sources:
        v = prob[y, x] * (1 / (N - k))
        prob[y, x] -= v
        prob_sum += v
    assert math.isclose(1.0, prob_sum)
    return prob_sum


def _update_prob_for_my_attack_hit(prob: np.ndarray, hit_pos: Pos, opponent_alive_count: int) -> None:
    """
    自軍の攻撃がヒットしたとき用の確率グリッド更新処理。
    opponent_alive_count は敵軍が死ぬ前の隻数。
    """
    # 既に確率が 1 になっているので early return
    if prob[hit_pos.row, hit_pos.col] >= (1.0 - 1e-10):
        return

    # ヒットマスの確率をゼロにして他のマスへ分散
    _suck_spot_and_distribute_prob(prob, hit_pos)

    _suck_one_submarine_prob(prob, all_cell_set() - {hit_pos}, opponent_alive_count)

    prob[hit_pos.row, hit_pos.col] = 1.0


def _update_prob_for_my_attack_dead(prob: np.ndarray, dead_pos: Pos, opponent_alive_count: int) -> None:
    """
    自軍の攻撃がヒットして敵軍が死んだ用の確率グリッド更新処理。
    opponent_alive_count は敵軍が死ぬ前の隻数。
    """
    _update_prob_for_my_attack_hit(prob, dead_pos, opponent_alive_count)
    prob[dead_pos.row, dead_pos.col] = 0.0
    assert math.isclose(np.sum(prob), opponent_alive_count - 1)  # 全マスの確率の総和は敵軍の(死んだ後の)隻数に等しいはず


def _update_prob_for_my_attack_near(prob: np.ndarray, attacked_pos: Pos, opponent_alive_count: int) -> None:
    """
    自軍の攻撃が波高しだった用の確率グリッド更新処理。
    """
    # もし波高しの周囲に、位置が明らかな敵艦が存在する場合は何もしない。
    if len(set_of_around_cells(attacked_pos) & _set_of_cells_greater_eq_one(prob)) > 0:
        return

    # 攻撃マスの確率をゼロにして他のマスへ分散 (ヒットはしてないので攻撃した位置には確実に居ない)
    _suck_spot_and_distribute_prob(prob, attacked_pos)

    # 1隻分の確率を各マスから奪って波高しの周囲マスに分配
    _suck_one_submarine_prob(prob, all_cell_set() - {attacked_pos}, opponent_alive_count)
    destinations = set_of_around_cells(attacked_pos) - _set_of_zero_union_greater_eq_one(prob)
    _distribute_prob(prob, 1.0, destinations)


def _update_prob_for_my_attack_nothing(prob: np.ndarray, attacked_pos: Pos) -> None:
    """
    自軍の攻撃が反応なしだった用の確率グリッド更新処理。
    """
    nothing_area = set_of_around_cells(attacked_pos).union({attacked_pos})

    # 反応なしだったマスとその周囲の確率をゼロにし、総和を s に格納
    s = 0
    for y, x in nothing_area:
        s += prob[y, x]
        prob[y, x] = 0

    destinations = all_cell_set() - nothing_area - _set_of_zero_union_greater_eq_one(prob)
    _distribute_prob(prob, s, destinations)
