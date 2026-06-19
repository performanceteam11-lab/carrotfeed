import json
import time
import re
import csv
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright


def get_all_prices(products):
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
        )
        # 봇 감지 우회
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        for prod in products:
            pid = prod["id"]
            url = prod["link"]
            print(f"크롤링: {pid} - {prod['title'][:20]}...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                content = page.content()

                price = None

                # 방법 1: JSON-LD
                matches = re.findall(
                    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                    content, re.DOTALL
                )
                for m in matches:
                    try:
                        data = json.loads(m)
                        if data.get("@type") == "Product":
                            offers = data.get("offers", {})
                            p_val = offers.get("price") or offers.get("lowPrice")
                            if p_val:
                                price = int(float(str(p_val).replace(",", "")))
                                break
                    except Exception:
                        pass

                # 방법 2: JSON 패턴
                if not price:
                    match = re.search(r'"price"\s*:\s*"?([\d]{4,})"?', content)
                    if match:
                        price = int(match.group(1).replace(",", ""))

                # 방법 3: 페이지 텍스트에서 가격 요소
                if not price:
                    for selector in [
                        "._1LY7DqCnwR", ".price_num", "._2pgHN-ntx6",
                        "[class*='price']", "strong[class*='price']"
                    ]:
                        try:
                            el = page.query_selector(selector)
                            if el:
                                txt = re.sub(r"[^\d]", "", el.inner_text())
                                if txt and len(txt) >= 4:
                                    price = int(txt)
                                    break
                        except Exception:
                            pass

                if price:
                    print(f"  → {price:,}원")
                    results[pid] = price
                else:
                    print(f"  → 가격 없음")

            except Exception as e:
                print(f"  → ERROR: {e}")

            time.sleep(1)

        browser.close()
    return results


def load_existing_prices():
    try:
        existing = {}
        with open("sharkninja_feed.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["id"]] = int(row["price_pc"])
        return existing
    except Exception:
        return {}


def main():
    with open("products.json", encoding="utf-8") as f:
        products = json.load(f)

    existing_prices = load_existing_prices()
    prices = get_all_prices(products)

    rows = []
    for p in products:
        price = prices.get(p["id"])
        num_id = re.search(r"/products/(\d+)", p["link"])
        nid = num_id.group(1) if num_id else p["id"]
        # 크롤링 실패 시 기존 가격 유지
        if not price:
            price = existing_prices.get(nid)
        if not price:
            continue
        rows.append({
            "id": nid,
            "title": p["title"],
            "brand": "샤크닌자",
            "image_link": p["image_link"],
            "link": p["link"],
            "price_pc": price,
            "category_name1": p["category_name1"],
            "category_name2": p["category_name2"],
        })

    fieldnames = ["id", "title", "brand", "image_link", "link", "price_pc",
                  "category_name1", "category_name2"]
    with open("sharkninja_feed.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료: {len(rows)}개 상품 → sharkninja_feed.csv")


if __name__ == "__main__":
    main()
