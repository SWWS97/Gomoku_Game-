import json
import time
from datetime import timedelta
from functools import wraps

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.core.cache import cache
from django.views.decorators.http import require_POST

from app.accounts.models import UserProfile
from app.accounts.views import get_online_users, AI_GAME_USERS_KEY

from .models import (
    BOARD_SIZE,
    DirectMessage,
    Friend,
    FriendRequest,
    Game,
    GameHistory,
    Move,
    Report,
    Sanction,
)

User = get_user_model()


def notify_lobby_room_change():
    """로비에 게임 방 목록 변경 알림"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)("lobby", {"type": "room_list_changed"})
    except Exception as e:
        print(f"[notify_lobby_room_change] ERROR: {repr(e)}")


@login_required
def lobby(request):
    """게임 로비 - 대기 중인 방 목록 표시"""
    # 온라인 유저 목록 가져오기 (하트비트 캐시 기반)
    online_users = get_online_users()
    online_user_ids = set(online_users.keys())

    # white가 null인 게임 = 대기 중인 방
    all_waiting_games = Game.objects.filter(white__isnull=True).order_by("-created_at")

    # 방장이 오프라인인 방 정리 (본인 방 제외)
    games_to_delete = []
    waiting_games = []
    for game in all_waiting_games:
        # 본인 방은 유지
        if game.black == request.user:
            waiting_games.append(game)
        # 방장이 온라인이면 유지
        elif game.black_id in online_user_ids:
            waiting_games.append(game)
        # 방장이 오프라인이면 삭제 대상
        else:
            games_to_delete.append(game.id)

    # 오프라인 방장의 빈 방 삭제
    if games_to_delete:
        Game.objects.filter(id__in=games_to_delete).delete()

    # 로비 진입 시 본인이 만든 빈 방 정리 (상대 없음, 게임 미시작)
    Game.objects.filter(
        black=request.user,
        white__isnull=True,
        game_started=False,
    ).delete()

    # 현재 사용자가 참여 중인 진행 중인 게임이 있는지 확인
    active_game = Game.objects.filter(
        Q(black=request.user) | Q(white=request.user), winner__isnull=True
    ).first()
    has_active_game = active_game is not None
    active_game_id = active_game.id if active_game else None

    # 현재 사용자의 RP 및 총 게임 수 조회
    try:
        my_profile = UserProfile.objects.get(user=request.user)
        my_rating = my_profile.rating
        my_total_games = my_profile.total_games
    except UserProfile.DoesNotExist:
        my_rating = 1000  # 기본 RP
        my_total_games = 0

    # 모든 프로필 데이터 (랭킹용)
    all_profiles = UserProfile.objects.filter(wins__gt=0).select_related("user").all()

    # 랭킹 데이터 - 레이팅 기준 (최소 5판 이상)
    ranking_by_rating = []
    for profile in all_profiles:
        if profile.total_games >= 5:
            ranking_by_rating.append(
                {
                    "username": profile.user.username,
                    "nickname": profile.user.first_name or profile.user.username,
                    "wins": profile.wins,
                    "losses": profile.losses,
                    "total_games": profile.total_games,
                    "win_rate": profile.win_rate,
                    "rating": profile.rating,
                }
            )

    # 레이팅 내림차순 정렬
    ranking_by_rating.sort(key=lambda x: (-x["rating"], -x["total_games"]))
    ranking_by_rating = ranking_by_rating[:10]
    for idx, item in enumerate(ranking_by_rating, 1):
        item["rank"] = idx

    # 랭킹 데이터 - 승률 기준 (최소 5판 이상)
    ranking_by_winrate = []
    for profile in all_profiles:
        if profile.total_games >= 5:
            ranking_by_winrate.append(
                {
                    "username": profile.user.username,
                    "nickname": profile.user.first_name or profile.user.username,
                    "wins": profile.wins,
                    "losses": profile.losses,
                    "total_games": profile.total_games,
                    "win_rate": profile.win_rate,
                    "rating": profile.rating,
                }
            )

    # 승률 내림차순 정렬 (승률 같으면 총 게임 수 많은 순)
    ranking_by_winrate.sort(key=lambda x: (-x["win_rate"], -x["total_games"]))
    ranking_by_winrate = ranking_by_winrate[:10]
    for idx, item in enumerate(ranking_by_winrate, 1):
        item["rank"] = idx

    # 랭킹 데이터 - 판수 기준
    ranking_by_games = []
    for profile in all_profiles:
        ranking_by_games.append(
            {
                "username": profile.user.username,
                "nickname": profile.user.first_name or profile.user.username,
                "wins": profile.wins,
                "losses": profile.losses,
                "total_games": profile.total_games,
                "win_rate": profile.win_rate,
                "rating": profile.rating,
            }
        )

    # 판수 기준으로 정렬
    ranking_by_games.sort(key=lambda x: (-x["total_games"], -x["wins"]))
    ranking_by_games = ranking_by_games[:10]
    for idx, item in enumerate(ranking_by_games, 1):
        item["rank"] = idx

    return render(
        request,
        "games/lobby.html",
        {
            "waiting_games": waiting_games,
            "has_active_game": has_active_game,
            "active_game_id": active_game_id,
            "ranking_by_rating": ranking_by_rating,
            "ranking_by_winrate": ranking_by_winrate,
            "ranking_by_games": ranking_by_games,
            "my_rating": my_rating,
            "my_total_games": my_total_games,
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
        password = request.POST.get("password", "").strip()
        if not title:
            title = "자신있는 사람 아무나"
        # 비밀번호가 빈 문자열이면 None으로 저장
        g = Game.objects.create(
            black=request.user, title=title, password=password if password else None
        )

        # 로비에 새 게임 방 알림
        notify_lobby_room_change()

        return redirect("games:room", pk=g.pk)

    # GET 요청은 로비로 리다이렉트
    return redirect("games:lobby")


@login_required
def join_game(request, pk):
    """게임 방 참가 (white 플레이어로)"""
    game = get_object_or_404(Game, pk=pk)

    # POST 요청인 경우 - 비밀번호 확인
    if request.method == "POST":
        input_password = request.POST.get("password", "")
        # 비밀번호가 설정된 방인데 비밀번호가 틀리면 403 반환
        if game.password and game.password != input_password:
            return HttpResponseForbidden("비밀번호가 틀렸습니다.")
        # 비밀번호가 맞으면 계속 진행 (아래 코드 실행)

    # GET 요청인 경우 - 비밀번호가 있으면 클라이언트에서 처리됨 (JavaScript)
    # 비밀번호가 없는 방이거나 비밀번호가 맞는 경우

    # 이미 white가 있으면 그냥 방으로 이동
    if game.white is None and game.black != request.user:
        game.white = request.user

        # 백 플레이어가 입장하면 게임 초기화
        game.clear_moves()
        game.reset_for_new_round()
        game.save()

        # WebSocket으로 모든 클라이언트에게 플레이어 입장 알림
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}", {"type": "player_joined"}
        )

        # 로비에 게임 방 목록 변경 알림 (방이 꽉 참)
        notify_lobby_room_change()

    return redirect("games:room", pk=game.pk)


def game_room(request, pk):
    game = get_object_or_404(Game, pk=pk)
    return render(request, "games/room.html", {"game": game, "BOARD_SIZE": BOARD_SIZE})


def ai_game(request):
    """AI 대전 게임 페이지"""
    difficulty = request.GET.get("difficulty", "normal")
    color = request.GET.get("color", "B")

    # 유효성 검사
    if difficulty not in ("easy", "normal", "hard"):
        difficulty = "normal"
    if color not in ("B", "W"):
        color = "B"

    return render(
        request,
        "games/ai_game.html",
        {
            "difficulty": difficulty,
            "player_color": color,
        },
    )


@login_required
@require_POST
def ai_game_status(request):
    """AI 게임 상태 업데이트 (하트비트)"""

    user = request.user
    ai_users = cache.get(AI_GAME_USERS_KEY, {})
    ai_users[str(user.id)] = {
        "user_id": user.id,
        "username": user.username,
        "nickname": user.first_name or user.username,
        "last_seen": time.time(),
    }
    cache.set(AI_GAME_USERS_KEY, ai_users, timeout=300)

    # 로비에 상태 변경 알림
    notify_lobby_status_change()

    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def ai_game_leave(request):
    """AI 게임 종료 알림"""
    user = request.user
    ai_users = cache.get(AI_GAME_USERS_KEY, {})
    if str(user.id) in ai_users:
        del ai_users[str(user.id)]
        cache.set(AI_GAME_USERS_KEY, ai_users, timeout=300)

    # 로비에 상태 변경 알림
    notify_lobby_status_change()

    return JsonResponse({"status": "ok"})


def notify_lobby_status_change():
    """로비에 유저 상태 변경 알림"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "lobby", {"type": "user_status_changed"}
        )
    except Exception as e:
        print(f"[notify_lobby_status_change] ERROR: {repr(e)}")


