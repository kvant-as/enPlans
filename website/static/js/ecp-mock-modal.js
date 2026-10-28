/* Модалка-прототип "Проверка ЭЦП". Способ "Аппаратный ключ" остаётся
 * чисто визуальным макетом будущего функционала — реальной проверки нет.
 * Способ "Сертификат ЭЦП" теперь проверяется по-настоящему: если передан
 * certCheckUrl, файл уходит на сервер (website/ecp.py :: verify_certificate
 * через /plans/plan/verify-certificate/<token>), который сверяет срок
 * действия и логирует (DEBUG) всё, что удалось прочитать из сертификата.
 * Без certCheckUrl способ "Сертификат" откатывается на демо-режим (как
 * было раньше — любой файл считается действительным). Компонент
 * переиспользуемый: разметка — macros/components.html :: ecp_mock_modal(),
 * открывается через new EcpMockModal({modalId, certCheckUrl, onSuccess}).open().
 */
class EcpMockModal {
    constructor(options = {}) {
        this.modalId = options.modalId || 'ecpMockModal';
        this.modal = document.getElementById(this.modalId);
        this.onSuccess = typeof options.onSuccess === 'function' ? options.onSuccess : function () {};
        this.certCheckUrl = options.certCheckUrl || null;
        if (!this.modal) return;

        this.slides = Array.from(this.modal.querySelectorAll('[data-ecp-slide]'));
        this.backBtn = this.modal.querySelector('[data-ecp-back-btn]');
        this.closeBtn = this.modal.querySelector('.modal-header .close');
        this.overlayCloseEnabled = options.closeOnOverlay !== false;
        this.history = [];
        this.timers = [];

        this._bindChoiceSlide();
        this._bindKeySlide();
        this._bindCertSlide();
        this._bindBack();
        this._bindClose();
    }

    open() {
        if (!this.modal) return;
        this._clearTimers();
        this._resetCertSlide();
        this.history = [];
        this._showSlide('choice', false);
        this.modal.classList.add('active');
    }

    close() {
        if (!this.modal) return;
        this.modal.classList.remove('active');
        this._clearTimers();
    }

    _clearTimers() {
        this.timers.forEach((t) => clearTimeout(t));
        this.timers = [];
    }

    _setTimeout(fn, delay) {
        const id = setTimeout(fn, delay);
        this.timers.push(id);
        return id;
    }

    _showSlide(name, pushHistory = true) {
        if (pushHistory && this.history[this.history.length - 1] !== name) {
            this.history.push(name);
        }
        this.slides.forEach((s) => s.classList.toggle('active', s.dataset.ecpSlide === name));
        if (this.backBtn) {
            this.backBtn.style.display = this.history.length > 1 ? 'inline-flex' : 'none';
        }
    }

