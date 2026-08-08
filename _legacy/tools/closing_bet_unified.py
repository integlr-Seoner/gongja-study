# -*- coding: utf-8 -*-
"""
Closing Bet Unified System v1.0
종가배팅 통합 시스템 (완전 신규)

[전자책 기반 핵심 전략]
- 드리블 분할매수 (30-30-20-20)
- 트랩 감지 → 자동 대응
- 스마트머니 확인
- 분할 익절 (30-30-나머지)
- 상황별 대응 ("매매는 결국 대응이다")

[모듈 구성]
1. UnifiedScanner      → 종목 스캔
2. UnifiedAnalyzer     → ABCD + 드리블 + 트랩 통합
3. UnifiedExecutor     → 분할 매수/매도 실행
4. PositionManager     → 포지션 관리
5. SituationHandler    → 상황별 대응

[참조]
- 미라클: p.74, p.76, p.79
- 와디즈: p.1216~1278
"""

import os
import sys
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

# 로컬 모듈
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 휴장일 대응
from market_utils import get_last_business_day, is_holiday

from dribble_entry import (
    DribbleEntryDetector, DribbleSignal, DribblePhase,
    ZoneStatus, ExitPhase, DribbleConfig
)
from trap_detector import (
    TrapDetector, TrapSignal, TrapType, TrapAction,
    SupportStatus, MABreakStatus, TrapConfig
)

# pykrx
try:
    from krx_data import get_client as _krx_client
    PYKRX_ENABLED = True
except ImportError:
    PYKRX_ENABLED = False
    print("[WARN] pykrx not available")

# 증권사 API (키움)
try:
    from pykiwoom.kiwoom import Kiwoom
    KIWOOM_ENABLED = True
except ImportError:
    KIWOOM_ENABLED = False

# 순위 필터
try:
    from screener.ranking_filter import RankingFilter, filter_by_ranking
    RANKING_FILTER_ENABLED = True
except ImportError:
    RANKING_FILTER_ENABLED = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# DB 경로
DB_PATH = os.path.join(BASE_DIR, "closing_bet_unified.db")


# =============================================================================
# Enums & DataClasses
# =============================================================================

class ActionType(Enum):
    """행동 유형"""
    # 매수
    BUY_PHASE1 = "Buy_P1"          # C구간 1파 (30%)
    BUY_PHASE2 = "Buy_P2"          # C구간 2파 (30%)
    BUY_PHASE3 = "Buy_P3"          # C구간 3파 (20%)
    BUY_D_ADD = "Buy_D"            # D구간 추가 (20%)
    BUY_CLOSING = "Buy_Closing"    # 종가 배팅
    
    # 매도
    SELL_PHASE1 = "Sell_P1"        # 1차 익절 (30%)
    SELL_PHASE2 = "Sell_P2"        # 2차 익절 (30%)
    SELL_PHASE3 = "Sell_P3"        # 3차 익절 (나머지)
    SELL_FULL = "Sell_Full"        # 전량 매도
    STOP_LOSS = "Stop_Loss"        # 손절
    REDUCE = "Reduce"              # 비중 축소
    
    # 대기/홀딩
    HOLD = "Hold"                  # 홀딩
    WAIT = "Wait"                  # 대기
    AVOID = "Avoid"                # 회피
    
    # 재진입
    REENTRY = "Reentry"            # 재진입


class MarketPhase(Enum):
    """장 시간대"""
    PRE_MARKET = "Pre"             # 장전 (09:00 이전)
    MORNING = "Morning"            # 오전 (09:00~12:00)
    AFTERNOON = "Afternoon"        # 오후 (12:00~14:30)
    CLOSING_ZONE = "Closing"       # 종가 시간대 (14:30~15:20)
    CLOSING_BET = "ClosingBet"     # 종가 배팅 (15:10~15:20)
    AFTER_MARKET = "After"         # 장후


@dataclass
class Position:
    """포지션 정보"""
    code: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    position_pct: float            # 총 자산 대비 비중
    
    # ABCD 정보
    a_price: float = 0
    b_price: float = 0
    c_price: float = 0
    stop_loss: float = 0
    target_1: float = 0
    target_2: float = 0
    target_3: float = 0
    
    # 매수 단계
    buy_phase: int = 0             # 1, 2, 3, 4 (D추가)
    
    # 익절 단계
    exit_phase: int = 0            # 0=없음, 1, 2, 3
    
    # 상태
    entry_date: str = ""
    last_action: str = ""
    last_action_date: str = ""
    
    @property
    def profit_pct(self) -> float:
        """수익률"""
        if self.avg_price <= 0:
            return 0
        return ((self.current_price - self.avg_price) / self.avg_price) * 100
    
    @property
    def profit_amount(self) -> int:
        """평가손익"""
        return int((self.current_price - self.avg_price) * self.quantity)


@dataclass
class ScanResult:
    """스캔 결과"""
    code: str
    name: str
    price: int
    
    # 패턴
    pattern_detected: bool
    pattern_quality: float
    zone: str
    
    # 분석 결과
    action: ActionType
    allocation_pct: float
    confidence: float
    
    # 가격 레벨
    a_price: float
    b_price: float
    c_price: float
    stop_loss: float
    stop_loss_reason: str
    target_1: float
    target_2: float
    target_3: float
    
    # 조건
    support_confirmed: bool
    smart_money_detected: bool
    volume_surge: bool
    ma_aligned: bool
    
    # 트랩
    trap_type: str
    trap_severity: float
    trap_action: str
    
    # 상황
    scenario: str
    reason: str
    
    # 다음날 체크
    need_next_day_check: bool = False
    next_day_guide: str = ""


@dataclass
class OrderResult:
    """주문 결과"""
    success: bool
    code: str
    order_type: str               # "buy" or "sell"
    quantity: int
    price: int
    order_no: str = ""
    message: str = ""
    timestamp: str = ""


@dataclass
class UnifiedConfig:
    """통합 설정"""
    # 자본금
    total_capital: int = 10_000_000
    max_position_pct: float = 20.0     # 종목당 최대 비중
    max_positions: int = 5              # 최대 보유 종목 수
    
    # 드리블 비중
    phase1_pct: float = 30.0
    phase2_pct: float = 30.0
    phase3_pct: float = 20.0
    phase_d_pct: float = 20.0
    
    # 익절 비중
    exit1_pct: float = 30.0
    exit2_pct: float = 30.0
    exit3_pct: float = 100.0           # 나머지 전량
    
    # 스캔 조건
    min_price: int = 1000
    max_price: int = 100000
    min_volume: int = 100000
    min_market_cap: int = 100_000_000_000  # 1000억
    
    # 시간 설정
    closing_bet_start: time = time(15, 10)
    closing_bet_end: time = time(15, 20)
    
    # 시뮬레이션 모드
    simulation_mode: bool = True
    
    # 순위 필터
    use_ranking_filter: bool = False
    ranking_top_n: int = 10
    
    # 로깅
    verbose: bool = True


# =============================================================================
# UnifiedScanner - 종목 스캔
# =============================================================================

