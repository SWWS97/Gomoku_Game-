# app/games/utils/consumers.py
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.db import transaction
from app.games.models import Game, Move, BOARD_SIZE
from app.games.utils.omok import check_five


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """
        웹소켓 연결 시: 그룹에 합류하고 현재 게임 상태를 전송
        (여기서는 DB 락 불필요)
        """
        try:
            self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
            self.group = f"game_{self.game_id}"
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.accept()

            game = await self.get_game()  # 락 없이 조회
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
        """
        클라이언트에서 넘어온 JSON 메시지 처리
        """
        try:
            msg_type = content.get("type")
            if msg_type == "play":
                x = int(content["x"])
                y = int(content["y"])
                user = self.scope.get("user")

                ok, msg = await self.try_play(user, x, y)
                if not ok:
                    await self.send_json({"type": "error", "message": msg})
                    return

                # 모든 참여자에게 최신 상태 브로드캐스트
                await self.channel_layer.group_send(self.group, {"type": "broadcast_state"})
        except Exception as e:
            print("[WS][receive_json] ERROR:", repr(e))
            await self.close(code=4001)

    async def broadcast_state(self, _event):
        """
        group_send 로 호출되는 핸들러.
        """
        try:
            game = await self.get_game()
            state = await self.game_state(game)
            await self.send_json({"type": "state", **state})
        except Exception as e:
            print("[WS][broadcast_state] ERROR:", repr(e))

    # ---------------------
    # DB helpers (sync -> async)
    # ---------------------
    @database_sync_to_async
    def get_game(self):
        # 트랜잭션 밖: 단순 조회
        return Game.objects.get(pk=self.game_id)

    @database_sync_to_async
    def game_state(self, game: Game):
        return {
            "board": game.board,
            "turn": game.turn,
            "winner": game.winner,
            "size": BOARD_SIZE,
        }

    @database_sync_to_async
    def try_play(self, user, x, y):
        """
        착수 처리: 반드시 트랜잭션 안에서 select_for_update 사용
        """
        with transaction.atomic():
            game = Game.objects.select_for_update().get(pk=self.game_id)

            if game.winner:
                return False, "game finished"
            if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
                return False, "out of bounds"
            if game.get_cell(x, y) != ".":
                return False, "occupied"

            expected_user = game.black if game.turn == "black" else game.white
            if expected_user and getattr(user, "is_authenticated", False) and user != expected_user:
                return False, "not your turn"

            stone = game.stone_of_turn()  # "B" or "W"
            game.set_cell(x, y, stone)

            move_order = Move.objects.filter(game=game).count() + 1
            Move.objects.create(
                game=game,
                player=user if getattr(user, "is_authenticated", False) else None,
                x=x,
                y=y,
                order=move_order,
            )

            if check_five(game.board, stone):
                game.winner = game.turn
            else:
                game.swap_turn()

            game.save(update_fields=["board", "turn", "winner"])
            return True, "ok"