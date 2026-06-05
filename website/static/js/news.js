class NewsLoader {
    constructor(options = {}) {
        this.newsData = [];
        this.currentPage = 1;
        this.currentFilter = 'published';
        this.currentSort = options.sort || 'date';
        this.totalPages = 1;
        this.isLoading = false;
        this.perPage = options.perPage || 9;
        
        this.gridId = options.gridId || 'newsGrid';
        this.paginationId = options.paginationId || 'pagination';
        this.pageNumbersId = options.pageNumbersId || 'pageNumbers';
        
        this.init();
    }
    
    init() {
        this.loadNews();
        this.attachEventListeners();
    }
    
    attachEventListeners() {
        document.querySelectorAll('.sort_btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.sort_btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentSort = btn.dataset.sort;
                this.currentPage = 1;
                this.loadNews();
            });
        });
        
        const prevBtn = document.querySelector('.page_btn.prev');
        const nextBtn = document.querySelector('.page_btn.next');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        }
    }
    
    async loadNews() {
        if (this.isLoading) return;
        this.isLoading = true;
        this.showLoading();
        
        try {
            const url = `/api/news?page=${this.currentPage}&per_page=${this.perPage}&filter=${this.currentFilter}&sort=${this.currentSort}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                this.newsData = data.news;
                this.totalPages = data.pages;
                this.renderNews();
                this.updatePagination();
            } else {
                this.showError();
            }
        } catch (error) {
            console.error('Error loading news:', error);
            this.showError();
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    renderNews() {
        const grid = document.getElementById(this.gridId);
        
        if (!this.newsData.length) {
            grid.innerHTML = this.getEmptyStateHTML();
            return;
        }
        
        grid.innerHTML = this.newsData.map(news => this.getNewsCardHTML(news)).join('');
    }
    
    getNewsCardHTML(news) {
        const imageHtml = news.image_url 
            ? `<img src="/static/img/news/${news.image_url}" alt="${this.escapeHtml(news.title)}">`
            : `<div class="image_placeholder">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="48" height="48">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" 
                          d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1M19 20a2 2 0 002-2V8a2 2 0 00-2-2h-4a2 2 0 00-2 2v10a2 2 0 002 2h4z"/>
                </svg>
            </div>`;
        
        return `
            <div class="news_card" onclick="window.newsLoader.viewNews(${news.id})">
                <div class="news_card_image">
                    ${imageHtml}
                </div>
                <div class="news_card_content">
                    <div class="news_card_meta">
                        <span class="news_card_date">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                            </svg>
                            ${this.formatDate(news.published_at || news.created_at)}
                        </span>
                    </div>
                    <h3 class="news_card_title">${this.escapeHtml(news.title)}</h3>
                    <p class="news_card_excerpt">${this.escapeHtml(news.content.substring(0, 120))}${news.content.length > 120 ? '...' : ''}</p>
                    <div class="news_card_footer">
                        <div class="news_card_stats">
                            <div class="news_stat">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                    <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                                </svg>
                                ${news.views_count || 0}
                            </div>
                        </div>
                        <div class="read_more">
                            Читать
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 5l7 7-7 7"/>
                            </svg>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    getEmptyStateHTML() {
        return `
            <div class="empty_state">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="64" height="64">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1M19 20a2 2 0 002-2V8a2 2 0 00-2-2h-4a2 2 0 00-2 2v10a2 2 0 002 2h4z"/>
                </svg>
                <h3>Новостей пока нет</h3>
                <p>Следите за обновлениями — новости появятся скоро</p>
            </div>
        `;
    }
    
    updatePagination() {
        const pageNumbers = document.getElementById(this.pageNumbersId);
        const prevBtn = document.querySelector('.page_btn.prev');
        const nextBtn = document.querySelector('.page_btn.next');
        
        if (this.totalPages <= 1) {
            if (pageNumbers) pageNumbers.innerHTML = '';
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            return;
        }
        
        let pagesHtml = '';
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);
        
        if (startPage > 1) {
            pagesHtml += `<div class="page_number" onclick="window.newsLoader.goToPage(1)">1</div>`;
            if (startPage > 2) pagesHtml += `<div class="page_number disabled">...</div>`;
        }
        
        for (let i = startPage; i <= endPage; i++) {
            pagesHtml += `<div class="page_number ${i === this.currentPage ? 'active' : ''}" onclick="window.newsLoader.goToPage(${i})">${i}</div>`;
        }
        
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) pagesHtml += `<div class="page_number disabled">...</div>`;
            pagesHtml += `<div class="page_number" onclick="window.newsLoader.goToPage(${this.totalPages})">${this.totalPages}</div>`;
        }
        
        if (pageNumbers) pageNumbers.innerHTML = pagesHtml;
        if (prevBtn) prevBtn.disabled = this.currentPage === 1;
        if (nextBtn) nextBtn.disabled = this.currentPage === this.totalPages;
    }
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        this.loadNews();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    viewNews(newsId) {
        window.location.href = `/news/${newsId}`;
    }
    
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / 86400000);
        const months = Math.floor(days / 30);
        
        if (days < 1) return 'Сегодня';
        if (days < 7) return `${days} дн. назад`;
        if (days < 30) return `${Math.floor(days / 7)} нед. назад`;
        if (months < 12) return `${months} мес. назад`;
        return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showLoading() {
        const grid = document.getElementById(this.gridId);
        if (grid && grid.children.length === 0) {
            grid.innerHTML = `
                <div class="loading_state">
                    <div class="loading_spinner"></div>
                    <p style="color: var(--text-subtitle);">Загрузка новостей...</p>
                </div>
            `;
        }
    }
    
    hideLoading() {
        // Handled by renderNews
    }
    
    showError() {
        const grid = document.getElementById(this.gridId);
        if (grid) {
            grid.innerHTML = `
                <div class="empty_state">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="64" height="64">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                    <h3>Ошибка загрузки</h3>
                    <p>Попробуйте обновить страницу</p>
                    <button class="submit-button" onclick="window.newsLoader.loadNews()" style="margin-top: 20px;">Повторить</button>
                </div>
            `;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.newsLoader = new NewsLoader({
        sort: 'date',
        perPage: 9,
        gridId: 'newsGrid',
        paginationId: 'pagination',
        pageNumbersId: 'pageNumbers'
    });
});