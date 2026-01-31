from dataclasses import dataclass


@dataclass
class TierInfo:
    name: str
    min_rp: int
    max_rp: int | None  # None = 무제한
    color: str  # hex color
    bg_color: str  # background color for badges
    icon_name: str  # SVG icon identifier


# 티어 정의 (낮은 RP부터 높은 RP 순서)
TIERS = [
    TierInfo("5급", 0, 899, "#6b7280", "#f3f4f6", "rank-5"),
    TierInfo("4급", 900, 999, "#3b82f6", "#eff6ff", "rank-4"),
    TierInfo("3급", 1000, 1099, "#06b6d4", "#ecfeff", "rank-3"),
    TierInfo("2급", 1100, 1199, "#10b981", "#ecfdf5", "rank-2"),
    TierInfo("1급", 1200, 1299, "#22c55e", "#f0fdf4", "rank-1"),
    TierInfo("1단", 1300, 1399, "#84cc16", "#f7fee7", "dan-1"),
    TierInfo("2단", 1400, 1499, "#eab308", "#fefce8", "dan-2"),
    TierInfo("3단", 1500, 1599, "#f59e0b", "#fffbeb", "dan-3"),
    TierInfo("낭인", 1600, 1699, "#8b5cf6", "#f5f3ff", "ronin"),
    TierInfo("달인", 1700, 1799, "#a855f7", "#faf5ff", "master"),
    TierInfo("명인", 1800, 1899, "#ec4899", "#fdf2f8", "expert"),
    TierInfo("지존", 1900, 1999, "#f43f5e", "#fff1f2", "supreme"),
    TierInfo("패왕", 2000, 2099, "#ef4444", "#fef2f2", "conqueror"),
    TierInfo("투신", 2100, 2199, "#dc2626", "#fef2f2", "wargod"),
    TierInfo("무신", 2200, None, "#b91c1c", "#1f1f1f", "divine"),
]


def get_tier(rp: int) -> TierInfo:
    """RP에 해당하는 티어 정보 반환"""
    for tier in TIERS:
        if tier.max_rp is None:
            if rp >= tier.min_rp:
                return tier
        elif tier.min_rp <= rp <= tier.max_rp:
            return tier
    # 기본값 (800 미만)
    return TIERS[0]


def get_tier_name(rp: int) -> str:
    """RP에 해당하는 티어 이름 반환"""
    return get_tier(rp).name


def get_tier_color(rp: int) -> str:
    """RP에 해당하는 티어 색상 반환"""
    return get_tier(rp).color


def get_tier_range_display(rp: int, range_delta: int) -> str:
    """
    RP 범위를 티어 범위로 표시
    예: rp=1050, range_delta=100 -> "4급 ~ 2급"
    """
    min_rp = max(0, rp - range_delta)
    max_rp = rp + range_delta

    min_tier = get_tier(min_rp)
    max_tier = get_tier(max_rp)

    if min_tier.name == max_tier.name:
        return min_tier.name
    return f"{min_tier.name} ~ {max_tier.name}"


def get_all_tiers() -> list[TierInfo]:
    """모든 티어 정보 반환"""
    return TIERS.copy()


