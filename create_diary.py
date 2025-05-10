import json
import openai
import os
import re
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("haruni")

# .env 파일 로드
load_dotenv()
logger.info("환경변수 로드 완료")

# OpenAI API 키 설정
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.error("API Key가 설정되지 않았습니다. .env 파일을 확인하세요.")
    raise ValueError("API Key가 설정되지 않았습니다. .env 파일을 확인하세요. ")
logger.info("OpenAI API 키 설정 완료")

client = openai.OpenAI(api_key=api_key)

app = Flask(__name__)
logger.info("Flask 앱 초기화 완료")

# JSON 파일 로드
def load_conversation_from_json(file_path):
    """
    JSON 파일에서 대화 데이터를 불러오는 함수
    """
    logger.info(f"JSON 파일 로드 시도: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            logger.info(f"JSON 파일 로드 성공: {file_path}")
            return data
    except Exception as e:
        logger.error(f"JSON 파일 로드 실패: {e}")
        print(f" JSON 파일 로드 실패: {e} ")
        return None

def summarize_conversation(conversation_history):
    """
    하루 동안의 대화를 2~4개의 간결한 문장으로 요약하고 감정을 분류하는 함수.

    반환값:
    1. 기분 분류: happy(긍정적), normal(중립적), sad(부정적) 중 하나
    2. 일기 형식 요약: 사용자에게 반환되는 일기 형식의 요약문
    3. 일러스트레이션 요약: 출력될 DALL-E 이미지를 더 잘 묘사하기 위해 생성하는 요약문
    """
    logger.info("대화 요약 및 감정 분석 시작")
    prompt_for_gpt = """
    The following is a record of my conversation with the AI chatbot, HARUNI.
    Based on this conversation, generate two summaries and classify the overall sentiment:

    1. DIARY_SUMMARY:  
    Write a personal diary entry in 2 to 4 sentences, as if I were writing it myself at the end of the day.  
    Avoid dry summaries—use a soft, reflective tone, like quietly talking to yourself.  
    Include not only what I did, but how it felt, what the atmosphere was like, and any small emotional details.  
    The tone should be warm, honest, and comforting—focus on moments like warm sunlight through the window, the hush of the evening, or the feeling of being proud or tired.  

    2. ILLUSTRATION_SUMMARY:  
    Describe one single, most memorable moment from the day in a way that can be visually illustrated.  
    Avoid summarizing multiple events. Instead, zoom in on one clear scene—like a snapshot frozen in time.  
    Describe the lighting, colors, textures, and emotional mood of that moment.  
    Use soft, poetic visual language that helps capture the mood (e.g., "a quiet room bathed in golden light," "sunlight pooling on a wooden desk," "a gentle breeze rustling the curtains").  
    This description will be used to create a dreamy, atmospheric illustration—so focus on what makes the moment visually and emotionally special.

    3. SENTIMENT:  
    Classify the overall sentiment of the conversation as either POSITIVE, NEUTRAL, or NEGATIVE based on the emotional tone, user satisfaction, and general mood of the interaction.

    Return your response in the following format exactly:

    DIARY_SUMMARY: <your diary summary here>  
    ILLUSTRATION_SUMMARY: <your illustration summary here>  
    SENTIMENT: <POSITIVE/NEUTRAL/NEGATIVE>

    The summaries must be written in Korean.
    """

    messages = [{"role": "system", "content": prompt_for_gpt}] + conversation_history
    logger.info(f"GPT 분석 요청: 대화 내역 {len(conversation_history)}개 메시지 처리")

    try:
        logger.info("GPT API 호출 시작")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.6,
            max_tokens=400
        )
        logger.info("GPT API 호출 완료")
        full_response = response.choices[0].message.content
        logger.debug(f"GPT 응답 전문: {full_response}")

        diary_marker = "DIARY_SUMMARY:"
        illust_marker = "ILLUSTRATION_SUMMARY:"
        sentiment_marker = "SENTIMENT:"

        diary_summary = ""
        illustration_summary = ""
        mood = "normal"

        if diary_marker in full_response:
            diary_start = full_response.find(diary_marker) + len(diary_marker)
            diary_end = full_response.find(illust_marker) if illust_marker in full_response else len(full_response)
            diary_summary = full_response[diary_start:diary_end].strip()
            logger.info("일기 요약 추출 완료")

        if illust_marker in full_response:
            illust_start = full_response.find(illust_marker) + len(illust_marker)
            illust_end = full_response.find(sentiment_marker) if sentiment_marker in full_response else len(full_response)
            illustration_summary = full_response[illust_start:illust_end].strip()
            logger.info("일러스트레이션 요약 추출 완료")

        if sentiment_marker in full_response:
            sentiment_start = full_response.find(sentiment_marker) + len(sentiment_marker)
            sentiment_text = full_response[sentiment_start:].strip().upper()

            if "POSITIVE" in sentiment_text:
                mood = "happy"
            elif "NEGATIVE" in sentiment_text:
                mood = "sad"
            else:
                mood = "normal"
            logger.info(f"감정 분석 결과: {mood}")

        if not diary_summary and not illustration_summary:
            logger.warning("요약 추출 실패, 전체 응답을 일기 요약으로 사용")
            diary_summary = full_response.strip()

        logger.info("대화 요약 및 감정 분석 완료")
        return mood, diary_summary, illustration_summary

    except Exception as e:
        logger.error(f"GPT 요약 생성 실패: {e}")
        print(f"GPT 요약 생성 실패: {e} ")
        return "normal", None, None


