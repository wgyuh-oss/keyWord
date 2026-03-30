import time

import requests

BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

_last_call = 0


def get_blog_doc_count(keyword, config):
    """네이버 블로그 검색 API로 해당 키워드의 블로그 문서 수 조회"""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 0.1:
        time.sleep(0.1 - elapsed)

    headers = {
        "X-Naver-Client-Id": config["client_id"],
        "X-Naver-Client-Secret": config["client_secret"],
    }
    params = {"query": keyword, "display": 1}

    try:
        resp = requests.get(BLOG_URL, headers=headers, params=params, timeout=10)
        _last_call = time.time()
        resp.raise_for_status()
        return resp.json().get("total", 0)
    except requests.RequestException as e:
        print(f"[Search API 오류] {keyword}: {e}")
        _last_call = time.time()
        return 0
