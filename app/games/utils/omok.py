EMPTY = "."
BLACK = "B"
WHITE = "W"

# ↔, ↕, ↗, ↘
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


# ------------------------------
# 기본 유틸
# ------------------------------
def _in_bounds(n, x, y):
    return 0 <= x < n and 0 <= y < n


def _run_length_from(board, x, y, dx, dy, stone):
    """(x,y)에 stone이 놓였다고 가정하고 (dx,dy) 양방향 연속 길이."""
    n = len(board)
    cnt = 1
    # +
    i, j = x + dx, y + dy
    while _in_bounds(n, i, j) and board[i][j] == stone:
        cnt += 1
        i, j = i + dx, j + dy
    # -
    i, j = x - dx, y - dy
    while _in_bounds(n, i, j) and board[i][j] == stone:
        cnt += 1
        i, j = i - dx, j - dy
    return cnt


def _line_as_string_with_coords(board, x, y, dx, dy, span=6):
    """
    (x,y) 기준 (dx,dy) 방향을 ±span 길이로 문자열화 + 각 글자의 보드 좌표를 함께 제공.
    경계 밖은 'X'.
    """
    n = len(board)
    chars, coords = [], []
    for k in range(-span, span + 1):
        i, j = x + k * dx, y + k * dy
        if _in_bounds(n, i, j):
            chars.append(board[i][j])
            coords.append((i, j))
        else:
            chars.append("X")
            coords.append((None, None))
    return "".join(chars), coords


# ------------------------------
# 5목/장목
# ------------------------------
def check_five(board, stone):
    """보드에 stone의 5목 이상이 하나라도 존재하면 True."""
    n = len(board)
    for i in range(n):
        for j in range(n):
            if board[i][j] != stone:
                continue
            for dx, dy in DIRECTIONS:
                if _run_length_from(board, i, j, dx, dy, stone) >= 5:
                    return True
    return False


def has_exact_five(board, x, y, stone):
    """
    (x,y)에 (이미) 둔 상태라고 가정하고 정확히 5목인가?
    - 어느 한 방향 run == 5 → True
    - run >= 6 있으면 False
    """
    exact = False
    for dx, dy in DIRECTIONS:
        run = _run_length_from(board, x, y, dx, dy, stone)
        if run >= 6:
            return False
        if run == 5:
            exact = True
    return exact


def is_overline_present(board, stone):
    """현재 보드에 stone의 장목(6목↑)이 존재하면 True."""
    n = len(board)
    for i in range(n):
        for j in range(n):
            if board[i][j] != stone:
                continue
            for dx, dy in DIRECTIONS:
                if _run_length_from(board, i, j, dx, dy, stone) >= 6:
                    return True
    return False


def would_be_overline(board, x, y, stone):
    """(x,y)에 두면 장목(6목↑)이 되는가? (시뮬레이션)"""
    n = len(board)
    if not _in_bounds(n, x, y) or board[x][y] != EMPTY:
        return False
    board[x][y] = stone
    try:
        for dx, dy in DIRECTIONS:
            if _run_length_from(board, x, y, dx, dy, stone) >= 6:
                return True
        return False
    finally:
        board[x][y] = EMPTY


def is_overline(board, x, y, stone, *, present_only=False, simulate=False):
    """
    테스트 호환용 래퍼.
    - present_only=True  → 현재 보드에 장목 존재? (비시뮬)
    - simulate=True      → (x,y)에 두면 장목? (시뮬)
    - 둘 다 False(기본값) → 과거 호환 위해 simulate 모드로 동작
    """
    if present_only and simulate:
        simulate = True  # simulate 우선
    if simulate or (not present_only and not simulate):
        return would_be_overline(board, x, y, stone)
    else:
        return is_overline_present(board, stone)


# ------------------------------
# 열린4 / 열린3
# ------------------------------
def _has_open_four_on_dir_str(s, coords, color):
    """
    s 안의 '.BBBB.' 모든 발생 위치를 훑으며,
    그 4연의 바깥이 같은 색으로 '즉시' 이어지지 않는(=독립된 열린4) 경우가 하나라도 있으면 True.
    """
    target = f".{color}{color}{color}{color}."
    n = len(s)
    start = 0
    while True:
        idx = s.find(target, start)
        if idx == -1:
            return False

        left_edge = idx  # 왼쪽 '.'
        right_edge = idx + 5  # 오른쪽 '.'

        left_out_idx = left_edge - 1
        right_out_idx = right_edge + 1

        left_ok = not (0 <= left_out_idx < n and s[left_out_idx] == color)
        right_ok = not (0 <= right_out_idx < n and s[right_out_idx] == color)

        if left_ok and right_ok:
            return True

        start = idx + 1  # 다음 후보 계속 검색


