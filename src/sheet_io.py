# sheet_io.py
import os
import time
import datetime as dt

import gspread

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON", "service_account.json")


def parse_korean_date(date_str: str) -> dt.date:
    """스프레드시트 날짜 문자열/시리얼 → date 객체."""
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    try:
        serial = float(date_str)
        base = dt.date(1899, 12, 30)
        return base + dt.timedelta(days=serial)
    except Exception:
        raise ValueError(f"알 수 없는 날짜 형식: {date_str}")


def connect_sheet(max_retries: int = 5, base_delay: float = 2.0):
    """서비스 계정으로 kobible 워크시트 연결.

    Google Sheets API가 일시적으로 503/500/429를 반환하는 경우가 있어
    지수 백오프(exponential backoff) 방식으로 자동 재시도한다.
    재시도해도 의미 없는 오류(권한 오류 403, 잘못된 요청 400 등)는
    즉시 그대로 전파한다.
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            gc = gspread.service_account(filename=SERVICE_ACCOUNT_JSON)
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("kobible")
            return ws
        except gspread.exceptions.APIError as e:
            last_err = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (503, 500, 429) or status is None:
                delay = base_delay * (2 ** (attempt - 1))
                print(
                    f"[connect_sheet] 재시도 {attempt}/{max_retries} "
                    f"- {e} - {delay:.0f}초 대기"
                )
                if attempt < max_retries:
                    time.sleep(delay)
                continue
            # 403, 400 등 재시도해도 소용없는 오류는 즉시 전파
            raise

    raise RuntimeError(
        f"connect_sheet: {max_retries}회 재시도 후에도 연결 실패"
    ) from last_err


DEBUG_SHEET = False


def fetch_row_from_sheet(target_date, target_time_type):
    """날짜 + 시기(출근/자기전)에 해당하는 행에서 5개 필드 반환."""
    ws = connect_sheet()
    records = ws.get_all_records()

    if DEBUG_SHEET:
        print(f"[DEBUG] 전체 행 수: {len(records)}")
        print(f"[DEBUG] 찾는 날짜: {target_date}, 시기: {target_time_type}")

    candidate = None

    for rec in records:
        date_str = str(rec.get("날짜", "")).strip()
        time_type = str(rec.get("시기", "")).strip()

        try:
            row_date = parse_korean_date(date_str)
        except ValueError:
            continue

        if DEBUG_SHEET:
            print(f"[DEBUG] row_date={row_date}, time_type={time_type}, title={rec.get('제목','')}")

        if row_date == target_date and time_type == target_time_type:
            title = str(rec.get("제목", "")).strip()
            verse = str(rec.get("말씀", "")).strip()
            content = str(rec.get("말씀 내용", "")).strip()
            script60 = str(rec.get("60초 스크립트", "")).strip()
            subscribe = str(rec.get("구독", "")).strip()
            return title, verse, content, script60, subscribe

        if row_date == target_date and candidate is None:
            candidate = rec

    if candidate:
        raise RuntimeError(
            f"{target_date} / {target_time_type} 행은 없지만, "
            f"같은 날짜의 다른 시기 행은 있습니다. 시기 값을 다시 확인해 주세요."
        )
    else:
        raise RuntimeError(f"{target_date} 날짜 자체가 시트에 없습니다.")
