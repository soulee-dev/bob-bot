import os
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse

URL = os.environ["URL"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

PUBLIC_DIR = "public"

def fetch_og_image(page_url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": page_url,
    }
    r = requests.get(page_url, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.find("meta", property="og:image")
    if not meta or not meta.get("content"):
        raise RuntimeError("No og:image meta tag found")
    return meta["content"]

def safe_upgrade(url: str) -> str:
    # kakao cdn의 img_m->img_xl 치환은 실패할 수 있으니 HEAD로 확인 후 fallback
    if url.endswith("img_m.jpg"):
        candidate = url[:-9] + "img_xl.jpg"
        try:
            h = requests.head(candidate, timeout=10, allow_redirects=True)
            if h.ok and "image" in (h.headers.get("Content-Type") or ""):
                return candidate
        except Exception:
            pass
    return url

def download_image(img_url: str, dest_path: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": f"{urlparse(img_url).scheme}://{urlparse(img_url).netloc}/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    r = requests.get(img_url, headers=headers, timeout=30)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(r.content)

def build_today_paths():
    today = datetime.now()
    yyyy = today.strftime("%Y")
    mm = today.strftime("%m")
    dd = today.strftime("%d")
    folder = os.path.join(PUBLIC_DIR, yyyy, mm)
    filename = f"{dd}.jpg"
    dated_rel_path = os.path.join(yyyy, mm, filename)  # GitHub Pages 기준 상대 경로
    return folder, os.path.join(folder, filename), os.path.join(PUBLIC_DIR, "latest.jpg"), dated_rel_path

def send_chat(image_url: str):
    title = datetime.now().strftime("%Y년 %m월 %d일 오늘의 메뉴")
    payload = {
        "cardsV2": [
            {
                "cardId": "daily-image",
                "card": {
                    "header": {"title": "밥봇 - 오늘의 메뉴"},
                    "sections": [
                        {"widgets": [{"image": {"imageUrl": image_url, "altText": "오늘의 메뉴"}}]},
                        {"widgets": [{"textParagraph": {"text": title}}]},
                    ],
                },
            }
        ]
    }
    resp = requests.post(
        WEBHOOK_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()

def main():
    img = fetch_og_image(URL)
    img = safe_upgrade(img)

    folder, today_path, latest_path, dated_rel_path = build_today_paths()
    download_image(img, today_path)

    # latest.jpg는 계속 유지(다른 용도), 단 Chat 전송에는 날짜 경로 사용
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    try:
        if os.path.exists(latest_path):
            os.remove(latest_path)
    except Exception:
        pass
    with open(today_path, "rb") as src, open(latest_path, "wb") as dst:
        dst.write(src.read())

    owner = os.getenv("GITHUB_REPOSITORY", "owner/repo").split("/")[0]
    repo = os.getenv("GITHUB_REPOSITORY", "owner/repo").split("/")[1]
    pages_base = f"https://{owner}.github.io/{repo}"

    # ✅ Google Chat에는 날짜 기반 고유 URL을 사용
    dated_image_url = f"{pages_base}/{dated_rel_path.replace(os.sep, '/')}"
    send_chat(dated_image_url)

    print("Posted image via GitHub Pages URL:", dated_image_url)
    print("latest also updated (not used for Chat):", f"{pages_base}/latest.jpg")

if __name__ == "__main__":
    main()
