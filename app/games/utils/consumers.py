# app/games/utils/consumers.py

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

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

User = get_user_model()


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
            elif content.get("type") == "surrender":
                user = self.scope.get("user")
                final_state = await self.handle_surrender(user)
                if final_state:
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_final", "state": final_state}
                    )
                else:
                    await self.send_json(
                        {"type": "error", "message": "항복할 수 없습니다"}
                    )
            elif content.get("type") == "reset_practice":
                # 연습 모드 게임 리셋
                await self.reset_practice_game()
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

    async def game_deleted(self, event):
        """게임 삭제 시 로비로 리다이렉트"""
        try:
            await self.send_json({"type": "game_deleted"})
        except Exception as e:
            print("[WS][game_deleted] ERROR:", repr(e))

    async def player_joined(self, event):
        """플레이어 입장 시 게임판 초기화 및 알림"""
        try:
            game = await self.get_game()
            state = await self.game_state(game)
            await self.send_json({"type": "player_joined", **state})
        except Exception as e:
            print("[WS][player_joined] ERROR:", repr(e))

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

        # 타이머 계산: 현재 턴인 플레이어의 시간 차감
        black_time = game.black_time_remaining
        white_time = game.white_time_remaining

        if game.last_move_time and not game.winner:
            # 마지막 착수 이후 경과 시간 계산
            elapsed = (timezone.now() - game.last_move_time).total_seconds()
            if game.turn == "black":
                black_time = max(0, black_time - int(elapsed))
            else:
                white_time = max(0, white_time - int(elapsed))

        return {
            "board": game.board,
            "turn": game.turn,
            "winner": game.winner,
            "size": BOARD_SIZE,
            "black_player": black_name,
            "white_player": white_name,
            "black_time": black_time,
            "white_time": white_time,
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

            # 타이머 업데이트: 현재 턴 플레이어의 시간 차감
            if game.last_move_time and game.black and game.white:
                elapsed = (timezone.now() - game.last_move_time).total_seconds()
                if game.turn == "black":
                    game.black_time_remaining = max(
                        0, game.black_time_remaining - int(elapsed)
                    )
                else:
                    game.white_time_remaining = max(
                        0, game.white_time_remaining - int(elapsed)
                    )

            # 타임아웃 체크: 현재 턴 플레이어의 시간이 0이면 자동 패배
            if game.black and game.white:
                if game.turn == "black" and game.black_time_remaining <= 0:
                    game.winner = "white"
                    black_name = (
                        game.black.first_name or game.black.username
                        if game.black
                        else None
                    )
                    white_name = (
                        game.white.first_name or game.white.username
                        if game.white
                        else None
                    )
                    final_state = {
                        "board": game.board,
                        "turn": game.turn,
                        "winner": game.winner,
                        "size": BOARD_SIZE,
                        "black_player": black_name,
                        "white_player": white_name,
                        "black_time": 0,
                        "white_time": game.white_time_remaining,
                    }
                    total_moves = Move.objects.filter(game=game).count()
                    GameHistory.objects.create(
                        game_id=game.id,
                        black=game.black,
                        white=game.white,
                        winner=game.winner,
                        created_at=game.created_at,
                        total_moves=total_moves,
                    )
                    game.delete()
                    return False, "시간 초과로 패배하였습니다", final_state
                elif game.turn == "white" and game.white_time_remaining <= 0:
                    game.winner = "black"
                    black_name = (
                        game.black.first_name or game.black.username
                        if game.black
                        else None
                    )
                    white_name = (
                        game.white.first_name or game.white.username
                        if game.white
                        else None
                    )
                    final_state = {
                        "board": game.board,
                        "turn": game.turn,
                        "winner": game.winner,
                        "size": BOARD_SIZE,
                        "black_player": black_name,
                        "white_player": white_name,
                        "black_time": game.black_time_remaining,
                        "white_time": 0,
                    }
                    total_moves = Move.objects.filter(game=game).count()
                    GameHistory.objects.create(
                        game_id=game.id,
                        black=game.black,
                        white=game.white,
                        winner=game.winner,
                        created_at=game.created_at,
                        total_moves=total_moves,
                    )
                    game.delete()
                    return False, "시간 초과로 패배하였습니다", final_state

            # 턴 검증(선택)
            expected_user = game.black if game.turn == "black" else game.white
            if (
                expected_user
                and getattr(user, "is_authenticated", False)
                and user != expected_user
            ):
                return False, "현재 상대 턴 입니다.", None

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

            # last_move_time 업데이트 (양쪽 플레이어가 있을 때만)
            if game.black and game.white:
                game.last_move_time = timezone.now()

            # 게임 종료 시 전적 기록 생성 및 게임 삭제
            if game.winner:
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
                    "black_time": game.black_time_remaining,
                    "white_time": game.white_time_remaining,
                }

                # 양쪽 플레이어가 모두 있는 경우만 전적 기록 및 게임 삭제
                if game.black and game.white:
                    total_moves = Move.objects.filter(game=game).count()
                    GameHistory.objects.create(
                        game_id=game.id,
                        black=game.black,
                        white=game.white,
                        winner=game.winner,
                        created_at=game.created_at,
                        total_moves=total_moves,
                    )
                    # 게임 삭제 (CASCADE로 Move도 함께 삭제됨)
                    game.delete()
                    return True, "ok", final_state  # 최종 상태 반환
                else:
                    # 혼자 플레이(연습 모드): 게임을 삭제하지 않고 상태만 반환
                    # 프론트엔드에서 리셋 처리
                    game.save(
                        update_fields=[
                            "board",
                            "turn",
                            "winner",
                            "black_time_remaining",
                            "white_time_remaining",
                            "last_move_time",
                        ]
                    )
                    return True, "ok", final_state

            # 저장
            game.save(
                update_fields=[
                    "board",
                    "turn",
                    "winner",
                    "black_time_remaining",
                    "white_time_remaining",
                    "last_move_time",
                ]
            )
            return True, "ok", None  # 게임 진행 중

    @database_sync_to_async
    def reset_practice_game(self):
        """연습 모드 게임 리셋"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임판 초기화
            game.board = "." * (BOARD_SIZE * BOARD_SIZE)
            game.turn = "black"
            game.winner = None
            # 타이머 리셋
            game.black_time_remaining = 900
            game.white_time_remaining = 900
            game.last_move_time = None
            game.save(
                update_fields=[
                    "board",
                    "turn",
                    "winner",
                    "black_time_remaining",
                    "white_time_remaining",
                    "last_move_time",
                ]
            )

            # 수 기록 삭제
            Move.objects.filter(game=game).delete()

    @database_sync_to_async
    def handle_surrender(self, user):
        """항복 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 이미 종료된 경우
            if game.winner:
                return None

            # 양쪽 플레이어가 없으면 항복할 수 없음
            if not game.black or not game.white:
                return None

            # 항복한 사용자가 게임 참가자인지 확인 및 승자 결정
            if user == game.black:
                game.winner = "white"
            elif user == game.white:
                game.winner = "black"
            else:
                return None  # 게임 참가자가 아님

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
            return final_state