class UnifiedScanner:
    """종목 스캐너"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        # 직전영업일 기준 (휴장일 대응)
        self.today = get_last_business_day()
        self.start_date = (datetime.strptime(self.today, "%Y%m%d") - timedelta(days=180)).strftime("%Y%m%d")
    
    def scan_market(self, market: str = "ALL") -> Dict[str, str]:
        """
        시장 전체 스캔
        
        Args:
            market: "KOSPI", "KOSDAQ", "ALL"
        
        Returns:
            {code: name} 딕셔너리
        """
        targets = {}
        
        # pykrx 시도
        if PYKRX_ENABLED:
            try:
                if market in ["KOSPI", "ALL"]:
                    kospi = _krx_client().get_market_ticker_list(self.today, market="KOSPI")
                    for code in kospi:
                        targets[code] = _krx_client().get_market_ticker_name(code)
                
                if market in ["KOSDAQ", "ALL"]:
                    kosdaq = _krx_client().get_market_ticker_list(self.today, market="KOSDAQ")
                    for code in kosdaq:
                        targets[code] = _krx_client().get_market_ticker_name(code)
                
                logger.info(f"[Scanner] Found {len(targets)} tickers in {market}")
                
            except Exception as e:
                logger.warning(f"[Scanner] pykrx failed: {e}")
        
        # pykrx 실패시 DB fallback
        if not targets:
            logger.info("[Scanner] DB fallback - screener 종목 사용")
            conn = None
            try:
                import sqlite3
                db_path = os.path.join(BASE_DIR, "trading_system.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT code, name FROM scanned_targets_v2 
                    WHERE date = (SELECT MAX(date) FROM scanned_targets_v2)
                    ORDER BY volume DESC LIMIT 100
                """)
                for row in cursor.fetchall():
                    targets[row[0]] = row[1]
                logger.info(f"[Scanner] DB fallback: {len(targets)} tickers")
            except Exception as e2:
                logger.error(f"[Scanner] DB fallback failed: {e2}")
        
            finally:
                if conn:
                    conn.close()
        return targets
    
    def filter_candidates(self, targets: Dict[str, str]) -> Dict[str, str]:
        """
        기본 필터링 (가격, 거래량, 시총)
        최적화: 배치 API로 전체 시장 한 번에 조회 (개별 호출 제거)
        """
        filtered = {}
        cfg = self.config
        
        # 배치 조회: 전체 시장 OHLCV 한 번에 가져오기
        try:
            market_data = {}
            for market in ["KOSPI", "KOSDAQ"]:
                df = _krx_client().get_market_ohlcv(self.today, market)
                if df is not None and not df.empty:
                    for code in df.index:
                        market_data[code] = {
                            'price': df.loc[code, '종가'] if '종가' in df.columns else 0,
                            'volume': df.loc[code, '거래량'] if '거래량' in df.columns else 0
                        }
            logger.info(f"[Scanner] 배치 조회 완료: {len(market_data)}개 종목")
        except Exception as e:
            logger.warning(f"[Scanner] 배치 조회 실패: {e}, 개별 조회로 fallback")
            market_data = {}
        
        for code, name in targets.items():
            try:
                # 우선주, 스팩 제외
                if not code.endswith('0'):
                    continue
                if '스팩' in name or 'SPAC' in name:
                    continue
                
                # 배치 데이터에서 조회 (빠름)
                if code in market_data:
                    price = market_data[code]['price']
                    volume = market_data[code]['volume']
                else:
                    # fallback: 개별 조회 (느림)
                    df = _krx_client().get_market_ohlcv_by_date(
                        (datetime.strptime(self.today, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d"),
                        self.today, code
                    )
                    if df.empty:
                        continue
                    price = df['종가'].iloc[-1]
                    volume = df['거래량'].iloc[-1]
                
                # 가격 필터
                if price < cfg.min_price or price > cfg.max_price:
                    continue
                
                # 거래량 필터
                if volume < cfg.min_volume:
                    continue
                
                filtered[code] = name
                
            except Exception as e:
                continue
        
        # 순위 필터 적용 (거래대금 상위 N개만)
        if self.config.use_ranking_filter and RANKING_FILTER_ENABLED:
            filtered_list = [(code, name) for code, name in filtered.items()]
            filtered_list = filter_by_ranking(filtered_list, top_n=self.config.ranking_top_n)
            filtered = {code: name for code, name in filtered_list}
            logger.info(f"[Scanner] After ranking filter: {len(filtered)} candidates")
        
        logger.info(f"[Scanner] Filtered: {len(filtered)} candidates")
        return filtered
    
    def get_ohlcv(self, code: str, days: int = 180) -> Optional[Dict]:
        """OHLCV 데이터 조회 (직전영업일 기준)"""
        try:
            start = (datetime.strptime(self.today, "%Y%m%d") - timedelta(days=days)).strftime("%Y%m%d")
            df = _krx_client().get_market_ohlcv_by_date(start, self.today, code)
            
            if df.empty or len(df) < 60:
                return None
            
            return {
                'open': df['시가'].tolist(),
                'high': df['고가'].tolist(),
                'low': df['저가'].tolist(),
                'close': df['종가'].tolist(),
                'volume': df['거래량'].tolist(),
                'dates': df.index.strftime('%Y%m%d').tolist()
            }
        except Exception as e:
            logger.debug(f"[Scanner] OHLCV failed for {code}: {e}")
            return None


# =============================================================================
# UnifiedAnalyzer - 통합 분석
# =============================================================================

class UnifiedAnalyzer:
    """통합 분석기"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.dribble_detector = DribbleEntryDetector()
        self.trap_detector = TrapDetector()
    
    def analyze(self, 
                code: str, 
                name: str, 
                ohlcv: Dict,
                position: Optional[Position] = None,
                current_time: datetime = None) -> Optional[ScanResult]:
        """
        종목 분석
        
        Args:
            code: 종목코드
            name: 종목명
            ohlcv: OHLCV 데이터
            position: 기존 포지션 (있으면)
            current_time: 현재 시간
        """
        current_time = current_time or datetime.now()
        close = np.array(ohlcv['close'], dtype=float)
        current_price = int(close[-1])
        
        # 현재 포지션 비중
        position_pct = position.position_pct if position else 0.0
        
        # 1. ABCD 패턴 감지
        pattern = self._detect_abcd_pattern(ohlcv)
        if not pattern:
            return None
        
        a_price = pattern['a_price']
        b_price = pattern['b_price']
        c_price = pattern['c_price']
        
        # 2. 드리블 분석
        dribble = self.dribble_detector.analyze(
            ohlcv, pattern, position_pct, current_time
        )
        
        # 3. 트랩 분석
        trap = self.trap_detector.analyze(
            ohlcv,
            support_price=c_price,
            resistance_price=b_price,
            current_time=current_time
        )
        
        # 4. 최종 행동 결정
        action, allocation, scenario = self._decide_action(
            dribble, trap, position_pct, position, current_time
        )
        
        # 5. 신뢰도 계산
        confidence = self._calculate_confidence(dribble, trap)
        
        # 6. 이유 생성
        reason = self._generate_reason(action, dribble, trap, scenario)
        
        return ScanResult(
            code=code,
            name=name,
            price=current_price,
            pattern_detected=True,
            pattern_quality=pattern.get('quality', 50),
            zone=dribble.zone.value if dribble else "Unknown",
            action=action,
            allocation_pct=allocation,
            confidence=confidence,
            a_price=a_price,
            b_price=b_price,
            c_price=c_price,
            stop_loss=dribble.stop_loss if dribble else 0,
            stop_loss_reason=dribble.stop_loss_reason if dribble else "",
            target_1=dribble.target_1 if dribble else 0,
            target_2=dribble.target_2 if dribble else 0,
            target_3=dribble.target_3 if dribble else 0,
            support_confirmed=dribble.support_confirmed if dribble else False,
            smart_money_detected=dribble.smart_money_detected if dribble else False,
            volume_surge=dribble.volume_increasing if dribble else False,
            ma_aligned=trap.ma_aligned if trap else False,
            trap_type=trap.trap_type.value if trap else "None",
            trap_severity=trap.severity if trap else 0,
            trap_action=trap.action.value if trap else "None",
            scenario=scenario,
            reason=reason,
            need_next_day_check=trap.need_next_day_check if trap else False,
            next_day_guide=trap.next_day_action if trap else ""
        )
    
    def _detect_abcd_pattern(self, ohlcv: Dict) -> Optional[Dict]:
        """ABCD 패턴 감지"""
        close = np.array(ohlcv['close'], dtype=float)
        high = np.array(ohlcv['high'], dtype=float)
        low = np.array(ohlcv['low'], dtype=float)
        
        n = len(close)
        if n < 30:
            return None
        
        # 최근 60일 분석
        lookback = min(60, n)
        
        # A: 시작 저점 (lookback 기간 내 저점)
        a_idx = n - lookback + np.argmin(low[-lookback:])
        a_price = low[a_idx]
        
        # B: A 이후 고점
        if a_idx >= n - 5:
            return None
        
        b_idx = a_idx + np.argmax(high[a_idx:])
        b_price = high[b_idx]
        
        # 유효성: 가격 > 0
        if a_price <= 0 or b_price <= 0:
            return None
        
        # 유효성: A→B 상승 필요
        ab_rise = (b_price - a_price) / a_price * 100
        if ab_rise < 5:  # 최소 5% 상승
            return None
        
        # C: B 이후 저점
        if b_idx >= n - 3:
            c_idx = n - 1
            c_price = low[-1]
        else:
            c_idx = b_idx + np.argmin(low[b_idx:])
            c_price = low[c_idx]
        
        # 유효성: C > A (더 높은 저점)
        if c_price <= a_price:
            return None
        
        # 유효성: B→C 조정 (최소 38.2%)
        bc_retrace = (b_price - c_price) / (b_price - a_price) * 100
        if bc_retrace < 30 or bc_retrace > 90:
            return None
        
        # 품질 점수
        quality = 50
        if 38 <= bc_retrace <= 62:  # 피보나치 구간
            quality += 20
        if ab_rise >= 10:
            quality += 15
        if c_idx > b_idx + 3:  # 충분한 조정 기간
            quality += 15
        
        return {
            'a_price': a_price,
            'b_price': b_price,
            'c_price': c_price,
            'a_idx': a_idx,
            'b_idx': b_idx,
            'c_idx': c_idx,
            'ab_rise': ab_rise,
            'bc_retrace': bc_retrace,
            'quality': min(100, quality)
        }
    
    def _decide_action(self,
                       dribble: Optional[DribbleSignal],
                       trap: Optional[TrapSignal],
                       position_pct: float,
                       position: Optional[Position],
                       current_time: datetime) -> Tuple[ActionType, float, str]:
        """최종 행동 결정"""
        
        cfg = self.config
        market_phase = self._get_market_phase(current_time)
        
        # ========================================
        # 1. 위험/트랩 상황 (최우선)
        # ========================================
        if trap:
            # 지지 이탈 → 손절/회피
            if trap.support_status == SupportStatus.BROKEN:
                if position_pct > 0:
                    return ActionType.STOP_LOSS, position_pct, "지지이탈→손절"
                return ActionType.AVOID, 0, "지지이탈→진입금지"
            
            # 이평선 돌파 실패 → 손절
            if trap.ma_status == MABreakStatus.BREAK_FAILED and position_pct > 0:
                return ActionType.STOP_LOSS, position_pct, "이평선실패→손절"
            
            # 종가 트랩
            if trap.trap_type == TrapType.CLOSING_TRAP:
                if trap.action == TrapAction.REDUCE and position_pct > 0:
                    return ActionType.REDUCE, position_pct * 0.5, "종가트랩→축소"
                if trap.action == TrapAction.WAIT_REENTRY:
                    return ActionType.WAIT, 0, "트랩→대기"
            
            # 쉐이크아웃 회복 → 재진입
            if trap.trap_type == TrapType.SHAKEOUT and trap.action == TrapAction.REENTRY:
                return ActionType.REENTRY, cfg.phase1_pct, "쉐이크아웃회복→재진입"
        
        # ========================================
        # 2. B구간 진입 자제
        # ========================================
        if dribble and dribble.zone == ZoneStatus.B_ZONE:
            return ActionType.WAIT, 0, "B구간→진입자제"
        
        # ========================================
        # 3. 익절 (포지션 있을 때)
        # ========================================
        if dribble and position_pct > 0:
            if dribble.exit_phase == ExitPhase.PHASE1:
                return ActionType.SELL_PHASE1, cfg.exit1_pct, "1차목표→30%익절"
            if dribble.exit_phase == ExitPhase.PHASE2:
                return ActionType.SELL_PHASE2, cfg.exit2_pct, "2차목표→30%익절"
            if dribble.exit_phase == ExitPhase.PHASE3:
                return ActionType.SELL_PHASE3, cfg.exit3_pct, "3차목표→나머지익절"
            
            # D 이상 부분 익절
            if dribble.zone == ZoneStatus.ABOVE_D:
                exit_pct = position_pct * 0.3
                return ActionType.SELL_PHASE1, exit_pct, "D이상→부분익절"
        
        # ========================================
        # 4. 드리블 매수
        # ========================================
        if dribble:
            # 지지 미확인
            if not dribble.support_confirmed and dribble.zone == ZoneStatus.C_ZONE:
                return ActionType.WAIT, 0, "지지미확인→대기"
            
            # C구간 1파
            if dribble.phase == DribblePhase.C_ZONE_PHASE1:
                return ActionType.BUY_PHASE1, cfg.phase1_pct, "C구간1파"
            
            # C구간 2파
            if dribble.phase == DribblePhase.C_ZONE_PHASE2:
                return ActionType.BUY_PHASE2, cfg.phase2_pct, "C구간2파"
            
            # C구간 3파 (스마트머니)
            if dribble.phase == DribblePhase.C_ZONE_PHASE3:
                if dribble.smart_money_detected:
                    return ActionType.BUY_PHASE3, cfg.phase3_pct, "C구간3파+SM"
                return ActionType.WAIT, 0, "스마트머니대기"
            
            # D구간 추가 (정배열)
            if dribble.phase == DribblePhase.D_ZONE_ADD:
                if trap and trap.ma_aligned:
                    return ActionType.BUY_D_ADD, cfg.phase_d_pct, "D구간추가"
                return ActionType.WAIT, 0, "정배열대기"
            
            # 종가 배팅 (15:10 이후)
            if (market_phase == MarketPhase.CLOSING_BET and 
                trap and trap.ma_aligned and 
                dribble.support_confirmed):
                return ActionType.BUY_CLOSING, cfg.phase1_pct, "종가배팅"
        
        # ========================================
        # 5. 기본
        # ========================================
        if position_pct > 0:
            return ActionType.HOLD, 0, "홀딩"
        
        return ActionType.WAIT, 0, "대기"
    
    def _get_market_phase(self, dt: datetime) -> MarketPhase:
        """장 시간대 판단"""
        t = dt.time()
        
        if t < time(9, 0):
            return MarketPhase.PRE_MARKET
        elif t < time(12, 0):
            return MarketPhase.MORNING
        elif t < time(14, 30):
            return MarketPhase.AFTERNOON
        elif t < time(15, 10):
            return MarketPhase.CLOSING_ZONE
        elif t < time(15, 20):
            return MarketPhase.CLOSING_BET
        else:
            return MarketPhase.AFTER_MARKET
    
    def _calculate_confidence(self,
                              dribble: Optional[DribbleSignal],
                              trap: Optional[TrapSignal]) -> float:
        """신뢰도 계산"""
        score = 50
        
        if dribble:
            score = dribble.confidence * 0.6
            if dribble.support_confirmed:
                score += 10
            if dribble.smart_money_detected:
                score += 10
        
        if trap:
            if trap.severity > 50:
                score -= 20
            elif trap.severity > 30:
                score -= 10
            if trap.ma_aligned:
                score += 10
        
        return max(0, min(100, score))
    
    def _generate_reason(self,
                         action: ActionType,
                         dribble: Optional[DribbleSignal],
                         trap: Optional[TrapSignal],
                         scenario: str) -> str:
        """이유 생성"""
        parts = [f"{action.value}", scenario]
        
        if dribble:
            parts.append(f"Z:{dribble.zone.value[:3]}")
            if dribble.support_confirmed:
                parts.append("Sup+")
            if dribble.smart_money_detected:
                parts.append("SM+")
        
        if trap and trap.trap_type != TrapType.NONE:
            parts.append(f"T:{trap.trap_type.value[:5]}")
        
        return " | ".join(parts)


# =============================================================================
# PositionManager - 포지션 관리
# =============================================================================

class PositionManager:
    """포지션 관리자"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self._init_db()
        self._load_positions()
    
    def _init_db(self):
        """DB 초기화"""
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    quantity INTEGER,
                    avg_price REAL,
                    position_pct REAL,
                    a_price REAL,
                    b_price REAL,
                    c_price REAL,
                    stop_loss REAL,
                    target_1 REAL,
                    target_2 REAL,
                    target_3 REAL,
                    buy_phase INTEGER,
                    exit_phase INTEGER,
                    entry_date TEXT,
                    last_action TEXT,
                    last_action_date TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    code TEXT,
                    name TEXT,
                    action TEXT,
                    quantity INTEGER,
                    price INTEGER,
                    amount INTEGER,
                    position_pct REAL,
                    reason TEXT,
                    scenario TEXT,
                    created_at TEXT
                )
            ''')
        
            conn.commit()
    
        finally:
            conn.close()
    def _load_positions(self):
        """포지션 로드"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT * FROM positions", conn)
            
            for _, row in df.iterrows():
                self.positions[row['code']] = Position(
                    code=row['code'],
                    name=row['name'],
                    quantity=row['quantity'],
                    avg_price=row['avg_price'],
                    current_price=row['avg_price'],  # 나중에 업데이트
                    position_pct=row['position_pct'],
                    a_price=row['a_price'],
                    b_price=row['b_price'],
                    c_price=row['c_price'],
                    stop_loss=row['stop_loss'],
                    target_1=row['target_1'],
                    target_2=row['target_2'],
                    target_3=row['target_3'],
                    buy_phase=row['buy_phase'],
                    exit_phase=row['exit_phase'],
                    entry_date=row['entry_date'],
                    last_action=row['last_action'],
                    last_action_date=row['last_action_date']
                )
            
            logger.info(f"[Position] Loaded {len(self.positions)} positions")
            
        except Exception as e:
            logger.error(f"[Position] Load failed: {e}")
    
        finally:
            if conn:
                conn.close()
    def get_position(self, code: str) -> Optional[Position]:
        """포지션 조회"""
        return self.positions.get(code)
    
    def update_position(self, code: str, name: str, quantity: int, 
                        avg_price: float, scan_result: ScanResult,
                        action: ActionType):
        """포지션 업데이트"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.now().strftime("%Y%m%d")
        
        if quantity <= 0:
            # 포지션 제거
            if code in self.positions:
                del self.positions[code]
                self._delete_from_db(code)
            return
        
        # 비중 계산
        position_pct = (quantity * avg_price) / self.config.total_capital * 100
        
        # 매수 단계 결정
        buy_phase = 0
        if action == ActionType.BUY_PHASE1:
            buy_phase = 1
        elif action == ActionType.BUY_PHASE2:
            buy_phase = 2
        elif action == ActionType.BUY_PHASE3:
            buy_phase = 3
        elif action == ActionType.BUY_D_ADD:
            buy_phase = 4
        
        if code in self.positions:
            pos = self.positions[code]
            pos.quantity = quantity
            pos.avg_price = avg_price
            pos.position_pct = position_pct
            pos.buy_phase = max(pos.buy_phase, buy_phase)
            pos.last_action = action.value
            pos.last_action_date = today
        else:
            self.positions[code] = Position(
                code=code,
                name=name,
                quantity=quantity,
                avg_price=avg_price,
                current_price=scan_result.price,
                position_pct=position_pct,
                a_price=scan_result.a_price,
                b_price=scan_result.b_price,
                c_price=scan_result.c_price,
                stop_loss=scan_result.stop_loss,
                target_1=scan_result.target_1,
                target_2=scan_result.target_2,
                target_3=scan_result.target_3,
                buy_phase=buy_phase,
                entry_date=today,
                last_action=action.value,
                last_action_date=today
            )
        
        self._save_to_db(self.positions[code])
    
    def _save_to_db(self, pos: Position):
        """DB에 저장"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT OR REPLACE INTO positions
                (code, name, quantity, avg_price, position_pct,
                 a_price, b_price, c_price, stop_loss, target_1, target_2, target_3,
                 buy_phase, exit_phase, entry_date, last_action, last_action_date,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pos.code, pos.name, pos.quantity, pos.avg_price, pos.position_pct,
                pos.a_price, pos.b_price, pos.c_price, pos.stop_loss,
                pos.target_1, pos.target_2, pos.target_3,
                pos.buy_phase, pos.exit_phase, pos.entry_date,
                pos.last_action, pos.last_action_date, now, now
            ))
            
            conn.commit()
        except Exception as e:
            logger.error(f"[Position] Save failed: {e}")
    
        finally:
            if conn:
                conn.close()
    def _delete_from_db(self, code: str):
        """DB에서 삭제"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM positions WHERE code = ?", (code,))
            conn.commit()
        except Exception as e:
            logger.error(f"[Position] Delete failed: {e}")
    
        finally:
            if conn:
                conn.close()
    def record_trade(self, code: str, name: str, action: ActionType,
                     quantity: int, price: int, reason: str, scenario: str):
        """거래 기록"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            today = datetime.now().strftime("%Y%m%d")
            amount = quantity * price
            position_pct = amount / self.config.total_capital * 100
            
            cursor.execute('''
                INSERT INTO trade_history
                (date, code, name, action, quantity, price, amount,
                 position_pct, reason, scenario, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, code, name, action.value, quantity, price, amount,
                position_pct, reason, scenario, now
            ))
            
            conn.commit()
            
            # trade_log 동시 기록
            try:
                from trade_recorder import record_trade
                tl_action = 'SELL' if 'SELL' in str(action.value).upper() else 'BUY'
                record_trade(
                    code=code, name=name, action=tl_action,
                    qty=quantity, price=price,
                    strategy='종가배팅', investment_type='종가배팅',
                    date_str=today
                )
            except Exception:
                pass
            
            logger.info(f"[Trade] {action.value} {code} {name} x{quantity} @{price:,}")
            
        except Exception as e:
            logger.error(f"[Trade] Record failed: {e}")
    
        finally:
            if conn:
                conn.close()
    def get_total_position_pct(self) -> float:
        """총 포지션 비중"""
        return sum(p.position_pct for p in self.positions.values())
    
    def get_position_count(self) -> int:
        """보유 종목 수"""
        return len(self.positions)


