/**
 * 오목 AI 엔진
 * - 렌주 규칙 (33, 44, 장목 금수)
 * - Minimax + Alpha-Beta Pruning
 */

const EMPTY = ".";
const BLACK = "B";
const WHITE = "W";
const SIZE = 15;
const DIRECTIONS = [[1, 0], [0, 1], [1, 1], [1, -1]]; // 가로, 세로, 대각선↘, 대각선↗

// ========================================
// 보드 클래스
// ========================================
class OmokBoard {
  constructor(boardStr = null) {
    if (boardStr && boardStr.length === SIZE * SIZE) {
      this.board = boardStr;
    } else {
      this.board = EMPTY.repeat(SIZE * SIZE);
    }
    this.lastMove = null;
  }

  get(x, y) {
    if (!this.inBounds(x, y)) return "X";
    return this.board[y * SIZE + x];
  }

  set(x, y, stone) {
    if (!this.inBounds(x, y)) return;
    const idx = y * SIZE + x;
    this.board = this.board.slice(0, idx) + stone + this.board.slice(idx + 1);
    this.lastMove = { x, y, stone };
  }

  inBounds(x, y) {
    return x >= 0 && x < SIZE && y >= 0 && y < SIZE;
  }

  isEmpty(x, y) {
    return this.get(x, y) === EMPTY;
  }

  clone() {
    const newBoard = new OmokBoard(this.board);
    newBoard.lastMove = this.lastMove ? { ...this.lastMove } : null;
    return newBoard;
  }

  // 빈 칸 목록 반환 (AI 후보 수 계산용)
  getEmptyPositions() {
    const positions = [];
    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (this.isEmpty(x, y)) {
          positions.push({ x, y });
        }
      }
    }
    return positions;
  }

  // 돌 주변의 빈 칸만 반환 (탐색 최적화)
  getCandidateMoves(range = 2) {
    const candidates = new Set();
    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (this.get(x, y) !== EMPTY) {
          // 주변 range 칸 이내의 빈 칸 추가
          for (let dy = -range; dy <= range; dy++) {
            for (let dx = -range; dx <= range; dx++) {
              const nx = x + dx;
              const ny = y + dy;
              if (this.inBounds(nx, ny) && this.isEmpty(nx, ny)) {
                candidates.add(`${nx},${ny}`);
              }
            }
          }
        }
      }
    }
    // 보드가 비어있으면 중앙
    if (candidates.size === 0) {
      return [{ x: 7, y: 7 }];
    }
    return Array.from(candidates).map(s => {
      const [x, y] = s.split(",").map(Number);
      return { x, y };
    });
  }

  getMoveCount() {
    let count = 0;
    for (let i = 0; i < this.board.length; i++) {
      if (this.board[i] !== EMPTY) count++;
    }
    return count;
  }
}

