"""
뉴스 데이터베이스 모듈
SQLite를 사용한 뉴스 저장 및 관리 기능
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

class NewsDatabase:
    """뉴스 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "news.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 뉴스 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    link TEXT UNIQUE NOT NULL,
                    description TEXT,
                    published TEXT,
                    source TEXT DEFAULT 'CryptoPanic',
                    translated_title TEXT,
                    translated_description TEXT,
                    translation_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_link ON news(link)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_published ON news(published)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_translation_status ON news(translation_status)
            ''')
            
            conn.commit()
            conn.close()
            print("데이터베이스 초기화 완료")
            
        except Exception as e:
            print(f"데이터베이스 초기화 오류: {e}")
    
    def is_news_exists(self, link: str) -> bool:
        """뉴스가 이미 존재하는지 확인"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM news WHERE link = ?", (link,))
            result = cursor.fetchone()
            
            conn.close()
            return result is not None
            
        except Exception as e:
            print(f"뉴스 존재 확인 오류: {e}")
            return False
    
    def save_news(self, news_item: Dict) -> bool:
        """새로운 뉴스 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 중복 체크
            if self.is_news_exists(news_item['link']):
                conn.close()
                return False
            
            cursor.execute('''
                INSERT INTO news (title, link, description, published, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                news_item['title'],
                news_item['link'],
                news_item.get('description', ''),
                news_item.get('published', ''),
                news_item.get('source', 'CryptoPanic')
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"뉴스 저장 오류: {e}")
            return False
    
    def save_news_batch(self, news_items: List[Dict]) -> int:
        """여러 뉴스 일괄 저장"""
        saved_count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for news_item in news_items:
                # 중복 체크
                if not self.is_news_exists(news_item['link']):
                    cursor.execute('''
                        INSERT INTO news (title, link, description, published, source)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        news_item['title'],
                        news_item['link'],
                        news_item.get('description', ''),
                        news_item.get('published', ''),
                        news_item.get('source', 'CryptoPanic')
                    ))
                    saved_count += 1
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"뉴스 일괄 저장 오류: {e}")
        
        return saved_count
    
    def update_translation(self, link: str, translated_title: str = None, 
                          translated_description: str = None) -> bool:
        """뉴스 번역 정보 업데이트"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            update_fields = []
            values = []
            
            if translated_title:
                update_fields.append("translated_title = ?")
                values.append(translated_title)
            
            if translated_description:
                update_fields.append("translated_description = ?")
                values.append(translated_description)
            
            if update_fields:
                update_fields.append("translation_status = ?")
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.extend(['completed', link])
                
                query = f"UPDATE news SET {', '.join(update_fields)} WHERE link = ?"
                cursor.execute(query, values)
                
                conn.commit()
                conn.close()
                return True
            
            conn.close()
            return False
            
        except Exception as e:
            print(f"번역 정보 업데이트 오류: {e}")
            return False
    
    def get_untranslated_news(self, limit: int = 50) -> List[Dict]:
        """번역되지 않은 뉴스 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, link, description, published, source
                FROM news 
                WHERE translation_status = 'pending' OR translated_title IS NULL
                ORDER BY published DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            news_list = []
            for row in rows:
                news_list.append({
                    'id': row[0],
                    'title': row[1],
                    'link': row[2],
                    'description': row[3],
                    'published': row[4],
                    'source': row[5]
                })
            
            return news_list
            
        except Exception as e:
            print(f"번역되지 않은 뉴스 조회 오류: {e}")
            return []
    
    def get_latest_news(self, limit: int = 20) -> List[Dict]:
        """최신 뉴스 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, link, description, published, source,
                       translated_title, translated_description
                FROM news 
                ORDER BY published DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            news_list = []
            for row in rows:
                news_item = {
                    'id': row[0],
                    'title': row[1],
                    'link': row[2],
                    'description': row[3],
                    'published': row[4],
                    'source': row[5]
                }
                
                # 번역된 제목은 별도 필드로 저장 (원본 제목 유지)
                if row[6]:  # translated_title
                    news_item['translated_title'] = row[6]
                
                if row[7]:  # translated_description
                    news_item['translated_description'] = row[7]
                
                news_list.append(news_item)
            
            return news_list
            
        except Exception as e:
            print(f"최신 뉴스 조회 오류: {e}")
            return []
    
    def get_news_count(self) -> Dict[str, int]:
        """뉴스 통계 정보 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 전체 뉴스 수
            cursor.execute("SELECT COUNT(*) FROM news")
            total_count = cursor.fetchone()[0]
            
            # 번역된 뉴스 수
            cursor.execute("SELECT COUNT(*) FROM news WHERE translated_title IS NOT NULL")
            translated_count = cursor.fetchone()[0]
            
            # 번역 대기 뉴스 수
            cursor.execute("SELECT COUNT(*) FROM news WHERE translation_status = 'pending'")
            pending_count = cursor.fetchone()[0]
            
            conn.close()
            
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM news 
                WHERE created_at < datetime('now', '-{} days')
            '''.format(days))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted_count
            
        except Exception as e:
            print(f"오래된 뉴스 정리 오류: {e}")
            return 0
    
    def get_news_by_link(self, link: str) -> Optional[Dict]:
        """링크로 뉴스 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, link, description, published, source,
                       translated_title, translated_description
                FROM news 
                WHERE link = ?
            ''', (link,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                news_item = {
                    'id': row[0],
                    'title': row[1],
                    'link': row[2],
                    'description': row[3],
                    'published': row[4],
                    'source': row[5]
                }
                
                if row[6]:  # translated_title
                    news_item['translated_title'] = row[6]
                
                if row[7]:  # translated_description
                    news_item['translated_description'] = row[7]
                
                return news_item
            
            return None
            
        except Exception as e:
            print(f"링크로 뉴스 조회 오류: {e}")
            return None
