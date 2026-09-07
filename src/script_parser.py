# script_parser.py
import re
import datetime as dt

# 날짜 줄 형식 예시:
#   "2026-8-12 수 출근"      (연도 포함, 요일 뒤에 공백)
#   "09.09 (수) 아침"        (연도 없음, 요일 괄호로 감쌈)
# 공통 규칙: [날짜] [요일] [시기] 세 부분으로 구성. 요일은 표시용일 뿐 실제
# 계산엔 안 쓰고(날짜에서 재계산 가능), 연도가 없으면 오늘 날짜 기준으로
# 자동 추론(이미 지난 날짜면 내년으로 넘김).

# 주말은 "출근" 대신 "아침"이라는 라벨을 쓰는데, 실질적으로는 같은 시간대(오전)이므로
# 파싱 단계에서 아예 "출근"으로 통일. 이후 파일명/예약 시각 등 모든 곳에서
# 별도 처리 없이 "출근"으로만 다루면 됨.
TIME_TYPE_ALIASES = {
    "아침": "출근",
    "저녁": "자기전",
}


def _parse_date_component(date_str: str) -> dt.date:
    date_str = date_str.strip()

    # 연도 포함: 2026-8-12 / 2026.8.12
    m = re.match(r'^(\d{4})[-.](\d{1,2})[-.](\d{1,2})$', date_str)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return dt.date(y, mo, d)

    # 연도 없음: 09.09 / 9.9 / 09-09
    m = re.match(r'^(\d{1,2})[-.](\d{1,2})$', date_str)
    if m:
        mo, d = (int(x) for x in m.groups())
        today = dt.date.today()
        candidate = dt.date(today.year, mo, d)
        if candidate < today:
            candidate = dt.date(today.year + 1, mo, d)
        return candidate

    raise ValueError(f"날짜를 인식할 수 없습니다: '{date_str}'")


def _parse_date_field(raw: str):
    raw = raw.strip()
    # 괄호는 공백으로 치환해서 "09.09 (수) 아침" -> "09.09  수  아침" 처럼 통일
    cleaned = raw.replace("(", " ").replace(")", " ")
    tokens = cleaned.split()

    if len(tokens) < 3:
        raise ValueError(
            f"날짜 형식을 인식할 수 없습니다: '{raw}' "
            f"(예: '2026-8-12 수 출근' 또는 '09.09 (수) 아침')"
        )

    date_part = tokens[0]
    time_type = tokens[-1]
    # tokens[1:-1] 은 요일 표시라 실제로는 사용 안 함

    date_obj = _parse_date_component(date_part)
    time_type = TIME_TYPE_ALIASES.get(time_type, time_type)
    return date_obj, time_type


def parse_devotional_text(text: str):
    """
    아래 형식의 텍스트(여러 날짜/시기 블록을 '---' 로 구분)를 파싱해서
    [{date, time_type, title, verse, content, script60}, ...] 리스트로 반환.

    **날짜:** 2026-8-12 수 출근
    **제목:** 범사에 감사하는 삶
    **성경말씀:** 데살로니가전서 5장 18절
    **말씀내용:** 범사에 감사하라 ...
    **묵상:** 출근길, 오늘 하루도 ...
    ---
    (다음 블록)
    """
    text = (text or "").strip()
    if not text:
        return []

    blocks = re.split(r'\n\s*-{3,}\s*\n', text)
    entries = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        fields = {}
        current_key = None
        for line in block.split("\n"):
            line = line.rstrip()
            # "**날짜:** 값" 형식과 "날짜: 값" (별표 없는) 형식을 둘 다 인식
            m = re.match(r'^\*{0,2}([^\*:\n]+):\*{0,2}\s*(.*)$', line)
            if m:
                current_key = m.group(1).strip()
                fields[current_key] = m.group(2).strip()
            elif current_key is not None and line.strip():
                fields[current_key] = (fields.get(current_key, "") + " " + line.strip()).strip()

        if "날짜" not in fields:
            # 형식에 안 맞는 블록(빈 줄 뭉치 등)은 건너뜀
            continue

        date_obj, time_type = _parse_date_field(fields["날짜"])

        entries.append({
            "date": date_obj,
            "time_type": time_type,
            "title": fields.get("제목", "").strip(),
            "verse": fields.get("성경말씀", "").strip(),
            "content": fields.get("말씀내용", "").strip(),
            "script60": fields.get("묵상", "").strip(),
        })

    return entries


def parse_devotional_file(path: str):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return parse_devotional_text(text)