// ========================================
// 렌주 규칙 엔진
// ========================================
class OmokRules {
  // 연속 돌 길이 계산 (양방향)
  static runLength(board, x, y, dx, dy, stone) {
    let count = 1;
    // + 방향
    let nx = x + dx, ny = y + dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      count++;
      nx += dx;
      ny += dy;
    }
    // - 방향
    nx = x - dx;
    ny = y - dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      count++;
      nx -= dx;
      ny -= dy;
    }
    return count;
  }

  // 라인을 문자열로 추출 (span 범위)
  static lineAsString(board, x, y, dx, dy, span = 6) {
    let chars = "";
    for (let k = -span; k <= span; k++) {
      const nx = x + k * dx;
      const ny = y + k * dy;
      chars += board.inBounds(nx, ny) ? board.get(nx, ny) : "X";
    }
    return chars;
  }

  // 5목 체크 (승리 조건)
  static checkFive(board, stone) {
    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (board.get(x, y) !== stone) continue;
        for (const [dx, dy] of DIRECTIONS) {
          if (this.runLength(board, x, y, dx, dy, stone) >= 5) {
            return true;
          }
        }
      }
    }
    return false;
  }

  // 정확히 5목인지 체크 (흑 승리 조건)
  static hasExactFive(board, x, y, stone) {
    let exact = false;
    for (const [dx, dy] of DIRECTIONS) {
      const run = this.runLength(board, x, y, dx, dy, stone);
      if (run >= 6) return false; // 장목
      if (run === 5) exact = true;
    }
    return exact;
  }

  // 장목 체크 (6목 이상)
  static wouldBeOverline(board, x, y, stone) {
    if (!board.inBounds(x, y) || !board.isEmpty(x, y)) return false;
    board.set(x, y, stone);
    let isOverline = false;
    for (const [dx, dy] of DIRECTIONS) {
      if (this.runLength(board, x, y, dx, dy, stone) >= 6) {
        isOverline = true;
        break;
      }
    }
    board.set(x, y, EMPTY);
    return isOverline;
  }

  // 열린4 체크 (.BBBB.)
  static hasOpenFourOnDir(board, x, y, dx, dy, stone) {
    const s = this.lineAsString(board, x, y, dx, dy, 6);
    const target = `.${stone}${stone}${stone}${stone}.`;
    let start = 0;
    while (true) {
      const idx = s.indexOf(target, start);
      if (idx === -1) return false;

      const leftOut = idx - 1;
      const rightOut = idx + 6;
      const leftOk = !(leftOut >= 0 && s[leftOut] === stone);
      const rightOk = !(rightOut < s.length && s[rightOut] === stone);

      if (leftOk && rightOk) return true;
      start = idx + 1;
    }
  }

  // 열린3 체크 (한 수 더 두면 열린4가 됨)
  static hasOpenThreeOnDir(board, x, y, dx, dy, stone) {
    const s = this.lineAsString(board, x, y, dx, dy, 6);

    // 시뮬레이션: 같은 방향의 빈칸에 두면 열린4가 되는지
    for (let t = -5; t <= 5; t++) {
      const nx = x + t * dx;
      const ny = y + t * dy;
      if (!board.inBounds(nx, ny) || !board.isEmpty(nx, ny)) continue;

      board.set(nx, ny, stone);
      const hasOpenFour = this.hasOpenFourOnDir(board, nx, ny, dx, dy, stone);
      board.set(nx, ny, EMPTY);

      if (hasOpenFour) return true;
    }

    // 보조 패턴
    const patterns = [
      `.${stone}${stone}${stone}.`,
      `.${stone}${stone}.${stone}.`,
      `.${stone}.${stone}${stone}.`
    ];
    return patterns.some(p => s.includes(p));
  }

  // 열린4 방향 개수
  static countOpenFourDirs(board, x, y, stone) {
    if (!board.inBounds(x, y) || !board.isEmpty(x, y)) return 0;

    board.set(x, y, stone);
    let count = 0;
    for (const [dx, dy] of DIRECTIONS) {
      if (this.hasOpenFourOnDir(board, x, y, dx, dy, stone)) {
        count++;
      }
    }
    board.set(x, y, EMPTY);
    return count;
  }

  // 33 금수 (흑만)
  static isForbiddenDoubleThree(board, x, y, stone) {
    if (stone !== BLACK) return false;
    if (!board.inBounds(x, y) || !board.isEmpty(x, y)) return false;

    board.set(x, y, stone);
    let dirs = 0;
    for (const [dx, dy] of DIRECTIONS) {
      if (this.hasOpenThreeOnDir(board, x, y, dx, dy, stone)) {
        dirs++;
        if (dirs >= 2) {
          board.set(x, y, EMPTY);
          return true;
        }
      }
    }
    board.set(x, y, EMPTY);
    return false;
  }

  // 44 금수 (흑만)
  static isForbiddenDoubleFour(board, x, y, stone) {
    if (stone !== BLACK) return false;
    return this.countOpenFourDirs(board, x, y, stone) >= 2;
  }

  // 금수 종합 체크
  static isForbiddenMove(board, x, y, stone) {
    if (stone !== BLACK) return false;
    if (!board.isEmpty(x, y)) return true;

    // 장목 금수
    if (this.wouldBeOverline(board, x, y, stone)) return true;
    // 33 금수
    if (this.isForbiddenDoubleThree(board, x, y, stone)) return true;
    // 44 금수
    if (this.isForbiddenDoubleFour(board, x, y, stone)) return true;

    return false;
  }

  // 유효한 수인지 체크
  static isValidMove(board, x, y, stone) {
    if (!board.inBounds(x, y)) return false;
    if (!board.isEmpty(x, y)) return false;
    if (this.isForbiddenMove(board, x, y, stone)) return false;
    return true;
  }

  // 승리 체크
  static checkWin(board, x, y, stone) {
    if (stone === BLACK) {
      return this.hasExactFive(board, x, y, stone);
    } else {
      // 백은 5목 이상이면 승리
      for (const [dx, dy] of DIRECTIONS) {
        if (this.runLength(board, x, y, dx, dy, stone) >= 5) {
          return true;
        }
      }
      return false;
    }
  }
}

// ========================================
// AI 엔진 (프로 레벨 강화 버전)
// ========================================
class OmokAI {
  constructor(difficulty = "normal") {
    this.difficulty = difficulty;
    // 난이도별 설정
    this.config = {
      easy: { depth: 2, candidateLimit: 6, randomFactor: 0.50, vcfDepth: 0, timeLimit: 1000, skipDefense: true },
      normal: { depth: 4, candidateLimit: 10, randomFactor: 0.25, vcfDepth: 0, timeLimit: 2000, skipDefense: true },
      hard: { depth: 6, candidateLimit: 18, randomFactor: 0, vcfDepth: 10, timeLimit: 4000, skipDefense: false }
    };
    const cfg = this.config[difficulty] || this.config.normal;
    this.maxDepth = cfg.depth;
    this.candidateLimit = cfg.candidateLimit;
    this.randomFactor = cfg.randomFactor;
    this.vcfDepth = cfg.vcfDepth;
    this.timeLimit = cfg.timeLimit;
    this.skipDefense = cfg.skipDefense || false;
    this.nodeCount = 0;
    this.vcfCache = new Map();
    this.startTime = 0;
    this.timeOut = false;

    // 패턴 점수 (공격/방어) - 프로 레벨
    this.SCORES = {
      FIVE: 100000000,
      VCF_WIN: 50000000,       // VCF로 승리 확정
      OPEN_FOUR: 5000000,      // .XXXX. - 막을 수 없음
      DOUBLE_FOUR: 4000000,    // 4-4 공격
      FOUR_THREE: 3000000,     // 4-3 공격
      CLOSED_FOUR: 500000,     // 4 with one side blocked
      DOUBLE_THREE: 400000,    // 3-3 공격
      OPEN_THREE: 50000,       // .XXX. - 열린 3
      JUMP_THREE: 30000,       // .X.XX. 또는 .XX.X. - 점프 3
      CLOSED_THREE: 5000,
      OPEN_TWO: 1000,
      JUMP_TWO: 500,
      CLOSED_TWO: 100,
      ONE: 10
    };
  }

  opponent(stone) {
    return stone === BLACK ? WHITE : BLACK;
  }

