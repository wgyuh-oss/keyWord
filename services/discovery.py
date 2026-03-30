import csv
import json
import os
import time
from collections import deque
from datetime import datetime

from apis.autocomplete import get_suggestions
from apis.search import get_blog_doc_count
from apis.searchad import get_related_keywords
from services.scoring import calculate_golden_score

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")

# 한국어 키워드 확장용 접미사/접두사
SUFFIXES = [
    "추천", "방법", "순위", "비교", "후기", "가격", "효과",
    "부작용", "종류", "만들기", "하는법", "차이", "장단점",
    "TOP", "best", "리뷰", "사용법", "팁", "주의사항",
]


def _event(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def discover_keywords(seed, target_count, config):
    """키워드 발굴 제너레이터 (SSE 스트리밍)"""
    searchad_config = config["searchad"]
    search_config = config["search"]

    seen = set()
    keyword_data = {}  # keyword -> {pc_volume, mobile_volume, comp_idx}
    queue = deque()

    # 시드 키워드로 시작
    queue.append(seed)
    seen.add(seed)

    # 접미사 확장 키워드 추가
    for suffix in SUFFIXES:
        expanded = f"{seed} {suffix}"
        if expanded not in seen:
            seen.add(expanded)
            queue.append(expanded)

    yield _event({
        "type": "status",
        "message": f"'{seed}' 키워드 발굴을 시작합니다...",
    })

    # Phase 1: 키워드 수집 (검색광고 API + 자동완성)
    batch = []
    api_call_count = 0

    while queue and len(keyword_data) < target_count:
        current = queue.popleft()
        batch.append(current)

        # 5개씩 배치로 검색광고 API 호출
        if len(batch) >= 5 or not queue:
            try:
                results = get_related_keywords(batch, searchad_config)
                api_call_count += 1

                for item in results:
                    kw = item["keyword"]
                    if kw not in keyword_data and len(keyword_data) < target_count:
                        keyword_data[kw] = item
                        # 새로 발견한 키워드를 큐에 추가 (탐색 확장)
                        if kw not in seen:
                            seen.add(kw)
                            queue.append(kw)

                yield _event({
                    "type": "progress",
                    "phase": "collecting",
                    "found": len(keyword_data),
                    "target": target_count,
                    "message": f"키워드 수집 중... ({len(keyword_data):,}/{target_count:,}개)",
                    "current_batch": batch[:3],
                })

            except Exception as e:
                yield _event({
                    "type": "warning",
                    "message": f"API 호출 오류: {str(e)}",
                })

            batch = []

            # 검색광고 API 속도 제한
            if api_call_count % 5 == 0:
                time.sleep(1.5)
            else:
                time.sleep(1.2)

        # 자동완성으로 추가 키워드 탐색 (매 3번째 키워드마다)
        if api_call_count % 3 == 0 and len(keyword_data) < target_count:
            suggestions = get_suggestions(current)
            for s in suggestions:
                if s not in seen:
                    seen.add(s)
                    queue.append(s)

    total_keywords = len(keyword_data)
    yield _event({
        "type": "status",
        "message": f"총 {total_keywords:,}개 키워드 수집 완료! 블로그 문서수 조회 중...",
    })

    # Phase 2: 블로그 문서수 조회
    keywords_list = list(keyword_data.keys())
    for i, kw in enumerate(keywords_list):
        doc_count = get_blog_doc_count(kw, search_config)
        keyword_data[kw]["blog_doc_count"] = doc_count

        if (i + 1) % 20 == 0 or i == len(keywords_list) - 1:
            yield _event({
                "type": "progress",
                "phase": "analyzing",
                "found": total_keywords,
                "analyzed": i + 1,
                "target": total_keywords,
                "message": f"문서수 분석 중... ({i + 1:,}/{total_keywords:,}개)",
            })

    # Phase 3: 황금키워드 점수 계산
    yield _event({
        "type": "status",
        "message": "황금키워드 점수 계산 중...",
    })

    for kw, data in keyword_data.items():
        data["total_volume"] = data["pc_volume"] + data["mobile_volume"]
        data["golden_score"] = calculate_golden_score(data)

    # 점수 기준 정렬
    sorted_keywords = sorted(
        keyword_data.values(),
        key=lambda x: x["golden_score"],
        reverse=True,
    )

    # Phase 4: CSV 저장
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"keywords_{seed}_{timestamp}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "키워드", "PC검색량", "모바일검색량", "총검색량",
            "블로그문서수", "경쟁도", "황금키워드점수",
        ])
        for item in sorted_keywords:
            writer.writerow([
                item["keyword"],
                item["pc_volume"],
                item["mobile_volume"],
                item["total_volume"],
                item.get("blog_doc_count", 0),
                item["comp_idx"],
                item["golden_score"],
            ])

    # 최종 결과 전송
    top_keywords = sorted_keywords[:100]  # 상위 100개만 UI에 전송
    yield _event({
        "type": "complete",
        "total": total_keywords,
        "csv_file": filename,
        "message": f"완료! 총 {total_keywords:,}개 키워드를 발굴했습니다.",
        "results": [
            {
                "keyword": item["keyword"],
                "pc_volume": item["pc_volume"],
                "mobile_volume": item["mobile_volume"],
                "total_volume": item["total_volume"],
                "blog_doc_count": item.get("blog_doc_count", 0),
                "comp_idx": item["comp_idx"],
                "golden_score": item["golden_score"],
            }
            for item in top_keywords
        ],
    })
