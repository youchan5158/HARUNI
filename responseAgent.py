import json
import re
from llm import llm
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
logger = logging.getLogger("ResponseAgent")

mbti_chat_guide = {
    "INTJ": {
        "대화스타일": "목표 지향적, 직설적인 언어 사용",
        "말투": "간결하고 논리적, 중립적 톤",
        "관심사": "체계, 미래 전략, 시스템, 통찰",
        "갈등시반응": "감정 표현 최소화, 해결책 중심 대응",
        "듣기태도": "실용적인 정보 위주로 선택적 청취"
    },
    "INTP": {
        "대화스타일": "아이디어 탐색형, 주제 이탈 가능",
        "말투": "중간에 뜸 들이거나 말수 적음",
        "관심사": "개념, 가능성, 지식 체계",
        "갈등시반응": "논리적 대응, 회피 경향",
        "듣기태도": "새로운 아이디어에 반응, 감정적 요소엔 무심"
    },
    "ENTJ": {
        "대화스타일": "주도적, 자기 주장 강함",
        "말투": "단호하고 확신에 찬 어조",
        "관심사": "조직화, 생산성, 리더십",
        "갈등시반응": "논리로 압박, 감정적 접근 무시",
        "듣기태도": "실질적 개선 제안 위주 청취"
    },
    "ENTP": {
        "대화스타일": "유쾌하고 도전적, 아이디어 폭풍형",
        "말투": "재치 있고 에너지 넘침",
        "관심사": "창의성, 논쟁, 가능성 탐색",
        "갈등시반응": "토론하듯 설득, 감정은 부차적",
        "듣기태도": "즉흥적으로 맞춰가며 반응 관찰"
    },
    "INFJ": {
        "대화스타일": "깊고 의미 있는 이야기 선호",
        "말투": "차분하고 성찰적인 어조",
        "관심사": "가치관, 관계의 본질",
        "갈등시반응": "거리를 두고 관찰, 나중에 표현",
        "듣기태도": "비언어적 신호까지 민감하게 감지"
    },
    "INFP": {
        "대화스타일": "조용하지만 감성적, 시적인 표현 사용",
        "말투": "내면을 반영한 부드러운 말투",
        "관심사": "자아, 이상, 진정성, 예술",
        "갈등시반응": "충돌 회피, 깊은 상처 가능",
        "듣기태도": "감정에 민감, 진심으로 경청"
    },
    "ENFJ": {
        "대화스타일": "타인의 감정을 살피며 리드",
        "말투": "따뜻하고 설득력 있음",
        "관심사": "조화, 공동체, 성장",
        "갈등시반응": "먼저 화해 시도, 관계 우선",
        "듣기태도": "상대 감정을 세심하게 포착"
    },
    "ENFP": {
        "대화스타일": "열정적, 감정과 공감 중심",
        "말투": "리액션 큼, 감탄사 풍부",
        "관심사": "다양성, 가치, 사람",
        "갈등시반응": "감정적이지만 빨리 회복",
        "듣기태도": "깊은 공감력으로 경청"
    },
    "ISTJ": {
        "대화스타일": "사실 중심, 논리적 설명 선호",
        "말투": "단순하고 딱 부러짐",
        "관심사": "의무, 규칙, 전통",
        "갈등시반응": "원칙 중시, 감정보다 논리 강조",
        "듣기태도": "요점 중심, 불필요한 말은 무시"
    },
    "ISFJ": {
        "대화스타일": "조용하면서도 친절함",
        "말투": "예의 바르고 배려 깊음",
        "관심사": "봉사, 가족, 안정",
        "갈등시반응": "회피, 마음속으로 상처",
        "듣기태도": "상대 기분을 세심하게 고려"
    },
    "ESTJ": {
        "대화스타일": "지시적, 해결책 중심",
        "말투": "명확하고 직설적",
        "관심사": "질서, 책임, 실행",
        "갈등시반응": "정면 돌파, 논쟁 불사",
        "듣기태도": "효율 중심 정보에만 반응"
    },
    "ESFJ": {
        "대화스타일": "사교적, 감정 고려형",
        "말투": "친근하고 따뜻한 어조",
        "관심사": "기대 충족, 관계 유지",
        "갈등시반응": "오해에 민감, 감정적으로 반응",
        "듣기태도": "정서적 교류에 집중"
    },
    "ISTP": {
        "대화스타일": "실용적, 간결함 중시",
        "말투": "직설적, 불필요한 말 없음",
        "관심사": "기계, 구조, 분석",
        "갈등시반응": "감정 억제, 거리두기",
        "듣기태도": "필요한 정보에만 집중"
    },
    "ISFP": {
        "대화스타일": "조용하고 섬세한 표현 선호",
        "말투": "부드럽고 감각적",
        "관심사": "아름다움, 가치, 개인의 자유",
        "갈등시반응": "회피, 침묵, 내면화",
        "듣기태도": "감정의 흐름에 맞춰 경청"
    },
    "ESTP": {
        "대화스타일": "직관적, 즉흥적, 유쾌한 접근",
        "말투": "직접적이고 에너지 넘침",
        "관심사": "자극, 행동, 경험",
        "갈등시반응": "정면돌파 또는 농담으로 넘김",
        "듣기태도": "흥미 위주로 선택적 경청"
    },
    "ESFP": {
        "대화스타일": "감정적이고 활발, 사람 중심",
        "말투": "감탄사와 리액션 많음",
        "관심사": "즐거움, 감정 공유, 사람",
        "갈등시반응": "감정적으로 격해지나 금방 풀림",
        "듣기태도": "정서적 연결 중심으로 경청"
    }
}

