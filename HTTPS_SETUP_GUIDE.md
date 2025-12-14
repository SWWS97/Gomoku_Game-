# 🚀 도메인 + HTTPS 배포 가이드

## ✅ 완료된 작업
- [x] Nginx Dockerfile 생성
- [x] Nginx 설정 파일 생성 (HTTP + HTTPS)
- [x] docker-compose.yml 수정 (Nginx, Certbot 추가)
- [x] docker-compose.prod.yml 수정
- [x] GitHub Actions 워크플로우 수정 (build.yml, deploy.yml)

## 📋 실행 체크리스트

### Step 1: 도메인 준비
1. **도메인 구매**
   - 가비아, Namecheap, Cloudflare 등에서 구매
   - 예: `gomoku-game.com`

2. **DNS 설정**
   - A 레코드 추가:
     ```
     Type: A
     Name: @
     Value: [EC2 퍼블릭 IP]
     TTL: 300

     Type: A
     Name: www
     Value: [EC2 퍼블릭 IP]
     TTL: 300
     ```

3. **DNS 전파 확인** (5분~1시간 소요)
   ```bash
   # 로컬 터미널에서 확인
   nslookup yourdomain.com
   dig yourdomain.com
   ```

### Step 2: EC2 보안 그룹 설정
AWS EC2 콘솔 → 보안 그룹 → 인바운드 규칙 추가:
```
Type: HTTP
Protocol: TCP
Port: 80
Source: 0.0.0.0/0

Type: HTTPS
Protocol: TCP
Port: 443
Source: 0.0.0.0/0
```

### Step 3: GitHub Secrets 추가
Repository → Settings → Secrets and variables → Actions

**새로 추가할 Secrets:**
```
DOMAIN = yourdomain.com
SSL_EMAIL = your-email@example.com
```

**기존 Secrets 확인:**
- ✅ `DOCKERHUB_USERNAME`
- ✅ `DOCKERHUB_TOKEN`
- ✅ `EC2_HOST`
- ✅ `EC2_USER`
- ✅ `EC2_SSH_KEY`
- ✅ `REPO_URL`
- ✅ `ENV_PROD`

### Step 4: ENV_PROD 환경변수 업데이트
`ENV_PROD` Secret에 다음 항목 추가/수정:

```bash
# 기존 설정들...
DEBUG=False
SECRET_KEY=your-production-secret-key

# HTTPS 관련 추가
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# HTTPS 강제 리다이렉트 (선택)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# 데이터베이스
DB_ENGINE=django.db.backends.postgresql
DB_NAME=gomoku_db
DB_USER=gomoku_user
DB_PASSWORD=your-db-password
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# 네이버 소셜 로그인
NAVER_CLIENT_ID=your-naver-client-id
NAVER_SECRET_KEY=your-naver-secret-key
```

### Step 5: 네이버 개발자 센터 콜백 URL 업데이트
https://developers.naver.com/apps/#/list

애플리케이션 선택 → API 설정:
```
Callback URL: https://yourdomain.com/accounts/naver/login/callback/
```

### Step 6: 코드 푸시 및 배포
```bash
# 로컬에서 실행
git add .
git commit -m "🚀 Add Nginx + HTTPS support"
git push origin main
```

### Step 7: 배포 확인
1. **GitHub Actions 확인**
   - Repository → Actions 탭
   - 3개 워크플로우 순차 실행 확인:
     - ✅ CI - Check Code
     - ✅ CI - Build and Push Docker Images (Web + Nginx)
     - ✅ CD - Deploy to EC2

2. **SSL 인증서 발급 확인**
   - Deploy 워크플로우 로그에서:
     ```
     🔐 SSL 인증서가 없습니다. 초기 발급을 시작합니다...
     📜 Let's Encrypt 인증서 발급 중...
     ✅ SSL 인증서 발급 완료 및 HTTPS 활성화!
     ```

3. **웹사이트 접속**
   ```
   http://yourdomain.com  → https://yourdomain.com 자동 리다이렉트
   https://yourdomain.com → ✅ 정상 작동
   ```

## 🔍 트러블슈팅

### DNS가 안 풀리는 경우
```bash
# 로컬에서 확인
ping yourdomain.com

# EC2에서 확인
curl -I http://yourdomain.com
```

### SSL 인증서 발급 실패
```bash
# EC2 서버 접속
ssh ubuntu@your-ec2-ip

cd /srv/gomoku

# 로그 확인
docker compose logs certbot

# 수동 재시도
docker compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

### Nginx 설정 오류
```bash
# EC2에서 Nginx 설정 테스트
docker compose exec nginx nginx -t

# Nginx 재시작
docker compose restart nginx
```

## 📊 배포 후 플로우

```
코드 푸시 (main)
    ↓
CI - Check Code (린트/테스트)
    ↓
CI - Build Images (Web + Nginx → Docker Hub)
    ↓
CD - Deploy to EC2
    ├─ Git pull
    ├─ 환경변수 설정
    ├─ SSL 인증서 확인/발급 (최초 1회)
    ├─ Docker Compose up
    └─ HTTPS 자동 활성화
    ↓
✅ https://yourdomain.com 접속 가능!
```

## 🎉 완료 확인

1. [ ] `https://yourdomain.com` 접속 시 자물쇠 아이콘 확인
2. [ ] 네이버 소셜 로그인 정상 작동
3. [ ] WebSocket 연결 정상 (게임 플레이 가능)
4. [ ] 정적 파일 로딩 확인 (CSS/JS)

---

## 💡 추가 정보

### SSL 인증서 자동 갱신
- Certbot 컨테이너가 자동으로 12시간마다 인증서 갱신 체크
- Let's Encrypt 인증서는 90일 유효 → 자동 갱신됨

### Nginx 캐싱
- 정적 파일: 30일 캐시
- 미디어 파일: 30일 캐시

### 로그 확인
```bash
# EC2에서
docker compose logs -f web      # Django 로그
docker compose logs -f nginx    # Nginx 로그
docker compose logs -f certbot  # SSL 인증서 로그
```