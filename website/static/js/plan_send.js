/* Страница «Отправка плана на рассмотрение» — перенесена сюда из модального
 * окна (раньше SendModalPreview в plan.js). Логика шагов 1-2 (выбор
 * согласующих/утверждающего) и предпросмотра пути согласования перенесена
 * почти без изменений; добавлен отдельный шаг предпросмотра (3) перед
 * шагом проверки ЭЦП (4) — сама проверка там сейчас чисто демонстрационная
 * (см. EcpMockModal, static/js/ecp-mock-modal.js), реальной серверной
 * валидации пока нет (функция в разработке).
 */
class PlanSendWizard {
    constructor(rootId) {
        this.root = document.getElementById(rootId);
        if (!this.root) {
            console.error('[PlanSendWizard] Root element not found:', rootId);
            return;
        }

        this.progressBar = this.root.querySelector('#modal-progress-bar');
        this.stepEls = Array.from(this.root.querySelectorAll('[id^="step"]'))
            .filter(el => /^step\d+$/.test(el.id))
            .sort((a, b) => parseInt(a.id.slice(4), 10) - parseInt(b.id.slice(4), 10));

        this.totalSteps = this.stepEls.length || 1;
        this.currentStep = 1;

        this.stepperDots = Array.from(document.querySelectorAll('#planSendStepper .plan-send-step-dot'));

        this.selectedCoordinators = new Map();
        this.selectedApprover = null;

        this.coordinatorSearch = this.root.querySelector('#coordinator-search');
        this.approverSearch = this.root.querySelector('#approver-search');
        this.coordinatorTbody = this.root.querySelector('#coordinator-tbody');
        this.approverTbody = this.root.querySelector('#approver-tbody');
        this.selectedCoordinatorsContainer = this.root.querySelector('#selected-coordinators');
        this.selectedApproverContainer = this.root.querySelector('#selected-approver');
        this.coordinatorIdsInput = this.root.querySelector('#coordinator-ids-input');
        this.approverIdInput = this.root.querySelector('#approver-id-input');
        this.coordinatorCount = this.root.querySelector('#coordinator-count');
        this.approverCount = this.root.querySelector('#approver-count');
        this.approvalSliderContainer = this.root.querySelector('#approval-slider-container');

        this.buttons = {
            step1Next: this.root.querySelector('#step1-next-btn'),
            step2Back: this.root.querySelector('#step2-back-btn'),
            step2Next: this.root.querySelector('#step2-next-btn'),
            step3Back: this.root.querySelector('#step3-back-btn'),
            step3Next: this.root.querySelector('#step3-next-btn'),
            step4Back: this.root.querySelector('#step4-back-btn'),
        };

        this.submitButton = this.root.querySelector('#submit-sent-button');

        this.coordinatorPage = 1;
        this.approverPage = 1;
        this.coordinatorHasMore = true;
        this.approverHasMore = true;
        this.coordinatorLoading = false;
        this.approverLoading = false;
        this.coordinatorSearchQuery = '';
        this.approverSearchQuery = '';
        this.coordinatorSearchTimeout = null;
        this.approverSearchTimeout = null;

        this.coordinatorSort = { field: null, dir: 'asc' };
        this.approverSort = { field: null, dir: 'asc' };

        this.regionNumber = window.regionNumber || '';
        this.regionNames = {
            1: 'Брестское областное управление по надзору за рациональным использованием ТЭР',
            2: 'Витебское областное управление по надзору за рациональным использованием ТЭР',
            3: 'Гомельское областное управление по надзору за рациональным использованием ТЭР',
            4: 'Гродненское областное управление по надзору за рациональным использованием ТЭР',
            5: 'Управление г. Минск по надзору за рациональным использованием ТЭР',
            6: 'Минское областное управление по надзору за рациональным использованием ТЭР',
            7: 'Могилевское областное управление по надзору за рациональным использованием ТЭР'
        };

        this.init();
        this.updateButtonsState();
        this.updateStepper();
    }

