from flask import Flask, request, jsonify
import os
import json
import logging
from dbAgent import DBAgent
from memoryAgent import MemoryAgent
from responseAgent import ResponseAgent
from llm import llm
from create_diary import summarize_conversation, create_daily_diary_image, analyze_weekly_sentiment_separated
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FlaskApp")

load_dotenv()
logger.info("환경 변수 로드 완료")

app = Flask(__name__)
logger.info("Flask 앱 초기화")

# 모델 인스턴스 생성 (서버 시작 시 한 번만 로드)
# model = llm("google/gemma-3-4b-it")
# model = llm("google/gemma-3-1b-it")
logger.info("LLM 모델 초기화 시작")
model = llm("ollama-gemma3:4b-it-qat")
#model = llm("google/gemma-3-4b-it-qat-q4_0-gguf")
logger.info("LLM 모델 초기화 완료")

db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# 서버 시작 시 Agent 객체 한 번만 생성
logger.info("에이전트 객체 초기화 시작")
db_agent = DBAgent(db_config, model)
memory_agent = MemoryAgent(model)
response_agent = ResponseAgent(model)
logger.info("에이전트 객체 초기화 완료")

# 전역 메시지 히스토리 관리 (사용자 ID별)
message_histories = {}

@app.route('/api/v1/question', methods=['POST'])
def chat():
    logger.info("질문 API 요청 수신")
    # 요청 데이터 파싱
    data = request.json
    user_id = data.get('userId')
    question = data.get('content')

    gender = data.get('gender')
    nickname = data.get('nickname')
    user_mbti = data.get('mbti')

    user_info = {
        "gender" : gender,
        "nickname" : nickname,
        "user_mbti" : user_mbti
    }

    sendingDate = data.get('sendingDate')
    sendingTime = data.get('sendingTime')

    haruniPersonality = data.get('haruniPersonality')
    
    if not user_id or not question:
        logger.warning("필수 매개변수 누락: user_id 또는 question")
        return jsonify({'error': 'user_id와 question이 필요합니다.'}), 400
    
    try:
        logger.info(f"사용자 ID: {user_id}")
        # 질문 전체 내용 로깅
        logger.info(f"질문 내용: {question}")
        
        # 사용자별 메시지 히스토리 가져오기 (없으면 빈 리스트 생성)
        msg_history = message_histories.get(user_id, [])
        
        # 현재 대화 컨텍스트에 필요한 히스토리만 필터링
        if len(msg_history) > 0:
            filtered_history = memory_agent.filter_context(msg_history, question)
        else:
            filtered_history = []

        # 1. DB Agent 처리 (사용자 정보 및 관련 컨텍스트 가져오기)
        db_agent.set_user_id(user_id)  # 사용자 ID 설정
        needs_db, db_result = db_agent.process_question(question, sendingDate, sendingTime)     
        
        # 응답 생성
        if needs_db:
            #logger.info(f"DB 참조 결과: {db_result[:200]}..." if len(db_result) > 200 else f"DB 참조 결과: {db_result}")
            #logger.info(f"DB 참조 결과: {db_result}")
            response, updated_history = response_agent.generate_response(question, filtered_history, db_result, user_info, user_mbti)
        else:
            response, updated_history = response_agent.generate_response(question, filtered_history, None, user_info, user_mbti)

        # 메시지 히스토리 업데이트
        message_histories[user_id] = updated_history
        
        # 응답 데이터 구성
        response_data = {
            'user_id': user_id,
            'response': response,
        }

        # 응답 내용 로깅
        logger.info(f"응답 내용: {response}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"질문 처리 중 오류 발생: {str(e)}", exc_info=True)
        print(e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/day-diary', methods=['POST'])
def day_diary():
    logger.info("일일 일기 API 요청 수신")
    try:
        conversation = request.json.get("conversation", [])
        logger.info(f"대화 내역 수신: {len(conversation)}개 메시지")
        
        mood, diary, illustration = summarize_conversation(conversation)
        logger.info(f"요약 결과 - 감정: {mood}")
        logger.info(f"일기 내용: {diary}")
        
        image_url = create_daily_diary_image(illustration)
        
        response_data = {
            "mood": mood,
            "daySummaryDescription": diary,
            "daySummaryImage": image_url,
            "date" : "2025-05-09"
        }
        logger.info("일일 일기 응답 생성 완료")
        return jsonify(response_data) # 수정해야함
    except Exception as e:
        logger.error(f"일일 일기 처리 중 오류 발생: {str(e)}", exc_info=True)
        return jsonify({"error": f"처리 중 오류 발생: {str(e)}"}), 500


@app.route('/api/v1/week-status', methods=['POST'])
def week_status():
    logger.info("주간 분석 API 요청 수신")
    try:
        weekly_data = request.json.get("weekly_data", [])
        logger.info(f"주간 데이터 수신: {len(weekly_data)}일치")
        
        feedback, summary, suggestions, recs = analyze_weekly_sentiment_separated(weekly_data)
        logger.info(f"주간 분석 결과 - 피드백: {feedback[:200]}..." if len(feedback) > 200 else f"주간 분석 결과 - 피드백: {feedback}")
        
        response_data = {
            "feedback": feedback,
            "week_summary": summary,
            "suggestion": suggestions,
            "recommendation": recs
        }
        logger.info("주간 분석 응답 생성 완료")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"주간 분석 처리 중 오류 발생: {str(e)}", exc_info=True)
        return jsonify({"error": f"처리 중 오류 발생: {str(e)}"}), 500


if __name__ == '__main__':
    logger.info("하루니 서버 시작")
    app.run(host='0.0.0.0', port=5000, debug=True) 
    logger.info("하루니 서버 종료") 