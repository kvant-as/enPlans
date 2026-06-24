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

var NumericInputHandler = {
    init: function(selector, options) {
        var defaults = {
            allowNegative: false,
            decimalPlaces: 2,
            defaultValue: '0,00'
        };
        var settings = Object.assign({}, defaults, options);
        
        var inputs = document.querySelectorAll(selector);
        inputs.forEach(function(input) {
            input.addEventListener('input', function(e) {
                NumericInputHandler.handleInput(e, settings);
            });
            input.addEventListener('focus', function(e) {
                NumericInputHandler.handleFocus(e, settings);
            });
            input.addEventListener('blur', function(e) {
                NumericInputHandler.handleBlur(e, settings);
            });
            input.addEventListener('click', function(e) {
                e.target.select();
            });
        });
    },
    
    handleInput: function(e, settings) {
        var input = e.target;
        var cursorPos = input.selectionStart;
        var oldValue = input.value;
        var newValue = oldValue;
        
        if (settings.allowNegative) {
            newValue = oldValue.replace(/[^\d,.-]/g, '');
            var minusCount = (newValue.match(/-/g) || []).length;
            if (minusCount > 1) {
                newValue = '-' + newValue.replace(/-/g, '');
            } else if (minusCount === 1 && !newValue.startsWith('-')) {
                newValue = '-' + newValue.replace(/-/g, '');
            }
            if (newValue === '-') {
                input.value = newValue;
                return;
            }
        } else {
            newValue = oldValue.replace(/[^\d,]/g, '');
            if (newValue === '') {
                input.value = '';
                return;
            }
        }
        
        if (newValue !== '' && newValue !== '-') {
            newValue = newValue.replace(',', '.');
            var parts = newValue.split('.');
            if (parts.length > 1) {
                newValue = parts[0] + '.' + parts[1].slice(0, settings.decimalPlaces);
            }

            if (!newValue.includes('.') && settings.decimalPlaces > 0) {
                newValue = newValue + '.' + '0'.repeat(settings.decimalPlaces);
            }
            
            var floatValue = parseFloat(newValue);
            if (!isNaN(floatValue)) {
                newValue = floatValue.toFixed(settings.decimalPlaces);
                newValue = newValue.replace('.', ',');
            }
        }
        
        if (newValue !== oldValue) {
            input.value = newValue;
            var newCursorPos = Math.min(cursorPos, newValue.length);
            input.setSelectionRange(newCursorPos, newCursorPos);
        }
    },
    
    handleFocus: function(e, settings) {
        var input = e.target;
        if (input.value === '' || input.value === '-') {
            input.value = settings.defaultValue;
        }
        var commaIndex = input.value.indexOf(',');
        if (commaIndex !== -1 && settings.decimalPlaces > 0) {
            input.setSelectionRange(commaIndex, commaIndex);
        } else if (settings.decimalPlaces === 0) {
            input.select();
        }
    },
    
    handleBlur: function(e, settings) {
        var input = e.target;
        if (input.value === '' || input.value === '-' || input.value === null) {
            input.value = settings.defaultValue;
        } else {
            var valueWithDot = input.value.replace(',', '.');
            var num = parseFloat(valueWithDot);
            if (!isNaN(num)) {
                var formatted = num.toFixed(settings.decimalPlaces);
                input.value = formatted.replace('.', ',');
            } else {
                input.value = settings.defaultValue;
            }
        }
    }
};

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
            tbody.innerHTML = `<tr class="no-results-row"><td colspan="19">${emptyMessage}</tr>`;
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
            <td style="text-align: end;">${(row.Volume || 0).toString()}</td>
            <td style="text-align: end;">${this.formatNumber(row.EffTut)}</td>
            <td style="text-align: end;">${(row.EffRub || 0).toString()}</td>
            <td style="text-align: center;">${row.ExpectedQuarter || ''}</td> 
            <td style="text-align: end;">${this.formatNumber(row.EffCurrYear)}</td>
            <td style="text-align: end;">${(row.Payback || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(row.ObchVolumeFin || 0).toString()}</td>
            <td style="text-align: end;">${(row.VolumeFinCurrentYear || 0).toString()}</td>
            <td style="text-align: end;">${(row.BudgetState || 0).toString()}</td>
            <td style="text-align: end;">${(row.BudgetRep || 0).toString()}</td>
            <td style="text-align: end;">${(row.BudgetLoc || 0).toString()}</td>
            <td style="text-align: end;">${(row.BudgetOther || 0).toString()}</td>
            <td style="text-align: end;">${(row.MoneyOwn || 0).toString()}</td>
            <td style="text-align: end;">${(row.MoneyLoan || 0).toString()}</td>
            <td style="text-align: end;">${(row.MoneyOther || 0).toString()}</td>
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
            <td style="text-align: end;">${(this.sumEvents(events, 'EffRub') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(events, 'EffCurrYear').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'ObchVolumeFin') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'VolumeFinCurrentYear') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'BudgetState') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'BudgetRep') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'BudgetLoc') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'BudgetOther') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'MoneyOwn') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'MoneyLoan') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(events, 'MoneyOther') || 0).toString().replace('.', ',')}</td>
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
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'EffTut').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'EffRub') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${this.sumEvents(allEvents, 'EffCurrYear').toFixed(2).replace('.', ',')}</td>
            <td style="text-align: end;">-</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'ObchVolumeFin') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'VolumeFinCurrentYear') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'BudgetState') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'BudgetRep') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'BudgetLoc') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'BudgetOther') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'MoneyOwn') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'MoneyLoan') || 0).toString().replace('.', ',')}</td>
            <td style="text-align: end;">${(this.sumEvents(allEvents, 'MoneyOther') || 0).toString().replace('.', ',')}</td>
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
                <td colspan="10"></td>
            `;
            
            otherContent.appendChild(row);
        });
        
        if (window.eventTableMenu) {
            window.eventTableMenu.init();
        }
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
                immutableEditCodes: ['0004'],
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
        if (value === null || value === undefined) return '';
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
                selectors.push(`#${containerId} tr`);
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
        
        const hasDataId = row.getAttribute('data-id') && row.getAttribute('data-id') !== 'null';
        
        if (!hasDataId) {
            return;
        }
        
        if (this.selectedRow && this.selectedRow !== row) {
            this.selectedRow.classList.remove('active-row');
        }
        
        row.classList.add('active-row');
        this.selectedRow = row;
        
        const isPeriodRow = row.closest('#other-content') !== null;
        
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

        const hasDataId = row.getAttribute('data-id') && row.getAttribute('data-id') !== 'null';
        
        if (!hasDataId) {
            this.updateButtonsState();
            return;
        }

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
        
        const isPeriodRow = row.closest('#other-content') !== null;
        
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


