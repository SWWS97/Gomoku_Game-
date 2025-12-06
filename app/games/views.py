from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import BOARD_SIZE, Game, GameHistory


@login_required
def lobby(request):
    """게임 로비 - 대기 중인 방 목록 표시"""
    # white가 null인 게임 = 대기 중인 방
    waiting_games = Game.objects.filter(
        white__isnull=True, winner__isnull=True
    ).order_by("-created_at")
    return render(request, "games/lobby.html", {"waiting_games": waiting_games})


@login_required
def new_game(request):
    """새 게임 방 생성"""
    g = Game.objects.create(black=request.user)
    return redirect("games:room", pk=g.pk)


@login_required
def join_game(request, pk):
    """게임 방 참가 (white 플레이어로)"""
    game = get_object_or_404(Game, pk=pk)

    # 이미 white가 있으면 그냥 방으로 이동
    if game.white is None and game.black != request.user:
        game.white = request.user
        game.save()

    return redirect("games:room", pk=game.pk)


def game_room(request, pk):
    game = get_object_or_404(Game, pk=pk)
    return render(request, "games/room.html", {"game": game, "BOARD_SIZE": BOARD_SIZE})


@login_required
def game_history(request):
    """사용자의 게임 전적 조회"""
    # 내가 참여한 게임 전적 (흑 또는 백으로 참여)
    from django.db.models import Q

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
