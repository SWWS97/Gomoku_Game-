from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import get_user_model
from django.http import JsonResponse

from app.accounts.models import UserProfile
from app.accounts.views import get_online_users

from .models import (
    BOARD_SIZE,
    DirectMessage,
    Friend,
    FriendRequest,
    Game,
    GameHistory,
    Move,
)

User = get_user_model()


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

    # 현재 사용자가 참여 중인 진행 중인 게임이 있는지 확인
    active_game = Game.objects.filter(
        Q(black=request.user) | Q(white=request.user), winner__isnull=True
    ).first()
    has_active_game = active_game is not None
    active_game_id = active_game.id if active_game else None

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
            from django.http import HttpResponseForbidden

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

    return redirect("games:room", pk=game.pk)


def game_room(request, pk):
    game = get_object_or_404(Game, pk=pk)
    return render(request, "games/room.html", {"game": game, "BOARD_SIZE": BOARD_SIZE})


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
        return redirect("games:friends")

    target_user = get_object_or_404(User, id=user_id)

    # 자기 자신에게 요청 불가
    if target_user == request.user:
        messages.error(request, "자기 자신에게 친구 요청을 보낼 수 없습니다.")
        return redirect("games:friends")

    # 이미 친구인지 확인
    is_already_friend = Friend.objects.filter(
        Q(user=request.user, friend=target_user)
        | Q(user=target_user, friend=request.user)
    ).exists()

    if is_already_friend:
        messages.info(request, "이미 친구입니다.")
        return redirect("games:friends")

    # 이미 요청이 있는지 확인
    existing_request = FriendRequest.objects.filter(
        from_user=request.user, to_user=target_user
    ).exists()

    if existing_request:
        messages.info(request, "이미 친구 요청을 보냈습니다.")
        return redirect("games:friends")

    # 친구 요청 생성
    FriendRequest.objects.create(from_user=request.user, to_user=target_user)
    messages.success(
        request,
        f"{target_user.first_name or target_user.username}님에게 친구 요청을 보냈습니다.",
    )

    return redirect("games:friends")


@login_required
def accept_friend_request(request, request_id):
    """친구 요청 수락"""
    if request.method != "POST":
        return redirect("games:friends")

    friend_request = get_object_or_404(
        FriendRequest, id=request_id, to_user=request.user
    )

    # 양방향 친구 관계 생성
    Friend.objects.create(user=request.user, friend=friend_request.from_user)
    Friend.objects.create(user=friend_request.from_user, friend=request.user)

    # 요청 삭제
    friend_request.delete()

    messages.success(
        request,
        f"{friend_request.from_user.first_name or friend_request.from_user.username}님과 친구가 되었습니다.",
    )

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

    friend = get_object_or_404(User, id=user_id)

    # 양방향 친구 관계 삭제
    Friend.objects.filter(
        Q(user=request.user, friend=friend) | Q(user=friend, friend=request.user)
    ).delete()

    messages.info(
        request,
        f"{friend.first_name or friend.username}님을 친구 목록에서 삭제했습니다.",
    )
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
