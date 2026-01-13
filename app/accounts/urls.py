from django.urls import path

from .views import (
    ProfileEditView,
    SignUpView,
    delete_account,
    privacy_policy,
    terms_of_service,
    user_profile,
)

app_name = "accounts"
urlpatterns = [
    path("signup/", SignUpView, name="signup"),  # 함수형 뷰이므로 as_view() 제거
    path("profile/edit/", ProfileEditView, name="profile_edit"),
    path("profile/<str:username>/", user_profile, name="profile"),
    path("delete/", delete_account, name="delete_account"),  # 계정 삭제
    path("privacy-policy/", privacy_policy, name="privacy_policy"),  # 개인정보처리방침
    path("terms-of-service/", terms_of_service, name="terms_of_service"),  # 서비스 약관
]
