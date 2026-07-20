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

        const coeffInputs = addModal.querySelectorAll('.coeff-input-display');
        coeffInputs.forEach(input => {
            input.removeEventListener('input', this.updateTutResults.bind(this));
            input.addEventListener('input', this.updateTutResults.bind(this));
        });

        this.updateTutResults();
    }

    initEditIndicatorModal() {
        const editModal = document.getElementById('EditIndicatorModal');
        if (!editModal) return;

        const numericInputs = editModal.querySelectorAll('.app-numeric-input');
        numericInputs.forEach(input => {
            input.removeEventListener('input', updateEditTutResults);
            input.addEventListener('input', updateEditTutResults);
        });

        const coeffInputs = editModal.querySelectorAll('.coeff-input-display');
        coeffInputs.forEach(input => {
            input.removeEventListener('input', updateEditTutResults);
            input.addEventListener('input', updateEditTutResults);
        });
    }

    onIndicatorRowClick(event) {
        const row = event.currentTarget;
        const selectedDisplay = document.getElementById('selected-indicator-display');
        const selectedName = document.getElementById('selected-indicator-name');
        const selectedCode = document.getElementById('selected-indicator-code');
        const idIndicatorInput = document.querySelector('input[name="id_indicator"]');
        
        const code = row.cells[1]?.textContent.trim() || '';
        const name = row.cells[2]?.textContent.trim() || '';
        const coeff = row.cells[4]?.textContent.trim() || '0';
        const unitName = row.cells[3]?.textContent.trim() || 'ед. изм.';
        const indicatorId = row.cells[0]?.textContent.trim() || '';
        const group = row.querySelector('td[data-group]')?.getAttribute('data-group') || '';
        
        if (selectedName) {
            selectedName.textContent = `${name}`;
        }        
        if (selectedCode) {
            selectedCode.textContent = `${code}`;
        }
        if (selectedDisplay) {
            selectedDisplay.style.display = 'block';
        }
        if (idIndicatorInput) {
            idIndicatorInput.value = indicatorId;
        }
        
        let coeffValue = parseFloat(coeff.replace(',', '.'));
        if (isNaN(coeffValue)) coeffValue = 0;
        const formattedCoeff = coeffValue.toFixed(3).replace('.', ',');
        
        const coeffInputs = document.querySelectorAll('#AddIndicatorModal .coeff-input-display');
        const isTut = unitName === 'т у.т.';
        
        coeffInputs.forEach(input => {
            input.value = formattedCoeff;
            if (isTut) {
                input.readOnly = true;
                input.style.backgroundColor = '#f5f5f5';
                input.style.cursor = 'not-allowed';
                input.style.color = '#999';
            } else {
                input.readOnly = false;
                input.style.backgroundColor = 'white';
                input.style.cursor = 'text';
                input.style.color = 'var(--green-main)';
            }
        });
        
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
                decimalPlaces = 2;
                defaultValue = '0,00';
            } else if (groupNumber === 6 || groupNumber === 7 || groupNumber === 8) {
                decimalPlaces = 1;
                defaultValue = '0,0';
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
                return value.toFixed(2).replace('.', ',');
            } else if (groupId === 6 || groupId === 7 || groupId === 8) {
                return value.toFixed(1).replace('.', ',');
            } else {
                return Math.round(value).toString().replace('.', ',');
            }
        };
        
        const years = ['before', 'prev', 'current'];
        years.forEach((year) => {
            const input = document.querySelector(`#AddIndicatorModal input[data-year="${year}"]`);
            const coeffInput = document.querySelector(`#AddIndicatorModal .coeff-input-display[data-year="${year}"]`);
            const resultSpan = document.getElementById(`result-${year}`);
            
            if (input && resultSpan && coeffInput) {
                let currentCoeff = 0;
                if (coeffInput.value) {
                    let coeffText = coeffInput.value.replace(',', '.');
                    currentCoeff = parseFloat(coeffText);
                }
                if (isNaN(currentCoeff)) currentCoeff = 0;
                
                if (input.value) {
                    let inputValue = input.value.replace(',', '.');
                    let value = parseFloat(inputValue);
                    if (isNaN(value)) value = 0;
                    const tutValue = value * currentCoeff;
                    let formattedResult = formatResultValue(tutValue, groupNumber);
                    resultSpan.textContent = '= ' + formattedResult + ' т у.т.';
                } else {
                    resultSpan.textContent = '= 0 т у.т.';
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
        
        const specialCodes = ['1796', '1797', '9916', '9917', '1425', '1424'];
        const reverseCodes = ['1000', '1105', '1405', '1104', '1404', '260'];
        
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
                    return value.toFixed(2).replace('.', ',');
                } else if (groupId === 6 || groupId === 7 || groupId === 8) {
                    return value.toFixed(1).replace('.', ',');
                } else {
                    return Math.round(value).toString().replace('.', ',');
                }
            };
            
            // Определение стиля для ячейки разницы
            let backgroundColor = '';
            let iconHtml = '';
            let textColor = '';
            
            if (row.group === 5 || row.group === 6) {
                // Для групп 5 и 6 - без заливки
            } else if (row.difference !== null && row.difference !== undefined && !isNaN(row.difference) && row.difference !== 0) {
                const code = String(row.code || '');
                const isSpecialCode = specialCodes.includes(code);
                const isReverseCode = reverseCodes.includes(code);
                
                const useReverseColoring = 
                    isSpecialCode ||
                    (row.is_local === true && row.group === 1) ||
                    [1.1, 1.2, 2, 3, 4, 5, 6, 7, 8].some(g => Math.abs(row.group - g) < 0.01);
                
                const isNegative = row.difference < 0;
                const formattedValue = formatValue(row.difference, row.group);
                
                // Определяем цвета для полной заливки ячейки
                let color, bgColor, icon;
                if (useReverseColoring) {
                    if (isNegative) {
                        // Снижение - красный (плохо)
                        color = '#dc3545';
                        bgColor = 'rgba(220, 53, 69, 0.12)';
                        icon = '↓';
                    } else {
                        // Увеличение - зеленый (хорошо)
                        color = '#28a745';
                        bgColor = 'rgba(40, 167, 69, 0.12)';
                        icon = '↑';
                    }
                } else {
                    if (isNegative) {
                        // Снижение - зеленый (хорошо - экономия)
                        color = '#28a745';
                        bgColor = 'rgba(40, 167, 69, 0.12)';
                        icon = '↓';
                    } else {
                        // Увеличение - красный (плохо - перерасход)
                        color = '#dc3545';
                        bgColor = 'rgba(220, 53, 69, 0.12)';
                        icon = '↑';
                    }
                }
                
                backgroundColor = bgColor;
                textColor = color;
                iconHtml = `<span style="color: ${color}; font-weight: 600; margin-right: 4px;">${icon}</span>`;
            }
            
            // Формируем содержимое ячейки
            let cellContent = '';
            if (row.group === 5 || row.group === 6) {
                cellContent = 'x';
            } else if (row.difference !== null && row.difference !== undefined && !isNaN(row.difference) && row.difference !== 0) {
                const formattedValue = formatValue(row.difference, row.group);
                cellContent = `${iconHtml}<span style="color: ${textColor}; font-weight: 600;">${formattedValue}</span>`;
            } else {
                cellContent = formatValue(row.difference, row.group);
            }
            
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
                <td class="difference-cell" style="border-right: none; text-align: center; background-color: ${backgroundColor};">
                    ${cellContent}
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

function checkCategoryRequired() {
    const selectedIndicatorName = document.getElementById('selected-indicator-name');
    const selectedIndicatorCode = document.getElementById('selected-indicator-code');
    const categorySection = document.getElementById('category-section');
    const nameSection = document.getElementById('name-section');
    const submitBtn = document.getElementById('submit-indicator-btn');
    const categoryRadios = document.querySelectorAll('input[name="fuel_category"]');
    const nameInput = document.getElementById('name-section-input');
    
    if (!selectedIndicatorName || !categorySection || !nameSection) return;
    
    const indicatorText = 'selectedIndicatorName.textContent';
    const indicatorTextCode = selectedIndicatorCode ? selectedIndicatorCode.textContent : '';
    
    const isCategoryRequired = indicatorTextCode.includes('2023') || indicatorTextCode.includes('2024');
    
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
        const noneRadio = document.querySelector('input[name="fuel_category"][value="none"]');
        if (noneRadio && !Array.from(categoryRadios).some(radio => radio.checked)) {
            noneRadio.checked = true;
        }
        
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
            decimalPlaces = 2;
            defaultValue = '0,00';
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            decimalPlaces = 1;
            defaultValue = '0,0';
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
            return value.toFixed(2).replace('.', ',');
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            return value.toFixed(1).replace('.', ',');
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
                const displayName = data.name;
                // const displayName = indicatorCode ? indicatorCode + ' - ' + data.name : data.name;
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
            const isCoeffLocked = ['9913', '9914', '1404', '1104', '1424', '1105', '1405', '1425', '1445'].includes(indicatorCode);
            const isTut = unitName === 'т у.т.';
            
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
            
            // Устанавливаем категорию топлива
            if (indicatorCode === '2023' || indicatorCode === '2024') {
                if (editCategorySection) editCategorySection.style.display = 'block';
                if (editNameSection) editNameSection.style.display = 'block';
                
                if (editNameInput) {
                    editNameInput.required = true;
                    if (data.note) {
                        editNameInput.value = data.note;
                    }
                }
                
                // Устанавливаем выбранную радио-кнопку
                const categoryRadios = document.querySelectorAll('#EditIndicatorModal input[name="fuel_category"]');
                let categoryValue = 'none';
                if (data.is_local) {
                    categoryValue = 'local';
                } else if (data.is_renewable) {
                    categoryValue = 'renewable';
                }
                
                categoryRadios.forEach(function(radio) {
                    if (radio.value === categoryValue) {
                        radio.checked = true;
                    } else {
                        radio.checked = false;
                    }
                });
                
                // Валидация формы
                function validateEditForm() {
                    const isCategoryChecked = Array.from(categoryRadios).some(radio => radio.checked);
                    const isNameFilled = editNameInput && editNameInput.value.trim() !== '';
                    const submitEditBtn = document.getElementById('edit-submit-btn');
                    
                    if (submitEditBtn) {
                        submitEditBtn.disabled = !(isCategoryChecked && isNameFilled);
                    }
                }
                
                categoryRadios.forEach(function(radio) {
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
                const submitEditBtn = document.getElementById('edit-submit-btn');
                if (submitEditBtn) submitEditBtn.disabled = false;
            }
            
            const coeffValue = data.CoeffToTut || 0;
            const formattedCoeff = coeffValue.toFixed(3).replace('.', ',');
            
            const coeffInputs = document.querySelectorAll('#EditIndicatorModal .coeff-input-display');
            coeffInputs.forEach(function(input) {
                let valueToSet = formattedCoeff;
                
                if (data.coeff_before_prev && input.dataset.year === 'before') {
                    valueToSet = data.coeff_before_prev.toFixed(3).replace('.', ',');
                } else if (data.coeff_prev && input.dataset.year === 'prev') {
                    valueToSet = data.coeff_prev.toFixed(3).replace('.', ',');
                } else if (data.coeff_current && input.dataset.year === 'current') {
                    valueToSet = data.coeff_current.toFixed(3).replace('.', ',');
                }
                
                input.value = valueToSet;
                
                if (isTut || isCoeffLocked || !isCoeffEditable) {
                    input.readOnly = true;
                    input.style.backgroundColor = '#f5f5f5';
                    input.style.cursor = 'not-allowed';
                    input.style.color = '#999';
                } else {
                    input.readOnly = false;
                    input.style.backgroundColor = 'white';
                    input.style.cursor = 'text';
                    input.style.color = 'var(--green-main)';
                }
            });
            
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
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / data.used_coeff_current) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            } else if (!isSpecialGroup) {
                const valBeforePrev = data.QYearBeforePrev ? (data.QYearBeforePrev / data.used_coeff_before) : null;
                const valPrev = data.QYearPrev ? (data.QYearPrev / data.used_coeff_prev) : null;
                setFormattedValue('QYearBeforePrev-edit', valBeforePrev, groupNumber);
                setFormattedValue('QYearCurr-edit', valPrev, groupNumber);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / data.used_coeff_current) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            } else {
                setFormattedValue('QYearBeforePrev-edit', null, groupNumber);
                setFormattedValue('QYearCurr-edit', null, groupNumber);
                const valCurrent = data.QYearCurrent ? (data.QYearCurrent / data.used_coeff_current) : null;
                setFormattedValue('QYearCurrent-edit', valCurrent, groupNumber);
            }

            const form = document.getElementById('editIndicatorForm');
            if (form) {
                const token = document.querySelector('#indicatorsTable')?.dataset?.token;
                if (token) {
                    form.action = `/plans/plan/edit-indicator/${token}`;
                }
            }
            
            setTimeout(function() {
                updateEditTutResults();
            }, 100);
        })
        .catch(error => {
            console.error('Error fetching indicator data:', error);
            alert('Ошибка при загрузке данных: ' + error.message);
        });
}