    _bindChoiceSlide() {
        this.modal.querySelectorAll('[data-ecp-method]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const method = btn.dataset.ecpMethod;
                if (method === 'key') {
                    this._showSlide('key');
                    this._runKeyAnimation();
                } else if (method === 'cert') {
                    this._showSlide('cert');
                }
            });
        });
    }

    _runKeyAnimation() {
        const statusEl = this.modal.querySelector('[data-ecp-key-status]');
        const stick = this.modal.querySelector('.ecp-key-stick');
        if (stick) {
            stick.classList.remove('inserted');
            // Перезапуск CSS-анимации при повторном открытии слайда.
            void stick.offsetWidth;
            stick.classList.add('inserted');
        }

        const steps = [
            { text: 'Подключите ключ ЭЦП к компьютеру…', delay: 0 },
            { text: 'Ключ обнаружен…', delay: 1500 },
            { text: 'Запуск программы подписи…', delay: 2700 },
            { text: 'Подпись подтверждена', delay: 3900 },
        ];
        steps.forEach(({ text, delay }) => {
            this._setTimeout(() => { if (statusEl) statusEl.textContent = text; }, delay);
        });
        this._setTimeout(() => this._succeed(), 4700);
    }

    _resetCertSlide() {
        const dropArea = this.modal.querySelector('[data-ecp-cert-drop]');
        const dropContainer = this.modal.querySelector('[data-ecp-cert-drop-container]');
        const fileInput = this.modal.querySelector('[data-ecp-cert-input]');
        const statusEl = this.modal.querySelector('[data-ecp-cert-status]');
        const checkBtn = this.modal.querySelector('[data-ecp-cert-check-btn]');
        const retryBtn = this.modal.querySelector('[data-ecp-cert-retry-btn]');
        const textElement = this.modal.querySelector('.drop-certificate-text');
        const keyAnimation = this.modal.querySelector('[data-ecp-cert-key-animation]');
        const keyStick = keyAnimation ? keyAnimation.querySelector('.ecp-key-stick') : null;

        if (fileInput) fileInput.value = '';
        if (dropArea) dropArea.classList.remove('has-file', 'drag-over');
        if (dropContainer) dropContainer.style.display = '';
        if (keyAnimation) {
            keyAnimation.style.display = 'none';
            keyAnimation.classList.remove('is-error');
        }
        if (keyStick) keyStick.classList.remove('inserted');
        if (statusEl) {
            statusEl.style.display = 'none';
            statusEl.textContent = '';
            statusEl.className = 'certificate-status';
        }
        if (checkBtn) {
            checkBtn.disabled = true;
            checkBtn.classList.remove('is-checking');
            checkBtn.style.display = '';
        }
        if (retryBtn) retryBtn.style.display = 'none';
        if (textElement) {
            textElement.innerHTML = 'Перетащите файл сертификата сюда или ' +
                '<label class="drop-certificate-label" data-ecp-cert-label>нажмите для выбора</label>';
        }
    }

    _bindKeySlide() {
        // Анимация запускается из _bindChoiceSlide при выборе способа —
        // отдельных обработчиков на самом слайде не требуется.
    }

    _bindCertSlide() {
        const dropArea = this.modal.querySelector('[data-ecp-cert-drop]');
        const dropContainer = this.modal.querySelector('[data-ecp-cert-drop-container]');
        const fileInput = this.modal.querySelector('[data-ecp-cert-input]');
        const statusEl = this.modal.querySelector('[data-ecp-cert-status]');
        const checkBtn = this.modal.querySelector('[data-ecp-cert-check-btn]');
        const retryBtn = this.modal.querySelector('[data-ecp-cert-retry-btn]');
        const keyAnimation = this.modal.querySelector('[data-ecp-cert-key-animation]');
        const keyStick = keyAnimation ? keyAnimation.querySelector('.ecp-key-stick') : null;
        if (!dropArea || !fileInput || !checkBtn) return;

        let hasFile = false;

        // Пока сертификат проверяется — вместо drop-зоны показываем
        // анимацию "ключ входит в компьютер" (та же, что у способа
        // "Аппаратный ключ", он просто пока заблокирован).
        const showCheckingAnimation = () => {
            if (dropContainer) dropContainer.style.display = 'none';
            if (keyAnimation) {
                keyAnimation.classList.remove('is-error');
                keyAnimation.style.display = 'flex';
                if (keyStick) {
                    keyStick.classList.remove('inserted');
                    void keyStick.offsetWidth;
                    keyStick.classList.add('inserted');
                }
            }
        };
        // Неудачная проверка — анимация не прячется, а застывает кадром
        // ошибки (красная подсветка + крестик), вместо кнопки "Проверить
        // ЭЦП" показывается "Попробовать ещё раз".
        const showErrorFrame = () => {
            if (keyAnimation) keyAnimation.classList.add('is-error');
            checkBtn.style.display = 'none';
            if (retryBtn) retryBtn.style.display = 'inline-flex';
        };
        // Полный сброс — после "Попробовать ещё раз" или при переоткрытии
        // модалки: прячем анимацию и кадр ошибки, возвращаем drop-зону.
        const resetToDropZone = () => {
            if (dropContainer) dropContainer.style.display = '';
            if (keyAnimation) {
                keyAnimation.style.display = 'none';
                keyAnimation.classList.remove('is-error');
            }
            if (keyStick) keyStick.classList.remove('inserted');
            checkBtn.style.display = '';
            if (retryBtn) retryBtn.style.display = 'none';
        };

        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                hasFile = false;
                fileInput.value = '';
                dropArea.classList.remove('has-file');
                const textElement = dropArea.querySelector('.drop-certificate-text');
                if (textElement) {
                    textElement.innerHTML = 'Перетащите файл сертификата сюда или ' +
                        '<label class="drop-certificate-label" data-ecp-cert-label>нажмите для выбора</label>';
                }
                if (statusEl) {
                    statusEl.style.display = 'none';
                    statusEl.textContent = '';
                    statusEl.className = 'certificate-status';
                }
                checkBtn.disabled = true;
                checkBtn.classList.remove('is-checking');
                resetToDropZone();
            });
        }

        const setFile = (file) => {
            if (!file) return;
            hasFile = true;
            checkBtn.disabled = false;
            const textElement = dropArea.querySelector('.drop-certificate-text');
            if (textElement) textElement.innerHTML = `<strong>${this._escapeHtml(file.name)}</strong>`;
            dropArea.classList.add('has-file');
        };

        dropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropArea.classList.add('drag-over');
        });
        dropArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropArea.classList.remove('drag-over');
        });
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                setFile(files[0]);
            }
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) setFile(e.target.files[0]);
        });
        dropArea.addEventListener('click', (e) => {
            if (e.target.closest('.certificate-status')) return;
            if (e.target === dropArea || e.target.closest('.drop-certificate-content')) {
                e.preventDefault();
                fileInput.click();
            }
        });

        checkBtn.addEventListener('click', async () => {
            if (!hasFile) return;
            checkBtn.disabled = true;
            checkBtn.classList.add('is-checking');
            statusEl.style.display = 'flex';
            statusEl.className = 'certificate-status certificate-status--pending';
            statusEl.textContent = 'Проверка сертификата…';
            showCheckingAnimation();

            if (!this.certCheckUrl) {
                // Нет URL для реальной проверки (модалка открыта без
                // certCheckUrl) — демонстрационный режим, любой файл
                // считается действительным.
                this._setTimeout(() => {
                    statusEl.className = 'certificate-status certificate-status--ok';
                    statusEl.textContent = 'Сертификат действителен';
                    this._setTimeout(() => this._succeed(), 700);
                }, 1800);
                return;
            }

            const file = fileInput.files[0];
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const formData = new FormData();
            formData.append('certificate', file);
            if (csrfToken) formData.append('csrf_token', csrfToken);

            // Сама проверка на сервере — доли секунды, но нарочно растягиваем
            // минимум до ~1.2с, чтобы пользователь успел увидеть, что
            // сертификат действительно проверяется, а не просто принимается.
            const minDuration = new Promise((resolve) => setTimeout(resolve, 1200));

            try {
                const [response] = await Promise.all([
                    fetch(this.certCheckUrl, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
                        body: formData,
                    }),
                    minDuration,
                ]);
                const data = await response.json();

                if (response.ok && data.valid) {
                    statusEl.className = 'certificate-status certificate-status--ok';
                    statusEl.textContent = 'Сертификат действителен';
                    this._setTimeout(() => this._succeed(), 700);
                } else {
                    showErrorFrame();
                    statusEl.className = 'certificate-status certificate-status--error';
                    statusEl.textContent = data.error || 'Сертификат не прошёл проверку.';
                    checkBtn.disabled = false;
                    checkBtn.classList.remove('is-checking');
                }
            } catch (error) {
                console.error('[EcpMockModal] certificate check error', error);
                showErrorFrame();
                statusEl.className = 'certificate-status certificate-status--error';
                statusEl.textContent = 'Не удалось проверить сертификат. Проверьте соединение.';
                checkBtn.disabled = false;
                checkBtn.classList.remove('is-checking');
            }
        });
    }

    _bindBack() {
        if (!this.backBtn) return;
        this.backBtn.addEventListener('click', () => {
            this._clearTimers();
            this.history.pop();
            const prev = this.history[this.history.length - 1] || 'choice';
            this._showSlide(prev, false);
        });
    }

    _bindClose() {
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
    }

    _succeed() {
        this._showSlide('success');
        this._setTimeout(() => {
            this.close();
            this.onSuccess();
        }, 1200);
    }

    _escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}

window.EcpMockModal = EcpMockModal;
