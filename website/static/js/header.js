let scrollTimeout;

function syncHeaderScrolled() {
    var header = document.querySelector('.fixed-header');
    if (!header) return;
    header.classList.toggle('scrolled', window.scrollY > 8);
}

window.addEventListener('scroll', function() {
    if (scrollTimeout) return;
    scrollTimeout = setTimeout(function() {
        syncHeaderScrolled();
        scrollTimeout = null;
    }, 10);
}, { passive: true });

window.addEventListener('resize', function() {
    clearTimeout(window.resizeTimeout);
    window.resizeTimeout = setTimeout(syncHeaderScrolled, 100);
});

document.addEventListener('DOMContentLoaded', syncHeaderScrolled);

function navigateToSection(sectionId) {
    const currentPath = window.location.pathname;
    const isHomePage = currentPath === '/' || currentPath === '';
    
    if (isHomePage) {
        const section = document.getElementById(sectionId);
        if (section) {
            setTimeout(() => {
                const headerOffset = 80;
                const elementPosition = section.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
            }, 100);
        }
    } else {
        window.location.href = '/';
        
        sessionStorage.setItem('scrollToSection', sectionId);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const sectionId = sessionStorage.getItem('scrollToSection');
    
    if (sectionId) {
        sessionStorage.removeItem('scrollToSection');
        
        const findAndScroll = (attempts = 0) => {
            const section = document.getElementById(sectionId);
            
            if (section) {
                const headerOffset = 80;
                const elementPosition = section.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            } else if (attempts < 20) {
                setTimeout(() => findAndScroll(attempts + 1), 200);
            }
        };
        
        setTimeout(() => findAndScroll(), 300);
    }
    
    if (window.location.hash) {
        const hashId = window.location.hash.substring(1);
        const section = document.getElementById(hashId);
        
        if (section) {
            setTimeout(() => {
                const headerOffset = 80;
                const elementPosition = section.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
            }, 500);
        }
    }
});