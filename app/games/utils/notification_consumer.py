from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """개인 알림용 WebSocket Consumer

    로비 등에서 실시간 알림을 받기 위한 채널.
    DM, 친구 요청 등의 알림을 수신.
    """

    async def connect(self):
        """WebSocket 연결"""
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # 개인 알림 그룹 (각 사용자별 고유 채널)
        self.notification_group = f"notifications_{self.user.id}"

        # 그룹에 추가
        await self.channel_layer.group_add(self.notification_group, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """WebSocket 연결 해제"""
        if hasattr(self, "notification_group"):
            await self.channel_layer.group_discard(
                self.notification_group, self.channel_name
            )

    async def receive_json(self, content):
        """클라이언트에서 메시지 수신 (현재는 사용하지 않음)"""
        pass

    async def dm_notification(self, event):
        """DM 알림을 클라이언트에 전송"""
        await self.send_json(
            {
                "type": "dm_notification",
                "sender_id": event["sender_id"],
                "sender_name": event["sender_name"],
                "message_preview": event["message_preview"],
            }
        )

    async def friend_request_notification(self, event):
        """친구 요청 알림 (향후 확장용)"""
        await self.send_json(
            {
                "type": "friend_request",
                "from_user": event["from_user"],
            }
        )
