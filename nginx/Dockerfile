FROM nginx:1.25-alpine

# 기본 설정 삭제
RUN rm /etc/nginx/conf.d/default.conf

# HTTPS 설정 사용 (인증서 발급됨)
COPY nginx-ssl.conf /etc/nginx/conf.d/default.conf

# HTTP 전용 설정 백업
COPY nginx.conf /etc/nginx/conf.d/nginx-http.conf.backup