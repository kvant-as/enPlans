function initStatusProgress() {
    const planElements = document.querySelectorAll('.plan-cont');
    const progressLine = document.querySelector('.progress-line-active');
    const statusDots = document.querySelectorAll('.status-dot');
    
    if (!planElements.length || !progressLine || !statusDots.length) {
        console.warn('Plan status progress elements not found');
        return;
    }
    
    const isAuditor = document.querySelector('body')?.dataset?.isAuditor === 'true' || 
                      document.querySelector('.stats-container')?.querySelector('.stat-number-sogl') !== null;
    
    let statusConfig;
    
    if (isAuditor) {
        statusConfig = {
            'plan-cont-sent': { width: '33%', color: 'var(--color-sented)', dotIndex: 0 },
            'plan-cont-sogl': { width: '66%', color: 'var(--color-sogl)', dotIndex: 1 },
            'plan-cont-eror': { width: '83%', color: 'var(--color-erorsed)', dotIndex: 2 },
            'plan-cont-sub': { width: '100%', color: 'var(--color-submited)', dotIndex: 3 }
        };
    } else {
        statusConfig = {
            'plan-cont-redac': { width: '20%', color: 'var(--color-redaced)', dotIndex: 0 },
            'plan-cont-control': { width: '40%', color: 'var(--color-controled)', dotIndex: 1 },
            'plan-cont-sent': { width: '60%', color: 'var(--color-sented)', dotIndex: 2 },
            'plan-cont-eror': { width: '80%', color: 'var(--color-erorsed)', dotIndex: 3 },
            'plan-cont-sub': { width: '100%', color: 'var(--color-submited)', dotIndex: 4 }
        };
    }
    
    const totalDots = Object.keys(statusConfig).length;
    
    let activePlan = null;
    let isHovering = false;
    
    function resetProgress() {
        progressLine.style.width = '0%';
        progressLine.style.background = 'var(--color-sented)';
        statusDots.forEach((dot, index) => {
            if (index < totalDots) {
                dot.classList.remove('active');
                dot.style.background = 'var(--border-color)';
                dot.style.display = '';
            } else {
                dot.style.display = 'none';
            }
        });
    }
    
    function updateProgress(className) {
        const config = statusConfig[className];
        if (!config) return;
        
        progressLine.style.width = config.width;
        progressLine.style.background = config.color;
        
        statusDots.forEach((dot, index) => {
            if (index < totalDots) {
                dot.style.display = '';
                if (index <= config.dotIndex) {
                    dot.classList.add('active');
                    dot.style.background = config.color;
                } else {
                    dot.classList.remove('active');
                    dot.style.background = 'var(--border-color)';
                }
            } else {
                dot.style.display = 'none';
            }
        });
    }
    
    planElements.forEach(plan => {
        plan.removeEventListener('mouseenter', plan._mouseEnterHandler);
        plan.removeEventListener('mouseleave', plan._mouseLeaveHandler);
    });
    
    planElements.forEach(plan => {
        const mouseEnterHandler = function() {
            isHovering = true;
            const className = Array.from(this.classList).find(cls => 
                cls.startsWith('plan-cont-')
            );
            if (className && statusConfig[className]) {
                activePlan = this;
                updateProgress(className);
            }
        };
        
        const mouseLeaveHandler = function() {
            isHovering = false;
            resetProgress();
        };
        
        plan.addEventListener('mouseenter', mouseEnterHandler);
        plan.addEventListener('mouseleave', mouseLeaveHandler);
        
        plan._mouseEnterHandler = mouseEnterHandler;
        plan._mouseLeaveHandler = mouseLeaveHandler;
    });
    
    statusDots.forEach((dot, index) => {
        if (index >= totalDots) {
            dot.style.display = 'none';
        }
    });

    resetProgress();
    syncProgressLineToTrack();
}

// На мобильном .stats-track листается по горизонтали и точки статусов
// (внутри трека) уезжают вместе со скроллом, а .progress-line-container —
// его сосед, абсолютно спозиционированный относительно НЕскроллящегося
// .stats-container — оставался на месте. Из-за этого заливка (её ширина
// считается в % от .progress-line-container) визуально не совпадала с
// тем, под какой именно точкой/статом она должна заканчиваться.
// Решение: растягиваем .progress-line-container до полной scrollWidth
// трека и двигаем его тем же transform, что и скролл — тогда линия и
// точки всегда остаются друг под другом, а .stats-container обрезает
// лишнее через overflow: hidden (см. base.css).
function syncProgressLineToTrack() {
    const track = document.querySelector('.stats-track');
    const lineContainer = document.querySelector('.progress-line-container');
    if (!track || !lineContainer) return;

    function sync() {
        const isScrollable = track.scrollWidth - track.clientWidth > 1;
        if (isScrollable) {
            lineContainer.style.width = track.scrollWidth + 'px';
            lineContainer.style.transform = `translateX(${-track.scrollLeft}px)`;
        } else {
            lineContainer.style.width = '';
            lineContainer.style.transform = '';
        }
    }

    if (!track.dataset.progressSyncBound) {
        track.dataset.progressSyncBound = 'true';
        track.addEventListener('scroll', sync, { passive: true });
        window.addEventListener('resize', sync);
    }

    sync();
}