def analyze_weekly_sentiment_separated(weekly_data):
    """
    일주일간의 감정 분류와 일기 내용을 분석하여 4가지 피드백 항목으로 나누어 제공하는 함수

    반환값:
    - week_feedback: 전반적인 따뜻한 피드백
    - week_summary: 이번 주 돌아보기
    - suggestions: 다음 주를 위한 작은 제안
    - recommendation: 하루니의 소소한 추천
    """
    logger.info("주간 감정 분석 시작")
    if not weekly_data or len(weekly_data) == 0:
        logger.warning("분석할 주간 데이터가 없음")
        return "분석할 데이터가 없습니다.", "", "", ""

    formatted_data = ""
    for i, day_data in enumerate(weekly_data):
        date = day_data.get("date", f"Day {i+1}")
        sentiment = day_data.get("sentiment", "기록 없음")
        diary = day_data.get("diary", "기록 없음")
        formatted_data += f"Date: {date}\nSentiment: {sentiment}\nDiary Entry: {diary}\n\n"
    
    logger.info(f"주간 분석 대상: {len(weekly_data)}일치 데이터")

    prompt_for_gpt = f"""
다음은 사용자와 AI 챗봇이 나눈 일주일 간의 대화 내용을 바탕으로 요약된 감정과 일기입니다:

{formatted_data}

이 데이터를 바탕으로 다음의 4가지 항목으로 나누어 자연스럽고 따뜻한 톤으로 작성해 주세요.
각 항목은 사용자의 감정을 공감하며 구체적인 일기 내용을 바탕으로 작성해야 합니다.
형식은 아래와 같으며, 모든 응답은 한국어로 해 주세요.

1. [WEEK_FEEDBACK]  
Based on the emotional flow and meaningful moments from the past week, write a warm, empathetic message as if it were from a close friend.  
- Do not include phrases like "The overall sentiment of the week was..."  
- Start directly as a paragraph, focusing on subtle emotional transitions and moments of reflection.  
- Avoid evaluative or overly structured language—just a gentle, heartfelt tone.

2. [WEEK_SUMMARY]  
Summarize the user's recurring emotions and activities this week in a natural, reflective tone.  
- Do not use a title like "Weekly Summary"—begin with the paragraph right away.  
- Feel free to use gentle speculative expressions such as "It seems that..." or "You often appeared to..."  
- Keep the language grounded and conversational rather than poetic.

3. [SUGGESTIONS]  
Provide 3 gentle suggestions for the coming week.  
- Two should build on this week's positive experiences.  
- One should be something new the user hasn't tried yet but might enjoy.  
- Use a numbered list like:  
  1. ~  
  2. ~  
  3. ~  
- Avoid commands—use soft tones like "Maybe try...", "It could be nice to...", or "If you have time, consider..."

4. [RECOMMENDATION]  
Offer 3 small emotional comforts for the user, based on how they felt this week.  
- Include elements like food, self-care, and sensory/nature-related experiences, but don't explicitly label them.  
- Just write them in a gentle, story-like manner that feels like warm advice from a caring friend.  
- Use a numbered list like:  
  1. ~  
  2. ~  
  3. ~  
- Avoid formal or poetic expressions—keep it warm, simple, and grounded in everyday life.




각 항목은 반드시 아래 형식으로 작성해 주세요:
[WEEK_FEEDBACK]
...
[WEEK_SUMMARY]
...
[SUGGESTIONS]
...
[RECOMMENDATION]
...
    """

    messages = [{"role": "system", "content": prompt_for_gpt}]
    try:
        logger.info("주간 분석 GPT API 호출 시작")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.75,
            max_tokens=1500
        )
        logger.info("주간 분석 GPT API 호출 완료")
        output = response.choices[0].message.content
        logger.debug(f"GPT 주간 분석 응답 전문: {output}")

        def extract_section(text, marker):
            import re
            match = re.search(rf"\[{marker}\](.*?)(?=\[\w+_?\w*\]|$)", text, re.DOTALL)
            return match.group(1).strip() if match else ""

        week_feedback = extract_section(output, "WEEK_FEEDBACK")
        week_summary = extract_section(output, "WEEK_SUMMARY")
        suggestions = extract_section(output, "SUGGESTIONS")
        recommendation = extract_section(output, "RECOMMENDATION")

        logger.info("주간 분석 섹션 추출 완료")
        return week_feedback, week_summary, suggestions, recommendation

    except Exception as e:
        logger.error(f"주간 분석 생성 실패: {e}")
        print(f" 주간 분석 생성 실패: {e}")
        return "오류 발생", "", "", ""




