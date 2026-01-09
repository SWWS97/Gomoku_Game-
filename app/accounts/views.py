from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileEditForm, SignUpForm
from .models import UserProfile
from app.games.models import GameHistory

User = get_user_model()


def SignUpView(request):
    """회원가입 뷰 (함수형)"""
    form = SignUpForm(request.POST or None)

    if form.is_valid():
        form.save()
        return redirect(settings.LOGIN_URL)

    return render(request, "account/signup.html", {"form": form})


@login_required
def ProfileEditView(request):
    """프로필 수정 뷰 (닉네임 + 비밀번호)"""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, user=request.user)
        if form.is_valid():
            # 비밀번호 변경 여부 체크
            password_changed = bool(form.cleaned_data.get("new_password1"))

            # 프로필 저장
            form.save()

            # 비밀번호 변경 시 세션 유지
            if password_changed:
                update_session_auth_hash(request, request.user)
                messages.success(
                    request, "프로필이 수정되었습니다. 비밀번호가 변경되었습니다."
                )
            else:
                messages.success(request, "프로필이 수정되었습니다.")

            return redirect("games:lobby")
    else:
        form = ProfileEditForm(user=request.user)

    return render(request, "account/profile_edit.html", {"form": form})


def user_profile(request, username):
    """사용자 프로필 페이지"""
    # 사용자 찾기
    user = get_object_or_404(User, username=username)

    # 프로필 가져오기 (없으면 생성)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # GameHistory 가져오기 (최근 20개)
    histories = GameHistory.objects.filter(Q(black=user) | Q(white=user)).order_by(
        "-finished_at"
    )[:20]

    # 전적 통계
    stats = {
        "total_games": profile.total_games,
        "wins": profile.wins,
        "losses": profile.losses,
        "win_rate": profile.win_rate,
    }

    context = {
        "profile_user": user,
        "profile": profile,
        "stats": stats,
        "histories": histories,
    }

    return render(request, "account/profile.html", context)
