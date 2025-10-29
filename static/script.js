// 뉴스 관리 클래스
class NewsManager {
    constructor() {
        this.cryptoNewsList = [];
        this.generalNewsList = [];
        this.maxNewsCount = 5; // 카테고리별 최대 뉴스 개수
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
            
            // 카테고리별 뉴스 수집
            const newsData = await this.fetchNewsFromCollector();
            
            if (newsData) {
                this.cryptoNewsList = newsData.crypto_news || [];
                this.generalNewsList = newsData.general_news || [];
                
                // 화면 업데이트
                this.displayNews();
                this.updateStats();
                
                console.log(`크립토 뉴스 ${this.cryptoNewsList.length}개, 일반 뉴스 ${this.generalNewsList.length}개가 업데이트되었습니다.`);
            } else {
                // 뉴스가 없을 때
                if (this.cryptoNewsList.length === 0 && this.generalNewsList.length === 0) {
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
            // Flask API를 통해 카테고리별 뉴스 수집
            const response = await fetch('/api/news');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            if (data.success) {
                return data;
            } else {
                console.error('뉴스 API 응답 오류:', data);
                return null;
            }
        } catch (error) {
            console.error('뉴스 수집기 호출 오류:', error);
            return null;
        }
    }

    displayNews() {
        // 일반 뉴스 섹션 업데이트
        this.displayGeneralNews();
        
        // 암호화폐 뉴스 섹션 업데이트
        this.displayCryptoNews();
    }

    displayGeneralNews() {
        const container = document.getElementById('generalNewsContainer');
        const generalNews = this.generalNewsList.slice(0, this.maxNewsCount);
        
        if (generalNews.length === 0) {
            container.innerHTML = `
                <div class="no-news-message">
                    <i class="fas fa-newspaper"></i>
                    <p>수집된 일반 뉴스가 없습니다.</p>
                </div>
            `;
            return;
        }

        const newsHTML = generalNews.map((news, index) => {
            const timeAgo = this.getTimeAgo(news.published);
            const isNew = index < 2; // 최신 2개는 새로운 뉴스로 표시
            
            return `
                <div class="news-item general ${isNew ? 'new' : ''}" onclick="newsManager.openNewsLink('${news.link}')">
                    <div class="news-header">
                        <h3 class="news-title">${this.escapeHtml(news.translated_title || news.title)}</h3>
                        <span class="news-time">${timeAgo}</span>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = newsHTML;
    }

    displayCryptoNews() {
        const container = document.getElementById('cryptoNewsContainer');
        const cryptoNews = this.cryptoNewsList.slice(0, this.maxNewsCount);
        
        if (cryptoNews.length === 0) {
            container.innerHTML = `
                <div class="no-news-message">
                    <i class="fab fa-bitcoin"></i>
                    <p>수집된 암호화폐 뉴스가 없습니다.</p>
                </div>
            `;
            return;
        }

        const newsHTML = cryptoNews.map((news, index) => {
            const timeAgo = this.getTimeAgo(news.published);
            const isNew = index < 2; // 최신 2개는 새로운 뉴스로 표시
            
            return `
                <div class="news-item crypto ${isNew ? 'new' : ''}" onclick="newsManager.openNewsLink('${news.link}')">
                    <div class="news-header">
                        <h3 class="news-title">${this.escapeHtml(news.translated_title || news.title)}</h3>
                        <span class="news-time">${timeAgo}</span>
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
        
        // published는 서버에서 이미 한국시간으로 변환된 문자열
        let newsTime;
        if (typeof published === 'string') {
            // "2025-10-29 00:30:57" 형식을 한국시간으로 파싱
            const [datePart, timePart] = published.split(' ');
            const [year, month, day] = datePart.split('-').map(Number);
            const [hour, minute, second] = timePart.split(':').map(Number);
            
            // 한국시간으로 Date 객체 생성 (이미 한국시간임)
            newsTime = new Date(year, month - 1, day, hour, minute, second);
        } else {
            newsTime = published;
        }
        
        // 시간 차이 계산 (밀리초)
        const diffMs = now - newsTime;
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSeconds / 60);
        
        // 1분 미만만 "방금"으로 표시
        if (diffMins < 1) return '방금';
        
        // 1분 이상은 "N분전"으로 표시
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
        // 일반 뉴스 로딩 인디케이터
        const generalLoadingIndicator = document.getElementById('generalLoadingIndicator');
        if (generalLoadingIndicator) {
            generalLoadingIndicator.style.display = show ? 'flex' : 'none';
        }
        
        // 암호화폐 뉴스 로딩 인디케이터
        const cryptoLoadingIndicator = document.getElementById('cryptoLoadingIndicator');
        if (cryptoLoadingIndicator) {
            cryptoLoadingIndicator.style.display = show ? 'flex' : 'none';
        }
    }

    showErrorMessage() {
        const generalContainer = document.getElementById('generalNewsContainer');
        const cryptoContainer = document.getElementById('cryptoNewsContainer');
        
        const errorMessage = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <p>뉴스 수집 중 오류가 발생했습니다.</p>
                <p>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
        
        generalContainer.innerHTML = errorMessage;
        cryptoContainer.innerHTML = errorMessage;
    }

    updateStats() {
        const totalCount = this.cryptoNewsList.length + this.generalNewsList.length;
        document.getElementById('totalNews').textContent = totalCount;
        
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
