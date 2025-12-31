from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from app.accounts.models import UserProfile

from .models import BOARD_SIZE, Game, GameHistory, Move


@login_required
def lobby(request):
    """게임 로비 - 대기 중인 방 목록 표시"""
    # white가 null인 게임 = 대기 중인 방
    waiting_games = Game.objects.filter(
        white__isnull=True, winner__isnull=True
    ).order_by("-created_at")

    # 현재 사용자가 참여 중인 진행 중인 게임이 있는지 확인
    has_active_game = Game.objects.filter(
        Q(black=request.user) | Q(white=request.user), winner__isnull=True
    ).exists()

    # 랭킹 데이터 - 승률 기준 (최소 5판 이상)
    ranking_by_winrate_raw = (
        UserProfile.objects.filter(wins__gt=0)
        .select_related("user")
        .order_by("-wins")[:10]
    )

    # 승률 순위 데이터 포맷팅
    ranking_by_winrate = []
    for idx, profile in enumerate(ranking_by_winrate_raw, 1):
        # 최소 5판 이상인 경우만 포함
        if profile.total_games >= 5:
            ranking_by_winrate.append(
                {
                    "rank": idx,
                    "nickname": profile.user.first_name or profile.user.username,
                    "wins": profile.wins,
                    "losses": profile.losses,
                    "total_games": profile.total_games,
                    "win_rate": profile.win_rate,
                }
            )

    # 랭킹 데이터 - 판수 기준
    ranking_by_games_raw = (
        UserProfile.objects.filter(wins__gt=0)
        .select_related("user")
        .order_by("-wins", "-losses")[:10]
    )

    # 판수 순위 데이터 포맷팅
    ranking_by_games = []
    for idx, profile in enumerate(ranking_by_games_raw, 1):
        ranking_by_games.append(
            {
                "rank": idx,
                "nickname": profile.user.first_name or profile.user.username,
                "wins": profile.wins,
                "losses": profile.losses,
                "total_games": profile.total_games,
                "win_rate": profile.win_rate,
            }
        )

    # 실제 판수 기준으로 정렬
    ranking_by_games.sort(key=lambda x: (-x["total_games"], -x["wins"]))
    # 순위 재조정
    for idx, item in enumerate(ranking_by_games, 1):
        item["rank"] = idx

    return render(
        request,
        "games/lobby.html",
        {
            "waiting_games": waiting_games,
            "has_active_game": has_active_game,
            "ranking_by_winrate": ranking_by_winrate,
            "ranking_by_games": ranking_by_games,
        },
    )


@login_required
def new_game(request):
    """새 게임 방 생성 (POST만 허용)"""
    # 현재 사용자가 참여 중인 진행 중인 게임이 있는지 확인
    has_active_game = Game.objects.filter(
        Q(black=request.user) | Q(white=request.user), winner__isnull=True
    ).exists()

    if has_active_game:
        messages.error(
            request,
            "진행 중인 게임이 있습니다. 게임을 종료한 후 새 게임을 만들 수 있습니다.",
        )
        return redirect("games:lobby")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        if not title:
            title = "자신있는 사람 아무나"
        g = Game.objects.create(black=request.user, title=title)
        return redirect("games:room", pk=g.pk)

    # GET 요청은 로비로 리다이렉트
    return redirect("games:lobby")


@login_required
def join_game(request, pk):
    """게임 방 참가 (white 플레이어로)"""
    game = get_object_or_404(Game, pk=pk)

    # 이미 white가 있으면 그냥 방으로 이동
    if game.white is None and game.black != request.user:
        game.white = request.user

        # 백 플레이어가 입장하면 게임 초기화
        # 1. 기존 수(Move) 모두 삭제
        Move.objects.filter(game=game).delete()

        # 2. 게임판 초기화
        game.board = "." * (BOARD_SIZE * BOARD_SIZE)
        game.turn = "black"  # 턴도 흑으로 리셋
        game.save()

        # WebSocket으로 모든 클라이언트에게 플레이어 입장 알림
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}", {"type": "player_joined"}
        )

    return redirect("games:room", pk=game.pk)


def game_room(request, pk):
    game = get_object_or_404(Game, pk=pk)
    return render(request, "games/room.html", {"game": game, "BOARD_SIZE": BOARD_SIZE})


@login_required
def leave_game(request, pk):
    """게임 나가기"""
    game = get_object_or_404(Game, pk=pk)

    # 게임이 이미 종료되었으면 로비로
    if game.winner:
        return redirect("games:lobby")

    # 게임이 시작되었는지 확인 (Move가 하나라도 있으면 시작됨)
    has_moves = Move.objects.filter(game=game).exists()

    # 양쪽 플레이어가 모두 있고 게임이 시작된 후에는 나가기 불가
    if has_moves and game.black and game.white:
        messages.error(
            request, "게임이 이미 시작되어 나갈 수 없습니다. 항복을 사용하세요."
        )
        return redirect("games:room", pk=pk)

    # 흑돌 플레이어(방 생성자)가 나가면 게임 삭제
    if request.user == game.black:
        game.delete()
        # WebSocket으로 백돌 플레이어에게 알림 (게임 삭제됨)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(f"game_{pk}", {"type": "game_deleted"})
        messages.info(request, "게임방을 나갔습니다.")
        return redirect("games:lobby")

    # 백돌 플레이어가 나가면 백돌만 제거
    if request.user == game.white:
        game.white = None
        game.save()
        # WebSocket으로 흑돌 플레이어에게 상태 업데이트
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{pk}", {"type": "broadcast_state"}
        )
        messages.info(request, "게임방을 나갔습니다.")
        return redirect("games:lobby")

    # 참가하지 않은 유저면 그냥 로비로
    return redirect("games:lobby")


@login_required
def game_history(request):
    """사용자의 게임 전적 조회"""
    # 내가 참여한 게임 전적 (흑 또는 백으로 참여)
    histories = GameHistory.objects.filter(
        Q(black=request.user) | Q(white=request.user)
    ).order_by("-finished_at")

    # 승/패/전체 통계 계산
    total_games = histories.count()
    wins = histories.filter(
        Q(winner="black", black=request.user) | Q(winner="white", white=request.user)
    ).count()
    losses = total_games - wins

    context = {
        "histories": histories,
        "total_games": total_games,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total_games * 100) if total_games > 0 else 0, 1),
    }

    return render(request, "games/history.html", context)
