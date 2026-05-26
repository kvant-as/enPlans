class PlanIndicators {
    constructor(token) {
        this.token = token;
        this.init();
    }

    async init() {
        await this.loadIndicators();
        this.initTableContextMenu();
        this.initColumnResize();
        this.initAddIndicatorModal();
        this.initEditIndicatorModal();
    }

    initAddIndicatorModal() {
        const addModal = document.getElementById('AddIndicatorModal');
        if (!addModal) return;

        const standardRadio = addModal.querySelector('input[name="coeff_type"][value="standard"]');
        const customRadio = addModal.querySelector('input[name="coeff_type"][value="custom"]');
        const customCoeffGroup = addModal.querySelector('#custom-coeff-group');
        const customCoeffInput = addModal.querySelector('input[name="custom_coeff"]');

        if (standardRadio && customRadio && customCoeffGroup) {
            standardRadio.addEventListener('change', () => {
                if (standardRadio.checked) {
                    customCoeffGroup.style.display = 'none';
                    if (customCoeffInput) customCoeffInput.value = '';
                    this.updateTutResults();
                }
            });

            customRadio.addEventListener('change', () => {
                if (customRadio.checked) {
                    customCoeffGroup.style.display = 'block';
                    this.updateTutResults();
                }
            });
        }

        if (customCoeffInput) {
            customCoeffInput.addEventListener('input', () => {
                if (customRadio && customRadio.checked) {
                    this.updateTutResults();
                }
            });
        }

        const table = addModal.querySelector('[data-action="modal-table-main"]');
        if (table) {
            table.querySelectorAll('tbody tr').forEach(row => {
                row.removeEventListener('click', this.onIndicatorRowClick.bind(this));
                row.addEventListener('click', this.onIndicatorRowClick.bind(this));
            });
        }

        const numericInputs = addModal.querySelectorAll('.app-numeric-input');
        numericInputs.forEach(input => {
            input.removeEventListener('input', this.updateTutResults.bind(this));
            input.addEventListener('input', this.updateTutResults.bind(this));
        });

        this.updateTutResults();
    }

    initEditIndicatorModal() {
        const editModal = document.getElementById('EditIndicatorModal');
        if (!editModal) return;

        const standardRadio = editModal.querySelector('input[name="coeff_type"][value="standard"]');
        const customRadio = editModal.querySelector('input[name="coeff_type"][value="custom"]');
        const customCoeffGroup = editModal.querySelector('#edit-custom-coeff-group');
        const customCoeffInput = editModal.querySelector('#edit-custom-coeff');

        if (standardRadio && customRadio && customCoeffGroup) {
            standardRadio.removeEventListener('change', this.handleEditStandardChange);
            customRadio.removeEventListener('change', this.handleEditCustomChange);
            
            this.handleEditStandardChange = () => {
                if (standardRadio.checked) {
                    customCoeffGroup.style.display = 'none';
                    if (customCoeffInput) customCoeffInput.value = '';
                    if (typeof updateEditTutResults === 'function') updateEditTutResults();
                }
            };
            
            this.handleEditCustomChange = () => {
                if (customRadio.checked) {
                    customCoeffGroup.style.display = 'block';
                    if (typeof updateEditTutResults === 'function') updateEditTutResults();
                }
            };
            
            standardRadio.addEventListener('change', this.handleEditStandardChange);
            customRadio.addEventListener('change', this.handleEditCustomChange);
        }

        if (customCoeffInput) {
            customCoeffInput.removeEventListener('input', this.handleEditCustomInput);
            this.handleEditCustomInput = () => {
                if (customRadio && customRadio.checked) {
                    if (typeof updateEditTutResults === 'function') updateEditTutResults();
                }
            };
            customCoeffInput.addEventListener('input', this.handleEditCustomInput);
        }

        const numericInputs = editModal.querySelectorAll('.app-numeric-input');
        numericInputs.forEach(input => {
            input.removeEventListener('input', updateEditTutResults);
            input.addEventListener('input', updateEditTutResults);
        });
    }

    onIndicatorRowClick(event) {
        const row = event.currentTarget;
        const selectedDisplay = document.getElementById('selected-indicator-display');
        const selectedName = document.getElementById('selected-indicator-name');
        const idIndicatorInput = document.querySelector('input[name="id_indicator"]');
        const standardCoeffSpan = document.getElementById('standard-coeff-value');
        
        const code = row.cells[1]?.textContent.trim() || '';
        const name = row.cells[2]?.textContent.trim() || '';
        const coeff = row.cells[4]?.textContent.trim() || '0';
        const unitName = row.cells[3]?.textContent.trim() || 'ед. изм.';
        const indicatorId = row.cells[0]?.textContent.trim() || '';
        
        if (selectedName) {
            selectedName.textContent = `${code} - ${name}`;
        }
        if (selectedDisplay) {
            selectedDisplay.style.display = 'block';
        }
        if (idIndicatorInput) {
            idIndicatorInput.value = indicatorId;
        }
        
        if (standardCoeffSpan) {
            let coeffValue = parseFloat(coeff.replace(',', '.'));
            if (isNaN(coeffValue)) coeffValue = 0;
            standardCoeffSpan.textContent = coeffValue.toFixed(3).replace('.', ',');
        }
        
        const unitSpans = document.querySelectorAll('#AddIndicatorModal .value-unit');
        unitSpans.forEach(span => {
            span.textContent = unitName;
        });
        
        if (typeof checkCategoryRequired === 'function') {
            checkCategoryRequired();
        }
        
        const table = document.querySelector('[data-action="modal-table-main"]');
        if (table) {
            table.querySelectorAll('tbody tr').forEach(tr => {
                tr.classList.remove('active-row');
            });
        }
        row.classList.add('active-row');
        
        const nextButton = document.getElementById('step1-next-btn');
        if (nextButton) {
            nextButton.disabled = false;
        }
        
        this.updateTutResults();
    }

    updateTutResults() {
        let currentCoeff = null;
        const coeffTypeRadio = document.querySelector('#AddIndicatorModal input[name="coeff_type"]:checked');
        
        if (!coeffTypeRadio) {
            const standardCoeffSpan = document.getElementById('standard-coeff-value');
            if (standardCoeffSpan) {
                let coeffText = standardCoeffSpan.textContent.replace(',', '.');
                currentCoeff = parseFloat(coeffText);
            }
        } else {
            const coeffType = coeffTypeRadio.value;
            
            if (coeffType === 'standard') {
                const coeffSpan = document.getElementById('standard-coeff-value');
                if (coeffSpan) {
                    let coeffText = coeffSpan.textContent.replace(',', '.');
                    currentCoeff = parseFloat(coeffText);
                }
            } else {
                const customInput = document.querySelector('#AddIndicatorModal input[name="custom_coeff"]');
                if (customInput && customInput.value) {
                    let customText = customInput.value.replace(',', '.');
                    currentCoeff = parseFloat(customText);
                } else {
                    currentCoeff = 0;
                }
            }
        }
        
        if (currentCoeff === null || isNaN(currentCoeff)) {
            currentCoeff = 0;
        }
        
        const years = ['before', 'prev', 'current'];
        years.forEach((year) => {
            const input = document.querySelector(`#AddIndicatorModal input[data-year="${year}"]`);
            const resultSpan = document.getElementById(`result-${year}`);
            
            if (input && resultSpan) {
                let inputValue = input.value.replace(',', '.');
                let value = parseFloat(inputValue);
                if (isNaN(value)) {
                    value = 0;
                }
                const tutValue = value * currentCoeff;
                let formattedResult = tutValue.toFixed(2).replace('.', ',');
                resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
            }
        });
    }

    async loadIndicators() {
        try {
            const response = await fetch(`/api/indicators/${this.token}`);
            const data = await response.json();
            
            if (data.success) {
                this.renderIndicatorsTable(data.indicators);
            } else {
                this.showError('Ошибка загрузки данных');
            }
        } catch (error) {
            console.error('Error loading indicators:', error);
            this.showError('Ошибка загрузки данных');
        }
    }

    renderIndicatorsTable(indicators) {
        const tbody = document.getElementById('indicators-tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        let lastGroup = null;
        
        indicators.forEach((row, index) => {
            const isNewGroup = row.group !== lastGroup;
            lastGroup = row.group;
            
            const tr = document.createElement('tr');
            tr.className = `menu-row ${isNewGroup ? 'group-header-indicator' : ''}`;
            tr.setAttribute('data-id', row.id);
            
            tr.innerHTML = `
                <td style="text-align: center;">${index + 1}</td>
                <td style="text-align: center">${isNewGroup ? (Number.isInteger(row.group) ? row.group : row.group) : ''}</td>
                <td style="text-align: start">${this.escapeHtml(row.name)}</td>
                <td style="text-align: start">${this.escapeHtml(row.unit_name)}</td>
                <td>${row.QYearBeforePrev_unit.toFixed(2).replace('.', ',')}</td>
                <td>${row.QYearBeforePrev_tut.toFixed(2).replace('.', ',')}</td>
                <td>${row.QYearPrev_unit.toFixed(2).replace('.', ',')}</td>
                <td>${row.QYearPrev_tut.toFixed(2).replace('.', ',')}</td>
                <td>${row.QYearCurrent_unit.toFixed(2).replace('.', ',')}</td>
                <td>${row.QYearCurrent_tut.toFixed(2).replace('.', ',')}</td>
                <td class="difference-cell" style="border-right: none; ${row.difference < 0 ? 'background-color: rgb(96, 255, 122, 0.705);' : (row.difference > 0 ? 'background-color: rgb(255, 96, 96, 0.705);' : '')}">
                    ${row.difference.toFixed(2).replace('.', ',')}
                </td>
                <td style="display: none">${row.code}</td>
                <td style="display: none" data-group="${row.group}">${row.group}</td>
            `;
            
            tbody.appendChild(tr);
        });
    }

    initTableContextMenu() {
        const indicatorsTable = document.getElementById('indicatorsTable');
        const indicatorsMenu = document.getElementById('MenuMainTable');
        
        if (indicatorsTable && indicatorsMenu && typeof TableContextMenu !== 'undefined') {
            if (window.indicatorsTableMenu) {
                window.indicatorsTableMenu = null;
            }
            
            window.indicatorsTableMenu = new TableContextMenu('indicatorsTable', 'MenuMainTable', {
                contextEditButtonId: 'contextEditButton',
                contextDeleteButtonId: 'contextDeleteButton',
                tableEditButtonId: 'tableEditButton',
                tableDeleteButtonId: 'tableDeleteButton',
                removeUrlTemplate: '../delete-indicator/{id}',
                immutableCodes: ['260', '9900', '9999', '1000', '1797', '1796', '9915', '9916', '9917', '9910'],
                immutableEditCodes: [],
                immutableDeleteCodes: ['9911', '9912', '9913', '9914', '1404', '1104', '1424', '1105', '1405', '1425', '1445'],
                codeColumnIndex: 11,
                hideCodeColumn: true
            });
        }
    }

    initColumnResize() {
        const table = document.querySelector('.main-table');
        if (!table) return;
        
        const thElements = table.querySelectorAll('th.resizable');
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        let currentTh = null;

        thElements.forEach(th => {
            const resizer = th.querySelector('.resizer');
            if (resizer) {
                resizer.addEventListener('mousedown', function(e) {
                    isResizing = true;
                    startX = e.clientX;
                    startWidth = th.offsetWidth;
                    currentTh = th;
                    document.body.style.cursor = 'col-resize';
                    e.preventDefault();
                });
            }
        });

        document.addEventListener('mousemove', function(e) {
            if (isResizing && currentTh) {
                const newWidth = startWidth + (e.clientX - startX);
                currentTh.style.width = newWidth + 'px';
                currentTh.style.minWidth = newWidth + 'px';
            }
        });

        document.addEventListener('mouseup', function() {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                currentTh = null;
            }
        });
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        const tbody = document.getElementById('indicators-tbody');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: red;">${message}<tr></tr>`;
        }
    }
}

