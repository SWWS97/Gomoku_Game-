import os
import uuid
from datetime import timedelta
from io import BytesIO

import boto3
from botocore.config import Config
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.files.base import ContentFile
from django.core.validators import EmailValidator
from django.utils import timezone

from .models import NicknameChangeLog, UserProfile


def upload_to_oci(file_content: bytes, filename: str, content_type: str) -> str:
    """Oracle Object Storage에 직접 업로드 (put_object 사용)"""
    # Oracle OCI S3 호환 설정
    config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.OCI_ACCESS_KEY,
        aws_secret_access_key=settings.OCI_SECRET_KEY,
        endpoint_url=f"https://{settings.OCI_NAMESPACE}.compat.objectstorage.{settings.OCI_REGION}.oraclecloud.com",
        region_name=settings.OCI_REGION,
        config=config,
    )

    # BytesIO로 감싸서 Content-Length 자동 계산
    file_obj = BytesIO(file_content)

    s3_client.put_object(
        Bucket=settings.OCI_BUCKET_NAME,
        Key=filename,
        Body=file_obj,
        ContentType=content_type,
    )

    return filename


User = get_user_model()


class SignUpForm(UserCreationForm):
    # EmailField 대신 CharField 사용 + EmailValidator로 검증
    email = forms.CharField(
        required=True,  # 필수 (비밀번호 재설정용)
        max_length=254,
        help_text="비밀번호 재설정에 사용됩니다",
        widget=forms.TextInput(attrs={"placeholder": "이메일 주소"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def clean_email(self):
        """이메일 형식 검증"""
        email = self.cleaned_data.get("email", "").strip()

        # 빈 값 체크 (필수)
        if not email:
            raise forms.ValidationError("이메일 주소를 입력하세요.")

        # 이메일 형식 검증
        validator = EmailValidator()
        try:
            validator(email)
        except forms.ValidationError:
            raise forms.ValidationError("올바른 이메일 주소를 입력하세요.")

        # 이메일 중복 체크
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("이미 사용 중인 이메일 주소입니다.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user


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

    def clean_nickname(self):
        """닉네임 중복 체크"""
        nickname = self.cleaned_data.get("nickname", "").strip()

        if not nickname:
            raise forms.ValidationError("닉네임을 입력하세요.")

        # 중복 체크 (first_name 필드 사용)
        if User.objects.filter(first_name=nickname).exists():
            raise forms.ValidationError(
                "이미 사용 중인 닉네임입니다. 다른 닉네임을 입력해주세요."
            )

        return nickname

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


class ProfileEditForm(forms.Form):
    """
    프로필 수정 폼 (프로필 이미지 + 닉네임 + 이메일 + 비밀번호)
    닉네임은 하루에 한번만 변경 가능
    """

    profile_image = forms.ImageField(
        required=False,
        label="프로필 이미지",
        widget=forms.FileInput(attrs={"accept": "image/*"}),
    )

    remove_profile_image = forms.BooleanField(
        required=False,
        label="프로필 이미지 삭제",
    )

    nickname = forms.CharField(
        max_length=30,
        required=False,
        label="닉네임",
        help_text="닉네임을 변경하려면 입력하세요 (하루에 한번만 가능)",
        widget=forms.TextInput(attrs={"placeholder": "새로운 닉네임"}),
    )

    # 이메일 (기존 유저가 이메일을 추가할 수 있도록)
    email = forms.CharField(
        max_length=254,
        required=False,
        label="이메일",
        widget=forms.TextInput(attrs={"placeholder": "이메일 주소"}),
    )

    # 비밀번호 변경 (선택 사항)
    old_password = forms.CharField(
        required=False,
        label="현재 비밀번호",
        widget=forms.PasswordInput(attrs={"placeholder": "현재 비밀번호"}),
    )
    new_password1 = forms.CharField(
        required=False,
        label="새 비밀번호",
        widget=forms.PasswordInput(attrs={"placeholder": "새 비밀번호"}),
    )
    new_password2 = forms.CharField(
        required=False,
        label="새 비밀번호 확인",
        widget=forms.PasswordInput(attrs={"placeholder": "새 비밀번호 확인"}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # 초기값 설정
        if self.user:
            self.fields["nickname"].initial = self.user.first_name
            self.fields["email"].initial = self.user.email

    def clean_email(self):
        """이메일 형식 검증 및 중복 체크"""
        email = self.cleaned_data.get("email", "").strip()

        # 빈 값은 허용 (기존 값 유지)
        if not email:
            return ""

        # 이메일 형식 검증
        validator = EmailValidator()
        try:
            validator(email)
        except forms.ValidationError:
            raise forms.ValidationError("올바른 이메일 주소를 입력하세요.")

        # 이메일 변경 시에만 중복 체크
        if email != self.user.email:
            if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
                raise forms.ValidationError("이미 사용 중인 이메일 주소입니다.")

        return email

    def clean_nickname(self):
        """닉네임 중복 검사 (현재 사용자 제외)"""
        nickname = self.cleaned_data.get("nickname", "").strip()

        # 닉네임을 변경하지 않으면 검사 안함
        if not nickname or nickname == self.user.first_name:
            return nickname

        # 다른 사용자와 중복 체크
        if User.objects.filter(first_name=nickname).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")

        # 24시간 제한 체크
        last_change = (
            NicknameChangeLog.objects.filter(user=self.user)
            .order_by("-changed_at")
            .first()
        )

        if last_change:
            time_since_change = timezone.now() - last_change.changed_at
            if time_since_change < timedelta(days=1):
                hours_left = 24 - int(time_since_change.total_seconds() / 3600)
                raise forms.ValidationError(
                    f"닉네임은 하루에 한번만 변경할 수 있습니다. ({hours_left}시간 후 변경 가능)"
                )

        return nickname

    def clean_profile_image(self):
        """프로필 이미지 검증 (5MB 제한, 이미지 형식만)"""
        image = self.cleaned_data.get("profile_image")
        if image:
            # 파일 크기 제한 (5MB)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("이미지 파일은 5MB 이하만 가능합니다.")

            # 파일 형식 검증
            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if image.content_type not in allowed_types:
                raise forms.ValidationError(
                    "JPG, PNG, GIF, WEBP 형식의 이미지만 업로드 가능합니다."
                )

        return image

    def clean(self):
        """비밀번호 변경 검증"""
        cleaned_data = super().clean()
        old_password = cleaned_data.get("old_password")
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        # 비밀번호 변경하려는 경우
        if any([old_password, new_password1, new_password2]):
            # 모든 필드가 입력되었는지 확인
            if not all([old_password, new_password1, new_password2]):
                raise forms.ValidationError(
                    "비밀번호를 변경하려면 모든 비밀번호 필드를 입력해야 합니다."
                )

            # 현재 비밀번호 확인
            if not self.user.check_password(old_password):
                raise forms.ValidationError("현재 비밀번호가 올바르지 않습니다.")

            # 새 비밀번호 일치 확인
            if new_password1 != new_password2:
                raise forms.ValidationError("새 비밀번호가 일치하지 않습니다.")

            # 비밀번호 최소 길이 체크
            if len(new_password1) < 8:
                raise forms.ValidationError("새 비밀번호는 최소 8자 이상이어야 합니다.")

        return cleaned_data

    def save(self):
        """프로필 수정 저장"""
        nickname = self.cleaned_data.get("nickname", "").strip()
        email = self.cleaned_data.get("email", "").strip()
        new_password1 = self.cleaned_data.get("new_password1")
        profile_image = self.cleaned_data.get("profile_image")
        remove_profile_image = self.cleaned_data.get("remove_profile_image")

        # UserProfile 가져오기 또는 생성
        profile, _ = UserProfile.objects.get_or_create(user=self.user)

        # 프로필 이미지 처리
        if remove_profile_image:
            # 기존 이미지 삭제
            if profile.profile_image:
                profile.profile_image.delete(save=False)
                profile.profile_image = None
                profile.save()
        elif profile_image:
            # 기존 이미지 삭제 후 새 이미지 저장
            if profile.profile_image:
                profile.profile_image.delete(save=False)

            file_content = profile_image.read()
            file_name = profile_image.name
            ext = os.path.splitext(file_name)[1].lower()
            new_filename = f"profiles/{uuid.uuid4().hex}{ext}"

            # Oracle Object Storage 사용 시 직접 업로드 (Content-Length 필수)
            if getattr(settings, "OCI_ACCESS_KEY", ""):
                content_type = profile_image.content_type or "image/jpeg"
                upload_to_oci(file_content, new_filename, content_type)
                profile.profile_image.name = new_filename
                profile.save()
            else:
                # 로컬 개발 환경
                profile.profile_image.save(
                    new_filename, ContentFile(file_content), save=True
                )

        # 닉네임 변경
        if nickname and nickname != self.user.first_name:
            old_nickname = self.user.first_name
            self.user.first_name = nickname
            self.user.save()

            # 변경 이력 저장
            NicknameChangeLog.objects.create(
                user=self.user, old_nickname=old_nickname, new_nickname=nickname
            )

        # 이메일 변경
        if email and email != self.user.email:
            self.user.email = email
            self.user.save()

        # 비밀번호 변경
        if new_password1:
            self.user.set_password(new_password1)
            self.user.save()

        return self.user
