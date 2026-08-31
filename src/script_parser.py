# script_parser.py
import re
import datetime as dt

# 날짜 줄 형식: "2026-8-12 수 출근" / "2026-8-15 토 아침" 등
# (연-월-일)(요일 한글자)(시기: 자유형식)
DATE_LINE_RE = re.compile(r'^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\S)\s+(\S+)\s*$')

# 주말은 "출근" 대신 "아침"이라는 라벨을 쓰는데, 실질적으로는 같은 시간대(오전)이므로
# 파싱 단계에서 아예 "출근"으로 통일. 이후 파일명/예약 시각 등 모든 곳에서
# 별도 처리 없이 "출근"으로만 다루면 됨.
TIME_TYPE_ALIASES = {
    "아침": "출근",
}


def _parse_date_field(raw: str):
    raw = raw.strip()
    m = DATE_LINE_RE.match(raw)
    if not m:
        raise ValueError(
            f"날짜 형식을 인식할 수 없습니다: '{raw}' "
            f"(예: '2026-8-12 수 출근')"
        )
    y, mo, d, _weekday, time_type = m.groups()
    time_type = TIME_TYPE_ALIASES.get(time_type, time_type)
    date_obj = dt.date(int(y), int(mo), int(d))
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
            m = re.match(r'\*\*(.+?):\*\*\s*(.*)', line)
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
