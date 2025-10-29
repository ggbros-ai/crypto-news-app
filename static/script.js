// 뉴스 관리 클래스
class NewsManager {
    constructor() {
        this.newsList = [];
        this.maxNewsCount = 50; // 최대 뉴스 개수
        this.updateInterval = 30000; // 30초마다 업데이트
        this.sentNewsLinks = new Set(); // 중복 방지를 위한 링크 저장
        
        this.init();
    }

    init() {
        // 시간 업데이트 시작
        this.updateCurrentTime();
        setInterval(() => this.updateCurrentTime(), 1000);
        
        // 뉴스 수집 시작
        this.startNewsCollection();
    }

    updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        const dateString = now.toLocaleDateString('ko-KR', {
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        });
        
        document.getElementById('currentTime').textContent = `${dateString} ${timeString}`;
    }

    async startNewsCollection() {
        // 즉시 한번 실행
        await this.collectAndDisplayNews();
        
        // 주기적으로 실행
        setInterval(async () => {
            await this.collectAndDisplayNews();
        }, this.updateInterval);
    }

    async collectAndDisplayNews() {
        try {
            this.showLoading(true);
            
            // 뉴스 수집 (백엔드에서 이미 번역된 뉴스를 받아옴)
            const newNews = await this.fetchNewsFromCollector();
            
            if (newNews && newNews.length > 0) {
                // 기존 뉴스 리스트 초기화하고 백엔드에서 받은 최신 뉴스로 교체
                this.newsList = newNews;
                
                // 중복 체크를 위한 링크 저장
                newNews.forEach(news => {
                    this.sentNewsLinks.add(news.link);
                });
                
                // 최대 개수 유지
                if (this.newsList.length > this.maxNewsCount) {
                    this.newsList = this.newsList.slice(0, this.maxNewsCount);
                }
                
                // 화면 업데이트
                this.displayNews();
                this.updateStats();
                
                console.log(`${newNews.length}개의 뉴스가 업데이트되었습니다.`);
            } else {
                // 뉴스가 없을 때
                if (this.newsList.length === 0) {
                    this.showNoNewsMessage();
                } else {
                    this.displayNews();
                    this.updateStats();
                }
            }
        } catch (error) {
            console.error('뉴스 수집 오류:', error);
            this.showErrorMessage();
        } finally {
            this.showLoading(false);
        }
    }

    async fetchNewsFromCollector() {
        try {
            // Flask API를 통해 뉴스 수집
            const response = await fetch('/api/news');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            if (data.success && data.news) {
                return data.news;
            } else {
                console.error('뉴스 API 응답 오류:', data);
                return [];
            }
        } catch (error) {
            console.error('뉴스 수집기 호출 오류:', error);
            return [];
        }
    }

    displayNews() {
        const container = document.getElementById('newsContainer');
        
        if (this.newsList.length === 0) {
            this.showNoNewsMessage();
            return;
        }

        const newsHTML = this.newsList.map((news, index) => {
            const timeAgo = this.getTimeAgo(news.published);
            const isNew = index < 3; // 최신 3개는 새로운 뉴스로 표시
            
            // 영문제목과 한글제목이 다를 경우에만 영문제목 표시
            const showOriginalTitle = news.title && news.translated_title && 
                                     news.title.trim() !== news.translated_title.trim();
            
            return `
                <div class="news-item ${isNew ? 'new' : ''}" onclick="newsManager.openNewsLink('${news.link}')">
                    <div class="news-header">
                        <span class="news-time">${timeAgo}</span>
                    </div>
                    <!-- 한글제목(번역제목) - 크게 표시 -->
                    <h3 class="news-title">${this.escapeHtml(news.translated_title || news.title)}</h3>
                    <!-- 영문제목(원본) - 한글제목과 다를 경우에만 표시 -->
                    ${showOriginalTitle ? `
                        <div class="news-original-title">${this.escapeHtml(news.title)}</div>
                    ` : ''}
                    ${news.translated_description || news.description ? `
                        <p class="news-description">${this.escapeHtml(news.translated_description || news.description)}</p>
                    ` : ''}
                    <div class="news-source">
                        <i class="fas fa-rss"></i>
                        ${news.source}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = newsHTML;
    }

    openNewsLink(link) {
        if (link) {
            window.open(link, '_blank');
        }
    }

    getTimeAgo(published) {
        const now = new Date();
        const newsTime = new Date(published);
        const diffMs = now - newsTime;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return '방금';
        if (diffMins < 60) return `${diffMins}분 전`;
        
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}시간 전`;
        
        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays}일 전`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showLoading(show) {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            if (show) {
                loadingIndicator.style.display = 'flex';
            } else {
                loadingIndicator.style.display = 'none';
            }
        }
    }

    showNoNewsMessage() {
        const container = document.getElementById('newsContainer');
        container.innerHTML = `
            <div class="no-news-message">
                <i class="fas fa-newspaper"></i>
                <p>수집된 뉴스가 없습니다.</p>
                <p>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
    }

    showErrorMessage() {
        const container = document.getElementById('newsContainer');
        container.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <p>뉴스 수집 중 오류가 발생했습니다.</p>
                <p>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
    }

    updateStats() {
        document.getElementById('totalNews').textContent = this.newsList.length;
        
        const now = new Date();
        const timeString = now.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('lastUpdate').textContent = timeString;
    }
}

// 뉴스 관리자 초기화
let newsManager;
document.addEventListener('DOMContentLoaded', () => {
    newsManager = new NewsManager();
});
