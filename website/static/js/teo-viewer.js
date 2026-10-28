// Просмотр файла ТЭО прямо на странице — боковая панель (drawer),
// открывающаяся справа, по образцу панели просмотра файлов в Claude Code:
// тёмный хедер с именем файла и бейджем формата, спиннер загрузки, затем
// содержимое. .pdf показывается во встроенном iframe, .docx рендерится в
// HTML на клиенте через mammoth.js (как настоящий документ, а не просто
// ссылка на скачивание); для .doc (старый бинарный формат, который mammoth
// не поддерживает) и на случай ошибки конвертации — понятное сообщение и
// кнопка скачивания.
(function () {
    let requestToken = 0;

    function buildDrawer() {
        const drawer = document.createElement('div');
        drawer.id = 'teoViewerDrawer';
        drawer.className = 'teo-viewer-drawer';
        drawer.innerHTML = `
            <div class="teo-viewer-overlay" data-action="teo-close"></div>
            <div class="teo-viewer-panel">
                <div class="teo-viewer-header">
                    <div class="teo-viewer-title-group">
                        <span class="teo-viewer-title" id="teoViewerTitle"></span>
                        <span class="teo-viewer-badge" id="teoViewerBadge"></span>
                    </div>
                    <div class="teo-viewer-actions">
                        <a class="teo-viewer-action-btn" id="teoViewerDownload" title="Скачать">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                                <path d="M12 3V16M12 16L9 13M12 16L15 13"/>
                                <path d="M5 17V18C5 19.1046 5.89543 20 7 20H17C18.1046 20 19 19.1046 19 18V17"/>
                            </svg>
                        </a>
                        <button type="button" class="teo-viewer-action-btn" id="teoViewerExpand" title="На весь экран">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                            </svg>
                        </button>
                        <button type="button" class="teo-viewer-action-btn teo-viewer-close" data-action="teo-close" aria-label="Закрыть">&times;</button>
                    </div>
                </div>
                <div class="teo-viewer-body">
                    <div class="teo-viewer-loading" id="teoViewerLoading">
                        <div class="loading-spinner"></div>
                    </div>
                    <iframe id="teoViewerFrame" class="teo-viewer-frame" style="display:none;"></iframe>
                    <div class="teo-viewer-docx-page" id="teoViewerDocx" style="display:none;"></div>
                    <div class="teo-viewer-fallback" id="teoViewerFallback" style="display:none;">
                        <p id="teoViewerFallbackText">Предпросмотр для этого формата файла недоступен в браузере.</p>
                        <a class="main-btn main-btn-primary" id="teoViewerFallbackDownload">Скачать файл</a>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(drawer);

        drawer.querySelectorAll('[data-action="teo-close"]').forEach((el) => {
            el.addEventListener('click', close);
        });

        document.getElementById('teoViewerExpand').addEventListener('click', () => {
            drawer.classList.toggle('teo-viewer-fullscreen');
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && drawer.classList.contains('active')) close();
        });

        return drawer;
    }

    function close() {
        const drawer = document.getElementById('teoViewerDrawer');
        if (!drawer) return;
        drawer.classList.remove('active');
        drawer.classList.remove('teo-viewer-fullscreen');
        const frame = document.getElementById('teoViewerFrame');
        if (frame) frame.src = 'about:blank';
        requestToken += 1;
    }

    function showLoading() {
        document.getElementById('teoViewerLoading').style.display = 'flex';
        document.getElementById('teoViewerFrame').style.display = 'none';
        document.getElementById('teoViewerDocx').style.display = 'none';
        document.getElementById('teoViewerFallback').style.display = 'none';
    }

    function showFallback(message, downloadUrl) {
        document.getElementById('teoViewerLoading').style.display = 'none';
        document.getElementById('teoViewerFrame').style.display = 'none';
        document.getElementById('teoViewerDocx').style.display = 'none';
        const fallback = document.getElementById('teoViewerFallback');
        fallback.style.display = 'flex';
        document.getElementById('teoViewerFallbackText').textContent = message;
        document.getElementById('teoViewerFallbackDownload').href = downloadUrl;
    }

    async function renderDocx(viewUrl, downloadUrl, token) {
        if (typeof mammoth === 'undefined') {
            showFallback('Не удалось загрузить модуль просмотра документов.', downloadUrl);
            return;
        }
        try {
            const response = await fetch(viewUrl);
            if (!response.ok) throw new Error('fetch failed');
            const arrayBuffer = await response.arrayBuffer();
            if (token !== requestToken) return;

            const result = await mammoth.convertToHtml({ arrayBuffer });
            if (token !== requestToken) return;

            const docxContainer = document.getElementById('teoViewerDocx');
            docxContainer.innerHTML = result.value || '<p><em>Документ пуст</em></p>';

            document.getElementById('teoViewerLoading').style.display = 'none';
            document.getElementById('teoViewerFallback').style.display = 'none';
            docxContainer.style.display = 'block';
        } catch (e) {
            console.error('[TeoViewer] docx render error', e);
            if (token !== requestToken) return;
            showFallback('Не удалось отобразить предпросмотр документа. Попробуйте скачать файл.', downloadUrl);
        }
    }

    function renderPdf(viewUrl, downloadUrl, token) {
        const frame = document.getElementById('teoViewerFrame');

        frame.onload = () => {
            if (token !== requestToken) return;
            document.getElementById('teoViewerLoading').style.display = 'none';
        };
        frame.onerror = () => {
            if (token !== requestToken) return;
            showFallback('Не удалось отобразить PDF. Попробуйте скачать файл.', downloadUrl);
        };

        frame.src = viewUrl;
        frame.style.display = 'block';
    }

    function open(eventId, originalName, explicitViewUrl) {
        if (!eventId && !explicitViewUrl) return;
        const drawer = document.getElementById('teoViewerDrawer') || buildDrawer();
        const token = ++requestToken;

        const viewUrl = explicitViewUrl || `/plans/plan/event/${eventId}/teo`;
        const downloadUrl = `${viewUrl}${viewUrl.includes('?') ? '&' : '?'}download=1`;
        const ext = (originalName || '').split('.').pop().toLowerCase();

        document.getElementById('teoViewerTitle').textContent = originalName || 'ТЭО';
        document.getElementById('teoViewerBadge').textContent = ext.toUpperCase();
        document.getElementById('teoViewerDownload').href = downloadUrl;

        drawer.classList.add('active');
        showLoading();

        if (ext === 'pdf') {
            renderPdf(viewUrl, downloadUrl, token);
        } else if (ext === 'docx') {
            renderDocx(viewUrl, downloadUrl, token);
        } else {
            showFallback('Предпросмотр для формата .doc недоступен в браузере — откройте файл после скачивания.', downloadUrl);
        }
    }

    window.TeoViewer = { open, close };
})();
