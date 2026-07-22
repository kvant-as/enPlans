// cookie.js
window.initCookieBanner = function() {
    const COOKIE_NAME = 'enplans-access';
    const COOKIE_DAYS = 365;
    
    const MODAL_CONFIG = {
        'system-welcom-modal-profile': {
            cookieName: 'enplans-profile',
            pages: ['/profile', '/plans'],
            hasSlides: true,
            delay: 500
        }

    };
    
    function setCookie(name, value, days) {
        let expires = '';
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = '; expires=' + date.toUTCString();
        }
        document.cookie = name + '=' + (value || '') + expires + '; path=/; SameSite=Lax';
    }
    
    function getCookie(name) {
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    function checkCurrentPage(pages) {
        const currentPath = window.location.pathname;
        return pages.some(page => {
            if (page === '/') {
                return currentPath === '/' || currentPath === '';
            }
            return currentPath.startsWith(page);
        });
    }

    function initModal(modalId, config) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        const shouldShowOnPage = checkCurrentPage(config.pages);
        
        if (shouldShowOnPage && !getCookie(config.cookieName)) {
            setTimeout(() => {
                modal.style.display = 'flex';
                setTimeout(() => {
                    modal.classList.add('active');
                    
                    if (config.hasSlides) {
                        initSlides();
                    }
                    
                }, 10);
            }, config.delay || 500);
            
            const closeBtn = modal.querySelector('.close');
            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    closeModal(modal);
                });
            }
            
            

            const dontShowAgainBtn = modal.querySelector('.close');
            if (dontShowAgainBtn) {
                dontShowAgainBtn.addEventListener('click', function() {
                    setCookie(config.cookieName, 'shown', COOKIE_DAYS);
                    closeModal(modal);
                });
            }
        }
    }
    
    function closeModal(modal) {
        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 400);
    }

    function initSlides(modalId = null) {
        const container = modalId ? document.getElementById(modalId) : document;
        const slides = container.querySelectorAll('.modal-slide');
        const prevBtn = container.querySelector('.slide-prev-vertical');
        const nextBtn = container.querySelector('.slide-next-vertical');
        
        if (!slides.length) return;
        
        let currentSlide = 0;
        
        function showSlide(index) {
            slides.forEach(slide => slide.classList.remove('active'));
            slides[index].classList.add('active');
            
            updateSlideCounter(index + 1, slides.length);
            
            currentSlide = index;
        }
        
        function updateSlideCounter(current, total) {
            const activeSlide = slides[current - 1];
            if (activeSlide) {
                const counter = activeSlide.querySelector('.slide-counter');
                if (counter) {
                    counter.textContent = `${current}/${total}`;
                }
            }
        }
        
        function nextSlide() {
            currentSlide = (currentSlide + 1) % slides.length;
            showSlide(currentSlide);
        }
        
        function prevSlide() {
            currentSlide = (currentSlide - 1 + slides.length) % slides.length;
            showSlide(currentSlide);
        }
        
        if (prevBtn) {
            prevBtn.addEventListener('click', prevSlide);
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', nextSlide);
        }
        
        showSlide(0);
    }
    
    if (!getCookie(COOKIE_NAME)) {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            setTimeout(() => {
                banner.style.display = 'block';
                setTimeout(() => {
                    banner.classList.add('show');
                }, 10);
            }, 500);
            
            const acceptBtn = document.getElementById('accept-cookies');
            const declineBtn = document.getElementById('decline-cookies');
            
            if (acceptBtn) {
                acceptBtn.addEventListener('click', function() {
                    setCookie(COOKIE_NAME, 'accepted', COOKIE_DAYS);
                    banner.classList.remove('show');
                    setTimeout(() => {
                        banner.style.display = 'none';
                    }, 400);
                });
            }
            
            if (declineBtn) {
                declineBtn.addEventListener('click', function() {
                    banner.classList.remove('show');
                    setTimeout(() => {
                        banner.style.display = 'none';
                    }, 400);
                });
            }
        }
    }
    
    for (const [modalId, config] of Object.entries(MODAL_CONFIG)) {
        initModal(modalId, config);
    }
};

document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.initCookieBanner === 'function') {
        window.initCookieBanner();
    }
});