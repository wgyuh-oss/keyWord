def calculate_golden_score(keyword_data):
    """황금 키워드 점수 계산: 검색량 높고 문서수 적은 키워드일수록 높은 점수"""
    total_volume = keyword_data["pc_volume"] + keyword_data["mobile_volume"]
    blog_count = max(keyword_data.get("blog_doc_count", 1), 1)

    comp_map = {"높음": 3.0, "중간": 2.0, "낮음": 1.0}
    comp_weight = comp_map.get(keyword_data.get("comp_idx", "중간"), 2.0)

    # 핵심 비율: 검색 수요 / 콘텐츠 공급
    ratio = total_volume / blog_count

    # 경쟁도 반영
    score = ratio / comp_weight

    # 모바일 비중 높으면 보너스 (한국은 모바일 중심)
    if total_volume > 0:
        mobile_ratio = keyword_data["mobile_volume"] / total_volume
        if mobile_ratio > 0.7:
            score *= 1.1

    return round(score, 4)