# =============================================================================
# UnifiedExecutor - 주문 실행
# =============================================================================

class UnifiedExecutor:
    """주문 실행기"""
    
    def __init__(self, config: UnifiedConfig, position_manager: PositionManager):
        self.config = config
        self.pm = position_manager
        self.kiwoom = None
        
        if KIWOOM_ENABLED and not config.simulation_mode:
            try:
                self.kiwoom = Kiwoom()
                self.kiwoom.CommConnect()
                logger.info("[Executor] Kiwoom connected")
            except Exception as e:
                logger.error(f"[Executor] Kiwoom failed: {e}")
    
    def execute(self, scan_result: ScanResult) -> Optional[OrderResult]:
        """주문 실행"""
        action = scan_result.action
        code = scan_result.code
        name = scan_result.name
        price = scan_result.price
        
        # 매수/매도 판단
        if action in [ActionType.BUY_PHASE1, ActionType.BUY_PHASE2,
                      ActionType.BUY_PHASE3, ActionType.BUY_D_ADD,
                      ActionType.BUY_CLOSING, ActionType.REENTRY]:
            return self._execute_buy(scan_result)
        
        elif action in [ActionType.SELL_PHASE1, ActionType.SELL_PHASE2,
                        ActionType.SELL_PHASE3, ActionType.SELL_FULL,
                        ActionType.STOP_LOSS, ActionType.REDUCE]:
            return self._execute_sell(scan_result)
        
        return None
    
    def _execute_buy(self, sr: ScanResult) -> OrderResult:
        """매수 실행"""
        cfg = self.config
        
        # 최대 종목 수 체크
        if self.pm.get_position_count() >= cfg.max_positions:
            if sr.code not in self.pm.positions:
                return OrderResult(
                    success=False,
                    code=sr.code,
                    order_type="buy",
                    quantity=0,
                    price=0,
                    message="최대 보유 종목 수 초과"
                )
        
        # 매수 금액 계산
        buy_amount = int(cfg.total_capital * (sr.allocation_pct / 100))
        
        # 최대 비중 체크
        existing_pos = self.pm.get_position(sr.code)
        existing_pct = existing_pos.position_pct if existing_pos else 0
        
        if existing_pct + sr.allocation_pct > cfg.max_position_pct:
            buy_amount = int(cfg.total_capital * (cfg.max_position_pct - existing_pct) / 100)
        
        if buy_amount < 100000:  # 최소 10만원
            return OrderResult(
                success=False,
                code=sr.code,
                order_type="buy",
                quantity=0,
                price=0,
                message="매수 금액 부족"
            )
        
        # 수량 계산
        quantity = buy_amount // sr.price
        if quantity <= 0:
            return OrderResult(
                success=False,
                code=sr.code,
                order_type="buy",
                quantity=0,
                price=sr.price,
                message="매수 수량 0"
            )
        
        # 시뮬레이션 모드
        if cfg.simulation_mode:
            logger.info(f"[SIM] BUY {sr.code} {sr.name} x{quantity} @{sr.price:,}")
            
            # 포지션 업데이트
            if existing_pos:
                total_qty = existing_pos.quantity + quantity
                total_amount = existing_pos.quantity * existing_pos.avg_price + quantity * sr.price
                avg_price = total_amount / total_qty
            else:
                total_qty = quantity
                avg_price = sr.price
            
            self.pm.update_position(
                sr.code, sr.name, total_qty, avg_price, sr, sr.action
            )
            self.pm.record_trade(
                sr.code, sr.name, sr.action, quantity, sr.price, sr.reason, sr.scenario
            )
            
            return OrderResult(
                success=True,
                code=sr.code,
                order_type="buy",
                quantity=quantity,
                price=sr.price,
                message="[SIM] 매수 완료",
                timestamp=datetime.now().strftime("%H:%M:%S")
            )
        
        # 실제 주문 (키움)
        if self.kiwoom:
            try:
                # ★ Phase 7-3: auto_trader._pending_executions에 등록 (외부주문 오분류 방지)
                try:
                    from auto_trader import get_auto_trader
                    _trader = get_auto_trader()
                    if _trader and hasattr(_trader, '_pending_executions'):
                        _trader._pending_executions[sr.code] = {
                            'action': 'BUY',
                            'code': sr.code,
                            'name': sr.name,
                            'price': sr.price,
                            'qty': quantity,
                            'amount': sr.price * quantity,
                            'strategy': sr.scenario or 'ClosingBet',
                            'investment_type': '종가배팅',
                            'order_time': datetime.now().strftime("%H:%M:%S"),
                        }
                except Exception:
                    pass  # pending 등록 실패해도 주문은 진행
                
                order_result = self.kiwoom.SendOrder(
                    "매수", "0101", self.kiwoom.account_no,
                    1,  # 신규매수
                    sr.code, quantity, sr.price, "00", ""
                )
                
                if order_result == 0:
                    self.pm.record_trade(
                        sr.code, sr.name, sr.action, quantity, sr.price, sr.reason, sr.scenario
                    )
                    return OrderResult(
                        success=True,
                        code=sr.code,
                        order_type="buy",
                        quantity=quantity,
                        price=sr.price,
                        message="매수 주문 완료"
                    )
                else:
                    return OrderResult(
                        success=False,
                        code=sr.code,
                        order_type="buy",
                        quantity=quantity,
                        price=sr.price,
                        message=f"주문 실패: {order_result}"
                    )
            except Exception as e:
                return OrderResult(
                    success=False,
                    code=sr.code,
                    order_type="buy",
                    quantity=quantity,
                    price=sr.price,
                    message=f"주문 에러: {e}"
                )
        
        return OrderResult(
            success=False,
            code=sr.code,
            order_type="buy",
            quantity=0,
            price=0,
            message="실행 불가"
        )
    
    def _execute_sell(self, sr: ScanResult) -> OrderResult:
        """매도 실행"""
        cfg = self.config
        
        pos = self.pm.get_position(sr.code)
        if not pos or pos.quantity <= 0:
            return OrderResult(
                success=False,
                code=sr.code,
                order_type="sell",
                quantity=0,
                price=0,
                message="보유 수량 없음"
            )
        
        # 매도 수량 계산
        if sr.action in [ActionType.SELL_FULL, ActionType.STOP_LOSS]:
            quantity = pos.quantity  # 전량
        else:
            sell_pct = sr.allocation_pct / 100
            quantity = int(pos.quantity * sell_pct)
            if quantity <= 0:
                quantity = pos.quantity  # 최소 1주
        
        # 시뮬레이션 모드
        if cfg.simulation_mode:
            logger.info(f"[SIM] SELL {sr.code} {sr.name} x{quantity} @{sr.price:,}")
            
            remaining = pos.quantity - quantity
            if remaining <= 0:
                self.pm.update_position(sr.code, sr.name, 0, 0, sr, sr.action)
            else:
                self.pm.update_position(
                    sr.code, sr.name, remaining, pos.avg_price, sr, sr.action
                )
            
            self.pm.record_trade(
                sr.code, sr.name, sr.action, quantity, sr.price, sr.reason, sr.scenario
            )
            
            return OrderResult(
                success=True,
                code=sr.code,
                order_type="sell",
                quantity=quantity,
                price=sr.price,
                message="[SIM] 매도 완료",
                timestamp=datetime.now().strftime("%H:%M:%S")
            )
        
        # 실제 주문 (키움)
        if self.kiwoom:
            try:
                order_result = self.kiwoom.SendOrder(
                    "매도", "0101", self.kiwoom.account_no,
                    2,  # 신규매도
                    sr.code, quantity, sr.price, "00", ""
                )
                
                if order_result == 0:
                    self.pm.record_trade(
                        sr.code, sr.name, sr.action, quantity, sr.price, sr.reason, sr.scenario
                    )
                    return OrderResult(
                        success=True,
                        code=sr.code,
                        order_type="sell",
                        quantity=quantity,
                        price=sr.price,
                        message="매도 주문 완료"
                    )
            except Exception as e:
                return OrderResult(
                    success=False,
                    code=sr.code,
                    order_type="sell",
                    quantity=quantity,
                    price=sr.price,
                    message=f"주문 에러: {e}"
                )
        
        return OrderResult(
            success=False,
            code=sr.code,
            order_type="sell",
            quantity=0,
            price=0,
            message="실행 불가"
        )


