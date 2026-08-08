# -*- coding: utf-8 -*-
"""
커밋 전 코드 검증 스크립트
사용: python pre_commit_check.py

체크 항목:
1. 스캔 테이블에 ORDER BY date DESC 사용 여부 (금지)
2. 스캔 테이블에 created_at 컬럼 누락 여부
3. PyQt 시그니처 순서 문제
4. 전략 모듈이 호출하는 KRXDataClient 메서드 존재 여부
5. DB 커넥션 누수 (새 코드 대상)
6. bare except 패턴 (새 코드 대상)
7. strategy_examiner.py 구조 무결성 (Phase 5-3)
8. earnings_quality.py 구조 무결성 (Phase 5-3)
9. trade_log 전략 귀속률 (Phase 7-5) - Unknown/외부주문 비율 5% 이하
10. trade_log investment_type 정합성 (Phase 7-5) - 수동 비율 5% 이하
11. 64bit 전용 모듈(sklearn) 32bit 코드 경로 import 금지
12. 루프 내 API sleep 누락
13. YYYYMMDD date 컨럼에 date('now') 함수 사용 금지 (형식 불일치 방지)
"""
import os
import re
import sys
import glob
import sqlite3
from contextlib import closing

# 인코딩 설정
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as e:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 스캔 결과 테이블 (ORDER BY date DESC 금지)
SCAN_TABLES = [
    'rs_targets_v2', 'bb_squeeze_v2', 'abcd_targets_v2', 'farley_signals_v2',
    'smc_structure_v2', 'scanned_targets_v2', 'ultimate_targets_v2',
    'modern_targets', 'mlpredict_v2', 'vsa_v2', 'sentiment_v2', 'orderflow_v2',
    'mtf_results', 'shakeout_targets', 'filtered_targets', 'plugin_results',
    'strategy_results', 'strategy_recommendations', 'unified_rankings',
    'quality_analysis', 'strategy_consensus'
]

# 예외 테이블 (date DESC 허용)
EXCEPTION_TABLES = [
    'trade_history', 'trade_log', 'mock_performance', 'execution_log',
    'daily_prices',   # 가격 이력 테이블 — 날짜 기준 최신 조회가 맞음
    'minute_ohlcv',   # 분봉 이력 테이블 — 동일
]

def check_order_by_date_desc():
    """ORDER BY date DESC 사용 검사"""
    errors = []
    
    # 전체 프로젝트 .py 파일 검사 (archive, __pycache__ 등 제외)
    exclude_dirs = {'archive', '__pycache__', '.git', 'venv', 'node_modules', 'scripts'}
    exclude_prefixes = ('check_', 'SYSTEM_CHECK_REPORT')
    
    for root, dirs, files in os.walk(BASE_DIR):
        # 제외 폴더 필터링
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for filename in files:
            if not filename.endswith('.py'):
                continue
            if filename.startswith(exclude_prefixes):
                continue
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, BASE_DIR)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # ORDER BY date DESC 패턴 찾기
                if re.search(r'ORDER BY\s+date\s+DESC', line, re.IGNORECASE):
                    # 예외 테이블인지 확인
                    is_exception = False
                    context_start = max(0, i - 10)
                    context = '\n'.join(lines[context_start:i])
                    
                    for exc_table in EXCEPTION_TABLES:
                        if exc_table in context:
                            is_exception = True
                            break
                    
                    if not is_exception:
                        # 스캔 테이블에서 사용된 것인지 확인
                        for scan_table in SCAN_TABLES:
                            if scan_table in context:
                                errors.append({
                                    'file': rel_path,
                                    'line': i,
                                    'table': scan_table,
                                    'content': line.strip()[:80]
                                })
                                break
    
    return errors

