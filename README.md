# 네이버 키워드 채굴기

시드 키워드 하나로 연관 키워드를 자동 발굴하고, 검색량/경쟁도/블로그 문서수를 분석하여 **황금 키워드**를 찾아주는 도구입니다.

## 필요한 API 키

시작 전 아래 2가지 API 키를 발급받아야 합니다.

| API | 발급처 | 필요한 값 |
|-----|--------|-----------|
| 네이버 검색광고 API | [searchad.naver.com](https://searchad.naver.com) → 도구 → API 사용 관리 | Customer ID, API Key, Secret Key |
| 네이버 검색 API | [developers.naver.com](https://developers.naver.com) → 애플리케이션 등록 (검색) | Client ID, Client Secret |

## 실행 방법 (로컬)

**Mac/Linux:**
```bash
git clone https://github.com/wgyuh-oss/keyWord.git && cd keyWord && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python app.py
```

**Windows:**
```bash
git clone https://github.com/wgyuh-oss/keyWord.git && cd keyWord && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && python app.py
```

브라우저에서 http://localhost:5000 접속 후 API 키를 입력하면 바로 사용 가능합니다.

## 주요 기능

- **BFS 키워드 확장** - 검색광고 API + 자동완성으로 연관 키워드 자동 탐색
- **황금 키워드 점수** - (검색량 / 블로그 문서수) / 경쟁도로 블루오션 키워드 발굴
- **CSV 내보내기** - 결과를 CSV 파일로 다운로드
- **실시간 진행 표시** - SSE 스트리밍으로 수집 현황 실시간 확인

## 참고

- 네이버 검색광고 API는 **한국 IP에서만** 동작합니다 (해외 서버 배포 불가)
- Streamlit 버전(`streamlit_app.py`)도 포함되어 있으나 위 제한으로 클라우드 배포는 불가합니다