function updateEditTutResults() {
    const activeRow = document.querySelector('.rows .active-row');
    let groupValue = '';
    let indicatorCode = '';
    
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
            return value.toFixed(2).replace('.', ',');
        } else if (groupId === 6 || groupId === 7 || groupId === 8) {
            return value.toFixed(1).replace('.', ',');
        } else {
            return Math.round(value).toString().replace('.', ',');
        }
    };
    
    const isCodes9911to9914 = ['9911', '9912', '9913', '9914'].includes(indicatorCode);
    
    const updateResult = function(inputId, resultId) {
        const input = document.getElementById(inputId);
        const resultSpan = document.getElementById(resultId);
        let year = 'current';
        if (inputId.includes('Before')) {
            year = 'before';
        } else if (inputId.includes('Curr') || inputId.includes('Prev')) {
            year = 'prev';
        }
        const coeffInput = document.querySelector('#EditIndicatorModal .coeff-input-display[data-year="' + year + '"]');
        
        if (input && resultSpan) {
            let currentCoeff = 0;
            if (coeffInput && coeffInput.value) {
                let coeffText = coeffInput.value.replace(',', '.');
                currentCoeff = parseFloat(coeffText);
            }
            if (isNaN(currentCoeff)) currentCoeff = 0;
            
            if (input.value) {
                let inputValue = input.value.replace(',', '.');
                let value = parseFloat(inputValue);
                if (isNaN(value)) value = 0;
                const tutValue = value * currentCoeff;
                let formattedResult = formatResultValue(tutValue, groupNumber);
                resultSpan.textContent = '= ' + formattedResult + ' т у.т.';
            } else {
                resultSpan.textContent = '= 0 т у.т.';
            }
        }
    };
    
    if (isCodes9911to9914) {
        updateResult('QYearCurrent-edit', 'edit-result-current');
    } else if (isSpecialGroup) {
        updateResult('QYearCurrent-edit', 'edit-result-current');
    } else {
        updateResult('QYearBeforePrev-edit', 'edit-result-before');
        updateResult('QYearCurr-edit', 'edit-result-prev');
        updateResult('QYearCurrent-edit', 'edit-result-current');
    }
}