class LobbyConsumer(AsyncJsonWebsocketConsumer):
    """로비 실시간 접속자 목록 관리"""

    # 클래스 레벨에서 접속자 관리 (channel_name -> user_id 매핑)
    connected_users = {}

    async def connect(self):
        try:
            self.group_name = "lobby"
            user = self.scope.get("user")

            # 인증된 사용자만 허용
            if not user or not user.is_authenticated:
                await self.close(code=4003)
                return

            self.user_id = user.id
            self.user_nickname = user.first_name or user.username

            # 그룹 추가
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            # 접속자 목록에 추가
            LobbyConsumer.connected_users[self.channel_name] = {
                "user_id": self.user_id,
                "nickname": self.user_nickname,
            }

            # 현재 접속자 목록 전송
            users = await self.get_online_users()
            await self.send_json({"type": "users", "users": users})

            # 다른 사용자들에게 새 접속자 알림
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_joined",
                    "user_info": {
                        "user_id": self.user_id,
                        "nickname": self.user_nickname,
                    },
                },
            )

        except Exception as e:
            print("[LobbyWS][connect] ERROR:", repr(e))
            try:
                await self.close(code=4000)
            except Exception:
                pass

    async def disconnect(self, code):
        try:
            # 접속자 목록에서 제거
            if self.channel_name in LobbyConsumer.connected_users:
                del LobbyConsumer.connected_users[self.channel_name]

            # 그룹에서 제거
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

            # 다른 사용자들에게 퇴장 알림
            await self.channel_layer.group_send(
                self.group_name, {"type": "user_left", "user_id": self.user_id}
            )

        except Exception as e:
            print("[LobbyWS][disconnect] ERROR:", repr(e))

    async def user_joined(self, event):
        """새 사용자 접속 알림"""
        try:
            # 자기 자신에게는 알리지 않음
            if event["user_info"]["user_id"] != self.user_id:
                users = await self.get_online_users()
                await self.send_json({"type": "users", "users": users})
        except Exception as e:
            print("[LobbyWS][user_joined] ERROR:", repr(e))

    async def user_left(self, event):
        """사용자 퇴장 알림"""
        try:
            # 자기 자신에게는 알리지 않음
            if event["user_id"] != self.user_id:
                users = await self.get_online_users()
                await self.send_json({"type": "users", "users": users})
        except Exception as e:
            print("[LobbyWS][user_left] ERROR:", repr(e))

    async def get_online_users(self):
        """현재 접속 중인 사용자 목록 반환 (중복 제거)"""
        # user_id 기준으로 중복 제거
        unique_users = {}
        for user_info in LobbyConsumer.connected_users.values():
            user_id = user_info["user_id"]
            if user_id not in unique_users:
                unique_users[user_id] = user_info

        return list(unique_users.values())
