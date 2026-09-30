document.addEventListener('DOMContentLoaded', function() {
    const questionLinks = document.querySelectorAll('.question-link-modern');
    const categoryHeaders = document.querySelectorAll('.category-header-modern');
    const answerSections = document.querySelectorAll('.answer-active-modern');
    const defaultView = document.getElementById('default-view');
    const searchInput = document.querySelector('.faq-search');

    categoryHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const category = this.parentElement;
            category.classList.toggle('active');
        });
    });

    const faqContent = document.querySelector('.faq-content-modern');
    function scrollToContentTop() {
        const target = faqContent || document.body;
        const headerOffset = 100;
        const top = target.getBoundingClientRect().top + window.pageYOffset - headerOffset;
        window.scrollTo({ top: Math.max(top, 0), behavior: 'smooth' });
    }

    questionLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            answerSections.forEach(section => section.classList.remove('show'));
            defaultView.style.display = 'none';
            const targetSection = document.getElementById(targetId);
            if (targetSection) targetSection.classList.add('show');
            questionLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            const category = this.closest('.category-modern');
            if (category) category.classList.add('active');
            history.pushState(null, null, `#${targetId}`);
            scrollToContentTop();
        });
    });

    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        let foundCount = 0;
        questionLinks.forEach(link => {
            const text = link.textContent.toLowerCase();
            if (text.includes(searchTerm) || searchTerm.length < 2) {
                link.style.display = 'flex';
                if (searchTerm.length >= 2 && text.includes(searchTerm)) {
                    link.style.background = 'rgba(0,0,0,0.05)';
                    foundCount++;
                    const category = link.closest('.category-modern');
                    if (category) category.classList.add('active');
                } else {
                    link.style.background = '';
                }
            } else {
                link.style.display = 'none';
            }
        });
        const oldInfo = document.querySelector('.search-results-info');
        if (oldInfo) oldInfo.remove();
        if (searchTerm.length >= 2) {
            const resultsInfo = document.createElement('div');
            resultsInfo.className = 'search-results-info';
            resultsInfo.innerHTML = `Найдено вопросов: <strong>${foundCount}</strong>`;
            searchInput.parentNode.appendChild(resultsInfo);
        }
    });

    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetLink = document.querySelector(`.question-link-modern[href="#${targetId}"]`);
            if (targetLink) targetLink.click();
        });
    });

    if (window.location.hash) {
        const hash = window.location.hash.substring(1);
        const targetLink = document.querySelector(`.question-link-modern[href="#${hash}"]`);
        if (targetLink) setTimeout(() => targetLink.click(), 100);
    }

    document.querySelectorAll('.faq-toc-link').forEach(link => {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href').substring(1);
            const targetEl = document.getElementById(targetId);
            if (!targetEl) return;
            e.preventDefault();
            const headerOffset = 90;
            const top = targetEl.getBoundingClientRect().top + window.pageYOffset - headerOffset;
            window.scrollTo({ top: Math.max(top, 0), behavior: 'smooth' });
            history.pushState(null, null, `#${targetId}`);
        });
    });

    document.querySelectorAll('.answer-text input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const label = this.parentElement;
            if (this.checked) {
                label.style.opacity = '0.6';
                label.style.textDecoration = 'line-through';
            } else {
                label.style.opacity = '1';
                label.style.textDecoration = 'none';
            }
        });
    });

    const lightbox = document.createElement('div');
    lightbox.className = 'faq-lightbox';
    lightbox.innerHTML = `
        <button type="button" class="faq-lightbox-close" aria-label="Закрыть">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
        <img class="faq-lightbox-img" src="" alt="">
    `;
    document.body.appendChild(lightbox);
    const lightboxImg = lightbox.querySelector('.faq-lightbox-img');
    const lightboxClose = lightbox.querySelector('.faq-lightbox-close');

    function openLightbox(img) {
        lightboxImg.src = img.src;
        lightboxImg.alt = img.alt || '';
        lightbox.classList.add('show');
        document.body.classList.add('faq-lightbox-open');
    }

    function closeLightbox() {
        lightbox.classList.remove('show');
        document.body.classList.remove('faq-lightbox-open');
        lightboxImg.src = '';
    }

    document.querySelectorAll('.faq-image').forEach(img => {
        img.addEventListener('click', () => openLightbox(img));
    });

    lightbox.addEventListener('click', function(e) {
        if (e.target === lightbox) closeLightbox();
    });
    lightboxClose.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && lightbox.classList.contains('show')) closeLightbox();
    });
});