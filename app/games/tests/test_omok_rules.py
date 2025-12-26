# -*- coding: utf-8 -*-
import unittest

# 추천: 상대 임포트
from ..utils.omok import (
    BLACK,
    EMPTY,
    WHITE,
    check_five,
    has_exact_five,
    is_forbidden_double_four,
    is_forbidden_double_three,
    is_overline,
)


# --- 테스트 유틸 ---
def board(n=15):
    """n x n 빈 보드 생성"""
    return [[EMPTY for _ in range(n)] for _ in range(n)]


def put(bd, coords, stone):
    """coords = [(x,y), ...] 에 stone을 배치"""
    for x, y in coords:
        bd[x][y] = stone
    return bd


class OmokRuleTests(unittest.TestCase):
    # ---------- 장목/정확5/백5이상 ----------
    def test_black_exact_five_true_overline_false(self):
        # 흑: 정확히 5목은 승리, 장목은 금수로 분리 (여기선 엔진 함수만 검증)
        bd = board()
        # 가로에 4개 미리 두고, (0,4) 두면 정확히 5
        put(bd, [(0, 0), (0, 1), (0, 2), (0, 3)], BLACK)
        bd2 = [row[:] for row in bd]
        self.assertFalse(is_overline(bd2, 0, 4, BLACK))
        bd2[0][4] = BLACK
        self.assertTrue(has_exact_five(bd2, 0, 4, BLACK))
        # 6목(장목)
        bd3 = [row[:] for row in bd]
        put(bd3, [(0, 4)], BLACK)  # 5개
        # (0,5)에 두기 전엔 장목 아님(현재 보드만 검사)
        self.assertFalse(is_overline(bd3, 0, 5, BLACK, present_only=True))
        # (0,5)에 두면 장목(한 수 둔다고 가정하는 시뮬레이션)
        self.assertTrue(
            is_overline([row[:] for row in bd3], 0, 5, BLACK, simulate=True)
        )

    def test_white_five_or_more_is_win(self):
        # 백은 5개 이상이면 check_five True
        bd = board()
        put(bd, [(3, 3), (3, 4), (3, 5), (3, 6), (3, 7)], WHITE)
        self.assertTrue(check_five(bd, WHITE))

    # ---------- 33(쌍삼) ----------
    def test_double_three_black_only(self):
        # 동일 배치에서 백은 금수 아님, 흑은 금수
        bd = board()
        # 중심 (7,7)에 둘 차례로 생각하고 주변에 '열린3'이 양방향 생기게 배치
        # 가로: .BB.B. 형태 (중앙 7,7에 두면 .BBB.)
        put(bd, [(7, 5), (7, 6)], BLACK)  # BB . (중앙 7,7) . B
        put(bd, [(7, 9)], BLACK)  # 한 칸 띄워서 B
        # 세로: .BB.B. 형태 (중앙 7,7에 두면 .BBB.)
        put(bd, [(5, 7), (6, 7)], BLACK)  # BB . (중앙 7,7) . B
        put(bd, [(9, 7)], BLACK)  # 한 칸 띄워서 B

        # 흑이 (7,7)에 두면 가로/세로 모두 열린3 (.BBB.) → 쌍삼 금수
        self.assertTrue(is_forbidden_double_three([row[:] for row in bd], 7, 7, BLACK))
        # 백은 동일 위치 허용
        self.assertFalse(is_forbidden_double_three([row[:] for row in bd], 7, 7, WHITE))

    def test_plus_shape_closed_three_is_not_double_three(self):
        # 십자(가로3 + 세로3)처럼 보이더라도 한쪽이 '닫힌3'이면 33이 아니다.
        bd = board()
        # 세로 3은 열린3이 되도록 비워두고
        put(bd, [(4, 5), (6, 5)], BLACK)  # 세로에서 .B . B . 구조 (중앙 5,5에 둘 예정)
        # 가로 3은 한쪽 끝을 같은 색으로 막아서 닫힌3으로 만들기
        put(bd, [(5, 4)], BLACK)
        put(bd, [(5, 6)], BLACK)
        put(bd, [(5, 7)], BLACK)  # 오른쪽이 막힌 형태
        put(bd, [(5, 8)], BLACK)

        # (5,5)에 흑을 두면 세로는 열린3이지만, 가로는 닫힌3 → 33 아님
        self.assertFalse(is_forbidden_double_three([row[:] for row in bd], 5, 5, BLACK))

    def test_clear_double_three_with_two_open_threes(self):
        # 확실한 쌍삼 케이스: 두 방향 모두 .BBB. 가 되게 구성
        bd = board()
        # 가로 라인: ..B.B.. (중앙에 두면 .BB.B. 포함)
        put(bd, [(8, 6), (8, 8)], BLACK)
        # 세로 라인: ..B.B.. (중앙에 두면 .BB.B. 포함)
        put(bd, [(6, 7), (10, 7)], BLACK)
        # (8,7)에 흑을 두면 가로/세로 모두 열린3 → 33
        self.assertTrue(is_forbidden_double_three([row[:] for row in bd], 8, 7, BLACK))

    # ---------- 44(쌍사) ----------
    def test_double_four(self):
        bd = board()
        # (7,7)에 둘 때 가로/세로에 동시에 .BBBB. 생기게 구성
        # 가로: B B B .  (좌우 하나씩 비워져 있어 중앙에 두면 .BBBB.)
        put(bd, [(7, 5), (7, 6), (7, 8)], BLACK)
        # 세로: B B B .  (위아래 하나씩 비워져 있어 중앙에 두면 .BBBB.)
        put(bd, [(5, 7), (6, 7), (8, 7)], BLACK)

        self.assertTrue(is_forbidden_double_four([row[:] for row in bd], 7, 7, BLACK))
        # 백은 허용
        self.assertFalse(is_forbidden_double_four([row[:] for row in bd], 7, 7, WHITE))

    # ---------- 경계/기본 ----------
    def test_out_of_bounds_and_occupied_behaviour(self):
        bd = board(5)
        # 보드 밖은 33/44 판단함수에서는 False로 처리(안 다룸), 엔진 호출부에서 별도 체크
        self.assertFalse(
            is_forbidden_double_three([row[:] for row in bd], -1, 0, BLACK)
        )
        self.assertFalse(
            is_forbidden_double_four([row[:] for row in bd], 10, 10, BLACK)
        )
        # 이미 돌이 있는 칸: 내부 구현상 True(둘 수 없음 취지)일 수 있으므로 빈 칸 사용 권장
        bd[2][2] = BLACK
        self.assertTrue(is_forbidden_double_three([row[:] for row in bd], 2, 2, BLACK))
