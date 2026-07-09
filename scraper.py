"""
scraper.py
Các hàm lấy dữ liệu (tài liệu / đề thi) từ nhiều trang nguồn bằng cách
parse HTML công khai (không dùng API riêng vì các trang không có API).

Nguồn hỗ trợ:
  - toanmath.com          (WordPress, tìm kiếm qua ?s=)
  - nganhangdethi.org     (Blogger, tìm kiếm qua /search?q=)
  - dethi.violet.vn       (mạng ViOLET, duyệt theo mục ?same=list&page=N,
                           không có tìm kiếm riêng nên quét theo trang)
"""

import re
import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# Định nghĩa các trang nguồn có URL bài viết dạng
# https://domain/YYYY/MM/slug.html — dùng chung 1 kiểu regex.
SITES = {
    "toanmath": {
        "name": "ToanMath",
        "base_url": "https://toanmath.com",
        "search_url": lambda kw: ("https://toanmath.com/", {"s": kw}),
    },
    "nganhangdethi": {
        "name": "Ngân Hàng Đề Thi",
        "base_url": "https://www.nganhangdethi.org",
        "search_url": lambda kw: (
            "https://www.nganhangdethi.org/search",
            {"q": kw},
        ),
    },
}

BASE_URL = SITES["toanmath"]["base_url"]  # giữ tương thích ngược cho code cũ

# dethi.violet.vn: URL bài viết dạng /present/<slug>-<id>.html, không theo
# ngày tháng nên cần regex riêng. Trang không có endpoint tìm kiếm công khai
# ổn định, nhưng có URL liệt kê "mới nhất trước" theo từng mục lớn, có phân
# trang qua &page=N — dùng cái này để lấy mới nhất và để quét tìm từ khóa.
VIOLET_NAME = "Violet"
VIOLET_BASE = "https://dethi.violet.vn"
VIOLET_CATEGORIES = {
    "thpt": "category/trung-hoc-pho-thong-8656239.html",  # THPT chương trình mới
    "thpt_qg": "category/de-thi-thpt-quoc-gia-8298648.html",  # đề thi TN THPT QG
}
VIOLET_POST_PATTERN = re.compile(
    r"^https?://(www\.)?dethi\.violet\.vn/present/[^/]+\.html$"
)

# Mỗi mục = (nhãn hiển thị, slug category trên toanmath.com)
CATEGORIES_BY_CLASS = {
    "10": {
        "Tài liệu": "chuyen-de-toan-10",
        "Đề cương": "de-cuong-on-tap-toan-10",
        "Đề giữa HK1": "de-thi-giua-hk1-toan-10",
        "Đề HK1": "de-thi-hk1-toan-10",
        "Đề giữa HK2": "de-thi-giua-hk2-toan-10",
        "Đề HK2": "de-thi-hk2-toan-10",
        "Đề khảo sát": "khao-sat-chat-luong-toan-10",
        "Đề HSG": "de-thi-hsg-toan-10",
        "Giáo án": "giao-an-toan-10",
        "Tips giải": "tips-giai-toan-10",
    },
    "11": {
        "Tài liệu": "chuyen-de-toan-11",
        "Đề cương": "de-cuong-on-tap-toan-11",
        "Đề giữa HK1": "de-thi-giua-hk1-toan-11",
        "Đề HK1": "de-thi-hk1-toan-11",
        "Đề giữa HK2": "de-thi-giua-hk2-toan-11",
        "Đề HK2": "de-thi-hk2-toan-11",
        "Đề khảo sát": "khao-sat-chat-luong-toan-11",
        "Đề HSG": "de-thi-hsg-toan-11",
        "Giáo án": "giao-an-toan-11",
        "Tips giải": "tips-giai-toan-11",
    },
    "12": {
        "Tài liệu": "chuyen-de-toan-12",
        "Đề cương": "de-cuong-on-tap-toan-12",
        "Đề giữa HK1": "de-thi-giua-hk1-toan-12",
        "Đề HK1": "de-thi-hk1-toan-12",
        "Đề giữa HK2": "de-thi-giua-hk2-toan-12",
        "Đề HK2": "de-thi-hk2-toan-12",
        "Đề khảo sát": "khao-sat-chat-luong-toan-12",
        "Đề HSG": "de-thi-hsg-toan-12",
        "Giáo án": "giao-an-toan-12",
        "Tips giải": "tips-giai-toan-12",
    },
    "thpt": {
        "Đề thi thử THPT": "de-thi-thu-thpt-mon-toan",
        "Đề THPT chính thức": "de-thi-thpt-mon-toan-chinh-thuc",
        "Đề đánh giá năng lực": "de-danh-gia-nang-luc-mon-toan",
        "Tài liệu ôn thi THPT": "tai-lieu-on-thi-thpt-mon-toan",
    },
}


