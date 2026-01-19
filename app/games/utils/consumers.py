# app/games/utils/consumers.py

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from ..models import BOARD_SIZE, Game, GameHistory, Move
from app.accounts.models import UserProfile, calculate_elo, INITIAL_RATING
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

# 욕설 필터링 목록
PROFANITY_WORDS = [
    "시발",
    "씨발",
    "ㅅㅂ",
    "ㅆㅂ",
    "병신",
    "ㅂㅅ",
    "개새",
    "새끼",
    "ㅅㄲ",
    "fuck",
    "shit",
    "damn",
    "ass",
    "bitch",
    "dick",
    "pussy",
    "지랄",
    "좆",
    "ㅈㄹ",
    "닥쳐",
    "꺼져",
    "죽어",
    "개같",
    "개노",
    "병1신",
    "호로",
    "시1발",
    "씨1발",
]


def filter_profanity(text):
    """욕설 필터링 함수"""
    filtered_text = text
    for word in PROFANITY_WORDS:
        if word in filtered_text:
            filtered_text = filtered_text.replace(word, "*" * len(word))
    return filtered_text


def update_user_stats(black_user, white_user, winner):
    """
    게임 종료 시 사용자 전적 및 레이팅 업데이트
    Returns: dict with rating changes
    """
    # 프로필이 없으면 생성 (초기 레이팅 1000점)
    black_profile, _ = UserProfile.objects.get_or_create(
        user=black_user,
        defaults={"rating": INITIAL_RATING}
    )
    white_profile, _ = UserProfile.objects.get_or_create(
        user=white_user,
        defaults={"rating": INITIAL_RATING}
    )

    # 현재 레이팅 저장 (변동 계산용)
    old_black_rating = black_profile.rating
    old_white_rating = white_profile.rating

    # 승패 및 레이팅 업데이트
    if winner == "black":
        black_profile.wins += 1
        white_profile.losses += 1
        # 레이팅 계산: 흑 승리
        new_black, new_white, black_change, white_change = calculate_elo(
            black_profile.rating, white_profile.rating
        )
        black_profile.rating = new_black
        white_profile.rating = new_white
    else:  # winner == "white"
        white_profile.wins += 1
        black_profile.losses += 1
        # 레이팅 계산: 백 승리
        new_white, new_black, white_change, black_change = calculate_elo(
            white_profile.rating, black_profile.rating
        )
        black_profile.rating = new_black
        white_profile.rating = new_white

    black_profile.save(update_fields=["wins", "losses", "rating"])
    white_profile.save(update_fields=["wins", "losses", "rating"])

    # 레이팅 변동 정보 반환
    return {
        "black_rating": black_profile.rating,
        "white_rating": white_profile.rating,
        "black_rating_change": black_profile.rating - old_black_rating,
        "white_rating_change": white_profile.rating - old_white_rating,
    }


