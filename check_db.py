#!/usr/bin/env python
"""현재 데이터베이스 설정 확인 스크립트"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['ENV_FILE'] = 'envs/.env.dev'

django.setup()

from django.conf import settings
from django.db import connection

print("=" * 50)
print("현재 데이터베이스 설정")
print("=" * 50)

db = settings.DATABASES['default']
print(f"엔진:   {db['ENGINE']}")
print(f"DB명:   {db.get('NAME', 'N/A')}")

if 'HOST' in db:
    print(f"호스트: {db['HOST']}")
    print(f"포트:   {db.get('PORT', '5432')}")

    if 'rds.amazonaws.com' in db['HOST']:
        print("\n✅ AWS RDS 사용 중")
    elif db['HOST'] in ['127.0.0.1', 'localhost']:
        print("\n⚠️  로컬 PostgreSQL 사용 중")
else:
    print(f"파일:   {db['NAME']}")
    print("\n📁 SQLite 사용 중")

print("=" * 50)

# 실제 연결 테스트
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\n✅ 데이터베이스 연결 성공!")
        print(f"버전: {version[:50]}...")
except Exception as e:
    print(f"\n❌ 데이터베이스 연결 실패: {e}")