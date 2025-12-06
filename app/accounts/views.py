from django.conf import settings
from django.shortcuts import redirect, render

from .forms import SignUpForm


def SignUpView(request):
    """회원가입 뷰 (함수형)"""
    form = SignUpForm(request.POST or None)

    if form.is_valid():
        form.save()
        return redirect(settings.LOGIN_URL)

    return render(request, "account/signup.html", {"form": form})