def check_created_at_missing():
    """INSERT 문에 created_at 누락 검사"""
    warnings = []
    
    # 전체 프로젝트 .py 파일 검사 (archive, __pycache__ 등 제외)
    exclude_dirs = {'archive', '__pycache__', '.git', 'venv', 'node_modules', 'scripts'}
    exclude_prefixes = ('check_', 'SYSTEM_CHECK_REPORT')
    
    for root, dirs, files in os.walk(BASE_DIR):
        # 제외 폴더 필터링
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for filename in files:
            if not filename.endswith('.py'):
                continue
            if filename.startswith(exclude_prefixes):
                continue
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, BASE_DIR)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                continue
            
            # INSERT INTO <scan_table> 패턴 찾기
            for table in SCAN_TABLES:
                pattern = rf'INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+{table}\s*\('
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                
                for match in matches:
                    # INSERT 문 전체 찾기 (다음 ) 까지)
                    start = match.start()
                    # VALUES까지 찾기
                    values_match = re.search(r'VALUES\s*\(', content[start:start+500], re.IGNORECASE)
                    if values_match:
                        insert_stmt = content[start:start+values_match.end()+200]
                        
                        # created_at 포함 여부
                        if 'created_at' not in insert_stmt.lower():
                            line_num = content[:start].count('\n') + 1
                            warnings.append({
                                'file': rel_path,
                                'line': line_num,
                                'table': table,
                                'message': 'INSERT 문에 created_at 컬럼 누락'
                            })
    
    return warnings


def check_strategy_method_exists():
    """전략 모듈이 호출하는 KRXDataClient 메서드 존재 여부 검사"""
    errors = []
    
    # 1. KRXDataClient 공개 메서드 목록 추출
    krx_data_path = os.path.join(BASE_DIR, 'krx_data.py')
    if not os.path.exists(krx_data_path):
        return errors
    
    with open(krx_data_path, 'r', encoding='utf-8') as f:
        krx_content = f.read()
    
    # class KRXDataClient 내부의 def 메서드 추출 (private 제외)
    krx_methods = set()
    in_class = False
    for line in krx_content.split('\n'):
        if 'class KRXDataClient' in line:
            in_class = True
            continue
        if in_class:
            # 클래스 끝 감지 (들여쓰기 없는 새 정의)
            if line and not line.startswith(' ') and not line.startswith('\t') and not line.startswith('#'):
                if 'class ' in line or 'def ' in line:
                    in_class = False
                    continue
            # 메서드 추출
            m = re.match(r'\s+def\s+([a-zA-Z]\w+)\s*\(', line)
            if m:
                krx_methods.add(m.group(1))
    
    # 2. strategy_*.py 파일에서 self.krx_client.메서드() 호출 추출
    for filename in os.listdir(BASE_DIR):
        if not filename.startswith('strategy_') or not filename.endswith('.py'):
            continue
        
        filepath = os.path.join(BASE_DIR, filename)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            # self.krx_client.메서드명( 패턴
            matches = re.findall(r'self\.krx_client\.([a-zA-Z_]\w*)\s*\(', line)
            for method_name in matches:
                if method_name not in krx_methods:
                    errors.append({
                        'file': filename,
                        'line': i,
                        'method': method_name,
                        'content': line.strip()[:80]
                    })
    
    return errors


def check_pyqt_slot_order():
    """PyQt 시그니처 순서 검사 - api/*.py 전체 대상"""
    warnings = []
    
    api_dir = os.path.join(BASE_DIR, 'api')
    if not os.path.isdir(api_dir):
        return warnings
    
    api_files = glob.glob(os.path.join(api_dir, '*.py'))
    
    for filepath in api_files:
        rel_path = os.path.relpath(filepath, BASE_DIR)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # @pyqtSlot 데코레이터 찾기
            if line.startswith('@pyqtSlot'):
                decorators = [line]
                j = i + 1
                
                # 연속된 데코레이터 수집
                while j < len(lines) and lines[j].strip().startswith('@pyqtSlot'):
                    decorators.append(lines[j].strip())
                    j += 1
                
                # 2개 이상 데코레이터가 있으면 순서 확인
                if len(decorators) >= 2:
                    # 인자 개수 추출
                    arg_counts = []
                    for dec in decorators:
                        # @pyqtSlot(result=str) -> 0개
                        # @pyqtSlot(str, result=str) -> 1개
                        # @pyqtSlot(str, str, result=str) -> 2개
                        args = re.findall(r'@pyqtSlot\(([^)]*)\)', dec)
                        if args:
                            arg_str = args[0]
                            # result= 제거하고 str, int 등 카운트
                            arg_str = re.sub(r'result\s*=\s*\w+', '', arg_str)
                            type_count = len([a for a in arg_str.split(',') if a.strip() and a.strip() in ('str', 'int', 'float', 'bool', 'list')])
                            arg_counts.append(type_count)
                        else:
                            arg_counts.append(0)
                    
                    # 인자 많은 것이 먼저 와야 함
                    if arg_counts != sorted(arg_counts, reverse=True):
                        warnings.append({
                            'file': rel_path,
                            'line': i + 1,
                            'message': f'pyqtSlot 순서 문제: 구체적인 것(인자 많은 것)이 먼저 와야 함',
                            'decorators': decorators
                        })
                
                i = j
            else:
                i += 1
    
    return warnings


