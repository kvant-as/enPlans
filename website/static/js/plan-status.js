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
}