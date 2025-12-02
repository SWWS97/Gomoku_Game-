#!/usr/bin/env python
"""RDS 데이터 확인 스크립트"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from app.games.models import Game, Move

User = get_user_model()

print("=" * 60)
print("📊 RDS 데이터 현황")
print("=" * 60)

# 사용자 현황
users = User.objects.all()
print(f"\n👥 전체 사용자: {users.count()}명")
if users.exists():
    print("\n최근 가입 유저:")
    for user in users.order_by('-date_joined')[:5]:
        nickname = user.first_name or "(닉네임 없음)"
        print(f"  - {user.username} ({nickname}) - {user.email}")

# 게임 현황
games = Game.objects.all()
print(f"\n🎮 전체 게임: {games.count()}판")
if games.exists():
    print("\n최근 게임:")
    for game in games.order_by('-created_at')[:5]:
        black = game.black.first_name if game.black and game.black.first_name else game.black.username if game.black else "없음"
        white = game.white.first_name if game.white and game.white.first_name else game.white.username if game.white else "대기중"
        status = "진행중"
        if game.winner == "black":
            status = f"흑승 ({black})"
        elif game.winner == "white":
            status = f"백승 ({white})"
        elif game.winner == "draw":
            status = "무승부"

        print(f"  #{game.id} - {black} vs {white} - {status}")

# 총 수순
total_moves = Move.objects.count()
print(f"\n📋 전체 수순: {total_moves}수")

print("\n" + "=" * 60)