def _get_staged_files():
    """git staged 파일 목록 반환 (새 코드만 검사용)"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True, text=True, cwd=BASE_DIR, encoding='utf-8', errors='ignore'
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split('\n') if f.endswith('.py') and f.strip()]
    except Exception:
        pass
    return []


def _get_staged_diff_lines(filepath):
    """staged 파일의 추가된 라인 번호 set 반환"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '-U0', '--', filepath],
            capture_output=True, text=True, cwd=BASE_DIR, encoding='utf-8', errors='ignore'
        )
        added_lines = set()
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                # @@ -old,count +new,count @@ 형식 파싱
                m = re.match(r'^@@\s.*\+(\d+)(?:,(\d+))?\s@@', line)
                if m:
                    start = int(m.group(1))
                    count = int(m.group(2)) if m.group(2) else 1
                    for ln in range(start, start + count):
                        added_lines.add(ln)
        return added_lines
    except Exception:
        return set()


def check_db_connection_leak():
    """[5/6] sqlite3.connect()가 finally: conn.close() 없이 사용된 새 코드 검사
    
    안전 패턴:
      ✅ try: ... conn = sqlite3.connect() ... finally: conn.close()
      ✅ with contextlib.closing(sqlite3.connect()) as conn:
    위험 패턴:
      ⚠️ conn = sqlite3.connect() → finally 블록 없음
    """
    warnings = []
    staged_files = _get_staged_files()
    
    if not staged_files:
        return warnings  # staged 파일 없으면 스킵
    
    for rel_path in staged_files:
        filepath = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(filepath):
            continue
        
        # 이 파일에서 새로 추가된 라인만 검사
        added_lines = _get_staged_diff_lines(rel_path)
        if not added_lines:
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            continue
        
        for i, line in enumerate(lines, 1):
            if i not in added_lines:
                continue
            
            if re.search(r'sqlite3\.connect\(', line) and not line.strip().startswith('#'):
                # 문자열/독스트링/주석 내부 패턴 무시
                stripped = line.strip()
                if stripped.startswith(('"""', "'''", '"', "'")):
                    continue
                # 인라인 주석 제거 후 체크
                code_part = stripped.split('#')[0]
                if 'sqlite3.connect(' not in code_part:
                    continue
                # 문자열 내부인지 간이 판별 (따옴표로 감싸져 있으면 스킵)
                if re.search(r'''['"].*sqlite3\.connect\(.*['"]''', code_part):
                    continue
                # finally: conn.close() 가 아래에 있는지 확인
                has_finally_close = False
                for j in range(i, min(i + 100, len(lines))):
                    if 'finally:' in lines[j]:
                        # finally 블록 내에 .close() 가 있는지
                        for k in range(j + 1, min(j + 10, len(lines))):
                            if '.close()' in lines[k]:
                                has_finally_close = True
                                break
                            # finally 블록 벗어남 감지
                            if lines[k].strip() and not lines[k].startswith(' ' * 8) and not lines[k].startswith('\t\t'):
                                break
                        break
                    # 새 함수/클래스 시작이면 중단
                    if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                        break
                
                # with closing() 패턴 확인
                has_closing = 'closing(sqlite3.connect' in line or 'closing( sqlite3.connect' in line
                
                if not has_finally_close and not has_closing:
                    warnings.append({
                        'file': rel_path,
                        'line': i,
                        'content': line.strip()[:80],
                        'message': 'sqlite3.connect()에 finally: conn.close() 없음'
                    })
    
    return warnings


