import json
import os
import re
import openai
import logging

import backoff
import torch
#import google.generativeai as genai
#from google.generativeai.types import GenerationConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
import requests
import subprocess
#from agent.Model_deepseek_r1 import Model_deepseek_r1

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haruni.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LLM")

MAX_NUM_TOKENS = 4096

class ModelProvider:
    """
    싱글톤 패턴을 사용하여 LLM 모델 인스턴스를 관리하는 클래스
    여러 에이전트가 동일한 모델 인스턴스를 공유할 수 있도록 함
    """
    _instances = {}  # 모델 ID를 키로 사용하는 인스턴스 딕셔너리
    
    @classmethod
    def get_model(cls, model_id):
        """
        모델 ID에 해당하는 모델 인스턴스를 반환하거나 생성
        
        Args:
            model_id (str): 모델 ID
            
        Returns:
            tuple: (client, model_id, tokenizer) 튜플
        """
        if model_id not in cls._instances:
            # 모델이 아직 로드되지 않은 경우 새로 로드
            logger.info(f"모델 로드: {model_id}")
            print(f"Loading model: {model_id}")
            cls._instances[model_id] = cls._create_model(model_id)
        
        return cls._instances[model_id]
    
    @staticmethod
    def _create_model(model_id):
        try:
            if model_id.startswith("ollama-gemma3:4b-it-qat"):
                # import subprocess
                # import atexit
                # # 서브프로세스 실행 (예: ollama 모델)
                # os.environ["OLLAMA_HOST"] = "127.0.0.1:11435"
                # os.environ["OLLAMA_API_BASE"] = "http://127.0.0.1:11435"

                # command = "ollama pull hf.co/google/gemma-3-4b-it-qat-q4_0-gguf:Q4_0 && ollama serve"
                # process = subprocess.Popen(command, shell=True)

                # # 메인 프로세스 종료 시 서브프로세스를 종료하도록 등록
                # atexit.register(lambda: process.terminate())
                logger.info("Ollama 모델 초기화")
                return None, model_id, None
            elif model_id.startswith("google/gemma-3-4b-it-qat-q4_0-gguf"):
                logger.info("GGUF 모델 로드 시작")
                from llama_cpp import Llama

                llm = Llama.from_pretrained(
                    repo_id="google/gemma-3-4b-it-qat-q4_0-gguf",
                    filename="gemma-3-4b-it-q4_0.gguf",
                    verbose=True, 
                    n_ctx=MAX_NUM_TOKENS,
                    n_gpu_layers=-1
                )
                logger.info("GGUF 모델 로드 완료")
                return llm, model_id, None
                        
            elif model_id.startswith("google/gemma-3-4b-it"):
                logger.info("Gemma-3-4b 모델 로드 시작")
                from transformers import AutoProcessor, Gemma3ForConditionalGeneration
                model = Gemma3ForConditionalGeneration.from_pretrained(
                    model_id, device_map="auto"
                ).eval()

                processor = AutoProcessor.from_pretrained(model_id)
                logger.info("Gemma-3-4b 모델 로드 완료")
                return model, model_id, processor
            elif model_id.startswith("google/gemma-3-1b-it"):
                logger.info("Gemma-3-1b 모델 로드 시작")
                from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM

                quantization_config = BitsAndBytesConfig(load_in_8bit=True)

                model = Gemma3ForCausalLM.from_pretrained(
                    model_id, quantization_config=quantization_config, device_map="cuda"
                ).eval()

                tokenizer = AutoTokenizer.from_pretrained(model_id)
                logger.info("Gemma-3-1b 모델 로드 완료")
                return model, model_id, tokenizer
            else:
                logger.error(f"지원되지 않는 모델: {model_id}")
                raise ValueError(f"Model {model_id} not supported.")
        except Exception as e:
            logger.error(f"모델 로드 실패: {model_id} - {str(e)}", exc_info=True)
            raise

