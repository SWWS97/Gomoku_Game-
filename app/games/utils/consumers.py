# app/games/utils/consumers.py

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction

from ..models import BOARD_SIZE, Game, GameHistory, Move
from .omok import (
    BLACK,
    WHITE,
    check_five,
    debug_double_three,
    has_exact_five,
    is_forbidden_double_four,
    is_forbidden_double_three,
    is_overline,
)


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
            self.group = f"game_{self.game_id}"
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.accept()

            game = await self.get_game()
            state = await self.game_state(game)
            await self.send_json({"type": "state", **state})
        except Exception as e:
            print("[WS][connect] ERROR:", repr(e))
            try:
                await self.close(code=4000)
            except Exception:
                pass

    async def disconnect(self, code):
        try:
            await self.channel_layer.group_discard(self.group, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
        try:
            if content.get("type") == "play":
                x = int(content["x"])
                y = int(content["y"])
                user = self.scope.get("user")

                ok, msg, final_state = await self.try_play(user, x, y)
                if not ok:
                    await self.send_json({"type": "error", "message": msg})
                    return

                # final_state가 있으면 게임 종료 (승자 정보 포함)
                if final_state:
                    # 게임이 삭제되었으므로 저장된 상태를 직접 broadcast
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_final", "state": final_state}
                    )
                else:
                    # 게임 진행 중이면 일반 broadcast
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_state"}
                    )
        except Exception as e:
            print("[WS][receive_json] ERROR:", repr(e))
            await self.close(code=4001)

    async def broadcast_state(self, _event):
        try:
            game = await self.get_game()
            state = await self.game_state(game)
            await self.send_json({"type": "state", **state})
        except Exception as e:
            print("[WS][broadcast_state] ERROR:", repr(e))

    async def broadcast_final(self, event):
        """게임 종료 시 최종 상태 전송 (게임이 이미 삭제됨)"""
        try:
            state = event["state"]
            await self.send_json({"type": "state", **state})
        except Exception as e:
            print("[WS][broadcast_final] ERROR:", repr(e))

    # ---------------------
    # DB helpers
    # ---------------------
    @database_sync_to_async
    def get_game(self):
        return Game.objects.get(pk=self.game_id)

    @database_sync_to_async
    def game_state(self, game: Game):
        # 닉네임 표시 (first_name이 있으면 사용, 없으면 username)
        black_name = None
        if game.black:
            black_name = game.black.first_name or game.black.username

        white_name = None
        if game.white:
            white_name = game.white.first_name or game.white.username

        return {
            "board": game.board,
            "turn": game.turn,
            "winner": game.winner,
            "size": BOARD_SIZE,
            "black_player": black_name,
            "white_player": white_name,
        }

    @database_sync_to_async
    def try_play(self, user, x, y):
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 기본 검증
            if game.winner:
                return False, "game finished", None
            if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
                return False, "out of bounds", None
            if game.get_cell(x, y) != ".":
                return False, "occupied", None

            # 턴 검증(선택)
            expected_user = game.black if game.turn == "black" else game.white
            if (
                expected_user
                and getattr(user, "is_authenticated", False)
                and user != expected_user
            ):
                return False, "not your turn", None

            # 이번 수의 돌 문자 통일 ("B"/"W")
            stone = game.stone_of_turn()
            if stone in ("black", "white"):
                stone = BLACK if stone == "black" else WHITE

            # 2D 스냅샷 생성 (판정기는 2D 기대)
            board2d = [
                [game.get_cell(i, j) for j in range(BOARD_SIZE)]
                for i in range(BOARD_SIZE)
            ]

            # --- 렌주 정석 금수: 흑만 ---
            if stone == BLACK:
                # 장목 금수
                if is_overline(board2d, x, y, BLACK):
                    return False, "장목 금수입니다. (6+)", None
                # 44 금수
                if is_forbidden_double_four(board2d, x, y, BLACK):
                    return False, "44 금수입니다. (44)", None
                # 33 금수
                if is_forbidden_double_three(board2d, x, y, BLACK):
                    # 로그용 디버그(결정은 본판정으로 이미 함)
                    dbg = debug_double_three(board2d, x, y, BLACK)
                    print(
                        f"[33-DEBUG] try=({x},{y}) dirs={dbg['dirs']} spots={dbg['spots']} is33={dbg['is33']}"
                    )
                    return False, "33 금수입니다. (33)", None

            # 실제 착수
            game.set_cell(x, y, stone)

            # 수 기록
            move_order = Move.objects.filter(game=game).count() + 1
            Move.objects.create(
                game=game,
                player=user if getattr(user, "is_authenticated", False) else None,
                x=x,
                y=y,
                order=move_order,
            )

            # 승리 판정
            board2d[x][y] = stone  # 스냅샷도 업데이트
            if stone == BLACK:
                # 흑은 '정확 5목'만 승리 (장목은 위에서 이미 금수 처리)
                if has_exact_five(board2d, x, y, BLACK):
                    game.winner = game.turn
                else:
                    game.swap_turn()
            else:
                # 백은 5목 이상 승리
                if check_five(board2d, WHITE):
                    game.winner = game.turn
                else:
                    game.swap_turn()

            # 게임 종료 시 전적 기록 생성 및 게임 삭제
            if game.winner:
                # 전적 기록 생성
                total_moves = Move.objects.filter(game=game).count()
                GameHistory.objects.create(
                    game_id=game.id,
                    black=game.black,
                    white=game.white,
                    winner=game.winner,
                    created_at=game.created_at,
                    total_moves=total_moves,
                )

                # 삭제 전에 최종 상태 저장 (broadcast용)
                black_name = (
                    game.black.first_name or game.black.username if game.black else None
                )
                white_name = (
                    game.white.first_name or game.white.username if game.white else None
                )
                final_state = {
                    "board": game.board,
                    "turn": game.turn,
                    "winner": game.winner,
                    "size": BOARD_SIZE,
                    "black_player": black_name,
                    "white_player": white_name,
                }

                # 게임 삭제 (CASCADE로 Move도 함께 삭제됨)
                game.delete()
                return True, "ok", final_state  # 최종 상태 반환

            # 저장
            game.save(update_fields=["board", "turn", "winner"])
            return True, "ok", None  # 게임 진행 중