def check_bare_except():
    """[6/6] bare except: (구체적 예외 타입 없음) 새 코드 검사
    
    위험 패턴:
      ⚠️ except:          → SystemExit, KeyboardInterrupt 삼킴
    안전 패턴:
      ✅ except Exception: → SystemExit 등 보존
      ✅ except Exception as e:
      ✅ except (ValueError, TypeError):
    """
    warnings = []
    staged_files = _get_staged_files()
    
    if not staged_files:
        return warnings
    
    for rel_path in staged_files:
        filepath = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(filepath):
            continue
        
        added_lines = _get_staged_diff_lines(rel_path)
        if not added_lines:
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            continue
        
        for i, line in enumerate(lines, 1):
            if i not in added_lines:
                continue
            
            # bare except: 패턴 (except 뒤에 아무 타입 없이 콜론)
            if re.match(r'^\s*except\s*:\s*$', line):
                warnings.append({
                    'file': rel_path,
                    'line': i,
                    'content': line.strip(),
                    'message': 'bare except: → except Exception: 으로 변경 권장'
                })
    
    return warnings


def check_strategy_examiner_integrity():
    """[7/8] strategy_examiner.py 구조 무결성 검사
    
    검사 항목:
    - SIGNAL_DIRECTION dict 존재 및 최소 키 수
    - run_full_exam() 반환 필드 완전성
    - kill_switch 로직 존재
    - TECH_STRATEGIES에 매핑된 모듈 파일 존재
    """
    errors = []
    filepath = os.path.join(BASE_DIR, 'strategy_examiner.py')
    
    if not os.path.exists(filepath):
        errors.append({'message': 'strategy_examiner.py 파일 없음'})
        return errors
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. SIGNAL_DIRECTION dict 최소 키 수 (80개 이상 예상)
    sig_keys = re.findall(r"'([A-Z_]+)':\s*[+-]?[01]", content)
    if len(sig_keys) < 50:
        errors.append({
            'message': f'SIGNAL_DIRECTION 키 수 부족: {len(sig_keys)}개 (최소 50개 필요)'
        })
    
    # 2. run_full_exam 반환 필드 완전성
    required_return_fields = [
        'final_score', 'tech', 'structural', 'fundamental',
        'sentiment', 'macro', 'kill_switch', 'strategy_details'
    ]
    exam_return_section = content[content.find("return {", content.find("def run_full_exam")):]
    exam_return_section = exam_return_section[:exam_return_section.find('}') + 1]
    
    for field in required_return_fields:
        if f"'{field}'" not in exam_return_section:
            errors.append({
                'message': f"run_full_exam() 반환값에 '{field}' 필드 누락"
            })
    
    # 3. check_kill_switch 메서드 존재
    if 'def check_kill_switch' not in content:
        errors.append({'message': 'check_kill_switch() 메서드 없음'})
    
    # 4. WEIGHTS dict에 5개 과목군 존재
    for subject in ['tech', 'structural', 'fundamental', 'sentiment', 'macro']:
        pattern = rf"['\"]?{subject}['\"]?\s*:"
        weights_section = content[content.find('WEIGHTS'):content.find('WEIGHTS') + 300] if 'WEIGHTS' in content else ''
        if subject not in weights_section:
            errors.append({
                'message': f"WEIGHTS dict에 '{subject}' 과목군 누락"
            })
    
    # 5. TECH_STRATEGIES 매핑 모듈 파일 존재
    tech_section = ''
    if 'TECH_STRATEGIES' in content:
        ts_start = content.find('TECH_STRATEGIES')
        ts_end = content.find('}', ts_start)
        if ts_end > ts_start:
            tech_section = content[ts_start:ts_end + 1]
    tech_modules = re.findall(r"'(strategy_\w+)'", tech_section)
    for mod in tech_modules:
        mod_file = os.path.join(BASE_DIR, f'{mod}.py')
        if not os.path.exists(mod_file):
            errors.append({
                'message': f"TECH_STRATEGIES 매핑 모듈 파일 없음: {mod}.py"
            })
    
    return errors