# =============================================================================
# ClosingBetUnified - 메인 클래스
# =============================================================================

class ClosingBetUnified:
    """종가배팅 통합 시스템"""
    
    def __init__(self, config: UnifiedConfig = None):
        self.config = config or UnifiedConfig()
        
        self.scanner = UnifiedScanner(self.config)
        self.analyzer = UnifiedAnalyzer(self.config)
        self.pm = PositionManager(self.config)
        self.executor = UnifiedExecutor(self.config, self.pm)
        
        self.scan_results: List[ScanResult] = []
        
        logger.info("=" * 60)
        logger.info(" Closing Bet Unified System v1.0")
        logger.info(f" Mode: {'SIMULATION' if self.config.simulation_mode else 'LIVE'}")
        logger.info(f" Capital: {self.config.total_capital:,}")
        logger.info("=" * 60)
    
    def run_scan(self, market: str = "ALL") -> List[ScanResult]:
        """전체 스캔 실행"""
        logger.info("\n[SCAN] Starting market scan...")
        
        # 1. 종목 스캔
        targets = self.scanner.scan_market(market)
        targets = self.scanner.filter_candidates(targets)
        
        if not targets:
            logger.warning("[SCAN] No candidates found")
            return []
        
        # 2. 분석
        results = []
        current_time = datetime.now()
        
        for i, (code, name) in enumerate(targets.items(), 1):
            if i % 100 == 0:
                logger.info(f"[SCAN] Progress: {i}/{len(targets)}")
            
            try:
                ohlcv = self.scanner.get_ohlcv(code)
                if not ohlcv:
                    continue
                
                pos = self.pm.get_position(code)
                result = self.analyzer.analyze(code, name, ohlcv, pos, current_time)
                
                if result and result.action not in [ActionType.WAIT, ActionType.AVOID]:
                    results.append(result)
                    
            except Exception as e:
                continue
        
        # 3. 정렬 (신뢰도 순)
        results.sort(key=lambda x: -x.confidence)
        self.scan_results = results
        
        # 4. 결과 저장
        self._save_scan_results(results)
        
        # 5. 요약 출력
        self._print_scan_summary(results)
        
        return results
    
    def run_positions_check(self) -> List[ScanResult]:
        """보유 종목 체크"""
        logger.info("\n[CHECK] Checking positions...")
        
        results = []
        current_time = datetime.now()
        
        for code, pos in self.pm.positions.items():
            try:
                ohlcv = self.scanner.get_ohlcv(code)
                if not ohlcv:
                    continue
                
                result = self.analyzer.analyze(code, pos.name, ohlcv, pos, current_time)
                if result:
                    results.append(result)
                    
                    # 위험 신호 즉시 출력
                    if result.action in [ActionType.STOP_LOSS, ActionType.REDUCE]:
                        logger.warning(f"  ⚠️ {result.action.value}: {code} {pos.name}")
                    
            except Exception as e:
                continue
        
        return results
    
    def execute_signals(self, results: List[ScanResult] = None, 
                        auto_execute: bool = False) -> List[OrderResult]:
        """신호 실행"""
        results = results or self.scan_results
        
        if not results:
            logger.info("[EXEC] No signals to execute")
            return []
        
        orders = []
        
        # 매도 먼저 (손절, 익절)
        sell_results = [r for r in results if r.action in [
            ActionType.STOP_LOSS, ActionType.REDUCE,
            ActionType.SELL_PHASE1, ActionType.SELL_PHASE2,
            ActionType.SELL_PHASE3, ActionType.SELL_FULL
        ]]
        
        for sr in sell_results:
            if auto_execute or self._confirm_order(sr):
                order = self.executor.execute(sr)
                if order:
                    orders.append(order)
        
        # 매수
        buy_results = [r for r in results if r.action in [
            ActionType.BUY_PHASE1, ActionType.BUY_PHASE2,
            ActionType.BUY_PHASE3, ActionType.BUY_D_ADD,
            ActionType.BUY_CLOSING, ActionType.REENTRY
        ]]
        
        for sr in buy_results[:5]:  # 상위 5개만
            if auto_execute or self._confirm_order(sr):
                order = self.executor.execute(sr)
                if order:
                    orders.append(order)
        
        return orders
    
    def _confirm_order(self, sr: ScanResult) -> bool:
        """주문 확인 (수동 모드)"""
        print(f"\n{'='*50}")
        print(f" {sr.action.value}: {sr.code} {sr.name}")
        print(f" Price: {sr.price:,} | Alloc: {sr.allocation_pct:.0f}%")
        print(f" Reason: {sr.reason}")
        print(f"{'='*50}")
        
        resp = input("Execute? (y/n): ").strip().lower()
        return resp == 'y'
    
    def _save_scan_results(self, results: List[ScanResult]):
        """스캔 결과 저장"""
        if not results:
            return
        
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_results (
                    date TEXT,
                    code TEXT,
                    name TEXT,
                    price INTEGER,
                    action TEXT,
                    allocation_pct REAL,
                    confidence REAL,
                    zone TEXT,
                    a_price INTEGER,
                    b_price INTEGER,
                    c_price INTEGER,
                    stop_loss INTEGER,
                    target_1 INTEGER,
                    target_2 INTEGER,
                    support_confirmed INTEGER,
                    smart_money INTEGER,
                    ma_aligned INTEGER,
                    trap_type TEXT,
                    scenario TEXT,
                    reason TEXT,
                    created_at TEXT,
                    PRIMARY KEY (date, code)
                )
            ''')
            
            today = datetime.now().strftime("%Y%m%d")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("DELETE FROM scan_results WHERE date = ?", (today,))
            
            for r in results[:100]:
                cursor.execute('''
                    INSERT INTO scan_results
                    (date, code, name, price, action, allocation_pct, confidence,
                     zone, a_price, b_price, c_price, stop_loss, target_1, target_2,
                     support_confirmed, smart_money, ma_aligned, trap_type,
                     scenario, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    today, r.code, r.name, r.price, r.action.value,
                    r.allocation_pct, r.confidence, r.zone,
                    int(r.a_price), int(r.b_price), int(r.c_price),
                    int(r.stop_loss), int(r.target_1), int(r.target_2),
                    1 if r.support_confirmed else 0,
                    1 if r.smart_money_detected else 0,
                    1 if r.ma_aligned else 0,
                    r.trap_type, r.scenario, r.reason, now
                ))
            
            conn.commit()
            
            logger.info(f"[SCAN] Saved {len(results[:100])} results")
            
        except Exception as e:
            logger.error(f"[SCAN] Save failed: {e}")
    
        finally:
            if conn:
                conn.close()
    def _print_scan_summary(self, results: List[ScanResult]):
        """스캔 요약 출력"""
        print("\n" + "=" * 70)
        print(" SCAN RESULTS")
        print("=" * 70)
        
        if not results:
            print("  No actionable signals")
            return
        
        # 행동별 분류
        action_counts = {}
        for r in results:
            action_counts[r.action.value] = action_counts.get(r.action.value, 0) + 1
        
        print("\n[Distribution]")
        for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
            print(f"  {action}: {count}")
        
        # 매수 신호
        buy_results = [r for r in results if r.action in [
            ActionType.BUY_PHASE1, ActionType.BUY_PHASE2,
            ActionType.BUY_PHASE3, ActionType.BUY_D_ADD
        ]]
        
        if buy_results:
            print("\n" + "-" * 70)
            print(" ** BUY SIGNALS **")
            print("-" * 70)
            
            for r in buy_results[:10]:
                print(f"\n  [{r.code}] {r.name}")
                print(f"    {r.action.value} ({r.allocation_pct:.0f}%) | {r.scenario}")
                print(f"    Price: {r.price:,} | Zone: {r.zone} | Conf: {r.confidence:.0f}")
                print(f"    SL: {r.stop_loss:,.0f} | T1: {r.target_1:,.0f} | T2: {r.target_2:,.0f}")
                flags = []
                if r.support_confirmed: flags.append("Sup+")
                if r.smart_money_detected: flags.append("SM+")
                if r.ma_aligned: flags.append("MA+")
                if flags:
                    print(f"    Flags: {' '.join(flags)}")
        
        print("\n" + "=" * 70)
    
    def get_status(self) -> Dict:
        """현재 상태"""
        return {
            'positions': len(self.pm.positions),
            'total_position_pct': self.pm.get_total_position_pct(),
            'scan_results': len(self.scan_results),
            'mode': 'SIMULATION' if self.config.simulation_mode else 'LIVE',
            'capital': self.config.total_capital
        }


