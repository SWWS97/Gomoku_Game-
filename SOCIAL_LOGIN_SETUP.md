# 소셜 로그인 설정 가이드

네이버 및 카카오 소셜 로그인을 사용하기 위한 설정 가이드입니다.

## 1. 네이버 개발자 센터 설정

### 1.1 애플리케이션 등록
1. [네이버 개발자 센터](https://developers.naver.com/apps/#/register) 접속
2. **Application 등록** 버튼 클릭
3. 애플리케이션 정보 입력:
   - **애플리케이션 이름**: 오목 게임 (원하는 이름)
   - **사용 API**: 네이버 로그인
   - **제공 정보 선택**: 회원이름, 이메일, 프로필 사진 (선택사항)

### 1.2 환경별 Callback URL 설정
- **로컬 개발 환경**: `http://localhost:8000/accounts/naver/login/callback/`
- **프로덕션 환경**: `https://yourdomain.com/accounts/naver/login/callback/`

### 1.3 Client ID 및 Secret 확인
- 등록 완료 후 **Client ID**와 **Client Secret** 확인
- 이 값들을 환경변수에 설정해야 합니다

---

## 2. 카카오 개발자 센터 설정

### 2.1 애플리케이션 등록
1. [카카오 개발자 센터](https://developers.kakao.com/console/app) 접속
2. **애플리케이션 추가하기** 클릭
3. 앱 정보 입력:
   - **앱 이름**: 오목 게임 (원하는 이름)
   - **사업자명**: 개인 또는 회사명

### 2.2 플랫폼 설정
1. 내 애플리케이션 > **앱 설정** > **플랫폼**
2. **Web 플랫폼 등록**:
   - **로컬 개발**: `http://localhost:8000`
   - **프로덕션**: `https://yourdomain.com`

### 2.3 카카오 로그인 활성화
1. **제품 설정** > **카카오 로그인**
2. **카카오 로그인 활성화** ON
3. **Redirect URI 설정**:
   - **로컬 개발**: `http://localhost:8000/accounts/kakao/login/callback/`
   - **프로덕션**: `https://yourdomain.com/accounts/kakao/login/callback/`

### 2.4 동의 항목 설정
1. **제품 설정** > **카카오 로그인** > **동의항목**
2. 필수 동의 항목 설정:
   - **닉네임**: 필수
   - **이메일**: 필수 (이메일 수집 필요 시)

### 2.5 REST API 키 확인
- **앱 설정** > **앱 키**에서 **REST API 키** 확인
- 이 값을 환경변수에 설정해야 합니다

---

## 3. Django 관리자 페이지 설정

소셜 로그인을 활성화하려면 Django 관리자 페이지에서 Social Application을 등록해야 합니다.

### 3.1 관리자 계정 생성 (없는 경우)
```bash
uv run python manage.py createsuperuser
```

### 3.2 관리자 페이지 접속
1. 개발 서버 실행: `make dev` 또는 `uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application`
2. 브라우저에서 `http://localhost:8000/admin/` 접속
3. 생성한 관리자 계정으로 로그인

### 3.3 Sites 설정
1. **Sites** > **Sites** 클릭
2. 기본 Site 편집 (`example.com`):
   - **Domain name**: `localhost:8000` (로컬 개발) 또는 `yourdomain.com` (프로덕션)
   - **Display name**: 오목 게임

### 3.4 네이버 Social Application 등록
1. **Social applications** > **Add social application** 클릭
2. 정보 입력:
   - **Provider**: Naver
   - **Name**: 네이버 로그인 (원하는 이름)
   - **Client id**: 네이버 개발자 센터에서 발급받은 Client ID
   - **Secret key**: 네이버 개발자 센터에서 발급받은 Client Secret
   - **Sites**: `localhost:8000` (또는 설정한 Site) 선택하여 **Chosen sites**로 이동
3. **Save** 클릭

### 3.5 카카오 Social Application 등록
1. **Social applications** > **Add social application** 클릭
2. 정보 입력:
   - **Provider**: Kakao
   - **Name**: 카카오 로그인 (원하는 이름)
   - **Client id**: 카카오 개발자 센터에서 발급받은 REST API 키
   - **Secret key**: (비워둠 - 카카오는 Secret Key 불필요)
   - **Sites**: `localhost:8000` (또는 설정한 Site) 선택하여 **Chosen sites**로 이동
3. **Save** 클릭

---

## 4. 환경 변수 설정 (선택사항)

환경 변수로 소셜 로그인 키를 관리하려면 `.env` 파일에 추가할 수 있습니다:

```bash
# envs/.env.dev
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

**참고**: django-allauth는 기본적으로 **Django Admin에서 설정한 값**을 사용하므로, 환경 변수는 선택사항입니다.

---

## 5. 테스트

### 5.1 로컬 개발 서버 실행
```bash
make dev
```
또는
```bash
uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### 5.2 로그인 페이지 접속
1. `http://localhost:8000/accounts/login/` 접속
2. **네이버로 로그인** 또는 **카카오로 로그인** 버튼 클릭
3. 해당 플랫폼 로그인 페이지로 리다이렉트
4. 로그인 후 애플리케이션으로 다시 돌아오는지 확인

---

## 6. 프로덕션 배포 시 체크리스트

- [ ] 네이버 개발자 센터에 프로덕션 Callback URL 추가 (`https://yourdomain.com/accounts/naver/login/callback/`)
- [ ] 카카오 개발자 센터에 프로덕션 플랫폼 및 Redirect URI 추가 (`https://yourdomain.com/accounts/kakao/login/callback/`)
- [ ] Django Admin에서 Sites 도메인을 프로덕션 도메인으로 변경
- [ ] Django Admin에서 Social Applications의 Sites 설정 확인
- [ ] HTTPS 설정 확인 (소셜 로그인은 HTTPS 필수)

---

## 7. 문제 해결

### 로그인 버튼 클릭 시 404 에러
- Django Admin에서 Social Application이 올바르게 등록되었는지 확인
- Sites 설정이 현재 도메인과 일치하는지 확인

### Callback URL 오류
- 네이버/카카오 개발자 센터에 등록한 Callback URL이 정확한지 확인
- 프로토콜(`http://` vs `https://`)과 포트 번호 확인

### 로그인 후 에러 발생
- `settings.py`의 `SITE_ID = 1` 설정 확인
- Django Admin에서 Sites의 ID가 1인지 확인 (`/admin/sites/site/`)

### 이메일 중복 오류
- `ACCOUNT_EMAIL_VERIFICATION = "optional"` 설정 확인
- 기존 사용자와 이메일이 중복되지 않는지 확인

---

## 참고 문서

- [django-allauth 공식 문서](https://docs.allauth.org/)
- [네이버 로그인 API 가이드](https://developers.naver.com/docs/login/api/)
- [카카오 로그인 API 가이드](https://developers.kakao.com/docs/latest/ko/kakaologin/common)