def check_earnings_quality_integrity():
    """[8/8] earnings_quality.py 구조 무결성 검사
    
    검사 항목:
    - _classify_profit_status 4분기 완전성 (normal/non_recurring/full_loss/tax_or_oneoff)
    - quality_multiplier 범위 0.3~1.0
    - ORDER BY fiscal_year DESC 사용
    """
    errors = []
    filepath = os.path.join(BASE_DIR, 'earnings_quality.py')
    
    if not os.path.exists(filepath):
        errors.append({'message': 'earnings_quality.py 파일 없음'})
        return errors
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. _classify_profit_status 4가지 분기 완전성
    required_flags = ['normal', 'non_recurring', 'full_loss', 'tax_or_oneoff']
    classify_section = ''
    if '_classify_profit_status' in content:
        start = content.find('def _classify_profit_status')
        # 다음 def까지
        next_def = content.find('\n    def ', start + 1)
        if next_def > start:
            classify_section = content[start:next_def]
    
    for flag in required_flags:
        if f"'{flag}'" not in classify_section:
            errors.append({
                'message': f"_classify_profit_status에 '{flag}' 분기 누락"
            })
    
    # 2. _calc_multiplier 범위 검증 (0.3 이상, 1.0 이하)
    multiplier_section = ''
    if '_calc_multiplier' in content:
        start = content.find('def _calc_multiplier')
        next_def = content.find('\n    def ', start + 1)
        if next_def > start:
            multiplier_section = content[start:next_def]
        else:
            multiplier_section = content[start:]
    
    # return 값에서 상수 추출
    multiplier_returns = re.findall(r'return\s+([\d.]+)', multiplier_section)
    for val_str in multiplier_returns:
        val = float(val_str)
        if val < 0.3 or val > 1.0:
            errors.append({
                'message': f"_calc_multiplier 반환값 {val}이 범위(0.3~1.0) 초과"
            })
    
    # 3. ORDER BY fiscal_year DESC 사용 여부
    if 'ORDER BY' in content and 'fiscal_year' in content:
        # fiscal_year를 사용하는 ORDER BY에서 DESC 확인
        if re.search(r'ORDER BY\s+fiscal_year\s+DESC', content, re.IGNORECASE):
            pass  # 정상
        elif re.search(r'ORDER BY\s+fiscal_year', content, re.IGNORECASE):
            errors.append({
                'message': 'ORDER BY fiscal_year에 DESC 누락 (최신 연도 우선 필요)'
            })
    
    return errors


def check_trade_log_strategy_quality():
    """[9/13] trade_log 전략 귀속률 검사
    
    Unknown/외부주문 비율이 5% 초과 시 경고.
    버그 #1~#3 재발 조기 감지용.
    """
    warnings = []
    db_path = os.path.join(BASE_DIR, 'trading_system.db')
    
    if not os.path.exists(db_path):
        return warnings  # DB 없으면 스킵
    
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM trade_log")
            total = c.fetchone()[0]
            
            if total < 10:
                return warnings  # 데이터 부족 시 스킵
            
            c.execute("SELECT COUNT(*) FROM trade_log WHERE strategy IN ('Unknown', '외부주문')")
            bad_count = c.fetchone()[0]
            
            ratio = bad_count / total * 100
            if ratio > 5.0:
                warnings.append({
                    'message': f'trade_log 전략 미귀속: {bad_count}/{total}건 ({ratio:.1f}%) - 목표 5% 이하',
                    'detail': 'auto_trader._pending_executions 또는 _add_holding() strategy 전달 확인 필요'
                })
    except Exception:
        pass  # DB 접근 실패 시 무시
    
    return warnings


def check_trade_log_investment_type_quality():
    """[10/13] trade_log investment_type 정합성 검사
    
    investment_type='수동'인데 strategy가 유효한 전략인 건 = 분류 오류.
    """
    warnings = []
    db_path = os.path.join(BASE_DIR, 'trading_system.db')
    
    if not os.path.exists(db_path):
        return warnings
    
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM trade_log")
            total = c.fetchone()[0]
            
            if total < 10:
                return warnings
            
            # 유효 전략인데 수동으로 분류된 건
            c.execute("""
                SELECT COUNT(*) FROM trade_log 
                WHERE investment_type = '수동' 
                AND strategy NOT IN ('Unknown', '외부주문', '키움동기화')
            """)
            mismatch = c.fetchone()[0]
            
            if mismatch > 0:
                warnings.append({
                    'message': f'trade_log 타입 불일치: {mismatch}건 (유효전략+수동)',
                    'detail': 'investment_type 분류 로직 확인 필요'
                })
            
            # 전체 수동 비율
            c.execute("SELECT COUNT(*) FROM trade_log WHERE investment_type = '수동'")
            manual_count = c.fetchone()[0]
            ratio = manual_count / total * 100
            if ratio > 5.0:
                warnings.append({
                    'message': f'trade_log 수동 비율: {manual_count}/{total}건 ({ratio:.1f}%) - 목표 5% 이하',
                    'detail': 'auto_trader의 investment_type 설정 확인 필요'
                })
    except Exception:
        pass
    
    return warnings


