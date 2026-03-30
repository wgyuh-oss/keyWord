import csv
import hashlib
import hmac
import base64
import io
import os
import time
from collections import deque
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="네이버 키워드 채굴기",
    page_icon="⛏️",
    layout="wide",
)

# ─────────────────────────────────────────────
# 커스텀 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00c73c, #00b4d8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-title {
        text-align: center;
        color: #8b949e;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .golden-badge {
        display: inline-block;
        background: linear-gradient(135deg, #f0b429, #f59e0b);
        color: #000;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 700;
    }
    .stat-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 800;
        color: #00c73c;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #8b949e;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# API 클라이언트 함수들
# ─────────────────────────────────────────────

def searchad_get_related(hint_keywords, config):
    """네이버 검색광고 API - 관련 키워드 + 검색량 조회"""
    timestamp = str(round(time.time() * 1000))
    sign_str = f"{timestamp}.GET./keywordstool"
    signature = base64.b64encode(
        hmac.new(
            config["secret_key"].encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    headers = {
        "X-API-KEY": config["api_key"],
        "X-CUSTOMER": config["customer_id"],
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }
    try:
        # 쉼표가 %2C로 인코딩되면 API가 400 에러를 반환하므로 URL을 직접 구성
        from urllib.parse import quote
        encoded_kws = ",".join(quote(kw, safe="") for kw in hint_keywords)
        url = f"https://api.searchad.naver.com/keywordstool?hintKeywords={encoded_kws}&showDetail=1"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.warning(f"검색광고 API 오류: {e}")
        return []

    results = []
    for item in data.get("keywordList", []):
        results.append({
            "keyword": item.get("relKeyword", ""),
            "pc_volume": _parse_vol(item.get("monthlyPcQcCnt", 0)),
            "mobile_volume": _parse_vol(item.get("monthlyMobileQcCnt", 0)),
            "comp_idx": item.get("compIdx", "중간"),
        })
    return results


def get_blog_count(keyword, config):
    """네이버 검색 API - 블로그 문서수 조회"""
    headers = {
        "X-Naver-Client-Id": config["client_id"],
        "X-Naver-Client-Secret": config["client_secret"],
    }
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/blog.json",
            headers=headers, params={"query": keyword, "display": 1}, timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("total", 0)
    except Exception:
        return 0


def get_autocomplete(keyword):
    """네이버 자동완성 제안어 수집"""
    params = {
        "q": keyword, "con": "1", "frm": "nx", "ans": "2",
        "r_format": "json", "r_enc": "UTF-8", "r_unicode": "0",
        "t_koreng": "1", "run": "2", "rev": "4", "q_enc": "UTF-8", "st": "100",
    }
    try:
        resp = requests.get("https://ac.search.naver.com/nx/ac", params=params, timeout=5)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items and len(items) > 0:
            return [i[0] for i in items[0] if isinstance(i, list) and i]
    except Exception:
        pass
    return []


def _parse_vol(val):
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str) and val.strip().replace(",", "").isdigit():
        return int(val.strip().replace(",", ""))
    return 5  # "< 10" 등


def calc_golden_score(row):
    total = row["pc_volume"] + row["mobile_volume"]
    blog = max(row.get("blog_doc_count", 1), 1)
    comp_w = {"높음": 3.0, "중간": 2.0, "낮음": 1.0}.get(row.get("comp_idx", "중간"), 2.0)
    score = (total / blog) / comp_w
    if total > 0 and (row["mobile_volume"] / total) > 0.7:
        score *= 1.1
    return round(score, 4)


# ─────────────────────────────────────────────
# 키워드 확장용 접미사
# ─────────────────────────────────────────────
SUFFIXES = [
    "추천", "방법", "순위", "비교", "후기", "가격", "효과",
    "부작용", "종류", "만들기", "하는법", "차이", "장단점",
    "TOP", "best", "리뷰", "사용법", "팁", "주의사항",
]


# ─────────────────────────────────────────────
# 메인 UI
# ─────────────────────────────────────────────

st.markdown('<h1 class="main-title">⛏️ 네이버 키워드 채굴기</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">시드 키워드 하나로 수천~수만 개 황금 키워드를 자동 발굴합니다</p>', unsafe_allow_html=True)


# ── 사용방법 모달 ──
@st.dialog("📖 사용방법 가이드", width="large")
def show_guide():
    st.markdown("## 1단계: API 키 발급 (최초 1회)")
    st.markdown("""
    이 프로그램은 **네이버 공식 API**를 사용합니다. 두 가지 API 키가 필요하며, 모두 **무료**입니다.
    """)

    # ── 검색광고 API 상세 안내 ──
    st.markdown("---")
    st.markdown("### 🔑 검색광고 API (키워드 검색량 조회용)")
    st.markdown("**필요한 키 3개**: Customer ID, API Key, Secret Key")

    st.markdown("""
    | 순서 | 할 일 | 상세 설명 |
    |:---:|------|---------|
    | 1 | **[네이버 검색광고](https://searchad.naver.com)** 접속 | 네이버 아이디로 로그인 |
    | 2 | **광고주 가입** | 처음이면 가입 화면이 뜹니다. **무료**이며, 광고비 충전은 필요 없습니다 |
    | 3 | 상단 메뉴에서 **`도구`** 클릭 | "광고관리", "정보관리", "보고서" 옆에 있습니다 |
    | 4 | 드롭다운에서 **`API 사용 관리`** 클릭 | API 관리 페이지로 이동합니다 |
    | 5 | **`API 라이선스 키 발급`** 버튼 클릭 | 키가 즉시 생성됩니다 |
    """)

    st.success("""
    **발급 완료 후 확인할 3가지:**
    - **Customer ID** → 광고 계정 상단에 표시되는 숫자 ID
    - **API Key** → 발급된 API 라이선스 키 (긴 영문+숫자 문자열)
    - **Secret Key** → 발급된 비밀 키 (긴 영문+숫자 문자열)
    """)

    with st.expander("⚠️ 도구 메뉴가 안 보여요"):
        st.markdown("""
        - 로그인 직후에는 **광고관리** 페이지가 보입니다
        - 화면 **상단 네비게이션 바**에서 `도구` 를 찾으세요
        - 모바일에서는 메뉴가 다를 수 있습니다. **PC 브라우저**를 사용해주세요
        - 광고주 가입이 안 되어 있으면 도구 메뉴가 안 보일 수 있습니다. 먼저 가입을 완료해주세요
        """)

    # ── 네이버 검색 API 상세 안내 ──
    st.markdown("---")
    st.markdown("### 🔍 네이버 검색 API (블로그 문서수 조회용)")
    st.markdown("**필요한 키 2개**: Client ID, Client Secret")

    st.markdown("""
    | 순서 | 할 일 | 상세 설명 |
    |:---:|------|---------|
    | 1 | **[네이버 개발자센터](https://developers.naver.com)** 접속 | 네이버 아이디로 로그인 |
    | 2 | 상단 메뉴 **`Application`** → **`애플리케이션 등록`** 클릭 | 새 앱을 만듭니다 |
    | 3 | **애플리케이션 이름** 입력 | 아무거나 OK (예: `키워드분석기`) |
    | 4 | **사용 API** 드롭다운에서 **`검색`** 선택 | 반드시 "검색"을 선택해야 합니다 |
    | 5 | **비로그인 오픈 API 서비스 환경** → **WEB 설정** | 환경 추가 드롭다운에서 WEB을 선택하세요 |
    | 6 | **웹 서비스 URL**에 `http://localhost` 입력 | 정확히 이대로 입력하면 됩니다 |
    | 7 | **`등록하기`** 버튼 클릭 | 즉시 발급됩니다 |
    """)

    st.success("""
    **등록 완료 후 확인할 2가지:**
    - **Client ID** → 내 애플리케이션 목록에서 확인 (영문+숫자 문자열)
    - **Client Secret** → Client ID 아래에 표시 (영문+숫자 문자열)
    """)

    with st.expander("⚠️ 애플리케이션 등록 시 주의사항"):
        st.markdown("""
        - 사용 API에서 **"검색"** 을 꼭 선택해야 합니다 (다른 것 선택하면 작동 안 함)
        - 추가로 **"데이터랩 (검색어트렌드)"** 도 선택하면 나중에 트렌드 분석에 활용 가능합니다
        - WEB 설정 URL은 `http://localhost` 그대로 입력 (https 아님)
        - 하루 **25,000건**까지 무료 호출 가능합니다
        """)

    st.info("💡 **두 곳 모두 완전 무료**이고, 가입 후 5분이면 발급이 완료됩니다.")

    st.divider()
    st.markdown("## 2단계: API 키 입력")
    st.markdown("""
    1. 왼쪽 **사이드바**(◀ 버튼)를 열어주세요
    2. 발급받은 **5개 키**를 각 입력란에 붙여넣기
    3. **💾 API 키 저장** 버튼 클릭
    4. **"🟢 API 연결됨"** 메시지가 뜨면 성공!

    > Streamlit Cloud에 배포한 경우: **Settings > Secrets**에 저장하면 매번 입력할 필요 없이 영구 적용됩니다
    """)

    st.divider()
    st.markdown("## 3단계: 키워드 발굴")
    st.markdown("""
    1. **시드 키워드** 입력 (예: 다이어트, 부동산, 강아지 사료...)
    2. **수집 목표 개수** 설정 (기본 500개, 최대 50,000개)
    3. **키워드 발굴 시작** 버튼 클릭
    4. 자동으로 관련 키워드를 재귀적으로 확장 수집합니다
    """)

    st.divider()
    st.markdown("## 4단계: 결과 분석")
    st.markdown("""
    수집이 완료되면 각 키워드별로 다음 데이터가 표시됩니다:

    | 항목 | 설명 |
    |------|------|
    | **PC검색량** | 월간 PC 검색 횟수 |
    | **모바일검색량** | 월간 모바일 검색 횟수 |
    | **총검색량** | PC + 모바일 합계 |
    | **블로그문서수** | 해당 키워드의 네이버 블로그 문서 수 |
    | **경쟁도** | 광고 경쟁 정도 (높음/중간/낮음) |
    | **황금키워드점수** | 검색량 대비 문서수가 적을수록 높은 점수 |
    """)

    st.divider()
    st.markdown("## ⭐ 황금 키워드란?")
    st.info("""
    **황금 키워드** = 검색량은 높은데, 관련 블로그 글은 적은 키워드

    이런 키워드로 블로그 글을 발행하면 **경쟁이 적어 상위 노출 확률이 높습니다.**

    **황금점수 공식**: (총검색량 ÷ 블로그문서수) ÷ 경쟁도 가중치

    점수가 높을수록 → 수요는 많고 공급은 적은 → 상위 노출 기회!
    """)

    st.divider()
    st.markdown("## 💡 활용 팁")
    st.markdown("""
    - **황금점수 상위 10%** 키워드를 집중 공략하세요
    - **경쟁도 "낮음"** 필터를 적용하면 더 쉬운 키워드를 찾을 수 있습니다
    - CSV 다운로드 후 엑셀에서 추가 분석 가능합니다
    - 시드 키워드를 바꿔가며 다양한 주제를 탐색해보세요
    """)

    if st.button("확인", use_container_width=True, type="primary"):
        st.rerun()


# 사용방법 버튼
_, center_col, _ = st.columns([2, 1, 2])
with center_col:
    if st.button("📖 사용방법 보기", use_container_width=True):
        show_guide()

st.write("")

# ── API 키 설정 (사이드바) ──
with st.sidebar:
    st.header("🔑 API 키 설정")
    st.caption("한 번 입력하면 자동 저장됩니다")

    st.subheader("검색광고 API")
    customer_id = st.text_input("Customer ID", value=st.session_state.get("customer_id", ""), type="default")
    api_key = st.text_input("API Key", value=st.session_state.get("api_key", ""), type="default")
    secret_key = st.text_input("Secret Key", value=st.session_state.get("secret_key", ""), type="password")

    st.subheader("네이버 검색 API")
    client_id = st.text_input("Client ID", value=st.session_state.get("client_id", ""), type="default")
    client_secret = st.text_input("Client Secret", value=st.session_state.get("client_secret", ""), type="password")

    if st.button("💾 API 키 저장", use_container_width=True):
        if all([customer_id, api_key, secret_key, client_id, client_secret]):
            st.session_state["customer_id"] = customer_id
            st.session_state["api_key"] = api_key
            st.session_state["secret_key"] = secret_key
            st.session_state["client_id"] = client_id
            st.session_state["client_secret"] = client_secret
            st.session_state["api_configured"] = True
            # secrets.toml 대신 session_state에 저장 (Streamlit Cloud에서는 Secrets 사용)
            st.success("✅ API 키가 저장되었습니다!")
        else:
            st.error("모든 항목을 입력해주세요.")

    # Streamlit Cloud Secrets 자동 로드
    try:
        if not st.session_state.get("api_configured"):
            st.session_state["customer_id"] = st.secrets["searchad"]["customer_id"]
            st.session_state["api_key"] = st.secrets["searchad"]["api_key"]
            st.session_state["secret_key"] = st.secrets["searchad"]["secret_key"]
            st.session_state["client_id"] = st.secrets["search"]["client_id"]
            st.session_state["client_secret"] = st.secrets["search"]["client_secret"]
            st.session_state["api_configured"] = True
    except Exception:
        pass

    api_ready = st.session_state.get("api_configured", False)
    if api_ready:
        st.success("🟢 API 연결됨")
    else:
        st.warning("🔴 API 키를 입력해주세요")

# ── 키워드 입력 ──
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    seed_keyword = st.text_input("🔍 시드 키워드", placeholder="예: 다이어트, 부동산, 주식투자...")
with col2:
    target_count = st.number_input("수집 목표", min_value=10, max_value=50000, value=500, step=100)
with col3:
    st.write("")
    st.write("")
    start_clicked = st.button("⛏️ 키워드 발굴 시작", use_container_width=True, type="primary", disabled=not api_ready)

# ── 키워드 발굴 실행 ──
if start_clicked and seed_keyword and api_ready:
    searchad_config = {
        "customer_id": st.session_state["customer_id"],
        "api_key": st.session_state["api_key"],
        "secret_key": st.session_state["secret_key"],
    }
    search_config = {
        "client_id": st.session_state["client_id"],
        "client_secret": st.session_state["client_secret"],
    }

    # 진행 상태 UI
    progress_bar = st.progress(0, text="키워드 채굴 준비 중...")
    status_text = st.empty()
    log_area = st.empty()
    logs = []

    seen = set()
    keyword_data = {}
    queue = deque()

    # 시드 + 접미사 확장
    queue.append(seed_keyword)
    seen.add(seed_keyword)
    for suffix in SUFFIXES:
        exp = f"{seed_keyword} {suffix}"
        if exp not in seen:
            seen.add(exp)
            queue.append(exp)

    def add_log(msg):
        t = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{t}] {msg}")
        log_area.code("\n".join(logs[-10:]), language=None)

    add_log(f"'{seed_keyword}' 키워드 발굴 시작!")

    # Phase 1: 키워드 수집
    batch = []
    api_calls = 0

    while queue and len(keyword_data) < target_count:
        current = queue.popleft()
        batch.append(current)

        if len(batch) >= 5 or not queue:
            results = searchad_get_related(batch, searchad_config)
            api_calls += 1

            for item in results:
                kw = item["keyword"]
                if kw not in keyword_data and len(keyword_data) < target_count:
                    keyword_data[kw] = item
                    if kw not in seen:
                        seen.add(kw)
                        queue.append(kw)

            pct = min(len(keyword_data) / target_count, 1.0)
            progress_bar.progress(pct * 0.7, text=f"키워드 수집 중... ({len(keyword_data):,}/{target_count:,}개)")
            status_text.info(f"🔍 수집된 키워드: **{len(keyword_data):,}개** | 대기열: {len(queue):,}개")

            batch = []
            if api_calls % 5 == 0:
                time.sleep(1.5)
            else:
                time.sleep(1.2)

        # 자동완성 확장
        if api_calls % 3 == 0 and len(keyword_data) < target_count:
            suggestions = get_autocomplete(current)
            for s in suggestions:
                if s not in seen:
                    seen.add(s)
                    queue.append(s)

    total_kw = len(keyword_data)
    add_log(f"키워드 {total_kw:,}개 수집 완료! 블로그 문서수 분석 시작...")

    # Phase 2: 블로그 문서수 조회
    kw_list = list(keyword_data.keys())
    for i, kw in enumerate(kw_list):
        keyword_data[kw]["blog_doc_count"] = get_blog_count(kw, search_config)

        if (i + 1) % 20 == 0 or i == len(kw_list) - 1:
            pct = 0.7 + (i / len(kw_list)) * 0.25
            progress_bar.progress(min(pct, 0.95), text=f"문서수 분석 중... ({i + 1:,}/{total_kw:,}개)")

        time.sleep(0.1)

    # Phase 3: 점수 계산
    add_log("황금키워드 점수 계산 중...")
    for kw, data in keyword_data.items():
        data["total_volume"] = data["pc_volume"] + data["mobile_volume"]
        data["golden_score"] = calc_golden_score(data)

    progress_bar.progress(1.0, text="✅ 채굴 완료!")
    add_log(f"총 {total_kw:,}개 키워드 발굴 완료!")

    # ── DataFrame 생성 ──
    df = pd.DataFrame(keyword_data.values())
    df = df.sort_values("golden_score", ascending=False).reset_index(drop=True)
    df.index += 1
    df = df.rename(columns={
        "keyword": "키워드",
        "pc_volume": "PC검색량",
        "mobile_volume": "모바일검색량",
        "total_volume": "총검색량",
        "blog_doc_count": "블로그문서수",
        "comp_idx": "경쟁도",
        "golden_score": "황금키워드점수",
    })

    st.session_state["results_df"] = df
    st.session_state["mining_done"] = True

