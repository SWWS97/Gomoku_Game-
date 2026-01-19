import uuid

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    소셜 로그인 시 username을 자동 생성
    """

    def populate_user(self, request, sociallogin, data):
        """
        User 객체 생성 시 username을 자동 생성
        """
        user = super().populate_user(request, sociallogin, data)

        # username 자동 생성
        email = data.get("email")
        if email:
            base_username = email.split("@")[0]
            # 중복 방지를 위해 UUID 추가
            username = f"{base_username}_{uuid.uuid4().hex[:8]}"
        else:
            username = f"user_{uuid.uuid4().hex[:12]}"

        user.username = username
        return user

    def add_message(
        self,
        request,
        level,
        message_template,
        message_context=None,
        extra_tags="",
    ):
        """
        메시지 추가 시 username 대신 닉네임 표시
        로그인 성공 메시지는 표시하지 않음
        """
        # 로그인 성공 메시지는 무시 (불필요)
        if "로그인" in message_template or "logged in" in message_template.lower():
            return

        # 원본 메시지 생성
        message_context = message_context or {}

        # user가 있고 first_name이 있으면 닉네임으로 대체
        if "user" in message_context:
            user = message_context["user"]
            if hasattr(user, "first_name") and user.first_name:
                # username을 닉네임으로 덮어씀
                message_context["user_display"] = user.first_name
            else:
                message_context["user_display"] = user.username

            # 메시지 템플릿에서 {user}를 {user_display}로 대체
            if "{user}" in message_template:
                message_template = message_template.replace("{user}", "{user_display}")

        # 부모 메서드 호출
        super().add_message(
            request, level, message_template, message_context, extra_tags
        )


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    일반 로그인/회원가입 메시지도 닉네임 표시
    """

    def add_message(
        self,
        request,
        level,
        message_template,
        message_context=None,
        extra_tags="",
    ):
        """
        메시지 추가 시 username 대신 닉네임 표시
        로그인 성공 메시지는 표시하지 않음
        """
        # 로그인 성공 메시지는 무시 (불필요)
        if "로그인" in message_template or "logged in" in message_template.lower():
            return

        message_context = message_context or {}

        # user가 있고 first_name이 있으면 닉네임으로 대체
        if "user" in message_context:
            user = message_context["user"]
            if hasattr(user, "first_name") and user.first_name:
                message_context["user_display"] = user.first_name
            else:
                message_context["user_display"] = user.username

            # 메시지 템플릿에서 {user}를 {user_display}로 대체
            if "{user}" in message_template:
                message_template = message_template.replace("{user}", "{user_display}")

        super().add_message(
            request, level, message_template, message_context, extra_tags
        )
