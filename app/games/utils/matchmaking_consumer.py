"""LOL 스타일 Rating 기반 매칭 WebSocket 컨슈머"""

import asyncio
import random

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db.models import Q

from app.accounts.models import INITIAL_RATING, UserProfile
from app.games.matchmaking import (
    ACCEPT_TIMEOUT,
    MatchStatus,
    get_current_range,
    matchmaking_service,
)
from app.games.models import Game

User = get_user_model()

class MatchmakingConsumer(AsyncJsonWebsocketConsumer):
    """매칭 WebSocket 컨슈머"""

    # 유저별 채널 매핑 (브로드캐스트용)
    user_channels: dict[int, str] = {}

    async def connect(self):
        """WebSocket 연결"""
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4003)
            return

        self.user = user
        self.user_id = user.id
        self.in_queue = False
        self.queue_task = None

        # 채널 매핑
        MatchmakingConsumer.user_channels[self.user_id] = self.channel_name

        await self.accept()

    async def disconnect(self, code):
        """WebSocket 연결 해제"""
        # 큐 업데이트 태스크 취소
        if self.queue_task:
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass

        # 매칭 서비스 정리
        matchmaking_service.cleanup_user(self.user_id)

        # 채널 매핑 제거
        MatchmakingConsumer.user_channels.pop(self.user_id, None)

    async def receive_json(self, content):
        """메시지 수신 처리"""
        msg_type = content.get("type")

        if msg_type == "join_queue":
            await self.handle_join_queue()
        elif msg_type == "leave_queue":
            await self.handle_leave_queue()
        elif msg_type == "accept_match":
            match_id = content.get("match_id")
            await self.handle_accept_match(match_id)
        elif msg_type == "decline_match":
            match_id = content.get("match_id")
            await self.handle_decline_match(match_id)

    async def handle_join_queue(self):
        """큐 진입 처리"""
        # 이미 진행 중인 게임이 있는지 확인
        has_active = await self.check_active_game()
        if has_active:
            await self.send_json({
                "type": "error",
                "message": "진행 중인 게임이 있습니다.",
            })
            return

        # Rating 조회
        rating = await self.get_user_rating()
        nickname = self.user.first_name or self.user.username

        # 큐에 추가
        success = matchmaking_service.add_to_queue(
            user_id=self.user_id,
            rating=rating,
            channel_name=self.channel_name,
            nickname=nickname,
            username=self.user.username,
        )

        if not success:
            await self.send_json({
                "type": "error",
                "message": "이미 매칭 중입니다.",
            })
            return

        self.in_queue = True

        # 큐 진입 확인
        await self.send_json({
            "type": "queue_joined",
            "rating": rating,
            "queue_size": matchmaking_service.get_queue_size(),
        })

        # 주기적 업데이트 및 매칭 체크 시작
        self.queue_task = asyncio.create_task(self.queue_update_loop())

    async def handle_leave_queue(self):
        """큐 이탈 처리"""
        if self.queue_task:
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass
            self.queue_task = None

        matchmaking_service.remove_from_queue(self.user_id)
        self.in_queue = False

        await self.send_json({"type": "queue_left"})

    async def queue_update_loop(self):
        """큐 업데이트 루프 (매초 실행)"""
        try:
            while self.in_queue:
                # 매칭 상대 찾기
                opponent = matchmaking_service.find_match(self.user_id)

                if opponent:
                    # 매칭 성공!
                    my_entry = matchmaking_service.get_queue_entry(self.user_id)
                    if my_entry:
                        await self.create_match(my_entry, opponent)
                        return

                # 큐 상태 업데이트 전송
                seconds = matchmaking_service.get_seconds_in_queue(self.user_id)
                current_range = get_current_range(seconds)

                await self.send_json({
                    "type": "queue_update",
                    "elapsed_seconds": seconds,
                    "current_range": current_range,
                    "queue_size": matchmaking_service.get_queue_size(),
                })

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass

    async def create_match(self, player1, player2):
        """매칭 생성 및 알림"""
        match_id = matchmaking_service.create_pending_match(player1, player2)
        self.in_queue = False

        # 양쪽에게 매칭 성공 알림
        await self.notify_match_found(match_id, player1, player2)

    async def notify_match_found(self, match_id, player1, player2):
        """매칭 성공 알림 전송"""
        # Player1에게 전송
        p1_channel = MatchmakingConsumer.user_channels.get(player1.user_id)
        if p1_channel:
            await self.channel_layer.send(p1_channel, {
                "type": "send_match_found",
                "match_id": match_id,
                "opponent_nickname": player2.nickname,
                "opponent_rating": player2.rating,
                "accept_timeout": ACCEPT_TIMEOUT,
            })

        # Player2에게 전송
        p2_channel = MatchmakingConsumer.user_channels.get(player2.user_id)
        if p2_channel:
            await self.channel_layer.send(p2_channel, {
                "type": "send_match_found",
                "match_id": match_id,
                "opponent_nickname": player1.nickname,
                "opponent_rating": player1.rating,
                "accept_timeout": ACCEPT_TIMEOUT,
            })

    async def send_match_found(self, event):
        """매칭 성공 메시지 전송 핸들러"""
        await self.send_json({
            "type": "match_found",
            "match_id": event["match_id"],
            "opponent": {
                "nickname": event["opponent_nickname"],
                "rating": event["opponent_rating"],
            },
            "accept_timeout": event["accept_timeout"],
        })

    async def handle_accept_match(self, match_id: str):
        """매칭 수락 처리"""
        if not match_id:
            return

        status = matchmaking_service.accept_match(match_id, self.user_id)

        if status == MatchStatus.CONFIRMED:
            # 양쪽 수락 완료 - 게임 생성
            match = matchmaking_service.confirm_and_cleanup(match_id)
            if match:
                game = await self.create_game(match.player1, match.player2)

                # 양쪽에게 게임 시작 알림
                await self.notify_match_confirmed(
                    match.player1.user_id,
                    match.player2.user_id,
                    game.pk,
                )

        elif status == MatchStatus.WAITING:
            # 상대방 수락 대기
            await self.send_json({
                "type": "match_status",
                "match_id": match_id,
                "status": "waiting",
            })

        elif status == MatchStatus.TIMEOUT:
            await self.send_json({
                "type": "match_timeout",
                "message": "수락 시간이 초과되었습니다.",
            })

    async def handle_decline_match(self, match_id: str):
        """매칭 거절 처리"""
        if not match_id:
            return

        status, other_player = matchmaking_service.decline_match(match_id, self.user_id)

        # 본인에게 거절 확인
        await self.send_json({
            "type": "match_declined",
            "reason": "self_declined",
        })

        # 상대방에게 알림 + 다시 큐에 넣기
        if other_player:
            # 상대방을 다시 큐에 넣기
            matchmaking_service.add_to_queue(
                user_id=other_player.user_id,
                rating=other_player.rating,
                channel_name=other_player.channel_name,
                nickname=other_player.nickname,
                username=other_player.username,
            )

            other_channel = MatchmakingConsumer.user_channels.get(other_player.user_id)
            if other_channel:
                await self.channel_layer.send(other_channel, {
                    "type": "send_match_declined",
                    "reason": "opponent_declined",
                })

    async def send_match_declined(self, event):
        """매칭 거절 메시지 전송 핸들러 - 다시 큐 루프 시작"""
        await self.send_json({
            "type": "match_declined",
            "reason": event["reason"],
        })

        # 다시 큐 업데이트 루프 시작 (상대방이 거절한 경우)
        # 이미 큐에 다시 등록되어 있음
        if matchmaking_service.get_queue_entry(self.user_id):
            self.in_queue = True
            if self.queue_task:
                self.queue_task.cancel()
            self.queue_task = asyncio.create_task(self.queue_update_loop())

    async def notify_match_confirmed(self, player1_id: int, player2_id: int, game_id: int):
        """매칭 확정 알림"""
        for player_id in [player1_id, player2_id]:
            channel = MatchmakingConsumer.user_channels.get(player_id)
            if channel:
                await self.channel_layer.send(channel, {
                    "type": "send_match_confirmed",
                    "game_id": game_id,
                })

    async def send_match_confirmed(self, event):
        """매칭 확정 메시지 전송 핸들러"""
        await self.send_json({
            "type": "match_confirmed",
            "game_id": event["game_id"],
        })

    @database_sync_to_async
    def get_user_rating(self) -> int:
        """유저 Rating 조회"""
        try:
            profile = UserProfile.objects.get(user=self.user)
            return profile.rating
        except UserProfile.DoesNotExist:
            return INITIAL_RATING

    @database_sync_to_async
    def check_active_game(self) -> bool:
        """진행 중인 게임 확인"""
        return Game.objects.filter(
            Q(black=self.user) | Q(white=self.user),
            winner__isnull=True,
        ).exists()

    @database_sync_to_async
    def create_game(self, player1, player2) -> Game:
        """매칭된 게임 생성"""
        # 흑/백 랜덤 배정
        players = [player1, player2]
        random.shuffle(players)
        black_player, white_player = players

        black_user = User.objects.get(id=black_player.user_id)
        white_user = User.objects.get(id=white_player.user_id)

        game = Game.objects.create(
            title="랭크 매칭",
            black=black_user,
            white=white_user,
            black_ready=True,
            white_ready=True,
        )

        return game