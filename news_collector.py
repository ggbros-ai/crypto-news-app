"""
뉴스 수집 모듈
FinancialModelingPrep API를 통한 암호화폐 뉴스 수집 기능
"""

import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
import pytz
import json
import re
import os
from dotenv import load_dotenv
from mongodb_database import NewsDatabase

# 환경 변수 로드
load_dotenv()


class NewsCollector:
    """FinancialModelingPrep API를 통한 암호화폐 뉴스 수집 클래스"""
    
    def __init__(self):
        # FinancialModelingPrep API 설정
        self.api_key = "11eafd88cfde4fb0b1a34e88c62e92bc"
        self.crypto_base_url = "https://financialmodelingprep.com/stable/news/crypto-latest"
        self.general_base_url = "https://financialmodelingprep.com/stable/news/general-latest"
        
        # AI 번역기 설정
        self.ai_base_url = "https://3f844cab6c8b.ngrok-free.app"
        self.ai_api_url = f"{self.ai_base_url}/v1"
        self.ai_model = "google/gemma-3-27b"
        self.ai_api_key = "1234"  # 테스트용 API 키
        
        # 데이터베이스 연결
        self.db = NewsDatabase()
        
        # 최신 뉴스 기준 시간 저장
        self.latest_news_time = None
        # 중복 체크를 위한 이미 전송된 뉴스 링크 저장
        self.sent_news_links = set()
    
    def fetch_crypto_news(self, page: int = 0, limit: int = 10) -> List[Dict]:
        """FinancialModelingPrep API에서 암호화폐 뉴스 수집"""
        try:
            params = {
                'page': page,
                'limit': limit,
                'apikey': self.api_key
            }
            
            print(f"FinancialModelingPrep API 요청: page={page}, limit={limit}")
            
            response = requests.get(self.crypto_base_url, params=params, timeout=10)
            print(f"API 응답 상태: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            print(f"API 응답 데이터 타입: {type(data)}, 길이: {len(data) if isinstance(data, list) else 'N/A'}")
            
            if not isinstance(data, list):
                print(f"예상치 못한 응답 형식: {type(data)}")
                return []
            
            news_items = []
            print(f"총 {len(data)}개의 뉴스 아이템 처리 시작...")
            
            for i, item in enumerate(data):
                try:
                    print(f"뉴스 아이템 {i+1}/{len(data)} 처리 중...")
                    
                    # API 응답에서 필요한 필드 추출
                    title = item.get('title', '')
                    published_date = item.get('publishedDate', '')
                    url = item.get('url', '')
                    
                    print(f"  - 제목: {title[:50]}...")
                    print(f"  - URL: {url}")
                    
                    # 필수 필드 확인
                    if not title.strip() or not url.strip():
                        print("  - 필수 필드 부족, 건너뜀")
                        continue
                    
                    # DB 중복 체크 - 이미 저장된 뉴스는 건너뛰기
                    print("  - DB 중복 체크...")
                    if self.db.is_news_exists(url):
                        print("  - 이미 존재하는 뉴스, 건너뜀")
                        continue
                    
                    # 시간을 한국시간으로 변환하여 저장
                    korea_time = self.parse_news_time(published_date)
                    if korea_time:
                        # 한국시간 문자열로 저장
                        published_korea = korea_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        published_korea = published_date
                    
                    news_item = {
                        'title': title,
                        'link': url,  # MongoDB 스키마에 맞게 link 필드 사용
                        'published': published_korea,  # 한국시간으로 변환하여 저장
                        'source': 'FinancialModelingPrep',
                        'description': '',  # FMP API는 description을 제공하지 않음
                        'category': 'crypto',  # 크립토 뉴스 카테고리 표시
                        'symbol': item.get('symbol', ''),
                        'publisher': item.get('publisher', ''),
                        'site': item.get('site', '')
                    }
                    
                    news_items.append(news_item)
                    print(f"  - 뉴스 아이템 추가 완료")
                
                except Exception as e:
                    print(f"개별 뉴스 아이템 처리 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"총 {len(news_items)}개의 새로운 뉴스 아이템 처리 완료")
            
            # DB에 새 뉴스 저장
            if news_items:
                print("DB 저장 시작...")
                saved_count = self.db.save_news_batch(news_items)
                print(f"{saved_count}개의 새로운 뉴스를 DB에 저장했습니다.")
            
            return news_items
            
        except Exception as e:
            print(f"FinancialModelingPrep API 요청 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def fetch_general_news(self, page: int = 0, limit: int = 5) -> List[Dict]:
        """FinancialModelingPrep API에서 일반 뉴스 수집"""
        try:
            params = {
                'page': page,
                'limit': limit,
                'apikey': self.api_key
            }
            
            print(f"FinancialModelingPrep 일반 뉴스 API 요청: page={page}, limit={limit}")
            
            response = requests.get(self.general_base_url, params=params, timeout=10)
            print(f"일반 뉴스 API 응답 상태: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            print(f"일반 뉴스 API 응답 데이터 타입: {type(data)}, 길이: {len(data) if isinstance(data, list) else 'N/A'}")
            
            if not isinstance(data, list):
                print(f"일반 뉴스 예상치 못한 응답 형식: {type(data)}")
                return []
            
            news_items = []
            print(f"총 {len(data)}개의 일반 뉴스 아이템 처리 시작...")
            
            for i, item in enumerate(data):
                try:
                    print(f"일반 뉴스 아이템 {i+1}/{len(data)} 처리 중...")
                    
                    # API 응답에서 필요한 필드 추출
                    title = item.get('title', '')
                    published_date = item.get('publishedDate', '')
                    url = item.get('url', '')
                    
                    print(f"  - 제목: {title[:50]}...")
                    print(f"  - URL: {url}")
                    
                    # 필수 필드 확인
                    if not title.strip() or not url.strip():
                        print("  - 필수 필드 부족, 건너뜀")
                        continue
                    
                    # DB 중복 체크 - 이미 저장된 뉴스는 건너뛰기
                    print("  - DB 중복 체크...")
                    if self.db.is_news_exists(url):
                        print("  - 이미 존재하는 뉴스, 건너뜀")
                        continue
                    
                    # 시간을 한국시간으로 변환하여 저장
                    korea_time = self.parse_news_time(published_date)
                    if korea_time:
                        # 한국시간 문자열로 저장
                        published_korea = korea_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        published_korea = published_date
                    
                    news_item = {
                        'title': title,
                        'link': url,  # MongoDB 스키마에 맞게 link 필드 사용
                        'published': published_korea,  # 한국시간으로 변환하여 저장
                        'source': 'FinancialModelingPrep',
                        'description': '',  # FMP API는 description을 제공하지 않음
                        'category': 'general',  # 일반 뉴스 카테고리 표시
                        'publisher': item.get('publisher', ''),
                        'site': item.get('site', '')
                    }
                    
                    news_items.append(news_item)
                    print(f"  - 일반 뉴스 아이템 추가 완료")
                
                except Exception as e:
                    print(f"개별 일반 뉴스 아이템 처리 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"총 {len(news_items)}개의 새로운 일반 뉴스 아이템 처리 완료")
            
            # DB에 새 뉴스 저장
            if news_items:
                print("일반 뉴스 DB 저장 시작...")
                saved_count = self.db.save_news_batch(news_items)
                print(f"{saved_count}개의 새로운 일반 뉴스를 DB에 저장했습니다.")
            
            return news_items
            
        except Exception as e:
            print(f"일반 뉴스 FinancialModelingPrep API 요청 오류: {e}")
            import traceback
            traceback.print_exc()
            return []

    def collect_crypto_news(self, currencies: str = "BTC,ETH", filter_type: str = "hot") -> List[Dict]:
        """암호화폐 뉴스 수집 (FinancialModelingPrep API 사용)"""
        # 기존 인터페이스 호환성을 위해 유지
        return self.fetch_crypto_news()

    def collect_general_news(self) -> List[Dict]:
        """일반 뉴스 수집"""
        return self.fetch_general_news()

    def collect_all_news(self) -> Dict[str, List[Dict]]:
        """크립토 뉴스와 일반 뉴스 모두 수집"""
        crypto_news = self.fetch_crypto_news(limit=5)
        general_news = self.fetch_general_news(limit=5)
        
        return {
            'crypto': crypto_news,
            'general': general_news
        }
    
    def format_message(self, news: Dict) -> str:
        """뉴스 메시지 포맷팅 - YouTube 채팅에 최적화 (링크 제외)"""
        title = news['title']
        description = news.get('description', '')
        published = news.get('published', '')
        
        # 발행시간 포맷팅 (한국 시간대, 24시간 표기)
        time_str = ""
        if published:
            try:
                # FinancialModelingPrep API 시간 포맷: "2025-10-28 23:08:34"
                parsed_time = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
                
                # 한국 시간대로 변환
                korea_tz = pytz.timezone('Asia/Seoul')
                if parsed_time.tzinfo is None:
                    parsed_time = pytz.utc.localize(parsed_time)
                
                korea_time = parsed_time.astimezone(korea_tz)
                time_str = f" ({korea_time.strftime('%H:%M')})"
                
            except Exception as e:
                print(f"시간 파싱 오류: {e}")
                # 간단히 시간만 추출
                time_match = re.search(r'(\d{1,2}:\d{2})', published)
                if time_match:
                    time_str = f" ({time_match.group(1)})"
        
        # YouTube 채팅을 위한 메시지 길이 제한
        MAX_YOUTUBE_LENGTH = 280
        
        # 기본 메시지 구성 (링크 제외)
        message_parts = []
        
        # 제목 (길이 제한)
        title_max_len = 150
        if len(title) > title_max_len:
            title = title[:title_max_len-3] + "..."
        message_parts.append(f"{title}{time_str}")
        
        # 설명 (선택적, 공간이 있을 때만)
        current_length = len(message_parts[0])
        remaining_space = MAX_YOUTUBE_LENGTH - current_length
        
        if description and remaining_space > 50:
            desc_max_len = min(remaining_space - 10, len(description))
            if desc_max_len > 20:
                message_parts.append(f"{description[:desc_max_len]}...")
        
        # 최종 메시지 조합 (링크 없음)
        final_message = " | ".join(message_parts)
        
        # 최종 길이 체크
        if len(final_message) > MAX_YOUTUBE_LENGTH:
            # 길이가 넘으면 제목만 보내기
            title_part = message_parts[0]
            if len(title_part) > MAX_YOUTUBE_LENGTH:
                title_part = title_part[:MAX_YOUTUBE_LENGTH-3] + "..."
            final_message = title_part
        
        return final_message
    
    def parse_news_time(self, published: str) -> Optional[datetime]:
        """뉴스 발행 시간을 파싱하여 datetime 객체로 반환 (한국시간 기준)"""
        if not published:
            return None
            
        try:
            # FinancialModelingPrep API 시간 포맷: "2025-10-28 23:08:34"
            # 이 시간은 뉴욕시간(EST/EDT) 기준이므로 한국시간으로 변환
            parsed_time = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
            
            # 뉴욕 시간대로 설정 (Eastern Time)
            eastern_tz = pytz.timezone('America/New_York')
            if parsed_time.tzinfo is None:
                eastern_time = eastern_tz.localize(parsed_time)
            else:
                eastern_time = parsed_time.astimezone(eastern_tz)
            
            # 한국 시간대로 변환하여 반환
            korea_tz = pytz.timezone('Asia/Seoul')
            korea_time = eastern_time.astimezone(korea_tz)
                
            print(f"시간 변환: {published} (뉴욕) → {korea_time.strftime('%Y-%m-%d %H:%M:%S')} (한국)")
            return korea_time
        except Exception as e:
            print(f"시간 파싱 오류: {e}")
            return None
    
    def set_latest_news_time(self, news: Dict):
        """최신 뉴스 기준 시간 설정"""
        if news and news.get('published'):
            parsed_time = self.parse_news_time(news['published'])
            if parsed_time:
                self.latest_news_time = parsed_time
                print(f"최신 뉴스 기준 시간 설정: {self.latest_news_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    def is_news_newer_than_latest(self, news: Dict) -> bool:
        """뉴스가 최신 기준 시간보다 새로운지 확인"""
        if not self.latest_news_time:
            return True
            
        news_time = self.parse_news_time(news.get('published', ''))
        if not news_time:
            return False
            
        return news_time > self.latest_news_time
    
    def get_newer_news_only(self, all_news: List[Dict]) -> List[Dict]:
        """최신 기준 시간보다 새로운 뉴스만 필터링"""
        if not self.latest_news_time:
            return []
        
        newer_news = []
        for news in all_news:
            if self.is_news_newer_than_latest(news):
                newer_news.append(news)
        
        return newer_news
    
    def mark_news_as_sent(self, news_list: List[Dict]):
        """전송된 뉴스를 중복 체크 목록에 추가"""
        for news in news_list:
            link = news.get('link', '')
            if link:
                self.sent_news_links.add(link)
    
    def get_time_message(self) -> str:
        """현재 시간 메시지 생성 (한국 시간대, 24시간 표기) - 간소화 버전"""
        korea_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(korea_tz)
        time_str = now.strftime("%H:%M")
        
        messages = [
            f"🕐 {time_str} - 뉴스 속보",
            f"⏰ {time_str} - 시장 동향",
            f"📅 {time_str} - 뉴스봇 작동",
            f"🕰️ {time_str} - 소식 업데이트"
        ]
        
        import random
        return random.choice(messages)
    
    def translate_text(self, text: str, source_lang: str = "english", target_lang: str = "korean") -> Optional[str]:
        """
        텍스트를 AI API로 번역합니다.
        
        Args:
            text: 번역할 텍스트
            source_lang: 원본 언어
            target_lang: 목표 언어
            
        Returns:
            번역된 텍스트 또는 None
        """
        try:
            # 프롬프트 구성
            prompt = f"Please translate the following {source_lang} text to {target_lang}. Only return the translated text, no explanations:\n\n{text}"
            
            # OpenAI compatible API 요청 데이터
            data = {
                "model": self.ai_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "max_tokens": 1000,
                "temperature": 0.3
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.ai_api_key}"
            }
            
            print(f"AI 번역 요청: {text[:50]}...")
            
            # API 요청
            response = requests.post(
                f"{self.ai_api_url}/chat/completions",
                json=data,
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 응답에서 번역된 텍스트 추출
            if "choices" in result and len(result["choices"]) > 0:
                translated_text = result["choices"][0]["message"]["content"].strip()
                print(f"번역 완료: {translated_text[:50]}...")
                return translated_text
            else:
                print(f"예상치 못한 응답 형식: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"AI API 요청 오류: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            print(f"번역 오류: {e}")
            return None
    
    def translate_news(self, news_item: Dict) -> Dict:
        """
        뉴스 아이템을 번역하고 DB에 저장합니다.
        
        Args:
            news_item: 번역할 뉴스 아이템
            
        Returns:
            번역된 뉴스 아이템 (원본과 번역본 모두 포함)
        """
        translated_news = news_item.copy()
        
        # 제목 번역
        if news_item.get('title'):
            translated_title = self.translate_text(news_item['title'])
            if translated_title:
                translated_news['translated_title'] = translated_title
                # DB에 번역 결과 저장
                self.db.update_translation(news_item['link'], translated_title=translated_title)
        
        # 내용 번역 (필요시 활성화)
        # if news_item.get('description'):
        #     translated_description = self.translate_text(news_item['description'])
        #     if translated_description:
        #         translated_news['translated_description'] = translated_description
        #         self.db.update_translation(news_item['link'], translated_description=translated_description)
        
        return translated_news
    
    def process_untranslated_news(self, limit: int = 10) -> List[Dict]:
        """
        번역되지 않은 뉴스를 가져와서 번역 처리합니다.
        
        Args:
            limit: 한 번에 처리할 뉴스 수
            
        Returns:
            번역된 뉴스 리스트
        """
        untranslated_news = self.db.get_untranslated_news(limit)
        translated_news_list = []
        
        for news in untranslated_news:
            try:
                print(f"뉴스 번역 처리: {news['title'][:50]}...")
                translated_news = self.translate_news(news)
                translated_news_list.append(translated_news)
                
                # API 호출 간격을 위해 잠시 대기
                time.sleep(1)
                
            except Exception as e:
                print(f"뉴스 번역 처리 오류: {e}")
                # 번역 실패 시 원본 뉴스 사용
                translated_news_list.append(news)
        
        return translated_news_list
    
    def get_latest_translated_news(self, limit: int = 5) -> List[Dict]:
        """
        최신 번역된 뉴스를 DB에서 가져옵니다.
        
        Args:
            limit: 가져올 뉴스 수
            
        Returns:
            최신 번역된 뉴스 리스트
        """
        return self.db.get_latest_news(limit)
    
    def format_translated_message(self, news: Dict) -> str:
        """번역된 뉴스 메시지 포맷팅 - YouTube 채팅에 최적화"""
        # 번역된 제목이 있으면 사용, 없으면 원본 제목 사용
        title = news.get('translated_title', news['title'])
        description = news.get('translated_description', news.get('description', ''))
        published = news.get('published', '')
        
        # 발행시간 포맷팅 (한국 시간대, 24시간 표기)
        time_str = ""
        if published:
            try:
                # FinancialModelingPrep API 시간 포맷: "2025-10-28 23:08:34"
                parsed_time = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
                
                # 한국 시간대로 변환
                korea_tz = pytz.timezone('Asia/Seoul')
                if parsed_time.tzinfo is None:
                    parsed_time = pytz.utc.localize(parsed_time)
                
                korea_time = parsed_time.astimezone(korea_tz)
                time_str = f" ({korea_time.strftime('%H:%M')})"
                
            except Exception as e:
                print(f"시간 파싱 오류: {e}")
                # 간단히 시간만 추출
                time_match = re.search(r'(\d{1,2}:\d{2})', published)
                if time_match:
                    time_str = f" ({time_match.group(1)})"
        
        # YouTube 채팅을 위한 메시지 길이 제한
        MAX_YOUTUBE_LENGTH = 280
        
        # 기본 메시지 구성 (링크 제외)
        message_parts = []
        
        # 제목 (길이 제한)
        title_max_len = 150
        if len(title) > title_max_len:
            title = title[:title_max_len-3] + "..."
        message_parts.append(f"{title}{time_str}")
        
        # 설명 (선택적, 공간이 있을 때만)
        current_length = len(message_parts[0])
        remaining_space = MAX_YOUTUBE_LENGTH - current_length
        
        if description and remaining_space > 50:
            desc_max_len = min(remaining_space - 10, len(description))
            if desc_max_len > 20:
                message_parts.append(f"{description[:desc_max_len]}...")
        
        # 최종 메시지 조합 (링크 없음)
        final_message = " | ".join(message_parts)
        
        # 최종 길이 체크
        if len(final_message) > MAX_YOUTUBE_LENGTH:
            # 길이가 넘으면 제목만 보내기
            title_part = message_parts[0]
            if len(title_part) > MAX_YOUTUBE_LENGTH:
                title_part = title_part[:MAX_YOUTUBE_LENGTH-3] + "..."
            final_message = title_part
        
        return final_message
