#!/usr/bin/env python3

from bluedragon import io
from bluedragon import logic
from bluedragon import model


def main():
    # 初手・後手の入力
    io.newline()
    is_me_first = io.ask_yesno("Is my team first? [y/n]: ")

    # 対戦データの初期化
    battle_data = model.BattleData()
    logic.initialize_my_placement(battle_data)

    # 初期配置の表示
    io.dump_my_grid(battle_data)

    def my_turn():
        # 自軍の操作を計算させて取得, 表示, battle_data に反映
        op = logic.suggest_my_op(battle_data)
        io.info(op)
        logic.apply_my_op(battle_data, op)

        # 攻撃に対する敵軍の反応を入力
        if op.is_attack():
            response = io.read_response()
            io.info(response)
            logic.apply_attack_response(battle_data, response)

    def opponent_turn():
        # 敵軍の操作を入力, 表示, battle_data に反映
        op = io.read_opponent_op()
        io.info(op)
        logic.apply_opponent_op(battle_data, op)

    # 現在が自軍のターンなら True。 ループ毎にトグルする。
    is_current_my_turn = is_me_first

    # 自軍・敵軍のどちらかの潜水艦の数が 0 になるまでループを続ける
    while not battle_data.has_game_finished():
        if is_current_my_turn:
            print("\n---------------------- My turn ----------------------")
            my_turn()
        else:
            print("\n------------------- Opponent turn -------------------")
            opponent_turn()

        is_current_my_turn = not is_current_my_turn
        io.dump_my_grid(battle_data)

    io.newline()
    if battle_data.my_alive_count <= 0:
        print("We lose...")
    else:
        print("We win!!")
    io.newline()


if __name__ == "__main__":
    main()
