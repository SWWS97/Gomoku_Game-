FROM nginx:1.25-alpine

# 기본 설정 삭제
RUN rm /etc/nginx/conf.d/default.conf

# HTTP 전용 설정 복사 (초기)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# HTTPS 설정 템플릿 복사 (인증서 발급 후 사용)
COPY nginx-ssl.conf /etc/nginx/conf.d/nginx-ssl.conf.template