def check_loop_api_no_sleep():
    """[12/12] 루프 내 API 호출에 sleep 누락 검사 (새 코드 대상)

    BEFORE_CODING.md 원칙:
      "루프 내 외부 API 호출이 있는가? → time.sleep() 또는 배치 간격 필수"
    """
    warnings = []
    staged_files = _get_staged_files()
    if not staged_files:
        return warnings

    api_patterns = ['requests.get(', 'requests.post(', '.get_stock_ohlcv(',
                    '.get_market_ohlcv', '.get_market_cap', 'get_fallen_stocks(']

    for rel_path in staged_files:
        filepath = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(filepath):
            continue
        added_lines = _get_staged_diff_lines(rel_path)
        if not added_lines:
            continue
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            continue

        # 루프 시작 위치 추적
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not (stripped.startswith('for ') or stripped.startswith('while ')) or ':' not in stripped:
                continue
            # 루프 내부에서 API 호출 검색 (30줄 이내)
            loop_indent = len(line) - len(line.lstrip())
            for j in range(i + 1, min(len(lines), i + 30)):
                lj = lines[j]
                lj_indent = len(lj) - len(lj.lstrip())
                if lj.strip() and lj_indent <= loop_indent:
                    break  # 루프 밖
                if (j + 1) not in added_lines:
                    continue  # 새 코드만
                if any(pat in lj for pat in api_patterns):
                    has_sleep = any('sleep' in lines[k] for k in range(max(0, j - 5), min(len(lines), j + 10)))
                    if not has_sleep:
                        warnings.append({
                            'file': rel_path,
                            'line': j + 1,
                            'content': lj.strip()[:80],
                            'message': '루프 내 API 호출에 sleep() 없음'
                        })
    return warnings


