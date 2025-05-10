# HARUNI (하루니)

하루니는 AI 기반 일기 작성 도우미 서비스입니다. 사용자와의 자연스러운 대화를 통해 일상을 기록하고, 감정 분석 및 일기 요약을 제공합니다.

## 주요 기능

- **자연스러운 대화**: 사용자의 MBTI를 고려한 맞춤형 대화 스타일로 소통합니다.
- **일일 일기 생성**: 대화 내용을 바탕으로 일기를 자동으로 작성합니다.
- **감정 분석**: 대화에서 감지된 감정을 분석하여 일기에 반영합니다.
- **일기 시각화**: 일기 내용을 기반으로 이미지를 생성합니다.
- **주간 감정 분석**: 일주일간의 감정 추이를 분석하고 인사이트를 제공합니다.

## 시스템 아키텍처

하루니는 다음과 같은 핵심 컴포넌트로 구성되어 있습니다:

- **DBAgent**: 데이터베이스 연결 및 쿼리 처리를 담당합니다.
- **ResponseAgent**: 사용자 질문에 대한 응답을 생성합니다.
- **StyleAgent**: 사용자의 선호도에 맞게 응답 스타일을 조정합니다.
- **MemoryAgent**: 대화 맥락을 유지하고 필요한 컨텍스트를 관리합니다.
- **LLM 모듈**: 다양한 대규모 언어 모델(Gemma 등)을 지원합니다.
- **일기 생성 모듈**: 대화를 요약하고 감정을 분석하여 일기를 작성합니다.

## 요구사항

- Python 3.9 이상
- MySQL 데이터베이스
- 필요한 Python 패키지(requirements.txt 참조)

## 설치 및 설정

1. 저장소 클론:
   ```bash
   git clone https://github.com/your-repo/HARUNI.git
   cd HARUNI
   ```

2. 가상환경 생성 및 활성화:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```

4. 환경 변수 설정:
   `.env` 파일을 생성하고 다음 내용을 추가합니다.
   ```
   DB_HOST=your_db_host
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=haruni
   OPENAI_API_KEY=your_openai_api_key
   ```

## 실행 방법

1. 서버 실행:
   ```bash
   cd haruni
   python app.py
   ```

2. API 테스트:
   ```bash
   python test_api.py
   ```

## API 엔드포인트

하루니는 다음과 같은 API 엔드포인트를 제공합니다:

### 1. 대화 API
- **URL**: `/api/v1/question`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "userId": "사용자 ID",
    "content": "사용자 메시지",
    "sendingTime": "메시지 전송 시간",
    "gender": "성별",
    "sendingDate": "메시지 전송 날짜",
    "mbti": "사용자 MBTI",
    "nickname": "사용자 닉네임"
  }
  ```
- **Response**:
  ```json
  {
    "user_id": "사용자 ID",
    "response": "하루니의 응답 메시지"
  }
  ```

### 2. 일일 일기 API
- **URL**: `/api/v1/day-diary`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "conversation": [대화 내역 배열]
  }
  ```
- **Response**:
  ```json
  {
    "mood": "감정 분석 결과",
    "daySummaryDescription": "일기 내용",
    "daySummaryImage": "이미지 URL",
    "date": "날짜"
  }
  ```

### 3. 주간 분석 API
- **URL**: `/api/v1/week-status`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "weekly_data": [주간 데이터 배열]
  }
  ```
- **Response**:
  ```json
  {
    "feedback": "주간 피드백",
    "week_summary": "주간 요약",
    "suggestion": "제안사항",
    "recommendation": "추천사항"
  }
  ```

## 로깅

하루니는 `haruni.log` 파일에 주요 이벤트와 오류를 기록합니다. 로그 파일을 통해 시스템의 동작 상태를 모니터링할 수 있습니다.

## 프로젝트 구조

```
HARUNI/
├── haruni/
│   ├── app.py                # 메인 Flask 애플리케이션
│   ├── dbAgent.py            # 데이터베이스 에이전트
│   ├── responseAgent.py      # 응답 생성 에이전트
│   ├── styleAgent.py         # 스타일 조정 에이전트
│   ├── memoryAgent.py        # 메모리 관리 에이전트
│   ├── llm.py                # LLM 모듈
│   ├── create_diary.py       # 일기 생성 모듈
│   └── test_api.py           # API 테스트 도구
├── .env                      # 환경 변수 파일
└── README.md                 # 이 파일
```

## License

이 프로젝트는 [MIT 라이선스](LICENSE)로 배포됩니다. 