# -*- coding: utf-8 -*-
"""
스냅샷 테스트 - 핵심 API 응답 캡처 및 비교
수정 전후 API 응답 변경 감지용

사용법:
  python snapshot_test.py capture   # 현재 상태 캡처
  python snapshot_test.py compare   # 캡처된 스냅샷과 비교
  python snapshot_test.py show      # 저장된 스냅샷 표시
"""
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

SNAPSHOT_FILE = BASE_DIR / "api_snapshot.json"

# ============================================================
# 테스트할 API 함수 목록
# ============================================================
def get_api_tests():
    """테스트할 API 함수 정의"""
    tests = {}
    
    # 1. market_utils
    def test_get_last_business_day():
        from market_utils import get_last_business_day
        return get_last_business_day()
    tests["get_last_business_day"] = test_get_last_business_day
    
    # 2. ApiResponse 구조
    def test_api_response_success():
        from api.core import ApiResponse
        return json.loads(ApiResponse.success({"test": "data"}))
    tests["ApiResponse.success_structure"] = test_api_response_success
    
    def test_api_response_error():
        from api.core import ApiResponse
        return json.loads(ApiResponse.error("test error"))
    tests["ApiResponse.error_structure"] = test_api_response_error
    
    # 3. DB 테이블 스키마
    def test_strategy_recommendations_schema():
        import sqlite3
        conn = sqlite3.connect(BASE_DIR / "trading_system.db")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(strategy_recommendations)")
            cols = [r[1] for r in cursor.fetchall()]
        finally:
            conn.close()
        return cols
    tests["strategy_recommendations_schema"] = test_strategy_recommendations_schema
    
    def test_unified_rankings_schema():
        import sqlite3
        conn = sqlite3.connect(BASE_DIR / "trading_system.db")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(unified_rankings)")
            cols = [r[1] for r in cursor.fetchall()]
        finally:
            conn.close()
        return cols
    tests["unified_rankings_schema"] = test_unified_rankings_schema
    
    def test_trade_log_schema():
        import sqlite3
        conn = sqlite3.connect(BASE_DIR / "trading_system.db")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(trade_log)")
            cols = [r[1] for r in cursor.fetchall()]
        finally:
            conn.close()
        return cols
    tests["trade_log_schema"] = test_trade_log_schema
    
    # 4. 설정 파일 구조
    def test_settings_keys():
        path = BASE_DIR / "settings.json"
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return sorted(data.keys())
        return []
    tests["settings_json_keys"] = test_settings_keys
    
    # 5. 전략 목록 (api_bridge에서 가져오기 어려우므로 하드코딩된 목록 확인)
    def test_strategy_modules():
        modules = []
        for name in ['smc_core', 'abcd_pattern_v2', 'bb_squeeze_v2', 
                     'strategy_rs_v2', 'whale_cvd', 'sector_rotation_scanner']:
            try:
                __import__(name)
                modules.append(name)
            except Exception as e:
                pass
        return modules
    tests["strategy_modules_available"] = test_strategy_modules
    
    return tests


def capture_snapshot():
    """현재 API 상태를 캡처하여 저장"""
    print("=" * 60)
    print("[SNAPSHOT] API 상태 캡처 중...")
    print("=" * 60)
    
    tests = get_api_tests()
    snapshot = {
        "captured_at": datetime.now().isoformat(),
        "results": {}
    }
    
    for name, func in tests.items():
        try:
            result = func()
            # JSON 직렬화 가능하도록 변환
            if isinstance(result, (list, dict, str, int, float, bool, type(None))):
                snapshot["results"][name] = {
                    "status": "ok",
                    "value": result,
                    "hash": hashlib.md5(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:8]
                }
            else:
                snapshot["results"][name] = {
                    "status": "ok",
                    "value": str(result),
                    "hash": hashlib.md5(str(result).encode()).hexdigest()[:8]
                }
            print(f"  [OK] {name}")
        except Exception as e:
            snapshot["results"][name] = {
                "status": "error",
                "error": str(e)[:100]
            }
            print(f"  [FAIL] {name}: {str(e)[:50]}")
    
    # 저장
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n[SAVED] {SNAPSHOT_FILE}")
    print(f"[INFO] 캡처된 항목: {len(snapshot['results'])}개")
    
    return snapshot


