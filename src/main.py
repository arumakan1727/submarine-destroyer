#!/usr/bin/env python3
import logging as _logging
import os
import sys
from datetime import datetime
from typing import List

from bluedragon import io
from bluedragon import logic
from bluedragon import model

log_directory = os.path.join(os.path.expanduser("~"), ".submarine-destroyer", "log")
log_file = os.path.join(log_directory, datetime.now().strftime("%Y-%m-%d_%H:%M:%S.log"))
log_format = "%(asctime)s %(name)-18s %(levelname)-8s %(message)s"
log_date_format = "%H:%M:%S"

os.makedirs(log_directory, exist_ok=True)
print("ログを `%s` に書き込みます" % log_file)

_logging.basicConfig(filename=log_file, format=log_format, level=_logging.DEBUG, datefmt=log_date_format)
logger = _logging.getLogger(__name__)


def main(argv: List[str]):
    logger.info("main() called")
    logger.debug("argv: %s" % argv)

    # ウェイ
    io.print_title()

    if "-q" in argv:
        io.success("`-q` オプションが付与されたので自軍の配置の表示を抑制します。", logger=None)
        should_show_my_positions = False
    else:
        io.info("Hint: `-q` オプションをつけて実行すると自軍の配置の表示を抑制できます。", logger=None)
        should_show_my_positions = True

    if "-n" in argv:
        i = argv.index("-n") + 1
        if i >= len(argv) or not argv[i].isdigit():
            io.newline()
            io.fail("`-n` オプションが指定されましたが敵艦の初期個数が指定されていません", logger=None)
            io.info("Usage: `-n <integer>`", logger=None)
            sys.exit(1)

        opponent_initial_submarine_count = int(argv[i])
        io.newline()
        io.success("`-n` オプションが指定され、敵艦の初期個数が %d に設定されました。" % opponent_initial_submarine_count, logger)
    else:
        io.newline()
        io.info("`-n <integer>` をつけて実行すると敵艦の初期個数を指定できます。", logger=None)
        io.info("敵艦の初期個数が指定されていないのでデフォルト値である 4 に設定します。", logger)
        opponent_initial_submarine_count = 4

    # 初手・後手の入力
    io.newline()
    is_me_first = io.ask_yesno("私達のチームが先手ですか？ [y/n]: ")
    logger.info("is_me_first = %s", is_me_first)

    # 対戦データの初期化
    battle_data = model.BattleData(opponent_initial_submarine_count)
    logic.initialize_my_placement(battle_data)

    # 初期配置の表示
    if should_show_my_positions:
        io.dump_my_grid(battle_data)

    def my_turn(cur_turn_count: int):
        # 自軍の操作を計算させて取得, 表示, battle_data に反映
        op = logic.suggest_my_op(battle_data, cur_turn_count)

        io.newline()
        io.success("自軍の操作: " + io.Color.yellow(op), logger)
        io.newline()

        logic.apply_my_op(battle_data, op)

        # 攻撃に対する敵軍の反応を入力
        if op.is_attack():
            response = io.read_response()
            io.success("次の入力を受け取りました: " + io.Color.green(response), logger)
            logic.apply_attack_response(battle_data, response)

        # 攻撃対象のマス位置を更新 (明確な敵艦の位置がわからなければ None になる)
        logic.update_tracking_cell(battle_data)

    def opponent_turn(cur_turn_count: int):
        # 敵軍の操作を入力, 表示, battle_data に反映
        op = io.read_opponent_op(cur_turn_count)
        io.success("次の入力を受け取りました: " + io.Color.green(op), logger)
        resp_from_me = logic.apply_opponent_op(battle_data, op)

        # 敵軍が攻撃したならそれに対する自軍の反応を表示
        if op.is_attack():
            assert resp_from_me is not None
            io.success("敵が攻撃しました。 自軍への命中状況: " + io.Color.yellow(resp_from_me), logger)

    # 現在が自軍のターンなら True。 ループ毎にトグルする。
    is_current_my_turn = is_me_first

    # ターン数
    turn_count = 0

    # 自軍・敵軍のどちらかの潜水艦の数が 0 になるまでループを続ける
    while not battle_data.has_game_finished():
        turn_count += 1
        if is_current_my_turn:
            print("\n---------------------- [Turn%02d] My turn ----------------------" % turn_count)
            logger.info("---------------------- [Turn%02d] My turn ----------------------" % turn_count)
            my_turn(turn_count)
        else:
            print("\n------------------- [Turn%02d] Opponent turn -------------------" % turn_count)
            logger.info("------------------- [Turn%02d] Opponent turn -------------------" % turn_count)
            opponent_turn(turn_count)

        print("次へ進むにはEnterを押してください。", end='')
        input()

        is_current_my_turn = not is_current_my_turn
        io.dump_battle_data(battle_data, should_show_my_positions)

    io.newline()
    if battle_data.my_alive_count <= 0:
        print("We lose...")
        logger.info("We lose...")
    else:
        print("We win!!")
        logger.info("We win!!")
    io.newline()


if __name__ == "__main__":
    main(sys.argv)
