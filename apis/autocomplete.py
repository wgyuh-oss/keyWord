import time

import requests

AC_URL = "https://ac.search.naver.com/nx/ac"


def get_suggestions(keyword):
    """네이버 자동완성 API로 연관 키워드 수집"""
    params = {
        "q": keyword,
        "con": "1",
        "frm": "nx",
        "ans": "2",
        "r_format": "json",
        "r_enc": "UTF-8",
        "r_unicode": "0",
        "t_koreng": "1",
        "run": "2",
        "rev": "4",
        "q_enc": "UTF-8",
        "st": "100",
    }

    try:
        resp = requests.get(AC_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if items and len(items) > 0:
            return [item[0] for item in items[0] if isinstance(item, list) and item]
    except Exception:
        pass

    time.sleep(0.3)
    return []