def check_64bit_module_in_32bit_path():
    """32bit 프로세스 코드에서 64bit 전용 모듈 직접 import 검사.
    
    ml_predictor는 sklearn 의존 → 32bit Python에 설치 불가.
    api/ 내에서 직접 import하면 안 되고, 반드시 64bit venv subprocess(_run_64bit_worker)를 사용해야 함.
    """
    SIXTY_FOUR_BIT_ONLY_MODULES = ['ml_predictor']
    ALLOWED_PATHS = ['workers', 'ml_worker']  # 64bit 워커 디렉토리는 허용
    
    errors = []
    base = os.path.dirname(os.path.abspath(__file__))
    
    for py_file in glob.glob(os.path.join(base, 'api', '**', '*.py'), recursive=True):
        rel = os.path.relpath(py_file, base)
        # workers 디렉토리는 64bit 전용이므로 제외
        if any(allowed in rel for allowed in ALLOWED_PATHS):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    for mod in SIXTY_FOUR_BIT_ONLY_MODULES:
                        if f'from {mod} import' in stripped or f'import {mod}' in stripped:
                            errors.append({
                                'file': rel,
                                'line': i,
                                'module': mod,
                                'content': stripped[:80]
                            })
        except Exception:
            continue
    
    # ModuleLoader에서 64bit 전용 모듈 로드도 검사
    core_path = os.path.join(base, 'api', 'core.py')
    if os.path.exists(core_path):
        try:
            with open(core_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    for mod in SIXTY_FOUR_BIT_ONLY_MODULES:
                        if f"name == '{mod}'" in stripped or f'name == "{mod}"' in stripped:
                            errors.append({
                                'file': 'api/core.py',
                                'line': i,
                                'module': mod,
                                'content': f"ModuleLoader에서 {mod} 로드 시도 (32bit 프로세스에서 실행됨)"
                            })
        except Exception:
            pass
    
    return errors


def check_date_format_mismatch():
    """YYYYMMDD date 컨럼에 date('now') 함수 사용 검사 (형식 불일치 방지)
    
    date('now') = 'YYYY-MM-DD' 반환 vs DB date 컨럼 = 'YYYYMMDD'
    → 비교 시 항상 잘못된 결과 (<=는 항상 FALSE, >=는 항상 TRUE)
    올바른 사용: strftime('%Y%m%d', 'now', ...)
    
    예외: created_at 컨럼은 'YYYY-MM-DD HH:MM:SS' 형식이므로 date() 사용 가능
    """
    warnings = []
    # 스캔 대상: 새 코드 (staged) 대신 전체 .py 스캔 (재발 방지 목적)
    exclude = ('bt_', 'test_', '_check', 'venv', '__pycache__', 'archive',
               'pre_commit_check.py')
    
    # date('now' 패턴 탐지 (정규식)
    # created_at/navigated_at/analysis_date/updated_at/executed_at/start_time/viewed_at 칸럼은 예외
    datetime_cols = ('created_at', 'navigated_at', 'analysis_date', 'updated_at',
                     'executed_at', 'start_time', 'viewed_at', 'modifiedTime')
    pattern = re.compile(r"""\bdate\s*\(\s*['"]now['"]""")
    
    for root, dirs, files in os.walk(BASE_DIR):
        # 제외 디렉토리
        dirs[:] = [d for d in dirs if d not in ('venv', '__pycache__', '.git',
                                                 'archive', 'node_modules')]
        for fname in files:
            if not fname.endswith('.py'):
                continue
            if any(fname.startswith(ex) for ex in exclude):
                continue
            
            fpath = os.path.join(root, fname)
            try:
                lines = open(fpath, encoding='utf-8').readlines()
            except Exception:
                continue
            
            for i, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                # created_at 등 datetime 컨럼 비교는 예외
                stripped = line.strip()
                if any(col in stripped for col in datetime_cols):
                    continue
                # 주석 제외
                if stripped.startswith('#'):
                    continue
                # strftime('%Y%m%d', date('now',...)) 패턴은 정상 (외부 strftime이 변환)
                if "strftime('%Y%m%d'" in stripped or 'strftime("%Y%m%d"' in stripped:
                    continue
                
                rel = os.path.relpath(fpath, BASE_DIR)
                warnings.append({
                    'file': rel,
                    'line': i + 1,
                    'content': stripped[:120],
                    'message': ("date('now') → YYYY-MM-DD 반환. "
                                "YYYYMMDD date 컨럼과 비교 시 strftime('%Y%m%d','now',...) 사용 필요")
                })
    
    return warnings


def main():
    print("=" * 60)
    print("StockAnalyst 커밋 전 코드 검증")
    print("=" * 60)
    print()
    
    has_error = False
    has_warning = False
    
    # 1. ORDER BY date DESC 검사
    print("[1/13] ORDER BY date DESC 검사 (스캔 테이블)...")
    errors = check_order_by_date_desc()
    if errors:
        has_error = True
        print(f"  ❌ {len(errors)}개 오류 발견!")
        for e in errors:
            print(f"     {e['file']}:{e['line']} - {e['table']}")
            print(f"        {e['content']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 2. created_at 누락 검사
    print("[2/13] created_at 컬럼 검사 (INSERT 문)...")
    warnings = check_created_at_missing()
    if warnings:
        has_warning = True
        print(f"  ⚠️ {len(warnings)}개 경고!")
        for w in warnings:
            print(f"     {w['file']}:{w['line']} - {w['table']}: {w['message']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 3. PyQt 시그니처 순서 검사
    print("[3/13] PyQt 시그니처 순서 검사...")
    slot_warnings = check_pyqt_slot_order()
    if slot_warnings:
        has_warning = True
        print(f"  ⚠️ {len(slot_warnings)}개 경고!")
        for w in slot_warnings:
            print(f"     {w['file']}:{w['line']} - {w['message']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 4. 전략 모듈 메서드 존재 검사
    print("[4/13] 전략 모듈 KRXDataClient 메서드 검사...")
    method_errors = check_strategy_method_exists()
    if method_errors:
        has_error = True
        print(f"  ❌ {len(method_errors)}개 오류 발견!")
        for e in method_errors:
            print(f"     {e['file']}:{e['line']} - KRXDataClient.{e['method']}() 없음")
            print(f"        {e['content']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 5. DB 커넥션 누수 검사 (staged 파일 대상)
    print("[5/13] DB 커넥션 누수 검사 (새 코드)...")
    leak_warnings = check_db_connection_leak()
    if leak_warnings:
        has_warning = True
        print(f"  ⚠️ {len(leak_warnings)}개 경고!")
        for w in leak_warnings:
            print(f"     {w['file']}:{w['line']} - {w['message']}")
            print(f"        {w['content']}")
        print("     💡 권장: try: ... finally: conn.close() 또는 with closing(sqlite3.connect()) as conn:")
    else:
        print("  ✅ 통과")
    print()
    
    # 6. bare except 검사 (staged 파일 대상)
    print("[6/13] bare except 검사 (새 코드)...")
    bare_warnings = check_bare_except()
    if bare_warnings:
        has_warning = True
        print(f"  ⚠️ {len(bare_warnings)}개 경고!")
        for w in bare_warnings:
            print(f"     {w['file']}:{w['line']} - {w['message']}")
        print("     💡 권장: except Exception as e: 으로 변경")
    else:
        print("  ✅ 통과")
    print()
    
    # 7. strategy_examiner.py 구조 무결성 검사
    print("[7/13] strategy_examiner.py 구조 검사...")
    examiner_errors = check_strategy_examiner_integrity()
    if examiner_errors:
        has_error = True
        print(f"  ❌ {len(examiner_errors)}개 오류 발견!")
        for e in examiner_errors:
            print(f"     {e['message']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 8. earnings_quality.py 구조 무결성 검사
    print("[8/13] earnings_quality.py 구조 검사...")
    eq_errors = check_earnings_quality_integrity()
    if eq_errors:
        has_error = True
        print(f"  ❌ {len(eq_errors)}개 오류 발견!")
        for e in eq_errors:
            print(f"     {e['message']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 9. trade_log 전략 귀속률 검사
    print("[9/13] trade_log 전략 귀속률 검사...")
    tl_strategy_warnings = check_trade_log_strategy_quality()
    if tl_strategy_warnings:
        has_warning = True
        print(f"  ⚠️ {len(tl_strategy_warnings)}개 경고!")
        for w in tl_strategy_warnings:
            print(f"     {w['message']}")
            print(f"     💡 {w['detail']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 10. trade_log investment_type 정합성 검사
    print("[10/13] trade_log investment_type 정합성 검사...")
    tl_type_warnings = check_trade_log_investment_type_quality()
    if tl_type_warnings:
        has_warning = True
        print(f"  ⚠️ {len(tl_type_warnings)}개 경고!")
        for w in tl_type_warnings:
            print(f"     {w['message']}")
            print(f"     💡 {w['detail']}")
    else:
        print("  ✅ 통과")
    print()
    
    # 11. 64bit 전용 모듈 32bit import 검사
    print("[11/13] 64bit 전용 모듈 32bit import 검사...")
    arch_errors = check_64bit_module_in_32bit_path()
    if arch_errors:
        has_error = True
        print(f"  ❌ {len(arch_errors)}개 오류!")
        for e in arch_errors:
            print(f"     {e['file']}:{e['line']} - {e['module']}: {e['content']}")
            print(f"     💡 64bit venv subprocess(_run_64bit_worker) 사용 필요")
    else:
        print("  ✅ 통과")
    print()
    
    # 12. 루프 내 API sleep 누락 검사
    print("[12/13] 루프 내 API sleep 누락 검사 (새 코드)...")
    loop_warnings = check_loop_api_no_sleep()
    if loop_warnings:
        has_warning = True
        print(f"  ⚠️ {len(loop_warnings)}개 경고!")
        for w in loop_warnings:
            print(f"     {w['file']}:{w['line']} - {w['message']}")
            print(f"        {w['content']}")
        print("     💡 권장: time.sleep() 또는 배치 간격 추가")
    else:
        print("  ✅ 통과")
    print()

    # 13. YYYYMMDD date 컨럼에 date('now') 함수 사용 검사
    print("[13/13] YYYYMMDD date 컨럼 date('now') 형식 불일치 검사...")
    date_warnings = check_date_format_mismatch()
    if date_warnings:
        has_error = True
        print(f"  ❌ {len(date_warnings)}개 오류! (date('now')→YYYY-MM-DD vs YYYYMMDD 비교 불가)")
        for w in date_warnings:
            print(f"     {w['file']}:{w['line']} - {w['content']}")
        print("     💡 strftime('%Y%m%d','now',...) 사용 필요. created_at 컨럼은 예외.")
    else:
        print("  ✅ 통과")
    print()

    # 결과
    print("=" * 60)
    if has_error:
        print("❌ 오류가 있습니다. 수정 후 커밋하세요!")
        return 1
    elif has_warning:
        print("⚠️ 경고가 있습니다. 확인 후 커밋하세요.")
        return 0
    else:
        print("✅ 모든 검사 통과!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
