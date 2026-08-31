# pages.py
import re
from typing import List

import moviepy as mp

from text_render import make_label_clip, make_body_label_clip, ImageClip, VIDEO_SIZE

CompositeVideoClip = mp.CompositeVideoClip
concatenate_videoclips = mp.concatenate_videoclips


def make_page(
    bg_path: str,
    title_text: str,
    body_text_list,
    title_fontsize: int = 80,
    body_fontsize: int = 60,
    each_duration: float = 3.0,
):
    """
    배경 이미지 하나에 여러 페이지(타이틀 + 본문)를 차례대로 붙인 클립.
    body_text_list: [("label", "내용"), ...]
    """
    pages = []

    bg = ImageClip(bg_path).resized(new_size=VIDEO_SIZE)

    # 제목 페이지
    title_clip = make_label_clip(
        title_text,
        each_duration,
        fontsize=title_fontsize,
        position=("center", "center"),
    )
    pages.append(CompositeVideoClip([bg, title_clip]).with_duration(each_duration))

    # 본문 페이지들
    for label, text in body_text_list:
        full_text = f"{label}\n{text}" if label else text
        txt_clip = make_body_label_clip(
            full_text,
            each_duration,
            fontsize=body_fontsize,
            position=("center", "center"),
        )
        pages.append(CompositeVideoClip([bg, txt_clip]).with_duration(each_duration))

    return concatenate_videoclips(pages)


# ---------- 60초 스크립트 분할 ----------

def split_script(script: str, max_chars: int = 40) -> List[str]:
    script = (script or "").strip()
    if not script:
        return []

    # 줄바꿈을 공백으로 통일
    script = script.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # 연속 공백 제거
    script = re.sub(r' +', ' ', script).strip()

    # 문장 분리
    sentences = re.split(r'(?<=[.!?。！？])\s*', script)

    chunks = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            while len(s) > max_chars:
                chunks.append(s[:max_chars])
                s = s[max_chars:]
            current = s.strip()

    if current:
        chunks.append(current)

    # 혹시 모를 빈 chunk 최종 필터링
    return [c for c in chunks if c.strip()]

def estimate_durations(chunks: List[str], total_audio_duration: float) -> List[float]:
    """
    전체 오디오 길이를 글자 수 비율에 따라 각 조각에 배분.
    """
    if not chunks:
        return []

    total_chars = sum(len(c) for c in chunks)
    durations = []
    for c in chunks:
        if total_chars > 0:
            ratio = len(c) / total_chars
        else:
            ratio = 1.0 / len(chunks)
        durations.append(total_audio_duration * ratio)
    return durations


def make_script_sequence(
    script_text: str,
    background_clip: mp.VideoClip,
    audio_clip: mp.AudioClip,
    font_size: int = 50,
    max_chars_per_chunk: int = 40,
):
    """
    60초 스크립트를 여러 페이지로 나누고, 오디오 길이에 맞춰 넘기는 시퀀스 생성.
    """
    chunks = split_script(script_text, max_chars=max_chars_per_chunk)
    if not chunks:
        # 자막 없이 배경 + 오디오만 재생
        return background_clip.with_duration(audio_clip.duration).with_audio(audio_clip)

    durations = estimate_durations(chunks, audio_clip.duration)

    pages = []
    for chunk, dur in zip(chunks, durations):
        txt_clip = make_body_label_clip(
            chunk,
            duration=dur,
            fontsize=font_size,
            position=("center", "center"),
        )
        page = CompositeVideoClip(
            [background_clip, txt_clip]
        ).with_duration(dur)
        pages.append(page)

    script_sequence = concatenate_videoclips(pages).with_audio(audio_clip)
    return script_sequence
