from django.urls import path

from .views import ProfileEditView, SignUpView, delete_account, user_profile

app_name = "accounts"
urlpatterns = [
    path("signup/", SignUpView, name="signup"),  # 함수형 뷰이므로 as_view() 제거
    path("profile/edit/", ProfileEditView, name="profile_edit"),
    path("profile/<str:username>/", user_profile, name="profile"),
    path("delete/", delete_account, name="delete_account"),  # 계정 삭제
]
