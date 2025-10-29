from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import json
import asyncio
from news_collector import NewsCollector
import threading
import time
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
CORS(app)

# 전역 뉴스 수집기 인스턴스
news_collector = NewsCollector()
latest_news = []
last_update_time = None

def background_news_collection():
    """백그라운드에서 뉴스 수집을 주기적으로 실행"""
    global latest_news, last_update_time
    
    while True:
        try:
            print("뉴스 수집 시작...")
            
            # 크립토 뉴스와 일반 뉴스 모두 수집
            all_news = news_collector.collect_all_news()
            
            if all_news['crypto'] or all_news['general']:
                # 번역되지 않은 뉴스만 번역 처리
                translated_news = news_collector.process_untranslated_news(10)
                
                # 최신 뉴스 업데이트 (DB에서 가져오기)
                latest_news = news_collector.db.get_news_by_categories(5, 5)
                last_update_time = time.strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"크립토 뉴스 {len(all_news['crypto'])}개, 일반 뉴스 {len(all_news['general'])}개가 업데이트되었습니다.")
            else:
                print("새로운 뉴스가 없습니다.")
                
        except Exception as e:
            print(f"뉴스 수집 오류: {e}")
        
        # 30초 대기
        time.sleep(30)

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/api/news')
def get_news():
    """카테고리별 최신 뉴스 API"""
    try:
        # DB에서 카테고리별 최신 뉴스 가져오기
        categorized_news = news_collector.db.get_news_by_categories(5, 5)
        
        response_data = {
            'success': True,
            'crypto_news': categorized_news['crypto'],
            'general_news': categorized_news['general'],
            'crypto_count': len(categorized_news['crypto']),
            'general_count': len(categorized_news['general']),
            'total_count': len(categorized_news['crypto']) + len(categorized_news['general']),
            'last_update': last_update_time
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/news/<category>')
def get_news_by_category(category):
    """특정 카테고리 뉴스 API"""
    try:
        if category not in ['crypto', 'general']:
            return jsonify({
                'success': False,
                'error': '유효하지 않은 카테고리입니다.'
            }), 400
        
        # 해당 카테고리 뉴스 가져오기
        news_list = news_collector.db.get_latest_news_by_category(category, 10)
        
        response_data = {
            'success': True,
            'category': category,
            'news': news_list,
            'count': len(news_list),
            'last_update': last_update_time
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/translate', methods=['POST'])
def translate_text():
    """텍스트 번역 API"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({
                'success': False,
                'error': '번역할 텍스트가 없습니다.'
            }), 400
        
        translated = news_collector.translate_text(text)
        
        if translated:
            return jsonify({
                'success': True,
                'translated_text': translated
            })
        else:
            return jsonify({
                'success': False,
                'error': '번역에 실패했습니다.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health')
def health_check():
    """헬스 체크 API"""
    # DB 통계 정보 가져오기
    db_stats = news_collector.db.get_news_count()
    
    return jsonify({
        'status': 'healthy',
        'news_count': len(latest_news),
        'last_update': last_update_time,
        'db_stats': db_stats
    })

@app.route('/api/stats')
def get_stats():
    """뉴스 통계 API"""
    try:
        db_stats = news_collector.db.get_news_count()
        
        return jsonify({
            'success': True,
            'stats': db_stats,
            'last_update': last_update_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/translate_pending', methods=['POST'])
def translate_pending_news():
    """번역 대기 뉴스 번역 처리 API"""
    try:
        data = request.get_json()
        limit = data.get('limit', 5)
        
        # 번역되지 않은 뉴스 처리
        translated_news = news_collector.process_untranslated_news(limit)
        
        return jsonify({
            'success': True,
            'processed_count': len(translated_news),
            'message': f'{len(translated_news)}개의 뉴스를 번역 처리했습니다.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 프로덕션 환경에서 백그라운드 스레드 시작
if not os.environ.get('WERKZEUG_RUN_MAIN'):
    collection_thread = threading.Thread(target=background_news_collection, daemon=True)
    collection_thread.start()

if __name__ == '__main__':
    print("뉴스 수집 웹 서버 시작...")
    print("http://localhost:5000 에서 접속 가능")
    
    # Flask 서버 실행 (개발 환경에서만)
    app.run(host='0.0.0.0', port=5000, debug=False)
