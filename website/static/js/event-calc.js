class EventModalManager {
    constructor() {
        this.EditEventModal = document.getElementById('EditEventModal');
        this.AddEventModal = document.getElementById('AddEventModal');
        this.planUsdRate = null;
        this.costPerToeUsd = null;
        this.ratesLoaded = false;
        this.ratesLoading = false;
        this.debug = false;
        
        this.updateCalculations = this.updateCalculations.bind(this);
        this.onRowClick = this.onRowClick.bind(this);
        this.step2NextHandler = this.step2NextHandler.bind(this);
        this.step3BackHandler = this.step3BackHandler.bind(this);
        this.searchHandler = this.searchHandler.bind(this);
        this.directionRowClickHandler = this.directionRowClickHandler.bind(this);
        
        if (this.AddEventModal) {
            this.initAddEventModal();
        }
    }

    log(...args) {
        if (this.debug) {
            console.log('[EventModalManager]', ...args);
        }
    }

    formatNumber(value, decimalPlaces = 2) {
        if (isNaN(value) || value === null || value === '') {
            if (decimalPlaces === 0) return '0';
            if (decimalPlaces === 1) return '0,0';
            return '0,00';
        }
        if (decimalPlaces === 0) return Math.round(value).toString();
        if (decimalPlaces === 1) return value.toFixed(1).replace('.', ',');
        return value.toFixed(2).replace('.', ',');
    }

    parseNumber(value) {
        if (!value) return 0;
        const str = value.toString().trim();
        if (str === '') return 0;
        return parseFloat(str.replace(',', '.')) || 0;
    }

    getActiveRow() {
        let activeRow = document.querySelector('.rows .active-row');
        if (!activeRow) {
            const allRowsContainers = document.querySelectorAll('.rows');
            for (const container of allRowsContainers) {
                const row = container.querySelector('.active-row');
                if (row) {
                    activeRow = row;
                    break;
                }
            }
        }
        return activeRow;
    }

    getPlanToken() {
        const hiddenToken = document.getElementById('plan-token');
        if (hiddenToken && hiddenToken.value) {
            return hiddenToken.value;
        }

        const eventTable = document.getElementById('eventTable');
        if (eventTable && eventTable.dataset.token) {
            return eventTable.dataset.token;
        }

        const modalForm = document.querySelector('#AddEventModal form');
        if (modalForm) {
            const actionUrl = modalForm.getAttribute('action');
            if (actionUrl) {
                const match = actionUrl.match(/\/create-event\/([a-zA-Z0-9]+)/);
                if (match && match[1]) {
                    return match[1];
                }
            }
        }

        return null;
    }

    getPeriodNameByCode(code) {
        const names = {
            '0001': 'Январь-Март',
            '0002': 'Январь-Июнь',
            '0003': 'Январь-Сентябрь',
            '0004': 'Январь-Декабрь'
        };
        return names[code] || code;
    }

    displayRates(usdRate, costPerToe) {
        const usdDisplay = document.getElementById('usd-rate-display');
        const costDisplay = document.getElementById('cost-per-toe-display');
        const editUsdDisplay = document.getElementById('edit-usd-rate-display');
        const editCostDisplay = document.getElementById('edit-cost-per-toe-display');
        
        const displayValue = (element, value, isUsd = false) => {
            if (!element) return;
            if (value !== null && value !== undefined && value > 0) {
                if (isUsd) {
                    element.textContent = value.toFixed(4).replace('.', ',');
                } else {
                    element.textContent = value.toFixed(2).replace('.', ',');
                }
            } else {
                element.textContent = '--';
            }
        };

        displayValue(usdDisplay, usdRate, true);
        displayValue(costDisplay, costPerToe, false);
        displayValue(editUsdDisplay, usdRate, true);
        displayValue(editCostDisplay, costPerToe, false);
    }

    async fetchPlanRates() {
        if (this.ratesLoading) return false;
        this.ratesLoading = true;

        try {
            const token = this.getPlanToken();
            if (!token) {
                this.displayRates(null, null);
                this.ratesLoaded = false;
                this.ratesLoading = false;
                return false;
            }

            const url = `/api/plan-rates/${token}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                this.displayRates(null, null);
                this.ratesLoaded = false;
                this.ratesLoading = false;
                return false;
            }

            const data = await response.json();

            if (data.success) {
                this.planUsdRate = data.usd_rate && data.usd_rate > 0 ? data.usd_rate : null;
                this.costPerToeUsd = data.cost_per_toe_usd && data.cost_per_toe_usd > 0 ? data.cost_per_toe_usd : null;

                if (this.planUsdRate === null && this.costPerToeUsd === null) {
                    this.displayRates(null, null);
                    this.ratesLoaded = false;
                    this.ratesLoading = false;
                    return false;
                }

                this.displayRates(this.planUsdRate, this.costPerToeUsd);
                this.ratesLoaded = true;
                this.ratesLoading = false;
                this.updateCalculations();
                return true;
            } else {
                this.displayRates(null, null);
                this.ratesLoaded = false;
                this.ratesLoading = false;
                return false;
            }
        } catch (error) {
            this.displayRates(null, null);
            this.ratesLoaded = false;
            this.ratesLoading = false;
            return false;
        }
    }

    getSelectedDirectionType() {
        const selectedRow = document.querySelector('#AddEventModal .modal-table-main tbody tr.active-row');
        if (!selectedRow) return null;
        
        const economCheckbox = selectedRow.querySelector('td:nth-child(5) input');
        const increaseCheckbox = selectedRow.querySelector('td:nth-child(6) input');
        
        const isEconom = economCheckbox?.checked || false;
        const isIncrease = increaseCheckbox?.checked || false;
        
        if (isEconom && isIncrease) return 'double';
        if (isEconom) return 'econom';
        if (isIncrease) return 'increase';
        return null;
    }

    showEffCurrYearWarning(message) {
        let warningSpan = document.getElementById('eff-curr-year-warning');
        
        if (!warningSpan) {
            const effCurrYearInput = document.querySelector('#AddEventModal input[name="EffCurrYear"]');
            if (effCurrYearInput && effCurrYearInput.parentNode) {
                const parentDiv = effCurrYearInput.parentNode;
                const relativeDiv = parentDiv.querySelector('.position-relative');
                
                if (relativeDiv) {
                    warningSpan = document.createElement('span');
                    warningSpan.id = 'eff-curr-year-warning';
                    warningSpan.className = 'text-danger small mt-1';
                    warningSpan.style.display = 'none';
                    warningSpan.style.fontSize = '12px';
                    warningSpan.style.marginTop = '5px';
                    relativeDiv.appendChild(warningSpan);
                } else {
                    warningSpan = document.createElement('span');
                    warningSpan.id = 'eff-curr-year-warning';
                    warningSpan.className = 'text-danger small';
                    warningSpan.style.display = 'none';
                    warningSpan.style.fontSize = '12px';
                    warningSpan.style.marginTop = '5px';
                    warningSpan.style.color = '#dc3545';
                    effCurrYearInput.insertAdjacentElement('afterend', warningSpan);
                }
            }
        }
        
        if (warningSpan) {
            warningSpan.textContent = message || 'Эффект в текущем году не может превышать общий эффект';
            warningSpan.style.display = 'block';
            
            setTimeout(() => {
                if (warningSpan) {
                    warningSpan.style.display = 'none';
                }
            }, 4000);
        }
    }

    validateEffCurrYear() {
        const effTutInput = document.querySelector('#AddEventModal input[name="EffTut"]');
        const effCurrYearInput = document.querySelector('#AddEventModal input[name="EffCurrYear"]');
        
        if (!effTutInput || !effCurrYearInput) return;
        
        const effTut = this.parseNumber(effTutInput.value);
        let effCurrYear = this.parseNumber(effCurrYearInput.value);
        
        if (effCurrYear > effTut) {
            effCurrYear = effTut;
            effCurrYearInput.value = this.formatNumber(effCurrYear, 2);
            
            const warningMessage = `Эффект в текущем году (${this.formatNumber(effCurrYear, 2)} т.у.т.) не может превышать общий эффект (${this.formatNumber(effTut, 2)} т.у.т.)`;
            this.showEffCurrYearWarning(warningMessage);
            
            effCurrYearInput.classList.add('is-invalid');
            setTimeout(() => {
                effCurrYearInput.classList.remove('is-invalid');
            }, 7000);
        } else {
            const warningSpan = document.getElementById('eff-curr-year-warning');
            if (warningSpan) {
                warningSpan.style.display = 'none';
            }
            effCurrYearInput.classList.remove('is-invalid');
        }
    }

    updateFinancingFieldsReadonly(isDouble, eventType) {
        const budgetFields = ['BudgetState', 'BudgetRep', 'BudgetLoc', 'BudgetOther', 'MoneyOwn', 'MoneyLoan', 'MoneyOther'];
        const VolumeFinCurrentYearInput = document.querySelector('#AddEventModal input[name="VolumeFinCurrentYear"]');
        const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
        const ObchVolumeFinInput = document.querySelector('#AddEventModal input[name="ObchVolumeFin"]');
        const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
        
        if (isDouble && eventType === 'saving') {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.value = '0';
                    input.readOnly = true;
                    input.disabled = true;
                }
            });
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.value = '0';
                VolumeFinCurrentYearInput.readOnly = true;
            }
            if (paybackInput) {
                paybackInput.value = '0,0';
                paybackInput.readOnly = true;
            }
            if (ObchVolumeFinInput) {
                ObchVolumeFinInput.value = '0';
                ObchVolumeFinInput.readOnly = true;
            }
            if (effRubInput) {
                effRubInput.readOnly = true;
            }
        } else if (isDouble && eventType === 'increase') {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.readOnly = false;
                    input.disabled = false;
                }
            });
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.readOnly = true;
            }
            if (paybackInput) {
                paybackInput.readOnly = true;
            }
            if (ObchVolumeFinInput) {
                ObchVolumeFinInput.readOnly = false;
                ObchVolumeFinInput.disabled = false;
            }
            if (effRubInput) {
                effRubInput.readOnly = false;
            }
        } else {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.readOnly = false;
                    input.disabled = false;
                }
            });
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.readOnly = true;
            }
            if (paybackInput) {
                paybackInput.readOnly = true;
            }
            if (ObchVolumeFinInput) {
                ObchVolumeFinInput.readOnly = false;
                ObchVolumeFinInput.disabled = false;
            }
            if (effRubInput) {
                if (eventType === 'increase') {
                    effRubInput.readOnly = false;
                } else {
                    effRubInput.readOnly = true;
                }
            }
        }
    }

    updateCalculations() {
        if (!this.ratesLoaded) return;
        if (this.planUsdRate === null || this.costPerToeUsd === null) return;

        this.validateEffCurrYear();

        const eventTypeInput = document.querySelector('#AddEventModal input[name="event_type"]');
        const eventType = eventTypeInput ? eventTypeInput.value : null;
        
        const directionType = this.getSelectedDirectionType();
        const isDouble = (directionType === 'double');
        
        this.updateFinancingFieldsReadonly(isDouble, eventType);
        
        if (isDouble && eventType === 'saving') {
            const effTut = this.parseNumber(document.querySelector('#AddEventModal input[name="EffTut"]')?.value);
            const effRub = Math.round(effTut * this.costPerToeUsd * this.planUsdRate);
            
            const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
            if (effRubInput) {
                effRubInput.value = this.formatNumber(effRub, 0);
                effRubInput.readOnly = true;
            }
            
            const VolumeFinCurrentYearInput = document.querySelector('#AddEventModal input[name="VolumeFinCurrentYear"]');
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.value = '0';
            }
            const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
            if (paybackInput) {
                paybackInput.value = '0,0';
            }
            const ObchVolumeFinInput = document.querySelector('#AddEventModal input[name="ObchVolumeFin"]');
            if (ObchVolumeFinInput) {
                ObchVolumeFinInput.value = '0';
            }
            return;
        }
        
        if (eventType === 'saving') {
            const budgetState = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetState"]')?.value);
            const budgetRep = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetRep"]')?.value);
            const budgetLoc = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetLoc"]')?.value);
            const budgetOther = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetOther"]')?.value);
            const moneyOwn = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyOwn"]')?.value);
            const moneyLoan = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyLoan"]')?.value);
            const moneyOther = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyOther"]')?.value);
            
            const VolumeFinCurrentYear = budgetState + budgetRep + budgetLoc + budgetOther + moneyOwn + moneyLoan + moneyOther;
            
            const VolumeFinCurrentYearInput = document.querySelector('#AddEventModal input[name="VolumeFinCurrentYear"]');
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.value = this.formatNumber(VolumeFinCurrentYear, 0);
            }
            
            const effTut = this.parseNumber(document.querySelector('#AddEventModal input[name="EffTut"]')?.value);
            const effRub = Math.round(effTut * this.costPerToeUsd * this.planUsdRate);
            const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
            if (effRubInput) {
                effRubInput.value = this.formatNumber(effRub, 0);
                effRubInput.readOnly = true;
            }
            
            let payback = 0;
            if (effRub > 0) {
                payback = VolumeFinCurrentYear / effRub;
                if (payback < 0.1 && payback > 0) {
                    payback = 0.1;
                }
            }
            const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
            if (paybackInput) {
                paybackInput.value = this.formatNumber(payback, 1);
            }
            return;
        }
        
        if (eventType === 'increase') {
            const budgetState = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetState"]')?.value);
            const budgetRep = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetRep"]')?.value);
            const budgetLoc = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetLoc"]')?.value);
            const budgetOther = this.parseNumber(document.querySelector('#AddEventModal input[name="BudgetOther"]')?.value);
            const moneyOwn = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyOwn"]')?.value);
            const moneyLoan = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyLoan"]')?.value);
            const moneyOther = this.parseNumber(document.querySelector('#AddEventModal input[name="MoneyOther"]')?.value);
            
            const VolumeFinCurrentYear = budgetState + budgetRep + budgetLoc + budgetOther + moneyOwn + moneyLoan + moneyOther;
            
            const VolumeFinCurrentYearInput = document.querySelector('#AddEventModal input[name="VolumeFinCurrentYear"]');
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.value = this.formatNumber(VolumeFinCurrentYear, 0);
            }
            
            const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
            if (effRubInput) {
                effRubInput.readOnly = false;
            }
            
            const effRub = this.parseNumber(effRubInput?.value);
            let payback = 0;
            if (effRub > 0) {
                payback = VolumeFinCurrentYear / effRub;
                if (payback < 0.1 && payback > 0) {
                    payback = 0.1;
                }
            }
            const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
            if (paybackInput) {
                paybackInput.value = this.formatNumber(payback, 1);
            }
            return;
        }
    }

    bindEventCalculations() {
        const fieldsToWatch = [
            '#AddEventModal input[name="EffTut"]',
            '#AddEventModal input[name="EffRub"]',
            '#AddEventModal input[name="EffCurrYear"]',
            '#AddEventModal input[name="BudgetState"]',
            '#AddEventModal input[name="BudgetRep"]',
            '#AddEventModal input[name="BudgetLoc"]',
            '#AddEventModal input[name="BudgetOther"]',
            '#AddEventModal input[name="MoneyOwn"]',
            '#AddEventModal input[name="MoneyLoan"]',
            '#AddEventModal input[name="MoneyOther"]',
            '#AddEventModal input[name="ObchVolumeFin"]',
            '#AddEventModal input[name="VolumeFinCurrentYear"]'
        ];
        
        fieldsToWatch.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.removeEventListener('input', this.updateCalculations);
                el.addEventListener('input', this.updateCalculations);
            });
        });
        
        const rows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        rows.forEach(row => {
            row.removeEventListener('click', this.onRowClick);
            row.addEventListener('click', this.onRowClick);
        });
    }

    onRowClick() {
        setTimeout(this.updateCalculations, 50);
    }

    step2NextHandler() {
        setTimeout(this.updateCalculations, 100);
    }

    step3BackHandler() {
        setTimeout(this.updateCalculations, 100);
    }

    initStep2NextButton() {
        const step2NextBtn = document.querySelector('#AddEventModal #step2-next-btn');
        if (step2NextBtn) {
            step2NextBtn.removeEventListener('click', this.step2NextHandler);
            step2NextBtn.addEventListener('click', this.step2NextHandler);
        }
    }

    initStep3BackButton() {
        const step3BackBtn = document.querySelector('#AddEventModal #step3-back-btn');
        if (step3BackBtn) {
            step3BackBtn.removeEventListener('click', this.step3BackHandler);
            step3BackBtn.addEventListener('click', this.step3BackHandler);
        }
    }

    initModalOpen() {
        if (!this.AddEventModal) return;
        
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    if (this.AddEventModal.style.display !== 'none') {
                        setTimeout(() => {
                            if (!this.ratesLoaded) {
                                this.fetchPlanRates();
                            }
                            this.bindEventCalculations();
                            this.updateCalculations();
                        }, 100);
                    }
                }
            });
        });
        observer.observe(this.AddEventModal, { attributes: true });
    }

    searchHandler(e) {
        const searchTerm = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        
        rows.forEach(row => {
            const code = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
            const name = row.querySelector('td:nth-child(3)')?.textContent.toLowerCase() || '';
            
            if (code.includes(searchTerm) || name.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    initSearchDirections() {
        const searchInput = document.querySelector('#AddEventModal [data-action="search-directions"]');
        if (!searchInput) return;
        
        searchInput.removeEventListener('input', this.searchHandler);
        searchInput.addEventListener('input', this.searchHandler);
    }

    directionRowClickHandler(e) {
        const row = e.currentTarget;
        
        const allRows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        allRows.forEach(r => r.classList.remove('active-row'));
        row.classList.add('active-row');
        
        const nextButton = document.getElementById('step1-next-btn');
        if (nextButton) {
            nextButton.disabled = false;
        }
        
        const idDirection = row.querySelector('td:first-child')?.textContent;
        const directionInput = document.querySelector('#AddEventModal input[name="id_direction"]');
        if (directionInput && idDirection) {
            directionInput.value = idDirection;
        }
    }

    initDirectionRowClick() {
        const rows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        rows.forEach(row => {
            row.removeEventListener('click', this.directionRowClickHandler);
            row.addEventListener('click', this.directionRowClickHandler);
        });
    }

    initAddEventModal() {
        this.fetchPlanRates();
        this.bindEventCalculations();
        this.initStep2NextButton();
        this.initStep3BackButton();
        this.initModalOpen();
        this.initSearchDirections();
        this.initDirectionRowClick();
        
        setTimeout(() => {
            this.updateCalculations();
        }, 500);
    }

    editPeriodModal() {
        const activeRow = this.getActiveRow();
        if (!activeRow) return;

        const periodCode = activeRow.getAttribute('data-period-code');
        if (!periodCode || !['0001', '0002', '0003', '0004'].includes(periodCode)) return;

        const idEvent = activeRow.getAttribute('data-id');
        if (!idEvent) return;

        this.showPeriodStep();
        this.setPeriodName(activeRow, periodCode);
        this.loadPeriodData(idEvent);
    }

    showPeriodStep() {
        const stepsedit = document.getElementById('steps-edit');
        const periodStep = document.getElementById('period-step');
        const editTypeInput = document.getElementById('edit-event-type');

        if (stepsedit) stepsedit.style.display = 'none';
        if (periodStep) periodStep.style.display = 'block';
        if (editTypeInput) editTypeInput.value = 'period';
    }

    setPeriodName(activeRow, periodCode) {
        const periodName = activeRow.getAttribute('data-period-name') ||
                          activeRow.querySelector('td:first-child')?.textContent.trim() ||
                          this.getPeriodNameByCode(periodCode);
        
        const periodNameDisplay = document.getElementById('period-name-display');
        if (periodNameDisplay) {
            periodNameDisplay.textContent = periodName;
        }
    }

    async loadPeriodData(idEvent) {
        try {
            const response = await fetch(`/api/get-event/${idEvent}`);
            const data = await response.json();

            if (data.error) throw new Error(data.error);

            const effCurrYearInput = document.getElementById('period-EffCurrYear-edit');
            if (effCurrYearInput) {
                let value = data.EffCurrYear || 0;
                value = parseFloat(value);
                if (isNaN(value)) value = 0;
                effCurrYearInput.value = value.toFixed(2).replace('.', ',');
            }

            const form = document.getElementById('editEventeForm');
            if (form) {
                form.action = `/plans/plan/edit-event/${idEvent}`;

                const allInputs = form.querySelectorAll('#steps-edit input, #steps-edit select, #steps-edit textarea');
                allInputs.forEach(input => input.disabled = true);

                const periodInputs = form.querySelectorAll('#period-step input, #period-step select, #period-step textarea');
                periodInputs.forEach(input => input.disabled = false);
            }
        } catch (error) {
            alert('Ошибка при загрузке данных периода: ' + error.message);
        }
    }

    editEventModal() {
        console.log('=== editEventModal НАЧАЛО ===');
        const activeRow = this.getActiveRow();
        console.log('activeRow:', activeRow);
        if (!activeRow) {
            console.log('editEventModal: activeRow не найдена, выход');
            return;
        }

        const idEvent = activeRow.getAttribute('data-id');
        console.log('idEvent:', idEvent);
        if (!idEvent) {
            console.log('editEventModal: idEvent не найден, выход');
            return;
        }

        const periodCode = activeRow.getAttribute('data-period-code');
        console.log('periodCode:', periodCode);
        const isPeriod = periodCode && ['0001', '0002', '0003', '0004'].includes(periodCode);

        if (isPeriod) {
            console.log('editEventModal: это период, вызываю editPeriodModal');
            this.editPeriodModal();
            return;
        }

        console.log('editEventModal: это мероприятие, продолжаем');
        this.showEventStep();
        this.disableNextButton(true);

        console.log('editEventModal: отправляю запросы');
        Promise.all([
            fetch(`/api/get-event/${idEvent}`).then(r => {
                console.log('editEventModal: fetch get-event ответ получен, status:', r.status);
                return r.json();
            }),
            this.fetchPlanRates()
        ]).then(([eventData, rates]) => {
            console.log('editEventModal: данные получены');
            console.log('editEventModal: eventData:', eventData);
            console.log('editEventModal: rates:', rates);
            
            if (eventData.error) {
                console.log('editEventModal: eventData.error:', eventData.error);
                throw new Error(eventData.error);
            }

            const isIncrease = eventData.is_increase === true;
            const isDoubleEffect = eventData.is_double_effect === true;
            
            console.log('editEventModal: isIncrease =', isIncrease);
            console.log('editEventModal: isDoubleEffect =', isDoubleEffect);
            
            this._currentEventType = isIncrease ? 'increase' : 'saving';
            this._isDoubleEffect = isDoubleEffect;
            
            console.log('editEventModal: _currentEventType =', this._currentEventType);
            console.log('editEventModal: _isDoubleEffect =', this._isDoubleEffect);
            
            console.log('editEventModal: вызываю setEventFields');
            this.setEventFields(eventData);
            console.log('editEventModal: вызываю setFormAction');
            this.setFormAction(idEvent);
            
            console.log('editEventModal: ищу элементы DOM');
            const effRubInput = document.getElementById('change-EffRub-edit-model');
            console.log('editEventModal: effRubInput:', effRubInput);
            
            const budgetFields = ['BudgetState', 'BudgetRep', 'BudgetLoc', 'BudgetOther', 'MoneyOwn', 'MoneyLoan', 'MoneyOther'];
            const VolumeFinCurrentYearInput = document.getElementById('change-VolumeFinCurrentYear-edit-model');
            console.log('editEventModal: VolumeFinCurrentYearInput:', VolumeFinCurrentYearInput);
            const ObchVolumeFinInput = document.getElementById('change-ObchVolumeFin-edit-model');
            console.log('editEventModal: ObchVolumeFinInput:', ObchVolumeFinInput);
            const paybackInput = document.getElementById('change-Payback-edit-model');
            console.log('editEventModal: paybackInput:', paybackInput);
            
            // ============ double_effect + saving = все блокируется ============
            if (isDoubleEffect && !isIncrease) {
                console.log('editEventModal: === double_effect + saving - блокируем все ===');
                
                if (effRubInput) {
                    effRubInput.readOnly = true;
                    effRubInput.disabled = false;
                    console.log('editEventModal: EffRub установлен readonly');
                }
                
                budgetFields.forEach(fieldName => {
                    const input = document.getElementById(`change-${fieldName}-edit-model`);
                    if (input) {
                        input.value = '0';
                        input.readOnly = true;
                        input.disabled = true;
                        console.log(`editEventModal: ${fieldName} установлен в 0 и заблокирован`);
                    } else {
                        console.log(`editEventModal: поле change-${fieldName}-edit-model не найдено`);
                    }
                });
                
                if (VolumeFinCurrentYearInput) {
                    VolumeFinCurrentYearInput.value = '0';
                    VolumeFinCurrentYearInput.readOnly = true;
                    console.log('editEventModal: VolumeFinCurrentYear установлен в 0 и заблокирован');
                }
                if (paybackInput) {
                    paybackInput.value = '0,0';
                    paybackInput.readOnly = true;
                    console.log('editEventModal: Payback установлен в 0 и заблокирован');
                }
                if (ObchVolumeFinInput) {
                    ObchVolumeFinInput.value = '0';
                    ObchVolumeFinInput.readOnly = true;
                    console.log('editEventModal: ObchVolumeFin установлен в 0 и заблокирован');
                }
                
                this.disableNextButton(false);
                console.log('editEventModal: double_effect + saving завершен');
                return;
            }
            
            // ============ Обычный increase ============
            if (isIncrease) {
                console.log('editEventModal: === increase режим ===');
                
                if (effRubInput) {
                    effRubInput.readOnly = false;
                    effRubInput.disabled = false;
                    console.log('editEventModal: EffRub доступен для редактирования (increase)');
                }
                
                budgetFields.forEach(fieldName => {
                    const input = document.getElementById(`change-${fieldName}-edit-model`);
                    if (input) {
                        input.readOnly = false;
                        input.disabled = false;
                        console.log(`editEventModal: ${fieldName} разблокирован`);
                    }
                });
                
                if (ObchVolumeFinInput) {
                    ObchVolumeFinInput.readOnly = false;
                    ObchVolumeFinInput.disabled = false;
                    console.log('editEventModal: ObchVolumeFin разблокирован');
                }
                
            } else {
                // ============ saving (не double_effect) ============
                console.log('editEventModal: === saving режим (не double_effect) ===');
                
                if (effRubInput) {
                    effRubInput.readOnly = true;
                    effRubInput.disabled = false;
                    console.log('editEventModal: EffRub readonly (saving)');
                }
                
                budgetFields.forEach(fieldName => {
                    const input = document.getElementById(`change-${fieldName}-edit-model`);
                    if (input) {
                        input.readOnly = false;
                        input.disabled = false;
                        console.log(`editEventModal: ${fieldName} разблокирован`);
                    }
                });
                
                if (ObchVolumeFinInput) {
                    ObchVolumeFinInput.readOnly = false;
                    ObchVolumeFinInput.disabled = false;
                    console.log('editEventModal: ObchVolumeFin разблокирован');
                }
            }
            
            // VolumeFinCurrentYear и Payback всегда readonly
            if (VolumeFinCurrentYearInput) {
                VolumeFinCurrentYearInput.readOnly = true;
                console.log('editEventModal: VolumeFinCurrentYear readonly');
            }
            if (paybackInput) {
                paybackInput.readOnly = true;
                console.log('editEventModal: Payback readonly');
            }
            
            this.disableNextButton(false);
            console.log('editEventModal: кнопка Next разблокирована');

            if (this.planUsdRate !== null && this.costPerToeUsd !== null) {
                console.log('editEventModal: курсы загружены, вызываю initEditCalculations');
                this.initEditCalculations();
            } else {
                console.log('editEventModal: курсы не загружены, пропускаю расчеты');
            }
            
            console.log('=== editEventModal КОНЕЦ ===');
        }).catch(error => {
            console.error('editEventModal: ОШИБКА:', error);
            alert('Ошибка при загрузке данных мероприятия: ' + error.message);
            this.disableNextButton(false);
        });
    }

    showEventStep() {
        const modalTitle = document.getElementById('modal-title');
        const step1 = document.getElementById('step1');
        const step2 = document.getElementById('step2');
        const periodStep = document.getElementById('period-step');
        const editType = document.getElementById('edit-event-type');
        const progressBarContainer = document.querySelector('.progress-modal-bar-container');
        const modalProgressBar = document.getElementById('modal-progress-bar');
        const stepsedit = document.getElementById('steps-edit');

        if (modalTitle) modalTitle.textContent = 'Редактирование мероприятия';
        if (stepsedit) stepsedit.style.display = 'block';
        if (step1) step1.style.display = 'block';
        if (step2) step2.style.display = 'none';
        if (periodStep) periodStep.style.display = 'none';
        if (progressBarContainer) progressBarContainer.style.display = '';
        if (modalProgressBar) modalProgressBar.style.width = '50%';
        if (editType) editType.value = 'full';

        const form = document.getElementById('editEventeForm');
        if (form) {
            const allInputs = form.querySelectorAll('#steps-edit input, #steps-edit select, #steps-edit textarea');
            allInputs.forEach(input => input.disabled = false);
        }
    }

    disableNextButton(disabled) {
        const nextButton = document.getElementById('step1-next-btn');
        if (nextButton) {
            nextButton.disabled = disabled;
        }
    }

    setEventFields(data) {
        const fields = {
            'change-name-edit-model': data.name || '',
            'change-Volume-edit-model': data.Volume || '',
            'change-EffTut-edit-model': data.EffTut || '',
            'change-EffRub-edit-model': data.EffRub || '',
            'change-ExpectedQuarter-edit-model': data.ExpectedQuarter || '',
            'change-EffCurrYear-edit-model': data.EffCurrYear || '',
            'change-Payback-edit-model': data.Payback || '',
            'change-VolumeFinCurrentYear-edit-model': data.VolumeFinCurrentYear || '',
            'change-BudgetState-edit-model': data.BudgetState || '0',
            'change-BudgetRep-edit-model': data.BudgetRep || '0',
            'change-BudgetLoc-edit-model': data.BudgetLoc || '0',
            'change-BudgetOther-edit-model': data.BudgetOther || '0',
            'change-MoneyOwn-edit-model': data.MoneyOwn || '0',
            'change-MoneyLoan-edit-model': data.MoneyLoan || '0',
            'change-MoneyOther-edit-model': data.MoneyOther || '0'
        };

        Object.entries(fields).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.value = value;
            }
        });
    }

    setFormAction(idEvent) {
        const form = document.getElementById('editEventeForm');
        if (form) {
            form.action = `/plans/plan/edit-event/${idEvent}`;
        }
    }

    initEditCalculations() {
        const self = this;
        
        const updateEditCalculations = () => {
            let eventType = self._currentEventType;
            if (!eventType) {
                const eventTypeInput = document.getElementById('edit-event-type');
                eventType = eventTypeInput ? eventTypeInput.value : null;
            }
            
            const isDoubleEffect = self._isDoubleEffect || false;
            
            const budgetState = self.parseNumber(document.getElementById('change-BudgetState-edit-model')?.value);
            const budgetRep = self.parseNumber(document.getElementById('change-BudgetRep-edit-model')?.value);
            const budgetLoc = self.parseNumber(document.getElementById('change-BudgetLoc-edit-model')?.value);
            const budgetOther = self.parseNumber(document.getElementById('change-BudgetOther-edit-model')?.value);
            const moneyOwn = self.parseNumber(document.getElementById('change-MoneyOwn-edit-model')?.value);
            const moneyLoan = self.parseNumber(document.getElementById('change-MoneyLoan-edit-model')?.value);
            const moneyOther = self.parseNumber(document.getElementById('change-MoneyOther-edit-model')?.value);

            const effRubInput = document.getElementById('change-EffRub-edit-model');
            const effTutInput = document.getElementById('change-EffTut-edit-model');
            const VolumeFinCurrentYearInput = document.getElementById('change-VolumeFinCurrentYear-edit-model');
            const paybackInput = document.getElementById('change-Payback-edit-model');
            
            let VolumeFinCurrentYear = 0;
            let effRub = 0;
            
            if (isDoubleEffect && eventType === 'saving') {
                VolumeFinCurrentYear = 0;
                
                const effTut = self.parseNumber(effTutInput?.value);
                effRub = Math.round(effTut * self.costPerToeUsd * self.planUsdRate);
                
                if (effRubInput) {
                    effRubInput.value = self.formatNumber(effRub, 0);
                }
                
                if (VolumeFinCurrentYearInput) {
                    VolumeFinCurrentYearInput.value = '0';
                }
                
                if (paybackInput) {
                    paybackInput.value = '0,0';
                }
                
                return;
            }
            
            if (eventType === 'increase') {
                VolumeFinCurrentYear = budgetState + budgetRep + budgetLoc + budgetOther + moneyOwn + moneyLoan + moneyOther;
                effRub = self.parseNumber(effRubInput?.value);
                
                if (VolumeFinCurrentYearInput) {
                    VolumeFinCurrentYearInput.value = self.formatNumber(VolumeFinCurrentYear, 0);
                    VolumeFinCurrentYearInput.readOnly = true;
                }
                
                if (effRubInput) {
                    effRubInput.readOnly = false;
                    effRubInput.disabled = false;
                }
                
            } else {
                VolumeFinCurrentYear = budgetState + budgetRep + budgetLoc + budgetOther + moneyOwn + moneyLoan + moneyOther;
                
                const effTut = self.parseNumber(effTutInput?.value);
                effRub = Math.round(effTut * self.costPerToeUsd * self.planUsdRate);
                
                if (effRubInput) {
                    effRubInput.value = self.formatNumber(effRub, 0);
                    effRubInput.readOnly = true;
                    effRubInput.disabled = false;
                }
                
                if (VolumeFinCurrentYearInput) {
                    VolumeFinCurrentYearInput.value = self.formatNumber(VolumeFinCurrentYear, 0);
                    VolumeFinCurrentYearInput.readOnly = true;
                }
            }
            
            let payback = 0;
            if (effRub > 0) {
                payback = VolumeFinCurrentYear / effRub;
                if (payback < 0.1 && payback > 0) {
                    payback = 0.1;
                }
            }
            
            if (paybackInput) {
                paybackInput.value = self.formatNumber(payback, 1);
                paybackInput.readOnly = true;
            }
        };

        const editFields = [
            'change-EffTut-edit-model',
            'change-EffRub-edit-model',
            'change-BudgetState-edit-model', 
            'change-BudgetRep-edit-model',
            'change-BudgetLoc-edit-model', 
            'change-BudgetOther-edit-model',
            'change-MoneyOwn-edit-model', 
            'change-MoneyLoan-edit-model',
            'change-MoneyOther-edit-model',
            'change-VolumeFinCurrentYear-edit-model'
        ];

        editFields.forEach(fieldId => {
            const input = document.getElementById(fieldId);
            if (input) {
                input.removeEventListener('input', updateEditCalculations);
                input.addEventListener('input', updateEditCalculations);
            }
        });

        setTimeout(updateEditCalculations, 100);
        setTimeout(updateEditCalculations, 300);
    }
}

function Edit_Period_modal() {
    const manager = new EventModalManager();
    manager.editPeriodModal();
}

function Edit_Evente_modal() {
    const manager = new EventModalManager();
    manager.editEventModal();
}

function getPlanToken() {
    const manager = new EventModalManager();
    return manager.getPlanToken();
}

async function fetchEditPlanRates() {
    const manager = new EventModalManager();
    return await manager.fetchPlanRates();
}

function initEditCalculations(usdRate, costPerToe) {
    const manager = new EventModalManager();
    manager.planUsdRate = usdRate;
    manager.costPerToeUsd = costPerToe;
    manager.ratesLoaded = true;
    manager.initEditCalculations();
}

function setValueIfExists(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.value = value;
    }
}

function validateAndEnableButton() {
    const addModal = document.getElementById('AddEventModal');
    if (addModal && addModal.style.display !== 'none') {
        const addFields = addModal.querySelectorAll('#step2 [name="name"], #step2 [name="Volume"], #step2 [name="ExpectedQuarter"]');
        const addButton = addModal.querySelector('#step2-next-btn[data-action="next-step-2"]');
        
        if (addFields.length === 3 && addButton) {
            const allFilled = Array.from(addFields).every(field => {
                const value = field.value.trim();
                if (field.name === 'name') return value !== '';
                if (field.name === 'Volume') return value !== '' && parseFloat(value) > 0;
                if (field.name === 'ExpectedQuarter') return value !== '' && parseInt(value) >= 1 && parseInt(value) <= 4;
                return false;
            });
            addButton.disabled = !allFilled;
        }
    }
    
    const editModal = document.getElementById('EditEventModal');
    if (editModal && editModal.style.display !== 'none') {
        const editType = document.getElementById('edit-event-type')?.value;
        
        if (editType === 'period') {
            const editButton = editModal.querySelector('#step1-next-btn');
            if (editButton) {
                editButton.disabled = false;
            }
            return;
        }
        
        const editFields = editModal.querySelectorAll('#step1 [name="name"], #step1 [name="Volume"], #step1 [name="ExpectedQuarter"]');
        const editButton = editModal.querySelector('#step1-next-btn');
        
        if (editFields.length === 3 && editButton) {
            const allFilled = Array.from(editFields).every(field => {
                const value = field.value.trim();
                if (field.name === 'name') return value !== '';
                if (field.name === 'Volume') return value !== '' && parseFloat(value) > 0;
                if (field.name === 'ExpectedQuarter') return value !== '' && parseInt(value) >= 1 && parseInt(value) <= 4;
                return false;
            });
            editButton.disabled = !allFilled;
        }
    }
}

function checkCategoryRequired() {
    const selectedIndicatorName = document.getElementById('selected-indicator-name');
    const categorySection = document.getElementById('category-section');
    const nameSection = document.getElementById('name-section');
    const submitBtn = document.getElementById('submit-indicator-btn');
    const categoryRadios = document.querySelectorAll('input[name="fuel_category"]');
    const nameInput = document.getElementById('name-section-input');
    
    if (!selectedIndicatorName || !categorySection || !nameSection) return;
    
    const indicatorText = selectedIndicatorName.textContent;
    const isCategoryRequired = indicatorText.includes('2023') || indicatorText.includes('2024');
    
    function validateForm() {
        const isCategoryChecked = Array.from(categoryRadios).some(radio => radio.checked);
        const isNameFilled = nameInput && nameInput.value.trim() !== '';
        
        if (submitBtn) {
            if (isCategoryRequired) {
                submitBtn.disabled = !(isCategoryChecked && isNameFilled);
            } else {
                submitBtn.disabled = false;
            }
        }
    }
    
    if (isCategoryRequired) {
        categorySection.style.display = 'block';
        nameSection.style.display = 'block';
        
        categoryRadios.forEach(radio => {
            radio.removeEventListener('change', validateForm);
            radio.addEventListener('change', validateForm);
        });
        
        if (nameInput) {
            nameInput.removeEventListener('input', validateForm);
            nameInput.addEventListener('input', validateForm);
        }
        
        validateForm();
    } else {
        categorySection.style.display = 'none';
        nameSection.style.display = 'none';
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('AddEventModal') || document.getElementById('EditEventModal')) {
        window.eventModalManager = new EventModalManager();
    }
 
    document.addEventListener('input', function(e) {
        if (e.target.matches('[name="name"], [name="Volume"], [name="ExpectedQuarter"]')) {
            setInterval(validateAndEnableButton, 300);   
        }
    });
});