def record_game_result(game):
    """
    게임 종료 시 전적 기록 및 통계 업데이트
    Returns: dict with rating changes
    """
    total_moves = game.moves.count()
    GameHistory.objects.create(
        game_id=game.id,
        black=game.black,
        white=game.white,
        winner=game.winner,
        created_at=game.created_at,
        total_moves=total_moves,
    )
    return update_user_stats(game.black, game.white, game.winner)


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

            # 로비에 사용자 상태 변경 알림 (게임방 입장)
            await self.notify_lobby_status_change()
        except Exception as e:
            print("[WS][connect] ERROR:", repr(e))
            try:
                await self.close(code=4000)
            except Exception:
                pass

    async def disconnect(self, code):
        try:
            # 게임 종료 후 상대방에게 퇴장 알림
            user = self.scope.get("user")
            if user and user.is_authenticated:
                await self.notify_opponent_left(user)

            await self.channel_layer.group_discard(self.group, self.channel_name)

            # 브라우저 뒤로가기 등으로 연결이 끊긴 경우 게임 정리
            if user and user.is_authenticated:
                await self.cleanup_game_on_disconnect(user)

            # 로비에 사용자 상태 변경 알림 (게임방 퇴장)
            await self.notify_lobby_status_change()
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
            elif content.get("type") == "player_ready":
                # 플레이어 준비 완료
                user = self.scope.get("user")
                await self.handle_player_ready(user)
                await self.channel_layer.group_send(
                    self.group, {"type": "broadcast_ready_state"}
                )
            elif content.get("type") == "start_game":
                # 방장이 게임 시작
                user = self.scope.get("user")
                success = await self.handle_start_game(user)
                if success:
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_game_start"}
                    )
                else:
                    await self.send_json(
                        {"type": "error", "message": "게임을 시작할 수 없습니다"}
                    )
            elif content.get("type") == "request_rematch":
                # 리매치 요청
                user = self.scope.get("user")
                success = await self.handle_rematch_request(user)
                if success:
                    # 상대방에게 리매치 요청 알림
                    await self.channel_layer.group_send(
                        self.group,
                        {"type": "notify_rematch_request", "requester_id": user.id},
                    )
            elif content.get("type") == "accept_rematch":
                # 리매치 수락
                user = self.scope.get("user")
                success = await self.handle_rematch_accept(user)
                if success:
                    # 양쪽 모두 수락했으므로 카운트다운 시작
                    await self.channel_layer.group_send(
                        self.group, {"type": "notify_rematch_accepted"}
                    )
                    # 게임 리셋된 상태를 브로드캐스트
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_state"}
                    )
            elif content.get("type") == "decline_rematch":
                # 리매치 거절
                user = self.scope.get("user")
                await self.handle_rematch_decline(user)
                # 상대방에게 거절 알림
                await self.channel_layer.group_send(
                    self.group, {"type": "notify_rematch_declined"}
                )
            elif content.get("type") == "timeout":
                # 타임아웃으로 게임 종료
                timeout_player = content.get("player")
                final_state = await self.handle_timeout(timeout_player)
                if final_state:
                    await self.channel_layer.group_send(
                        self.group, {"type": "broadcast_final", "state": final_state}
                    )
            elif content.get("type") == "quick_chat":
                # 빠른 채팅 메시지 브로드캐스트
                message = content.get("message", "").strip()
                user = self.scope.get("user")
                if message and user and user.is_authenticated:
                    # 게임 정보 가져와서 발신자 색상 확인
                    is_black = await self.check_if_black_player(user.id)

                    # 상대방에게만 전송 (본인은 프론트엔드에서 이미 표시)
                    await self.channel_layer.group_send(
                        self.group,
                        {
                            "type": "broadcast_quick_chat",
                            "message": message,
                            "sender_id": user.id,
                            "is_black": is_black,
                        },
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
    def check_if_black_player(self, user_id):
        """사용자가 흑돌 플레이어인지 확인"""
        try:
            game = Game.objects.get(pk=self.game_id)
            return game.black_id == user_id if game.black_id else False
        except Game.DoesNotExist:
            return False

    @database_sync_to_async
    def game_state(self, game: Game):
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

        # 플레이어 레이팅 조회
        black_rating = INITIAL_RATING
        white_rating = INITIAL_RATING
        if game.black:
            black_profile = UserProfile.objects.filter(user=game.black).first()
            if black_profile:
                black_rating = black_profile.rating
        if game.white:
            white_profile = UserProfile.objects.filter(user=game.white).first()
            if white_profile:
                white_rating = white_profile.rating

        return {
            "board": game.board,
            "turn": game.turn,
            "winner": game.winner,
            "size": BOARD_SIZE,
            **game.get_both_player_names(),
            "black_time": black_time,
            "white_time": white_time,
            "black_ready": game.black_ready,
            "white_ready": game.white_ready,
            "game_started": game.game_started,
            "black_rating": black_rating,
            "white_rating": white_rating,
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
                return False, "이미 착수가 된 자리입니다.", None

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
                    final_state = {
                        "board": game.board,
                        "turn": game.turn,
                        "winner": game.winner,
                        "size": BOARD_SIZE,
                        **game.get_both_player_names(),
                        "black_time": 0,
                        "white_time": game.white_time_remaining,
                    }
                    record_game_result(game)
                    # 게임 저장 (리매치를 위해 삭제하지 않음)
                    game.save(
                        update_fields=[
                            "winner",
                            "black_time_remaining",
                            "white_time_remaining",
                        ]
                    )
                    return False, "시간 초과로 패배하였습니다", final_state
                elif game.turn == "white" and game.white_time_remaining <= 0:
                    game.winner = "black"
                    final_state = {
                        "board": game.board,
                        "turn": game.turn,
                        "winner": game.winner,
                        "size": BOARD_SIZE,
                        **game.get_both_player_names(),
                        "black_time": game.black_time_remaining,
                        "white_time": 0,
                    }
                    record_game_result(game)
                    # 게임 저장 (리매치를 위해 삭제하지 않음)
                    game.save(
                        update_fields=[
                            "winner",
                            "black_time_remaining",
                            "white_time_remaining",
                        ]
                    )
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
                final_state = {
                    "board": game.board,
                    "turn": game.turn,
                    "winner": game.winner,
                    "size": BOARD_SIZE,
                    **game.get_both_player_names(),
                    "black_time": game.black_time_remaining,
                    "white_time": game.white_time_remaining,
                }

                # 양쪽 플레이어가 모두 있는 경우만 전적 기록
                if game.black and game.white:
                    rating_info = record_game_result(game)
                    final_state.update(rating_info)
                    # 게임 저장 (리매치를 위해 삭제하지 않음)
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

            # 게임 초기화
            game.clear_moves()
            game.reset_for_new_round()
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

    async def broadcast_ready_state(self, _event):
        """준비 상태 브로드캐스트"""
        try:
            game = await self.get_game()
            user = self.scope.get("user")
            ready_state = await self.get_ready_state(game)
            # 현재 유저가 방장(흑)인지 확인
            is_room_creator = (
                user == game.black if user and user.is_authenticated else False
            )
            await self.send_json(
                {
                    "type": "ready_state",
                    "is_room_creator": is_room_creator,
                    **ready_state,
                }
            )
        except Exception as e:
            print("[WS][broadcast_ready_state] ERROR:", repr(e))

    async def broadcast_game_start(self, _event):
        """게임 시작 브로드캐스트"""
        try:
            game = await self.get_game()
            state = await self.game_state(game)
            await self.send_json({"type": "game_start", **state})
        except Exception as e:
            print("[WS][broadcast_game_start] ERROR:", repr(e))

    @database_sync_to_async
    def get_ready_state(self, game: Game):
        """준비 상태 반환"""
        return {
            "black_ready": game.black_ready,
            "white_ready": game.white_ready,
            "game_started": game.game_started,
            **game.get_both_player_names(),
        }

    @database_sync_to_async
    def handle_player_ready(self, user):
        """플레이어 준비 완료 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 이미 시작되었으면 무시
            if game.game_started:
                return

            # 사용자가 흑인지 백인지 확인하고 준비 상태 업데이트
            if user == game.black:
                game.black_ready = True
            elif user == game.white:
                game.white_ready = True

            game.save(update_fields=["black_ready", "white_ready"])

    @database_sync_to_async
    def handle_start_game(self, user):
        """게임 시작 처리 (방장만 가능)"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 방장(흑 플레이어)인지 확인
            if user != game.black:
                return False

            # 양쪽 모두 준비 완료되었는지 확인
            if not game.black_ready or not game.white_ready:
                return False

            # 게임 시작
            game.game_started = True
            game.last_move_time = timezone.now()  # 타이머 시작
            game.save(update_fields=["game_started", "last_move_time"])
            return True

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

            # 전적 기록 생성 및 레이팅 변동 정보 가져오기
            rating_info = record_game_result(game)

            # 최종 상태 저장 (broadcast용)
            final_state = {
                "board": game.board,
                "turn": game.turn,
                "winner": game.winner,
                "size": BOARD_SIZE,
                **game.get_both_player_names(),
                **rating_info,
            }

            # 게임 저장 (리매치를 위해 삭제하지 않음)
            game.save(update_fields=["winner"])
            return final_state

    @database_sync_to_async
    def handle_rematch_request(self, user):
        """리매치 요청 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 종료되지 않았으면 리매치 불가
            if not game.winner:
                return False

            # 양쪽 플레이어가 없으면 리매치 불가
            if not game.black or not game.white:
                return False

            # 사용자가 흑인지 백인지 확인하고 리매치 요청 상태 업데이트
            if user == game.black:
                game.rematch_black = True
            elif user == game.white:
                game.rematch_white = True
            else:
                return False  # 게임 참가자가 아님

            # 양쪽 모두 리매치 요청했으면 게임 리셋
            if game.rematch_black and game.rematch_white:
                # 흑/백 플레이어 교체 (색 교대)
                game.black, game.white = game.white, game.black

                # 게임 초기화
                game.clear_moves()
                game.reset_for_new_round()

                # 리매치 플래그 리셋
                game.rematch_black = False
                game.rematch_white = False
                # 준비 상태 초기화 (다시 준비완료 필요)
                game.black_ready = False
                game.white_ready = False
                game.game_started = False

                game.save(
                    update_fields=[
                        "board",
                        "turn",
                        "winner",
                        "black",
                        "white",
                        "black_time_remaining",
                        "white_time_remaining",
                        "last_move_time",
                        "rematch_black",
                        "rematch_white",
                        "black_ready",
                        "white_ready",
                        "game_started",
                    ]
                )
            else:
                # 한쪽만 요청한 경우 리매치 플래그만 저장
                game.save(update_fields=["rematch_black", "rematch_white"])

            return True

    async def broadcast_rematch_state(self, _event):
        """리매치 상태 브로드캐스트"""
        try:
            game = await self.get_game()
            rematch_state = await self.get_rematch_state(game)
            await self.send_json({"type": "rematch_state", **rematch_state})
        except Exception as e:
            print("[WS][broadcast_rematch_state] ERROR:", repr(e))

    @database_sync_to_async
    def get_rematch_state(self, game: Game):
        """리매치 상태 반환"""
        return {
            "rematch_black": game.rematch_black,
            "rematch_white": game.rematch_white,
            "game_reset": game.rematch_black and game.rematch_white,
        }

    @database_sync_to_async
    def handle_rematch_accept(self, user):
        """리매치 수락 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 종료되지 않았으면 리매치 불가
            if not game.winner:
                return False

            # 양쪽 플레이어가 없으면 리매치 불가
            if not game.black or not game.white:
                return False

            # 사용자가 흑인지 백인지 확인하고 리매치 수락 상태 업데이트
            if user == game.black:
                game.rematch_black = True
            elif user == game.white:
                game.rematch_white = True
            else:
                return False  # 게임 참가자가 아님

            # 양쪽 모두 수락했으면 게임 리셋
            if game.rematch_black and game.rematch_white:
                # 흑/백 플레이어 교체 (색 교대)
                game.black, game.white = game.white, game.black

                # 게임 초기화
                game.clear_moves()
                game.reset_for_new_round()

                # 리매치 플래그 리셋
                game.rematch_black = False
                game.rematch_white = False
                # 준비 상태 초기화 (다시 준비완료 필요)
                game.black_ready = False
                game.white_ready = False
                game.game_started = False

                game.save(
                    update_fields=[
                        "board",
                        "turn",
                        "winner",
                        "black",
                        "white",
                        "black_time_remaining",
                        "white_time_remaining",
                        "last_move_time",
                        "rematch_black",
                        "rematch_white",
                        "black_ready",
                        "white_ready",
                        "game_started",
                    ]
                )
                return True  # 리셋 완료
            else:
                # 한쪽만 수락한 경우 플래그만 저장
                game.save(update_fields=["rematch_black", "rematch_white"])
                return False  # 아직 대기 중

    @database_sync_to_async
    def handle_rematch_decline(self, user):
        """리매치 거절 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 종료되지 않았으면 무시
            if not game.winner:
                return

            # 리매치 플래그 리셋
            game.rematch_black = False
            game.rematch_white = False
            game.save(update_fields=["rematch_black", "rematch_white"])

    @database_sync_to_async
    def handle_timeout(self, timeout_player):
        """타임아웃 처리"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            # 게임이 이미 종료된 경우
            if game.winner:
                return None

            # 양쪽 플레이어가 없으면 타임아웃 처리 불가
            if not game.black or not game.white:
                return None

            # 타임아웃된 플레이어 확인 및 승자 결정
            if timeout_player == "black":
                game.winner = "white"
                game.black_time_remaining = 0
            elif timeout_player == "white":
                game.winner = "black"
                game.white_time_remaining = 0
            else:
                return None  # 잘못된 타임아웃 플레이어

            # 전적 기록 생성 및 레이팅 변동 정보 가져오기
            rating_info = record_game_result(game)

            # 최종 상태 저장 (broadcast용)
            final_state = {
                "board": game.board,
                "turn": game.turn,
                "winner": game.winner,
                "size": BOARD_SIZE,
                **game.get_both_player_names(),
                "black_time": game.black_time_remaining,
                "white_time": game.white_time_remaining,
                **rating_info,
            }

            # 게임 저장 (리매치를 위해 삭제하지 않음)
            game.save(
                update_fields=[
                    "winner",
                    "black_time_remaining",
                    "white_time_remaining",
                ]
            )
            return final_state

    async def broadcast_quick_chat(self, event):
        """빠른 채팅 메시지 브로드캐스트"""
        try:
            user = self.scope.get("user")
            sender_id = event.get("sender_id")
            message = event.get("message")
            is_black = event.get("is_black", False)

            # 발신자가 아닌 사람에게만 메시지 전송
            if user and user.is_authenticated and user.id != sender_id:
                await self.send_json(
                    {"type": "quick_chat", "message": message, "is_black": is_black}
                )
        except Exception as e:
            print("[WS][broadcast_quick_chat] ERROR:", repr(e))

    async def notify_rematch_request(self, event):
        """상대방에게 리매치 요청 알림"""
        try:
            user = self.scope.get("user")
            requester_id = event.get("requester_id")

            # 요청자가 아닌 사람에게만 모달 표시
            if user and user.is_authenticated and user.id != requester_id:
                await self.send_json({"type": "rematch_request"})
        except Exception as e:
            print("[WS][notify_rematch_request] ERROR:", repr(e))

    async def notify_rematch_accepted(self, _event):
        """양쪽 모두 리매치 수락 알림"""
        try:
            await self.send_json({"type": "rematch_accepted"})
        except Exception as e:
            print("[WS][notify_rematch_accepted] ERROR:", repr(e))

    async def notify_rematch_declined(self, _event):
        """리매치 거절 알림"""
        try:
            await self.send_json({"type": "rematch_declined"})
        except Exception as e:
            print("[WS][notify_rematch_declined] ERROR:", repr(e))

    async def notify_lobby_status_change(self):
        """로비에 사용자 상태 변경 알림"""
        try:
            await self.channel_layer.group_send(
                "lobby", {"type": "user_status_changed"}
            )
        except Exception as e:
            print("[WS][notify_lobby_status_change] ERROR:", repr(e))

    @database_sync_to_async
    def check_opponent_in_finished_game(self, user):
        """게임 종료 후 상대방이 남아있는지 확인"""
        try:
            game = Game.objects.filter(pk=self.game_id).first()
            if not game or not game.winner:
                return False, None

            # 양쪽 플레이어가 없으면 체크할 필요 없음
            if not game.black or not game.white:
                return False, None

            # 나간 사용자의 상대방 확인
            if user == game.black:
                return True, game.white.id
            elif user == game.white:
                return True, game.black.id

            return False, None
        except Exception:
            return False, None

    async def notify_opponent_left(self, user):
        """게임 종료 후 상대방에게 퇴장 알림"""
        try:
            should_notify, opponent_id = await self.check_opponent_in_finished_game(
                user
            )
            if should_notify and opponent_id:
                # 상대방에게만 알림 전송
                await self.channel_layer.group_send(
                    self.group,
                    {"type": "opponent_left_game", "opponent_id": opponent_id},
                )
        except Exception as e:
            print("[WS][notify_opponent_left] ERROR:", repr(e))

    async def opponent_left_game(self, event):
        """상대방 퇴장 알림 수신"""
        try:
            user = self.scope.get("user")
            opponent_id = event.get("opponent_id")

            # 해당 유저에게만 알림
            if user and user.is_authenticated and user.id == opponent_id:
                await self.send_json({"type": "opponent_left"})
        except Exception as e:
            print("[WS][opponent_left_game] ERROR:", repr(e))

    @database_sync_to_async
    def cleanup_game_on_disconnect(self, user):
        """
        브라우저 뒤로가기 등으로 연결이 끊긴 경우 게임 정리
        - 게임 시작 전: 방장이 나가면 방 삭제, 백플레이어가 나가면 제거
        - 게임 진행 중: 아무것도 안 함 (재접속 가능)
        - 게임 종료 후: 상대방이 나가면 게임 초기화 (대기 방으로 전환)
        - 혼자 연습 모드: 방 삭제
        """
        try:
            with transaction.atomic():
                game = Game.objects.select_for_update().filter(pk=self.game_id).first()

                if not game:
                    return

                # 사용자가 게임 참가자인지 확인
                is_black = user == game.black
                is_white = user == game.white

                if not is_black and not is_white:
                    return  # 관전자는 무시

                # 케이스 1: 게임이 종료된 경우 → 나간 사람 제거 후 게임 초기화
                if game.winner:
                    # 백플레이어가 나간 경우 → 게임 초기화 (대기 방으로 전환)
                    if is_white:
                        print(
                            f"[CLEANUP] 게임 종료 후 백플레이어 나감 - 게임 초기화: game_id={game.id}"
                        )
                        # 백플레이어 제거
                        game.white = None

                        # 게임 초기화
                        game.clear_moves()
                        game.reset_for_new_round()

                        # 준비 상태 및 리매치 플래그 리셋
                        game.black_ready = False
                        game.white_ready = False
                        game.game_started = False
                        game.rematch_black = False
                        game.rematch_white = False

                        game.save(
                            update_fields=[
                                "board",
                                "turn",
                                "winner",
                                "white",
                                "black_time_remaining",
                                "white_time_remaining",
                                "last_move_time",
                                "black_ready",
                                "white_ready",
                                "game_started",
                                "rematch_black",
                                "rematch_white",
                            ]
                        )
                        return

                    # 방장(흑)이 나간 경우 → 방 삭제
                    if is_black:
                        print(
                            f"[CLEANUP] 게임 종료 후 방장 나감 - 방 삭제: game_id={game.id}"
                        )
                        game.delete()
                        return

                # 케이스 2: 게임이 시작되지 않은 경우
                if not game.game_started:
                    # 방장(흑)이 나간 경우
                    if is_black:
                        # 백 플레이어가 있으면 방 삭제 (빈 방은 의미 없음)
                        if game.white:
                            print(
                                f"[CLEANUP] 방장이 게임 시작 전 나감 (백 있음) - 방 삭제: game_id={game.id}"
                            )
                            game.delete()
                            return
                        else:
                            # 백 플레이어가 없으면 방 유지 (방장 혼자 대기 중, 새로고침 대응)
                            print(
                                f"[CLEANUP] 방장이 게임 시작 전 나감 (백 없음) - 방 유지: game_id={game.id}"
                            )
                            return

                    # 백플레이어가 나간 경우 → 백플레이어만 제거
                    if is_white:
                        print(
                            f"[CLEANUP] 백플레이어가 게임 시작 전 나감 - 백플레이어 제거: game_id={game.id}"
                        )
                        game.white = None
                        game.white_ready = False
                        game.save(update_fields=["white", "white_ready"])
                        return

                # 케이스 3: 게임이 시작되었지만 상대가 없는 경우 (연습 모드)
                if game.game_started and not game.white:
                    print(f"[CLEANUP] 혼자 연습 모드 - 방 삭제: game_id={game.id}")
                    game.delete()
                    return

                # 케이스 4: 게임이 진행 중인 경우 → 아무것도 안 함 (재접속 가능)
                print(
                    f"[CLEANUP] 게임 진행 중 - 유지: game_id={game.id}, user={user.username}"
                )

        except Game.DoesNotExist:
            # 게임이 이미 삭제된 경우
            pass
        except Exception as e:
            print(f"[CLEANUP] ERROR: {repr(e)}")


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
            self.username = user.username

            # 그룹 추가
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            # 접속자 목록에 추가
            LobbyConsumer.connected_users[self.channel_name] = {
                "user_id": self.user_id,
                "nickname": self.user_nickname,
                "username": self.username,
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

    async def user_status_changed(self, event):
        """사용자 상태 변경 알림"""
        try:
            users = await self.get_online_users()
            await self.send_json({"type": "users", "users": users})
        except Exception as e:
            print("[LobbyWS][user_status_changed] ERROR:", repr(e))

    async def receive_json(self, content):
        """클라이언트로부터 메시지 수신"""
        try:
            message_type = content.get("type")

            if message_type == "chat_message":
                message = content.get("message", "").strip()
                if message:
                    # 욕설 필터링 적용
                    filtered_message = filter_profanity(message)

                    # 채팅 메시지 브로드캐스트
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "broadcast_chat_message",
                            "sender_id": self.user_id,
                            "sender": self.user_nickname,
                            "message": filtered_message,
                        },
                    )
        except Exception as e:
            print("[LobbyWS][receive_json] ERROR:", repr(e))

    async def broadcast_chat_message(self, event):
        """채팅 메시지 브로드캐스트"""
        try:
            await self.send_json(
                {
                    "type": "chat_message",
                    "sender": event["sender"],
                    "message": event["message"],
                    "is_mine": event["sender_id"] == self.user_id,
                }
            )
        except Exception as e:
            print("[LobbyWS][broadcast_chat_message] ERROR:", repr(e))

    async def get_online_users(self):
        """현재 접속 중인 사용자 목록 반환 (중복 제거) + 게임 상태"""
        # 1. 로비에 연결된 사용자
        unique_users = {}
        for user_info in LobbyConsumer.connected_users.values():
            user_id = user_info["user_id"]
            if user_id not in unique_users:
                unique_users[user_id] = user_info

        # 2. 게임 중인 사용자 추가 (로비에 없는 사람)
        game_users = await self.get_users_in_games()
        for user_info in game_users:
            user_id = user_info["user_id"]
            if user_id not in unique_users:
                unique_users[user_id] = user_info

        # 각 사용자의 게임 상태 확인
        users_with_status = []
        for user_info in unique_users.values():
            status = await self.get_user_game_status(user_info["user_id"])
            users_with_status.append(
                {
                    "user_id": user_info["user_id"],
                    "nickname": user_info["nickname"],
                    "username": user_info.get("username", ""),
                    "status": status,
                }
            )

        return users_with_status

    @database_sync_to_async
    def get_users_in_games(self):
        """진행 중인 게임의 모든 플레이어 조회"""
        # 승자가 없는 모든 게임 (진행 중인 게임)
        games = Game.objects.filter(winner__isnull=True).select_related(
            "black", "white"
        )

        users = []
        seen_user_ids = set()

        for game in games:
            # 흑 플레이어
            if game.black and game.black.id not in seen_user_ids:
                users.append(
                    {
                        "user_id": game.black.id,
                        "nickname": game.black.first_name or game.black.username,
                        "username": game.black.username,
                    }
                )
                seen_user_ids.add(game.black.id)

            # 백 플레이어
            if game.white and game.white.id not in seen_user_ids:
                users.append(
                    {
                        "user_id": game.white.id,
                        "nickname": game.white.first_name or game.white.username,
                        "username": game.white.username,
                    }
                )
                seen_user_ids.add(game.white.id)

        return users

    @database_sync_to_async
    def get_user_game_status(self, user_id):
        """사용자의 게임 상태 반환: online, waiting, playing"""
        # 진행 중인 게임 찾기 (승자가 없는 게임)
        game = Game.objects.filter(
            Q(black_id=user_id) | Q(white_id=user_id), winner__isnull=True
        ).first()

        if not game:
            return "online"  # 게임 없음

        # 양쪽 플레이어가 모두 있으면 "게임중"
        if game.black and game.white:
            return "playing"

        # 한쪽만 있으면 "게임룸 대기중"
        return "waiting"