    init() {
        this.loadCoordinators();
        this.loadApprovers();
        this.initSearch();
        this.initNavigation();
        this.initScrollLoading();
        this.initSliderDrag();
        this.initSort();
        this.updateButtonsState();
    }

    initSort() {
        this.initPickerSort(this.root.querySelector('#step1 .org-picker-toolbar'), this.coordinatorSort, () => this.loadCoordinators(true));
        this.initPickerSort(this.root.querySelector('#step2 .org-picker-toolbar'), this.approverSort, () => this.loadApprovers(true));
    }

    // Панель "Сортировать: По названию / По УНП" над списком — раньше это
    // были кликабельные заголовки таблицы, теперь список организаций не
    // таблица, а карточки (см. renderOrganizations), поэтому сортировка
    // вынесена в отдельную панель кнопок.
    initPickerSort(toolbar, sortState, reload) {
        if (!toolbar) return;
        const buttons = Array.from(toolbar.querySelectorAll('.org-picker-sort-btn'));

        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const field = btn.dataset.field;
                const direction = sortState.field === field && sortState.dir === 'asc' ? 'desc' : 'asc';
                sortState.field = field;
                sortState.dir = direction;

                buttons.forEach((b) => b.classList.remove('org-picker-sort-btn--active', 'org-picker-sort-btn--desc'));
                btn.classList.add('org-picker-sort-btn--active');
                if (direction === 'desc') btn.classList.add('org-picker-sort-btn--desc');

                reload();
            });
        });
    }

    buildSortParams(sortState) {
        if (!sortState || !sortState.field) return '';
        return `&sort=${encodeURIComponent(sortState.field)}&order=${sortState.dir}`;
    }

    async loadCoordinators(reset = true) {
        if (this.coordinatorLoading) return;

        if (reset) {
            this.coordinatorPage = 1;
            this.coordinatorHasMore = true;
            this.coordinatorTbody.innerHTML = '';
            this.coordinatorTbody.scrollTop = 0;
        }

        if (!this.coordinatorHasMore) {
            this.removeLoading(this.coordinatorTbody);
            return;
        }

        this.coordinatorLoading = true;
        this.showLoading(this.coordinatorTbody);

        try {
            const url = `/api/organizations?type=auditor&page=${this.coordinatorPage}&per_page=10&q=${encodeURIComponent(this.coordinatorSearchQuery)}&hide_rm=true${this.buildSortParams(this.coordinatorSort)}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading coordinators:', data.error);
                this.coordinatorLoading = false;
                this.removeLoading(this.coordinatorTbody);
                return;
            }

            this.removeLoading(this.coordinatorTbody);

            if (data.organizations && data.organizations.length > 0) {
                this.renderOrganizations(this.coordinatorTbody, data.organizations, 'coordinator');
            } else if (reset) {
                this.showEmptyMessage(this.coordinatorTbody);
            }

            this.coordinatorHasMore = data.has_next || false;
            this.coordinatorPage = data.page + 1;
        } catch (error) {
            console.error('Error loading coordinators:', error);
            this.removeLoading(this.coordinatorTbody);
        } finally {
            this.coordinatorLoading = false;
        }
    }

    async loadApprovers(reset = true) {
        if (this.approverLoading) return;

        if (reset) {
            this.approverPage = 1;
            this.approverHasMore = true;
            this.approverTbody.innerHTML = '';
            this.approverTbody.scrollTop = 0;
        }

        if (!this.approverHasMore) {
            this.removeLoading(this.approverTbody);
            return;
        }

        this.approverLoading = true;
        this.showLoading(this.approverTbody);

        try {
            const url = `/api/organizations?type=approver&page=${this.approverPage}&per_page=10&q=${encodeURIComponent(this.approverSearchQuery)}${this.buildSortParams(this.approverSort)}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading approvers:', data.error);
                this.approverLoading = false;
                this.removeLoading(this.approverTbody);
                return;
            }

            this.removeLoading(this.approverTbody);

            if (data.organizations && data.organizations.length > 0) {
                this.renderOrganizations(this.approverTbody, data.organizations, 'approver');
            } else if (reset) {
                this.showEmptyMessage(this.approverTbody);
            }

            this.approverHasMore = data.has_next || false;
            this.approverPage = data.page + 1;
        } catch (error) {
            console.error('Error loading approvers:', error);
            this.removeLoading(this.approverTbody);
        } finally {
            this.approverLoading = false;
        }
    }

    renderOrganizations(tbody, organizations, type) {
        if (!tbody) return;
        if (!organizations || organizations.length === 0) return;

        organizations.forEach(org => {
            const isCoordinator = type === 'coordinator';
            const checkboxType = isCoordinator ? 'coordinator-checkbox' : 'approver-checkbox';
            const isChecked = isCoordinator ? this.selectedCoordinators.has(String(org.id)) : this.selectedApprover === String(org.id);

            // <label> оборачивает чекбокс — клик по всей карточке уже
            // переключает выбор нативно, без ручной обработки клика мимо
            // инпута (как было раньше с <tr>).
            const row = document.createElement('label');
            row.className = 'org-picker-row';
            row.dataset.id = org.id;
            row.dataset.name = org.name;
            row.innerHTML = `
                <input type="checkbox" class="${checkboxType}" value="${org.id}" data-name="${this.escapeHtml(org.name)}" ${isChecked ? 'checked' : ''}>
                <span class="org-picker-check"></span>
                <span class="org-picker-info">
                    <span class="org-picker-name">${this.escapeHtml(org.name)}</span>
                    <span class="org-picker-meta">
                        ${org.ynp ? `<span class="org-picker-meta-item">УНП ${this.escapeHtml(org.ynp)}</span>` : ''}
                        ${org.okpo ? `<span class="org-picker-meta-item">ОКПО ${this.escapeHtml(org.okpo)}</span>` : ''}
                        ${org.region ? `<span class="org-picker-meta-item">${this.escapeHtml(org.region)}</span>` : ''}
                    </span>
                </span>
            `;

            if (isChecked) row.classList.add('active-row');
            tbody.appendChild(row);

            if (isCoordinator) {
                this.initCoordinatorRow(row, row.querySelector('.coordinator-checkbox'));
            } else {
                this.initApproverRow(row, row.querySelector('.approver-checkbox'));
            }
        });
    }

    initCoordinatorRow(row, checkbox) {
        if (!checkbox) return;

        checkbox.addEventListener('change', (e) => {
            const id = e.target.value;
            const name = e.target.dataset.name;
            if (e.target.checked) {
                this.selectedCoordinators.set(id, name);
                row.classList.add('active-row');
            } else {
                this.selectedCoordinators.delete(id);
                row.classList.remove('active-row');
            }
            this.updateSelectedCoordinators();
            this.updateButtonsState();
            this.updateApprovalPath();
        });
    }

    initApproverRow(row, checkbox) {
        if (!checkbox) return;

        // Чекбокс визуально выглядит как радио (org-picker-list--radio,
        // см. CSS) — переключаем в change остальные, чтобы фактически
        // работал как единственный выбор.
        checkbox.addEventListener('change', (e) => {
            const id = e.target.value;

            if (e.target.checked) {
                this.approverTbody.querySelectorAll('.org-picker-row').forEach(r => {
                    const cb = r.querySelector('.approver-checkbox');
                    if (cb && cb !== e.target) {
                        cb.checked = false;
                        r.classList.remove('active-row');
                    }
                });
                this.selectedApprover = id;
                row.classList.add('active-row');
            } else {
                this.selectedApprover = null;
                row.classList.remove('active-row');
            }

            this.updateSelectedApprover();
            this.updateButtonsState();
            this.updateApprovalPath();
        });
    }

    showLoading(list) {
        if (!list) return;
        let loadingRow = list.querySelector('.org-picker-loading-row');
        if (!loadingRow) {
            loadingRow = document.createElement('div');
            loadingRow.className = 'org-picker-loading-row';
            loadingRow.innerHTML = `<span class="loading-spinner"></span> Загрузка...`;
            list.appendChild(loadingRow);
        }
        loadingRow.style.display = '';
    }

    removeLoading(list) {
        if (!list) return;
        const loadingRow = list.querySelector('.org-picker-loading-row');
        if (loadingRow) loadingRow.remove();
    }

    showEmptyMessage(list) {
        if (!list) return;
        if (list.querySelector('.org-picker-empty-row')) return;

        const row = document.createElement('div');
        row.className = 'org-picker-empty-row';
        row.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="10.5" cy="10.5" r="6.5"></circle>
                <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                <line x1="8" y1="10.5" x2="13" y2="10.5"></line>
            </svg>
            <span>Организация не найдена</span>
        `;
        list.appendChild(row);
    }

    initScrollLoading() {
        if (this.coordinatorTbody) {
            this.coordinatorTbody.addEventListener('scroll', (e) => {
                const c = e.target;
                if (c.scrollTop + c.clientHeight >= c.scrollHeight - 50 && !this.coordinatorLoading && this.coordinatorHasMore) {
                    this.loadCoordinators(false);
                }
            });
        }

        if (this.approverTbody) {
            this.approverTbody.addEventListener('scroll', (e) => {
                const c = e.target;
                if (c.scrollTop + c.clientHeight >= c.scrollHeight - 50 && !this.approverLoading && this.approverHasMore) {
                    this.loadApprovers(false);
                }
            });
        }
    }

    initSliderDrag() {
        const container = this.approvalSliderContainer;
        if (!container) return;

        let isDown = false;
        let startX = 0;
        let scrollLeft = 0;

        container.addEventListener('mousedown', (e) => {
            isDown = true;
            container.style.cursor = 'grabbing';
            startX = e.pageX - container.offsetLeft;
            scrollLeft = container.scrollLeft;
            container.style.userSelect = 'none';
        });

        container.addEventListener('mouseleave', () => {
            if (isDown) {
                isDown = false;
                container.style.cursor = 'grab';
                container.style.userSelect = '';
            }
        });

        container.addEventListener('mouseup', () => {
            isDown = false;
            container.style.cursor = 'grab';
            container.style.userSelect = '';
        });

        container.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - container.offsetLeft;
            const walk = (x - startX) * 1.5;
            container.scrollLeft = scrollLeft - walk;
        });

        let touchStartX = 0;
        let touchScrollLeft = 0;

        container.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].pageX - container.offsetLeft;
            touchScrollLeft = container.scrollLeft;
        });

        container.addEventListener('touchmove', (e) => {
            const x = e.touches[0].pageX - container.offsetLeft;
            const walk = (x - touchStartX) * 1.5;
            container.scrollLeft = touchScrollLeft - walk;
        });
    }

    initSearch() {
        if (this.coordinatorSearch) {
            this.coordinatorSearch.addEventListener('input', (e) => {
                clearTimeout(this.coordinatorSearchTimeout);
                this.coordinatorSearchTimeout = setTimeout(() => {
                    const newQuery = e.target.value.trim();
                    if (newQuery !== this.coordinatorSearchQuery) {
                        this.coordinatorSearchQuery = newQuery;
                        this.coordinatorHasMore = true;
                        this.loadCoordinators(true);
                    }
                }, 300);
            });
        }

        if (this.approverSearch) {
            this.approverSearch.addEventListener('input', (e) => {
                clearTimeout(this.approverSearchTimeout);
                this.approverSearchTimeout = setTimeout(() => {
                    const newQuery = e.target.value.trim();
                    if (newQuery !== this.approverSearchQuery) {
                        this.approverSearchQuery = newQuery;
                        this.approverHasMore = true;
                        this.loadApprovers(true);
                    }
                }, 300);
            });
        }
    }

    initNavigation() {
        this.buttons.step1Next?.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.validateStep1()) this.nextStep();
        });

        this.buttons.step2Back?.addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        this.buttons.step2Next?.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.validateStep2()) this.nextStep();
        });

        this.buttons.step3Back?.addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        // Шаг 3 — предпросмотр финальных этапов (путь согласования),
        // "Далее" просто переходит к последнему шагу с сертификатом.
        this.buttons.step3Next?.addEventListener('click', (e) => {
            e.preventDefault();
            this.nextStep();
        });

        this.buttons.step4Back?.addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        this.root.querySelector('#sentForm')?.addEventListener('submit', () => {
            if (this.coordinatorIdsInput) {
                this.coordinatorIdsInput.value = Array.from(this.selectedCoordinators.keys()).join(',');
            }
            if (this.approverIdInput) {
                this.approverIdInput.value = this.selectedApprover;
            }
        });

        // Шаг 4 — кнопка "Отправить план" выключена, пока не пройдена
        // демонстрационная проверка ЭЦП в модалке (см. EcpMockModal,
        // static/js/ecp-mock-modal.js). Сама проверка пока чисто
        // визуальная — реального бэкенда у неё нет (функция в разработке).
        const openEcpCheckBtn = this.root.querySelector('#openEcpCheckBtn');
        const ecpCheckPromptTitle = this.root.querySelector('#ecpCheckPromptTitle');
        const ecpCheckPromptText = this.root.querySelector('#ecpCheckPromptText');
        const ecpKeyHero = this.root.querySelector('#ecpKeyHero');
        if (openEcpCheckBtn && window.EcpMockModal) {
            const ecpModal = new EcpMockModal({
                modalId: 'ecpMockModal',
                certCheckUrl: window.planToken ? `/plans/plan/verify-certificate/${window.planToken}` : null,
                onSuccess: () => {
                    // Модалка уже закрылась (EcpMockModal делает это сама перед
                    // вызовом onSuccess) — ключ слева перестаёт парить,
                    // опускается и слегка покачивается (ecpKeyDrop, ~0.6с —
                    // см. base.css), кнопка рядом плавно гаснет. После этого
                    // меняем текст рядом и разблокируем "Отправить план".
                    if (ecpKeyHero) ecpKeyHero.classList.add('is-open');
                    if (openEcpCheckBtn) openEcpCheckBtn.classList.add('is-done');
                    setTimeout(() => {
                        if (ecpCheckPromptTitle) ecpCheckPromptTitle.textContent = 'Проверка ЭЦП пройдена';
                        if (ecpCheckPromptText) ecpCheckPromptText.textContent = 'Теперь план можно отправить на согласование.';
                        const promptEl = this.root.querySelector('#ecpCheckPrompt');
                        if (promptEl) promptEl.classList.add('is-verified');
                        if (this.submitButton) this.submitButton.disabled = false;
                    }, 650);
                },
            });
            openEcpCheckBtn.addEventListener('click', () => ecpModal.open());
        }
    }

    updateSelectedCoordinators() {
        if (!this.selectedCoordinatorsContainer) return;
        const container = this.selectedCoordinatorsContainer;
        container.innerHTML = '';

        if (this.coordinatorCount) this.coordinatorCount.textContent = this.selectedCoordinators.size;

        if (this.selectedCoordinators.size === 0) {
            container.innerHTML = this.emptyMessageHtml();
            return;
        }

        let order = 0;
        this.selectedCoordinators.forEach((name, id) => {
            order += 1;
            const row = document.createElement('div');
            row.className = 'selected-org-row';
            row.innerHTML = `
                <span class="selected-org-order">${order}</span>
                <span class="selected-org-name">${this.escapeHtml(name)}</span>
                <button class="selected-org-remove" data-id="${id}" type="button" aria-label="Убрать">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `;
            row.querySelector('.selected-org-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                const checkbox = this.coordinatorTbody?.querySelector(`.coordinator-checkbox[value="${id}"]`);
                if (checkbox) {
                    checkbox.checked = false;
                    checkbox.dispatchEvent(new Event('change'));
                } else {
                    this.selectedCoordinators.delete(id);
                    this.updateSelectedCoordinators();
                    this.updateButtonsState();
                    this.updateApprovalPath();
                }
            });
            container.appendChild(row);
        });
    }

    updateSelectedApprover() {
        if (!this.selectedApproverContainer) return;
        const container = this.selectedApproverContainer;
        container.innerHTML = '';

        if (this.approverCount) this.approverCount.textContent = this.selectedApprover ? '1' : '0';

        if (!this.selectedApprover) {
            container.innerHTML = this.emptyMessageHtml();
            return;
        }

        const orgRow = this.approverTbody?.querySelector(`.org-picker-row[data-id="${this.selectedApprover}"]`);
        const name = orgRow ? orgRow.dataset.name : `ID: ${this.selectedApprover}`;
        const row = document.createElement('div');
        row.className = 'selected-org-row selected-org-row--approver';
        row.innerHTML = `
            <span class="selected-org-order selected-org-order--check">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </span>
            <span class="selected-org-name">${this.escapeHtml(name)}</span>
            <button class="selected-org-remove" data-id="${this.selectedApprover}" type="button" aria-label="Убрать">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        row.querySelector('.selected-org-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            const checkbox = this.approverTbody?.querySelector(`.approver-checkbox[value="${this.selectedApprover}"]`);
            if (checkbox) {
                checkbox.checked = false;
                checkbox.dispatchEvent(new Event('change'));
            }
        });
        container.appendChild(row);
    }

    updateApprovalPath() {
        const container = this.approvalSliderContainer;
        if (!container) return;

        const coordinators = [];
        const approver = this.selectedApprover;
        const regionName = this.regionNames[this.regionNumber] || 'Регион';

        this.selectedCoordinators.forEach((name) => coordinators.push(name));

        let approverName = '';
        if (approver) {
            const row = this.approverTbody?.querySelector(`.org-picker-row[data-id="${approver}"]`);
            if (row) approverName = row.dataset.name;
        }

        const allSteps = [regionName, ...coordinators];
        if (approverName) allSteps.push(approverName);

        if (allSteps.length === 1) {
            container.innerHTML = `
                <div class="approval-path-placeholder" style="text-align: center; padding: 20px; color: #999;">
                    Выберите организацию/и для отображения пути согласования
                </div>
            `;
            return;
        }

        const totalSteps = allSteps.length;

        const sliderDiv = document.createElement('div');
        sliderDiv.className = 'enplans-approval-slider';

        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'enplans-approval-slider-steps';

        allSteps.forEach((name, index) => {
            const isFirst = index === 0;
            const stepDiv = document.createElement('div');
            stepDiv.className = `enplans-approval-step ${isFirst ? 'active' : 'pending'}`;

            const iconDiv = document.createElement('div');
            iconDiv.className = 'enplans-approval-step-icon';
            iconDiv.innerHTML = this.getStepIcon(index, allSteps.length);
            stepDiv.appendChild(iconDiv);

            const nameDiv = document.createElement('div');
            nameDiv.className = 'enplans-approval-step-name';
            nameDiv.textContent = name;
            nameDiv.title = name;
            stepDiv.appendChild(nameDiv);

            const timeDiv = document.createElement('div');
            timeDiv.className = 'enplans-approval-step-time';
            timeDiv.textContent = 'Ожидает';
            stepDiv.appendChild(timeDiv);

            stepsDiv.appendChild(stepDiv);
        });

        sliderDiv.appendChild(stepsDiv);

        const progressContainer = document.createElement('div');
        progressContainer.className = 'enplans-approval-progress-container';
        const progressLine = document.createElement('div');
        progressLine.className = 'enplans-approval-progress-line';
        progressLine.style.width = '0%';
        progressContainer.appendChild(progressLine);
        sliderDiv.appendChild(progressContainer);

        const progressText = document.createElement('div');
        progressText.className = 'enplans-approval-progress-text';
        progressText.innerHTML = `<span>0 из ${totalSteps} этапов (0%)</span>`;
        sliderDiv.appendChild(progressText);

        container.innerHTML = '';
        container.appendChild(sliderDiv);
    }

    getStepIcon(index, total) {
        const isFirst = index === 0;
        const isLast = index === total - 1;
        if (isFirst) return window.icons.icon_region;
        if (isLast) return window.icons.icon_higher;
        return window.icons.icon_municipal;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    emptyMessageHtml() {
        return `
            <div class="empty-message">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="4" y="3" width="16" height="18" rx="1"></rect>
                    <line x1="8" y1="7.5" x2="8" y2="7.5"></line>
                    <line x1="12" y1="7.5" x2="12" y2="7.5"></line>
                    <line x1="16" y1="7.5" x2="16" y2="7.5"></line>
                    <line x1="8" y1="11.5" x2="8" y2="11.5"></line>
                    <line x1="12" y1="11.5" x2="12" y2="11.5"></line>
                    <line x1="16" y1="11.5" x2="16" y2="11.5"></line>
                    <path d="M9 21v-6h6v6"></path>
                </svg>
                <span>Ничего не выбрано</span>
            </div>
        `;
    }

    activeStepEl() {
        return this.stepEls[this.currentStep - 1];
    }

    updateProgressBar() {
        if (!this.progressBar) return;
        this.progressBar.style.width = (this.currentStep / this.totalSteps) * 100 + '%';
    }

    updateStepper() {
        this.stepperDots.forEach((dot) => {
            const step = parseInt(dot.dataset.step, 10);
            dot.classList.remove('active', 'completed');
            if (step < this.currentStep) dot.classList.add('completed');
            else if (step === this.currentStep) dot.classList.add('active');
        });
    }

    nextStep() {
        if (this.currentStep >= this.totalSteps) return;
        this.activeStepEl().style.display = 'none';
        this.currentStep++;
        this.activeStepEl().style.display = 'block';
        this.updateProgressBar();
        this.updateStepper();
        this.updateButtonsState();

        if (this.currentStep === 2) {
            const rows = this.approverTbody?.querySelectorAll('.org-picker-row') || [];
            if (rows.length === 0) {
                this.approverHasMore = true;
                this.loadApprovers(true);
            }
        }

        if (this.currentStep === 3) {
            this.updateApprovalPath();
            setTimeout(() => this.initSliderDrag(), 100);
        }
    }

    prevStep() {
        if (this.currentStep <= 1) return;
        this.activeStepEl().style.display = 'none';
        this.currentStep--;
        this.activeStepEl().style.display = 'block';
        this.updateProgressBar();
        this.updateStepper();
        this.updateButtonsState();
    }

    updateButtonsState() {
        // Шаг 1 (согласующие) необязателен: региональное управление и так
        // добавляется в путь согласования автоматически (см.
        // handle_sent_status на бэкенде), поэтому пользователь может сразу
        // перейти к выбору утверждающей организации, ничего не отмечая здесь.
        if (this.buttons.step1Next) {
            this.buttons.step1Next.disabled = false;
        }
        if (this.buttons.step2Next) {
            this.buttons.step2Next.disabled = !this.selectedApprover;
        }
        // submitButton управляется отдельно — включается только когда
        // пройдена проверка ЭЦП в модалке (см. EcpMockModal в bindEvents()).
    }

    validateStep1() {
        // Согласующие организации необязательны — см. комментарий в
        // updateButtonsState(). Шаг нужен только тем, кому действительно
        // есть кого добавить помимо автоматического регионального управления.
        return true;
    }

    validateStep2() {
        if (!this.selectedApprover) {
            alert('Пожалуйста, выберите организацию для утверждения');
            return false;
        }
        return true;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('planSendRoot')) {
        window.planSendWizard = new PlanSendWizard('planSendRoot');
    }
});
