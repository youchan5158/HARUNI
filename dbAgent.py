import json
import torch
import mysql.connector
from mysql.connector import Error
from typing import Dict, List, Optional
from llm import llm, extract_json_between_markers
import re
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
logger = logging.getLogger("DBAgent")

SQL_KEYWORDS = (
    "SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH"
)
def extract_sql(text: str):
    """
    전달된 문자열에서 SQL 문장(세미콜론으로 끝나는)을 찾아 리스트로 반환.
    """
    pattern = rf"(?is)\b(?:{SQL_KEYWORDS})\b.*?;"
    matches = re.findall(pattern, text)
    return [m.strip() for m in matches]

class DBAgent:
    def __init__(self, connection_params: Dict, model : llm, user_id : str = None):
        """데이터베이스 에이전트 초기화"""
        logger.info("DBAgent 초기화")
        self.connection_params = connection_params
        self.connection = None
        self.cursor = None
        self.connect_to_database()
        self.model = model
        self.system_msg = "당신은 데이터베이스 전문가 AI 어시스턴트입니다. 사용자의 질문에 대한 정확한 SQL 쿼리를 생성하고, 결과를 분석하여 답변해주세요."
        self.schema = self.get_schema()
        self.user_id = user_id

    def connect_to_database(self):
        """데이터베이스에 연결"""
        try:
            self.connection = mysql.connector.connect(**self.connection_params)
            
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info("MySQL 데이터베이스 연결 성공")
                
        except Error as e:
            logger.error(f"데이터베이스 연결 오류: {e}")

    def get_schema(self) -> str:
        """information_schema를 활용한 데이터베이스 스키마 정보 가져오기"""
        try:
            # 테이블 목록 및 기본 정보 가져오기
            self.cursor.execute("""
                SELECT 
                    t.TABLE_NAME, 
                    t.TABLE_COMMENT,
                    t.TABLE_ROWS,
                    t.CREATE_TIME 
                FROM 
                    information_schema.TABLES t 
                WHERE 
                    t.TABLE_SCHEMA = %s
                ORDER BY 
                    t.TABLE_NAME
            """, (self.connection_params['database'],))
            
            tables = self.cursor.fetchall()
            schema_info = []
            
            for table in tables:
                table_name = table['TABLE_NAME']
                
                # 각 테이블의 컬럼 정보 가져오기
                self.cursor.execute("""
                    SELECT 
                        c.COLUMN_NAME,
                        c.COLUMN_TYPE,
                        c.IS_NULLABLE,
                        c.COLUMN_KEY,
                        c.COLUMN_DEFAULT,
                        c.EXTRA,
                        c.COLUMN_COMMENT
                    FROM 
                        information_schema.COLUMNS c
                    WHERE 
                        c.TABLE_SCHEMA = %s AND
                        c.TABLE_NAME = %s
                    ORDER BY 
                        c.ORDINAL_POSITION
                """, (self.connection_params['database'], table_name))
                
                columns = self.cursor.fetchall()
                
                # 외래 키 정보 가져오기 (있는 경우)
                self.cursor.execute("""
                    SELECT
                        k.COLUMN_NAME,
                        k.REFERENCED_TABLE_NAME,
                        k.REFERENCED_COLUMN_NAME
                    FROM
                        information_schema.KEY_COLUMN_USAGE k
                    WHERE
                        k.TABLE_SCHEMA = %s AND
                        k.TABLE_NAME = %s AND
                        k.REFERENCED_TABLE_NAME IS NOT NULL
                """, (self.connection_params['database'], table_name))
                
                foreign_keys = self.cursor.fetchall()
                
                # 테이블 정보 구성
                table_info = [f"Table: {table_name}"]
                if table['TABLE_COMMENT']:
                    table_info.append(f"Description: {table['TABLE_COMMENT']}")
                
                # 컬럼 정보 추가
                table_info.append("Columns:")
                for col in columns:
                    col_info = f"  - {col['COLUMN_NAME']} ({col['COLUMN_TYPE']})"
                    if col['COLUMN_KEY'] == 'PRI':
                        col_info += " [PRIMARY KEY]"
                    if col['IS_NULLABLE'] == 'NO':
                        col_info += " [NOT NULL]"
                    if col['COLUMN_DEFAULT'] is not None:
                        col_info += f" [DEFAULT: {col['COLUMN_DEFAULT']}]"
                    if col['COLUMN_COMMENT']:
                        col_info += f" - {col['COLUMN_COMMENT']}"
                    table_info.append(col_info)
                
                # 외래 키 정보 추가
                if foreign_keys:
                    table_info.append("Foreign Keys:")
                    for fk in foreign_keys:
                        table_info.append(f"  - {fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")
                
                schema_info.append("\n".join(table_info))
            
            return "\n\n".join(schema_info)

        except Error as e:
            logger.error(f"스키마 정보 가져오기 오류: {e}")
            return "스키마 정보를 가져올 수 없습니다."
        
    def get_user_id(self) -> str:
        """사용자 ID 가져오기"""
        return self.user_id
    
    def set_user_id(self, user_id : str):
        """사용자 ID 설정"""
        self.user_id = user_id
    
    def run_query(self, query: str) -> str:
        """SQL 쿼리 실행"""
        try:
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            return json.dumps(results, ensure_ascii=False, default=str)
        except Error as e:
            logger.error(f"쿼리 실행 오류: {e}")
            return f"쿼리 실행 오류: {e}"
    
    def check_db_relevance(self, question: str) -> Dict:
        """질문이 DB 참조가 필요한지 판단"""
        schema = self.get_schema()
        prompt = f"""
        사용자의 질문이 데이터베이스에서 정보를 찾아야 할 질문인지 판단하세요.
        
        데이터베이스 스키마:
        {schema}
        
        사용자 질문: {question}
        
        판단 과정:
        1. 질문이 데이터베이스에 저장된 정보를 필요로 하는지 분석하세요.
        2. 데이터베이스 스키마를 참고하여 필요한 정보가 있을 가능성을 평가하세요.
        
        다음 형식으로 응답하세요:
        {{
            "needs_db": true/false,
            "explanation": "판단 이유",
            "possible_tables": ["table1", "table2"]
        }}
        """
        
        response, _ = self.model.get_response_from_llm(self.system_msg, prompt)
        response_json = extract_json_between_markers(response)

        if response_json:
            return response_json
        else:
            logger.warning("DB 관련성 분석 결과 파싱 실패")
            return {
                "needs_db": False,
                "explanation": "응답 형식 오류로 판단 불가",
                "possible_tables": []
            }
    
    def generate_sql_query(self, question: str, sendingDate, sendingTime) -> str:
        """SQL 쿼리 생성"""
        schema = self.get_schema()
        prompt = f"""
        다음 데이터베이스 스키마와 사용자 질문을 바탕으로 적절한 MySQL의 쿼리를 생성하세요.
        
        데이터베이스 스키마:
        {schema}

        스키마 추가정보:
        1. 사용자 정보는 모두 users 테이블에 저장되어 있습니다.
        2. 일기 정보는 모두 diaries 테이블에 저장되어 있습니다.
        3. 채팅 정보는 모두 chats 테이블에 저장되어 있습니다.
        4. 날짜 정보는 모두 YYYY-MM-DD 형식으로 저장되어 있습니다.
        5. 시간 정보는 모두 HH:MM:SS 형식으로 저장되어 있습니다.
        6. 날짜와 시간을 조회하는 SQL 쿼리는 함수를 이용하지 말고, 직접 형식을 맞춰서 조회해야 합니다.

        user_id: 
        {self.user_id}

        sendingDate: {sendingDate}
        sendingTime: {sendingTime}

        
        사용자 질문: 
        {question}
        
        정확한 SQL 쿼리만 작성하세요. 주석이나 설명 없이 실행 가능한 쿼리만 반환하세요.
        """
        
        response, _ = self.model.get_response_from_llm(self.system_msg, prompt)
        response = extract_sql(response)
        
        if response and len(response) > 0:
            logger.info(f"SQL 쿼리 생성: {response[0]}")
            return response[0]
        else:
            logger.warning("유효한 SQL 쿼리를 생성하지 못함")
            return ""
    
    def analyze_results(self, question: str, query: str, results: str) -> str:
        """쿼리 결과 분석 및 응답 생성"""
        schema = self.get_schema()
        prompt = f"""
        데이터베이스에서 조회한 결과를 바탕으로 분석 결과를 JSON 형식으로 제공하세요.
        
        데이터베이스 스키마:
        {schema}
        
        사용자 질문: {question}
        
        실행된 SQL 쿼리: {query}
        
        쿼리 결과: {results}
        
        분석 과정:
        1. 쿼리 결과가 사용자 질문과 관련이 있는지 판단하세요.
        2. 결과가 충분한지, 아니면 추가 정보가 필요한지 평가하세요.
        3. 결과를 바탕으로 분석 결과를 JSON 형식으로 작성하세요.
        
        다음 형식으로 JSON을 작성하세요:
        {{
            "is_sufficient": true/false,
            "explanation": "결과가 충분한지 또는 추가 정보가 필요한지에 대한 설명",
            "query_results": results,
            "analysis": "쿼리 결과에 대한 간단한 분석"
        }}
        
        JSON 형식으로만 응답하세요. 추가 설명이나 텍스트 없이 유효한 JSON만 반환하세요.
        """
        
        response, _ = self.model.get_response_from_llm(self.system_msg, prompt)
        result_json = extract_json_between_markers(response)
        
        if not result_json:
            logger.warning("쿼리 결과 분석 실패 - JSON 파싱 오류")
            # JSON 파싱 실패 시 기본 JSON 응답
            result_json = {
                "is_sufficient": False,
                "explanation": "결과 분석 중 오류가 발생했습니다.",
                "query_results": results,
                "analysis": "분석 실패"
            }
            
        return json.dumps(result_json, ensure_ascii=False)
    
    def process_question(self, question: str, sendingDate, sendingTime) -> str:
        """사용자 질문 처리"""
        try:
            # 1. DB 참조 필요성 판단
            relevance_data = self.check_db_relevance(question)
            needs_db = relevance_data.get("needs_db", False)
            
            if not needs_db:
                return False, json.dumps({
                    "is_sufficient": True,
                    "explanation": f"이 질문은 데이터베이스 조회가 필요하지 않습니다. 이유: {relevance_data.get('explanation', '')}",
                    "query_results": [],
                    "analysis": "데이터베이스 조회 없이 처리된 질문입니다."
                }, ensure_ascii=False)
            
            # 2. SQL 쿼리 생성
            sql_query = self.generate_sql_query(question, sendingDate, sendingTime)

            # 3. 쿼리 실행
            query_results = self.run_query(sql_query)
            
            # 4. 응답 생성
            if len(query_results) > 0:
                final_response = self.analyze_results(question, sql_query, query_results)
            else:
                logger.warning("쿼리 결과 없음")
                return False, json.dumps({
                    "is_sufficient": False,
                    "explanation": "쿼리 결과가 없습니다.",
                    "query_results": [],
                    "analysis": "쿼리 결과가 없습니다."
                }, ensure_ascii=False)
            
            return True, final_response
            
        except Exception as e:
            logger.error(f"질문 처리 중 오류 발생: {str(e)}", exc_info=True)
            return False, json.dumps({
                "is_sufficient": False,
                "explanation": f"질문 처리 중 오류 발생: {str(e)}",
                "query_results": [],
                "analysis": "오류 발생"
            }, ensure_ascii=False)
    
    def close_connection(self):
        """데이터베이스 연결 종료"""
        if self.cursor:
            self.cursor.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL 연결 종료")