  // ========================================
  // VCF (Victory by Continuous Four) 탐색
  // 연속으로 4를 만들어 강제로 이기는 수순 탐색
  // ========================================
  findVCF(board, stone, depth, isAttacker = true) {
    if (depth <= 0) return null;

    // 시간 초과 체크
    if (Date.now() - this.startTime > this.timeLimit * 0.3) {
      return null;
    }

    const cacheKey = board.board + stone + depth + isAttacker;
    if (this.vcfCache.has(cacheKey)) {
      return this.vcfCache.get(cacheKey);
    }

    const oppStone = this.opponent(stone);

    if (isAttacker) {
      // 공격자: 4를 만드는 수 찾기
      const fourMoves = this.getFourMoves(board, stone);

      for (const { x, y } of fourMoves) {
        if (!OmokRules.isValidMove(board, x, y, stone)) continue;

        const testBoard = board.clone();
        testBoard.set(x, y, stone);

        // 5목 완성?
        if (OmokRules.checkWin(testBoard, x, y, stone)) {
          this.vcfCache.set(cacheKey, { x, y, win: true });
          return { x, y, win: true };
        }

        // 열린4면 승리
        if (this.isOpenFourAt(testBoard, x, y, stone)) {
          this.vcfCache.set(cacheKey, { x, y, win: true });
          return { x, y, win: true };
        }

        // 상대가 막아야 하는 위치 찾기
        const blockMoves = this.getMustBlockMoves(testBoard, stone);
        if (blockMoves.length === 0) continue;

        // 상대가 막은 후 계속 공격
        let canWin = true;
        for (const block of blockMoves) {
          if (!testBoard.isEmpty(block.x, block.y)) continue;

          const blockBoard = testBoard.clone();
          blockBoard.set(block.x, block.y, oppStone);

          // 상대가 막으면서 5목?
          if (OmokRules.checkWin(blockBoard, block.x, block.y, oppStone)) {
            canWin = false;
            break;
          }

          // 재귀적으로 VCF 계속
          const nextVCF = this.findVCF(blockBoard, stone, depth - 2, true);
          if (!nextVCF || !nextVCF.win) {
            canWin = false;
            break;
          }
        }

        if (canWin) {
          this.vcfCache.set(cacheKey, { x, y, win: true });
          return { x, y, win: true };
        }
      }
    }

    this.vcfCache.set(cacheKey, null);
    return null;
  }

  // 4를 만드는 모든 수 찾기
  getFourMoves(board, stone) {
    const moves = [];
    const candidates = board.getCandidateMoves(2);

    for (const { x, y } of candidates) {
      if (!board.isEmpty(x, y)) continue;

      board.set(x, y, stone);
      let makesFour = false;

      for (const [dx, dy] of DIRECTIONS) {
        const { count } = this.countLine(board, x, y, dx, dy, stone);
        if (count >= 4) {
          makesFour = true;
          break;
        }
      }

      board.set(x, y, EMPTY);

      if (makesFour) {
        // 열린4 우선
        const priority = this.createsOpenFour(board, x, y, stone) ? 100 : 1;
        moves.push({ x, y, priority });
      }
    }

    return moves.sort((a, b) => b.priority - a.priority);
  }

