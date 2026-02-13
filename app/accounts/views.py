import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProfileEditForm, SignUpForm
from .models import UserProfile
from app.games.models import Friend, FriendRequest, GameHistory


# 온라인 상태 관련 상수
ONLINE_TIMEOUT = 60  # 60초 내 활동이 있으면 온라인
ONLINE_USERS_KEY = "online_users"  # 캐시 키
AI_GAME_USERS_KEY = "ai_game_users"  # AI 게임 중인 유저 캐시 키

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
    """프로필 수정 뷰 (프로필 이미지 + 닉네임 + 비밀번호)"""
    # 현재 유저의 프로필 가져오기
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, user=request.user)
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

    return render(
        request,
        "account/profile_edit.html",
        {
            "form": form,
            "profile": profile,
            "selected_avatar": profile.default_avatar or "green",
        },
    )


def user_profile(request, username):
    """사용자 프로필 페이지"""
    # 사용자 찾기
    user = get_object_or_404(User, username=username)

    # 프로필 가져오기 (없으면 생성)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # GameHistory 페이지네이션 (페이지당 10개)
    history_list = GameHistory.objects.filter(Q(black=user) | Q(white=user)).order_by(
        "-finished_at"
    )
    paginator = Paginator(history_list, 10)
    page_number = request.GET.get("page", 1)
    histories = paginator.get_page(page_number)

    # 전적 통계
    stats = {
        "total_games": profile.total_games,
        "wins": profile.wins,
        "losses": profile.losses,
        "win_rate": profile.win_rate,
    }

    # 친구 관계 상태 확인
    friend_status = None  # 비로그인 또는 본인
    pending_request = None
    if request.user.is_authenticated and request.user != user:
        if Friend.objects.filter(user=request.user, friend=user).exists():
            friend_status = "friend"
        elif FriendRequest.objects.filter(
            from_user=request.user, to_user=user
        ).exists():
            friend_status = "sent"
        elif FriendRequest.objects.filter(
            from_user=user, to_user=request.user
        ).exists():
            friend_status = "received"
            pending_request = FriendRequest.objects.filter(
                from_user=user, to_user=request.user
            ).first()
        else:
            friend_status = "none"

    context = {
        "profile_user": user,
        "profile": profile,
        "stats": stats,
        "histories": histories,
        "friend_status": friend_status,
        "friend_request_id": (
            pending_request.id if friend_status == "received" else None
        ),
        "is_own_profile": (
            request.user == user if request.user.is_authenticated else False
        ),
    }

    return render(request, "account/profile.html", context)


@login_required
def delete_account(request):
    """계정 삭제 (탈퇴) 뷰"""
    if request.method == "POST":
        # 비밀번호 확인
        password = request.POST.get("password", "")
        user = authenticate(username=request.user.username, password=password)

        if user is None:
            messages.error(request, "비밀번호가 올바르지 않습니다.")
            return redirect("accounts:delete_account")

        # 최종 확인
        confirm = request.POST.get("confirm", "")
        if confirm != "계정삭제":
            messages.error(request, '"계정삭제"를 정확히 입력해주세요.')
            return redirect("accounts:delete_account")

        # 계정 삭제
        # CASCADE 설정으로 인해 관련 데이터가 자동으로 삭제
        # - UserProfile (CASCADE)
        # - NicknameChangeLog (CASCADE)
        # - Friend (CASCADE)
        # - FriendRequest (CASCADE)
        # - DirectMessage (CASCADE)
        # - Move (CASCADE)
        # Game의 black/white는 SET_NULL이므로 전적은 유지
        # GameHistory의 black/white도 SET_NULL이므로 전적 기록은 유지

        username = request.user.username
        request.user.delete()

        # 로그아웃
        logout(request)

        messages.success(request, f"{username}님의 계정이 성공적으로 삭제되었습니다.")
        return redirect("games:lobby")

    return render(request, "account/delete_account.html")


def privacy_policy(request):
    """개인정보처리방침 페이지"""
    return render(request, "account/privacy_policy.html")


def terms_of_service(request):
    """서비스 약관 페이지"""
    return render(request, "account/terms_of_service.html")


# ──────────────────────────────────────────────────────────────────────
# 온라인 상태 관리 (하트비트)
# ──────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def heartbeat(request):
    """
    하트비트 API - 유저 온라인 상태 갱신
    모든 페이지에서 30초마다 호출됨
    """
    user = request.user
    current_time = time.time()

    # 현재 온라인 유저 목록 가져오기
    online_users = cache.get(ONLINE_USERS_KEY, {})

    # 유저 정보 업데이트
    online_users[user.id] = {
        "user_id": user.id,
        "username": user.username,
        "nickname": user.first_name or user.username,
        "last_seen": current_time,
    }

    # 만료된 유저 정리 (60초 이상 활동 없는 유저)
    online_users = {
        uid: info
        for uid, info in online_users.items()
        if current_time - info["last_seen"] < ONLINE_TIMEOUT
    }

    # 캐시 저장 (2분 TTL)
    cache.set(ONLINE_USERS_KEY, online_users, timeout=120)

    return JsonResponse({"status": "ok", "online_count": len(online_users)})


def get_online_users():
    """온라인 유저 목록 반환 (다른 모듈에서 사용)"""
    current_time = time.time()
    online_users = cache.get(ONLINE_USERS_KEY, {})

    # 만료된 유저 필터링
    return {
        uid: info
        for uid, info in online_users.items()
        if current_time - info["last_seen"] < ONLINE_TIMEOUT
    }


def set_user_offline(user_id):
    """유저를 오프라인으로 설정 (로그아웃 시 등)"""
    online_users = cache.get(ONLINE_USERS_KEY, {})
    if user_id in online_users:
        del online_users[user_id]
        cache.set(ONLINE_USERS_KEY, online_users, timeout=120)
