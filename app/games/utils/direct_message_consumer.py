from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from app.games.models import DirectMessage, Friend

User = get_user_model()


class DirectMessageConsumer(AsyncJsonWebsocketConsumer):
    """1대1 메시지용 WebSocket Consumer"""

    async def connect(self):
        """WebSocket 연결"""
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # 대화 상대방 ID
        self.friend_id = self.scope["url_route"]["kwargs"]["friend_id"]

        # 친구 관계 확인
        is_friend = await self.check_friendship()
        if not is_friend:
            await self.close()
            return

        # 채널 그룹 이름 생성 (작은 ID가 앞으로)
        user_ids = sorted([self.user.id, int(self.friend_id)])
        self.room_group_name = f"dm_{user_ids[0]}_{user_ids[1]}"

        # 그룹에 추가
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # 연결 시 읽지 않은 메시지 전송
        await self.send_unread_messages()

    async def disconnect(self, close_code):
        """WebSocket 연결 해제"""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive_json(self, content):
        """메시지 수신"""
        message_type = content.get("type")

        if message_type == "send_message":
            await self.handle_send_message(content)
        elif message_type == "mark_read":
            await self.handle_mark_read(content)

    async def handle_send_message(self, content):
        """메시지 전송 처리"""
        message_content = content.get("content", "").strip()

        if not message_content:
            return

        # 욕설 필터링 (기존 quick_chat과 동일한 로직 적용 가능)
        # 일단 기본 구현
        if len(message_content) > 500:
            message_content = message_content[:500]

        # 메시지 DB 저장
        message = await self.save_message(message_content)

        # 그룹에 메시지 브로드캐스트
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "new_message",
                "message": {
                    "id": message.id,
                    "sender_id": self.user.id,
                    "sender_username": self.user.username,
                    "sender_display_name": self.user.first_name or self.user.username,
                    "content": message.content,
                    "is_read": message.is_read,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )

        # 수신자의 알림 채널에도 알림 전송 (로비 등에서 토스트 알림용)
        recipient_notification_group = f"notifications_{self.friend_id}"
        sender_display_name = self.user.first_name or self.user.username
        # 메시지 미리보기 (30자 제한)
        message_preview = (
            message_content[:30] + "..."
            if len(message_content) > 30
            else message_content
        )

        await self.channel_layer.group_send(
            recipient_notification_group,
            {
                "type": "dm_notification",
                "sender_id": self.user.id,
                "sender_name": sender_display_name,
                "message_preview": message_preview,
            },
        )

    async def handle_mark_read(self, content):
        """메시지 읽음 처리"""
        message_ids = content.get("message_ids", [])
        if message_ids:
            await self.mark_messages_as_read(message_ids)

    async def new_message(self, event):
        """새 메시지를 클라이언트에 전송"""
        await self.send_json(
            {
                "type": "new_message",
                "message": event["message"],
            }
        )

    async def message_notification(self, event):
        """메시지 알림을 클라이언트에 전송 (다른 페이지에 있을 때)"""
        await self.send_json(
            {
                "type": "message_notification",
                "notification": event["notification"],
            }
        )

    @database_sync_to_async
    def check_friendship(self):
        """친구 관계 확인"""
        try:
            friend = User.objects.get(id=self.friend_id)
            # 양방향 친구 관계 확인
            return (
                Friend.objects.filter(user=self.user, friend=friend).exists()
                or Friend.objects.filter(user=friend, friend=self.user).exists()
            )
        except User.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        """메시지를 DB에 저장"""
        try:
            recipient = User.objects.get(id=self.friend_id)
            message = DirectMessage.objects.create(
                sender=self.user, recipient=recipient, content=content
            )
            return message
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def send_unread_messages(self):
        """읽지 않은 메시지 전송"""
        try:
            friend = User.objects.get(id=self.friend_id)
            messages = DirectMessage.objects.filter(
                sender=friend, recipient=self.user, is_read=False
            ).order_by("created_at")

            for message in messages:
                # 클라이언트로 전송하는 로직은 별도로 처리
                pass
        except User.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_messages_as_read(self, message_ids):
        """메시지를 읽음으로 표시"""
        DirectMessage.objects.filter(id__in=message_ids, recipient=self.user).update(
            is_read=True
        )
