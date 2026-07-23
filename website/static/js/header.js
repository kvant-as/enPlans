window.addEventListener('scroll', () => {
    const header = document.querySelector('.fixed-header');
    header.classList.toggle('bubble', window.scrollY > 50);
});

window.addEventListener('resize', () => {
    const header = document.querySelector('.fixed-header');
    if (window.innerWidth <= 768) {
        header.classList.toggle('bubble', window.scrollY > 50);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const lenis = new Lenis({
        duration: 0.8,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 2,
    });

    function raf(time) {
        lenis.raf(time);
        requestAnimationFrame(raf);
    }

    requestAnimationFrame(raf);

    // document.querySelectorAll('.table-container, .main-table, .modal-table-conteiner').forEach(el => {
    //     el.addEventListener('wheel', (e) => {
    //         e.stopPropagation();
    //     }, { passive: true });
    // });

    document.querySelectorAll('.modal-table-conteiner', '.stat-log-textarea').forEach(el => {
        el.addEventListener('wheel', (e) => {
            e.stopPropagation();
        }, { passive: true });
    });

    window.addEventListener('scroll', () => {
        const header = document.querySelector('.fixed-header');
        const scrollY = window.scrollY;
        const threshold = 50;
        
        if (!window._scrollTicking) {
            window.requestAnimationFrame(() => {
                if (scrollY > threshold) {
                    header.classList.add('bubble');
                } else {
                    header.classList.remove('bubble');
                }
                window._scrollTicking = false;
            });
            window._scrollTicking = true;
        }
    });
});

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