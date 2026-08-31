# audio_util.py
import os
import asyncio
import edge_tts
import moviepy as mp

AudioFileClip = mp.AudioFileClip

# 한국어 뉴럴 음성 목록 (Edge TTS 제공, 무료. 2026-08 기준 실제 확인된 목록):
#   ko-KR-SunHiNeural              - 여성, 확신에 찬 / 격식있는 톤 (기본값)
#   ko-KR-InJoonNeural             - 남성, 캐주얼하고 친근한 톤
#   ko-KR-HyunsuMultilingualNeural - 남성, 격식있고 또렷한 톤
# .env 에 TTS_VOICE=ko-KR-InJoonNeural 식으로 넣으면 기본값을 바꿀 수 있습니다.
# 최신 목록은 언제든 아래 명령으로 재확인 가능:
#   python -m edge_tts --list-voices | findstr ko-KR
DEFAULT_VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")

# 말하기 속도/톤 조절 (필요하면 .env 의 TTS_RATE, TTS_PITCH 로 조정)
#   느리게: "-10%"  /  빠르게: "+10%"
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%")
DEFAULT_PITCH = os.getenv("TTS_PITCH", "+0Hz")


async def _synthesize(text: str, voice: str, path: str, rate: str, pitch: str):
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(path)


def make_tts_for_script(
    script_text: str,
    output_dir: str,
    filename: str = "script60.mp3",
    lang: str = "ko",
    voice: str = None,
):
    """
    Edge TTS 로 음성 파일을 생성하고 AudioFileClip 과 경로를 함께 반환.
    mp3 는 output_dir/audio/ 아래에 저장.
    (lang 파라미터는 기존 호출부와의 호환을 위해 남겨두지만 실제로는
     voice 값이 언어까지 함께 결정합니다.)
    """
    audio_root = os.path.join(output_dir, "audio")
    os.makedirs(audio_root, exist_ok=True)

    path = os.path.join(audio_root, filename)

    script_text = (script_text or "").strip()
    if not script_text:
        raise ValueError("빈 텍스트는 TTS를 만들 수 없습니다.")

    selected_voice = voice or DEFAULT_VOICE

    asyncio.run(_synthesize(script_text, selected_voice, path, DEFAULT_RATE, DEFAULT_PITCH))

    audio_clip = AudioFileClip(path)
    return audio_clip, path