# 티어 아이콘 SVG 정의
TIER_ICONS = {
    # 급 (5급~1급) - 바둑돌 모양, 점점 채워짐
    "rank-5": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/>
        <text x="12" y="16" text-anchor="middle" font-size="10" font-weight="bold" fill="currentColor">5</text>
    </svg>""",
    "rank-4": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/>
        <circle cx="12" cy="12" r="3" fill="currentColor"/>
        <text x="12" y="16" text-anchor="middle" font-size="10" font-weight="bold" fill="currentColor">4</text>
    </svg>""",
    "rank-3": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/>
        <circle cx="12" cy="12" r="5" fill="currentColor" opacity="0.3"/>
        <text x="12" y="16" text-anchor="middle" font-size="10" font-weight="bold" fill="currentColor">3</text>
    </svg>""",
    "rank-2": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/>
        <circle cx="12" cy="12" r="6" fill="currentColor" opacity="0.5"/>
        <text x="12" y="16" text-anchor="middle" font-size="10" font-weight="bold" fill="currentColor">2</text>
    </svg>""",
    "rank-1": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="currentColor" opacity="0.7"/>
        <text x="12" y="16" text-anchor="middle" font-size="10" font-weight="bold" fill="white">1</text>
    </svg>""",

    # 단 (1단~3단) - 검은 바둑돌 + 별
    "dan-1": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" fill="currentColor"/>
        <path d="M12 6l1.5 3 3.5.5-2.5 2.5.5 3.5L12 14l-3 1.5.5-3.5L7 9.5l3.5-.5z" fill="white"/>
    </svg>""",
    "dan-2": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" fill="currentColor"/>
        <path d="M8 8l1 2 2.3.3-1.6 1.6.3 2.3L8 13l-2 1.2.3-2.3L4.7 10.3 7 10z" fill="white"/>
        <path d="M16 8l1 2 2.3.3-1.6 1.6.3 2.3-2-1.2-2 1.2.3-2.3-1.6-1.6 2.3-.3z" fill="white"/>
    </svg>""",
    "dan-3": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" fill="currentColor"/>
        <path d="M12 4l.8 1.8 2 .2-1.4 1.4.3 2L12 8.5l-1.7.9.3-2-1.4-1.4 2-.2z" fill="white"/>
        <path d="M7 11l.6 1.4 1.5.2-1.1 1 .2 1.5-1.2-.7-1.3.7.2-1.5-1-1 1.5-.2z" fill="white"/>
        <path d="M17 11l.6 1.4 1.5.2-1.1 1 .2 1.5-1.2-.7-1.3.7.2-1.5-1-1 1.5-.2z" fill="white"/>
    </svg>""",

    # 낭인 - 검
    "ronin": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 3L5 17l2 2L21 5l-2-2z" fill="currentColor"/>
        <path d="M5 17l-2 4 4-2" fill="currentColor"/>
        <path d="M14.5 9.5l-5 5" stroke="white" stroke-width="1"/>
        <circle cx="18" cy="6" r="2" fill="currentColor" stroke="white" stroke-width="0.5"/>
    </svg>""",

    # 달인 - 쌍검
    "master": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M7 2L3 18l1.5 1.5L18 6 7 2z" fill="currentColor" opacity="0.8"/>
        <path d="M17 2l4 16-1.5 1.5L6 6l11-4z" fill="currentColor"/>
        <path d="M3 18l2 3 2-1" fill="currentColor"/>
        <path d="M21 18l-2 3-2-1" fill="currentColor"/>
    </svg>""",

    # 명인 - 불꽃
    "expert": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C12 2 8 6 8 11c0 2 1 4 2.5 5C9 14 9 12 10 10c1 3 2 5 2 7 0-2 1-4 2-7 1 2 1 4-.5 6 1.5-1 2.5-3 2.5-5 0-5-4-9-4-9z" fill="currentColor"/>
        <path d="M12 14c-1 0-2 1-2 2.5S11 19 12 20c1-1 2-2 2-3.5S13 14 12 14z" fill="white" opacity="0.6"/>
    </svg>""",

    # 지존 - 왕관
    "supreme": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 18h18v3H3z" fill="currentColor"/>
        <path d="M4 8l3 6 5-4 5 4 3-6v10H4V8z" fill="currentColor"/>
        <circle cx="4" cy="7" r="2" fill="currentColor"/>
        <circle cx="12" cy="5" r="2" fill="currentColor"/>
        <circle cx="20" cy="7" r="2" fill="currentColor"/>
        <path d="M8 14h8v2H8z" fill="white" opacity="0.3"/>
    </svg>""",

    # 패왕 - 번개 왕관
    "conqueror": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 18h18v3H3z" fill="currentColor"/>
        <path d="M4 8l3 6 5-4 5 4 3-6v10H4V8z" fill="currentColor"/>
        <circle cx="4" cy="7" r="2" fill="currentColor"/>
        <circle cx="12" cy="5" r="2.5" fill="currentColor"/>
        <circle cx="20" cy="7" r="2" fill="currentColor"/>
        <path d="M13 1l-2 4h3l-3 5 1-3H9l3-6z" fill="white"/>
    </svg>""",

    # 투신 - 불타는 해골
    "wargod": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C8 2 5 5 5 9c0 2 1 4 2 5v4h10v-4c1-1 2-3 2-5 0-4-3-7-7-7z" fill="currentColor"/>
        <circle cx="9" cy="9" r="2" fill="white"/>
        <circle cx="15" cy="9" r="2" fill="white"/>
        <circle cx="9" cy="9" r="1" fill="currentColor"/>
        <circle cx="15" cy="9" r="1" fill="currentColor"/>
        <path d="M9 14h6v1H9z" fill="white"/>
        <path d="M10 15v3M12 15v4M14 15v3" stroke="white" stroke-width="1"/>
        <path d="M6 3c0-1 2-2 3-1-1 0-2 1-2 2" fill="currentColor" opacity="0.6"/>
        <path d="M18 3c0-1-2-2-3-1 1 0 2 1 2 2" fill="currentColor" opacity="0.6"/>
    </svg>""",

    # 무신 - 용
    "divine": """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 8c0-2 2-4 4-4 1 0 2 .5 3 1.5C12 4.5 13 4 14 4c2 0 4 2 4 4" stroke="currentColor" stroke-width="2" fill="none"/>
        <path d="M6 8c0 3 2 5 4 6l2 1 2-1c2-1 4-3 4-6" fill="currentColor"/>
        <circle cx="9" cy="9" r="1.5" fill="white"/>
        <circle cx="15" cy="9" r="1.5" fill="white"/>
        <circle cx="9" cy="9" r="0.7" fill="currentColor"/>
        <circle cx="15" cy="9" r="0.7" fill="currentColor"/>
        <path d="M12 12v2M10 13l2 2 2-2" stroke="white" stroke-width="0.7"/>
        <path d="M2 6l2 1-1 2" fill="currentColor"/>
        <path d="M22 6l-2 1 1 2" fill="currentColor"/>
        <path d="M12 15c-1 1-2 3-2 5h4c0-2-1-4-2-5z" fill="currentColor"/>
        <path d="M8 19c-1 1-3 2-5 2M16 19c1 1 3 2 5 2" stroke="currentColor" stroke-width="1.5"/>
    </svg>""",
}


def get_tier_icon_svg(rp: int) -> str:
    """RP에 해당하는 티어 아이콘 SVG 반환"""
    tier = get_tier(rp)
    return TIER_ICONS.get(tier.icon_name, TIER_ICONS["rank-5"])