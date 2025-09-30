BOARD_SIZE = 15

def in_bounds(x, y):
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

def check_five(board_str, stone):
    # board_str: 길이 225, '.', 'B', 'W'
    dirs = [(1,0),(0,1),(1,1),(1,-1)]
    def get(x,y):
        return board_str[y*BOARD_SIZE + x]
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if get(x,y) != stone:
                continue
            for dx,dy in dirs:
                cnt = 1
                nx, ny = x+dx, y+dy
                while in_bounds(nx,ny) and get(nx,ny)==stone:
                    cnt += 1
                    if cnt >= 5:
                        return True
                    nx += dx; ny += dy
    return False