import json
import logging
from agent.llm import llm, ModelProvider

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StyleAgent")

# 현재 responseAgent에서 간소화 버전 사용 중

class StyleAgent:
    def __init__(self, model_id="google/gemma-3-4b-it"):
        """
        메시지 스타일을 조정하는 에이전트 초기화
        
        Args:
            model_id (str): 사용할 LLM 모델 ID
        """
        logger.info(f"StyleAgent 초기화: {model_id}")
        self.model_id = model_id
        self.llm = llm(model_id)
        self.system_message = """
너는 사용자의 응답 메시지를 사용자의 말투 선호에 맞게 다듬는 역할을 한다.  
절대 문장의 의미나 정보를 바꾸지 말고, **말투만 수정**하라.

사용자의 말투 선호는 다음과 같다:
- 친한 친구와 대화하듯 편하게 반말을 사용함
- 감탄사와 형용사를 활용하여 감정을 확실히 표현함
- 이모티콘을 적극 활용함 😊🥲😆

!절대 새로운 문장을 만들거나 의미를 바꾸지 마라. 오직 말투만 바꿔라.
!오직 수정된 문장만 출력하라. 설명이나 추가 문장은 포함하지 마라.
"""
        try:
            self.llm.set_system_message(self.system_message)
        except Exception as e:
            logger.error(f"시스템 메시지 설정 중 오류: {str(e)}", exc_info=True)
        
    def apply_style(self, message):
        """
        메시지에 스타일을 적용하는 메서드
        
        Args:
            message (str): 스타일을 적용할 원본 메시지
            
        Returns:
            str: 스타일이 적용된 메시지
        """
        try:
            # 빈 메시지 히스토리로 스타일 적용 요청
            styled_message, _ = self.llm.get_response_from_llm(message, [])
            return styled_message
        except Exception as e:
            logger.error(f"스타일 적용 중 오류: {str(e)}", exc_info=True)
            return message  # 오류 발생 시 원본 메시지 반환
    
    def update_style_preferences(self, preferences):
        """
        스타일 선호도를 업데이트하는 메서드
        
        Args:
            preferences (dict): 스타일 선호도 설정
                {
                    'formality': 'casual'|'formal', 
                    'emotion_level': 'high'|'medium'|'low',
                    'emoji_usage': 'high'|'medium'|'none'
                }
        """
        logger.info(f"스타일 선호도 업데이트: {preferences}")
        # 기본 시스템 메시지 템플릿
        base_message = """
너는 사용자의 응답 메시지를 사용자의 말투 선호에 맞게 다듬는 역할을 한다.  
절대 문장의 의미나 정보를 바꾸지 말고, **말투만 수정**하라.

사용자의 말투 선호는 다음과 같다:
{preferences}

!절대 새로운 문장을 만들거나 의미를 바꾸지 마라. 오직 말투만 바꿔라.
!오직 수정된 문장만 출력하라. 설명이나 추가 문장은 포함하지 마라.
"""
        # 선호도에 따른 설명 구성
        pref_texts = []
        
        # 격식 수준 설정
        if preferences.get('formality') == 'formal':
            pref_texts.append("- 존댓말을 사용하며 격식있는 표현을 선호함")
        else:
            pref_texts.append("- 친한 친구와 대화하듯 편하게 반말을 사용함")
            
        # 감정 표현 수준 설정
        if preferences.get('emotion_level') == 'high':
            pref_texts.append("- 감탄사와 형용사를 적극 활용하여 감정을 확실히 표현함")
        elif preferences.get('emotion_level') == 'medium':
            pref_texts.append("- 적절한 수준의 감정 표현을 사용함")
        else:
            pref_texts.append("- 감정 표현을 최소화하고 간결하게 표현함")
            
        # 이모티콘 사용 수준 설정
        if preferences.get('emoji_usage') == 'high':
            pref_texts.append("- 이모티콘을 적극 활용함 😊🥲😆")
        elif preferences.get('emoji_usage') == 'medium':
            pref_texts.append("- 이모티콘을 가끔 적절히 사용함")
        else:
            pref_texts.append("- 이모티콘을 사용하지 않음")
        
        # 시스템 메시지 업데이트
        updated_message = base_message.format(preferences="\n".join(pref_texts))
        try:
            self.llm.set_system_message(updated_message)
            self.system_message = updated_message
        except Exception as e:
            logger.error(f"시스템 메시지 업데이트 중 오류: {str(e)}", exc_info=True)
