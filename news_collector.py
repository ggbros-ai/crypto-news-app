"""
뉴스 수집 모듈
CryptoPanic RSS/API를 통한 암호화폐 뉴스 수집 기능
"""

import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET
import re
import pytz
import json
from database import NewsDatabase


class NewsCollector:
    """CryptoPanic RSS/API를 통한 암호화폐 뉴스 수집 클래스"""
    
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        
        # CryptoPanic API 엔드포인트
        self.RSS_URL = "https://cryptopanic.com/news/rss/"
        self.API_RSS_URL = "https://cryptopanic.com/api/v1/posts/"
        
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
    
    def fetch_rss_via_api(self, params: dict = None) -> Optional[str]:
        """CryptoPanic API로 RSS 포맷으로 데이터를 요청"""
        if not self.auth_token:
            return None
        
        if params is None:
            params = {}
        
        params["format"] = "rss"
        params["auth_token"] = self.auth_token

        try:
            resp = requests.get(self.API_RSS_URL, params=params, timeout=10)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"CryptoPanic API 요청 오류: {e}")
            return None
    
    def parse_rss_xml(self, xml_content: str) -> List[Dict]:
        """RSS XML 문자열을 파싱해서 항목들(title, link, published 등)을 리스트로 반환"""
        try:
            root = ET.fromstring(xml_content)
            
            items = []
            
            # RSS 2.0 형식 처리
            if root.tag == 'rss':
                channel = root.find('channel')
                items_elements = channel.findall('item') if channel is not None else []
            # Atom 형식 처리
            elif root.tag.endswith('feed'):
                items_elements = root.findall('{http://www.w3.org/2005/Atom}entry')
            else:
                print(f"알 수 없는 RSS 형식: {root.tag}")
                items_elements = []
            
            for item in items_elements:
                try:
                    # 제목 가져오기
                    title_elem = item.find('title')
                    title = title_elem.text if (title_elem is not None and title_elem.text) else ''
                    
                    # 링크 가져오기
                    link_elem = item.find('link')
                    if link_elem is not None:
                        link = link_elem.get('href') if link_elem.get('href') else (link_elem.text or '')
                    else:
                        link = ''
                    
                    # 발행일 가져오기
                    pub_elem = item.find('pubDate')
                    if pub_elem is None:
                        pub_elem = item.find('{http://www.w3.org/2005/Atom}published')
                    published = pub_elem.text if (pub_elem is not None and pub_elem.text) else ''
                    
                    # 설명 가져오기
                    desc_elem = item.find('description') or item.find('summary')
                    summary = desc_elem.text if (desc_elem is not None and desc_elem.text) else ''
                    
                    # 유효한 뉴스 아이템만 추가
                    if title.strip() and link.strip():
                        item_data = {
                            "title": title,
                            "link": link,
                            "published": published,
                            "summary": summary
                        }
                        items.append(item_data)
                
                except Exception as e:
                    print(f"개별 뉴스 아이템 처리 오류: {e}")
                    continue
            
            return items
        except Exception as e:
            print(f"RSS XML 파싱 오류: {e}")
            return []
    
    def fetch_fallback_rss(self) -> List[Dict]:
        """API 토큰이 없을 경우 일반 RSS 피드에서 데이터 가져오기 (폴백)"""
        try:
            print(f"RSS URL 요청: {self.RSS_URL}")
            resp = requests.get(self.RSS_URL, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            resp.raise_for_status()
            
            items = self.parse_rss_xml(resp.text)
            return items
        except Exception as e:
            print(f"폴백 RSS 요청 오류: {e}")
            return []
    
    def collect_crypto_news(self, currencies: str = "BTC,ETH", filter_type: str = "hot") -> List[Dict]:
        """암호화폐 뉴스 수집 (항상 RSS 사용)"""
        news_items = []
        
        try:
            print("CryptoPanic RSS 피드에서 뉴스 수집 중...")
            items = self.fetch_fallback_rss()
            
            # 뉴스 아이템 포맷 변환 및 중복 체크
            for item in items:
                title = item.get('title', '')
                link = item.get('link', '')
                
                # 빈 제목이나 링크는 건너뛰기
                if not title.strip() or not link.strip():
                    continue
                
                # DB 중복 체크 - 이미 저장된 뉴스는 건너뛰기
                if self.db.is_news_exists(link):
                    continue
                    
                news_item = {
                    'title': f"{item['title']}",
                    'description': item['summary'][:100] + '...' if len(item.get('summary', '')) > 100 else item.get('summary', ''),
                    'link': item['link'],
                    'published': item['published'],
                    'source': 'CryptoPanic'
                }
                
                news_items.append(news_item)
            
            # DB에 새 뉴스 저장
            if news_items:
                saved_count = self.db.save_news_batch(news_items)
                print(f"{saved_count}개의 새로운 뉴스를 DB에 저장했습니다.")
            
            print(f"{len(news_items)}개의 새로운 뉴스 아이템 처리 완료")
            return news_items
            
        except Exception as e:
            print(f"암호화폐 뉴스 수집 오류: {e}")
            return []
    
    def format_message(self, news: Dict) -> str:
        """뉴스 메시지 포맷팅 - YouTube 채팅에 최적화 (링크 제외)"""
        title = news['title']
        description = news['description']
        published = news.get('published', '')
        
        # 발행시간 포맷팅 (한국 시간대, 24시간 표기)
        time_str = ""
        if published:
            try:
                # 다양한 RSS 시간 포맷 파싱
                time_formats = [
                    "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
                    "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
                    "%Y-%m-%d %H:%M:%S %z",       # Custom
                ]
                
                parsed_time = None
                for fmt in time_formats:
                    try:
                        clean_time = published.replace('GMT', '+0000').replace('UTC', '+0000')
                        parsed_time = datetime.strptime(clean_time, fmt)
                        break
                    except:
                        continue
                
                if parsed_time:
                    # 한국 시간대로 변환
                    korea_tz = pytz.timezone('Asia/Seoul')
                    if parsed_time.tzinfo is None:
                        parsed_time = pytz.utc.localize(parsed_time)
                    
                    korea_time = parsed_time.astimezone(korea_tz)
                    time_str = f" ({korea_time.strftime('%H:%M')})"
                else:
                    # 파싱 실패 시 간단히 시간만 추출
                    time_match = re.search(r'(\d{1,2}:\d{2})', published)
                    if time_match:
                        time_str = f" ({time_match.group(1)})"
            except Exception as e:
                print(f"시간 파싱 오류: {e}")
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
        """뉴스 발행 시간을 파싱하여 datetime 객체로 반환"""
        if not published:
            return None
            
        try:
            time_formats = [
                "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
                "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
                "%Y-%m-%d %H:%M:%S %z",       # Custom
            ]
            
            parsed_time = None
            for fmt in time_formats:
                try:
                    clean_time = published.replace('GMT', '+0000').replace('UTC', '+0000')
                    parsed_time = datetime.strptime(clean_time, fmt)
                    break
                except:
                    continue
            
            if parsed_time and parsed_time.tzinfo is None:
                parsed_time = pytz.utc.localize(parsed_time)
                
            return parsed_time
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
    
    def get_latest_translated_news(self, limit: int = 20) -> List[Dict]:
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
        description = news.get('translated_description', news['description'])
        published = news.get('published', '')
        
        # 발행시간 포맷팅 (한국 시간대, 24시간 표기)
        time_str = ""
        if published:
            try:
                # 다양한 RSS 시간 포맷 파싱
                time_formats = [
                    "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
                    "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
                    "%Y-%m-%d %H:%M:%S %z",       # Custom
                ]
                
                parsed_time = None
                for fmt in time_formats:
                    try:
                        clean_time = published.replace('GMT', '+0000').replace('UTC', '+0000')
                        parsed_time = datetime.strptime(clean_time, fmt)
                        break
                    except:
                        continue
                
                if parsed_time:
                    # 한국 시간대로 변환
                    korea_tz = pytz.timezone('Asia/Seoul')
                    if parsed_time.tzinfo is None:
                        parsed_time = pytz.utc.localize(parsed_time)
                    
                    korea_time = parsed_time.astimezone(korea_tz)
                    time_str = f" ({korea_time.strftime('%H:%M')})"
                else:
                    # 파싱 실패 시 간단히 시간만 추출
                    time_match = re.search(r'(\d{1,2}:\d{2})', published)
                    if time_match:
                        time_str = f" ({time_match.group(1)})"
            except Exception as e:
                print(f"시간 파싱 오류: {e}")
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
