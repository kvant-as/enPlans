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

    document.querySelectorAll('.modal-table-conteiner').forEach(el => {
        el.addEventListener('wheel', (e) => {
            e.stopPropagation();
        }, { passive: true });
    });

    window.addEventListener('scroll', () => {
        const header = document.querySelector('.fixed-header');
        header.classList.toggle('bubble', window.scrollY > 50);
    });
});