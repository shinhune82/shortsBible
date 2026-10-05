# compose.py
import os
import re
import random
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

UNSPLASH_KEY = os.getenv("UNSPLASH_KEY")
PEXELS_KEY = os.getenv("PEXELS_KEY")
PIXABAY_KEY = os.getenv("PIXABAY_KEY")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")

IMG_DIR = Path(OUTPUT_DIR) / "bg_images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# 이 파일(compose.py)은 src 폴더 안에 있고, assets 폴더는 그 한 단계 위(저장소
# 최상위)에 있음을 기준으로 경로를 계산. cwd가 src든 repo root든 항상 같은 곳을 가리킴.
_SRC_DIR = Path(__file__).resolve().parent
ASSETS_DIR = _SRC_DIR.parent / "assets"

# ── 인물 클로즈업 배제 설정 ─────────────────────────────────────────
# 가장 큰 얼굴이 이미지 면적에서 차지하는 비율이 이 값 이상이면 "인물 클로즈업"으로
# 보고 제외. 더 엄격하게 거르려면 .env 에 FACE_MAX_RATIO=0.005 처럼 낮추면 됨.
FACE_MAX_RATIO = float(os.getenv("FACE_MAX_RATIO", "0.02"))

# Unsplash 가 알려주는 사진 설명/태그에 아래 단어가 들어 있으면 제외
_EXCLUDE_WORDS = re.compile(
    r"\b(woman|women|girl|girls|lady|ladies|female|model|portrait|selfie|face|bikini|lingerie|bride)\b",
    re.IGNORECASE,
)

_face_cascades = None


def _load_face_cascades():
    """OpenCV 얼굴 검출기(정면 + 측면)를 한 번만 로드. 없으면 빈 리스트."""
    global _face_cascades
    if _face_cascades is not None:
        return _face_cascades
    try:
        import cv2
    except ImportError:
        print("[BG] opencv 미설치 - 얼굴 클로즈업 필터를 건너뜁니다.")
        _face_cascades = []
        return _face_cascades

    cascades = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        c = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        if not c.empty():
            cascades.append(c)
    _face_cascades = cascades
    return cascades


def has_large_face(image_path) -> bool:
    """이미지에 '큰 얼굴'(인물 클로즈업)이 있으면 True."""
    cascades = _load_face_cascades()
    if not cascades:
        return False

    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        return False

    h, w = img.shape[:2]
    scale = 800 / max(h, w)  # 속도를 위해 긴 변 800px 로 축소
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    min_side = max(20, int(min(h, w) * 0.10))

    largest = 0
    for c in cascades:
        faces = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_side, min_side))
        for (_x, _y, fw, fh) in faces:
            largest = max(largest, fw * fh)

    return (largest / float(w * h)) >= FACE_MAX_RATIO


def _metadata_text(item: dict) -> str:
    parts = [item.get("alt_description") or "", item.get("description") or ""]
    for t in item.get("tags") or []:
        parts.append(t.get("title") or "")
    return " ".join(parts)


def _is_excluded_by_metadata(item: dict) -> bool:
    return bool(_EXCLUDE_WORDS.search(_metadata_text(item)))


def download_image(url: str, filename: str) -> str:
    resp = requests.get(url, stream=True, timeout=15)
    resp.raise_for_status()
    path = IMG_DIR / filename
    with open(path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return str(path)


def get_background_images_from_title(title: str):
    keyword = title.split()[0] if title else "nature"
    print(f"[BG] 제목='{title}', keyword='{keyword}'")

    chosen = []

    # 1) Unsplash: 후보를 넉넉히 받아서 인물 위주 사진을 걸러낸 뒤 2장 선택
    if UNSPLASH_KEY:
        try:
            r = requests.get(
                "https://api.unsplash.com/photos/random",
                params={
                    "query": keyword,
                    "orientation": "portrait",
                    "count": 12,
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=10,
            )
            print("[BG] Unsplash status:", r.status_code)
            if not r.ok:
                print("[BG] Unsplash 응답:", r.text[:200])
            else:
                data = r.json()
                if isinstance(data, dict):
                    data = [data]

                rejected_meta = 0
                rejected_face = 0
                for i, item in enumerate(data):
                    if len(chosen) >= 2:
                        break
                    if _is_excluded_by_metadata(item):
                        rejected_meta += 1
                        continue
                    path = download_image(item["urls"]["regular"], f"unsplash_{keyword}_{i}.jpg")
                    if has_large_face(path):
                        rejected_face += 1
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                        continue
                    chosen.append(path)

                print(
                    f"[BG] 후보 {len(data)}장 중 설명/태그로 제외 {rejected_meta}장, "
                    f"얼굴 클로즈업 제외 {rejected_face}장, 사용 {len(chosen)}장"
                )
        except Exception as e:
            print("[BG] Unsplash error:", e)

    # 2) 못 구했으면 assets 폴더의 기본 배경 (여기서도 얼굴 클로즈업은 우선 제외)
    if not chosen:
        print("[BG] API에서 쓸 만한 이미지를 못 찾아서 assets 폴더의 기본 배경을 사용합니다.")
        candidates = list(ASSETS_DIR.glob("*.jpg")) + \
                     list(ASSETS_DIR.glob("*.jpeg")) + \
                     list(ASSETS_DIR.glob("*.png"))

        if len(candidates) == 0:
            raise RuntimeError(
                f"assets 폴더에 사용할 수 있는 이미지가 없습니다. (찾은 위치: {ASSETS_DIR})"
            )

        random.shuffle(candidates)
        safe = []
        for c in candidates:
            if len(safe) >= 2:
                break
            if not has_large_face(c):
                safe.append(str(c))

        pool = safe or [str(c) for c in candidates]  # 전부 걸러지면 필터 없이 사용
        if len(pool) >= 2:
            return pool[0], pool[1]
        return pool[0], pool[0]

    if len(chosen) == 1:
        chosen.append(chosen[0])

    return chosen[0], chosen[1]
