# preview_voices.py
# 한국어 음성 3종을 짧게 미리 들어보는 테스트 스크립트.
# shorts_new\src 폴더에 놓고 실행하세요: python preview_voices.py
import asyncio
import edge_tts
import os

SAMPLE_TEXT = "오늘의 말씀입니다. 세상이 줄 수 없는 참된 평안을 누리시기를 기도합니다."

# 2026-08 기준 실제 확인된 한국어 음성 (python -m edge_tts --list-voices | findstr ko-KR 로 재확인 가능)
VOICES = [
    "ko-KR-SunHiNeural",               # 여성, 확신에 찬 / 격식있는 톤
    "ko-KR-InJoonNeural",               # 남성, 캐주얼하고 친근한 톤
    "ko-KR-HyunsuMultilingualNeural",   # 남성, 격식있고 또렷한 톤
]

OUT_DIR = "voice_preview"


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for voice in VOICES:
        path = os.path.join(OUT_DIR, f"{voice}.mp3")
        communicate = edge_tts.Communicate(SAMPLE_TEXT, voice=voice)
        await communicate.save(path)
        print(f"생성 완료: {path}")
    print(f"\n{OUT_DIR} 폴더의 mp3 파일들을 들어보고 마음에 드는 목소리를 골라")
    print("audio_util.py 의 DEFAULT_VOICE 또는 .env 의 TTS_VOICE 값으로 넣으세요.")


if __name__ == "__main__":
    asyncio.run(main())