function Edit_indicator_modal() {
    const EditIndicatorModal = document.getElementById('EditIndicatorModal');
    if (!EditIndicatorModal) return;

    const activeRow = document.querySelector('.rows .active-row');
    if (!activeRow) return;

    const idIndicator = activeRow.getAttribute('data-id');
    if (!idIndicator) return;

    const editIdInput = document.getElementById('edit-id-indicator');
    if (editIdInput) {
        editIdInput.value = idIndicator;
    }

    let groupValue = '';
    const groupDataCell = activeRow.querySelector('td[data-group]');
    if (groupDataCell) {
        groupValue = groupDataCell.getAttribute('data-group');
    }

    const isGroup5 = groupValue === '5.0';
    const isGroup6 = groupValue === '6.0';
    const isSpecialGroup = isGroup5 || isGroup6;

    const qYearCurrNoDisplay = document.getElementById('QYearCurr-edit-nodisplay');
    const QYearBeforePrevNoDisplay = document.getElementById('QYearBeforePrev-edit-nodisplay');
    const QYearCurrentCard = document.getElementById('QYearCurrent-edit-nodisplay');
    
    fetch(`/api/get-indicator/${idIndicator}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            
            const editSelectedIndicatorName = document.getElementById('edit-selected-indicator-name');
            if (editSelectedIndicatorName && data.name) {
                const indicatorCode = data.code || '';
                const displayName = indicatorCode ? indicatorCode + ' - ' + data.name : data.name;
                editSelectedIndicatorName.textContent = displayName;
            }
            
            const unitName = data.unit_name || 'ед. изм.';
            const unitSpans = document.querySelectorAll('#EditIndicatorModal .value-unit');
            unitSpans.forEach(function(span) {
                span.textContent = unitName;
            });
            
            const indicatorCode = data.code;
            const indicatorCodeNum = parseInt(indicatorCode);
            const isCoeffEditable = indicatorCodeNum >= 2000 && indicatorCodeNum <= 2024;
            const isCodes9911to9914 = ['9911', '9912', '9913', '9914'].includes(indicatorCode);
            
            if (isCodes9911to9914) {
                if (QYearBeforePrevNoDisplay) QYearBeforePrevNoDisplay.style.display = 'none';
                if (qYearCurrNoDisplay) qYearCurrNoDisplay.style.display = 'none';
                if (QYearCurrentCard) {
                    QYearCurrentCard.style.display = 'block';
                    const currentInput = QYearCurrentCard.querySelector('input');
                    if (currentInput) {
                        currentInput.setAttribute('required', 'required');
                        currentInput.removeAttribute('readonly');
                    }
                }
            } else if (isSpecialGroup) {
                if (QYearBeforePrevNoDisplay) QYearBeforePrevNoDisplay.style.display = 'none';
                if (qYearCurrNoDisplay) qYearCurrNoDisplay.style.display = 'none';
                if (QYearCurrentCard) {
                    QYearCurrentCard.style.display = 'block';
                    const currentInput = QYearCurrentCard.querySelector('input');
                    if (currentInput) {
                        currentInput.setAttribute('required', 'required');
                        currentInput.removeAttribute('readonly');
                    }
                }
            } else {
                if (QYearBeforePrevNoDisplay) QYearBeforePrevNoDisplay.style.display = '';
                if (qYearCurrNoDisplay) qYearCurrNoDisplay.style.display = '';
                if (QYearCurrentCard) {
                    QYearCurrentCard.style.display = 'block';
                    const currentInput = QYearCurrentCard.querySelector('input');
                    if (currentInput) {
                        currentInput.setAttribute('required', 'required');
                        currentInput.removeAttribute('readonly');
                    }
                }
            }
            
            const coeffSection = document.getElementById('edit-coeff-section');
            const customOption = document.getElementById('edit-custom-option');
            
            if (isCoeffEditable) {
                coeffSection.style.display = 'block';
                customOption.style.display = 'block';
            } else {
                coeffSection.style.display = 'block';
                customOption.style.display = 'none';
                const standardRadio = document.querySelector('#EditIndicatorModal input[name="coeff_type"][value="standard"]');
                if (standardRadio) {
                    standardRadio.checked = true;
                }
            }
            
            const standardCoeffSpan = document.getElementById('edit-standard-coeff-value');
            if (standardCoeffSpan) {
                standardCoeffSpan.textContent = data.CoeffToTut.toFixed(3).replace('.', ',');
            }
            
            const customCoeffGroup = document.getElementById('edit-custom-coeff-group');
            const customCoeffInput = document.getElementById('edit-custom-coeff');
            const standardRadio = document.querySelector('#EditIndicatorModal input[name="coeff_type"][value="standard"]');
            const customRadio = document.querySelector('#EditIndicatorModal input[name="coeff_type"][value="custom"]');
            
            if (isCoeffEditable && data.is_custom && data.custom_coeff_to_tut) {
                if (customRadio) customRadio.checked = true;
                if (customCoeffGroup) customCoeffGroup.style.display = 'block';
                if (customCoeffInput) customCoeffInput.value = data.custom_coeff_to_tut.toFixed(3).replace('.', ',');
            } else {
                if (standardRadio) standardRadio.checked = true;
                if (customCoeffGroup) customCoeffGroup.style.display = 'none';
                if (customCoeffInput) customCoeffInput.value = '';
            }
            
            const usedCoeff = data.used_coeff;
            const coeffValue = usedCoeff ? usedCoeff : data.CoeffToTut;
            
            if (isCodes9911to9914) {
                setValueIfExists('QYearBeforePrev-edit', '');
                setValueIfExists('QYearCurr-edit', '');
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue).toFixed(2).replace('.', ',') : '0,00';
                setValueIfExists('QYearCurrent-edit', valCurrent);
            } else if (!isSpecialGroup) {
                const valBeforePrev = data.QYearBeforePrev ? (data.QYearBeforePrev / coeffValue).toFixed(2).replace('.', ',') : '0,00';
                const valPrev = data.QYearPrev ? (data.QYearPrev / coeffValue).toFixed(2).replace('.', ',') : '0,00';
                setValueIfExists('QYearBeforePrev-edit', valBeforePrev);
                setValueIfExists('QYearCurr-edit', valPrev);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue).toFixed(2).replace('.', ',') : '0,00';
                setValueIfExists('QYearCurrent-edit', valCurrent);
            } else {
                setValueIfExists('QYearBeforePrev-edit', '');
                setValueIfExists('QYearCurr-edit', '');
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue).toFixed(2).replace('.', ',') : '0,00';
                setValueIfExists('QYearCurrent-edit', valCurrent);
            }
            
            const categorySection = document.getElementById('edit-category-section');
            
            if (indicatorCode === '2023' || indicatorCode === '2024') {
                categorySection.style.display = 'block';
                
                const localRadio = document.querySelector('#EditIndicatorModal input[name="fuel_category"][value="local"]');
                const renewableRadio = document.querySelector('#EditIndicatorModal input[name="fuel_category"][value="renewable"]');
                
                if (data.is_local) {
                    if (localRadio) localRadio.checked = true;
                } else if (data.is_renewable) {
                    if (renewableRadio) renewableRadio.checked = true;
                }
            } else {
                categorySection.style.display = 'none';
            }

            const form = document.getElementById('editIndicatorForm');
            if (form) {
                const token = document.querySelector('#indicatorsTable')?.dataset?.token;
                if (token) {
                    form.action = `/plans/plan/edit-indicator/${token}`;
                }
            }
            
            updateEditTutResults();
        })
        .catch(error => {
            console.error('Error fetching indicator data:', error);
            alert('Ошибка при загрузке данных: ' + error.message);
        });
}

function updateEditTutResults() {
    let currentCoeff = null;
    const coeffTypeRadio = document.querySelector('#EditIndicatorModal input[name="coeff_type"]:checked');
    
    if (!coeffTypeRadio) {
        const standardCoeffSpan = document.getElementById('edit-standard-coeff-value');
        if (standardCoeffSpan) {
            let coeffText = standardCoeffSpan.textContent.replace(',', '.');
            currentCoeff = parseFloat(coeffText);
        }
    } else {
        const coeffType = coeffTypeRadio.value;
        
        if (coeffType === 'standard') {
            const coeffSpan = document.getElementById('edit-standard-coeff-value');
            if (coeffSpan) {
                let coeffText = coeffSpan.textContent.replace(',', '.');
                currentCoeff = parseFloat(coeffText);
            }
        } else {
            const customInput = document.getElementById('edit-custom-coeff');
            if (customInput && customInput.value) {
                let customText = customInput.value.replace(',', '.');
                currentCoeff = parseFloat(customText);
            } else {
                currentCoeff = 0;
            }
        }
    }
    
    if (currentCoeff === null || isNaN(currentCoeff)) {
        currentCoeff = 0;
    }
    
    const activeRow = document.querySelector('.rows .active-row');
    let indicatorCode = '';
    if (activeRow) {
        const codeCell = activeRow.querySelector('td:nth-child(12)');
        if (codeCell) {
            indicatorCode = codeCell.textContent.trim();
        }
    }
    
    const isCodes9911to9914 = ['9911', '9912', '9913', '9914'].includes(indicatorCode);
    
    if (isCodes9911to9914) {
        const currentInput = document.getElementById('QYearCurrent-edit');
        const resultSpan = document.getElementById('edit-result-current');
        
        if (currentInput && resultSpan && currentInput.value) {
            let inputValue = currentInput.value.replace(',', '.');
            let value = parseFloat(inputValue);
            if (isNaN(value)) value = 0;
            const tutValue = value * currentCoeff;
            let formattedResult = tutValue.toFixed(2).replace('.', ',');
            resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
        }
    } else {
        const inputs = [
            { id: 'QYearBeforePrev-edit', resultId: 'edit-result-before' },
            { id: 'QYearCurr-edit', resultId: 'edit-result-prev' },
            { id: 'QYearCurrent-edit', resultId: 'edit-result-current' }
        ];
        
        inputs.forEach(function(item) {
            const input = document.getElementById(item.id);
            const resultSpan = document.getElementById(item.resultId);
            
            if (input && resultSpan && input.value && !input.readOnly) {
                let inputValue = input.value.replace(',', '.');
                let value = parseFloat(inputValue);
                if (isNaN(value)) value = 0;
                const tutValue = value * currentCoeff;
                let formattedResult = tutValue.toFixed(2).replace('.', ',');
                resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
            }
        });
    }
}

function setValueIfExists(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.value = value;
    }
}

class PlanEvents {
    constructor(token, eventType) {
        this.token = token;
        this.eventType = eventType;
        this.init();
    }

    async init() {
        await this.loadEvents();
        this.initTableContextMenu();
        this.initCollapseSections();
        this.initColumnResize();
    }

    async loadEvents() {
        try {
            const response = await fetch(`/api/events/${this.token}?type=${this.eventType}`);
            const data = await response.json();
            
            if (data.success) {
                this.originalEvents = data.original_events;
                this.eventsWithChanges = data.events_with_changes;
                this.periodMetrics = data.period_metrics;
                this.totalMetrics = data.total_metrics;
                this.directions = data.directions;
                
                this.renderOriginalEvents();
                this.renderEventsWithChanges();
                this.updateTotalMetrics();
            } else {
                this.showError('Ошибка загрузки данных');
            }
        } catch (error) {
            console.error('Error loading events:', error);
            this.showError('Ошибка загрузки данных');
        }
    }

    getPartNumber() {
        return this.eventType === 'saving' ? '2' : '3';
    }

    renderOriginalEvents() {
        const tbody = document.getElementById('non-local-content');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (!this.originalEvents || this.originalEvents.length === 0) {
            const emptyMessage = this.eventType === 'saving' 
                ? 'Нет мероприятий по экономии ТЭР' 
                : 'Нет мероприятий по увеличению использования местных ТЭР';
            tbody.innerHTML = `<tr class="no-results-row"><td colspan="18">${emptyMessage}</tr>`;
            return;
        }
        
        this.originalEvents.forEach((row, index) => {
            const tr = this.createEventRow(row, index);
            tbody.appendChild(tr);
        });
        
        this.addTotalRow(tbody, this.originalEvents);
    }

    renderEventsWithChanges() {
        const tbody = document.getElementById('local-content');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (!this.eventsWithChanges || this.eventsWithChanges.length === 0) {
            const emptyMessage = this.eventType === 'saving'
                ? 'Отсутствуют мероприятия по экономии ТЭР (включенные в план при внесении в него изменений)'
                : 'Отсутствуют мероприятия по увеличению использования местных ТЭР (включенные в перечень при внесении в него изменений)';
            tbody.innerHTML = `<tr class="no-results-row"><td colspan="18">${emptyMessage}</tr>`;
            return;
        }
        
        this.eventsWithChanges.forEach((row, index) => {
            const tr = this.createEventRow(row, index);
            tbody.appendChild(tr);
        });
        
        this.addTotalRow(tbody, this.eventsWithChanges);
    }

    createEventRow(row, index) {
        const tr = document.createElement('tr');
        tr.className = 'menu-row';
        tr.setAttribute('data-id', row.id);
        
        tr.innerHTML = `
            <td style="text-align: center;">${index + 1}</td>
            <td style="text-align: center;">${this.escapeHtml(row.display_code || row.direction_code)}</td>
            <td style="text-align: start;">${this.escapeHtml(row.name)}</td>
            <td style="text-align: center;">${this.escapeHtml(row.unit_name)}</td>
            <td style="text-align: end;">${this.formatNumber(row.Volume)}</td>
            <td style="text-align: end;">${this.formatNumber(row.EffTut)}</td>
            <td style="text-align: end;">${this.formatNumber(row.EffRub)}</td>
            <td style="text-align: center;">${row.ExpectedQuarter || ''}</td>
            <td style="text-align: end;">${this.formatNumber(row.EffCurrYear)}</td>
            <td style="text-align: end;">${this.formatNumber(row.Payback)}</td>
            <td style="text-align: end;">${this.formatNumber(row.VolumeFin)}</td>
            <td style="text-align: end;">${this.formatNumber(row.BudgetState)}</td>
            <td style="text-align: end;">${this.formatNumber(row.BudgetRep)}</td>
            <td style="text-align: end;">${this.formatNumber(row.BudgetLoc)}</td>
            <td style="text-align: end;">${this.formatNumber(row.BudgetOther)}</td>
            <td style="text-align: end;">${this.formatNumber(row.MoneyOwn)}</td>
            <td style="text-align: end;">${this.formatNumber(row.MoneyLoan)}</td>
            <td style="text-align: end;">${this.formatNumber(row.MoneyOther)}</td>
        `;
        
        return tr;
    }

    addTotalRow(tbody, events) {
        if (events.length === 0) return;
        
        const totalRow = document.createElement('tr');
        totalRow.className = 'total-row';
        totalRow.innerHTML = `
            <td style="text-align: left; padding-left: 60px" colspan="4">Итого по разделу:</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(events, 'EffTut').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'EffRub').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(events, 'EffCurrYear').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(events, 'VolumeFin').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'BudgetState').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'BudgetRep').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'BudgetLoc').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'BudgetOther').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'MoneyOwn').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'MoneyLoan').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(events, 'MoneyOther').toFixed(2).replace('.', ',')}</td>
        `;
        tbody.appendChild(totalRow);
    }

    sumEvents(events, field) {
        return events.reduce((sum, event) => sum + (parseFloat(event[field]) || 0), 0);
    }

    updateTotalMetrics() {
        const otherContent = document.getElementById('other-content');
        if (!otherContent) return;
        
        otherContent.innerHTML = '';
        
        const allEvents = [...(this.originalEvents || []), ...(this.eventsWithChanges || [])];
        const partNumber = this.getPartNumber();
        
        const totalRow = document.createElement('tr');
        totalRow.className = 'total-row';
        totalRow.innerHTML = `
            <td colspan="3">Всего по части ${partNumber}, в том числе:</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'Volume').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'EffTut').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'EffRub').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'EffCurrYear').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'VolumeFin').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'BudgetState').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'BudgetRep').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'BudgetLoc').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'BudgetOther').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'MoneyOwn').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'MoneyLoan').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'MoneyOther').toFixed(2).replace('.', ',')}</td>
        `;
        otherContent.appendChild(totalRow);
        
        const periods = [
            { code: '0001', name: 'Январь-Март' },
            { code: '0002', name: 'Январь-Июнь' },
            { code: '0003', name: 'Январь-Сентябрь' },
            { code: '0004', name: 'Январь-Декабрь' }
        ];
        
        periods.forEach(period => {
            const periodData = this.periodMetrics && this.periodMetrics[period.code];
            const eventId = periodData ? periodData.id : null;
            const effValue = periodData ? periodData.eff_curr_year : 0;
            
            const row = document.createElement('tr');
            row.className = 'menu-row';
            if (eventId) {
                row.setAttribute('data-id', eventId);
            }
            row.setAttribute('data-period-code', period.code);
            row.setAttribute('data-period-name', period.name);
            row.innerHTML = `
                <td colspan="8">${period.name}</td>
                <td style="text-align: end;" class="period-eff-value">${this.formatNumber(effValue)}</td>
                <td colspan="9"></td>
            `;
            
            otherContent.appendChild(row);
        });
    }

    initTableContextMenu() {
        const eventTable = document.getElementById('eventTable');
        const eventMenu = document.getElementById('MenuMainTable');
        
        if (eventTable && eventMenu && typeof TableContextMenu !== 'undefined') {
            if (window.eventTableMenu) {
                window.eventTableMenu = null;
            }
            
            window.eventTableMenu = new TableContextMenu('eventTable', 'MenuMainTable', {
                contextEditButtonId: 'contextEditButton',
                contextDeleteButtonId: 'contextDeleteButton',
                tableEditButtonId: 'tableEditButton',
                tableDeleteButtonId: 'tableDeleteButton',
                removeUrlTemplate: '/plans/plan/delete-eventes/{id}',
                immutableCodes: [],
                immutableEditCodes: [],
                immutableDeleteCodes: ['0001', '0002', '0003', '0004'],
                codeColumnIndex: 11,
                hideCodeColumn: true,
                additionalContainers: ['other-content']
            });
        }
    }

    initCollapseSections() {
        if (typeof TableCollapseManager !== 'undefined') {
            TableCollapseManager.init();
        }
    }

    initColumnResize() {
        const table = document.querySelector('.main-table');
        if (!table) return;
        
        const thElements = table.querySelectorAll('th.resizable');
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        let currentTh = null;

        thElements.forEach(th => {
            const resizer = th.querySelector('.resizer');
            if (resizer) {
                resizer.addEventListener('mousedown', function(e) {
                    isResizing = true;
                    startX = e.clientX;
                    startWidth = th.offsetWidth;
                    currentTh = th;
                    document.body.style.cursor = 'col-resize';
                    e.preventDefault();
                });
            }
        });

        document.addEventListener('mousemove', function(e) {
            if (isResizing && currentTh) {
                const newWidth = startWidth + (e.clientX - startX);
                currentTh.style.width = newWidth + 'px';
                currentTh.style.minWidth = newWidth + 'px';
            }
        });

        document.addEventListener('mouseup', function() {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                currentTh = null;
            }
        });
    }

    formatNumber(value) {
        if (value === null || value === undefined) return '0,00';
        const num = parseFloat(value);
        if (isNaN(num)) return '0,00';
        return num.toFixed(2).replace('.', ',');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        const container = document.querySelector('.table-container');
        if (container) {
            container.innerHTML = `<div class="error-message" style="text-align: center; padding: 40px; color: red;">${message}</div>`;
        }
    }
}

class EventModal {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        if (!this.modal) return;

        this.progressBar = this.modal.querySelector('#modal-progress-bar');

        this.stepEls = Array.from(this.modal.querySelectorAll('[id^="step"]'))
            .filter(el => /^step\d+$/.test(el.id))
            .sort((a, b) => parseInt(a.id.slice(4), 10) - parseInt(b.id.slice(4), 10));

        this.totalSteps = this.stepEls.length || 1;
        this.currentStep = 1;

        this.buttons = {
            step1Next: this.modal.querySelector('#step1-next-btn'),
            step2Back: this.modal.querySelector('#step2-back-btn'),
            step2Next: this.modal.querySelector('#step2-next-btn'),
            step3Back: this.modal.querySelector('#step3-back-btn'),
            step3Next: this.modal.querySelector('#step3-next-btn')
        };

        this.init();
    }

    init() {
        this.buttons.step1Next?.addEventListener('click', () => this.nextStep());
        this.buttons.step2Back?.addEventListener('click', () => this.prevStep());
        this.buttons.step2Next?.addEventListener('click', () => this.nextStep());
        this.buttons.step3Back?.addEventListener('click', () => this.prevStep());
        this.buttons.step3Next?.addEventListener('click', () => this.submitForm());
    }

    activeStepEl() {
        return this.stepEls[this.currentStep - 1];
    }

    updateProgressBar() {
        if (!this.progressBar) return;
        const progress = (this.currentStep / this.totalSteps) * 100;
        this.progressBar.style.width = progress + '%';
    }

    nextStep() {
        if (this.currentStep >= this.totalSteps) return;
        this.activeStepEl().style.display = 'none';
        this.currentStep++;
        this.activeStepEl().style.display = 'block';
        this.updateProgressBar();
    }

    prevStep() {
        if (this.currentStep <= 1) return;
        this.activeStepEl().style.display = 'none';
        this.currentStep--;
        this.activeStepEl().style.display = 'block';
        this.updateProgressBar();
    }

    validateStep1() { return true; }
    validateStep2() { return true; }

    submitForm() {}

    close() {
        this.modal.style.display = 'none';
    }

    resetForm() {
        this.stepEls.forEach((el, i) => el.style.display = i === 0 ? 'block' : 'none');
        this.currentStep = 1;
        this.updateProgressBar();
    }
}

class TableContextMenu {
    constructor(tableId, menuId, options = {}) {
        this.table = document.getElementById(tableId);
        this.menu = document.getElementById(menuId);
        this.selectedRow = null;
        
        this.contextDeleteButton = options.contextDeleteButtonId ? document.getElementById(options.contextDeleteButtonId) : null;
        this.contextEditButton = options.contextEditButtonId ? document.getElementById(options.contextEditButtonId) : null;
        
        this.tableDeleteButton = options.tableDeleteButtonId ? document.getElementById(options.tableDeleteButtonId) : null;
        this.tableEditButton = options.tableEditButtonId ? document.getElementById(options.tableEditButtonId) : null;
        
        this.editCallback = options.editCallback || null;
        this.removeCallback = options.removeCallback || null;
        this.removeUrlTemplate = options.removeUrlTemplate || null;
        
        this.immutableCodes = options.immutableCodes || [];
        this.immutableEditCodes = options.immutableEditCodes || [];
        this.immutableDeleteCodes = options.immutableDeleteCodes || [];
        this.codeColumnIndex = options.codeColumnIndex || 0;
        this.hideCodeColumn = options.hideCodeColumn !== false;
        this.additionalContainers = options.additionalContainers || [];

        if (!this.table || !this.menu) return;
        this.init();
    }

    init() {
        if (this.hideCodeColumn) {
            this.hideCodeColumnInTable();
        }

        const selectors = ['tbody.rows tr.menu-row', 'tr.group-header'];
        this.additionalContainers.forEach(containerId => {
            const container = document.getElementById(containerId);
            if (container) {
                selectors.push(`#${containerId} tr.menu-row`);
                if (!container.classList.contains('rows')) {
                    selectors.push(`#${containerId}.rows tr.menu-row`);
                }
            }
        });
        
        selectors.forEach(selector => {
            this.table.querySelectorAll(selector).forEach(row => {
                row.removeEventListener('contextmenu', this.onRowRightClick.bind(this));
                row.removeEventListener('click', this.onRowLeftClick.bind(this));
                row.addEventListener('contextmenu', (event) => this.onRowRightClick(event, row));
                row.addEventListener('click', (event) => this.onRowLeftClick(event, row));
            });
        });
        
        document.addEventListener('click', (event) => {
            if (!this.menu.contains(event.target)) {
                this.hideMenu();
            }
        });

        if (this.contextEditButton) {
            this.contextEditButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.isRowActive() && this.editCallback && !this.isEditDisabled(this.selectedRow)) {
                    this.editCallback(this.selectedRow.dataset.id);
                }
            });
        }

        if (this.contextDeleteButton) {
            this.contextDeleteButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.isRowActive() && !this.isDeleteDisabled(this.selectedRow)) {
                    this.showConfirmModal(this.selectedRow.dataset.id);
                }
            });
        }

        if (this.tableEditButton) {
            this.tableEditButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.isRowActive() && this.editCallback && !this.isEditDisabled(this.selectedRow)) {
                    this.editCallback(this.selectedRow.dataset.id);
                }
            });
        }

        if (this.tableDeleteButton) {
            this.tableDeleteButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.isRowActive() && !this.isDeleteDisabled(this.selectedRow)) {
                    this.showConfirmModal(this.selectedRow.dataset.id);
                }
            });
        }

        this.updateButtonsState();
    }

    hideCodeColumnInTable() {
        const headerCells = this.table.querySelectorAll('thead th');
        if (headerCells.length > this.codeColumnIndex) {
            headerCells[this.codeColumnIndex].classList.add('hidden-column');
        }
        
        const rows = this.table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length > this.codeColumnIndex) {
                cells[this.codeColumnIndex].classList.add('hidden-column');
            }
        });
    }

    getRowCode(row) {
        const periodCode = row.getAttribute('data-period-code');
        if (periodCode) {
            return periodCode;
        }
        
        const cells = row.querySelectorAll('td');
        if (cells.length > this.codeColumnIndex) {
            return cells[this.codeColumnIndex].textContent.trim();
        }
        return null;
    }

    isEditDisabled(row) {
        if (!row) return true;
        const rowCode = this.getRowCode(row);
        return this.immutableCodes.includes(rowCode) || this.immutableEditCodes.includes(rowCode);
    }

    isDeleteDisabled(row) {
        if (!row) return true;
        const rowCode = this.getRowCode(row);
        return this.immutableCodes.includes(rowCode) || this.immutableDeleteCodes.includes(rowCode);
    }

    isRowActive() {
        return this.selectedRow && this.selectedRow.classList.contains('active-row');
    }

    updateButtonsState() {
        const isActive = this.isRowActive();
        const isEditDisabled = this.isEditDisabled(this.selectedRow);
        const isDeleteDisabled = this.isDeleteDisabled(this.selectedRow);
        
        const allButtons = [
            this.contextEditButton,
            this.contextDeleteButton,
            this.tableEditButton,
            this.tableDeleteButton
        ];
        
        allButtons.forEach(button => {
            if (button) {
                if (!isActive) {
                    button.classList.add('btn-disabled');
                } else {
                    const isEditButton = button === this.contextEditButton || button === this.tableEditButton;
                    const isDeleteButton = button === this.contextDeleteButton || button === this.tableDeleteButton;
                    
                    if (isEditButton && isEditDisabled) {
                        button.classList.add('btn-disabled');
                    } else if (isEditButton && !isEditDisabled) {
                        button.classList.remove('btn-disabled');
                    } else if (isDeleteButton && isDeleteDisabled) {
                        button.classList.add('btn-disabled');
                    } else if (isDeleteButton && !isDeleteDisabled) {
                        button.classList.remove('btn-disabled');
                    }
                }
            }
        });
    }

    onRowLeftClick(event, row) {
        event.stopPropagation();
        
        if (row.classList.contains('active-row')) {
            row.classList.remove('active-row');
            this.selectedRow = null;
        } else {
            if (this.selectedRow && this.selectedRow !== row) {
                this.selectedRow.classList.remove('active-row');
            }
            row.classList.add('active-row');
            this.selectedRow = row;
        }
        
        const isPeriodRow = row.closest('#other-content') !== null || row.classList.contains('group-header');
        
        // Небольшая задержка, чтобы DOM обновился
        setTimeout(() => {
            if (isPeriodRow) {
                if (typeof Edit_Period_modal === 'function') {
                    Edit_Period_modal();
                }
            } else {
                const editEventModal = document.getElementById('EditEventModal');
                if (editEventModal) {
                    if (typeof Edit_Evente_modal === 'function') {
                        Edit_Evente_modal();
                    }
                }
            }
        }, 10);

        const editIndicatorModal = document.getElementById('EditIndicatorModal');
        if (editIndicatorModal) {
            if (typeof Edit_indicator_modal === 'function') {
                Edit_indicator_modal();
            }
        }

        this.updateButtonsState();
        this.hideContextMenu();
    }

    onRowRightClick(event, row) {
        event.preventDefault();
        event.stopPropagation();

        if (this.selectedRow && this.selectedRow !== row) {
            this.selectedRow.classList.remove('active-row');
        }

        row.classList.add('active-row');
        this.selectedRow = row;

        if (!this.isDeleteDisabled(row) && this.removeUrlTemplate) {
            const removeForm = this.menu.querySelector('form#removeForm');
            if (removeForm) {
                removeForm.action = this.removeUrlTemplate.replace('{id}', row.dataset.id);
            }
        }
        
        const isPeriodRow = row.closest('#other-content') !== null || row.classList.contains('group-header');
        
        if (isPeriodRow) {
            if (typeof Edit_Period_modal === 'function') {
                Edit_Period_modal();
            }
        } else {
            const editEventModal = document.getElementById('EditEventModal');
            if (editEventModal) {
                if (typeof Edit_Evente_modal === 'function') {
                    Edit_Evente_modal();
                }
            }
        }

        const editIndicatorModal = document.getElementById('EditIndicatorModal');
        if (editIndicatorModal) {
            if (typeof Edit_indicator_modal === 'function') {
                Edit_indicator_modal();
            }
        }
        
        this.updateButtonsState();
        this.showMenu(event.pageX, event.pageY);
    }

    showMenu(x, y) {
        this.menu.style.top = `${y}px`;
        this.menu.style.left = `${x}px`;
        this.menu.style.display = 'flex';
    }

    hideMenu() {
        this.hideContextMenu();
    }
    
    hideContextMenu() {
        this.menu.style.display = 'none';
    }

    showConfirmModal(rowId) {
        if (this.isDeleteDisabled(this.selectedRow)) {
            return;
        }

        const modal = document.getElementById('confirmModal');
        if (!modal) return;

        const yesBtn = modal.querySelector('#confirmYesdelete');
        const noBtn = modal.querySelector('#confirmNodelete');

        modal.classList.add('active');

        yesBtn.onclick = null;
        noBtn.onclick = null;

        yesBtn.onclick = () => {
            modal.classList.remove('active');
            
            if (this.removeCallback) {
                this.removeCallback(rowId);
            } else if (this.removeUrlTemplate) {
                this.submitForm(this.removeUrlTemplate.replace('{id}', rowId));
            }
        };

        noBtn.onclick = () => {
            modal.classList.remove('active');
        };

        window.onclick = (event) => {
            if (event.target === modal) {
                modal.classList.remove('active');
            }
        };
    }

    submitForm(url) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url;
        form.style.display = 'none';
        
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token'; 
            csrfInput.value = csrfToken.content;
            form.appendChild(csrfInput);
        }

        document.body.appendChild(form);
        form.submit();
    }
}