def main():
    """메인 함수"""
    logger.info("DBAgent 메인 함수 시작")
    # 데이터베이스 연결 정보

    import os

    db_config = {
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME")
    }
    
    db_agent = DBAgent(db_config, llm("ollama-gemma3:4b-it-qat"))
    
    db_agent.set_user_id("1")
    logger.info("사용자 정보 조회 완료")
    
    try:
        logger.info("대화 루프 시작")
        while True:
            user_question = input("질문을 입력하세요 (종료하려면 'exit' 입력): ")

            print("\n")
            
            if user_question.lower() == 'exit':
                logger.info("사용자가 종료 요청")
                break
            
            logger.info(f"사용자 질문: {user_question[:30]}...")
            _, response = db_agent.process_question(user_question)
            print("\n처리 결과:")
            
            # JSON 형식의 응답을 파싱하여 보기 좋게 출력
            try:
                result = json.loads(response)
                print(f"결과 충분성: {'충분함' if result.get('is_sufficient', False) else '불충분함'}")
                print(f"설명: {result.get('explanation', '')}")
                print(f"분석: {result.get('analysis', '')}")
                print("\n쿼리 결과:")
                query_results = result.get('query_results', [])
                if isinstance(query_results, str):
                    # 쿼리 결과가 문자열 형태로 저장된 경우
                    try:
                        query_results = json.loads(query_results)
                    except:
                        logger.warning("쿼리 결과 JSON 파싱 실패")
                        pass
                
                if query_results and isinstance(query_results, list):
                    for idx, item in enumerate(query_results):
                        print(f"{idx+1}. {json.dumps(item, ensure_ascii=False, indent=2)}")
                else:
                    print("쿼리 결과가 없거나 유효하지 않습니다.")
            except json.JSONDecodeError:
                logger.error("응답이 유효한 JSON 형식이 아님", exc_info=True)
                print("응답이 유효한 JSON 형식이 아닙니다:")
                print(response)
            
            print("\n" + "-"*50 + "\n")
            
    finally:
        logger.info("프로그램 종료")
        db_agent.close_connection()


if __name__ == "__main__":
    main()