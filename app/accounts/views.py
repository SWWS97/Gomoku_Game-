from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileEditForm, SignUpForm


def SignUpView(request):
    """회원가입 뷰 (함수형)"""
    form = SignUpForm(request.POST or None)

    if form.is_valid():
        form.save()
        return redirect(settings.LOGIN_URL)

    return render(request, "account/signup.html", {"form": form})


@login_required
def ProfileEditView(request):
    """프로필 수정 뷰 (닉네임 + 비밀번호)"""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, user=request.user)
        if form.is_valid():
            # 비밀번호 변경 여부 체크
            password_changed = bool(form.cleaned_data.get("new_password1"))

            # 프로필 저장
            form.save()

            # 비밀번호 변경 시 세션 유지
            if password_changed:
                update_session_auth_hash(request, request.user)
                messages.success(
                    request, "프로필이 수정되었습니다. 비밀번호가 변경되었습니다."
                )
            else:
                messages.success(request, "프로필이 수정되었습니다.")

            return redirect("games:lobby")
    else:
        form = ProfileEditForm(user=request.user)

    return render(request, "account/profile_edit.html", {"form": form})
