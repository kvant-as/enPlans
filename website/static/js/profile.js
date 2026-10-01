document.addEventListener('DOMContentLoaded', function() {
    const confirmInput = document.getElementById('confirm-email-field');
    const deleteProfileBtn = document.getElementById('deleteProfileBtn');
    const currentUserEmailElement = document.getElementById('current_user_email');
    const currentUserEmail = currentUserEmailElement ? currentUserEmailElement.value : '';
    
    if (confirmInput && deleteProfileBtn) {
        deleteProfileBtn.disabled = true;
        
        confirmInput.addEventListener('input', function() {
            const enteredEmail = this.value.trim();
            
            if (enteredEmail === currentUserEmail) {
                deleteProfileBtn.disabled = false;
                this.classList.remove('input-invalid');
                this.classList.add('input-valid');
            } else {
                deleteProfileBtn.disabled = true;
                this.classList.remove('input-valid');
                if (enteredEmail.length > 0) {
                    this.classList.add('input-invalid');
                } else {
                    this.classList.remove('input-invalid');
                }
            }
        });
    }
    
    if (document.getElementById('deleteProfileBtn')) {
        initConfirmModal({
            triggerId: 'deleteProfileBtn',
            formId: 'deleteProfile_form',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите удалить свой профиль в EnPlans?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    const profileTabs = document.getElementById('profileTabs');
    if (profileTabs) {
        const tabButtons = profileTabs.querySelectorAll('.profile-tab');
        const tabPanels = document.querySelectorAll('.profile-tab-panel');

        function activateTab(tabName) {
            tabButtons.forEach((btn) => {
                const isActive = btn.dataset.tab === tabName;
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            tabPanels.forEach((panel) => {
                panel.classList.toggle('active', panel.dataset.tabPanel === tabName);
            });
        }

        tabButtons.forEach((btn) => {
            btn.addEventListener('click', () => activateTab(btn.dataset.tab));
        });
    }

    initAccountVerification();
});

// Периодическая верификация аккаунта сертификатом ЭЦП (вкладка
// «Верификация» в профиле). Два шага, как на странице отправки плана
// (CertificateUploadHandler в plan_send.js): сначала файл проверяется
// (/account/verify-check, без записи в БД) с анимацией загрузки ~5с,
// затем появляется кнопка «Пройти верификацию», которая и выполняет
// само действие (/account/verify).
function initAccountVerification() {
    const dropArea = document.getElementById('verifyCertDropArea');
    const fileInput = document.getElementById('verifyCertInput');
    const statusEl = document.getElementById('verifyCertStatus');
    const badge = document.getElementById('verificationStatusBadge');
    const submitArea = document.getElementById('verifySubmitArea');
    const submitButton = document.getElementById('submitVerifyButton');

    if (!dropArea || !fileInput || !statusEl || !submitArea || !submitButton) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    let checkToken = 0;
    let checkedFile = null;

    function showStatus(message, kind, withSpinner) {
        statusEl.style.display = 'flex';
        statusEl.className = `certificate-status certificate-status--${kind}`;
        statusEl.innerHTML = withSpinner
            ? `<span class="loading-spinner"></span>${escapeHtml(message)}`
            : escapeHtml(message);
    }

    function showFileDisplay(fileName) {
        const textElement = dropArea.querySelector('.drop-certificate-text');
        if (textElement) textElement.innerHTML = `<strong>${escapeHtml(fileName)}</strong>`;
        dropArea.classList.add('has-file');
    }

    function resetFileDisplay() {
        const textElement = dropArea.querySelector('.drop-certificate-text');
        if (textElement) {
            textElement.innerHTML = 'Перетащите файл сертификата сюда или \n                <label for="verifyCertInput" class="drop-certificate-label">нажмите для выбора</label>';
        }
        dropArea.classList.remove('has-file');
    }

    function hideSubmitArea() {
        submitArea.classList.remove('show');
        submitArea.style.display = 'none';
        submitButton.classList.remove('is-checking');
        submitButton.disabled = false;
    }

    function showSubmitArea() {
        submitArea.style.display = 'flex';
        // classList.add в этом же тике схлопнет transition — браузер должен
        // сперва отрисовать стартовое (скрытое) состояние.
        requestAnimationFrame(() => submitArea.classList.add('show'));
    }

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function isValidFile(file) {
        return file.name.toLowerCase().endsWith('.cer');
    }

    async function checkCertificate(file) {
        hideSubmitArea();
        showStatus('Проверка сертификата…', 'pending', true);
        const myToken = ++checkToken;

        const formData = new FormData();
        formData.append('certificate', file);
        if (csrfToken) formData.append('csrf_token', csrfToken);

        // Намеренно растягиваем видимую проверку до ~5с — реальная проверка
        // занимает доли секунды, но пользователь должен успеть увидеть, что
        // сертификат действительно проверяется, а не просто принимается.
        const minDuration = new Promise((resolve) => setTimeout(resolve, 5000));

        try {
            const [response] = await Promise.all([
                fetch('/account/verify-check', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
                    body: formData,
                }),
                minDuration,
            ]);
            const data = await response.json();
            if (myToken !== checkToken) return;

            if (response.ok && data.valid) {
                checkedFile = file;
                showStatus('Сертификат действителен. Нажмите «Пройти верификацию», чтобы подтвердить.', 'ok');
                showSubmitArea();
            } else {
                checkedFile = null;
                showStatus(data.error || 'Сертификат не прошёл проверку.', 'error');
                resetFileDisplay();
            }
        } catch (error) {
            await minDuration;
            if (myToken !== checkToken) return;
            console.error('[AccountVerification] check error', error);
            checkedFile = null;
            showStatus('Не удалось проверить сертификат. Проверьте соединение и попробуйте снова.', 'error');
            resetFileDisplay();
        }
    }

    async function submitVerification() {
        if (!checkedFile) return;

        submitButton.disabled = true;
        submitButton.classList.add('is-checking');

        const formData = new FormData();
        formData.append('certificate', checkedFile);
        if (csrfToken) formData.append('csrf_token', csrfToken);

        try {
            const response = await fetch('/account/verify', {
                method: 'POST',
                credentials: 'same-origin',
                headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
                body: formData,
            });
            const data = await response.json();

            if (response.ok && data.success) {
                showStatus(`Аккаунт верифицирован до ${data.verified_until}.`, 'ok');
                if (badge) {
                    badge.textContent = `Верифицировано до ${data.verified_until}`;
                    badge.classList.remove('unverified');
                    badge.classList.add('verified');
                }
                hideSubmitArea();
                checkedFile = null;
            } else {
                showStatus(data.error || 'Не удалось подтвердить верификацию.', 'error');
                submitButton.classList.remove('is-checking');
                submitButton.disabled = false;
            }
        } catch (error) {
            console.error('[AccountVerification] submit error', error);
            showStatus('Не удалось отправить запрос. Проверьте соединение и попробуйте снова.', 'error');
            submitButton.classList.remove('is-checking');
            submitButton.disabled = false;
        }
    }

    function processFile(file) {
        if (!isValidFile(file)) {
            hideSubmitArea();
            showStatus('Неверный формат файла. Разрешены только файлы .cer', 'error');
            fileInput.value = '';
            resetFileDisplay();
            return;
        }
        showFileDisplay(file.name);
        checkCertificate(file);
    }

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
        if (files.length > 0) {
            fileInput.files = files;
            processFile(files[0]);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) processFile(e.target.files[0]);
    });
    dropArea.addEventListener('click', (e) => {
        // Кнопка и статус теперь лежат внутри .drop-certificate-content
        // (см. profile.html) — клик по ним не должен открывать выбор файла.
        if (e.target.closest('.verify-submit-area') || e.target.closest('.certificate-status')) {
            return;
        }
        if (e.target === dropArea || e.target.closest('.drop-certificate-content')) {
            e.preventDefault();
            fileInput.click();
        }
    });
    submitButton.addEventListener('click', (e) => {
        e.stopPropagation();
        submitVerification();
    });
}