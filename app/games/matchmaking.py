import random
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# 매칭 설정
BASE_RANGE = 50  # 기본 Rating 범위
EXPANSION_RATE = 25  # 확장 속도 (15초당)
EXPANSION_INTERVAL = 15  # 확장 간격 (초)
MAX_RANGE = 300  # 최대 범위
ACCEPT_TIMEOUT = 10  # 수락 제한 시간 (초)


class MatchStatus(Enum):
    WAITING = "waiting"  # 상대방 수락 대기
    CONFIRMED = "confirmed"  # 양쪽 수락 완료
    DECLINED = "declined"  # 거절됨
    TIMEOUT = "timeout"  # 시간 초과


@dataclass
class QueueEntry:
    user_id: int
    rating: int
    channel_name: str
    nickname: str
    username: str
    joined_at: float  # timestamp
    total_games: int = 0  # 총 게임 수 (배치 여부 판단용)
    profile_image: str = ""  # 프로필 이미지 URL


@dataclass
class PendingMatch:
    match_id: str
    player1: QueueEntry
    player2: QueueEntry
    player1_accepted: bool
    player2_accepted: bool
    created_at: float


def get_rating_range(rating: int, seconds_in_queue: int) -> tuple[int, int]:
    """큐 대기 시간에 따른 Rating 범위 계산"""
    expansions = seconds_in_queue // EXPANSION_INTERVAL
    current_range = min(BASE_RANGE + (expansions * EXPANSION_RATE), MAX_RANGE)
    return (rating - current_range, rating + current_range)


def get_current_range(seconds_in_queue: int) -> int:
    """현재 검색 범위 반환 (UI 표시용)"""
    expansions = seconds_in_queue // EXPANSION_INTERVAL
    return min(BASE_RANGE + (expansions * EXPANSION_RATE), MAX_RANGE)