function initStatusProgress() {
    const STATUS_CONFIG = {
        'plan-cont-redac': { width: '20%', color: 'var(--color-redaced)' },
        'plan-cont-control': { width: '40%', color: 'var(--color-controled)' },
        'plan-cont-sent': { width: '60%', color: 'var(--color-sented)' },
        'plan-cont-eror': { width: '80%', color: 'var(--color-erorsed)' },
        'plan-cont-sub': { width: '100%', color: 'var(--color-submited)' }
    };

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



class SendModalPreview {
    constructor(modalId) {
        console.log('[SendModalPreview] Constructor called with modalId:', modalId);
        
        this.modal = document.getElementById(modalId);
        if (!this.modal) {
            console.error('[SendModalPreview] Modal element not found:', modalId);
            return;
        }

        this.progressBar = this.modal.querySelector('#modal-progress-bar');
        this.stepEls = Array.from(this.modal.querySelectorAll('[id^="step"]'))
            .filter(el => /^step\d+$/.test(el.id))
            .sort((a, b) => parseInt(a.id.slice(4), 10) - parseInt(b.id.slice(4), 10));

        this.totalSteps = this.stepEls.length || 1;
        this.currentStep = 1;

        this.selectedCoordinators = new Set();
        this.selectedApprover = null;

        this.coordinatorSearch = this.modal.querySelector('#coordinator-search');
        this.approverSearch = this.modal.querySelector('#approver-search');
        this.coordinatorTbody = this.modal.querySelector('#coordinator-tbody');
        this.approverTbody = this.modal.querySelector('#approver-tbody');
        this.selectedCoordinatorsContainer = this.modal.querySelector('#selected-coordinators');
        this.selectedApproverContainer = this.modal.querySelector('#selected-approver');
        this.summaryCoordinators = this.modal.querySelector('#summary-coordinators');
        this.summaryApprover = this.modal.querySelector('#summary-approver');
        this.coordinatorIdsInput = this.modal.querySelector('#coordinator-ids-input');
        this.approverIdInput = this.modal.querySelector('#approver-id-input');
        this.coordinatorCount = this.modal.querySelector('#coordinator-count');
        this.approverCount = this.modal.querySelector('#approver-count');
        this.approvalSliderContainer = this.modal.querySelector('#approval-slider-container');

        this.buttons = {
            step1Next: this.modal.querySelector('#step1-next-btn'),
            step2Back: this.modal.querySelector('#step2-back-btn'),
            step2Next: this.modal.querySelector('#step2-next-btn'),
            step3Back: this.modal.querySelector('#step3-back-btn')
        };

        this.submitButton = this.modal.querySelector('#submit-sent-button');

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

        this.regionNumber = window.regionNumber || '';
        this.regionNames = {
            1: 'Брестское областное управление',
            2: 'Витебское областное управление',
            3: 'Гомельское областное управление',
            4: 'Гродненское областное управление',
            5: 'Управление г. Минск',
            6: 'Минское областное управление',
            7: 'Могилевское областное управление'
        };
        
        this.init();
        this.updateButtonsState();
    }

    init() {
        this.loadCoordinators();
        this.loadApprovers();
        this.initSearch();
        this.initNavigation();
        this.initScrollLoading();
        this.initSliderDrag();
        this.updateButtonsState();
    }

    async loadCoordinators(reset = true) {
        if (this.coordinatorLoading) return;
        
        if (reset) {
            this.coordinatorPage = 1;
            this.coordinatorHasMore = true;
            this.coordinatorTbody.innerHTML = '';
        }
        
        if (!this.coordinatorHasMore) {
            this.removeLoading(this.coordinatorTbody);
            return;
        }

        this.coordinatorLoading = true;
        this.showLoading(this.coordinatorTbody, 3);

        try {
            const url = `/api/organizations?type=auditor&page=${this.coordinatorPage}&per_page=10&q=${encodeURIComponent(this.coordinatorSearchQuery)}`;
            console.log('[SendModalPreview] Loading coordinators, page:', this.coordinatorPage);
            
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
            }
            
            this.coordinatorHasMore = data.has_next || false;
            this.coordinatorPage = data.page + 1;

            console.log('[SendModalPreview] Coordinators loaded:', data.organizations?.length || 0, 'Has more:', this.coordinatorHasMore);

            if (!this.coordinatorHasMore) {
                this.removeLoading(this.coordinatorTbody);
                this.showEndMessage(this.coordinatorTbody, 3);
            }
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
        }
        
        if (!this.approverHasMore) {
            this.removeLoading(this.approverTbody);
            return;
        }

        this.approverLoading = true;
        this.showLoading(this.approverTbody, 3);

        try {
            const url = `/api/organizations?type=approver&page=${this.approverPage}&per_page=10&q=${encodeURIComponent(this.approverSearchQuery)}`;
            console.log('[SendModalPreview] Loading approvers, page:', this.approverPage);
            
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
            }
            
            this.approverHasMore = data.has_next || false;
            this.approverPage = data.page + 1;

            console.log('[SendModalPreview] Approvers loaded:', data.organizations?.length || 0, 'Has more:', this.approverHasMore);

            if (!this.approverHasMore) {
                this.removeLoading(this.approverTbody);
                this.showEndMessage(this.approverTbody, 3);
            }
        } catch (error) {
            console.error('Error loading approvers:', error);
            this.removeLoading(this.approverTbody);
        } finally {
            this.approverLoading = false;
        }
    }

    renderOrganizations(tbody, organizations, type) {
        if (!tbody) return;

        if (!organizations || organizations.length === 0) {
            return;
        }

        organizations.forEach(org => {
            const row = document.createElement('tr');
            row.className = 'org-row';
            row.dataset.id = org.id;
            row.dataset.name = org.name;

            const isCoordinator = type === 'coordinator';
            const checkboxType = isCoordinator ? 'coordinator-checkbox' : 'approver-checkbox';

            row.innerHTML = `
                <td style="text-align: center;">
                    <input type="checkbox" class="${checkboxType}" value="${org.id}" data-name="${this.escapeHtml(org.name)}">
                </td>
                <td>${this.escapeHtml(org.name)}</td>
                <td>${this.escapeHtml(org.ynp || '')}</td>
            `;

            tbody.appendChild(row);

            if (isCoordinator) {
                const checkbox = row.querySelector('.coordinator-checkbox');
                this.initCoordinatorRow(row, checkbox);
            } else {
                const checkbox = row.querySelector('.approver-checkbox');
                this.initApproverRow(row, checkbox);
            }
        });
    }

    initCoordinatorRow(row, checkbox) {
        if (!checkbox) return;

        row.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') return;
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change'));
        });

        checkbox.addEventListener('change', (e) => {
            const id = e.target.value;
            if (e.target.checked) {
                this.selectedCoordinators.add(id);
                row.classList.add('active-row');
            } else {
                this.selectedCoordinators.delete(id);
                row.classList.remove('active-row');
            }
            this.updateSelectedCoordinators();
            this.updateButtonsState();
            this.updateApprovalPath();
        });

        if (this.selectedCoordinators.has(checkbox.value)) {
            checkbox.checked = true;
            row.classList.add('active-row');
        }
    }

    initApproverRow(row, checkbox) {
        if (!checkbox) return;

        row.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') return;
            const isChecked = !checkbox.checked;
            
            this.approverTbody.querySelectorAll('tr.org-row').forEach(r => {
                const cb = r.querySelector('.approver-checkbox');
                if (cb) {
                    cb.checked = false;
                    r.classList.remove('active-row');
                }
            });
            
            if (isChecked) {
                checkbox.checked = true;
                row.classList.add('active-row');
                this.selectedApprover = checkbox.value;
            } else {
                checkbox.checked = false;
                row.classList.remove('active-row');
                this.selectedApprover = null;
            }
            
            this.updateSelectedApprover();
            this.updateButtonsState();
            this.updateApprovalPath();
        });

        checkbox.addEventListener('change', (e) => {
            const id = e.target.value;
            
            if (e.target.checked) {
                this.approverTbody.querySelectorAll('tr.org-row').forEach(r => {
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

        if (this.selectedApprover === checkbox.value) {
            checkbox.checked = true;
            row.classList.add('active-row');
        }
    }

    showLoading(tbody, colspan = 3) {
        if (!tbody) return;
        
        let loadingRow = tbody.querySelector('.loading-row');
        if (!loadingRow) {
            loadingRow = document.createElement('tr');
            loadingRow.className = 'loading-row';
            loadingRow.innerHTML = `
                <td colspan="${colspan}" style="text-align: center; padding: 20px;">
                    <span class="loading-spinner"></span> Загрузка...
                </td>
            `;
            tbody.appendChild(loadingRow);
        }
        loadingRow.style.display = '';
    }

    removeLoading(tbody) {
        if (!tbody) return;
        const loadingRow = tbody.querySelector('.loading-row');
        if (loadingRow) {
            loadingRow.remove();
        }
    }

    showEndMessage(tbody, colspan = 3) {
        if (!tbody) return;
        
        const endRow = tbody.querySelector('.end-message-row');
        if (endRow) return;
        
        const row = document.createElement('tr');
        row.className = 'end-message-row';
        row.innerHTML = `
            <td colspan="${colspan}" style="text-align: center; padding: 15px; color: #999; font-size: 13px;">
                Все организации загружены
            </td>
        `;
        tbody.appendChild(row);
    }

    initScrollLoading() {
        const coordinatorContainer = this.modal.querySelector('#step1 .modal-table-conteiner');
        const approverContainer = this.modal.querySelector('#step2 .modal-table-conteiner');
        
        console.log('[SendModalPreview] Containers found:', {
            coordinatorContainer: !!coordinatorContainer,
            approverContainer: !!approverContainer
        });

        if (coordinatorContainer) {
            coordinatorContainer.addEventListener('scroll', (e) => {
                const container = e.target;
                const scrollTop = container.scrollTop;
                const scrollHeight = container.scrollHeight;
                const clientHeight = container.clientHeight;

                const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50;

                if (isNearBottom && !this.coordinatorLoading && this.coordinatorHasMore) {
                    console.log('[SendModalPreview] Coordinator scroll: loading more...');
                    this.loadCoordinators(false);
                }
            });
        }

        if (approverContainer) {
            approverContainer.addEventListener('scroll', (e) => {
                const container = e.target;
                const scrollTop = container.scrollTop;
                const scrollHeight = container.scrollHeight;
                const clientHeight = container.clientHeight;

                const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50;

                if (isNearBottom && !this.approverLoading && this.approverHasMore) {
                    console.log('[SendModalPreview] Approver scroll: loading more...');
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
            if (this.validateStep1()) {
                this.nextStep();
            }
        });

        this.buttons.step2Back?.addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        this.buttons.step2Next?.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.validateStep2()) {
                this.updateSummary();
                this.nextStep();
            }
        });

        this.buttons.step3Back?.addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        this.modal.querySelector('#sentForm')?.addEventListener('submit', (e) => {
            if (this.coordinatorIdsInput) {
                this.coordinatorIdsInput.value = Array.from(this.selectedCoordinators).join(',');
            }
            if (this.approverIdInput) {
                this.approverIdInput.value = this.selectedApprover;
            }
        });
    }

    updateSelectedCoordinators() {
        if (!this.selectedCoordinatorsContainer) return;
        
        const container = this.selectedCoordinatorsContainer;
        container.innerHTML = '';
        
        if (this.coordinatorCount) {
            this.coordinatorCount.textContent = this.selectedCoordinators.size;
        }
        
        if (this.selectedCoordinators.size === 0) {
            container.innerHTML = '<span class="empty-message">Ничего не выбрано</span>';
            return;
        }
        
        this.selectedCoordinators.forEach(id => {
            const row = this.coordinatorTbody?.querySelector(`tr.org-row[data-id="${id}"]`);
            const name = row ? row.dataset.name : `ID: ${id}`;
            const tag = document.createElement('span');
            tag.className = 'selected-tag';
            tag.innerHTML = `
                <span class="tag-text">${this.escapeHtml(name)}</span>
                <button class="remove-tag" data-id="${id}" type="button">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `;
            tag.querySelector('.remove-tag').addEventListener('click', (e) => {
                e.stopPropagation();
                const checkbox = this.coordinatorTbody?.querySelector(`.coordinator-checkbox[value="${id}"]`);
                if (checkbox) {
                    checkbox.checked = false;
                    checkbox.dispatchEvent(new Event('change'));
                }
            });
            container.appendChild(tag);
        });
    }

    updateSelectedApprover() {
        if (!this.selectedApproverContainer) return;
        
        const container = this.selectedApproverContainer;
        container.innerHTML = '';
        
        if (this.approverCount) {
            this.approverCount.textContent = this.selectedApprover ? '1' : '0';
        }
        
        if (!this.selectedApprover) {
            container.innerHTML = '<span class="empty-message">Ничего не выбрано</span>';
            return;
        }
        
        const row = this.approverTbody?.querySelector(`tr.org-row[data-id="${this.selectedApprover}"]`);
        const name = row ? row.dataset.name : `ID: ${this.selectedApprover}`;
        const tag = document.createElement('span');
        tag.className = 'selected-tag approver-tag';
        tag.innerHTML = `
            <span class="tag-text">${this.escapeHtml(name)}</span>
            <button class="remove-tag" data-id="${this.selectedApprover}" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        tag.querySelector('.remove-tag').addEventListener('click', (e) => {
            e.stopPropagation();
            const checkbox = this.approverTbody?.querySelector(`.approver-checkbox[value="${this.selectedApprover}"]`);
            if (checkbox) {
                checkbox.checked = false;
                checkbox.dispatchEvent(new Event('change'));
            }
        });
        container.appendChild(tag);
    }

    updateSummary() {
        if (this.summaryCoordinators) {
            this.summaryCoordinators.innerHTML = '';
            if (this.selectedCoordinators.size > 0) {
                this.selectedCoordinators.forEach(id => {
                    const row = this.coordinatorTbody?.querySelector(`tr.org-row[data-id="${id}"]`);
                    const name = row ? row.dataset.name : `ID: ${id}`;
                    const tag = document.createElement('span');
                    tag.className = 'summary-tag';
                    tag.textContent = name;
                    this.summaryCoordinators.appendChild(tag);
                });
            } else {
                this.summaryCoordinators.innerHTML = '<span class="empty-message">Не выбрано</span>';
            }
        }
        
        if (this.summaryApprover) {
            this.summaryApprover.innerHTML = '';
            if (this.selectedApprover) {
                const row = this.approverTbody?.querySelector(`tr.org-row[data-id="${this.selectedApprover}"]`);
                const name = row ? row.dataset.name : `ID: ${this.selectedApprover}`;
                const tag = document.createElement('span');
                tag.className = 'summary-tag approver-tag';
                tag.textContent = name;
                this.summaryApprover.appendChild(tag);
            } else {
                this.summaryApprover.innerHTML = '<span class="empty-message">Не выбрано</span>';
            }
        }

        this.updateApprovalPath();
    }

    updateApprovalPath() {
        const container = this.approvalSliderContainer;
        if (!container) return;

        const regionNumber = this.regionNumber;
        const coordinators = [];
        const approver = this.selectedApprover;

        const regionNames = {
            1: 'Брестское областное управление',
            2: 'Витебское областное управление',
            3: 'Гомельское областное управление',
            4: 'Гродненское областное управление',
            5: 'Управление г. Минск',
            6: 'Минское областное управление',
            7: 'Могилевское областное управление'
        };

        const regionName = regionNames[regionNumber] || 'Регион';

        this.selectedCoordinators.forEach(id => {
            const row = this.coordinatorTbody?.querySelector(`tr.org-row[data-id="${id}"]`);
            if (row) {
                coordinators.push(row.dataset.name);
            }
        });

        let approverName = '';
        if (approver) {
            const row = this.approverTbody?.querySelector(`tr.org-row[data-id="${approver}"]`);
            if (row) {
                approverName = row.dataset.name;
            }
        }

        const allSteps = [regionName, ...coordinators];
        if (approverName) {
            allSteps.push(approverName);
        }

        if (allSteps.length === 1) {
            container.innerHTML = `
                <div class="approval-path-placeholder" style="text-align: center; padding: 20px; color: #999;">
                    Выберите организацию/и для отображения пути согласования
                </div>
            `;
            return;
        }

        const totalSteps = allSteps.length;
        const completedSteps = 0;
        const progressWidth = 0;

        const sliderDiv = document.createElement('div');
        sliderDiv.className = 'enplans-approval-slider';

        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'enplans-approval-slider-steps';

        allSteps.forEach((name, index) => {
            const isFirst = index === 0;
            const statusClass = isFirst ? 'active' : 'pending';
            
            const stepDiv = document.createElement('div');
            stepDiv.className = `enplans-approval-step ${statusClass}`;
            
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
        progressLine.style.width = `${progressWidth}%`;
        progressContainer.appendChild(progressLine);
        sliderDiv.appendChild(progressContainer);

        const progressText = document.createElement('div');
        progressText.className = 'enplans-approval-progress-text';
        progressText.innerHTML = `<span>${completedSteps} из ${totalSteps} этапов (${progressWidth}%)</span>`;
        sliderDiv.appendChild(progressText);

        container.innerHTML = '';
        container.appendChild(sliderDiv);
    }

    getStepIcon(index, total) {
        const isFirst = index === 0;
        const isLast = index === total - 1;
        
        if (isFirst) {
            return window.icons.icon_region;
        } else if (isLast) {
            return window.icons.icon_higher;
        } else {
            return window.icons.icon_municipal;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        this.updateButtonsState();
        
        if (this.currentStep === 2) {
            const rows = this.approverTbody?.querySelectorAll('tr.org-row') || [];
            if (rows.length === 0) {
                this.approverHasMore = true;
                this.loadApprovers(true);
            }
        }
        
        if (this.currentStep === 3) {
            this.updateApprovalPath();
            setTimeout(() => {
                this.initSliderDrag();
            }, 100);
        }
    }

    prevStep() {
        if (this.currentStep <= 1) return;
        this.activeStepEl().style.display = 'none';
        this.currentStep--;
        this.activeStepEl().style.display = 'block';
        this.updateProgressBar();
        this.updateButtonsState();
    }

    updateButtonsState() {
        if (this.buttons.step1Next) {
            this.buttons.step1Next.disabled = this.selectedCoordinators.size === 0;
        }

        if (this.buttons.step2Next) {
            this.buttons.step2Next.disabled = !this.selectedApprover;
        }

        if (this.submitButton) {
            // const hasCertificate = document.querySelector('#drop-certificate-area.has-file') !== null;
            // this.submitButton.disabled = !hasCertificate;
            
            // Пока отключаем проверку
            this.submitButton.disabled = false;
            this.submitButton.classList.remove('disabled');
        }
    }

    validateStep1() {
        if (this.selectedCoordinators.size === 0) {
            alert('Пожалуйста, выберите хотя бы одну организацию для согласования');
            return false;
        }
        return true;
    }

    validateStep2() {
        if (!this.selectedApprover) {
            alert('Пожалуйста, выберите организацию для утверждения');
            return false;
        }
        return true;
    }

    close() {
        this.modal.style.display = 'none';
    }

    resetForm() {
        this.selectedCoordinators.clear();
        this.selectedApprover = null;
        
        this.coordinatorTbody?.querySelectorAll('tr.org-row').forEach(row => {
            const cb = row.querySelector('.coordinator-checkbox');
            if (cb) {
                cb.checked = false;
                row.classList.remove('active-row');
            }
        });
        
        this.approverTbody?.querySelectorAll('tr.org-row').forEach(row => {
            const cb = row.querySelector('.approver-checkbox');
            if (cb) {
                cb.checked = false;
                row.classList.remove('active-row');
            }
        });
        
        if (this.coordinatorCount) {
            this.coordinatorCount.textContent = '0';
        }
        
        if (this.approverCount) {
            this.approverCount.textContent = '0';
        }
        
        this.coordinatorSearchQuery = '';
        this.approverSearchQuery = '';
        if (this.coordinatorSearch) this.coordinatorSearch.value = '';
        if (this.approverSearch) this.approverSearch.value = '';
        
        this.coordinatorHasMore = true;
        this.approverHasMore = true;
        
        this.updateSelectedCoordinators();
        this.updateSelectedApprover();
        this.updateSummary();
        
        this.loadCoordinators(true);
        this.loadApprovers(true);
        
        this.stepEls.forEach((el, i) => {
            el.style.display = i === 0 ? 'block' : 'none';
        });
        this.currentStep = 1;
        this.updateProgressBar();
        this.updateButtonsState();
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
            console.log('form:', this.form);
            console.log('dropArea:', this.dropArea);
            console.log('fileInput:', this.fileInput);
            console.log('submitButton:', this.submitButton);
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
            textElement.innerHTML = 'Перетащите файл сертификата сюда или \n                <label for="certificate-to-check" class="drop-certificate-label">нажмите для выбора</label>';
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

class PlansLoader {
    constructor(options = {}) {
        this.currentStatus = options.initialStatus || 'all';
        this.currentYear = options.initialYear || 'all';
        this.currentRegion = options.initialRegion || 'all';
        this.currentSearchName = '';
        this.currentSearchOkpo = '';
        this.currentPage = 1;
        this.isLoading = false;
        this.hasMore = true;
        this.searchTimeout = null;
        this.perPage = options.perPage || 5;
        
        this.containerId = options.containerId || 'plans-container';
        this.loadMoreBtnId = options.loadMoreBtnId || 'load-more-btn';
        this.searchNameId = options.searchNameId || 'search-name';
        this.searchOkpoId = options.searchOkpoId || 'search-okpo';
        
        this.init();
    }
    
    updateUrl() {
        const params = new URLSearchParams();
        
        if (this.currentStatus && this.currentStatus !== 'all') {
            params.set('status', this.currentStatus);
        }
        if (this.currentYear && this.currentYear !== 'all') {
            params.set('year', this.currentYear);
        }
        if (this.currentRegion && this.currentRegion !== 'all') {
            params.set('region', this.currentRegion);
        }
        if (this.currentSearchName) {
            params.set('search_name', this.currentSearchName);
        }
        if (this.currentSearchOkpo) {
            params.set('search_okpo', this.currentSearchOkpo);
        }
        
        const newUrl = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
        window.history.pushState({}, '', newUrl);
    }
    
    async loadPlans(reset = true) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        const page = reset ? 1 : this.currentPage + 1;
        const container = document.getElementById(this.containerId);
        
        if (reset && container) {
            container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div></div>';
        }
        
        this.updateUrl();
        
        try {
            let url = `/api/plans?page=${page}&per_page=${this.perPage}&status=${this.currentStatus}&year=${this.currentYear}&region=${this.currentRegion}`;
            if (this.currentSearchName) {
                url += `&search_name=${encodeURIComponent(this.currentSearchName)}`;
            }
            if (this.currentSearchOkpo) {
                url += `&search_okpo=${encodeURIComponent(this.currentSearchOkpo)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                if (reset) {
                    if (container) {
                        container.innerHTML = `<div class="plans-area">${data.html}</div>`;
                    }
                    this.currentPage = 1;
                } else {
                    const plansArea = document.querySelector('.plans-area');
                    if (plansArea) {
                        plansArea.insertAdjacentHTML('beforeend', data.html);
                    }
                    this.currentPage = page;
                }
                
                this.hasMore = data.pagination.has_next;
                this.updateLoadMoreButton();
                this.updateCountsDisplay(data.counts);
                this.attachCheckboxListeners();
            }
        } catch (error) {
            console.error('Error loading plans:', error);
        } finally {
            this.isLoading = false;
        }
    }
    
    updateLoadMoreButton() {
        const loadMoreContainer = document.getElementById('load-more-container');
        if (loadMoreContainer) {
            loadMoreContainer.style.display = this.hasMore ? 'block' : 'none';
        }
    }
    
    updateCountsDisplay(counts) {
        if (!counts) return;
        
        const statAll = document.querySelector('.stat-number');
        const statDraft = document.querySelector('.stat-number-redac');
        const statControl = document.querySelector('.stat-number-control');
        const statSent = document.querySelector('.stat-number-sent');
        const statError = document.querySelector('.stat-number-eror');
        const statApproved = document.querySelector('.stat-number-sub');
        
        if (statAll) statAll.textContent = counts.all || '-';
        if (statDraft) statDraft.textContent = counts.draft || '-';
        if (statControl) statControl.textContent = counts.control || '-';
        if (statSent) statSent.textContent = counts.sent || '-';
        if (statError) statError.textContent = counts.error || '-';
        if (statApproved) statApproved.textContent = counts.approved || '-';
    }
    
    attachCheckboxListeners() {
        const checkboxes = document.querySelectorAll('.plans-area input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.removeEventListener('change', this.handleCheckboxChange);
            cb.addEventListener('change', this.handleCheckboxChange.bind(this));
        });
    }
    
    handleCheckboxChange(e) {
        const checkbox = e.target;
        const planId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedPlans.add(planId);
        } else {
            this.selectedPlans.delete(planId);
        }
        
        this.updateSelectAllButton();
        this.updateExportButton();
    }
    
    updateSelectAllButton() {
        const selectAllBtn = document.getElementById('selectAllBtn');
        const clearAllBtn = document.getElementById('clearAllBtn');
        
        if (selectAllBtn && clearAllBtn) {
            if (this.selectedPlans && this.selectedPlans.size > 0) {
                selectAllBtn.style.display = 'none';
                clearAllBtn.style.display = 'flex';
            } else {
                selectAllBtn.style.display = 'flex';
                clearAllBtn.style.display = 'none';
            }
        }
    }
    
    updateExportButton() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.disabled = !(this.selectedPlans && this.selectedPlans.size > 0 && this.selectedFormat);
        }
    }
    
    handleSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.currentSearchName = document.getElementById(this.searchNameId)?.value || '';
            this.currentSearchOkpo = document.getElementById(this.searchOkpoId)?.value || '';
            this.updateUrl();
            this.loadPlans(true);
        }, 500);
    }
    
    initFilters() {
        const searchNameInput = document.getElementById(this.searchNameId);
        const searchOkpoInput = document.getElementById(this.searchOkpoId);
        
        if (searchNameInput) {
            searchNameInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchOkpoInput) {
            searchOkpoInput.addEventListener('input', () => this.handleSearch());
        }
        
        const statusDropdown = document.querySelector('[data-filter-type="status"]');
        const yearDropdown = document.querySelector('[data-filter-type="year"]');
        const regionDropdown = document.querySelector('[data-filter-type="region"]');
        
        if (statusDropdown) {
            const toggleBtn = statusDropdown.querySelector('.dropdown-toggle');
            const items = statusDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-status');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (yearDropdown) yearDropdown.classList.remove('active');
                    if (regionDropdown) regionDropdown.classList.remove('active');
                    statusDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentStatus = value;
                    if (selectedSpan) selectedSpan.textContent = item.textContent;
                    statusDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }
        
        if (yearDropdown) {
            const toggleBtn = yearDropdown.querySelector('.dropdown-toggle');
            const items = yearDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-year');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (statusDropdown) statusDropdown.classList.remove('active');
                    if (regionDropdown) regionDropdown.classList.remove('active');
                    yearDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentYear = value;
                    if (selectedSpan) {
                        if (value === 'all') {
                            selectedSpan.textContent = 'Год';
                        } else {
                            selectedSpan.textContent = value;
                        }
                    }
                    yearDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }
        
        if (regionDropdown) {
            const toggleBtn = regionDropdown.querySelector('.dropdown-toggle');
            const items = regionDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-region');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (statusDropdown) statusDropdown.classList.remove('active');
                    if (yearDropdown) yearDropdown.classList.remove('active');
                    regionDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentRegion = value;
                    if (selectedSpan) selectedSpan.textContent = item.textContent;
                    regionDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }

        document.addEventListener('click', (e) => {
            if (statusDropdown && !statusDropdown.contains(e.target)) {
                statusDropdown.classList.remove('active');
            }
            if (yearDropdown && !yearDropdown.contains(e.target)) {
                yearDropdown.classList.remove('active');
            }
            if (regionDropdown && !regionDropdown.contains(e.target)) {
                regionDropdown.classList.remove('active');
            }
        });
        
        window.addEventListener('popstate', (event) => {
            const params = new URLSearchParams(window.location.search);
            const newStatus = params.get('status') || 'all';
            const newYear = params.get('year') || 'all';
            const newRegion = params.get('region') || 'all';
            const newSearchName = params.get('search_name') || '';
            const newSearchOkpo = params.get('search_okpo') || '';
            
            if (newStatus !== this.currentStatus || newYear !== this.currentYear || newRegion !== this.currentRegion ||
                newSearchName !== this.currentSearchName || newSearchOkpo !== this.currentSearchOkpo) {
                
                this.currentStatus = newStatus;
                this.currentYear = newYear;
                this.currentRegion = newRegion;
                this.currentSearchName = newSearchName;
                this.currentSearchOkpo = newSearchOkpo;
                
                if (searchNameInput) searchNameInput.value = newSearchName;
                if (searchOkpoInput) searchOkpoInput.value = newSearchOkpo;
                
                this.updateFilterDisplay();
                this.loadPlans(true);
            }
        });
        
        const loadMoreBtn = document.getElementById(this.loadMoreBtnId);
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', () => this.loadPlans(false));
        }
    }
    
    updateFilterDisplay() {
        const statusMap = {
            'all': 'Статус',
            'draft': 'В редакции',
            'control': 'Контроль пройден',
            'sent': 'На рассмотрении',
            'error': 'С ошибками',
            'approved': 'Согласованные'
        };
        
        const regionMap = {
            'all': 'Регион',
            '1': 'Брестское областное управление',
            '2': 'Витебское областное управление',
            '3': 'Гомельское областное управление',
            '4': 'Гродненское областное управление',
            '5': 'Управление г. Минск',
            '6': 'Минское областное управление',
            '7': 'Могилевское областное управление'
        };
        
        const selectedStatusSpan = document.getElementById('selected-status');
        if (selectedStatusSpan && statusMap[this.currentStatus]) {
            selectedStatusSpan.textContent = statusMap[this.currentStatus];
        }
        
        const selectedYearSpan = document.getElementById('selected-year');
        if (selectedYearSpan) {
            if (this.currentYear === 'all') {
                selectedYearSpan.textContent = 'Год';
            } else {
                selectedYearSpan.textContent = this.currentYear;
            }
        }
        
        const selectedRegionSpan = document.getElementById('selected-region');
        if (selectedRegionSpan && regionMap[this.currentRegion]) {
            selectedRegionSpan.textContent = regionMap[this.currentRegion];
        }
    }
    
    init() {
        this.selectedPlans = new Set();
        this.selectedFormat = null;
        this.initFilters();
        this.loadPlans(true);
    }
}