@login_required
def leave_game(request, pk):
    """게임 나가기"""
    # 게임이 이미 삭제된 경우 로비로 리다이렉트
    try:
        game = Game.objects.get(pk=pk)
    except Game.DoesNotExist:
        messages.info(request, "게임이 이미 종료되었습니다.")
        return redirect("games:lobby")

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
        # 로비에 게임 방 목록 변경 알림
        notify_lobby_room_change()
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
        # 로비에 게임 방 목록 변경 알림 (방이 다시 대기 중으로 전환)
        notify_lobby_room_change()
        return redirect("games:lobby")

    # 참가하지 않은 유저면 그냥 로비로
    return redirect("games:lobby")


@login_required
def game_history(request):
    """사용자의 게임 전적 조회"""
    # 내가 참여한 게임 전적 (흑 또는 백으로 참여)
    all_histories = GameHistory.objects.filter(
        Q(black=request.user) | Q(white=request.user)
    ).order_by("-finished_at")

    # 승/패/전체 통계 계산 (페이지네이션 전에)
    total_games = all_histories.count()
    wins = all_histories.filter(
        Q(winner="black", black=request.user) | Q(winner="white", white=request.user)
    ).count()
    losses = total_games - wins

    # 페이지네이션 (15개씩)
    paginator = Paginator(all_histories, 15)
    page_number = request.GET.get("page", 1)
    histories = paginator.get_page(page_number)

    context = {
        "histories": histories,
        "total_games": total_games,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total_games * 100) if total_games > 0 else 0, 1),
    }

    return render(request, "games/history.html", context)