def create_daily_diary_image(illustration_summary):
    """
    사용자의 하루 중 가장 중요한 순간을 반영하여, 배경과 상황을 묘사하는 DALL·E 이미지 생성
    그림 생성에 사용될 프롬프트는 'ILLUSTRATION_SUMMARY'을 바탕으로 작성됨.
    
    반환값:
    - image_url: 생성된 이미지의 URL (단일 문자열)
    """
    logger.info("일기 이미지 생성 시작")
    
    prompt_for_dalle = f"""
    Generate a single atmospheric, semi-realistic illustration based on the following description.
    Focus on capturing the environment, objects, and ambiance that reflect the scene, based on the ILLUSTRATION_SUMMARY.

    ### **Key Elements to Emphasize:**
    1. **Focus on One Key Moment**
        - Depict only the single, most visually significant event described.
    2. **Time of Day & Lighting**
        - Adapt lighting to match the specific time of day (e.g., warm morning sunlight, golden hour, cool evening glow).
    3. **Weather & Surroundings**
        - Incorporate relevant weather elements (e.g., clear blue sky, misty park, rainy reflections).
    4. **Mood & Emotion**
        - Use lighting, colors, and composition to express the atmosphere of the moment.
    5. **People and Text Restrictions**
        - Do not include any human figures or text. However, if a human figure is necessary, it must be depicted only from the back view.
        - Proper nouns (e.g., YouTube) are allowed to appear as text if relevant.

    ### **Description for Illustration:**
    {illustration_summary}

    ### **Instruction:**
    Illustrate the moment described above in a visually compelling way.
    """
    
    logger.debug(f"DALL-E 프롬프트: {prompt_for_dalle}")
    image_url = None
    
    try:
        logger.info("DALL-E API 호출 시작")
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt_for_dalle,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url
        logger.info("이미지 생성 성공")
        logger.debug(f"생성된 이미지 URL: {image_url}")
    except Exception as e:
        logger.error(f"DALL-E 이미지 생성 실패: {e}")
        print(f"DALL·E 이미지 생성 실패: {e}")
    
    logger.info("이미지 생성 완료")
    return image_url

# 오늘 날짜를 반환하는 함수
def get_today_date():
    """
    오늘 날짜를 "date": "YYYY-MM-DD" 형식으로 반환하는 함수
    
    반환값:
    - date_dict: {"date": "YYYY-MM-DD"} 형식의 딕셔너리
    """
    logger.info("오늘 날짜 요청")
    today = datetime.now()
    formatted_date = today.strftime("%Y-%m-%d")
    date_dict = {"date": formatted_date}
    logger.info(f"오늘 날짜: {formatted_date}")
    return date_dict

# -------------------------------------- Flask Routes -------------------------------------- #

@app.route('/api/v1/day-diary', methods=['POST'])
def day_diary():
    logger.info("일일 일기 API 요청 수신")
    try:
        conversation = request.json.get("conversation", [])
        logger.info(f"대화 내역 수신: {len(conversation)}개 메시지")
        
        mood, diary, illustration = summarize_conversation(conversation)
        logger.info(f"대화 요약 완료 - 감정: {mood}")
        
        image_url = create_daily_diary_image(illustration)
        logger.info("일기 이미지 생성 완료")
        
        response_data = {
            "mood": mood,
            "diary_summary": diary,
            "image_url": image_url
        }
        logger.info("일일 일기 API 응답 전송")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"일일 일기 API 처리 중 오류: {str(e)}")
        return jsonify({"error": f"처리 중 오류 발생: {str(e)}"}), 500


@app.route('/api/v1/week-status', methods=['POST'])
def week_status():
    logger.info("주간 분석 API 요청 수신")
    try:
        weekly_data = request.json.get("weekly_data", [])
        logger.info(f"주간 데이터 수신: {len(weekly_data)}일치")
        
        feedback, summary, suggestions, recs = analyze_weekly_sentiment_separated(weekly_data)
        logger.info("주간 분석 완료")
        
        response_data = {
            "feedback": feedback,
            "week_summary": summary,
            "suggestion": suggestions,
            "recommendation": recs
        }
        logger.info("주간 분석 API 응답 전송")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"주간 분석 API 처리 중 오류: {str(e)}")
        return jsonify({"error": f"처리 중 오류 발생: {str(e)}"}), 500

@app.route('/api/v1/today', methods=['GET'])
def today():
    """
    오늘 날짜를 반환하는 API 엔드포인트
    """
    logger.info("오늘 날짜 API 요청 수신")
    try:
        date_dict = get_today_date()
        logger.info("오늘 날짜 API 응답 전송")
        return jsonify(date_dict)
    except Exception as e:
        logger.error(f"오늘 날짜 API 처리 중 오류: {str(e)}")
        return jsonify({"error": f"처리 중 오류 발생: {str(e)}"}), 500

# -------------------------------------- Flask Routes -------------------------------------- #

if __name__ == '__main__':
    logger.info("하루니 서버 시작")
    app.run(host='0.0.0.0', port=5000)