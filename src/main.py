# main.py
import sys
import os
import gc
import argparse
import re

# Windows 콘솔 기본 인코딩(cp949)과 무관하게 항상 UTF-8로 출력하도록 강제.
# GUI(subprocess)나 다른 콘솔에서 실행되어도 한글 깨짐/인코딩 오류를 방지.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
import moviepy as mp

from compose import get_background_images_from_title
from script_parser import parse_devotional_file
from text_render import make_label_clip, make_body_label_clip, make_labeled_body_clip
from pages import split_script
from audio_util import make_tts_for_script
from youtube_upload import upload_to_youtube, build_description

SUBSCRIBE_FONT_SIZE = 45

# 스프레드시트의 '구독' 열을 대체하는 고정 문구.
# .env 에 SUBSCRIBE_TEXT 를 넣으면 바꿀 수 있습니다.
DEFAULT_SUBSCRIBE_TEXT = os.getenv(
    "SUBSCRIBE_TEXT",
    "오늘의 은혜가 계속되기를 기도하며 [구독]하고 다음 말씀도 놓치지 마세요",
)


def normalize_subscribe_text(subscribe: str) -> str:
    if not subscribe:
        return ""
    txt = subscribe.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in txt.split("\n")]
    return "\n".join(lines).strip()


def make_subscribe_clip(subscribe_text: str, duration: float):
    subscribe_text = normalize_subscribe_text(subscribe_text)
    if not subscribe_text:
        return None
    return make_body_label_clip(
        subscribe_text,
        duration=duration,
        fontsize=SUBSCRIBE_FONT_SIZE,
        position=("right", "bottom"),
    )


_WEEKDAY_MAP = ["월", "화", "수", "목", "금", "토", "일"]


def _format_date_line(entry):
    wd = _WEEKDAY_MAP[entry["date"].weekday()]
    return f"{entry['date'].strftime('%Y-%m-%d')} {wd} {entry['time_type']}"


def _entry_to_text_block(entry):
    """입력 텍스트와 같은 형식으로 항목 하나를 다시 조립 (Suno 등에 재사용하기 쉽게)."""
    return (
        f"**날짜:** {_format_date_line(entry)}\n\n"
        f"**제목:** {entry['title']}\n\n"
        f"**성경말씀:** {entry['verse']}\n\n"
        f"**말씀내용:** {entry['content']}\n\n"
        f"**묵상:** {entry['script60']}\n"
    )


