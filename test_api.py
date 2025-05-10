import requests
import json
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TestAPI")

def test_chat_api():
    """
    Flask API 서버의 chat 엔드포인트를 테스트하는 함수
    """
    logger.info("API 테스트 시작")
    # 서버 URL
    url = "http://127.0.0.1:5000/api/v1/question"
    #url = "https://e7e9-117-16-196-163.ngrok-free.app/api/v1/question"
    # 테스트 데이터
    data = {
        "userId": "1",
        "content": "나 지난주에 뭐했더라??",
        "sendingTime": "123456",
        "gender": "MALE",
        "sendingDate": "2025-05-09",
        "mbti": "INTJ",
        "nickname": "횃불이"
    }
    
    print(f"요청 URL: {url}")
    print(f"요청 데이터: {json.dumps(data, ensure_ascii=False)}")
    
    try:
        # API 요청
        response = requests.post(url, json=data)
        
        # 응답 출력
        print(f"응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print("\n응답 데이터:")
            print(json.dumps(response_data, ensure_ascii=False, indent=2))
        else:
            logger.error(f"에러 응답: {response.text}")
            print(f"에러 응답: {response.text}")
            
    except Exception as e:
        logger.error(f"요청 중 오류 발생: {str(e)}", exc_info=True)
        print(f"요청 중 오류 발생: {str(e)}")
    
    logger.info("API 테스트 완료")
        
if __name__ == "__main__":
    logger.info("테스트 스크립트 시작")
    test_chat_api()
    logger.info("테스트 스크립트 종료") 