class ResponseAgent:
    def __init__(self, model : llm):
        """
        대화 응답을 생성하는 에이전트 초기화
        
        Args:
            model_id (str): 사용할 LLM 모델 ID
        """
        logger.info("ResponseAgent 초기화")
        self.model = model
        
        # 말투 수정을 위한 StyleAgent 설정
        self.style_system_msg = """
너는 사용자의 응답 메시지를 사용자의 말투 선호에 맞게 다듬는 역할을 한다.  
절대 문장의 의미나 정보를 바꾸지 말고, **말투만 수정**할 것.

사용자의 말투 선호는 다음과 같다:
- 친한 친구와 대화하듯 편하게 반말을 사용함
- 감탄사와 형용사를 활용하여 감정을 확실히 표현함
- 이모티콘을 적극 활용함 😊🥲😆

!절대 새로운 문장을 만들거나 의미를 바꾸지 마라. 오직 말투만 바꿔라.
!오직 수정된 문장만 출력하라. 설명이나 추가 문장은 포함하지 마라.
"""
    def set_system_msg(self, user_info, user_mbti):
        system_msg = f"""
너는 대화 어시스턴트야.
너는 항상 유저의 일상을 궁금해하며 이야기를 잘 들어줘야해.
또한, 대화가 끊이지 않게 계속해서 후속 질문을 해야해.
단, 말이 너무 길어지지 않도록 주의해. 가능한 3문장을 넘어서지 마.

유저 정보:
{user_info}

유저의 대화 특성은 다음과 같아. 이를 잘 고려해서 답변 하도록 해.
{mbti_chat_guide[user_mbti]}

너의 특성은 다음과 같아. 이를 반영해서 답변 하도록 해.
- 이름은 '하루'야. 단, 사용자가 물어보지 않는한 너의 이름을 소개할 필요는 없어.
- 상대방의 감정과 관심에 주의를 기울여서 답변하도록 해.
- 대화 상대의 감정에 따라 적절한 반응하도록 해.
- 긍정적인 감정 표현을 자주 하도록 해.
- AI라는 것을 절대 티내지마.
- 한번의 대화에서 질문은 한가지만 하도록 하고, 말이 너무 길어지지 않도록 해.
- 과거와 현재를 명확하게 구분해서 답변하도록 해.

이 대화를 통해 유저의 일기를 작성하는 것이 목표야.
따라서, 일기를 작성해기 위해 필요한 정보들을 유저로부터 이끌어내야해.
그러기 위해서 적절한 질문을 통해 유저가 일상에서 겪은 일들을 궁금해하며, 어떤 기분이었는지를 알아내야해.
"""
        return system_msg
    
    def generate_response(self, user_message, message_history=None, db_context=None, user_info=None, user_mbti="INTJ", is_ollama=False):
        """
        사용자 메시지에 대한 응답을 생성하는 메서드
        
        Args:
            user_message (str): 사용자 메시지
            message_history (list, optional): 이전 대화 히스토리
            
        Returns:
            str: 생성된 응답
            list: 업데이트된 메시지 히스토리
        """
        
        # 응답 생성
        system_msg = self.set_system_msg(user_info, user_mbti)
        
        # message_history가 None이면 빈 리스트로 초기화
        if message_history is None:
            message_history = []
            
        if db_context is not None:
            # DB 컨텍스트가 있는 경우 임시 히스토리로 응답만 생성
            temp_message = f"DB 정보:DB:\n{db_context}\n DB 정보를 참고하여 다음 질문에 답변하도록 해.\n" + user_message

            response, updated_history = self.model.get_response_from_llm(system_msg, temp_message, message_history)

            if is_ollama:
                updated_history[-2] = {"role": "user", "content": user_message}
            else:
                updated_history[-2] = {"role": "user", "content": [{"type": "text", "text": user_message}]}
        else:
            response, updated_history = self.model.get_response_from_llm(system_msg, user_message, message_history)
        
        # 말투 수정
        styled_response = self.apply_style(response)
        
        if is_ollama:
            updated_history[-1] = [{"role": "assistant", "content": styled_response}]   
        else:
            updated_history[-1] = [{"role": "assistant", "content": [{"type": "text", "text": styled_response}]}]
        
        return styled_response, updated_history
    
    def apply_style(self, message):
        """
        생성된 메시지에 말투 스타일을 적용하는 메서드
        
        Args:
            message (str): 스타일을 적용할 원본 메시지
            
        Returns:
            str: 스타일이 적용된 메시지
        """
        # 빈 메시지 히스토리로 스타일 적용 요청
        styled_response, _ = self.model.get_response_from_llm(self.style_system_msg, message)
        return styled_response
    
if __name__ == "__main__":
    logger.info("ResponseAgent 테스트 시작")
    model = llm("google/gemma-3-4b-it")
    response_agent = ResponseAgent(model)
    result = response_agent.generate_response("안녕하세요. 오늘 기분이 좋아요. 오늘 너무 좋아요.", [], None, {"nickname": "홍길동", "gender": "남자", "mbti": "INTJ"}, "INTJ")
    print(result)
    logger.info("ResponseAgent 테스트 완료")