# =============================================================================
# GapUpPredictor - 갭상승 예측 (전자책 p.424)
# =============================================================================

class GapUpPredictor:
    """
    다음날 갭상승 확률 예측
    
    전자책 (p.424): "차트 패턴 + 재료 = 다음날 갭상승 높은 확률"
    
    [점수 구성] (100점 만점)
    - 차트 패턴: 50점 (종가배팅 3조건)
    - 거래대금 급증: 20점
    - 종가 위치: 10점
    - 호재/뉴스: 20점
    
    [등급]
    - 80점+: HIGH (3-5% 갭상승 기대)
    - 60점+: MEDIUM (1-3% 갭상승)
    - 40점+: LOW (0-1%)
    - 40점-: VERY_LOW
    """
    
    def __init__(self):
        # 직전영업일 기준 (휴장일 대응)
        self.today = get_last_business_day()
    
    def predict(self, code: str, ohlcv: pd.DataFrame, 
                news_score: int = 0, cb_conditions: dict = None) -> dict:
        """
        갭상승 확률 예측
        
        Args:
            code: 종목코드
            ohlcv: OHLCV 데이터프레임
            news_score: 뉴스/재료 점수 (0-20, 외부 입력)
            cb_conditions: 종가배팅 3조건 결과 (screener에서 전달)
        
        Returns:
            {
                'code': str,
                'total_score': int,
                'grade': str,
                'expected_gap': str,
                'breakdown': dict,
                'recommendation': str
            }
        """
        if len(ohlcv) < 20:
            return self._empty_result(code, "데이터 부족")
        
        scores = {}
        
        # (1) 차트 패턴 점수 (최대 50점)
        scores['chart'] = self._score_chart_pattern(ohlcv, cb_conditions)
        
        # (2) 거래대금 급증 (최대 20점)
        scores['trading_value'] = self._score_trading_value(ohlcv)
        
        # (3) 종가 위치 (최대 10점)
        scores['close_position'] = self._score_close_position(ohlcv)
        
        # (4) 뉴스/재료 (최대 20점) - 외부 입력
        scores['news'] = min(20, max(0, news_score))
        
        # 총점
        total_score = sum(scores.values())
        
        # 등급 및 예상 갭
        grade, expected_gap = self._determine_grade(total_score)
        
        # 추천
        recommendation = self._get_recommendation(grade, scores)
        
        return {
            'code': code,
            'total_score': total_score,
            'grade': grade,
            'expected_gap': expected_gap,
            'breakdown': scores,
            'recommendation': recommendation
        }
    
    def _score_chart_pattern(self, ohlcv: pd.DataFrame, cb_conditions: dict = None) -> int:
        """
        차트 패턴 점수 (최대 50점)
        
        종가배팅 3조건 기반:
        - 조건1: 정배열 + 장대양봉 + 거래대금 (20점)
        - 조건2: 신고가 + 작은 캔들 (15점)
        - 조건3: 눌림목 돌파 (15점)
        """
        score = 0
        
        # 외부에서 종가배팅 조건 결과 전달된 경우
        if cb_conditions:
            if cb_conditions.get('cond1_pass'):
                score += 20
            if cb_conditions.get('cond2_pass'):
                score += 15
            if cb_conditions.get('cond3_pass'):
                score += 15
            return min(50, score)
        
        # 직접 계산
        close = ohlcv['종가'] if '종가' in ohlcv.columns else ohlcv['close']
        open_p = ohlcv['시가'] if '시가' in ohlcv.columns else ohlcv['open']
        high = ohlcv['고가'] if '고가' in ohlcv.columns else ohlcv['high']
        low = ohlcv['저가'] if '저가' in ohlcv.columns else ohlcv['low']
        
        # 조건1: 정배열 + 양봉
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        
        # NaN 체크
        if pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma20):
            return score
        
        if ma5 > ma10 > ma20:
            score += 10
            # 장대양봉 체크
            today_body = close.iloc[-1] - open_p.iloc[-1]
            today_range = high.iloc[-1] - low.iloc[-1]
            if today_range > 0 and today_body > 0:
                if today_body / today_range > 0.6:
                    score += 10
        
        # 조건2: 신고가 (60일)
        period_high = high.iloc[-61:-1].max() if len(ohlcv) > 60 else high.iloc[:-1].max()
        if high.iloc[-1] > period_high:
            score += 15
        
        # 조건3: 눌림목 후 반등
        recent_high = high.iloc[-10:].max()
        recent_low = low.iloc[-5:].min()
        if recent_high > 0:
            pullback = (recent_high - recent_low) / recent_high * 100
            if 5 <= pullback <= 15:
                if close.iloc[-1] > close.iloc[-2]:  # 오늘 양봉
                    score += 15
        
        return min(50, score)
    
    def _score_trading_value(self, ohlcv: pd.DataFrame) -> int:
        """
        거래대금 급증 점수 (최대 20점)
        
        - 3배 이상: 20점
        - 2배 이상: 15점
        - 1.5배 이상: 10점
        """
        close = ohlcv['종가'] if '종가' in ohlcv.columns else ohlcv['close']
        volume = ohlcv['거래량'] if '거래량' in ohlcv.columns else ohlcv['volume']
        
        trading_value = close * volume
        avg_20 = trading_value.rolling(20).mean().iloc[-2]  # 전일까지 평균
        today_value = trading_value.iloc[-1]
        
        # NaN 체크
        if pd.isna(avg_20) or avg_20 <= 0:
            return 0
        
        ratio = today_value / avg_20
        
        if ratio >= 3.0:
            return 20
        elif ratio >= 2.0:
            return 15
        elif ratio >= 1.5:
            return 10
        elif ratio >= 1.2:
            return 5
        return 0
    
    def _score_close_position(self, ohlcv: pd.DataFrame) -> int:
        """
        종가 위치 점수 (최대 10점)
        
        당일 고가 대비 종가 위치
        - 고가 근접 (95%+): 10점
        - 상단 (85%+): 7점
        - 중상단 (70%+): 4점
        """
        close = ohlcv['종가'] if '종가' in ohlcv.columns else ohlcv['close']
        high = ohlcv['고가'] if '고가' in ohlcv.columns else ohlcv['high']
        low = ohlcv['저가'] if '저가' in ohlcv.columns else ohlcv['low']
        
        today_range = high.iloc[-1] - low.iloc[-1]
        if today_range <= 0:
            return 5
        
        position = (close.iloc[-1] - low.iloc[-1]) / today_range
        
        if position >= 0.95:
            return 10
        elif position >= 0.85:
            return 7
        elif position >= 0.70:
            return 4
        return 0
    
    def _determine_grade(self, total_score: int) -> Tuple[str, str]:
        """등급 및 예상 갭 결정"""
        if total_score >= 80:
            return "HIGH", "3-5%+"
        elif total_score >= 60:
            return "MEDIUM", "1-3%"
        elif total_score >= 40:
            return "LOW", "0-1%"
        else:
            return "VERY_LOW", "불확실"
    
    def _get_recommendation(self, grade: str, scores: dict) -> str:
        """투자 추천"""
        if grade == "HIGH":
            return "적극 매수 (종가배팅 적합)"
        elif grade == "MEDIUM":
            if scores.get('chart', 0) >= 30:
                return "매수 고려 (차트 양호)"
            elif scores.get('news', 0) >= 15:
                return "매수 고려 (재료 있음)"
            return "관망 권고"
        elif grade == "LOW":
            return "관망 (조건 부족)"
        else:
            return "매수 비권고"
    
    def _empty_result(self, code: str, reason: str) -> dict:
        """빈 결과"""
        return {
            'code': code,
            'total_score': 0,
            'grade': "N/A",
            'expected_gap': "N/A",
            'breakdown': {},
            'recommendation': reason
        }
    
    def print_prediction(self, result: dict):
        """예측 결과 출력"""
        print("\n" + "-" * 50)
        print(f" 갭상승 예측: {result['code']}")
        print("-" * 50)
        print(f"  총점: {result['total_score']}/100")
        print(f"  등급: {result['grade']}")
        print(f"  예상 갭: {result['expected_gap']}")
        
        if result['breakdown']:
            print("\n  [점수 상세]")
            print(f"    차트 패턴: {result['breakdown'].get('chart', 0)}/50")
            print(f"    거래대금: {result['breakdown'].get('trading_value', 0)}/20")
            print(f"    종가 위치: {result['breakdown'].get('close_position', 0)}/10")
            print(f"    뉴스/재료: {result['breakdown'].get('news', 0)}/20")
        
        print(f"\n  추천: {result['recommendation']}")
        print("-" * 50)
    
    # =========================================================================
    # V4 카운트 기반 예측 (신규, 2026-04-22)
    # =========================================================================
    # 근거: PHASE_1A_DATA_SOURCES.md §11~§36
    # - 견고성 5/5, 레짐 3/3, Walk-Forward 3/3 모두 통과
    # - 슬리피지 반영 5억 자본 기준 실전 CAGR +5.83%, Calmar 2.712
    # - 설계서: V4_PATCH_DESIGN_v2.md + V4_PATCH_DESIGN_v3_APPENDIX.md
    
    def predict_v4(self, code: str, ohlcv: pd.DataFrame,
                   news_score: int = 0, cb_conditions: dict = None) -> dict:
        """
        V4 카운트 기반 갭상승 예측 (Stage 1+2 패치)
        
        기존 predict() 무수정. 호환 반환 형식 (5개 키) 유지.
        
        V4 시그널 (4조건 각 1점, 총 0~4):
            C1. 정배열 (MA5>MA10>MA20) + 장대양봉 (body/range > 0.6)
            C2. 60일 신고가 (today.high > prev60.max)
            C3. 거래대금 3배↑ (today.tv / avg20.tv >= 3.0)
            C4. 종가 위치 95%↑ ((close-low)/(high-low) >= 0.95)
        
        Mode A (확정): score==4 만 매수 시그널로 사용 (§9 Q2 권고)
        
        반환:
            total_score: v4_score * 25 (0/25/50/75/100) — 기존 필터 ≥40 호환
            grade: V4_STRONG / V4_HIGH / V4_MEDIUM / V4_LOW / V4_NONE
            expected_gap: 백테스트 평균 갭 기반
            breakdown: {'v4_score': 0-4, 'c1': bool, 'c2': bool, 'c3': bool, 'c4': bool}
            recommendation: Mode A 기반 (STRONG_BUY / STRONG_BUY_PRIORITY / SKIP / WATCH)
        """
        if len(ohlcv) < 61:  # 60일 신고가 계산 필요
            return self._empty_result_v4(code, "데이터 부족 (최소 61일 필요)")
        
        # 컬럼 영/한 둘 다 지원 (호출처: legacy_scan_ext_api.py 영문 사용)
        def _col(ohlcv, kor, eng):
            if kor in ohlcv.columns: return ohlcv[kor]
            if eng in ohlcv.columns: return ohlcv[eng]
            return None
        
        close = _col(ohlcv, '종가', 'Close')
        open_p = _col(ohlcv, '시가', 'Open')
        high = _col(ohlcv, '고가', 'High')
        low = _col(ohlcv, '저가', 'Low')
        volume = _col(ohlcv, '거래량', 'Volume')
        
        if close is None or open_p is None or high is None or low is None or volume is None:
            return self._empty_result_v4(code, "컬럼 누락")
        
        # 최소 가격/거래량 필터 (원칙: 유동성 보장)
        close_t = float(close.iloc[-1])
        vol_t = float(volume.iloc[-1])
        if close_t < 1000 or vol_t < 50000:
            return self._empty_result_v4(code, "가격/거래량 미달")
        
        # 이동평균
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        if pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma20):
            return self._empty_result_v4(code, "이동평균 계산 불가")
        
        # C1: 정배열 + 장대양봉
        has_align = (ma5 > ma10) and (ma10 > ma20)
        body = close_t - float(open_p.iloc[-1])
        rng = float(high.iloc[-1]) - float(low.iloc[-1])
        c1 = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
        
        # C2: 60일 신고가
        prev60_max = high.iloc[-61:-1].max()
        c2 = float(high.iloc[-1]) > float(prev60_max)
        
        # C3: 거래대금 3배↑
        tv_arr = close.iloc[-21:-1] * volume.iloc[-21:-1]  # 전일까지 20일
        tv_avg20 = float(tv_arr.mean())
        today_tv = close_t * vol_t
        c3 = tv_avg20 > 0 and (today_tv / tv_avg20 >= 3.0)
        
        # C4: 종가 위치 95%↑
        c4 = rng > 0 and ((close_t - float(low.iloc[-1])) / rng >= 0.95)
        
        # V4 점수 (0~4)
        v4_score = int(c1) + int(c2) + int(c3) + int(c4)
        
        # 호환 total_score (기존 ≥40 필터 통과용)
        total_score = v4_score * 25
        
        # 등급 + 예상 갭 (§11~§18 백테스트 기반)
        if v4_score == 4:
            grade = "V4_STRONG"; expected_gap = "+3~5%"
        elif v4_score == 3:
            grade = "V4_HIGH"; expected_gap = "+1~3%"
        elif v4_score == 2:
            grade = "V4_MEDIUM"; expected_gap = "+0~1%"
        elif v4_score == 1:
            grade = "V4_LOW"; expected_gap = "불확실"
        else:
            grade = "V4_NONE"; expected_gap = "-"
        
        # 가격/거래대금 필터 (§22 황금/함정 조합, v3 Q3)
        tv_eok = today_tv / 1e8  # 억 단위
        if v4_score == 4:
            if 10000 <= close_t < 30000 and tv_eok >= 1000:
                recommendation = "SKIP"  # 함정 조합 (-0.107%)
            elif close_t < 5000 and tv_eok >= 200:
                recommendation = "STRONG_BUY_PRIORITY"  # 황금 (+6.405%)
            else:
                recommendation = "STRONG_BUY"  # 일반 V4=4
        elif v4_score == 3:
            recommendation = "WATCH"  # Mode A 는 미매수
        else:
            recommendation = "NO_SIGNAL"
        
        return {
            'code': code,
            'total_score': total_score,
            'grade': grade,
            'expected_gap': expected_gap,
            'breakdown': {
                'v4_score': v4_score,
                'c1_pattern': bool(c1),
                'c2_new_high': bool(c2),
                'c3_volume': bool(c3),
                'c4_close_pos': bool(c4),
                'price': close_t,
                'tv_eok': round(tv_eok, 1),
            },
            'recommendation': recommendation,
        }
    
    def _empty_result_v4(self, code: str, reason: str) -> dict:
        """V4 빈 결과"""
        return {
            'code': code,
            'total_score': 0,
            'grade': "N/A",
            'expected_gap': "N/A",
            'breakdown': {'v4_score': 0, 'reason': reason},
            'recommendation': reason,
        }