# ====== 친구 관련 뷰 ======


@login_required
def friends_list(request):
    """친구 목록 페이지"""
    # 양방향 친구 조회
    friends_query = Friend.objects.filter(Q(user=request.user) | Q(friend=request.user))

    # 친구 리스트 구성 (중복 제거)
    friends_set = set()
    for f in friends_query:
        if f.user == request.user:
            friends_set.add(f.friend)
        else:
            friends_set.add(f.user)

    # 각 친구별 안 읽은 메시지 개수 추가
    friends_data = []
    for friend in friends_set:
        unread_count = DirectMessage.objects.filter(
            sender=friend, recipient=request.user, is_read=False
        ).count()
        friends_data.append(
            {
                "user": friend,
                "unread_count": unread_count,
            }
        )

    # 친구 요청 목록
    friend_requests = FriendRequest.objects.filter(to_user=request.user)

    context = {
        "friends": friends_data,
        "friend_requests": friend_requests,
    }

    return render(request, "games/friends.html", context)


@login_required
def send_friend_request(request, user_id):
    """친구 요청 보내기"""
    if request.method != "POST":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "POST 요청만 허용됩니다."}, status=405)
        return redirect("games:friends")

    target_user = get_object_or_404(User, id=user_id)
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.content_type == "application/json"
    )
    target_name = target_user.first_name or target_user.username

    # 자기 자신에게 요청 불가
    if target_user == request.user:
        if is_ajax:
            return JsonResponse(
                {"error": "자기 자신에게 친구 요청을 보낼 수 없습니다."}, status=400
            )
        messages.error(request, "자기 자신에게 친구 요청을 보낼 수 없습니다.")
        return redirect("games:friends")

    # 이미 친구인지 확인
    is_already_friend = Friend.objects.filter(
        Q(user=request.user, friend=target_user)
        | Q(user=target_user, friend=request.user)
    ).exists()

    if is_already_friend:
        if is_ajax:
            return JsonResponse({"error": "이미 친구입니다."}, status=400)
        messages.info(request, "이미 친구입니다.")
        return redirect("games:friends")

    # 이미 요청이 있는지 확인
    existing_request = FriendRequest.objects.filter(
        from_user=request.user, to_user=target_user
    ).exists()

    if existing_request:
        if is_ajax:
            return JsonResponse({"error": "이미 친구 요청을 보냈습니다."}, status=400)
        messages.info(request, "이미 친구 요청을 보냈습니다.")
        return redirect("games:friends")

    # 친구 요청 생성
    FriendRequest.objects.create(from_user=request.user, to_user=target_user)

    if is_ajax:
        return JsonResponse({"message": f"{target_name}님에게 친구 요청을 보냈습니다."})

    messages.success(request, f"{target_name}님에게 친구 요청을 보냈습니다.")
    return redirect("games:friends")


