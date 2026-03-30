import base64
import hashlib
import hmac
import time
from urllib.parse import quote

import requests

BASE_URL = "https://api.searchad.naver.com"


def _make_signature(secret_key, method, uri):
    timestamp = str(round(time.time() * 1000))
    sign_str = f"{timestamp}.{method}.{uri}"
    signature = base64.b64encode(
        hmac.new(
            secret_key.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return timestamp, signature


def _make_headers(config):
    timestamp, signature = _make_signature(
        config["secret_key"], "GET", "/keywordstool"
    )
    return {
        "X-API-KEY": config["api_key"],
        "X-CUSTOMER": config["customer_id"],
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }


def _parse_volume(val):
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        val = val.strip().replace(",", "")
        if val.isdigit():
            return int(val)
    return 5  # "< 10" 등 저볼륨 키워드


def get_related_keywords(hint_keywords, config):
    """네이버 검색광고 API로 관련 키워드 + 검색량 조회"""
    headers = _make_headers(config)
    params = {
        "hintKeywords": ",".join(hint_keywords),
        "showDetail": "1",
    }

    try:
        # requests의 params는 쉼표를 %2C, 공백을 +로 인코딩하여 네이버 API가 거부함
        # quote(safe=",")로 쉼표는 유지, 공백은 %20으로 인코딩
        encoded_kws = quote(",".join(hint_keywords), safe=",")
        url = f"{BASE_URL}/keywordstool?hintKeywords={encoded_kws}&showDetail=1"
        req = requests.Request("GET", url, headers=headers)
        prepared = req.prepare()
        prepared.url = url  # requests의 재인코딩 방지
        resp = requests.Session().send(prepared, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        body = ""
        if hasattr(e, "response") and e.response is not None:
            body = e.response.text[:200]
        print(f"[SearchAd API 오류] {e} | {body}")
        return []

    results = []
    for item in data.get("keywordList", []):
        results.append(
            {
                "keyword": item.get("relKeyword", ""),
                "pc_volume": _parse_volume(item.get("monthlyPcQcCnt", 0)),
                "mobile_volume": _parse_volume(item.get("monthlyMobileQcCnt", 0)),
                "comp_idx": item.get("compIdx", "중간"),
            }
        )
    return results
