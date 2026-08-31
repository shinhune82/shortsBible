# text_render.py
import os
import numpy as np

from PIL import Image, ImageDraw, ImageFont
import moviepy as mp

VIDEO_SIZE = (1080, 1920)
FONT_PATH = os.getenv("FONT_PATH", "C:/Windows/Fonts/malgunbd.ttf")

ImageClip = mp.ImageClip

# 유튜브 쇼츠 자체 UI(좋아요/댓글/공유 버튼, 제목/채널명 캡션 영역)를
# 피하기 위한 안전 여백(px). 실제 화면(1080x1920 기준)에서
# 우측 버튼 컬럼과 하단 캡션 영역을 넉넉히 피하도록 잡았습니다.
RIGHT_SAFE_MARGIN = 140
BOTTOM_SAFE_MARGIN = 280
LEFT_SAFE_MARGIN = 40
TOP_SAFE_MARGIN = 40


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    font_path = FONT_PATH if os.path.exists(FONT_PATH) else None
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def _resolve_position(position, img_w, img_h):
    """
    position 튜플의 'right' / 'bottom' / 'left' / 'top' 을
    화면 끝에 딱 붙이는 대신, 유튜브 쇼츠 UI를 피한 좌표(px)로 변환.
    'center' 는 기존처럼 moviepy가 알아서 처리하도록 문자열 그대로 둠.
    숫자나 그 외 값은 그대로 통과시킴.
    """
    h_pos, v_pos = position

    if h_pos == "right":
        x = VIDEO_SIZE[0] - img_w - RIGHT_SAFE_MARGIN
    elif h_pos == "left":
        x = LEFT_SAFE_MARGIN
    else:
        x = h_pos  # "center" 등은 그대로 통과

    if v_pos == "bottom":
        y = VIDEO_SIZE[1] - img_h - BOTTOM_SAFE_MARGIN
    elif v_pos == "top":
        y = TOP_SAFE_MARGIN
    else:
        y = v_pos  # "center" 등은 그대로 통과

    return (x, y)


def make_text_image_clip(
    text: str,
    duration: float,
    fontsize: int = 60,
    position=("center", "center"),
    max_width_ratio: float = 0.8,
    with_label_split: bool = False,
    label_color=(255, 255, 255, 255),
):
    """
    Pillow 로 (반투명 검정 박스 + 흰 글자) 이미지를 만들고 ImageClip 으로 반환.
    with_label_split=True 이면 첫 줄을 '라벨'로 보고 스타일 분리.
    label_color 로 라벨 줄(첫 줄)의 색을 따로 지정 가능 (기본은 흰색).
    """
    if not text:
        text = ""

    base_font = _load_font(fontsize)
    label_font = _load_font(int(fontsize * 0.8))

    dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)

    max_width_px = int(VIDEO_SIZE[0] * max_width_ratio)

    # 1) 라벨/본문 분리
    if with_label_split:
        raw_lines = text.split("\n", 1)
        label_line = raw_lines[0]
        body_text = raw_lines[1] if len(raw_lines) > 1 else ""
    else:
        label_line = ""
        body_text = text

    # 2) 본문 줄바꿈
    body_lines = []
    if body_text:
        words = body_text.split()
        current = ""
        for w in words:
            test = (current + " " + w).strip()
            left, top, right, bottom = draw.textbbox((0, 0), test, font=base_font)
            if right - left <= max_width_px or not current:
                current = test
            else:
                body_lines.append(current)
                current = w
        if current:
            body_lines.append(current)

    # 3) 전체 줄 구성
    all_lines = []
    if label_line:
        all_lines.append(("label", label_line))
    if body_lines:
        for ln in body_lines:
            all_lines.append(("body", ln))
    if not all_lines:
        all_lines.append(("body", text))

    # 4) 전체 크기 계산
    line_spacing = int(fontsize * 0.4)
    max_line_w = 0
    total_h = 0
    for kind, ln in all_lines:
        f = label_font if kind == "label" else base_font
        left, top, right, bottom = draw.textbbox((0, 0), ln, font=f)
        w, h = right - left, bottom - top
        max_line_w = max(max_line_w, w)
        total_h += h + line_spacing
    total_h -= line_spacing

    padding_x = 40
    padding_y = 20

    img_w = max_line_w + padding_x * 2
    img_h = total_h + padding_y * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 배경 박스 (50% 투명)
    box_color = (0, 0, 0, int(255 * 0.5))
    draw.rectangle([0, 0, img_w, img_h], fill=box_color)

    # 5) 한 줄씩 그리기
    y = padding_y
    for kind, ln in all_lines:
        f = label_font if kind == "label" else base_font
        left, top, right, bottom = draw.textbbox((0, 0), ln, font=f)
        w, h = right - left, bottom - top
        x = (img_w - w) // 2
        fill_color = label_color if kind == "label" else (255, 255, 255, 255)
        draw.text((x, y), ln, font=f, fill=fill_color)
        y += h + line_spacing

    img_array = np.array(img)
    resolved_position = _resolve_position(position, img_w, img_h)
    return ImageClip(img_array).with_duration(duration).with_position(resolved_position)


def make_label_clip(text, duration, fontsize=60, position=("center", "center"), label_color=(255, 255, 255, 255)):
    """제목/짧은 말씀용 (라벨/본문 분리 사용)."""
    return make_text_image_clip(
        text=text,
        duration=duration,
        fontsize=fontsize,
        position=position,
        max_width_ratio=0.9,
        with_label_split=True,
        label_color=label_color,
    )


def make_body_label_clip(text, duration, fontsize=50, position=("center", "center")):
    """라벨 + 본문을 모두 같은 서식(본문)으로 보여줄 때 사용 (60초 스크립트용)."""
    return make_text_image_clip(
        text=text,
        duration=duration,
        fontsize=fontsize,
        position=position,
        max_width_ratio=0.8,
        with_label_split=False,
    )


def make_labeled_body_clip(text, duration, fontsize=50, position=("center", "center")):
    """첫 화면 '말씀', '말씀 내용' 처럼 첫 줄을 라벨로 강조하고 싶을 때 사용."""
    return make_text_image_clip(
        text=text,
        duration=duration,
        fontsize=fontsize,
        position=position,
        max_width_ratio=0.8,
        with_label_split=True,
    )