@login_required
def accept_friend_request(request, request_id):
    """친구 요청 수락"""
    if request.method != "POST":
        return redirect("games:friends")

    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.content_type == "application/json"
    )

    friend_request = get_object_or_404(
        FriendRequest, id=request_id, to_user=request.user
    )

    from_name = friend_request.from_user.first_name or friend_request.from_user.username

    # 양방향 친구 관계 생성
    Friend.objects.create(user=request.user, friend=friend_request.from_user)
    Friend.objects.create(user=friend_request.from_user, friend=request.user)

    # 요청 삭제
    friend_request.delete()

    if is_ajax:
        return JsonResponse({"message": f"{from_name}님과 친구가 되었습니다."})

    messages.success(request, f"{from_name}님과 친구가 되었습니다.")
    return redirect("games:friends")


@login_required
def decline_friend_request(request, request_id):
    """친구 요청 거절"""
    if request.method != "POST":
        return redirect("games:friends")

    friend_request = get_object_or_404(
        FriendRequest, id=request_id, to_user=request.user
    )
    friend_request.delete()

    messages.info(request, "친구 요청을 거절했습니다.")
    return redirect("games:friends")


@login_required
def remove_friend(request, user_id):
    """친구 삭제"""
    if request.method != "POST":
        return redirect("games:friends")

    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.content_type == "application/json"
    )

    friend = get_object_or_404(User, id=user_id)
    friend_name = friend.first_name or friend.username

    # 양방향 친구 관계 삭제
    Friend.objects.filter(
        Q(user=request.user, friend=friend) | Q(user=friend, friend=request.user)
    ).delete()

    if is_ajax:
        return JsonResponse(
            {"message": f"{friend_name}님을 친구 목록에서 삭제했습니다."}
        )

    messages.info(request, f"{friend_name}님을 친구 목록에서 삭제했습니다.")
    return redirect("games:friends")


# ====== 메시지 관련 뷰 ======