def _extract_articles(html: str, limit: int = 10, domain: str = "toanmath.com", pattern=None):
    """
    Trích danh sách (tiêu đề, link) từ 1 trang HTML.
    Mặc định dùng kiểu URL /YYYY/MM/slug.html (toanmath.com, nganhangdethi.org).
    Truyền `pattern` (regex đã compile) để dùng kiểu URL khác (vd Violet).
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    results = []

    if pattern is None:
        domain_escaped = re.escape(domain)
        pattern = re.compile(
            rf"^https?://(www\.)?{domain_escaped}/\d{{4}}/\d{{2}}/[^/]+\.html$"
        )

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not pattern.match(href):
            continue
        title = a.get("title") or a.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        if href in seen:
            continue
        seen.add(href)
        results.append({"title": title.strip(), "url": href})
        if len(results) >= limit:
            break

    return results


def _domain_of(url: str) -> str:
    return url.split("//", 1)[1].split("/", 1)[0].replace("www.", "")


def _get_violet_page(category: str, page: int = 1):
    """Lấy 1 trang danh sách '?same=list' của 1 mục Violet (mới nhất trước)."""
    slug = VIOLET_CATEGORIES[category]
    params = {"same": "list"}
    if page > 1:
        params["page"] = page
    resp = requests.get(f"{VIOLET_BASE}/{slug}", params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return _extract_articles(resp.text, limit=50, pattern=VIOLET_POST_PATTERN)


def get_latest_violet(limit: int = 10, category: str = "thpt"):
    """Tài liệu mới nhất của 1 mục Violet (mặc định: THPT chương trình mới)."""
    items = _get_violet_page(category, page=1)
    for it in items:
        it["source"] = VIOLET_NAME
    return items[:limit]


def search_violet(keyword: str, limit: int = 10, category: str = "thpt", pages_to_scan: int = 5):
    """
    Violet không có endpoint tìm kiếm công khai ổn định, nên quét vài trang
    đầu (mới nhất trước) của mục và lọc theo từ khóa.
    """
    norm_kw = _normalize(keyword)
    results = []
    seen_urls = set()
    for page in range(1, pages_to_scan + 1):
        try:
            items = _get_violet_page(category, page=page)
        except requests.RequestException:
            continue
        for item in items:
            if norm_kw in _normalize(item["title"]) and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                item["source"] = VIOLET_NAME
                results.append(item)
        if len(results) >= limit:
            break
    return results[:limit]


def get_latest(limit: int = 10, source: str = "all"):
    """
    Lấy danh sách tài liệu mới nhất.
    source: "toanmath", "nganhangdethi", "violet", hoặc "all" (gộp cả 3,
    xen kẽ theo nguồn).
    """
    if source == "violet":
        return get_latest_violet(limit=limit)

    sources = list(SITES.keys()) if source == "all" else [source]
    all_items = []
    for key in sources:
        site = SITES[key]
        try:
            resp = requests.get(site["base_url"], headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        items = _extract_articles(
            resp.text, limit=limit, domain=_domain_of(site["base_url"])
        )
        for it in items:
            it["source"] = site["name"]
        all_items.extend(items)

    if source == "all":
        try:
            violet_items = get_latest_violet(limit=limit)
        except requests.RequestException:
            violet_items = []
        all_items.extend(violet_items)
        sources = sources + ["violet"]
        names = [SITES[k]["name"] for k in SITES] + [VIOLET_NAME]
    else:
        return all_items[:limit]

    # gộp xen kẽ theo nguồn để không bị 1 trang chiếm hết danh sách
    per_source_lists = [[it for it in all_items if it["source"] == n] for n in names]
    merged = []
    i = 0
    while len(merged) < limit and any(per_source_lists):
        for lst in per_source_lists:
            if i < len(lst):
                merged.append(lst[i])
        i += 1
    return merged[:limit]


def get_by_category(class_key: str, category_label: str, limit: int = 10):
    """
    Lấy danh sách tài liệu theo lớp + loại (vd: lớp 12, Đề HSG).
    Chỉ áp dụng cho toanmath.com — nganhangdethi.org không có URL chuyên mục
    cố định (dùng widget JS), nên trang đó chỉ hỗ trợ /moinhat và /timkiem.
    """
    slug = CATEGORIES_BY_CLASS[class_key][category_label]
    url = f"{SITES['toanmath']['base_url']}/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return _extract_articles(resp.text, limit=limit, domain="toanmath.com")


def _normalize(text: str) -> str:
    return unidecode(text).lower()


def search_keyword(keyword: str, limit: int = 10, source: str = "all", pages_to_scan: int = 6):
    """
    Tìm kiếm theo từ khóa trên các nguồn.
    - toanmath.com / nganhangdethi.org: dùng endpoint tìm kiếm riêng (?s=,
      /search?q=), rồi quét thêm vài chuyên mục toanmath.com nếu chưa đủ.
    - dethi.violet.vn: không có endpoint tìm kiếm ổn định, quét vài trang
      mới nhất của mục THPT.
    So khớp không phân biệt dấu/hoa-thường (dùng unidecode).
    """
    norm_kw = _normalize(keyword)
    results = []
    seen_urls = set()

    if source == "violet":
        return search_violet(keyword, limit=limit, pages_to_scan=pages_to_scan)

    sources = list(SITES.keys()) if source == "all" else [source]

    for key in sources:
        site = SITES[key]
        try:
            url, params = site["search_url"](keyword)
            resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        items = _extract_articles(
            resp.text, limit=50, domain=_domain_of(site["base_url"])
        )
        for item in items:
            if norm_kw in _normalize(item["title"]) and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                item["source"] = site["name"]
                results.append(item)

    if source == "all":
        try:
            for item in search_violet(keyword, limit=limit, pages_to_scan=pages_to_scan):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    results.append(item)
        except requests.RequestException:
            pass

    if len(results) >= limit or "toanmath" not in sources:
        return results[:limit]

    # Bước bổ sung: chỉ cho toanmath.com — quét thêm vài chuyên mục gần đây
    all_slugs = []
    for group in CATEGORIES_BY_CLASS.values():
        all_slugs.extend(group.values())

    toanmath_base = SITES["toanmath"]["base_url"]
    for slug in all_slugs[:pages_to_scan]:
        try:
            resp = requests.get(f"{toanmath_base}/{slug}", headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        for item in _extract_articles(resp.text, limit=30, domain="toanmath.com"):
            if norm_kw in _normalize(item["title"]) and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                item["source"] = SITES["toanmath"]["name"]
                results.append(item)
        if len(results) >= limit:
            break

    return results[:limit]