def compare_snapshot():
    """저장된 스냅샷과 현재 상태 비교"""
    print("=" * 60)
    print("[COMPARE] 스냅샷 비교 중...")
    print("=" * 60)
    
    if not SNAPSHOT_FILE.exists():
        print("[ERROR] 스냅샷 파일이 없습니다. 먼저 'capture' 실행하세요.")
        return False
    
    saved = json.loads(SNAPSHOT_FILE.read_text(encoding='utf-8'))
    print(f"[INFO] 스냅샷 시간: {saved['captured_at']}")
    
    tests = get_api_tests()
    changes = []
    matches = 0
    errors = 0
    
    for name, func in tests.items():
        saved_result = saved["results"].get(name, {})
        
        try:
            current = func()
            
            # 현재 값의 해시 계산
            if isinstance(current, (list, dict, str, int, float, bool, type(None))):
                current_hash = hashlib.md5(json.dumps(current, sort_keys=True, default=str).encode()).hexdigest()[:8]
            else:
                current_hash = hashlib.md5(str(current).encode()).hexdigest()[:8]
            
            saved_hash = saved_result.get("hash", "")
            
            if saved_result.get("status") == "error":
                print(f"  [NEW] {name} - 이전에 에러였음, 현재 정상")
                changes.append((name, "error->ok"))
            elif current_hash == saved_hash:
                print(f"  [OK] {name}")
                matches += 1
            else:
                print(f"  [CHANGED] {name}")
                print(f"      이전: {str(saved_result.get('value', ''))[:60]}")
                print(f"      현재: {str(current)[:60]}")
                changes.append((name, "value_changed"))
                
        except Exception as e:
            if saved_result.get("status") == "ok":
                print(f"  [BROKEN] {name} - 이전 정상, 현재 에러: {str(e)[:40]}")
                changes.append((name, f"ok->error: {str(e)[:30]}"))
                errors += 1
            else:
                print(f"  [STILL_ERROR] {name}")
                errors += 1
    
    # 요약
    print("\n" + "=" * 60)
    print("[SUMMARY]")
    print("=" * 60)
    print(f"  일치: {matches}개")
    print(f"  변경: {len(changes)}개")
    print(f"  에러: {errors}개")
    
    if changes:
        print("\n[CHANGES]")
        for name, change_type in changes:
            print(f"  - {name}: {change_type}")
        return False
    else:
        print("\n[OK] 모든 API가 스냅샷과 일치합니다!")
        return True


def show_snapshot():
    """저장된 스냅샷 표시"""
    if not SNAPSHOT_FILE.exists():
        print("[ERROR] 스냅샷 파일이 없습니다.")
        return
    
    saved = json.loads(SNAPSHOT_FILE.read_text(encoding='utf-8'))
    print("=" * 60)
    print(f"[SNAPSHOT] 캡처 시간: {saved['captured_at']}")
    print("=" * 60)
    
    for name, data in saved["results"].items():
        status = data.get("status", "unknown")
        if status == "ok":
            value = data.get("value", "")
            hash_val = data.get("hash", "")
            print(f"\n[{name}] hash={hash_val}")
            print(f"  값: {str(value)[:80]}")
        else:
            print(f"\n[{name}] ERROR")
            print(f"  에러: {data.get('error', 'unknown')}")


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python snapshot_test.py capture  - 현재 상태 캡처")
        print("  python snapshot_test.py compare  - 스냅샷과 비교")
        print("  python snapshot_test.py show     - 스냅샷 표시")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "capture":
        capture_snapshot()
    elif cmd == "compare":
        success = compare_snapshot()
        sys.exit(0 if success else 1)
    elif cmd == "show":
        show_snapshot()
    else:
        print(f"[ERROR] 알 수 없는 명령: {cmd}")
        print("  사용 가능: capture, compare, show")


if __name__ == "__main__":
    main()