  // 반드시 막아야 하는 위치 (상대 4 완성 방지)
  getMustBlockMoves(board, attackerStone) {
    const blocks = [];

    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (!board.isEmpty(x, y)) continue;

        board.set(x, y, attackerStone);
        let wouldWin = false;

        for (const [dx, dy] of DIRECTIONS) {
          const { count } = this.countLine(board, x, y, dx, dy, attackerStone);
          if (count >= 5) {
            wouldWin = true;
            break;
          }
        }

        board.set(x, y, EMPTY);

        if (wouldWin) {
          blocks.push({ x, y });
        }
      }
    }

    return blocks;
  }

  // 해당 위치에 열린4가 있는지
  isOpenFourAt(board, x, y, stone) {
    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
      if (count === 4 && openEnds === 2) return true;
    }
    return false;
  }

  // ========================================
  // 최선의 수 찾기 (메인)
  // ========================================
  findBestMove(board, stone) {
    this.nodeCount = 0;
    this.startTime = Date.now();
    this.timeOut = false;
    const oppStone = this.opponent(stone);

    // 오프닝 북 (초반 정석)
    const moveCount = board.getMoveCount();

    // 첫 수는 중앙
    if (moveCount === 0) {
      return { x: 7, y: 7 };
    }

    // 2번째 수 (상대가 첫 수를 둔 경우)
    if (moveCount === 1) {
      if (!board.isEmpty(7, 7)) {
        // 상대가 중앙에 뒀으면 대각선 인접
        const diagonals = [{x:6,y:6}, {x:6,y:8}, {x:8,y:6}, {x:8,y:8}];
        return diagonals[Math.floor(Math.random() * diagonals.length)];
      }
      return { x: 7, y: 7 };
    }

    // 3번째 수 (흑의 두번째 수)
    if (moveCount === 2 && stone === BLACK) {
      // 화월, 포월 등 정석 대응
      if (!board.isEmpty(7, 7)) {
        // 내가 중앙에 뒀고 상대가 인접에 뒀으면
        const responses = [
          { check: {x:6,y:6}, play: {x:8,y:8} }, { check: {x:6,y:8}, play: {x:8,y:6} },
          { check: {x:8,y:6}, play: {x:6,y:8} }, { check: {x:8,y:8}, play: {x:6,y:6} },
          { check: {x:6,y:7}, play: {x:8,y:7} }, { check: {x:8,y:7}, play: {x:6,y:7} },
          { check: {x:7,y:6}, play: {x:7,y:8} }, { check: {x:7,y:8}, play: {x:7,y:6} }
        ];
        for (const { check, play } of responses) {
          if (!board.isEmpty(check.x, check.y) && board.isEmpty(play.x, play.y)) {
            return play;
          }
        }
      }
    }

    // 초반 (5수 이내) 중앙 근처 선호
    if (moveCount < 5) {
      const preferredMoves = [];
      for (let dy = -2; dy <= 2; dy++) {
        for (let dx = -2; dx <= 2; dx++) {
          const nx = 7 + dx, ny = 7 + dy;
          if (board.isEmpty(nx, ny) && OmokRules.isValidMove(board, nx, ny, stone)) {
            const urgency = this.getMoveUrgency(board, nx, ny, stone, oppStone);
            preferredMoves.push({ x: nx, y: ny, urgency });
          }
        }
      }
      if (preferredMoves.length > 0) {
        preferredMoves.sort((a, b) => b.urgency - a.urgency);
        if (preferredMoves[0].urgency > 5000) {
          return { x: preferredMoves[0].x, y: preferredMoves[0].y };
        }
      }
    }

    const candidates = this.getSortedCandidates(board, stone);
    if (candidates.length === 0) {
      return { x: 7, y: 7 };
    }

    // 1. 즉시 승리 체크
    for (const { x, y } of candidates) {
      if (!OmokRules.isValidMove(board, x, y, stone)) continue;
      const testBoard = board.clone();
      testBoard.set(x, y, stone);
      if (OmokRules.checkWin(testBoard, x, y, stone)) {
        return { x, y, score: this.SCORES.FIVE };
      }
    }

    // 2. 상대 즉시 승리 방어 (쉬움 모드: 25% 확률로 무시)
    if (!this.skipDefense || Math.random() > 0.25) {
      for (const { x, y } of candidates) {
        if (!board.isEmpty(x, y)) continue;
        const testBoard = board.clone();
        testBoard.set(x, y, oppStone);
        if (OmokRules.checkWin(testBoard, x, y, oppStone)) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            return { x, y, score: this.SCORES.FIVE - 1 };
          }
        }
      }
    }

    // 3. 열린4 만들기 체크
    for (const { x, y } of candidates) {
      if (!OmokRules.isValidMove(board, x, y, stone)) continue;
      if (this.createsOpenFour(board, x, y, stone)) {
        return { x, y, score: this.SCORES.OPEN_FOUR };
      }
    }

    // 4. 상대 열린4 방어 (쉬움 모드: 40% 확률로 무시)
    if (!this.skipDefense || Math.random() > 0.4) {
      for (const { x, y } of candidates) {
        if (!board.isEmpty(x, y)) continue;
        if (this.createsOpenFour(board, x, y, oppStone)) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            return { x, y, score: this.SCORES.OPEN_FOUR - 1 };
          }
        }
      }
    }

    // 쉬움 모드가 아닐 때만 고급 방어
    if (!this.skipDefense) {
      // 4.5. 상대 점프4(띈4) 방어 - X.XXX, XX.XX, XXX.X 패턴
      const oppJumpFourBlocks = this.findJumpFourBlockMoves(board, oppStone);
      if (oppJumpFourBlocks.length > 0) {
        for (const { x, y } of oppJumpFourBlocks) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            return { x, y, score: this.SCORES.CLOSED_FOUR + 10000 };
          }
        }
      }

      // 4.6. 상대 열린3 방어
      const oppOpenThreeBlocks = this.findOpenThreeBlockMoves(board, oppStone);
      if (oppOpenThreeBlocks.length > 0) {
        for (const { x, y, threat } of oppOpenThreeBlocks) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            const myThreat = this.evaluatePosition(board, x, y, stone);
            if (myThreat > this.SCORES.OPEN_THREE) {
              return { x, y, score: this.SCORES.OPEN_FOUR - 50 };
            }
          }
        }
        for (const { x, y } of oppOpenThreeBlocks) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            return { x, y, score: this.SCORES.OPEN_THREE + 1000 };
          }
        }
      }
    }

    // 5. VCF 탐색 (쉬움 모드는 vcfDepth=0이라 스킵됨)
    if (this.vcfDepth > 0) {
      this.vcfCache.clear();
      const myVCF = this.findVCF(board, stone, this.vcfDepth, true);
      if (myVCF && myVCF.win) {
        return { x: myVCF.x, y: myVCF.y, score: this.SCORES.VCF_WIN };
      }

      // 6. 상대 VCF 방어
      if (!this.skipDefense) {
        this.vcfCache.clear();
        const oppVCF = this.findVCF(board, oppStone, this.vcfDepth, true);
        if (oppVCF && oppVCF.win) {
          if (OmokRules.isValidMove(board, oppVCF.x, oppVCF.y, stone)) {
            return { x: oppVCF.x, y: oppVCF.y, score: this.SCORES.VCF_WIN - 1 };
          }
        }
      }
    }

    // 7. 4-3 (쌍공격) 만들기
    for (const { x, y } of candidates) {
      if (!OmokRules.isValidMove(board, x, y, stone)) continue;
      if (this.createsFourThree(board, x, y, stone)) {
        return { x, y, score: this.SCORES.OPEN_FOUR - 100 };
      }
    }

    // 8. 상대 4-3 방어 (쉬움 모드 스킵)
    if (!this.skipDefense) {
      for (const { x, y } of candidates) {
        if (!board.isEmpty(x, y)) continue;
        if (this.createsFourThree(board, x, y, oppStone)) {
          if (OmokRules.isValidMove(board, x, y, stone)) {
            return { x, y, score: this.SCORES.OPEN_FOUR - 200 };
          }
        }
      }
    }

    // 7. 3-3 공격 (백일 경우)
    if (stone === WHITE) {
      for (const { x, y } of candidates) {
        if (!OmokRules.isValidMove(board, x, y, stone)) continue;
        if (this.createsDoubleThree(board, x, y, stone)) {
          return { x, y, score: this.SCORES.DOUBLE_THREE };
        }
      }
    }

    // 8. 열린3 만들기
    for (const { x, y } of candidates) {
      if (!OmokRules.isValidMove(board, x, y, stone)) continue;
      if (this.createsOpenThree(board, x, y, stone)) {
        // 상대도 열린3을 만들 수 있는지 체크
        let dominated = false;
        for (const { x: ox, y: oy } of candidates) {
          if (!board.isEmpty(ox, oy)) continue;
          if (this.createsOpenFour(board, ox, oy, oppStone) ||
              this.createsFourThree(board, ox, oy, oppStone)) {
            dominated = true;
            break;
          }
        }
        if (!dominated) {
          return { x, y, score: this.SCORES.OPEN_THREE };
        }
      }
    }

    // 9. Minimax 탐색
    let bestMove = null;
    let bestScore = -Infinity;

    const searchCandidates = candidates
      .filter(({ x, y }) => OmokRules.isValidMove(board, x, y, stone))
      .slice(0, this.candidateLimit);

    for (const { x, y } of searchCandidates) {
      const testBoard = board.clone();
      testBoard.set(x, y, stone);

      const score = this.minimax(
        testBoard,
        this.maxDepth - 1,
        -Infinity,
        Infinity,
        false,
        stone
      );

      if (score > bestScore) {
        bestScore = score;
        bestMove = { x, y, score };
      }
    }

    // 쉬움 모드: 확률적으로 차선 선택
    if (this.randomFactor > 0 && Math.random() < this.randomFactor && searchCandidates.length > 2) {
      const randomIdx = Math.floor(Math.random() * Math.min(4, searchCandidates.length));
      bestMove = { x: searchCandidates[randomIdx].x, y: searchCandidates[randomIdx].y };
    }

    const elapsed = Date.now() - this.startTime;
    console.log(`AI[${this.difficulty}]: ${this.nodeCount} nodes, ${elapsed}ms, best: (${bestMove?.x}, ${bestMove?.y}) score: ${bestScore}${this.timeOut ? ' (timeout)' : ''}`);

    return bestMove || { x: 7, y: 7 };
  }

  // 후보 수를 우선순위로 정렬
  getSortedCandidates(board, stone) {
    const candidates = board.getCandidateMoves(2);
    const oppStone = this.opponent(stone);

    return candidates
      .map(({ x, y }) => ({
        x, y,
        priority: this.getMoveUrgency(board, x, y, stone, oppStone)
      }))
      .sort((a, b) => b.priority - a.priority);
  }

  // 수의 긴급도 평가 (정렬용)
  getMoveUrgency(board, x, y, stone, oppStone) {
    if (!board.isEmpty(x, y)) return -Infinity;

    let score = 0;

    // 내 공격 점수
    score += this.evaluatePosition(board, x, y, stone) * 1.0;
    // 상대 방어 점수 (더 높은 가중치)
    score += this.evaluatePosition(board, x, y, oppStone) * 1.2;

    // 중앙 근접 보너스
    const centerDist = Math.abs(x - 7) + Math.abs(y - 7);
    score += (14 - centerDist) * 2;

    return score;
  }

  // 특정 위치에 놓았을 때 점수 평가
  evaluatePosition(board, x, y, stone) {
    let score = 0;
    board.set(x, y, stone);

    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);

      if (count >= 5) score += this.SCORES.FIVE;
      else if (count === 4) {
        score += openEnds === 2 ? this.SCORES.OPEN_FOUR : this.SCORES.CLOSED_FOUR;
      }
      else if (count === 3) {
        score += openEnds === 2 ? this.SCORES.OPEN_THREE : this.SCORES.CLOSED_THREE;
      }
      else if (count === 2) {
        score += openEnds === 2 ? this.SCORES.OPEN_TWO : this.SCORES.CLOSED_TWO;
      }
      else score += this.SCORES.ONE;
    }

    board.set(x, y, EMPTY);
    return score;
  }

  // 라인의 연속 돌 수와 열린 끝 수 계산
  countLine(board, x, y, dx, dy, stone) {
    let count = 1;
    let openEnds = 0;

    // + 방향
    let nx = x + dx, ny = y + dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      count++;
      nx += dx;
      ny += dy;
    }
    if (board.inBounds(nx, ny) && board.get(nx, ny) === EMPTY) openEnds++;

    // - 방향
    nx = x - dx;
    ny = y - dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      count++;
      nx -= dx;
      ny -= dy;
    }
    if (board.inBounds(nx, ny) && board.get(nx, ny) === EMPTY) openEnds++;

    return { count, openEnds };
  }

  // 점프 패턴 감지 (.X.XX., .XX.X., X.X.X 등)
  countJumpPattern(board, x, y, dx, dy, stone) {
    const line = [];

    // -5 ~ +5 범위의 라인 추출
    for (let i = -5; i <= 5; i++) {
      const nx = x + i * dx;
      const ny = y + i * dy;
      if (board.inBounds(nx, ny)) {
        line.push(board.get(nx, ny));
      } else {
        line.push('X'); // 벽
      }
    }

    const lineStr = line.join('');
    let score = 0;

    // 점프 3 패턴 (.X.XX., .XX.X.)
    const jump3Patterns = [
      new RegExp(`\\.${stone}\\.${stone}${stone}\\.`),
      new RegExp(`\\.${stone}${stone}\\.${stone}\\.`),
      new RegExp(`\\.${stone}\\.${stone}\\.${stone}\\.`)
    ];
    for (const p of jump3Patterns) {
      if (p.test(lineStr)) score += this.SCORES.JUMP_THREE;
    }

    // 점프 2 패턴 (.X..X., .X.X..)
    const jump2Patterns = [
      new RegExp(`\\.${stone}\\.\\.${stone}\\.`),
      new RegExp(`\\.${stone}\\.${stone}\\.\\.`)
    ];
    for (const p of jump2Patterns) {
      if (p.test(lineStr)) score += this.SCORES.JUMP_TWO;
    }

    return score;
  }

  // 열린4를 만드는지 체크
  createsOpenFour(board, x, y, stone) {
    board.set(x, y, stone);
    let result = false;

    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
      if (count === 4 && openEnds === 2) {
        result = true;
        break;
      }
    }

    board.set(x, y, EMPTY);
    return result;
  }

  // 4-3 (닫힌4 + 열린3) 만드는지 체크
  createsFourThree(board, x, y, stone) {
    board.set(x, y, stone);

    let hasFour = false;
    let hasOpenThree = false;

    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
      if (count >= 4) hasFour = true;
      else if (count === 3 && openEnds === 2) hasOpenThree = true;
    }

    board.set(x, y, EMPTY);
    return hasFour && hasOpenThree;
  }

  // 3-3 (쌍삼) 만드는지 체크
  createsDoubleThree(board, x, y, stone) {
    board.set(x, y, stone);

    let openThreeCount = 0;
    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
      if (count === 3 && openEnds === 2) openThreeCount++;
    }

    board.set(x, y, EMPTY);
    return openThreeCount >= 2;
  }

  // 열린3을 만드는지 체크
  createsOpenThree(board, x, y, stone) {
    board.set(x, y, stone);
    let result = false;

    for (const [dx, dy] of DIRECTIONS) {
      const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
      if (count === 3 && openEnds === 2) {
        result = true;
        break;
      }
    }

    board.set(x, y, EMPTY);
    return result;
  }

  // 상대의 점프4(띈4)를 막을 수 있는 위치 찾기
  // 패턴: X.XXX, XX.XX, XXX.X (빈칸 채우면 4가 됨)
  findJumpFourBlockMoves(board, targetStone) {
    const blockMoves = [];
    const checked = new Set();

    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (board.get(x, y) !== targetStone) continue;

        for (const [dx, dy] of DIRECTIONS) {
          const key = `${x},${y},${dx},${dy}`;
          if (checked.has(key)) continue;
          checked.add(key);

          // 이 방향으로 점프4 패턴 찾기
          const jumpFourPos = this.findJumpFourInLine(board, x, y, dx, dy, targetStone);
          if (jumpFourPos) {
            if (!blockMoves.some(m => m.x === jumpFourPos.x && m.y === jumpFourPos.y)) {
              blockMoves.push(jumpFourPos);
            }
          }
        }
      }
    }

    return blockMoves;
  }

  // 특정 라인에서 점프4 패턴의 빈칸 위치 찾기
  findJumpFourInLine(board, x, y, dx, dy, stone) {
    const lineStr = this.getLineString(board, x, y, dx, dy, 6);
    const center = 6; // 중앙 인덱스

    // 점프4 패턴들 (. = 빈칸, X = 돌)
    const patterns = [
      { regex: new RegExp(`${stone}\\.${stone}${stone}${stone}`), gapOffset: 1 },  // X.XXX
      { regex: new RegExp(`${stone}${stone}\\.${stone}${stone}`), gapOffset: 2 },  // XX.XX
      { regex: new RegExp(`${stone}${stone}${stone}\\.${stone}`), gapOffset: 3 },  // XXX.X
    ];

    for (const { regex, gapOffset } of patterns) {
      let match;
      const tempStr = lineStr;
      let searchStart = 0;

      while ((match = regex.exec(tempStr.slice(searchStart))) !== null) {
        const matchStart = searchStart + match.index;
        const gapIdx = matchStart + gapOffset;

        // 빈칸 위치 계산
        const offset = gapIdx - center;
        const gapX = x + offset * dx;
        const gapY = y + offset * dy;

        if (board.inBounds(gapX, gapY) && board.isEmpty(gapX, gapY)) {
          return { x: gapX, y: gapY };
        }

        searchStart = matchStart + 1;
      }
    }

    return null;
  }

  // 상대의 열린3을 막을 수 있는 위치 찾기
  findOpenThreeBlockMoves(board, targetStone) {
    const blockMoves = [];

    // 보드에서 열린3 패턴 찾기
    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        if (board.get(x, y) !== targetStone) continue;

        for (const [dx, dy] of DIRECTIONS) {
          // 이 방향으로 열린3이 있는지 확인
          const lineInfo = this.analyzeLineForBlock(board, x, y, dx, dy, targetStone);
          if (lineInfo && lineInfo.isOpenThree) {
            // 막을 수 있는 위치들 추가
            for (const pos of lineInfo.blockPositions) {
              const key = `${pos.x},${pos.y}`;
              if (!blockMoves.some(m => m.x === pos.x && m.y === pos.y)) {
                blockMoves.push({ x: pos.x, y: pos.y, threat: lineInfo.threat });
              }
            }
          }
        }
      }
    }

    // 위협도 순으로 정렬
    return blockMoves.sort((a, b) => b.threat - a.threat);
  }

  // 라인을 분석해서 열린3인지, 어디를 막아야 하는지 확인
  analyzeLineForBlock(board, x, y, dx, dy, stone) {
    // 연속된 돌 찾기
    let stones = [{ x, y }];

    // + 방향
    let nx = x + dx, ny = y + dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      stones.push({ x: nx, y: ny });
      nx += dx;
      ny += dy;
    }
    const afterStones = { x: nx, y: ny, empty: board.inBounds(nx, ny) && board.isEmpty(nx, ny) };

    // - 방향
    nx = x - dx;
    ny = y - dy;
    while (board.inBounds(nx, ny) && board.get(nx, ny) === stone) {
      stones.unshift({ x: nx, y: ny });
      nx -= dx;
      ny -= dy;
    }
    const beforeStones = { x: nx, y: ny, empty: board.inBounds(nx, ny) && board.isEmpty(nx, ny) };

    // 정확히 3개이고 양쪽이 빈 칸인지 (열린3)
    if (stones.length === 3 && beforeStones.empty && afterStones.empty) {
      const blockPositions = [];

      // 양쪽 끝을 막으면 됨
      blockPositions.push({ x: beforeStones.x, y: beforeStones.y });
      blockPositions.push({ x: afterStones.x, y: afterStones.y });

      // 한 칸 더 바깥도 체크 (4가 되는 걸 막기 위해)
      const farBefore = { x: beforeStones.x - dx, y: beforeStones.y - dy };
      const farAfter = { x: afterStones.x + dx, y: afterStones.y + dy };

      if (board.inBounds(farBefore.x, farBefore.y) && board.isEmpty(farBefore.x, farBefore.y)) {
        blockPositions.push(farBefore);
      }
      if (board.inBounds(farAfter.x, farAfter.y) && board.isEmpty(farAfter.x, farAfter.y)) {
        blockPositions.push(farAfter);
      }

      return {
        isOpenThree: true,
        blockPositions,
        threat: this.SCORES.OPEN_THREE
      };
    }

    // 점프3 패턴도 체크 (.X.XX. 또는 .XX.X.)
    // 더 넓은 범위에서 패턴 확인
    const lineStr = this.getLineString(board, x, y, dx, dy, 6);
    const jumpPatterns = [
      { pattern: `.${stone}.${stone}${stone}.`, blockIdx: [0, 2, 5] },
      { pattern: `.${stone}${stone}.${stone}.`, blockIdx: [0, 3, 5] }
    ];

    for (const { pattern, blockIdx } of jumpPatterns) {
      const idx = lineStr.indexOf(pattern);
      if (idx !== -1) {
        const blockPositions = blockIdx.map(i => {
          const offset = idx + i - 6; // 중앙이 6번째
          return {
            x: x + offset * dx,
            y: y + offset * dy
          };
        }).filter(pos => board.inBounds(pos.x, pos.y) && board.isEmpty(pos.x, pos.y));

        if (blockPositions.length > 0) {
          return {
            isOpenThree: true,
            blockPositions,
            threat: this.SCORES.JUMP_THREE
          };
        }
      }
    }

    return null;
  }

  // 라인을 문자열로 추출
  getLineString(board, x, y, dx, dy, range) {
    let str = '';
    for (let i = -range; i <= range; i++) {
      const nx = x + i * dx;
      const ny = y + i * dy;
      if (board.inBounds(nx, ny)) {
        str += board.get(nx, ny);
      } else {
        str += 'X';
      }
    }
    return str;
  }

  // Minimax with Alpha-Beta Pruning
  minimax(board, depth, alpha, beta, isMaximizing, aiStone) {
    this.nodeCount++;

    // 시간 초과 체크
    if (this.nodeCount % 1000 === 0) {
      if (Date.now() - this.startTime > this.timeLimit) {
        this.timeOut = true;
        return this.evaluate(board, aiStone);
      }
    }
    if (this.timeOut) {
      return this.evaluate(board, aiStone);
    }

    // 터미널 체크
    if (board.lastMove) {
      const { x, y, stone } = board.lastMove;
      if (OmokRules.checkWin(board, x, y, stone)) {
        return stone === aiStone ? this.SCORES.FIVE + depth : -this.SCORES.FIVE - depth;
      }
    }

    if (depth === 0) {
      return this.evaluate(board, aiStone);
    }

    const currentStone = isMaximizing ? aiStone : this.opponent(aiStone);
    const oppStone = this.opponent(currentStone);

    // 후보 수 정렬 및 제한
    let candidates = board.getCandidateMoves(2)
      .filter(({ x, y }) => OmokRules.isValidMove(board, x, y, currentStone))
      .map(({ x, y }) => ({
        x, y,
        priority: this.getMoveUrgency(board, x, y, currentStone, oppStone)
      }))
      .sort((a, b) => b.priority - a.priority)
      .slice(0, Math.max(12, this.candidateLimit - depth));

    if (candidates.length === 0) {
      return this.evaluate(board, aiStone);
    }

    if (isMaximizing) {
      let maxEval = -Infinity;
      for (const { x, y } of candidates) {
        const testBoard = board.clone();
        testBoard.set(x, y, currentStone);
        const evalScore = this.minimax(testBoard, depth - 1, alpha, beta, false, aiStone);
        maxEval = Math.max(maxEval, evalScore);
        alpha = Math.max(alpha, evalScore);
        if (beta <= alpha) break;
      }
      return maxEval;
    } else {
      let minEval = Infinity;
      for (const { x, y } of candidates) {
        const testBoard = board.clone();
        testBoard.set(x, y, currentStone);
        const evalScore = this.minimax(testBoard, depth - 1, alpha, beta, true, aiStone);
        minEval = Math.min(minEval, evalScore);
        beta = Math.min(beta, evalScore);
        if (beta <= alpha) break;
      }
      return minEval;
    }
  }

  // 보드 전체 평가 함수 (프로 레벨)
  evaluate(board, aiStone) {
    const oppStone = this.opponent(aiStone);
    let aiScore = 0;
    let oppScore = 0;

    // 위협 카운트
    let aiOpenThrees = 0, aiClosedFours = 0;
    let oppOpenThrees = 0, oppClosedFours = 0;

    // 모든 위치 패턴 평가
    const evaluated = new Set();

    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        const stone = board.get(x, y);
        if (stone === EMPTY) continue;

        for (const [dx, dy] of DIRECTIONS) {
          // 정방향만 체크 (중복 방지)
          if (dx < 0 || (dx === 0 && dy < 0)) continue;

          // 이미 평가된 라인 스킵
          const key = `${x},${y},${dx},${dy}`;
          if (evaluated.has(key)) continue;
          evaluated.add(key);

          const { count, openEnds } = this.countLine(board, x, y, dx, dy, stone);
          const patternScore = this.getPatternScore(count, openEnds);

          // 점프 패턴 추가 점수
          const jumpScore = this.countJumpPattern(board, x, y, dx, dy, stone);

          if (stone === aiStone) {
            aiScore += patternScore + jumpScore;
            if (count === 3 && openEnds === 2) aiOpenThrees++;
            if (count === 4) aiClosedFours++;
          } else {
            oppScore += patternScore + jumpScore;
            if (count === 3 && openEnds === 2) oppOpenThrees++;
            if (count === 4) oppClosedFours++;
          }
        }
      }
    }

    // 복합 위협 보너스
    if (aiOpenThrees >= 2) aiScore += this.SCORES.DOUBLE_THREE;
    if (aiClosedFours >= 2) aiScore += this.SCORES.DOUBLE_FOUR;
    if (aiClosedFours >= 1 && aiOpenThrees >= 1) aiScore += this.SCORES.FOUR_THREE;

    if (oppOpenThrees >= 2) oppScore += this.SCORES.DOUBLE_THREE;
    if (oppClosedFours >= 2) oppScore += this.SCORES.DOUBLE_FOUR;
    if (oppClosedFours >= 1 && oppOpenThrees >= 1) oppScore += this.SCORES.FOUR_THREE;

    // 상대 점수에 가중치 (난이도별 방어 중요도)
    const defenseWeight = this.skipDefense ? 0.5 : 1.5;
    return aiScore - oppScore * defenseWeight;
  }

  // 패턴별 점수
  getPatternScore(count, openEnds) {
    if (count >= 5) return this.SCORES.FIVE;

    if (count === 4) {
      return openEnds === 2 ? this.SCORES.OPEN_FOUR :
             openEnds === 1 ? this.SCORES.CLOSED_FOUR : 100;
    }
    if (count === 3) {
      return openEnds === 2 ? this.SCORES.OPEN_THREE :
             openEnds === 1 ? this.SCORES.CLOSED_THREE : 20;
    }
    if (count === 2) {
      return openEnds === 2 ? this.SCORES.OPEN_TWO :
             openEnds === 1 ? this.SCORES.CLOSED_TWO : 3;
    }
    return this.SCORES.ONE;
  }
}