# ── 결과 표시 ──
if st.session_state.get("mining_done") and st.session_state.get("results_df") is not None:
    df = st.session_state["results_df"]

    st.divider()

    # 통계 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 키워드", f"{len(df):,}개")
    with col2:
        golden_count = max(1, len(df) // 10)
        st.metric("황금 키워드 (상위 10%)", f"{golden_count:,}개")
    with col3:
        avg_volume = int(df["총검색량"].mean()) if len(df) > 0 else 0
        st.metric("평균 검색량", f"{avg_volume:,}")
    with col4:
        top_score = df["황금키워드점수"].max() if len(df) > 0 else 0
        st.metric("최고 황금점수", f"{top_score:.4f}")

    # CSV 다운로드
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=True, encoding="utf-8-sig")

    st.download_button(
        label="📥 CSV 다운로드",
        data=csv_buffer.getvalue().encode("utf-8-sig"),
        file_name=f"keywords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # 필터
    col1, col2 = st.columns([2, 1])
    with col1:
        search_filter = st.text_input("🔎 키워드 검색", placeholder="결과 내 키워드 검색...")
    with col2:
        comp_filter = st.multiselect("경쟁도 필터", ["높음", "중간", "낮음"], default=["높음", "중간", "낮음"])

    filtered_df = df.copy()
    if search_filter:
        filtered_df = filtered_df[filtered_df["키워드"].str.contains(search_filter, case=False, na=False)]
    if comp_filter:
        filtered_df = filtered_df[filtered_df["경쟁도"].isin(comp_filter)]

    # 결과 테이블
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=600,
        column_config={
            "PC검색량": st.column_config.NumberColumn(format="%d"),
            "모바일검색량": st.column_config.NumberColumn(format="%d"),
            "총검색량": st.column_config.NumberColumn(format="%d"),
            "블로그문서수": st.column_config.NumberColumn(format="%d"),
            "황금키워드점수": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    # 상위 20개 차트
    st.subheader("📊 상위 20 황금 키워드")
    top20 = df.head(20).copy()
    chart_data = top20.set_index("키워드")[["총검색량", "블로그문서수"]]
    st.bar_chart(chart_data)