# =============================================================================
# 메인
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print(" Closing Bet Unified System v1.0")
    print(" 전자책 기반 종가배팅 통합 시스템")
    print("=" * 70)
    
    # 설정
    config = UnifiedConfig(
        total_capital=10_000_000,
        simulation_mode=True,
        verbose=True
    )
    
    # 시스템 초기화
    system = ClosingBetUnified(config)
    
    # 메뉴
    while True:
        print("\n[MENU]")
        print("  1. 전체 스캔")
        print("  2. 보유 종목 체크")
        print("  3. 신호 실행")
        print("  4. 포지션 현황")
        print("  5. 상태 확인")
        print("  0. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == '1':
            system.run_scan("ALL")
        
        elif choice == '2':
            results = system.run_positions_check()
            for r in results:
                print(f"  {r.code} {r.name}: {r.action.value} - {r.scenario}")
        
        elif choice == '3':
            system.execute_signals(auto_execute=False)
        
        elif choice == '4':
            print("\n[POSITIONS]")
            for code, pos in system.pm.positions.items():
                print(f"  {code} {pos.name}: {pos.quantity}주 @{pos.avg_price:,.0f}")
                print(f"    Phase: {pos.buy_phase} | P/L: {pos.profit_pct:+.1f}%")
        
        elif choice == '5':
            status = system.get_status()
            print(f"\n[STATUS]")
            for k, v in status.items():
                print(f"  {k}: {v}")
        
        elif choice == '0':
            print("\n종료합니다.")
            break


if __name__ == "__main__":
    main()


# =============================================================================
# ClosingBetMonitor - 종가배팅 실시간 모니터링 (14:00~15:20)
# =============================================================================

class ClosingBetMonitor:
    """
    종가배팅 전용 모니터링 (14:00 ~ 15:20)
    
    전자책 핵심 (p.424):
    - 2시~3시20분 매수세 체크
    - 1분봉 계단식 상승
    - 거래대금 점진적 증가
    """
    
    def __init__(self, kiwoom=None):
        self.kiwoom = kiwoom
        self.monitor_start = time(14, 0)
        self.monitor_end = time(15, 20)
        self.final_decision = time(15, 10)
        
        # 모니터링 대상: {code: MonitorData}
        self.candidates = {}
    
    def is_monitoring_time(self) -> bool:
        """현재 시간이 모니터링 시간대인지"""
        now = datetime.now().time()
        return self.monitor_start <= now <= self.monitor_end
    
    def is_decision_time(self) -> bool:
        """최종 결정 시간인지 (15:10~15:20)"""
        now = datetime.now().time()
        return self.final_decision <= now <= self.monitor_end
    
    def add_candidate(self, code: str, name: str, initial_price: int = 0):
        """모니터링 대상 추가"""
        self.candidates[code] = {
            'name': name,
            'start_time': datetime.now(),
            'initial_price': initial_price,
            'price_history': [],
            'volume_history': [],
            'stair_score': 0,
            'volume_trend': 'FLAT',
            'final_score': 0,
            'recommendation': 'WAIT'
        }
        logger.info(f"[Monitor] {code} {name} 추가됨")
    
    def remove_candidate(self, code: str):
        """모니터링 대상 제거"""
        if code in self.candidates:
            del self.candidates[code]
    
    def update_candidate(self, code: str, price: int, volume: int):
        """실시간 데이터 업데이트"""
        if code not in self.candidates:
            return
        
        now = datetime.now()
        data = self.candidates[code]
        
        # 초기가격 설정
        if data['initial_price'] == 0:
            data['initial_price'] = price
        
        data['price_history'].append({'time': now, 'price': price})
        data['volume_history'].append({'time': now, 'volume': volume})
        
        # 최근 100개만 유지
        if len(data['price_history']) > 100:
            data['price_history'] = data['price_history'][-100:]
            data['volume_history'] = data['volume_history'][-100:]
        
        # 계단식 상승 체크 (10개 이상 데이터)
        if len(data['price_history']) >= 10:
            data['stair_score'] = self._check_stair_pattern(data['price_history'])
        
        # 거래량 추세 체크
        if len(data['volume_history']) >= 5:
            data['volume_trend'] = self._check_volume_trend(data['volume_history'])
        
        # 종합 점수
        data['final_score'] = self._calculate_score(data)
        
        # 추천 결정
        if data['final_score'] >= 70:
            data['recommendation'] = 'BUY'
        elif data['final_score'] >= 50:
            data['recommendation'] = 'WATCH'
        else:
            data['recommendation'] = 'PASS'
    
    def _check_stair_pattern(self, price_history: List[Dict]) -> int:
        """
        계단식 상승 패턴 체크
        
        전자책: "1분봉 차트: 주가 우상향 (계단식 상승) 확인"
        저점이 점점 높아지는지 확인
        """
        if len(price_history) < 10:
            return 0
        
        prices = [p['price'] for p in price_history[-20:]]
        
        # 3개씩 그룹으로 나눠 저점 추출
        lows = []
        for i in range(0, len(prices) - 2, 3):
            segment = prices[i:i+3]
            lows.append(min(segment))
        
        if len(lows) < 3:
            return 0
        
        # 저점 상승 횟수
        rising_count = sum(1 for i in range(len(lows)-1) if lows[i+1] > lows[i])
        
        score = int(rising_count / (len(lows) - 1) * 100)
        return min(100, score)
    
    def _check_volume_trend(self, volume_history: List[Dict]) -> str:
        """
        거래량 추세 체크
        
        전자책: "거래량(거래대금) 유지 or 점진적 증가 확인"
        """
        if len(volume_history) < 5:
            return 'FLAT'
        
        volumes = [v['volume'] for v in volume_history[-10:]]
        
        # 전반부 vs 후반부 평균 비교
        mid = len(volumes) // 2
        first_half = sum(volumes[:mid]) / mid if mid > 0 else 0
        second_half = sum(volumes[mid:]) / (len(volumes) - mid) if len(volumes) > mid else 0
        
        if first_half <= 0:
            return 'FLAT'
        
        ratio = second_half / first_half
        
        if ratio > 1.2:
            return 'INCREASING'
        elif ratio < 0.8:
            return 'DECREASING'
        else:
            return 'FLAT'
    
    def _calculate_score(self, data: Dict) -> int:
        """종가배팅 최종 점수 (100점 만점)"""
        score = 0
        
        # (1) 계단식 상승 (최대 40점)
        score += min(40, int(data['stair_score'] * 0.4))
        
        # (2) 거래량 추세 (최대 30점)
        if data['volume_trend'] == 'INCREASING':
            score += 30
        elif data['volume_trend'] == 'FLAT':
            score += 15
        # DECREASING는 0점
        
        # (3) 가격 상승률 (최대 30점)
        if data['price_history'] and data['initial_price'] > 0:
            current_price = data['price_history'][-1]['price']
            change_pct = (current_price - data['initial_price']) / data['initial_price'] * 100
            
            if change_pct > 3:
                score += 30
            elif change_pct > 1:
                score += 20
            elif change_pct > 0:
                score += 10
        
        return score
    
    def get_recommendations(self, min_score: int = 50) -> List[Dict]:
        """
        종가배팅 추천 종목
        
        전자책: "마감 직전 (3시~3시20분) 진입 여부 결정"
        """
        recommendations = []
        
        for code, data in self.candidates.items():
            if data['final_score'] >= min_score:
                current_price = data['price_history'][-1]['price'] if data['price_history'] else 0
                change_pct = 0
                if data['initial_price'] > 0 and current_price > 0:
                    change_pct = (current_price - data['initial_price']) / data['initial_price'] * 100
                
                recommendations.append({
                    'code': code,
                    'name': data['name'],
                    'score': data['final_score'],
                    'stair_score': data['stair_score'],
                    'volume_trend': data['volume_trend'],
                    'current_price': current_price,
                    'change_pct': round(change_pct, 2),
                    'recommendation': data['recommendation']
                })
        
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)
    
    def get_status(self) -> Dict:
        """모니터링 상태"""
        return {
            'is_monitoring_time': self.is_monitoring_time(),
            'is_decision_time': self.is_decision_time(),
            'candidates_count': len(self.candidates),
            'buy_recommendations': len([c for c in self.candidates.values() if c['recommendation'] == 'BUY']),
            'watch_recommendations': len([c for c in self.candidates.values() if c['recommendation'] == 'WATCH']),
        }
    
    def print_status(self):
        """상태 출력"""
        status = self.get_status()
        print("\n" + "=" * 60)
        print(" 종가배팅 모니터링 현황")
        print("=" * 60)
        print(f"  모니터링 시간: {'O' if status['is_monitoring_time'] else 'X'}")
        print(f"  결정 시간: {'O' if status['is_decision_time'] else 'X'}")
        print(f"  모니터링 종목: {status['candidates_count']}개")
        print(f"  BUY 추천: {status['buy_recommendations']}개")
        print(f"  WATCH 추천: {status['watch_recommendations']}개")
        
        if self.candidates:
            print("\n[종목별 현황]")
            for code, data in self.candidates.items():
                print(f"  {code} {data['name']}: 점수={data['final_score']} "
                      f"계단={data['stair_score']} 거래량={data['volume_trend']} "
                      f"→ {data['recommendation']}")



if __name__ == "__main__":
    main()