// ========================================
// 게임 컨트롤러 (AI 모드용)
// ========================================
class AIGameController {
  constructor(playerColor, difficulty) {
    this.board = new OmokBoard();
    this.playerColor = playerColor;
    this.aiColor = playerColor === BLACK ? WHITE : BLACK;
    this.ai = new OmokAI(difficulty);
    this.currentTurn = BLACK; // 항상 흑이 선공
    this.gameOver = false;
    this.winner = null;
    this.moveHistory = [];
  }

  // 현재 턴이 플레이어인지
  isPlayerTurn() {
    return this.currentTurn === this.playerColor;
  }

  // 플레이어 착수
  playerMove(x, y) {
    if (this.gameOver) return { success: false, message: "게임 종료" };
    if (!this.isPlayerTurn()) return { success: false, message: "AI 턴입니다" };
    if (!OmokRules.isValidMove(this.board, x, y, this.playerColor)) {
      return { success: false, message: "금수입니다" };
    }

    this.board.set(x, y, this.playerColor);
    this.moveHistory.push({ x, y, stone: this.playerColor });

    if (OmokRules.checkWin(this.board, x, y, this.playerColor)) {
      this.gameOver = true;
      this.winner = this.playerColor;
      return { success: true, win: true };
    }

    this.currentTurn = this.aiColor;
    return { success: true };
  }

