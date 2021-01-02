from unittest import TestCase

from . import logic
from .model import *
from .traits import set_of_around_cells


def create_initial_prob_grid(submarine_count: int) -> np.ndarray:
    return np.full((5, 5), submarine_count / 25, dtype=np.float64)


class TestUpdateProb(TestCase):
    def test__update_prob_for_my_attack_hit_01(self):
        def test_sub(p: Pos):
            m = create_initial_prob_grid(submarine_count=4)
            logic._update_prob_for_my_attack_hit(m, p, 4)
            print(m)
            self.assertAlmostEqual(m.sum(), 4)
            self.assertEqual(m[p.row, p.col], 1)

        test_sub(Pos(0, 0))
        test_sub(Pos(0, 1))
        test_sub(Pos(2, 2))
        test_sub(Pos(4, 4))

    def test__update_prob_for_my_attack_hit_02(self):
        """
        エリア内に4隻いるとして、異なる4マスにヒット情報を適用する。
        ヒット情報を適用した4マスは全て確率1となり、それ以外のマスは全て確率ゼロとなるはず。
        """
        m = create_initial_prob_grid(4)
        p1 = Pos(0, 0)
        p2 = Pos(0, 4)
        p3 = Pos(2, 2)
        p4 = Pos(4, 3)
        logic._update_prob_for_my_attack_hit(m, p1, 4)
        print(m)
        logic._update_prob_for_my_attack_hit(m, p2, 4)
        print(m)
        logic._update_prob_for_my_attack_hit(m, p3, 4)
        print(m)
        logic._update_prob_for_my_attack_hit(m, p4, 4)
        print(m)

        self.assertEqual(m[p1.row, p1.col], 1)
        self.assertEqual(m[p2.row, p2.col], 1)
        self.assertEqual(m[p3.row, p3.col], 1)
        self.assertEqual(m[p4.row, p4.col], 1)
        self.assertEqual(m.sum(), 4)

    def test__update_prob_for_my_attack_hit_03(self):
        """
        同一のマスに連続でヒット情報を適用する。
        """
        m = create_initial_prob_grid(4)
        p = Pos(1, 1)
        logic._update_prob_for_my_attack_hit(m, p, 4)
        logic._update_prob_for_my_attack_hit(m, p, 4)
        logic._update_prob_for_my_attack_hit(m, p, 4)
        logic._update_prob_for_my_attack_hit(m, p, 4)
        self.assertEqual(m[p.row, p.col], 1)

    def test__update_prob_for_my_attack_dead_01(self):
        m = create_initial_prob_grid(4)
        p = Pos(1, 1)
        logic._update_prob_for_my_attack_dead(m, p, 4)
        self.assertEqual(m[p.row, p.col], 0)
        self.assertEqual(m.sum(), 3)

    def test__update_prob_for_my_attack_near_01(self):
        m = create_initial_prob_grid(4)
        p = Pos(2, 2)
        logic._update_prob_for_my_attack_near(m, p, 4)
        print(m)
        self.assertEqual(m[p.row, p.col], 0)
        self.assertAlmostEqual(m.sum(), 4)

    def test__update_prob_for_my_attack_nothing_01(self):
        m = create_initial_prob_grid(4)
        p = Pos(2, 2)
        logic._update_prob_for_my_attack_nothing(m, p)
        print(m)
        self.assertEqual(m[p.row, p.col], 0)
        self.assertTrue(all(m[y, x] == 0 for y, x in set_of_around_cells(p)))

    def test__update_prob_something(self):
        m = create_initial_prob_grid(4)
        pX = Pos(3, 1)
        p1 = Pos(2, 2)
        p2 = Pos(0, 4)
        p3 = Pos(2, 1)
        logic._update_prob_for_my_attack_near(m, p1, 4)
        self.assertAlmostEqual(4, m.sum())

        logic._update_prob_for_my_attack_hit(m, pX, 4)
        self.assertAlmostEqual(4, m.sum())
        self.assertEqual(1, m[pX.row, pX.col])

        logic._update_prob_for_my_attack_near(m, p2, 4)
        self.assertAlmostEqual(4, m.sum())
        self.assertEqual(1, m[pX.row, pX.col])

        logic._update_prob_for_my_attack_hit(m, pX, 4)
        self.assertAlmostEqual(4, m.sum())
        self.assertEqual(1, m[pX.row, pX.col])

        logic._update_prob_for_my_attack_near(m, p3, 4)
        print(m)
        self.assertAlmostEqual(4, m.sum())
        self.assertEqual(1, m[pX.row, pX.col])

    def test__update_prob_for_opponent_move_01(self):
        m = create_initial_prob_grid(4)
        logic._update_prob_for_opponent_move(m, MoveInfo(fromPos=None, dirY=2, dirX=0))
        self.assertAlmostEqual(4.0, m.sum())

    def test__update_prob_for_opponent_move_02(self):
        m = create_initial_prob_grid(4)
        logic._update_prob_for_my_attack_near(m, Pos(2, 2), 4)
        logic._update_prob_for_my_attack_near(m, Pos(3, 0), 4)
        logic._update_prob_for_my_attack_near(m, Pos(3, 2), 4)
        print("--------- move before ------------")
        print(m)

        logic._update_prob_for_opponent_move(m, MoveInfo(fromPos=None, dirY=2, dirX=0))
        print("--------- move after ------------")
        print(m)
        self.assertAlmostEqual(4.0, m.sum())
