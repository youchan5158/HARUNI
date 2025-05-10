import json
import re
import logging
from llm import llm, ModelProvider

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryAgent")

# 현재 미사용

class MemoryAgent:
    def __init__(self, model : llm):
        """
        대화 문맥을 유지하고 정리하는 에이전트 초기화
        
        Args:
            model_id (str): 사용할 LLM 모델 ID
        """
        logger.info("MemoryAgent 초기화")
        self.model = model
        self.system_msg = """
너는 대화 문맥을 유지하고 정리하는 어시스턴트야. 
주어진 대화 히스토리에서 주제가 바뀐 부분을 감지하여 이전 문맥 중 불필요한 부분은 제거하고, 현재 대화와 관련된 문맥만 남겨. 
핵심은 현재 사용자의 질문에 필요한 문맥만 남기는 거야.

너의 출력은 필터링된 메시지 히스토리이며, 형식은 원래와 동일하게 유지해야 한다. 절대로 구조나 포맷을 변경하지 마라.
"""
        
    def filter_context(self, message_history, current_message):
        """
        대화 히스토리에서 현재 메시지와 관련된 문맥만 필터링하는 메서드
        
        Args:
            message_history (list): 대화 히스토리 (메시지 객체 목록)
            current_message (str): 현재 사용자 메시지
            
        Returns:
            list: 필터링된 대화 히스토리
        """
        if not message_history or len(message_history) <= 2:
            return message_history
        
        # 메시지 히스토리와 현재 메시지를 문자열로 변환
        history_str = json.dumps(message_history, ensure_ascii=False)
        
        # LLM에 전달할 입력 생성
        input_text = f"{history_str}\n\n현재 메시지: {current_message}"
        
        try:
            # LLM을 통해 필터링된 문맥 얻기
            response, _ = self.model.get_response_from_llm(self.system_msg, input_text)
            
            # 결과 파싱 시도
            # 응답이 이미 JSON 형식의 문자열일 경우 직접 파싱
            filtered_history = json.loads(response)
            
            # 기본 유효성 검사
            if isinstance(filtered_history, list) and all(isinstance(item, dict) for item in filtered_history):
                return filtered_history
            else:
                return message_history  # 유효하지 않은 형식이면 원본 반환
                
        except json.JSONDecodeError:
            # 응답에서 JSON 추출 시도
            try:
                # 정규식으로 JSON 배열 패턴을 찾음
                match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    filtered_history = json.loads(json_str)
                    return filtered_history
                else:
                    logger.warning("JSON 패턴을 찾지 못함 - 원본 히스토리 반환")
                    return message_history  # JSON 패턴을 찾지 못하면 원본 반환
            except Exception as e:
                logger.error(f"컨텍스트 필터링 중 오류 발생: {str(e)}", exc_info=True)
                return message_history  # 예외 발생 시 원본 반환
        except Exception as e:
            logger.error(f"컨텍스트 필터링 중 오류 발생: {str(e)}", exc_info=True)
            return message_history  # 예외 발생 시 원본 반환