  // AI 착수
  aiMove() {
    if (this.gameOver) return null;
    if (this.isPlayerTurn()) return null;

    const move = this.ai.findBestMove(this.board, this.aiColor);
    if (!move) return null;

    this.board.set(move.x, move.y, this.aiColor);
    this.moveHistory.push({ x: move.x, y: move.y, stone: this.aiColor });

    if (OmokRules.checkWin(this.board, move.x, move.y, this.aiColor)) {
      this.gameOver = true;
      this.winner = this.aiColor;
      return { ...move, win: true };
    }

    this.currentTurn = this.playerColor;
    return move;
  }

  // 게임 리셋
  reset() {
    this.board = new OmokBoard();
    this.currentTurn = BLACK;
    this.gameOver = false;
    this.winner = null;
    this.moveHistory = [];
  }

  // 보드 문자열 반환
  getBoardString() {
    return this.board.board;
  }

  // 마지막 수 반환
  getLastMove() {
    return this.moveHistory.length > 0
      ? this.moveHistory[this.moveHistory.length - 1]
      : null;
  }
}

// 전역 내보내기
window.OmokBoard = OmokBoard;
window.OmokRules = OmokRules;
window.OmokAI = OmokAI;
window.AIGameController = AIGameController;
window.EMPTY = EMPTY;
window.BLACK = BLACK;
window.WHITE = WHITE;