const TableCollapseManager = (function() {
    let isInitialized = false;
    let groupHeaders = [];

    function toggleContent(header) {
        const targetId = header.getAttribute('data-target');
        const target = document.getElementById(targetId);
        
        if (target) {
            if (target.style.display === 'none') {
                target.style.display = 'table-row-group';
                const arrow = header.querySelector('.dropdown-arrow');
                if (arrow) {
                    arrow.style.transform = 'rotate(0deg)';
                    arrow.style.transition = 'transform 0.3s ease';
                }
            } else {
                target.style.display = 'none';
                const arrow = header.querySelector('.dropdown-arrow');
                if (arrow) {
                    arrow.style.transform = 'rotate(-90deg)';
                    arrow.style.transition = 'transform 0.3s ease';
                }
            }
        }
    }
    
    function initHeaders() {
        groupHeaders = document.querySelectorAll('.group-header');
        
        groupHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            
            const isCollapsed = header.getAttribute('data-collapsed') === 'true';
            const targetId = header.getAttribute('data-target');
            const target = document.getElementById(targetId);
            
            if (isCollapsed && target) {
                target.style.display = 'none';
                const arrow = header.querySelector('.dropdown-arrow');
                if (arrow) {
                    arrow.style.transform = 'rotate(-90deg)';
                    arrow.style.transition = 'transform 0.3s ease';
                }
            }
            
            header.addEventListener('click', function() {
                toggleContent(this);
            });
            
            header.addEventListener('mouseenter', function() {
                this.style.backgroundColor = '#f5f5f5';
            });
            
            header.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
        });
    }
    
    return {
        init: function(options = {}) {
            if (isInitialized) {
                return;
            }
            
            const config = {
                autoInit: options.autoInit !== false,
                initiallyCollapsed: options.initiallyCollapsed || [],
                ...options
            };
            
            if (config.autoInit) {
                this.initializeAll();
            }
            
            if (config.initiallyCollapsed && config.initiallyCollapsed.length > 0) {
                config.initiallyCollapsed.forEach(sectionId => {
                    this.collapseSection(sectionId);
                });
            }
            
            isInitialized = true;
        },
        
        initializeAll: function() {
            initHeaders();
        },
        
        collapseSection: function(sectionId) {
            const header = document.querySelector(`[data-target="${sectionId}"]`);
            const target = document.getElementById(sectionId);
            
            if (header && target && target.style.display !== 'none') {
                toggleContent(header);
            }
        },
        
        expandSection: function(sectionId) {
            const header = document.querySelector(`[data-target="${sectionId}"]`);
            const target = document.getElementById(sectionId);
            
            if (header && target && target.style.display === 'none') {
                toggleContent(header);
            }
        },
        
        toggleSection: function(sectionId) {
            const header = document.querySelector(`[data-target="${sectionId}"]`);
            if (header) {
                toggleContent(header);
            }
        },
        
        getSectionState: function(sectionId) {
            const target = document.getElementById(sectionId);
            return target ? target.style.display !== 'none' : null;
        },
        
        destroy: function() {
            groupHeaders.forEach(header => {
                const newHeader = header.cloneNode(true);
                header.parentNode.replaceChild(newHeader, header);
            });
            
            groupHeaders = [];
            isInitialized = false;
        },
        
        isInitialized: function() {
            return isInitialized;
        },
        
        getSections: function() {
            const sections = [];
            groupHeaders.forEach(header => {
                const targetId = header.getAttribute('data-target');
                sections.push({
                    id: targetId,
                    header: header,
                    content: document.getElementById(targetId),
                    isExpanded: this.getSectionState(targetId)
                });
            });
            return sections;
        }
    };
})();

