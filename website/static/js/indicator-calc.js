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
        const group = row.querySelector('td[data-group]')?.getAttribute('data-group') || '';
        
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
        
        const groupNumber = parseFloat(group);
        this.initAddNumericInputsByGroup(groupNumber);
        
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


    initAddNumericInputsByGroup(groupNumber) {
        const inputs = [
            document.querySelector('#AddIndicatorModal input[data-year="before"]'),
            document.querySelector('#AddIndicatorModal input[data-year="prev"]'),
            document.querySelector('#AddIndicatorModal input[data-year="current"]')
        ];
        
        inputs.forEach(input => {
            if (!input) return;
            
            let decimalPlaces = 0;
            let defaultValue = '0';
            
            if (groupNumber === 5) {
                decimalPlaces = 1;
                defaultValue = '0,0';
            } else if (groupNumber === 6 || groupNumber === 7 || groupNumber === 8) {
                decimalPlaces = 2;
                defaultValue = '0,00';
            } else {
                decimalPlaces = 0;
                defaultValue = '0';
            }
            
            const settings = {
                allowNegative: false,
                decimalPlaces: decimalPlaces,
                defaultValue: defaultValue
            };
            
            input.removeEventListener('input', input._addInputHandler);
            input.removeEventListener('focus', input._addFocusHandler);
            input.removeEventListener('blur', input._addBlurHandler);
            
            const inputHandler = (e) => { 
                NumericInputHandler.handleInput(e, settings);
                this.updateTutResults();
            };
            const focusHandler = (e) => { 
                NumericInputHandler.handleFocus(e, settings);
            };
            const blurHandler = (e) => { 
                NumericInputHandler.handleBlur(e, settings);
                this.updateTutResults();
            };
            
            input.addEventListener('input', inputHandler);
            input.addEventListener('focus', focusHandler);
            input.addEventListener('blur', blurHandler);
            input.addEventListener('click', (e) => { e.target.select(); });
            
            input._addInputHandler = inputHandler;
            input._addFocusHandler = focusHandler;
            input._addBlurHandler = blurHandler;
            
            if (decimalPlaces === 0) {
                input.placeholder = '0';
            } else if (decimalPlaces === 1) {
                input.placeholder = '0,0';
            } else {
                input.placeholder = '0,00';
            }
        });
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
        
        const activeRow = document.querySelector('[data-action="modal-table-main"] tbody tr.active-row');
        let groupValue = '';
        if (activeRow) {
            const groupDataCell = activeRow.querySelector('td[data-group]');
            if (groupDataCell) {
                groupValue = groupDataCell.getAttribute('data-group');
            }
        }
        const groupNumber = parseFloat(groupValue);
        
        const formatResultValue = (value, groupId) => {
            if (value === null || value === undefined || isNaN(value)) return '0';
            
            if (groupId === 5) {
                return value.toFixed(1).replace('.', ',');
            } else if (groupId === 6 || groupId === 7 || groupId === 8) {
                return value.toFixed(2).replace('.', ',');
            } else {
                return Math.round(value).toString().replace('.', ',');
            }
        };
        
        const years = ['before', 'prev', 'current'];
        years.forEach((year) => {
            const input = document.querySelector(`#AddIndicatorModal input[data-year="${year}"]`);
            const resultSpan = document.getElementById(`result-${year}`);
            
            if (input && resultSpan) {
                if (input.value) {
                    let inputValue = input.value.replace(',', '.');
                    let value = parseFloat(inputValue);
                    if (isNaN(value)) value = 0;
                    const tutValue = value * currentCoeff;
                    let formattedResult = formatResultValue(tutValue, groupNumber);
                    resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
                } else {
                    resultSpan.textContent = '= 0 т.у.т.';
                }
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
            tr.setAttribute('data-code', row.code);
            
            const formatValue = (value, groupId) => {
                if (value === null || value === undefined || isNaN(value)) return '';
                
                if (groupId === 5) {
                    return value.toFixed(1).replace('.', ',');
                } else if (groupId === 6 || groupId === 7 || groupId === 8) {
                    return value.toFixed(2).replace('.', ',');
                } else {
                    return Math.round(value).toString().replace('.', ',');
                }
            };
            
            tr.innerHTML = `
                <td style="text-align: center; display: none;">${index + 1}</td>
                <td style="text-align: center">${isNewGroup ? (Number.isInteger(row.group) ? row.group : row.group) : ''}</td>
                <td style="text-align: start">
                    ${this.escapeHtml(row.name)}${row.note ? ' (' + this.escapeHtml(row.note) + ')' : ''}
                </td>
                <td style="text-align: start">${this.escapeHtml(row.unit_name)}</td>
                <td>${(row.group === 5 || row.group === 6) ? 'x' : formatValue(row.QYearBeforePrev_unit, row.group)}</td>
                <td>${(row.group === 5 || row.group === 6) ? 'x' : formatValue(row.QYearBeforePrev_tut, row.group)}</td>
                <td>${(row.group === 5 || row.group === 6) ? 'x' : formatValue(row.QYearPrev_unit, row.group)}</td>
                <td>${(row.group === 5 || row.group === 6) ? 'x' : formatValue(row.QYearPrev_tut, row.group)}</td>
                <td>${formatValue(row.QYearCurrent_unit, row.group)}</td>
                <td>${formatValue(row.QYearCurrent_tut, row.group)}</td>
                <td class="difference-cell" style="border-right: none; ${row.difference < 0 ? 'background-color: rgb(96, 255, 122, 0.705);' : (row.difference > 0 ? 'background-color: rgb(255, 96, 96, 0.705);' : '')}">
                    ${(row.group === 5 || row.group === 6) ? 'x' : formatValue(row.difference, row.group)}
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
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: red;">${message}</td></tr>`;
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

    const groupNumber = parseFloat(groupValue);
    const isGroup5 = groupNumber === 5;
    const isGroup6 = groupNumber === 6;
    const isGroup7 = groupNumber === 7;
    const isGroup8 = groupNumber === 8;
    const isSpecialGroup = isGroup5 || isGroup6;

    const qYearCurrNoDisplay = document.getElementById('QYearCurr-edit-nodisplay');
    const QYearBeforePrevNoDisplay = document.getElementById('QYearBeforePrev-edit-nodisplay');
    const QYearCurrentCard = document.getElementById('QYearCurrent-edit-nodisplay');
    const editCategorySection = document.getElementById('edit-category-section');
    const editNameSection = document.getElementById('edit-name-section');
    const editNameInput = document.getElementById('edit-name-section-input');
    
    const initNumericInput = (inputElement, groupId) => {
        if (!inputElement) return;
        
        let decimalPlaces = 0;
        let defaultValue = '0';
        
        if (groupId === 5) {
            decimalPlaces = 1;
            defaultValue = '0,0';
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            decimalPlaces = 2;
            defaultValue = '0,00';
        } else {
            decimalPlaces = 0;
            defaultValue = '0';
        }
        
        const settings = {
            allowNegative: false,
            decimalPlaces: decimalPlaces,
            defaultValue: defaultValue
        };
        
        const inputHandler = function(e) { 
            NumericInputHandler.handleInput(e, settings);
            updateEditTutResults();
        };
        const focusHandler = function(e) { 
            NumericInputHandler.handleFocus(e, settings);
        };
        const blurHandler = function(e) { 
            NumericInputHandler.handleBlur(e, settings);
            updateEditTutResults();
        };
        
        inputElement.removeEventListener('input', inputElement._inputHandler);
        inputElement.removeEventListener('focus', inputElement._focusHandler);
        inputElement.removeEventListener('blur', inputElement._blurHandler);
        
        inputElement.addEventListener('input', inputHandler);
        inputElement.addEventListener('focus', focusHandler);
        inputElement.addEventListener('blur', blurHandler);
        inputElement.addEventListener('click', function(e) { e.target.select(); });
        
        inputElement._inputHandler = inputHandler;
        inputElement._focusHandler = focusHandler;
        inputElement._blurHandler = blurHandler;
    };
    
    const formatDisplayValue = (value, groupId) => {
        if (value === null || value === undefined || isNaN(value)) return '';
        
        if (groupId === 5) {
            return value.toFixed(1).replace('.', ',');
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            return value.toFixed(2).replace('.', ',');
        } else {
            return Math.round(value).toString().replace('.', ',');
        }
    };
    
    const beforePrevInput = document.getElementById('QYearBeforePrev-edit');
    const prevInput = document.getElementById('QYearCurr-edit');
    const currentInput = document.getElementById('QYearCurrent-edit');
    
    initNumericInput(beforePrevInput, groupNumber);
    initNumericInput(prevInput, groupNumber);
    initNumericInput(currentInput, groupNumber);
    
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
            
            const setFormattedValue = (inputId, value, groupId) => {
                const input = document.getElementById(inputId);
                if (input) {
                    if (value === null || value === undefined || isNaN(value)) {
                        input.value = '';
                    } else {
                        input.value = formatDisplayValue(value, groupId);
                    }
                }
            };
            
            if (isCodes9911to9914) {
                setFormattedValue('QYearBeforePrev-edit', null, groupNumber);
                setFormattedValue('QYearCurr-edit', null, groupNumber);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            } else if (!isSpecialGroup) {
                const valBeforePrev = data.QYearBeforePrev ? (data.QYearBeforePrev / coeffValue) : null;
                const valPrev = data.QYearPrev ? (data.QYearPrev / coeffValue) : null;
                setFormattedValue('QYearBeforePrev-edit', valBeforePrev, groupNumber);
                setFormattedValue('QYearCurr-edit', valPrev, groupNumber);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            } else {
                setFormattedValue('QYearBeforePrev-edit', null, groupNumber);
                setFormattedValue('QYearCurr-edit', null, groupNumber);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / coeffValue) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            }
            
            function validateEditForm() {
                const isCategoryChecked = categoryRadios && Array.from(categoryRadios).some(radio => radio.checked);
                const isNameFilled = editNameInput && editNameInput.value.trim() !== '';
                const submitEditBtn = document.getElementById('submit-edit-indicator-btn');
                
                if (submitEditBtn) {
                    if (indicatorCode === '2023' || indicatorCode === '2024') {
                        submitEditBtn.disabled = !(isCategoryChecked && isNameFilled);
                    } else {
                        submitEditBtn.disabled = false;
                    }
                }
            }
            
            const categoryRadios = document.querySelectorAll('#EditIndicatorModal input[name="fuel_category"]');
            
            if (indicatorCode === '2023' || indicatorCode === '2024') {
                if (editCategorySection) editCategorySection.style.display = 'block';
                if (editNameSection) editNameSection.style.display = 'block';
                
                if (editNameInput) {
                    editNameInput.removeAttribute('required');
                    editNameInput.required = true;
                }
                
                if (data.note && editNameInput) {
                    editNameInput.value = data.note;
                }
                
                if (data.is_local) {
                    const localRadio = document.querySelector('#EditIndicatorModal input[name="fuel_category"][value="local"]');
                    if (localRadio) localRadio.checked = true;
                } else if (data.is_renewable) {
                    const renewableRadio = document.querySelector('#EditIndicatorModal input[name="fuel_category"][value="renewable"]');
                    if (renewableRadio) renewableRadio.checked = true;
                }
                
                categoryRadios.forEach(radio => {
                    radio.removeEventListener('change', validateEditForm);
                    radio.addEventListener('change', validateEditForm);
                });
                
                if (editNameInput) {
                    editNameInput.removeEventListener('input', validateEditForm);
                    editNameInput.addEventListener('input', validateEditForm);
                }
                
                validateEditForm();
            } else {
                if (editCategorySection) editCategorySection.style.display = 'none';
                if (editNameSection) editNameSection.style.display = 'none';
                if (editNameInput) {
                    editNameInput.required = false;
                    editNameInput.value = '';
                }
                const submitEditBtn = document.getElementById('submit-edit-indicator-btn');
                if (submitEditBtn) submitEditBtn.disabled = false;
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
    let groupValue = '';
    
    if (activeRow) {
        const codeCell = activeRow.querySelector('td:nth-child(12)');
        if (codeCell) {
            indicatorCode = codeCell.textContent.trim();
        }
        const groupDataCell = activeRow.querySelector('td[data-group]');
        if (groupDataCell) {
            groupValue = groupDataCell.getAttribute('data-group');
        }
    }
    
    const groupNumber = parseFloat(groupValue);
    const isGroup5 = groupNumber === 5;
    const isGroup6 = groupNumber === 6;
    const isGroup7 = groupNumber === 7;
    const isGroup8 = groupNumber === 8;
    const isSpecialGroup = isGroup5 || isGroup6;
    
    const formatResultValue = (value, groupId) => {
        if (value === null || value === undefined || isNaN(value)) return '0';
        
        if (groupId === 5) {
            return value.toFixed(1).replace('.', ',');
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            return value.toFixed(2).replace('.', ',');
        } else {
            return Math.round(value).toString().replace('.', ',');
        }
    };
    
    const isCodes9911to9914 = ['9911', '9912', '9913', '9914'].includes(indicatorCode);
    
    if (isCodes9911to9914) {
        const currentInput = document.getElementById('QYearCurrent-edit');
        const resultSpan = document.getElementById('edit-result-current');
        
        if (currentInput && resultSpan && currentInput.value) {
            let inputValue = currentInput.value.replace(',', '.');
            let value = parseFloat(inputValue);
            if (isNaN(value)) value = 0;
            const tutValue = value * currentCoeff;
            let formattedResult = formatResultValue(tutValue, groupNumber);
            resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
        } else if (resultSpan) {
            resultSpan.textContent = '= 0 т.у.т.';
        }
    } else if (isSpecialGroup) {
        const currentInput = document.getElementById('QYearCurrent-edit');
        const resultSpan = document.getElementById('edit-result-current');
        
        if (currentInput && resultSpan && currentInput.value) {
            let inputValue = currentInput.value.replace(',', '.');
            let value = parseFloat(inputValue);
            if (isNaN(value)) value = 0;
            const tutValue = value * currentCoeff;
            let formattedResult = formatResultValue(tutValue, groupNumber);
            resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
        } else if (resultSpan) {
            resultSpan.textContent = '= 0 т.у.т.';
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
            
            if (input && resultSpan) {
                if (input.value && !input.readOnly) {
                    let inputValue = input.value.replace(',', '.');
                    let value = parseFloat(inputValue);
                    if (isNaN(value)) value = 0;
                    const tutValue = value * currentCoeff;
                    let formattedResult = formatResultValue(tutValue, groupNumber);
                    resultSpan.textContent = '= ' + formattedResult + ' т.у.т.';
                } else {
                    resultSpan.textContent = '= 0 т.у.т.';
                }
            }
        });
    }
}