@login_required
def message_room(request, user_id):
    """특정 친구와의 채팅 페이지"""
    friend = get_object_or_404(User, id=user_id)

    # 친구 관계 확인
    is_friend = Friend.objects.filter(
        Q(user=request.user, friend=friend) | Q(user=friend, friend=request.user)
    ).exists()

    if not is_friend:
        messages.error(request, "친구만 메시지를 보낼 수 있습니다.")
        return redirect("games:friends")

    # 메시지 이력 가져오기 (양방향)
    message_history = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=friend)
        | Q(sender=friend, recipient=request.user)
    ).order_by("created_at")

    # 받은 메시지 읽음 처리
    DirectMessage.objects.filter(
        sender=friend, recipient=request.user, is_read=False
    ).update(is_read=True)

    context = {
        "friend": friend,
        "messages": message_history,
    }

    return render(request, "games/message_room.html", context)


@login_required
def get_unread_message_count(request):
    """읽지 않은 메시지 개수 조회 (AJAX)"""
    unread_count = DirectMessage.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return JsonResponse({"unread_count": unread_count})


@login_required
def search_users(request):
    """사용자 검색 (AJAX)"""
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"users": []})

    # 사용자명 또는 닉네임으로 검색 (본인 제외)
    users = User.objects.filter(
        Q(username__icontains=query) | Q(first_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    # 각 사용자별 친구 상태 확인
    results = []
    for user in users:
        # 이미 친구인지 확인
        is_friend = Friend.objects.filter(
            Q(user=request.user, friend=user) | Q(user=user, friend=request.user)
        ).exists()

        # 이미 친구 요청을 보냈는지 확인
        request_sent = FriendRequest.objects.filter(
            from_user=request.user, to_user=user
        ).exists()

        # 상대방이 나에게 친구 요청을 보냈는지 확인
        request_received = FriendRequest.objects.filter(
            from_user=user, to_user=request.user
        ).exists()

        results.append(
            {
                "id": user.id,
                "username": user.username,
                "display_name": user.first_name or user.username,
                "is_friend": is_friend,
                "request_sent": request_sent,
                "request_received": request_received,
            }
        )

    return JsonResponse({"users": results})


# ──────────────────────────────────────────────────────────────────────
# 신고 API
# ──────────────────────────────────────────────────────────────────────


@login_required
def submit_report(request):
    """신고 접수 API"""
    if request.method != "POST":
        return JsonResponse({"error": "POST만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청입니다."}, status=400)

    reported_user_id = data.get("reported_user_id")
    report_type = data.get("report_type")
    reason = data.get("reason")
    description = data.get("description", "")
    evidence = data.get("evidence", "")

    if not all([reported_user_id, report_type, reason]):
        return JsonResponse({"error": "필수 항목이 누락되었습니다."}, status=400)

    if int(reported_user_id) == request.user.id:
        return JsonResponse({"error": "자기 자신을 신고할 수 없습니다."}, status=400)

    reported_user = get_object_or_404(User, id=reported_user_id)

    # 중복 신고 방지 (같은 대상, 24시간 내)

    recent = Report.objects.filter(
        reporter=request.user,
        reported_user=reported_user,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).exists()
    if recent:
        return JsonResponse(
            {"error": "이미 최근 24시간 내에 해당 유저를 신고했습니다."}, status=400
        )

    Report.objects.create(
        reporter=request.user,
        reported_user=reported_user,
        report_type=report_type,
        reason=reason,
        description=description,
        evidence=evidence,
    )

    return JsonResponse({"success": True, "message": "신고가 접수되었습니다."})


# ──────────────────────────────────────────────────────────────────────
# 관리자 페이지
# ──────────────────────────────────────────────────────────────────────


def staff_required(view_func):
    """is_staff 데코레이터"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("접근 권한이 없습니다.")
        return view_func(request, *args, **kwargs)

    return wrapper


@staff_required
def admin_panel(request):
    """관리자 페이지"""

    pending_count = Report.objects.filter(status="pending").count()
    total_users = User.objects.count()
    today = timezone.now().date()
    today_reports = Report.objects.filter(created_at__date=today).count()

    context = {
        "pending_count": pending_count,
        "total_users": total_users,
        "today_reports": today_reports,
    }
    return render(request, "games/admin_panel.html", context)


@staff_required
def admin_reports_api(request):
    """신고 목록 API"""
    status_filter = request.GET.get("status", "pending")
    page = int(request.GET.get("page", 1))

    reports = Report.objects.select_related("reporter", "reported_user", "reviewed_by")
    if status_filter != "all":
        reports = reports.filter(status=status_filter)

    paginator = Paginator(reports, 20)
    page_obj = paginator.get_page(page)

    results = []
    for r in page_obj:
        results.append(
            {
                "id": r.id,
                "reporter": r.reporter.first_name or r.reporter.username,
                "reported_user": r.reported_user.first_name or r.reported_user.username,
                "reported_user_id": r.reported_user.id,
                "report_type": r.get_report_type_display(),
                "reason": r.get_reason_display(),
                "description": r.description,
                "evidence": r.evidence,
                "status": r.status,
                "status_display": r.get_status_display(),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
                "reviewed_by": (r.reviewed_by.first_name or r.reviewed_by.username)
                if r.reviewed_by
                else None,
            }
        )

    return JsonResponse(
        {
            "reports": results,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
        }
    )


@staff_required
def admin_report_action(request, report_id):
    """신고 처리 API"""
    if request.method != "POST":
        return JsonResponse({"error": "POST만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청입니다."}, status=400)

    report = get_object_or_404(Report, id=report_id)
    action = data.get("action")  # dismiss, warning, chat_ban, suspend, permanent_ban
    duration_days = data.get("duration_days")
    admin_note = data.get("admin_note", "")

    if action == "dismiss":
        report.status = "dismissed"
        report.admin_note = admin_note
        report.reviewed_at = timezone.now()
        report.reviewed_by = request.user
        report.save()
        return JsonResponse({"success": True, "message": "신고를 기각했습니다."})

    # 제재 처리
    report.status = "reviewed"
    report.admin_note = admin_note
    report.reviewed_at = timezone.now()
    report.reviewed_by = request.user
    report.save()

    profile, _ = UserProfile.objects.get_or_create(user=report.reported_user)
    ends_at = None

    if action == "warning":
        Sanction.objects.create(
            user=report.reported_user,
            sanction_type="warning",
            reason=admin_note or report.get_reason_display(),
            issued_by=request.user,
            related_report=report,
        )
        return JsonResponse({"success": True, "message": "경고를 부여했습니다."})

    elif action == "chat_ban":
        days = int(duration_days or 1)
        ends_at = timezone.now() + timedelta(days=days)
        profile.chat_banned_until = ends_at
        profile.save()
        Sanction.objects.create(
            user=report.reported_user,
            sanction_type="chat_ban",
            reason=admin_note or report.get_reason_display(),
            duration_days=days,
            ends_at=ends_at,
            issued_by=request.user,
            related_report=report,
        )
        return JsonResponse(
            {"success": True, "message": f"채팅 금지 {days}일을 부여했습니다."}
        )

    elif action == "suspend":
        days = int(duration_days or 1)
        ends_at = timezone.now() + timedelta(days=days)
        profile.suspended_until = ends_at
        profile.save()
        Sanction.objects.create(
            user=report.reported_user,
            sanction_type="suspend",
            reason=admin_note or report.get_reason_display(),
            duration_days=days,
            ends_at=ends_at,
            issued_by=request.user,
            related_report=report,
        )
        return JsonResponse(
            {"success": True, "message": f"계정 정지 {days}일을 부여했습니다."}
        )

    elif action == "permanent_ban":
        profile.is_permanently_banned = True
        profile.save()
        Sanction.objects.create(
            user=report.reported_user,
            sanction_type="permanent_ban",
            reason=admin_note or report.get_reason_display(),
            issued_by=request.user,
            related_report=report,
        )
        return JsonResponse({"success": True, "message": "영구 정지를 부여했습니다."})

    return JsonResponse({"error": "잘못된 액션입니다."}, status=400)


@staff_required
def admin_users_api(request):
    """유저 검색 API"""

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"users": []})

    users = User.objects.filter(
        Q(username__icontains=query) | Q(first_name__icontains=query)
    )[:20]

    results = []
    for u in users:
        try:
            profile = u.profile
            rating = profile.rating
            total_games = profile.total_games
            chat_banned = bool(
                profile.chat_banned_until and profile.chat_banned_until > timezone.now()
            )
            suspended = bool(
                profile.suspended_until and profile.suspended_until > timezone.now()
            )
            permanently_banned = profile.is_permanently_banned
        except UserProfile.DoesNotExist:
            rating = 1000
            total_games = 0
            chat_banned = False
            suspended = False
            permanently_banned = False

        sanctions = Sanction.objects.filter(user=u).order_by("-starts_at")[:5]
        sanction_list = [
            {
                "type": s.get_sanction_type_display(),
                "reason": s.reason[:50],
                "date": s.starts_at.strftime("%Y-%m-%d"),
                "ends_at": s.ends_at.strftime("%Y-%m-%d %H:%M")
                if s.ends_at
                else "영구",
            }
            for s in sanctions
        ]

        results.append(
            {
                "id": u.id,
                "username": u.username,
                "nickname": u.first_name or u.username,
                "rating": rating,
                "total_games": total_games,
                "is_staff": u.is_staff,
                "chat_banned": chat_banned,
                "suspended": suspended,
                "permanently_banned": permanently_banned,
                "sanctions": sanction_list,
                "report_count": Report.objects.filter(reported_user=u).count(),
            }
        )

    return JsonResponse({"users": results})


@staff_required
def admin_user_sanction(request, user_id):
    """유저 직접 제재 API"""
    if request.method != "POST":
        return JsonResponse({"error": "POST만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청입니다."}, status=400)

    target_user = get_object_or_404(User, id=user_id)
    action = data.get("action")
    duration_days = data.get("duration_days")
    reason = data.get("reason", "관리자 직접 제재")

    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    if action == "chat_ban":
        days = int(duration_days or 1)
        ends_at = timezone.now() + timedelta(days=days)
        profile.chat_banned_until = ends_at
        profile.save()
        Sanction.objects.create(
            user=target_user,
            sanction_type="chat_ban",
            reason=reason,
            duration_days=days,
            ends_at=ends_at,
            issued_by=request.user,
        )
        return JsonResponse({"success": True, "message": f"채팅 금지 {days}일"})

    elif action == "suspend":
        days = int(duration_days or 1)
        ends_at = timezone.now() + timedelta(days=days)
        profile.suspended_until = ends_at
        profile.save()
        Sanction.objects.create(
            user=target_user,
            sanction_type="suspend",
            reason=reason,
            duration_days=days,
            ends_at=ends_at,
            issued_by=request.user,
        )
        return JsonResponse({"success": True, "message": f"계정 정지 {days}일"})

    elif action == "permanent_ban":
        profile.is_permanently_banned = True
        profile.save()
        Sanction.objects.create(
            user=target_user,
            sanction_type="permanent_ban",
            reason=reason,
            issued_by=request.user,
        )
        return JsonResponse({"success": True, "message": "영구 정지"})

    elif action == "unsanction":
        profile.chat_banned_until = None
        profile.suspended_until = None
        profile.is_permanently_banned = False
        profile.save()
        return JsonResponse({"success": True, "message": "제재를 해제했습니다."})

    return JsonResponse({"error": "잘못된 액션입니다."}, status=400)