const STATUS_CONFIG = {
    'plan-cont-redac': { width: '20%', color: 'var(--color-redaced)' },
    'plan-cont-control': { width: '40%', color: 'var(--color-controled)' },
    'plan-cont-sent': { width: '60%', color: 'var(--color-sented)' },
    'plan-cont-eror': { width: '80%', color: 'var(--color-erorsed)' },
    'plan-cont-sub': { width: '100%', color: 'var(--color-submited)' }
};

function initStatusProgress() {
    const planConts = document.querySelectorAll('.plan-cont');
    const progressLine = document.querySelector('.progress-line-active');
    const dots = document.querySelectorAll('.status-dot');

    if (!planConts.length || !progressLine || !dots.length) {
        console.warn('Не найдены необходимые элементы для прогресс-бара');
        return;
    }

    const handleMouseEnter = (event) => {
        const planCont = event.currentTarget;
        
        for (const [className, config] of Object.entries(STATUS_CONFIG)) {
            if (planCont.classList.contains(className)) {
                progressLine.style.width = config.width;
                progressLine.style.background = config.color;
                
                const activeIndex = Object.keys(STATUS_CONFIG).indexOf(className);
                const activeColor = STATUS_CONFIG[className].color;
                
                dots.forEach((dot, index) => {
                    dot.style.background = index <= activeIndex ? activeColor : 'var(--border-color)';
                });
                break;
            }
        }
    };

    const handleMouseLeave = () => {
        progressLine.style.width = '0';
        dots.forEach(dot => {
            dot.style.background = 'var(--border-color)';
        });
    };

    planConts.forEach(planCont => {
        planCont.addEventListener('mouseenter', handleMouseEnter);
        planCont.addEventListener('mouseleave', handleMouseLeave);
    });
}