class MatchmakingService:
    """싱글톤 매칭 서비스"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.queue: dict[int, QueueEntry] = {}
            cls._instance.pending_matches: dict[str, PendingMatch] = {}
            cls._instance.user_match_map: dict[int, str] = {}  # user_id -> match_id
        return cls._instance

    def add_to_queue(
        self,
        user_id: int,
        rating: int,
        channel_name: str,
        nickname: str,
        username: str,
        total_games: int = 0,
        profile_image: str = "",
    ) -> bool:
        """큐에 사용자 추가"""
        # 이미 큐에 있거나 매칭 중이면 거부
        if user_id in self.queue or user_id in self.user_match_map:
            return False

        self.queue[user_id] = QueueEntry(
            user_id=user_id,
            rating=rating,
            channel_name=channel_name,
            nickname=nickname,
            username=username,
            joined_at=time.time(),
            total_games=total_games,
            profile_image=profile_image,
        )
        return True

    def remove_from_queue(self, user_id: int) -> bool:
        """큐에서 사용자 제거"""
        if user_id in self.queue:
            del self.queue[user_id]
            return True
        return False

    def get_queue_entry(self, user_id: int) -> Optional[QueueEntry]:
        """큐 엔트리 조회"""
        return self.queue.get(user_id)

    def get_seconds_in_queue(self, user_id: int) -> int:
        """큐 대기 시간 반환"""
        entry = self.queue.get(user_id)
        if entry:
            return int(time.time() - entry.joined_at)
        return 0

    def find_match(self, user_id: int) -> Optional[QueueEntry]:
        """매칭 상대 찾기"""
        entry = self.queue.get(user_id)
        if not entry:
            return None

        seconds_in_queue = int(time.time() - entry.joined_at)
        min_rating, max_rating = get_rating_range(entry.rating, seconds_in_queue)

        # 대기 시간 순으로 정렬하여 검색
        candidates = sorted(
            [e for e in self.queue.values() if e.user_id != user_id],
            key=lambda x: x.joined_at,
        )

        for candidate in candidates:
            # 내 범위 안에 있는지 확인
            if not (min_rating <= candidate.rating <= max_rating):
                continue

            # 상대방의 범위 안에 내가 있는지 확인
            candidate_seconds = int(time.time() - candidate.joined_at)
            cand_min, cand_max = get_rating_range(candidate.rating, candidate_seconds)

            if cand_min <= entry.rating <= cand_max:
                return candidate

        return None

    def create_pending_match(self, player1: QueueEntry, player2: QueueEntry) -> str:
        """매칭 성공 - 대기 상태 생성"""
        match_id = str(uuid.uuid4())

        # 큐에서 제거
        self.remove_from_queue(player1.user_id)
        self.remove_from_queue(player2.user_id)

        # 대기 매치 생성
        self.pending_matches[match_id] = PendingMatch(
            match_id=match_id,
            player1=player1,
            player2=player2,
            player1_accepted=False,
            player2_accepted=False,
            created_at=time.time(),
        )

        # 유저-매치 매핑
        self.user_match_map[player1.user_id] = match_id
        self.user_match_map[player2.user_id] = match_id

        return match_id

    def get_pending_match(self, match_id: str) -> Optional[PendingMatch]:
        """대기 매치 조회"""
        return self.pending_matches.get(match_id)

    def get_user_match(self, user_id: int) -> Optional[PendingMatch]:
        """유저의 대기 매치 조회"""
        match_id = self.user_match_map.get(user_id)
        if match_id:
            return self.pending_matches.get(match_id)
        return None

    def accept_match(self, match_id: str, user_id: int) -> MatchStatus:
        """매칭 수락"""
        match = self.pending_matches.get(match_id)
        if not match:
            return MatchStatus.DECLINED

        # 수락 타임아웃 체크
        if time.time() - match.created_at > ACCEPT_TIMEOUT:
            self._cleanup_match(match_id)
            return MatchStatus.TIMEOUT

        # 수락 처리
        if match.player1.user_id == user_id:
            match.player1_accepted = True
        elif match.player2.user_id == user_id:
            match.player2_accepted = True

        # 양쪽 수락 확인
        if match.player1_accepted and match.player2_accepted:
            return MatchStatus.CONFIRMED

        return MatchStatus.WAITING

    def decline_match(
        self, match_id: str, user_id: int
    ) -> tuple[MatchStatus, Optional[QueueEntry]]:
        """매칭 거절 - 상대방을 다시 큐에 넣음"""
        match = self.pending_matches.get(match_id)
        if not match:
            return MatchStatus.DECLINED, None

        # 상대방 정보
        other_player = (
            match.player2 if match.player1.user_id == user_id else match.player1
        )

        # 매치 정리
        self._cleanup_match(match_id)

        return MatchStatus.DECLINED, other_player

    def confirm_and_cleanup(self, match_id: str) -> Optional[PendingMatch]:
        """매칭 확정 후 정리"""
        match = self.pending_matches.get(match_id)
        if match:
            self._cleanup_match(match_id)
        return match

    def _cleanup_match(self, match_id: str):
        """매치 정리"""
        match = self.pending_matches.get(match_id)
        if match:
            # 유저-매치 매핑 제거
            self.user_match_map.pop(match.player1.user_id, None)
            self.user_match_map.pop(match.player2.user_id, None)
            # 매치 제거
            del self.pending_matches[match_id]

    def cleanup_user(self, user_id: int):
        """유저 연결 해제 시 정리"""
        # 큐에서 제거
        self.remove_from_queue(user_id)

        # 대기 매치가 있으면 거절 처리
        match_id = self.user_match_map.get(user_id)
        if match_id:
            self.decline_match(match_id, user_id)

    def get_queue_size(self) -> int:
        """큐 크기 반환"""
        return len(self.queue)

    @staticmethod
    def assign_colors() -> tuple[str, str]:
        """흑/백 랜덤 배정 (player1, player2 순서)"""
        if random.random() < 0.5:
            return "black", "white"
        return "white", "black"


# 싱글톤 인스턴스
matchmaking_service = MatchmakingService()
