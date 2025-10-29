"""
뉴스 데이터베이스 모듈 (MongoDB 버전)
MongoDB를 사용한 뉴스 저장 및 관리 기능
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import json

class NewsDatabase:
    """뉴스 데이터베이스 관리 클래스 (MongoDB)"""
    
    def __init__(self, connection_string: str = None, db_name: str = "crypto_news"):
        """
        MongoDB 데이터베이스 연결 초기화
        
        Args:
            connection_string: MongoDB 연결 문자열
            db_name: 데이터베이스 이름
        """
        if connection_string is None:
            # 환경 변수에서 MongoDB 연결 문자열 가져오기 (로컬 시도 없음)
            connection_string = os.getenv('MONGODB_URI')
            
            if not connection_string:
                raise ValueError("MONGODB_URI 환경 변수가 설정되지 않았습니다. MongoDB Atlas 연결 문자열이 필요합니다.")
        
        self.connection_string = connection_string
        self.db_name = db_name
        self.client = None
        self.db = None
        self.news_collection = None
        
        self.connect_database()
    
    def connect_database(self):
        """데이터베이스 연결 및 초기화"""
        try:
            # 타임아웃 설정으로 MongoDB 클라이언트 생성
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 서버 선택 타임아웃 5초
                socketTimeoutMS=10000,         # 소켓 타임아웃 10초
                connectTimeoutMS=5000,         # 연결 타임아웃 5초
                maxPoolSize=10,               # 최대 커넥션 풀 크기
                retryWrites=True,             # 쓰기 재시도
                w="majority"                  # 쓰기 확인 레벨
            )
            
            # 연결 테스트 (짧은 타임아웃)
            self.client.admin.command('ping', maxTimeMS=2000)
            
            self.db = self.client[self.db_name]
            self.news_collection = self.db['news']
            
            # 인덱스 생성
            self._create_indexes()
            
            print("MongoDB 연결 성공")
            
        except ConnectionFailure as e:
            print(f"MongoDB 연결 실패: {e}")
            raise
        except Exception as e:
            print(f"데이터베이스 초기화 오류: {e}")
            raise
    
    def _create_indexes(self):
        """필요한 인덱스 생성"""
        try:
            # 고유 링크 인덱스
            self.news_collection.create_index("link", unique=True)
            
            # 발행일 인덱스
            self.news_collection.create_index("published")
            
            # 번역 상태 인덱스
            self.news_collection.create_index("translation_status")
            
            # 카테고리 인덱스
            self.news_collection.create_index("category")
            
            # 복합 인덱스 (발행일 + 번역 상태)
            self.news_collection.create_index([
                ("published", -1),
                ("translation_status", 1)
            ])
            
            # 복합 인덱스 (카테고리 + 발행일)
            self.news_collection.create_index([
                ("category", 1),
                ("published", -1)
            ])
            
        except Exception as e:
            print(f"인덱스 생성 오류: {e}")
    
    def is_news_exists(self, link: str) -> bool:
        """뉴스가 이미 존재하는지 확인"""
        try:
            # 타임아웃 설정으로 빠른 조회
            result = self.news_collection.find_one(
                {"link": link}, 
                projection={"_id": 1},
                max_time_ms=1000  # 1초 타임아웃
            )
            return result is not None
            
        except Exception as e:
            print(f"뉴스 존재 확인 오류: {e}")
            # 오류 발생 시 중복 방지를 위해 False 반환 (새 뉴스로 처리)
            return False
    
    def save_news(self, news_item: Dict) -> bool:
        """새로운 뉴스 저장"""
        try:
            # 중복 체크
            if self.is_news_exists(news_item['link']):
                return False
            
            # 현재 시간 추가
            news_item['created_at'] = datetime.now(timezone.utc)
            news_item['updated_at'] = datetime.now(timezone.utc)
            
            # 기본값 설정
            news_item.setdefault('source', 'CryptoPanic')
            news_item.setdefault('translation_status', 'pending')
            
            result = self.news_collection.insert_one(news_item)
            return result.acknowledged
            
        except DuplicateKeyError:
            # 중복 데이터는 무시
            return False
        except Exception as e:
            print(f"뉴스 저장 오류: {e}")
            return False
    
    def save_news_batch(self, news_items: List[Dict]) -> int:
        """여러 뉴스 일괄 저장"""
        saved_count = 0
        
        try:
            # 중복되지 않는 뉴스만 필터링
            new_items = []
            
            for news_item in news_items:
                if not self.is_news_exists(news_item['link']):
                    # 현재 시간 추가
                    news_item['created_at'] = datetime.now(timezone.utc)
                    news_item['updated_at'] = datetime.now(timezone.utc)
                    
                    # 기본값 설정
                    news_item.setdefault('source', 'CryptoPanic')
                    news_item.setdefault('translation_status', 'pending')
                    
                    new_items.append(news_item)
            
            if new_items:
                result = self.news_collection.insert_many(new_items, ordered=False)
                saved_count = len(result.inserted_ids)
            
        except Exception as e:
            print(f"뉴스 일괄 저장 오류: {e}")
        
        return saved_count
    
    def update_translation(self, link: str, translated_title: str = None, 
                          translated_description: str = None) -> bool:
        """뉴스 번역 정보 업데이트"""
        try:
            update_fields = {}
            
            if translated_title:
                update_fields['translated_title'] = translated_title
            
            if translated_description:
                update_fields['translated_description'] = translated_description
            
            if update_fields:
                update_fields['translation_status'] = 'completed'
                update_fields['updated_at'] = datetime.now(timezone.utc)
                
                result = self.news_collection.update_one(
                    {"link": link},
                    {"$set": update_fields}
                )
                
                return result.modified_count > 0
            
            return False
            
        except Exception as e:
            print(f"번역 정보 업데이트 오류: {e}")
            return False
    
    def get_untranslated_news(self, limit: int = 50) -> List[Dict]:
        """번역되지 않은 뉴스 조회"""
        try:
            # 번역이 필요한 뉴스 조회
            cursor = self.news_collection.find({
                "$or": [
                    {"translation_status": "pending"},
                    {"translated_title": None},
                    {"translated_title": ""}
                ]
            }).sort("published", -1).limit(limit)
            
            news_list = []
            for doc in cursor:
                # MongoDB의 _id 제거하고 일반 dict로 변환
                news_item = {
                    'id': str(doc['_id']),
                    'title': doc.get('title', ''),
                    'link': doc.get('link', ''),
                    'description': doc.get('description', ''),
                    'published': doc.get('published', ''),
                    'source': doc.get('source', 'CryptoPanic')
                }
                news_list.append(news_item)
            
            return news_list
            
        except Exception as e:
            print(f"번역되지 않은 뉴스 조회 오류: {e}")
            return []
    
    def get_latest_news(self, limit: int = 20) -> List[Dict]:
        """최신 뉴스 조회"""
        try:
            cursor = self.news_collection.find().sort("published", -1).limit(limit)
            
            news_list = []
            for doc in cursor:
                news_item = {
                    'id': str(doc['_id']),
                    'title': doc.get('title', ''),
                    'link': doc.get('link', ''),
                    'description': doc.get('description', ''),
                    'published': doc.get('published', ''),
                    'source': doc.get('source', 'CryptoPanic'),
                    'category': doc.get('category', 'crypto')  # 기본값 crypto
                }
                
                # 번역된 제목이 있으면 추가
                if doc.get('translated_title'):
                    news_item['translated_title'] = doc['translated_title']
                
                if doc.get('translated_description'):
                    news_item['translated_description'] = doc['translated_description']
                
                news_list.append(news_item)
            
            return news_list
            
        except Exception as e:
            print(f"최신 뉴스 조회 오류: {e}")
            return []

    def get_latest_news_by_category(self, category: str, limit: int = 5) -> List[Dict]:
        """카테고리별 최신 뉴스 조회"""
        try:
            cursor = self.news_collection.find(
                {"category": category}
            ).sort("published", -1).limit(limit)
            
            news_list = []
            for doc in cursor:
                news_item = {
                    'id': str(doc['_id']),
                    'title': doc.get('title', ''),
                    'link': doc.get('link', ''),
                    'description': doc.get('description', ''),
                    'published': doc.get('published', ''),
                    'source': doc.get('source', 'CryptoPanic'),
                    'category': doc.get('category', category)
                }
                
                # 번역된 제목이 있으면 추가
                if doc.get('translated_title'):
                    news_item['translated_title'] = doc['translated_title']
                
                if doc.get('translated_description'):
                    news_item['translated_description'] = doc['translated_description']
                
                news_list.append(news_item)
            
            return news_list
            
        except Exception as e:
            print(f"카테고리별 뉴스 조회 오류: {e}")
            return []

    def get_news_by_categories(self, crypto_limit: int = 5, general_limit: int = 5) -> Dict[str, List[Dict]]:
        """카테고리별 뉴스 조회 (크립토와 일반)"""
        try:
            crypto_news = self.get_latest_news_by_category('crypto', crypto_limit)
            general_news = self.get_latest_news_by_category('general', general_limit)
            
            return {
                'crypto': crypto_news,
                'general': general_news
            }
            
        except Exception as e:
            print(f"카테고리별 뉴스 조회 오류: {e}")
            return {'crypto': [], 'general': []}
    
    def get_news_count(self) -> Dict[str, int]:
        """뉴스 통계 정보 조회"""
        try:
            # 전체 뉴스 수
            total_count = self.news_collection.count_documents({})
            
            # 번역된 뉴스 수
            translated_count = self.news_collection.count_documents({
                "translated_title": {"$ne": None, "$ne": ""}
            })
            
            # 번역 대기 뉴스 수
            pending_count = self.news_collection.count_documents({
                "$or": [
                    {"translation_status": "pending"},
                    {"translated_title": None},
                    {"translated_title": ""}
                ]
            })
            
            return {
                'total': total_count,
                'translated': translated_count,
                'pending': pending_count
            }
            
        except Exception as e:
            print(f"뉴스 통계 조회 오류: {e}")
            return {'total': 0, 'translated': 0, 'pending': 0}
    
    def cleanup_old_news(self, days: int = 30) -> int:
        """오래된 뉴스 정리"""
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            result = self.news_collection.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            return result.deleted_count
            
        except Exception as e:
            print(f"오래된 뉴스 정리 오류: {e}")
            return 0
    
    def get_news_by_link(self, link: str) -> Optional[Dict]:
        """링크로 뉴스 조회"""
        try:
            doc = self.news_collection.find_one({"link": link})
            
            if doc:
                news_item = {
                    'id': str(doc['_id']),
                    'title': doc.get('title', ''),
                    'link': doc.get('link', ''),
                    'description': doc.get('description', ''),
                    'published': doc.get('published', ''),
                    'source': doc.get('source', 'CryptoPanic')
                }
                
                if doc.get('translated_title'):
                    news_item['translated_title'] = doc['translated_title']
                
                if doc.get('translated_description'):
                    news_item['translated_description'] = doc['translated_description']
                
                return news_item
            
            return None
            
        except Exception as e:
            print(f"링크로 뉴스 조회 오류: {e}")
            return None
    
    def close_connection(self):
        """데이터베이스 연결 종료"""
        try:
            if self.client:
                self.client.close()
                print("MongoDB 연결 종료")
        except Exception as e:
            print(f"연결 종료 오류: {e}")