class ExportPlansLoader {
    constructor(options = {}) {
        this.currentStatus = options.initialStatus || 'all';
        this.currentYear = options.initialYear || 'all';
        this.currentRegion = options.initialRegion || 'all';
        this.currentSearchName = '';
        this.currentSearchOkpo = '';
        this.currentPage = 1;
        this.isLoading = false;
        this.hasMore = true;
        this.searchTimeout = null;
        this.perPage = options.perPage || 5;
        this.selectedPlans = new Set();
        this.selectedFormat = null;
        this.exportInProgress = false;
        this.currentTaskId = null;
        this.progressInterval = null;
        this.isInitialLoad = true;
        
        this.containerId = options.containerId || 'plans-container';
        this.loadMoreBtnId = options.loadMoreBtnId || 'load-more-btn';
        this.searchNameId = options.searchNameId || 'search-name';
        this.searchOkpoId = options.searchOkpoId || 'search-okpo';
        this.selectAllId = options.selectAllId || 'selectAllBtn';
        this.clearAllId = 'clearAllBtn';
        this.exportFormId = options.exportFormId || 'exportForm';
        
        this.init();
    }
    
    updateUrl() {
        const params = new URLSearchParams();
        
        if (this.currentStatus && this.currentStatus !== 'all') {
            params.set('status', this.currentStatus);
        }
        if (this.currentYear && this.currentYear !== 'all') {
            params.set('year', this.currentYear);
        }
        if (this.currentRegion && this.currentRegion !== 'all') {
            params.set('region', this.currentRegion);
        }
        if (this.currentSearchName) {
            params.set('search_name', this.currentSearchName);
        }
        if (this.currentSearchOkpo) {
            params.set('search_okpo', this.currentSearchOkpo);
        }
        
        const newUrl = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
        
        if (this.isInitialLoad) {
            window.history.replaceState({}, '', newUrl);
            this.isInitialLoad = false;
        } else {
            window.history.pushState({}, '', newUrl);
        }
    }
    
