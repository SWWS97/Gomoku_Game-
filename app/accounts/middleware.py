from django.shortcuts import redirect, render
from django.utils import timezone

from app.accounts.models import UserProfile


class SuspensionCheckMiddleware:
    """계정 정지 체크 미들웨어"""

    EXEMPT_PATHS = [
        "/accounts/login/",
        "/accounts/logout/",
        "/accounts/signup/",
        "/accounts/suspended/",
        "/admin/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_staff:
            path = request.path
            if not any(path.startswith(p) for p in self.EXEMPT_PATHS):
                try:
                    profile = UserProfile.objects.get(user=request.user)
                    if profile.is_permanently_banned:
                        return render(
                            request,
                            "account/suspended.html",
                            {"reason": "영구 정지된 계정입니다.", "permanent": True},
                        )
                    if (
                        profile.suspended_until
                        and profile.suspended_until > timezone.now()
                    ):
                        remaining = profile.suspended_until - timezone.now()
                        return render(
                            request,
                            "account/suspended.html",
                            {
                                "reason": "계정이 일시 정지되었습니다.",
                                "until": profile.suspended_until,
                                "remaining_days": remaining.days,
                                "permanent": False,
                            },
                        )
                except UserProfile.DoesNotExist:
                    pass

        return self.get_response(request)