function Edit_Period_modal() {
    const EditEventModal = document.getElementById('EditEventModal');
    if (!EditEventModal) {
        console.log('Edit_Period_modal: EditEventModal не найден, выход');
        return;
    }

    const activeRow = document.querySelector('.active-row');
    if (!activeRow) {
        console.log('Edit_Period_modal: activeRow не найден, выход');
        return;
    }
    
    const periodCode = activeRow.getAttribute('data-period-code');
    if (!periodCode || !['0001', '0002', '0003', '0004'].includes(periodCode)) {
        return;
    }
    
    const idEvent = activeRow.getAttribute('data-id');
    if (!idEvent) {
        console.log('Edit_Period_modal: idEvent не найден, выход');
        return;
    }

    const modalTitle = document.getElementById('modal-title');
    const stepsedit = document.getElementById('steps-edit');
    const periodStep = document.getElementById('period-step');
    const editTypeInput = document.getElementById('edit-event-type');
    if (stepsedit) stepsedit.style.display = 'none';
    
    if (periodStep) periodStep.style.display = 'block';
    
    if (editTypeInput) {
        editTypeInput.value = 'period';
    }
    
    const periodName = activeRow.getAttribute('data-period-name') || 
                      activeRow.querySelector('td:first-child')?.textContent.trim() || 
                      getPeriodNameByCode(periodCode);
    
    const periodNameDisplay = document.getElementById('period-name-display');
    if (periodNameDisplay) {
        periodNameDisplay.textContent = periodName;
    }
    
    fetch(`/api/get-event/${idEvent}`)
        .then(response => {
            // console.log('Edit_Period_modal: fetch ответ получен, status =', response.status);
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
    
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
                
                allInputs.forEach(input => {
                    input.disabled = true;
                });
                
                const periodInputs = form.querySelectorAll('#period-step input, #period-step select, #period-step textarea');
                periodInputs.forEach(input => {
                    input.disabled = false;
                });
            }

        })
        .catch(error => {
            console.error('Edit_Period_modal: ОШИБКА:', error);
            alert('Ошибка при загрузке данных периода: ' + error.message);
        });
}

