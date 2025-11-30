from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render

from .models import BOARD_SIZE, Game


@login_required
def lobby(request):
    """게임 로비 - 대기 중인 방 목록 표시"""
    # white가 null인 게임 = 대기 중인 방
    waiting_games = Game.objects.filter(white__isnull=True, winner__isnull=True).order_by('-created_at')
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


def sign_up(request):
    form = UserCreationForm(
        request.POST or None
    )  # 입력된 값이 없으면 빈 양식을 폼에 저장

    if form.is_valid():  # form이 valid 하지 않으면 error(dict 형태: add_error 메서드 동작) 메시지를 폼에 저장
        form.save()
        return redirect(settings.LOGIN_URL)

    context = {
        "form": form,
    }

    return render(request, "account/signup.html", context)