class llm():
    def __init__(self, model_id):
        logger.info(f"LLM 인스턴스 초기화: {model_id}")
        self.system_message = None
        self.msg_history = []
        
        # ModelProvider를 통해 모델 인스턴스 가져오기
        self.client, self.model_id, self.tokenizer = ModelProvider.get_model(model_id)

    def get_model_id(self):
        return self.model_id

    #@backoff.on_exception(backoff.expo)
    def get_response_from_llm(
            self, system_message, msg, msg_history=None
    ):
        if msg_history is None:
            msg_history = []

        if self.model_id in ["ollama-gemma3:4b-it-qat"]:
            msg_history.append({
                "role": "user",
                "content": msg
            })

            prompt = [
                    {"role": "system", "content": system_message},
                    *msg_history,
                ]
            
            payload = {
                "model": "gemma3:4b-it-qat",
                "messages": prompt,

            }

            try:
                response = requests.post("http://localhost:11434/api/chat", json=payload, stream=False)
                content = ""
                if response.status_code == 200:
                    for line in response.text.strip().splitlines():
                        data = json.loads(line)
                        message_data = data.get("message", {})
                        content += message_data.get("content", "")
                else:
                    logger.error(f"Ollama API 요청 실패. 상태 코드: {response.status_code}")
                    print("API 요청 실패. 상태 코드:", response.status_code)

                msg_history.append({"role": "assistant", "content": content})
                return content, msg_history
            except Exception as e:
                logger.error(f"Ollama 응답 생성 중 오류: {str(e)}", exc_info=True)
                raise

        if self.model_id.startswith("google/gemma-3-4b-it-qat-q4_0-gguf"):
            try:
                msg_history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg}
                    ]
                })
                prompt = [
                        {"role": "system", "content": [{"type": "text", "text": system_message}]},
                        *msg_history,
                    ]
                
                # 채팅 완성 생성
                response = self.client.create_chat_completion(
                    messages=prompt,
                    max_tokens=10000,
                    temperature=0.7,
                    stop=[]  # 필요시 중지 토큰 추가
                )
                
                # 응답 추출
                decoded = response["choices"][0]["message"]["content"]
                
                # 히스토리에 응답 추가
                assistant_message = {"role": "assistant", "content": [{"type": "text", "text": decoded}]}
                msg_history.append(assistant_message)
                
                return decoded, msg_history
            except Exception as e:
                logger.error(f"GGUF 모델 응답 생성 중 오류: {str(e)}", exc_info=True)
                raise
        
        elif self.model_id in ["google/gemma-3-4b-it"]:
            try:
                msg_history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg}
                    ]
                })
                prompt = [
                        {"role": "system", "content": [{"type": "text", "text": system_message}]},
                        *msg_history,
                    ]

                inputs = self.tokenizer.apply_chat_template(
                    prompt, add_generation_prompt=True, tokenize=True,
                    return_dict=True, return_tensors="pt"
                ).to(self.client.device, dtype=torch.bfloat16)

                input_len = inputs["input_ids"].shape[-1]

                with torch.inference_mode():
                    generation = self.client.generate(**inputs, max_new_tokens=1000, do_sample=True)
                    generation = generation[0][input_len:]

                decoded = self.tokenizer.decode(generation, skip_special_tokens=True)

                msg_history.append([{"role": "assistant", "content": {"type": "text", "text": decoded}}])
                return decoded, msg_history
            except Exception as e:
                logger.error(f"Gemma-3-4b 모델 응답 생성 중 오류: {str(e)}", exc_info=True)
                raise

        elif self.model_id in ["google/gemma-3-1b-it"]:
            try:
                msg_history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg}
                    ]
                })
                prompt = [
                        {"role": "system", "content": [{"type": "text", "text": system_message}]},
                        *msg_history,
                    ]

                inputs = self.tokenizer.apply_chat_template(
                    prompt,
                    add_generation_prompt=True,
                    tokenize=True,
                    return_dict=True,
                    return_tensors="pt",
                ).to(self.client.device).to(torch.bfloat16)

                input_len = inputs["input_ids"].shape[-1]

                with torch.inference_mode():
                    generation = self.client.generate(**inputs, max_new_tokens=1000, do_sample=True)
                    generation = generation[0][input_len:]

                decoded = self.tokenizer.decode(generation, skip_special_tokens=True)

                msg_history.append([{"role": "assistant", "content": {"type": "text", "text": decoded}}])
                return decoded, msg_history 
            except Exception as e:
                logger.error(f"Gemma-3-1b 모델 응답 생성 중 오류: {str(e)}", exc_info=True)
                raise
        else:
            logger.error(f"지원되지 않는 모델: {self.model_id}")
            raise ValueError(f"Model {self.model_id} not supported.")


def extract_json_between_markers(llm_output):
    # Regular expression pattern to find JSON content between ```json and ```
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)
    for json_string in matches:
        json_string = json_string.strip()
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            # Attempt to fix common JSON issues
            try:
                # Remove invalid control characters
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                return parsed_json
            except json.JSONDecodeError:
                continue  # Try next match
    logger.warning("유효한 JSON을 찾지 못함")
    return None  # No valid JSON found

if __name__ == "__main__":
    logger.info("LLM 모듈 테스트 시작")
    llm = llm("ollama-gemma3:4b")
    result, _= llm.get_response_from_llm("너는 하루니야!","안녕?")
    print(result)
    logger.info("LLM 모듈 테스트 완료")