    async loadPlans(reset = true) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        const page = reset ? 1 : this.currentPage + 1;
        const container = document.getElementById(this.containerId);
        
        if (reset && container) {
            container.innerHTML = '<div class="loading-spinner" style="text-align: center; padding: 40px;"></div>';
        }
        
        const loadMoreBtn = document.getElementById(this.loadMoreBtnId);
        if (!reset && loadMoreBtn) {
            loadMoreBtn.disabled = true;
            loadMoreBtn.innerHTML = '<span class="loading-spinner" style="display: inline-block;"></span> Загрузка...';
        }
        
        try {
            let url = `/api/export-plans?page=${page}&per_page=${this.perPage}&status=${this.currentStatus}&year=${this.currentYear}&region=${this.currentRegion}`;
            if (this.currentSearchName) {
                url += `&search_name=${encodeURIComponent(this.currentSearchName)}`;
            }
            if (this.currentSearchOkpo) {
                url += `&search_okpo=${encodeURIComponent(this.currentSearchOkpo)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                if (reset) {
                    if (container) {
                        container.innerHTML = `<div class="plans-area">${data.html}</div>`;
                    }
                    this.currentPage = 1;
                    this.selectedPlans.clear();
                } else {
                    const plansArea = document.querySelector('.plans-area');
                    if (plansArea) {
                        plansArea.insertAdjacentHTML('beforeend', data.html);
                    }
                    this.currentPage = page;
                }
                
                this.hasMore = data.pagination.has_next;
                this.updateLoadMoreButton();
                this.attachCheckboxListeners();
                this.updateButtons();
                this.updateExportButton();
            }
        } catch (error) {
            console.error('Error loading plans:', error);
            if (reset && container) {
                container.innerHTML = '<div class="plans-error" style="text-align: center; padding: 40px; color: red;">Ошибка загрузки планов</div>';
            }
        } finally {
            this.isLoading = false;
            if (!reset && loadMoreBtn) {
                loadMoreBtn.disabled = false;
                loadMoreBtn.innerHTML = '<span class="btn-text">Загрузить еще</span>';
            }
        }
    }
    
    updateLoadMoreButton() {
        const loadMoreContainer = document.getElementById('load-more-container');
        if (loadMoreContainer) {
            loadMoreContainer.style.display = this.hasMore ? 'block' : 'none';
        }
    }
    
    attachCheckboxListeners() {
        const checkboxes = document.querySelectorAll('.plans-area input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.removeEventListener('change', this.handleCheckboxChange);
            cb.addEventListener('change', this.handleCheckboxChange.bind(this));
        });
        this.updateButtons();
        this.updateExportButton();
    }
    
    handleCheckboxChange(e) {
        const checkbox = e.target;
        const planId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedPlans.add(planId);
        } else {
            this.selectedPlans.delete(planId);
        }
        
        this.updateButtons();
        this.updateExportButton();
    }
    
    updateButtons() {
        const selectAllBtn = document.getElementById(this.selectAllId);
        const clearAllBtn = document.getElementById(this.clearAllId);
        
        if (selectAllBtn && clearAllBtn) {
            if (this.selectedPlans.size > 0) {
                selectAllBtn.style.display = 'none';
                clearAllBtn.style.display = 'flex';
            } else {
                selectAllBtn.style.display = 'flex';
                clearAllBtn.style.display = 'none';
            }
        }
        
        this.updateExportButton();
    }
    
    updateExportButton() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.disabled = this.selectedPlans.size === 0 || !this.selectedFormat;
        }
    }
    
    selectAll() {
        const checkboxes = document.querySelectorAll('.plans-area input[type="checkbox"]');
        
        checkboxes.forEach(cb => {
            cb.checked = true;
            const planId = cb.value;
            this.selectedPlans.add(planId);
        });
        
        this.updateButtons();
        this.updateExportButton();
    }
    
    clearAll() {
        const checkboxes = document.querySelectorAll('.plans-area input[type="checkbox"]');
        
        checkboxes.forEach(cb => {
            cb.checked = false;
            const planId = cb.value;
            this.selectedPlans.delete(planId);
        });
        
        this.updateButtons();
        this.updateExportButton();
    }
    
    handleSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.currentSearchName = document.getElementById(this.searchNameId)?.value || '';
            this.currentSearchOkpo = document.getElementById(this.searchOkpoId)?.value || '';
            this.updateUrl();
            this.loadPlans(true);
        }, 500);
    }
    
    initFormatSelection() {
        const formatItems = document.querySelectorAll('.export-choose');
        formatItems.forEach(item => {
            if (item.classList.contains('disabled')) return;
            
            item.removeEventListener('click', this.formatClickHandler);
            this.formatClickHandler = () => {
                const format = item.dataset.format;
                formatItems.forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                this.selectedFormat = format;
                
                const exportForm = document.getElementById(this.exportFormId);
                if (exportForm) {
                    exportForm.action = `/export-to/${format}`;
                }
                
                this.updateExportButton();
            };
            item.addEventListener('click', this.formatClickHandler);
        });
    }
    
    initFilters() {
        const searchNameInput = document.getElementById(this.searchNameId);
        const searchOkpoInput = document.getElementById(this.searchOkpoId);
        
        if (searchNameInput) {
            searchNameInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchOkpoInput) {
            searchOkpoInput.addEventListener('input', () => this.handleSearch());
        }
        
        const statusDropdown = document.querySelector('[data-filter-type="status"]');
        const yearDropdown = document.querySelector('[data-filter-type="year"]');
        const regionDropdown = document.querySelector('[data-filter-type="region"]');
        
        if (statusDropdown) {
            const toggleBtn = statusDropdown.querySelector('.dropdown-toggle');
            const items = statusDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-status');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (yearDropdown) yearDropdown.classList.remove('active');
                    if (regionDropdown) regionDropdown.classList.remove('active');
                    statusDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentStatus = value;
                    if (selectedSpan) selectedSpan.textContent = item.textContent;
                    statusDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }
        
        if (yearDropdown) {
            const toggleBtn = yearDropdown.querySelector('.dropdown-toggle');
            const items = yearDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-year');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (statusDropdown) statusDropdown.classList.remove('active');
                    if (regionDropdown) regionDropdown.classList.remove('active');
                    yearDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentYear = value;
                    if (selectedSpan) {
                        if (value === 'all') {
                            selectedSpan.textContent = 'Год';
                        } else {
                            selectedSpan.textContent = value;
                        }
                    }
                    yearDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }
        
        if (regionDropdown) {
            const toggleBtn = regionDropdown.querySelector('.dropdown-toggle');
            const items = regionDropdown.querySelectorAll('.dropdown-item');
            const selectedSpan = document.getElementById('selected-region');
            
            if (toggleBtn) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (statusDropdown) statusDropdown.classList.remove('active');
                    if (yearDropdown) yearDropdown.classList.remove('active');
                    regionDropdown.classList.toggle('active');
                });
            }
            
            items.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const value = item.dataset.value;
                    this.currentRegion = value;
                    if (selectedSpan) selectedSpan.textContent = item.textContent;
                    regionDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans(true);
                });
            });
        }
        
        document.addEventListener('click', (e) => {
            if (statusDropdown && !statusDropdown.contains(e.target)) {
                statusDropdown.classList.remove('active');
            }
            if (yearDropdown && !yearDropdown.contains(e.target)) {
                yearDropdown.classList.remove('active');
            }
            if (regionDropdown && !regionDropdown.contains(e.target)) {
                regionDropdown.classList.remove('active');
            }
        });
        
        window.addEventListener('popstate', (event) => {
            const params = new URLSearchParams(window.location.search);
            const newStatus = params.get('status') || 'all';
            const newYear = params.get('year') || 'all';
            const newRegion = params.get('region') || 'all';
            const newSearchName = params.get('search_name') || '';
            const newSearchOkpo = params.get('search_okpo') || '';
            
            if (newStatus !== this.currentStatus || newYear !== this.currentYear || newRegion !== this.currentRegion ||
                newSearchName !== this.currentSearchName || newSearchOkpo !== this.currentSearchOkpo) {
                
                this.currentStatus = newStatus;
                this.currentYear = newYear;
                this.currentRegion = newRegion;
                this.currentSearchName = newSearchName;
                this.currentSearchOkpo = newSearchOkpo;
                
                if (searchNameInput) searchNameInput.value = newSearchName;
                if (searchOkpoInput) searchOkpoInput.value = newSearchOkpo;
                
                this.updateFilterDisplay();
                this.loadPlans(true);
            }
        });
        
        const loadMoreBtn = document.getElementById(this.loadMoreBtnId);
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', () => this.loadPlans(false));
        }
    }
    
    updateFilterDisplay() {
        const statusMap = {
            'all': 'Статус',
            'draft': 'В редакции',
            'control': 'Контроль пройден',
            'sent': 'На рассмотрении',
            'error': 'С ошибками',
            'approved': 'Согласованные'
        };
        
        const regionMap = {
            'all': 'Регион',
            '1': 'Брестское областное управление',
            '2': 'Витебское областное управление',
            '3': 'Гомельское областное управление',
            '4': 'Гродненское областное управление',
            '5': 'Управление г. Минск',
            '6': 'Минское областное управление',
            '7': 'Могилевское областное управление'
        };
        
        const selectedStatusSpan = document.getElementById('selected-status');
        if (selectedStatusSpan && statusMap[this.currentStatus]) {
            selectedStatusSpan.textContent = statusMap[this.currentStatus];
        }
        
        const selectedYearSpan = document.getElementById('selected-year');
        if (selectedYearSpan) {
            if (this.currentYear === 'all') {
                selectedYearSpan.textContent = 'Год';
            } else {
                selectedYearSpan.textContent = this.currentYear;
            }
        }
        
        const selectedRegionSpan = document.getElementById('selected-region');
        if (selectedRegionSpan && regionMap[this.currentRegion]) {
            selectedRegionSpan.textContent = regionMap[this.currentRegion];
        }
    }
    
    showExportProgress() {
        let modal = document.getElementById('export-progress-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'export-progress-modal';
            modal.className = 'export-progress-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h1>Формирование архива</h1>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill"></div>
                    </div>
                    <p class="progress-text">Подготовка файлов... 0%</p>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.style.display = 'flex';
        modal.classList.add('active');
    }
    
    updateExportProgress(percent) {
        const modal = document.getElementById('export-progress-modal');
        if (!modal) return;
        const fill = modal.querySelector('.progress-bar-fill');
        const text = modal.querySelector('.progress-text');
        if (fill) fill.style.width = `${percent}%`;
        if (text) text.textContent = `Подготовка файлов... ${Math.round(percent)}%`;
    }
    
    hideExportProgress() {
        const modal = document.getElementById('export-progress-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('active');
        }
    }
    
    showNotification(message, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        } else {
            alert(message);
        }
    }
    
    async startAsyncExport() {
        if (this.selectedPlans.size === 0 || !this.selectedFormat) {
            this.showNotification('Выберите планы и формат экспорта', 'warning');
            return;
        }
        
        if (this.exportInProgress) {
            this.showNotification('Экспорт уже выполняется', 'warning');
            return;
        }
        
        const formData = new FormData();
        formData.append('format', this.selectedFormat);
        this.selectedPlans.forEach(planId => formData.append('ids', planId));
        
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (csrfToken) {
            formData.append('csrf_token', csrfToken);
        }
        
        this.showExportProgress();
        this.exportInProgress = true;
        
        try {
            const response = await fetch('/export/start', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentTaskId = data.task_id;
                this.pollExportStatus();
            } else {
                this.hideExportProgress();
                this.showNotification(data.error || 'Ошибка при запуске экспорта', 'error');
                this.exportInProgress = false;
            }
        } catch (error) {
            console.error('Error starting export:', error);
            this.hideExportProgress();
            this.showNotification('Ошибка сети при запуске экспорта', 'error');
            this.exportInProgress = false;
        }
    }
    
    pollExportStatus() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        this.progressInterval = setInterval(async () => {
            if (!this.currentTaskId) {
                clearInterval(this.progressInterval);
                return;
            }
            
            try {
                const response = await fetch(`/export/status/${this.currentTaskId}`);
                const data = await response.json();
                
                if (data.success) {
                    this.updateExportProgress(data.progress || 0);
                    
                    if (data.status === 'completed') {
                        clearInterval(this.progressInterval);
                        window.location.href = `/export/download/${this.currentTaskId}`;
                        setTimeout(() => {
                            this.hideExportProgress();
                            this.exportInProgress = false;
                            this.currentTaskId = null;
                        }, 1000);
                    } else if (data.status === 'error') {
                        clearInterval(this.progressInterval);
                        this.hideExportProgress();
                        this.showNotification(data.error || 'Ошибка при экспорте', 'error');
                        this.exportInProgress = false;
                        this.currentTaskId = null;
                    }
                }
            } catch (error) {
                console.error('Error polling status:', error);
                clearInterval(this.progressInterval);
                this.hideExportProgress();
                this.showNotification('Ошибка при проверке статуса экспорта', 'error');
                this.exportInProgress = false;
                this.currentTaskId = null;
            }
        }, 1000);
    }
    
    initFormSubmit() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.removeEventListener('click', this.formSubmitHandler);
            this.formSubmitHandler = (e) => {
                e.preventDefault();
                this.startAsyncExport();
            };
            exportBtn.addEventListener('click', this.formSubmitHandler);
        }
    }
    
    init() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        this.initFilters();
        
        const selectAllBtn = document.getElementById(this.selectAllId);
        if (selectAllBtn) {
            selectAllBtn.removeEventListener('click', this.selectAllHandler);
            this.selectAllHandler = () => this.selectAll();
            selectAllBtn.addEventListener('click', this.selectAllHandler);
        }
        
        const clearAllBtn = document.getElementById(this.clearAllId);
        if (clearAllBtn) {
            clearAllBtn.removeEventListener('click', this.clearAllHandler);
            this.clearAllHandler = () => this.clearAll();
            clearAllBtn.addEventListener('click', this.clearAllHandler);
        }
        
        this.initFormatSelection();
        this.initFormSubmit();
        this.isInitialLoad = true;
        this.loadPlans(true);
    }
}

function initEditableHeaders() {
    const editIcons = document.querySelectorAll('.edit-header-icon');
    
    editIcons.forEach(icon => {
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            
            const th = icon.closest('.colspan-header');
            const link = th.querySelector('a');
            const currentText = link.textContent;
            const configId = icon.dataset.configId;
            const currentYear = icon.dataset.year;
            const currentLabel = icon.dataset.label;
            
            const select = document.createElement('select');
            select.className = 'header-edit-input';
            select.innerHTML = `
                <option value="отчет" ${currentLabel === 'отчет' ? 'selected' : ''}>отчет</option>
                <option value="оценка" ${currentLabel === 'оценка' ? 'selected' : ''}>оценка</option>
                <option value="прогноз" ${currentLabel === 'прогноз' ? 'selected' : ''}>прогноз</option>
            `;
            
            link.textContent = '';
            link.appendChild(select);
            select.focus();
            
            const saveChanges = async () => {
                const newLabel = select.value;
                const newText = `${currentYear} г. ${newLabel}`;
                
                if (newLabel !== currentLabel) {
                    try {
                        const response = await fetch(`/plans/plan/update-column-label/${window.planToken}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                            },
                            body: JSON.stringify({
                                config_id: configId,
                                label: newLabel
                            })
                        });
                        
                        const data = await response.json();
                        if (data.success) {
                            link.textContent = newText;
                            icon.dataset.label = newLabel;
                        } else {
                            link.textContent = currentText;
                        }
                    } catch (error) {
                        console.error('Error:', error);
                        link.textContent = currentText;
                    }
                } else {
                    link.textContent = currentText;
                }
            };
            
            select.addEventListener('blur', saveChanges);
            select.addEventListener('change', saveChanges);
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('SendModal')) {
        new CertificateUploadHandler();
    }

    const tokencolumnIndicator = document.querySelector('#indicatorsTable')?.dataset?.token;
    if (tokencolumnIndicator) {
        window.planToken = tokencolumnIndicator;
        initEditableHeaders();
    }
    
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (selectAllBtn) {
        window.exportPlansLoader = new ExportPlansLoader({
            initialStatus: window.initialStatus || 'all',
            initialYear: window.initialYear || 'all',
            perPage: 5,
            containerId: 'plans-container',
            loadMoreBtnId: 'load-more-btn',
            searchNameId: 'search-name',
            searchOkpoId: 'search-okpo',
            selectAllId: 'selectAllBtn',
            exportFormId: 'exportForm'
        });
    } else {
        window.plansLoader = new PlansLoader({
            initialStatus: window.initialStatus || 'all',
            initialYear: window.initialYear || 'all',
            perPage: 5,
            containerId: 'plans-container',
            loadMoreBtnId: 'load-more-btn',
            searchNameId: 'search-name',
            searchOkpoId: 'search-okpo'
        });
    }

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

    const sentPlanButton = document.getElementById('sentPlanButton');
    const SendModal = document.getElementById('SendModal');
    if (SendModal && sentPlanButton) {
        handleModal(SendModal, sentPlanButton, SendModal.querySelector('.close'));
        
    
        window.sendModalInstance = new SendModalPreview('SendModal');
        
   
        sentPlanButton.addEventListener('click', function() {
            if (window.sendModalInstance) {
                window.sendModalInstance.resetForm();
            }
        });
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

    if (document.querySelector('[data-modal-trigger="deletePlanconfirm"]')) {
        initConfirmModal({
            triggerButton: '[data-modal-trigger="deletePlanconfirm"]',
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