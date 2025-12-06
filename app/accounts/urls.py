from django.urls import path

from .views import SignUpView

app_name = "accounts"
urlpatterns = [
    path("signup/", SignUpView, name="signup"),  # 함수형 뷰이므로 as_view() 제거
]
