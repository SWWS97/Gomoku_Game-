from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render

from .models import BOARD_SIZE, Game


@login_required
def new_game(request):
    g = Game.objects.create(black=request.user)
    return redirect("games:room", pk=g.pk)


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

    return render(request, "registration/signup.html", context)
