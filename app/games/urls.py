from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    path("", views.lobby, name="lobby"),  # 로비
    path("new/", views.new_game, name="new"),  # 새 방 만들기
    path("history/", views.game_history, name="history"),  # 전적 조회
    path("<int:pk>/join/", views.join_game, name="join"),  # 방 참가
    path("<int:pk>/leave/", views.leave_game, name="leave"),  # 방 나가기
    path("<int:pk>/", views.game_room, name="room"),  # 게임 방
    # 친구 관련
    path("friends/", views.friends_list, name="friends"),  # 친구 목록
    path("api/users/search/", views.search_users, name="search_users"),  # 사용자 검색
    path(
        "friends/request/<int:user_id>/",
        views.send_friend_request,
        name="send_friend_request",
    ),  # 친구 요청
    path(
        "friends/accept/<int:request_id>/",
        views.accept_friend_request,
        name="accept_friend_request",
    ),  # 친구 수락
    path(
        "friends/decline/<int:request_id>/",
        views.decline_friend_request,
        name="decline_friend_request",
    ),  # 친구 거절
    path(
        "friends/remove/<int:user_id>/", views.remove_friend, name="remove_friend"
    ),  # 친구 삭제
    # 메시지 관련
    path("messages/<int:user_id>/", views.message_room, name="message_room"),  # 채팅방
    path(
        "api/messages/unread/",
        views.get_unread_message_count,
        name="unread_message_count",
    ),  # 안 읽은 메시지 수
    # 신고
    path("api/report/", views.submit_report, name="submit_report"),
    # 관리자 페이지
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/api/reports/", views.admin_reports_api, name="admin_reports_api"),
    path(
        "admin-panel/api/reports/<int:report_id>/action/",
        views.admin_report_action,
        name="admin_report_action",
    ),
    path("admin-panel/api/users/", views.admin_users_api, name="admin_users_api"),
    path(
        "admin-panel/api/users/<int:user_id>/sanction/",
        views.admin_user_sanction,
        name="admin_user_sanction",
    ),
]