def _has_open_four_on_dir(board, x, y, dx, dy, color):
    s, coords = _line_as_string_with_coords(board, x, y, dx, dy, span=6)
    return _has_open_four_on_dir_str(s, coords, color)


def _has_open_three_on_dir(board, x, y, dx, dy, color):
    """
    (x,y)에 color가 '이미' 놓였다고 가정.
    같은 방향에서 '빈칸 하나에 한 수 더 두면' 열린4(.BBBB.)가 되는 경우가 있으면 True.

    주의: 이미 열린4(.BBBB.)인 방향은 열린3으로 간주하지 않음 (표준 렌주 룰)
    """
    # 현재 라인 문자열
    s, _ = _line_as_string_with_coords(board, x, y, dx, dy, span=6)
    c = color

    n = len(board)

    # (1) 시뮬레이션: 같은 방향 라인의 빈칸 하나에 한 수 더 두면 .BBBB. ?
    for t in range(-5, 6):
        i, j = x + t * dx, y + t * dy
        if not _in_bounds(n, i, j) or board[i][j] != EMPTY:
            continue
        board[i][j] = color
        try:
            if _has_open_four_on_dir(board, i, j, dx, dy, color):
                return True
        finally:
            board[i][j] = EMPTY

    # (2) 보조 패턴: .BBB. / .BB.B. / .B.BB. / .B.B.
    patterns = [
        f".{c}{c}{c}.",  # .BBB.
        f".{c}{c}.{c}.",  # .BB.B.
        f".{c}.{c}{c}.",  # .B.BB.
        f".{c}.{c}.",  # .B.B. (점프 활삼)
    ]
    return any(p in s for p in patterns)


def count_open_four_dirs(board, x, y, color):
    """(x,y)에 color를 둘 때 생성되는 '독립된' 열린4가 서로 다른 방향에서 몇 개인지."""
    n = len(board)
    if not _in_bounds(n, x, y) or board[x][y] != EMPTY:
        return 0
    board[x][y] = color
    try:
        cnt = 0
        for dx, dy in DIRECTIONS:
            if _has_open_four_on_dir(board, x, y, dx, dy, color):
                cnt += 1
        return cnt
    finally:
        board[x][y] = EMPTY


# ------------------------------
# 금수 본판정 (정석룰)
# ------------------------------
def is_forbidden_double_three(board, x, y, stone):
    """
    흑(B)만 33 금수.
    (x,y)에 두었을 때 서로 다른 두 방향 이상에서 '열린3'이면 True.
    - 범위 밖: False (유효성은 호출부에서 별도 처리 권장)
    - 이미 돌이 있는 칸: True (착수 불가 취지)
    """
    if stone != BLACK:
        return False
    n = len(board)
    if not _in_bounds(n, x, y):
        return False
    if board[x][y] != EMPTY:
        return True

    board[x][y] = stone
    try:
        dirs = 0
        for dx, dy in DIRECTIONS:
            if _has_open_three_on_dir(board, x, y, dx, dy, stone):
                dirs += 1
                if dirs >= 2:
                    return True
        return False
    finally:
        board[x][y] = EMPTY


def is_forbidden_double_four(board, x, y, stone):
    """
    흑(B)만 44 금수.
    (x,y)에 둘 때 서로 다른 두 방향 이상에서 '독립된' 열린4(.BBBB.)가 동시에 만들어지면 True.
    """
    if stone != BLACK:
        return False
    return count_open_four_dirs(board, x, y, stone) >= 2


# ------------------------------
# 디버그 헬퍼
# ------------------------------
DIR_NAMES = {(1, 0): "H(가로)", (0, 1): "V(세로)", (1, 1): "D↘", (1, -1): "D↗"}


def debug_double_three(board, x, y, stone):
    if stone != BLACK:
        return {"is33": False, "dirs": [], "spots": {}}
    n = len(board)
    if not _in_bounds(n, x, y):
        return {"is33": False, "dirs": [], "spots": {}}

    placed = board[x][y] == stone
    if not placed:
        if board[x][y] != EMPTY:
            return {"is33": True, "dirs": [], "spots": {}}
        board[x][y] = stone

    try:
        dirs, spots = [], {}
        for dx, dy in DIRECTIONS:
            has_three = False
            cand = []
            for t in range(-5, 6):
                i, j = x + t * dx, y + t * dy
                if not _in_bounds(n, i, j) or board[i][j] != EMPTY:
                    continue
                board[i][j] = stone
                try:
                    if _has_open_four_on_dir(board, i, j, dx, dy, stone):
                        has_three = True
                        cand.append((i, j))
                finally:
                    board[i][j] = EMPTY
            if has_three:
                name = DIR_NAMES[(dx, dy)]
                dirs.append(name)
                spots[name] = cand
        return {"is33": len(dirs) >= 2, "dirs": dirs, "spots": spots}
    finally:
        if not placed:
            board[x][y] = EMPTY
