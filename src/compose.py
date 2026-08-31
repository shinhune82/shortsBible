# compose.py
import os
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

    paths = []

    # 1) Unsplash
    if UNSPLASH_KEY:
        try:
            r = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": keyword, "orientation": "portrait", "count": 2},
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=10,
            )
            print("[BG] Unsplash status:", r.status_code, r.text[:200])
            if r.ok:
                data = r.json()
                if isinstance(data, dict):
                    data = [data]
                for i, item in enumerate(data[:2]):
                    url = item["urls"]["regular"]
                    paths.append(download_image(url, f"unsplash_{keyword}_{i}.jpg"))
        except Exception as e:
            print("[BG] Unsplash error:", e)

    # TODO: Pexels / Pixabay 로직도 같은 식으로 status_code, error 출력 추가

    # 여기까지 왔는데도 paths가 비어 있으면 assets 폴더에서 랜덤 선택
    if not paths:
        print("[BG] API에서 이미지를 못 찾아서 assets 폴더의 기본 배경을 랜덤 사용합니다.")
        assets_dir = Path("assets")
        # jpg, jpeg, png 파일만 대상으로
        candidates = list(assets_dir.glob("*.jpg")) + \
                     list(assets_dir.glob("*.jpeg")) + \
                     list(assets_dir.glob("*.png"))

        if len(candidates) == 0:
            raise RuntimeError("assets 폴더에 사용할 수 있는 이미지가 없습니다.")

        # 2장 이상이면 무작위 2장, 1장이면 그 한 장을 두 번 사용
        if len(candidates) >= 2:
            chosen = random.sample(candidates, 2)
            return str(chosen[0]), str(chosen[1])
        else:
            only = str(candidates[0])
            return only, only

    if len(paths) == 1:
        paths.append(paths[0])

    return paths[0], paths[1]