def save_script_file(entry, output_dir):
    """영상 하나에 해당하는 스크립트를 outputs/scripts/ 에 별도 텍스트 파일로 저장."""
    scripts_dir = os.path.join(output_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    date_str = entry["date"].strftime("%Y-%m-%d")
    tt = entry["time_type"]
    path = os.path.join(scripts_dir, f"script_{date_str}_{tt}.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write(_entry_to_text_block(entry))

    print(f"[스크립트] 저장 완료 → {path}")
    return path


def save_batch_script_file(entries, output_dir):
    """이번 실행에서 처리한 항목 전체를 하나의 텍스트 파일로 모아서 저장."""
    if not entries:
        return None

    scripts_dir = os.path.join(output_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    first_date = entries[0]["date"].strftime("%Y%m%d")
    last_date = entries[-1]["date"].strftime("%Y%m%d")
    if first_date == last_date:
        filename = f"batch_{first_date}.txt"
    else:
        filename = f"batch_{first_date}-{last_date}.txt"
    path = os.path.join(scripts_dir, filename)

    blocks = [_entry_to_text_block(e) for e in entries]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n---\n\n".join(blocks))

    print(f"[스크립트] 이번 배치 전체 모음 저장 완료 → {path}")
    return path


def process_entry(entry, output_dir, video_size, do_upload):
    """텍스트에서 파싱된 항목 하나(날짜+시기)로 영상 생성 + 업로드."""
    date_str = entry["date"].strftime("%Y-%m-%d")
    tt = entry["time_type"]
    title = entry["title"]
    verse = entry["verse"]
    content = entry["content"]
    script60 = entry["script60"]
    subscribe = DEFAULT_SUBSCRIBE_TEXT

    print(f"\n{'='*50}")
    print(f"[처리 시작] {date_str} / {tt} / {title}")
    print(f"{'='*50}")

    # 영상 생성/업로드와 별개로, 스크립트 자체도 텍스트 파일로 저장
    # (나중에 Suno 등으로 가사/노래 만들 때 재사용하기 편하도록)
    save_script_file(entry, output_dir)

    ImageClip              = mp.ImageClip
    CompositeVideoClip     = mp.CompositeVideoClip
    concatenate_videoclips = mp.concatenate_videoclips

    output_name = f"short_output_{date_str}_{tt}.mp4"
    output_path = os.path.join(output_dir, output_name)

    first_bg_path, second_bg_path = get_background_images_from_title(title)

    all_clips_to_close = []

    # ---------- 첫 화면 ----------
    first_pages = []
    first_items = [
        ("오늘의 말씀\n" + title, 65),
        ("말씀\n" + verse, 50),
        ("말씀 내용\n" + content, 50),
    ]
    for idx, (page_text, font_size) in enumerate(first_items):
        audio_clip, _ = make_tts_for_script(
            script_text=page_text.replace("\n", " "),
            output_dir=output_dir,
            filename=f"{date_str}_{tt}_first_{idx}.mp3",
            lang="ko",
        )
        duration = audio_clip.duration
        first_bg = ImageClip(first_bg_path).resized(new_size=video_size)
        if idx == 0:
            # 시작 화면: "오늘의 말씀" 라벨을 골드색으로 강조해서
            # 자막처럼 보이지 않고 확실한 오프닝 카드로 느껴지게.
            txt_clip = make_label_clip(
                page_text, duration=duration, fontsize=font_size,
                position=("center", "center"), label_color=(255, 205, 60, 255),
            )
        else:
            txt_clip = make_labeled_body_clip(page_text, duration=duration, fontsize=font_size, position=("center", "center"))
        page = CompositeVideoClip([first_bg, txt_clip]).with_duration(duration).with_audio(audio_clip)
        first_pages.append(page)
        first_bg.close()
        all_clips_to_close.append(audio_clip)

    first_screen_clip = concatenate_videoclips(first_pages)
    all_clips_to_close.append(first_screen_clip)

    # ---------- 두 번째 화면 (묵상 = 60초 스크립트) ----------
    script_chunks = split_script(script60, max_chars=40)
    script_pages = []
    for idx, chunk in enumerate(script_chunks):
        chunk = (chunk or "").strip()
        if not chunk or not re.search(r'[가-힣a-zA-Z0-9]', chunk):
            continue
        audio_clip, _ = make_tts_for_script(
            script_text=chunk,
            output_dir=output_dir,
            filename=f"{date_str}_{tt}_script_{idx}.mp3",
            lang="ko",
        )
        duration = audio_clip.duration
        second_bg = ImageClip(second_bg_path).resized(new_size=video_size)
        txt_clip = make_body_label_clip(chunk, duration=duration, fontsize=50, position=("center", "center"))
        sub_clip = make_subscribe_clip(subscribe, duration)
        clips = [second_bg, txt_clip]
        if sub_clip is not None:
            clips.append(sub_clip)
        page = CompositeVideoClip(clips).with_duration(duration).with_audio(audio_clip)
        script_pages.append(page)
        second_bg.close()
        all_clips_to_close.append(audio_clip)

    subscribe_text = (subscribe or "").strip()
    if subscribe_text:
        sub_duration = 3.0
        second_bg = ImageClip(second_bg_path).resized(new_size=video_size)
        sub_txt_clip = make_body_label_clip(subscribe_text, duration=sub_duration, fontsize=50, position=("center", "center"))
        sub_page = CompositeVideoClip([second_bg, sub_txt_clip]).with_duration(sub_duration)
        script_pages.append(sub_page)
        second_bg.close()

    if script_pages:
        second_screen_clip = concatenate_videoclips(script_pages)
        final_clip = concatenate_videoclips([first_screen_clip, second_screen_clip])
        all_clips_to_close.append(second_screen_clip)
    else:
        final_clip = first_screen_clip

    # -------- 영상 출력 --------
    final_clip.write_videofile(output_path, fps=30, codec="libx264", audio=True, preset="medium", threads=4)

    # -------- write 완료 후 메모리 정리 --------
    final_clip.close()
    for p in first_pages:
        p.close()
    for p in script_pages:
        p.close()
    for c in all_clips_to_close:
        try:
            c.close()
        except Exception:
            pass
    gc.collect()
    print(f"[메모리] {date_str} / {tt} 클립 정리 완료")

    # YouTube 예약 업로드
    if do_upload:
        yt_title = f"[오늘의 말씀] {title}"
        yt_description = build_description(date_str=date_str, verse=verse, content=content)
        upload_to_youtube(
            video_path=output_path,
            title=yt_title,
            description=yt_description,
            date_str=date_str,
            time_type=tt,
        )
        # 업로드 성공했으면 로컬 mp4는 용량 절약을 위해 바로 삭제.
        # (--no-upload 로 로컬 확인용으로 돌린 경우는 지우지 않음)
        try:
            os.remove(output_path)
            print(f"[정리] 업로드 완료 후 로컬 영상 삭제: {output_path}")
        except OSError as e:
            print(f"[정리] 영상 삭제 실패 (무시하고 계속 진행): {e}")
    else:
        print(f"[YouTube] 업로드 건너뜀")


def cleanup_old_files(output_dir, days=30):
    """
    outputs/bg_images, outputs/audio, outputs/scripts 안에서
    days 일보다 오래된 파일을 정리. 매 실행마다 자동으로 호출됨.
    .env 의 CLEANUP_DAYS 로 주기 조정 가능 (기본 30일 = 약 1달, 분기 단위면 90).
    """
    import time
    cutoff = time.time() - (days * 86400)
    targets = ["bg_images", "audio", "scripts"]
    removed = 0

    for sub in targets:
        folder = os.path.join(output_dir, sub)
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    removed += 1
            except OSError:
                pass

    if removed:
        print(f"[정리] {days}일 지난 파일 {removed}개 삭제 (bg_images/audio/scripts)")


# -------- 전역 설정 --------
load_dotenv()

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
VIDEO_SIZE = (1080, 1920)
YT_UPLOAD  = os.getenv("YT_UPLOAD", "true").lower() == "true"
CLEANUP_DAYS = int(os.getenv("CLEANUP_DAYS", "30"))  # 기본 30일(약 1달). 분기 단위면 .env 에 90 으로 설정

os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    # 매 실행 시작할 때 오래된 부산물(이미지/음성/스크립트) 먼저 정리
    cleanup_old_files(OUTPUT_DIR, days=CLEANUP_DAYS)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", default="input.txt",
        help="파싱할 텍스트 파일 경로 (기본값: input.txt, shorts_new 폴더 기준)"
    )
    parser.add_argument("--no-upload", action="store_true", help="YouTube 업로드 건너뛰기")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"오류: 입력 파일을 찾을 수 없습니다 - {args.input}")
        return

    entries = parse_devotional_file(args.input)
    if not entries:
        print(f"오류: {args.input} 에서 파싱된 항목이 없습니다. 형식을 확인해주세요.")
        return

    do_upload = YT_UPLOAD and not args.no_upload

    total = len(entries)
    print(f"총 {total}개 항목 처리 예정 (입력 파일: {args.input})")

    for i, entry in enumerate(entries, 1):
        print(f"\n[{i}/{total}]")
        process_entry(
            entry=entry,
            output_dir=OUTPUT_DIR,
            video_size=VIDEO_SIZE,
            do_upload=do_upload,
        )

    print(f"\n{'='*50}")
    print(f"모든 처리 완료! ({total}개)")
    print(f"{'='*50}")

    # 이번 배치 전체를 모은 스크립트 파일도 하나 더 저장
    save_batch_script_file(entries, OUTPUT_DIR)


if __name__ == "__main__":
    main()
