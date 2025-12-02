from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False, help_text="선택 (비밀번호 찾기 등에 사용)")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class SocialSignupForm(forms.Form):
    """
    소셜 로그인 회원가입 시 닉네임만 입력받는 폼
    username은 adapter에서 자동 생성됨
    """

    nickname = forms.CharField(
        max_length=30,
        required=True,
        label="닉네임",
        help_text="게임에서 사용할 닉네임을 입력하세요",
        widget=forms.TextInput(attrs={"placeholder": "닉네임을 입력하세요"}),
    )

    def __init__(self, *args, **kwargs):
        """allauth가 전달하는 sociallogin 인자를 받아서 처리"""
        self.sociallogin = kwargs.pop("sociallogin", None)
        super().__init__(*args, **kwargs)

    def try_save(self, request):
        """
        allauth가 요구하는 try_save 메서드
        (user, response) 튜플을 반환
        """

        # sociallogin 객체에서 user를 가져옴
        user = self.sociallogin.user

        # username 설정 (adapter에서 이미 설정되었지만 확인)
        if not user.username:
            import uuid

            email = user.email
            if email:
                base_username = email.split("@")[0]
                user.username = f"{base_username}_{uuid.uuid4().hex[:8]}"
            else:
                user.username = f"user_{uuid.uuid4().hex[:12]}"

        # 닉네임 설정
        user.first_name = self.cleaned_data["nickname"]

        # User 저장
        user.save()

        # sociallogin 완료 처리
        self.sociallogin.save(request, connect=True)

        return user, None
