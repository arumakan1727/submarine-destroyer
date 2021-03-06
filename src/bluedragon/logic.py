import math
from logging import getLogger
from random import randint, choice
from typing import List, Optional, Set

import numpy as np

from . import io
from .model import OpInfo, AttackInfo, Response, BattleData, MoveInfo
from .rule import Pos
from .rule import ROW, COL, INITIAL_HP, INITIAL_SUBMARINE_COUNT
from .rule import set_of_around_cells, all_cell_set, is_within_area

thisFileLogger = getLogger(__name__)


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

    # 確率グリッドの更新
    attacked_pos = data.my_history[-1].detail.attack_pos
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
    敵軍の操作を data に適用する。
    敵軍の操作が攻撃だった場合はそれに対するレスポンスを返す。 そうでなければ None を返す。
    """
    data.opponent_history.append(op)

    # 確率グリッドの更新
    if op.is_attack():
        _update_prob_for_opponent_attack(data.prob, op.detail.attack_pos, data.opponent_alive_count)
    elif op.is_move():
        _update_prob_for_opponent_move(data.prob, op.detail)

    # 敵の攻撃を自軍のHPへ反映・レスポンスを返す。
    if op.is_attack():
        ay, ax = op.detail.attack_pos

        # 敵が攻撃した位置に自軍が存在していたならHPを減算する。
        if data.my_grid[ay, ax] > 0:
            data.my_grid[ay, ax] -= 1
            # HPが0なら自軍の潜水艦が死んだので Dead を返し、そうでなければ Hit を返す。
            if data.my_grid[ay, ax] <= 0:
                data.my_alive_count -= 1
                data.opponent_history[-1].detail.resp = Response.Dead
                return Response.Dead
            else:
                data.opponent_history[-1].detail.resp = Response.Hit
                return Response.Hit
        # 敵が攻撃した位置の周囲に自軍が一隻以上存在していたなら Near。
        elif any(data.my_grid[i, j] > 0 for i, j in set_of_around_cells(Pos(ay, ax))):
            data.opponent_history[-1].detail.resp = Response.Near
            return Response.Near
        # 反応なし。
        else:
            data.opponent_history[-1].detail.resp = Response.Nothing
            return Response.Nothing

    elif op.is_move():
        return None


def update_tracking_cell(data: BattleData) -> None:
    """
    対戦データ内の tracking_cell 変数、すなわち位置が明らかで、次も攻撃する対象の敵艦の位置 (=マーク位置) を更新する。
    この関数は、自軍の操作をした直後 (攻撃した場合はそのレスポンスを受け取った直後) に呼び出されることを想定している。
    """
    assert len(data.my_history) > 0

    current_tracking_cell = data.tracking_cell
    last_my_op = data.my_history[-1]
    last_opponent_op = None if len(data.opponent_history) <= 0 else data.opponent_history[-1]

    # 敵が1艦になったばかりではない かつ 位置が明らか かつ 敵が1艦しかいない場合
    if not (last_my_op.is_attack() and last_my_op.detail.resp is Response.Dead) and (
            current_tracking_cell is not None) and (data.opponent_alive_count == 1):
        if last_opponent_op.is_move():
            sy, sx = current_tracking_cell
            dirY = last_opponent_op.detail.dirY
            dirX = last_opponent_op.detail.dirX
            data.tracking_cell = Pos(sy + dirY, sx + dirX)
            io.info("敵の位置が明らか かつ 敵が1艦しかいない 状態で敵が移動しました。 tracking_cell を移動先の %s にします。" %
                    data.tracking_cell.code(), thisFileLogger)
            return
        else:
            io.info("敵の位置が明らか かつ 敵が1艦しかいない 状態で敵は移動していません。 tracking_cell はそのまま %s を維持します。" %
                    data.tracking_cell.code(), thisFileLogger)
            return

    data.tracking_cell = _calculate_next_tracking_cell(
        current_tracking_cell,
        last_my_op=last_my_op,
        last_opponent_op=last_opponent_op)

    if data.tracking_cell is not None:
        _update_prob_for_my_attack_hit(data.prob, data.tracking_cell, data.opponent_alive_count)


def suggest_my_op(data: BattleData, cur_turn_count: int) -> OpInfo:
    """
    対戦データをもとに自軍の操作を提案して返す。
    この関数は data に一切書込をしない。
    """
    # 自軍の射程内にあるマス位置の集合
    attackable_cells = data.set_of_my_attackable_cells()

    # 敵軍の直前の操作
    last_opponent_op = None if (len(data.opponent_history) <= 0) else data.opponent_history[-1]

    ######################################################################################################
    # 先手かつ初手の場合は、candidates からランダムに抽出した位置を攻撃する。
    if len(data.my_history) <= 0 and len(data.opponent_history) <= 0:
        # 攻撃先候補 と attackable_cells の積集合をとって確実に攻撃可能な位置を得る。
        candidates = set(Pos(y, x) for y in range(1, ROW - 1) for x in range(1, COL - 1)) & attackable_cells
        attack_to = choice(list(candidates))
        io.info("初手 " + attack_to.code() + " への攻撃を選択しました", thisFileLogger)
        assert attack_to in attackable_cells
        return OpInfo(AttackInfo(attack_pos=attack_to), turn_count=cur_turn_count)

    ######################################################################################################
    # 位置が明らかな敵艦があれば、そいつを攻撃し続けたい
    if data.tracking_cell is not None:
        # 攻撃可能とは限らない攻撃先候補
        candidates_unsafe: Set[Pos] = {data.tracking_cell}

        # 直前に敵艦が移動していたら移動先のマスも候補に含める
        if (last_opponent_op is not None) and last_opponent_op.is_move():
            sy, sx = data.tracking_cell
            dirY = last_opponent_op.detail.dirY
            dirX = last_opponent_op.detail.dirX
            candidates_unsafe.add(Pos(sy + dirY, sx + dirX))

        # 候補の中で攻撃可能なマスがあればその中からランダムに抽出してそれを攻撃先とする
        candidates = candidates_unsafe & attackable_cells
        if len(candidates) > 0:
            attack_to = choice(list(candidates))
            assert attack_to in attackable_cells
            io.info("tracking_cell と 敵の移動情報に基づいて " + attack_to.code() + " の攻撃を選択しました", thisFileLogger)
            return OpInfo(AttackInfo(attack_pos=attack_to), turn_count=cur_turn_count)

    ######################################################################################################
    # 攻撃可能かどうかを考慮しない確率最高値のマスを求める。
    true_highest_prob_cell: Pos = max(all_cell_set(), key=lambda p: data.prob[p.row, p.col])
    true_highest_prob_value = data.prob[true_highest_prob_cell.row, true_highest_prob_cell.col]
    io.info("攻撃可能とは限らないマスの中で確率最高値のマスは %s (確率 %g) です" %
            (true_highest_prob_cell.code(), true_highest_prob_value), thisFileLogger)

    # 確率最高値のマスの確率がかなり高く、それにもかかわらず自軍の射程にない場合は自軍をその方角へ移動させる
    probability_threshold_high = (data.opponent_alive_count * 0.1)
    if true_highest_prob_value > probability_threshold_high and true_highest_prob_cell not in attackable_cells:
        # 確率最高値のマスが自軍の位置とかぶっている場合はその自軍の艦を移動させる
        if true_highest_prob_cell in data.set_of_my_submarine_positions():
            from_pos = true_highest_prob_cell
            move_dest_candidates = set(
                Pos(y, x)
                for y, x in data.set_of_my_movable_cells(from_pos)
                if abs(y - from_pos.row) + abs(x - from_pos.col) == 1
            )
            if len(move_dest_candidates) > 0:
                # 自軍の他の艦とのマンハッタン距離の総和が一番大きくなるような位置へ移動する
                dest = max(move_dest_candidates,
                           key=lambda p: sum(
                               abs(p.row + q.row) + abs(p.col + q.col)
                               for q in data.set_of_my_submarine_positions()))
                io.info("確率最高セルと自軍がかぶっているので自軍を %s から %s へ移動させます" % (from_pos.code(), dest.code()), thisFileLogger)
                return OpInfo(MoveInfo(fromPos=from_pos, dirY=dest.row - from_pos.row, dirX=dest.col - from_pos.col),
                              turn_count=cur_turn_count)

        # 確率最高マスへの距離が最も近い艦を動かす
        actor: Pos = min(data.set_of_my_submarine_positions(),
                         key=lambda p: (abs(true_highest_prob_cell.row - p.row)
                                        + abs(true_highest_prob_cell.col - p.col)))
        # 移動可能なマスのうち最も確率最高マスへの距離が近いマスを移動先とする
        dest = min(data.set_of_my_movable_cells(actor),
                   key=lambda p: (
                       999 if (p == true_highest_prob_cell)
                       else abs(true_highest_prob_cell.row - p.row) + abs(true_highest_prob_cell.col - p.col)))
        io.info("確率最高セルへ向けて自軍を %s から %s へ移動させます" % (actor.code(), dest.code()), thisFileLogger)
        return OpInfo(MoveInfo(fromPos=actor, dirY=dest.row - actor.row, dirX=dest.col - actor.col),
                      turn_count=cur_turn_count)

    if ((last_opponent_op is not None)
            and last_opponent_op.is_attack()
            and last_opponent_op.detail.resp in (Response.Hit, Response.Dead)):
        attacked_pos = last_opponent_op.detail.attack_pos
        io.info("敵の攻撃が命中しているので、攻撃を食らっているマス %s の周囲かつ攻撃可能マスで最も確率が高いマスを求めます。" % attacked_pos.code(), thisFileLogger)
        candidates = set_of_around_cells(attacked_pos) & attackable_cells
        if len(candidates) <= 0:
            io.info("攻撃を食らっているマスの周囲に攻撃可能なマスはありませんでした。", thisFileLogger)
        else:
            dest = max(candidates, key=lambda p: data.prob[p.row, p.col])
            if math.isclose(0, data.prob[dest.row, dest.col], abs_tol=1e-7):
                io.info("「攻撃を食らっているマスの周囲 && 攻撃可能マス の中で最高確率のマス」の確率が ゼロ なので攻撃しません。", thisFileLogger)
            else:
                io.info("「攻撃を食らっているマスの周囲 && 攻撃可能マス の中で最高確率のマス」である %s を攻撃します。" % dest.code(), thisFileLogger)
                return OpInfo(AttackInfo(attack_pos=dest), turn_count=cur_turn_count)

    ######################################################################################################
    # 攻撃可能なマスの中で確率最高値のマスを求める。
    attackable_highest_prob_cell: Pos = max(attackable_cells, key=lambda p: data.prob[p.row, p.col])
    attackable_highest_prob_value = data.prob[attackable_highest_prob_cell.row, attackable_highest_prob_cell.col]
    io.info("攻撃可能なマスの中で確率最高値のマスは %s (確率 %g) です" %
            (attackable_highest_prob_cell.code(), attackable_highest_prob_value), thisFileLogger)

    # 最高確率値がしきい値より確率が高ければ攻撃する
    probability_threshold_high = (data.opponent_alive_count * 0.1)
    if attackable_highest_prob_value > probability_threshold_high:
        io.info("確率値がしきい値 %g より高いので %s を攻撃します" %
                (probability_threshold_high, attackable_highest_prob_cell.code()), thisFileLogger)
        assert attackable_highest_prob_cell in attackable_cells
        return OpInfo(AttackInfo(attack_pos=attackable_highest_prob_cell), turn_count=cur_turn_count)

    ######################################################################################################
    # 敵の攻撃位置を遡り、その攻撃位置へ移動可能なら移動する
    for op in reversed(data.opponent_history):
        if op.is_move():
            break
        assert op.is_attack()
        attacked_pos = op.detail.attack_pos
        my_movable_submarines = set(
            p
            for p in data.set_of_my_submarine_positions()
            if attacked_pos in data.set_of_my_movable_cells(from_pos=p)
        )

        # 敵が攻撃した位置へ移動可能な自軍の潜水艦のうち、攻撃可能範囲の個数が一番小さい艦を移動させる
        if len(my_movable_submarines) > 0:
            actor: Pos = min(my_movable_submarines, key=lambda p: len(set_of_around_cells(p)))
            io.info("%s に位置する自軍の艦を、過去に敵が攻撃した位置 %s へ移動させます" % (actor.code(), attacked_pos.code()), thisFileLogger)
            dirY = attacked_pos.row - actor.row
            dirX = attacked_pos.col - actor.col
            assert (abs(dirY) + abs(dirX)) in (1, 2)
            assert dirY == 0 or dirX == 0
            return OpInfo(MoveInfo(fromPos=actor, dirY=dirY, dirX=dirX), turn_count=cur_turn_count)

    # 自軍の数が2以下の場合は50%の確率でランダムに移動
    if data.my_alive_count <= 2 and randint(0, 99) < 50:
        actor = choice(list(data.set_of_my_submarine_positions()))
        dest = choice(list(data.set_of_my_movable_cells(actor)))
        io.info("確率が高いマスが見当たらず自軍の数が2以下の場合は5割の確率でランダムに移動します...選ばれたのは移動でした (%s -> %s)。" %
                (actor.code(), dest.code()), thisFileLogger)
        return OpInfo(MoveInfo(fromPos=actor, dirY=dest.row - actor.row, dirX=dest.col - actor.col),
                      turn_count=cur_turn_count)

    io.info("しきい値より高くはないもののこれ以外に行動パターンが無いので最高確率値のマス %s に攻撃します" %
            attackable_highest_prob_cell.code(), thisFileLogger)
    return OpInfo(AttackInfo(attack_pos=attackable_highest_prob_cell), turn_count=cur_turn_count)


def initialize_my_placement(data: BattleData) -> None:
    """
    自軍の初期配置を決定して data に書き込む。
    """
    X = INITIAL_HP
    candidates = [
        [
            [0, 0, 0, 0, 0],
            [X, 0, X, 0, 0],
            [0, 0, 0, 0, 0],
            [0, X, 0, 0, X],
            [0, 0, 0, 0, 0],
        ],

        [
            [0, 0, 0, X, 0],
            [X, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, X, 0, 0, X],
            [0, 0, 0, 0, 0],
        ],

        [
            [0, 0, 0, 0, 0],
            [0, X, 0, 0, X],
            [0, 0, 0, 0, 0],
            [X, 0, 0, 0, 0],
            [0, 0, 0, X, 0],
        ],

        [
            [0, 0, 0, 0, 0],
            [0, 0, X, 0, 0],
            [X, 0, 0, 0, X],
            [0, 0, X, 0, 0],
            [0, 0, 0, 0, 0],
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

    io.info("%d 個の初期配置候補を validate しています..." % len(candidates), thisFileLogger)
    for mat in candidates:
        validate(mat)
    io.success("どの初期配置候補も不正はありませんでした。", thisFileLogger)

    # TODO selectID は乱数にするか定数にするか
    candidate_id = randint(0, len(candidates) - 1)

    io.info("候補のうち %d 番目 (0-indexed) の初期配置を選択します。" % candidate_id, thisFileLogger)
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
        if math.isclose(prob[y, x], 0, abs_tol=1e-7)
    )


def _set_of_cells_greater_eq_one(prob: np.ndarray) -> Set[Pos]:
    return set(
        Pos(y, x)
        for y in range(0, ROW) for x in range(0, COL)
        if prob[y, x] >= (1.0 - 1e-7)
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
    if k == N:
        return 0
    sources = source_candidates - _set_of_zero_union_greater_eq_one(prob)
    prob_sum = 0
    for y, x in sources:
        v = prob[y, x] * (1 / (N - k))
        prob[y, x] -= v
        prob_sum += v
    assert math.isclose(1.0, prob_sum, rel_tol=1e-7)
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
    assert math.isclose(np.sum(prob), opponent_alive_count - 1, rel_tol=1e-7)  # 全マスの確率の総和は敵軍の(死んだ後の)隻数に等しいはず


def _update_prob_for_my_attack_near(prob: np.ndarray, attacked_pos: Pos, opponent_alive_count: int) -> None:
    """
    自軍の攻撃が波高しだった用の確率グリッド更新処理。
    """
    # もし敵が攻撃してきた位置が既に確率ゼロなら何もしない。
    if math.isclose(0.0, prob[attacked_pos.row, attacked_pos.col], abs_tol=1e-7):
        return

    # 攻撃マスの確率をゼロにして他のマスへ分散 (ヒットはしてないので攻撃した位置には確実に居ない)
    _suck_spot_and_distribute_prob(prob, attacked_pos)

    # もし波高しの周囲に、位置が明らかな敵艦が存在する場合は何もしない。
    if len(set_of_around_cells(attacked_pos) & _set_of_cells_greater_eq_one(prob)) > 0:
        return

    # 1隻分の確率を各マスから奪って波高しの周囲マスに分配
    # !!! destinations は suck する前に得ること！
    destinations = set_of_around_cells(attacked_pos) - _set_of_zero_union_greater_eq_one(prob)
    _suck_one_submarine_prob(prob, all_cell_set() - {attacked_pos}, opponent_alive_count)
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


def _update_prob_for_opponent_attack(prob: np.ndarray, attacked_pos: Pos, opponent_alive_count: int) -> None:
    """
    敵が attacked_pos に攻撃した場合の確率グリッド更新処理。
    """
    return _update_prob_for_my_attack_near(prob, attacked_pos, opponent_alive_count)


def _update_prob_for_opponent_move(prob: np.ndarray, moving_info: MoveInfo) -> None:
    """
    敵が移動した場合の確率グリッド更新処理。
    各マスの確率値を少し移動させる。 確率値が0や1のマスに対して特別処理を行うことはしない。
    """
    dirY = moving_info.dirY
    dirX = moving_info.dirX
    from_cells = [
        Pos(y, x)
        for y in range(ROW) for x in range(COL)
        if is_within_area(Pos(y + dirY, x + dirX))
    ]
    prob_sum = sum(prob[y, x] for y, x in from_cells)

    # 移動元の確率の総和がゼロならこれ以上何もしない。
    # (あとの処理で prob_sum で割るためゼロ除算を避ける)
    if math.isclose(0, prob_sum, abs_tol=1e-7):
        return

    # 移動させた分の確率値の一時的な保存場所。
    # for文で確率値の数割を移動先へ加算したあと、その加算した値ををさらに移動させると確率が壊れるため)
    a = np.zeros((ROW, COL), dtype=np.float64)

    for y, x in from_cells:
        v = prob[y, x] * (prob[y, x] / prob_sum)
        prob[y, x] -= v
        a[y + dirY, x + dirX] = v

    prob += a


def _calculate_next_tracking_cell(
        current_tracking_cell: Optional[Pos],
        last_my_op: OpInfo,
        last_opponent_op: Optional[OpInfo]
) -> Optional[Pos]:
    """
    現在の敵艦マーク位置と、自軍の直前の操作、敵軍の直前の操作から、次のターン用の敵艦マーク位置を求めて返す。
    この関数は、自軍の操作をした直後 (攻撃した場合はそのレスポンスを受け取った直後) に呼び出されることを想定している。
    my_last_op に直前のターンの自軍の操作を渡し、opponent_last_op には「my_my_last_op の前のターンでの敵軍の操作」を渡さなければならない。

    初手が自軍の場合には敵軍の直前の操作は存在しないので、opponent_last_op は Optional にしている。
    """
    io.info("更新前の敵艦予想位置: %s, 自軍の直前の操作: %s, 敵の直前の操作: %s" %
            (current_tracking_cell.code() if (current_tracking_cell is not None) else "None",
             str(last_my_op),
             str(last_opponent_op)), thisFileLogger)

    # 自軍の直前の操作が攻撃だった場合
    if last_my_op.is_attack():
        response = last_my_op.detail.resp
        assert response is not None

        # 自軍の攻撃が当たって死んだ場合は、そのマスにはもう敵艦は存在しない。マーク位置の敵艦が消えた & 他の敵艦の位置は分からないので None。
        if response is Response.Dead:
            io.info("自軍の攻撃が当たって消えたので tracking_cell を %s にします。" % None, thisFileLogger)
            return None

        # 自軍の攻撃が当たってまだ生きている場合は、そのマスに敵艦が確実にいるのでマークする。
        if response is Response.Hit:
            io.info("自軍の攻撃が当たってまだ敵が生きているので tracking_cell を命中位置の %s にします。" %
                    last_my_op.detail.attack_pos.code(), thisFileLogger)
            return last_my_op.detail.attack_pos

        # 以下の流れで自軍の攻撃が当たらなかった場合 (response が Near または Nothing の場合)。
        #    1. マーク位置がある
        #    2. 敵艦が移動
        if (current_tracking_cell is not None) and (last_opponent_op is not None) and last_opponent_op.is_move():
            my_attacked_pos = last_my_op.detail.attack_pos
            # 自軍は敵の移動に追従せずもとの位置に撃ったが、当たらなかったので敵の移動はフェイントでは無かった。移動先に敵艦が確実にいる。
            if my_attacked_pos == current_tracking_cell:
                y, x = current_tracking_cell
                dirY = last_opponent_op.detail.dirY
                dirX = last_opponent_op.detail.dirX
                ret = Pos(y + dirY, x + dirX)
                io.info("敵の移動に追従ぜず もとの位置に撃ったものの命中しませんでした。", thisFileLogger)
                io.info("敵の移動はフェイントではなかったので tracking_cell を敵の移動に従って %s -> %s にします。" %
                        (current_tracking_cell.code(), ret.code()), thisFileLogger)
                return ret
            # 自軍は敵の移動に追従して撃ったが、当たらなかったので敵の移動はフェイントだった。もとの位置に敵艦が確実にいる。
            else:
                io.info("敵の移動に追従して 移動先に撃ったものの命中しませんでした。", thisFileLogger)
                io.info("敵の移動はフェイントだったので tracking_cell をもとの位置 %s にします。" % current_tracking_cell.code(), thisFileLogger)
                return current_tracking_cell

        # 自軍の攻撃が当たらなかったけど敵の位置が明らかで移動していないならもとのマーク位置をそのまま返す。
        if (current_tracking_cell is not None) and (last_opponent_op is not None) and (not last_opponent_op.is_move()):
            io.info("自軍の攻撃は当たらなかったものの直前の敵の位置が明らかで敵は移動していないので、 tracking_cell は維持します。", thisFileLogger)
            return current_tracking_cell

        # 敵艦の確実な位置がわからないので None
        return None
    # -------- END OF `if my_last_op.is_attack()` ----------
    # 以下、自軍の直前操作が攻撃ではない場合:

    # 敵艦の位置が明らかで、なおかつ敵が移動していない場合は 追跡中のセル位置をそのまま返す。
    if (current_tracking_cell is not None) and (not last_opponent_op.is_move()):
        return current_tracking_cell

    # 敵艦の確実な位置がわからないので None
    return None