function Edit_Evente_modal() {
    const EditEventModal = document.getElementById('EditEventModal');
    if (!EditEventModal) return;

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
    
    if (!activeRow) return;
    
    const idEvent = activeRow.getAttribute('data-id');
    if (!idEvent) return;

    const periodCode = activeRow.getAttribute('data-period-code');

    const isPeriod = periodCode && ['0001', '0002', '0003', '0004'].includes(periodCode);
    // console.log('activeRow HTML:', activeRow.outerHTML);
    if (isPeriod) {
        console.log('Вызов Edit_Period_modal для периода');
        Edit_Period_modal();
        return;
    }
    
    const modalTitle = document.getElementById('modal-title');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const periodStep = document.getElementById('period-step');
    const editType = document.getElementById('edit-event-type');
    const nextButton = document.getElementById('step1-next-btn');
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
        allInputs.forEach(input => {
            input.disabled = false;
        });
    }
    
    if (nextButton) nextButton.disabled = true;
    
    fetch(`/api/get-event/${idEvent}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);

            setValueIfExists('change-name-edit-model', data.name || '');
            setValueIfExists('change-Volume-edit-model', data.Volume || '');
            setValueIfExists('change-EffTut-edit-model', data.EffTut || '');
            setValueIfExists('change-EffRub-edit-model', data.EffRub || '');
            setValueIfExists('change-ExpectedQuarter-edit-model', data.ExpectedQuarter || '');
            setValueIfExists('change-EffCurrYear-edit-model', data.EffCurrYear || '');
            setValueIfExists('change-Payback-edit-model', data.Payback || '');
            setValueIfExists('change-VolumeFin-edit-model', data.VolumeFin || '');
            setValueIfExists('change-BudgetState-edit-model', data.BudgetState || '');
            setValueIfExists('change-BudgetRep-edit-model', data.BudgetRep || '');
            setValueIfExists('change-BudgetLoc-edit-model', data.BudgetLoc || '');
            setValueIfExists('change-BudgetOther-edit-model', data.BudgetOther || '');
            setValueIfExists('change-MoneyOwn-edit-model', data.MoneyOwn || '');
            setValueIfExists('change-MoneyLoan-edit-model', data.MoneyLoan || '');
            setValueIfExists('change-MoneyOther-edit-model', data.MoneyOther || '');
            
            if (form) {
                form.action = `/plans/plan/edit-event/${idEvent}`;
            }
            
            if (nextButton) nextButton.disabled = false;
        })
        .catch(error => {
            console.error('Error fetching Event data:', error);
            alert('Ошибка при загрузке данных мероприятия: ' + error.message);
            if (nextButton) nextButton.disabled = false;
        });
}

function getPeriodNameByCode(code) {
    const periodNames = {
        '0001': 'Январь-Март',
        '0002': 'Январь-Июнь',
        '0003': 'Январь-Сентябрь',
        '0004': 'Январь-Декабрь'
    };
    return periodNames[code] || 'Период';
}

function setValueIfExists(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.value = value;
    }
}

function initExportPage() {
    const form = document.getElementById("exportForm");
    const formatInput = document.getElementById("selectedFormat");
    const checkboxes = document.querySelectorAll('input[name="ids"]');
    const exportBtn = document.getElementById("exportBtn");
    const selectAllBtn = document.getElementById("selectAllBtn");

    function updateButtonState() {
        const formatSelected = !!formatInput.value;
        const planSelected = Array.from(checkboxes).some(cb => cb.checked);
        exportBtn.disabled = !(formatSelected && planSelected);
        form.action = formatSelected ? `/export-to/${formatInput.value}` : "";
    }

    document.querySelectorAll(".export-choose").forEach(item => {
        item.addEventListener("click", () => {
            document.querySelectorAll(".export-choose").forEach(el => el.classList.remove("active"));
            item.classList.add("active");
            formatInput.value = item.dataset.format;
            updateButtonState();
        });
    });

    if (selectAllBtn) {
        selectAllBtn.addEventListener("change", () => {
            checkboxes.forEach(cb => cb.checked = selectAllBtn.checked);
            updateButtonState();
        });
    }

    checkboxes.forEach(cb => cb.addEventListener("change", updateButtonState));
    updateButtonState();
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
    const submitBtn = document.getElementById('submit-indicator-btn');
    const categoryRadios = document.querySelectorAll('input[name="fuel_category"]');
    
    if (!selectedIndicatorName || !categorySection) return;
    
    const indicatorText = selectedIndicatorName.textContent;
    const isCategoryRequired = indicatorText.includes('2023') || indicatorText.includes('2024');
    
    if (isCategoryRequired) {
        categorySection.style.display = 'block';
        
        function validateCategory() {
            const isChecked = Array.from(categoryRadios).some(radio => radio.checked);
            if (submitBtn) {
                submitBtn.disabled = !isChecked;
            }
        }
        
        categoryRadios.forEach(radio => {
            radio.removeEventListener('change', validateCategory);
            radio.addEventListener('change', validateCategory);
        });
        
        validateCategory();
    } else {
        categorySection.style.display = 'none';
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }
}

class CertificateUploadHandler {
    constructor() {
        this.form = document.getElementById('sentForm');
        this.dropArea = document.getElementById('drop-certificate-area');
        this.fileInput = document.getElementById('certificate-to-check');
        this.submitButton = document.getElementById('submit-sent-button');
        
        this.init();
    }

    init() {
        if (!this.form || !this.dropArea || !this.fileInput || !this.submitButton) {
            console.error('Required elements not found');
            return;
        }

        this.bindEvents();
        this.updateSubmitButtonState(false);
    }

    bindEvents() {
        this.dropArea.addEventListener('dragover', this.handleDragOver.bind(this));
        this.dropArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        this.dropArea.addEventListener('drop', this.handleDrop.bind(this));
        this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));
        
        this.dropArea.addEventListener('click', (e) => {
            if (e.target === this.dropArea || e.target.closest('.drop-certificate-content')) {
                e.preventDefault();
                this.fileInput.click();
            }
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        this.dropArea.classList.add('drag-over');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.dropArea.classList.remove('drag-over');
    }

    handleDrop(e) {
        e.preventDefault();
        this.dropArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.fileInput.files = files;
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    processFile(file) {
        this.clearError();

        if (!this.isValidFile(file)) {
            this.showError('Неверный формат файла. Разрешены только файлы .cer');
            this.resetFileInput();
            this.resetFileDisplay();
            this.updateSubmitButtonState(false);
            return;
        }

        this.showFileDisplay(file.name);
        this.updateSubmitButtonState(true);
    }

    isValidFile(file) {
        const fileName = file.name.toLowerCase();
        return fileName.endsWith('.cer');
    }

    showFileDisplay(fileName) {
        const textElement = this.dropArea.querySelector('.drop-certificate-text');
        if (textElement) {
            textElement.innerHTML = `<strong>${this.escapeHtml(fileName)}</strong>`;
        }
        this.dropArea.classList.add('has-file');
    }

    resetFileDisplay() {
        const textElement = this.dropArea.querySelector('.drop-certificate-text');
        if (textElement) {
            textElement.innerHTML = `Перетащите файл сертификата сюда или 
                <label for="certificate-to-check" class="drop-certificate-label">нажмите для выбора</label>`;
        }
        this.dropArea.classList.remove('has-file');
    }

    resetFileInput() {
        this.fileInput.value = '';
        this.fileInput.files = null;
    }

    updateSubmitButtonState(isEnabled) {
        this.submitButton.disabled = !isEnabled;
        
        if (isEnabled) {
            this.submitButton.classList.remove('disabled');
        } else {
            this.submitButton.classList.add('disabled');
        }
    }

    showError(message) {
        let errorDiv = this.dropArea.querySelector('.error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            this.dropArea.appendChild(errorDiv);
        }
        errorDiv.textContent = message;
        
        setTimeout(() => {
            this.clearError();
        }, 3000);
    }

    clearError() {
        const errorDiv = this.dropArea.querySelector('.error-message');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const formEventeForm = document.getElementById('editEventeForm');
    if (formEventeForm) {
        formEventeForm.addEventListener('submit', function(e) {
            const editType = document.getElementById('edit-event-type')?.value;
            if (editType === 'period') {
                const effCurrYearInput = document.getElementById('period-EffCurrYear-edit');
                const hiddenEffCurrYear = document.getElementById('change-EffCurrYear-edit-model');
                
                if (effCurrYearInput && hiddenEffCurrYear) {
                    let value = effCurrYearInput.value.replace(',', '.');
                    hiddenEffCurrYear.value = value;
                }
            }
        });
    }


    if (document.querySelector('.plan-cont')) {
        initStatusProgress();
    }

    if (document.getElementById('indicatorsTable') && document.getElementById('indicators-tbody')) {
        const token = document.getElementById('indicatorsTable')?.dataset?.token;
        if (token) {
            window.planIndicators = new PlanIndicators(token);
        }
    }
    
    if (document.getElementById('eventTable')) {
        const token = document.getElementById('eventTable')?.dataset?.token;
        const eventType = document.getElementById('eventTable')?.dataset?.eventType || 
                         (window.location.pathname.includes('saving') ? 'saving' : 'increase');
        if (token) {
            window.planEvents = new PlanEvents(token, eventType);
        }
    }

    if (document.getElementById('exportForm')) {
        initExportPage();
    }

    validateAndEnableButton();
    setInterval(validateAndEnableButton, 300);
    
    document.addEventListener('input', function(e) {
        if (e.target.matches('[name="name"], [name="Volume"], [name="ExpectedQuarter"]')) {
            validateAndEnableButton();
        }
    });

    if (document.querySelectorAll('.plan-cont')) {
        window.initPlansFilter();
    }

    const sentPlanButton = document.getElementById('sentPlanButton');
    const sentmodal = document.getElementById('sentmodal');
    if (sentmodal && sentPlanButton) {
        handleModal(sentmodal, sentPlanButton, sentmodal.querySelector('.close'));
    }

    if (document.getElementById('editPlanButton')) {
        initConfirmModal({
            triggerId: 'editPlanButton',
            formId: 'editPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    if (document.getElementById('controlPlanButton')) {
        const form = document.getElementById('controlPlanForm');
        const planType = form?.dataset?.planType;
        
        let modalText, modalTextSecond;
        
        if (planType === 'org_small') {
            modalText = 'Вами было указано что вы заполняете план <strong>до 25 тыс. т.</strong>';
            modalTextSecond = 'Вы действительно хотите пройти контроль плана? План сменит статус.';
        } else if (planType === 'org_large') {
            modalText = 'Вами было указано что вы заполняете план <strong>более 25 тыс. т.</strong>';
            modalTextSecond = 'Вы действительно хотите пройти контроль плана? План сменит статус.';
        } else {
            modalText = 'Вы действительно хотите пройти контроль?';
            modalTextSecond = 'План сменит статус.';
        }
        
        initConfirmModal({
            triggerId: 'controlPlanButton',
            formId: 'controlPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            textSecondId: 'modal-text-second',
            modalText: modalText,
            modalTextSecond: modalTextSecond
        });
    }

    if (document.querySelector('[data-modal-trigger="deletePlan"]')) {
        initConfirmModal({
            triggerButton: '[data-modal-trigger="deletePlan"]',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите удалить план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    if (document.getElementById('sent_mesPlanButton')) {
        initConfirmModal({
            triggerId: 'sent_mesPlanButton',
            formId: 'sent_mesPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отправить сообщение об ошибках пользователю?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Описывайте ошибки максимально подробно, для наилучшего восприятия со стороны пользователя.'
        });
    }

    if (document.getElementById('to_deletePlanButton')) {
        initConfirmModal({
            triggerId: 'to_deletePlanButton',
            formId: 'to_deletePlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите сменить статус плана на "Есть ошибки"?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус для последующего исправления ошибок.'
        });
    }

    if (document.getElementById('confirmPlanButton')) {
        initConfirmModal({
            triggerId: 'confirmPlanButton',
            formId: 'confirmPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите одобрить план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус и не будет подлежать последующей редакции или удалению со всех сторон.'
        });
    }

    if (document.getElementById('cancel_auditPlanButton')) {
        initConfirmModal({
            triggerId: 'cancel_auditPlanButton',
            formId: 'cancel_auditPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отменить изменения в статусе плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус обратно на "Не просмотренный". Отменить изменния можно только в течении 30-ти дней.'
        });
    }

    if (document.getElementById('logoutButton')) {
        initConfirmModal({
            triggerId: 'logoutButton',
            formId: 'logout_form',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите выйти из системы EnPlans?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить. Убедитесь, что вы сохранили свою работу.'
        });
    }

    if (document.getElementById('editprofileButton')) {
        initConfirmModal({
            triggerId: 'editprofileButton',
            formId: 'editprofileForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные профиля?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    const ticketsContainer = document.querySelector('.tickets-container');
    if (ticketsContainer) {
        function customSmoothScroll(element, targetPosition, duration = 800) {
            if (!element) return;
            
            const startPosition = element.scrollTop;
            const distance = targetPosition - startPosition;
            let startTime = null;

            function animation(currentTime) {
                if (startTime === null) startTime = currentTime;
                const timeElapsed = currentTime - startTime;
                const progress = Math.min(timeElapsed / duration, 1);
                
                const ease = progress < 0.5 
                    ? 4 * progress * progress * progress 
                    : 1 - Math.pow(-2 * progress + 2, 3) / 2;
                
                element.scrollTop = startPosition + distance * ease;
                
                if (timeElapsed < duration) {
                    requestAnimationFrame(animation);
                }
            }

            requestAnimationFrame(animation);
        }
        
        customSmoothScroll(ticketsContainer, ticketsContainer.scrollHeight);
    }

    const addEventModal = document.getElementById('AddEventModal');
    const addEventModal1 = new EventModal('AddEventModal');
    if (addEventModal && addEventModal1) {
        handleModal(addEventModal, document.getElementById('AddEventsModalBtn'), addEventModal.querySelector('.close'));
    }

    const editEventModal = document.getElementById('EditEventModal');
    const eventModal = new EventModal('EditEventModal');

    if (editEventModal && eventModal) {
        const tableEditButton = document.getElementById('tableEditButton');
        const contextEditButton = document.getElementById('contextEditButton');
        const closeButton = editEventModal.querySelector('.close');
        
        if (tableEditButton && closeButton) {
            handleModal(editEventModal, tableEditButton, closeButton);
        }
        
        if (contextEditButton && closeButton) {
            handleModal(editEventModal, contextEditButton, closeButton);
        }
    }

    const addIndicatorModal = document.getElementById('AddIndicatorModal');
    const IndicatorModal = new EventModal('AddIndicatorModal');
    if (addIndicatorModal && IndicatorModal) {
        handleModal(addIndicatorModal, document.getElementById('AddIndicatorModalButton'), addIndicatorModal.querySelector('.close'));
    }

    const editIndicatorModal = document.getElementById('EditIndicatorModal');
    if (editIndicatorModal) {
        handleModal(editIndicatorModal, document.getElementById('tableEditButton'), editIndicatorModal.querySelector('.close'));
        handleModal(editIndicatorModal, document.getElementById('contextEditButton'), editIndicatorModal.querySelector('.close'));
    }

    const orgUserModal = document.getElementById('orgUserModal');
    if (orgUserModal) {
        handleModal(orgUserModal, document.getElementById('orgUserbutton'), orgUserModal.querySelector('.close'));
    }
});