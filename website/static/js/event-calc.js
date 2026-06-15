(function() {
    let planUsdRate = null;
    let costPerToeUsd = null;
    let ratesLoaded = false;

    function formatNumber(value, decimalPlaces = 2) {
        if (isNaN(value) || value === null || value === '') {
            if (decimalPlaces === 0) return '0';
            if (decimalPlaces === 1) return '0,0';
            return '0,00';
        }
        if (decimalPlaces === 0) {
            return Math.round(value).toString();
        }
        if (decimalPlaces === 1) {
            return value.toFixed(1).replace('.', ',');
        }
        return value.toFixed(2).replace('.', ',');
    }

    function parseNumber(value) {
        if (!value) return 0;
        const str = value.toString().trim();
        if (str === '') return 0;
        return parseFloat(str.replace(',', '.')) || 0;
    }

    function getPlanToken() {
        const eventTable = document.getElementById('eventTable');
        if (eventTable && eventTable.dataset.token) {
            console.log('Token from #eventTable:', eventTable.dataset.token);
            return eventTable.dataset.token;
        }
        
        const modalForm = document.querySelector('#AddEventModal form');
        if (modalForm) {
            const actionUrl = modalForm.getAttribute('action');
            if (actionUrl) {
                const match = actionUrl.match(/\/create-event\/([a-zA-Z0-9]+)/);
                if (match && match[1]) {
                    console.log('Token from form action:', match[1]);
                    return match[1];
                }
            }
        }
        
        console.error('Could not find plan token in DOM');
        return null;
    }

    function displayRates(usdRate, costPerToe) {
        const usdDisplay = document.getElementById('usd-rate-display');
        const costDisplay = document.getElementById('cost-per-toe-display');
        
        if (usdDisplay) {
            if (usdRate !== null && usdRate !== undefined && usdRate > 0) {
                usdDisplay.textContent = usdRate.toFixed(4).replace('.', ',');
            } else {
                usdDisplay.textContent = '--';
            }
        }
        
        if (costDisplay) {
            if (costPerToe !== null && costPerToe !== undefined && costPerToe > 0) {
                costDisplay.textContent = costPerToe.toFixed(2).replace('.', ',');
            } else {
                costDisplay.textContent = '--';
            }
        }
    }

    async function fetchPlanRates() {
        try {
            const token = getPlanToken();
            
            if (!token) {
                displayRates(null, null);
                return false;
            }

            const response = await fetch(`/api/plan-rates/${token}`);
            
            if (!response.ok) {
                displayRates(null, null);
                return false;
            }
            
            const data = await response.json();

            if (data.success) {
                if (data.usd_rate && data.usd_rate > 0) {
                    planUsdRate = data.usd_rate;
                } else {
                    planUsdRate = null;
                }

                if (data.cost_per_toe_usd && data.cost_per_toe_usd > 0) {
                    costPerToeUsd = data.cost_per_toe_usd;
                } else {
                    costPerToeUsd = null;
                }

                if (planUsdRate === null && costPerToeUsd === null) {
                    displayRates(null, null);
                    ratesLoaded = false;
                    return false;
                }

                displayRates(planUsdRate, costPerToeUsd);
                ratesLoaded = true;
                updateCalculations();
                return true;
            } else {
                displayRates(null, null);
                ratesLoaded = false;
                return false;
            }
        } catch (error) {
            console.error('Error fetching plan rates:', error);
            displayRates(null, null);
            ratesLoaded = false;
            return false;
        }
    }

    function getSelectedDirectionType() {
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

    function showEffCurrYearWarning(message) {
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

    function validateEffCurrYear() {
        const effTutInput = document.querySelector('#AddEventModal input[name="EffTut"]');
        const effCurrYearInput = document.querySelector('#AddEventModal input[name="EffCurrYear"]');
        
        if (!effTutInput || !effCurrYearInput) return;
        
        const effTut = parseNumber(effTutInput.value);
        let effCurrYear = parseNumber(effCurrYearInput.value);
        
        if (effCurrYear > effTut) {
            effCurrYear = effTut;
            effCurrYearInput.value = formatNumber(effCurrYear, 2);
            
            const warningMessage = `Эффект в текущем году (${formatNumber(effCurrYear, 2)} т.у.т.) не может превышать общий эффект (${formatNumber(effTut, 2)} т.у.т.)`;
            showEffCurrYearWarning(warningMessage);
            
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

    function updateFinancingFieldsReadonly(isDouble, eventType) {
        const budgetFields = ['BudgetState', 'BudgetRep', 'BudgetLoc', 'BudgetOther', 'MoneyOwn', 'MoneyLoan', 'MoneyOther'];
        const volumeFinInput = document.querySelector('#AddEventModal input[name="VolumeFin"]');
        const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
        
        if (isDouble && eventType === 'saving') {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.value = '0';
                    input.readOnly = true;
                    input.disabled = true;
                }
            });
            if (volumeFinInput) {
                volumeFinInput.value = '0';
                volumeFinInput.readOnly = true;
            }
            if (paybackInput) {
                paybackInput.value = '0,0';
                paybackInput.readOnly = true;
            }
        } else if (isDouble && eventType === 'increase') {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.readOnly = false;
                    input.disabled = false;
                }
            });
            if (volumeFinInput) volumeFinInput.readOnly = true;
            if (paybackInput) paybackInput.readOnly = true;
        } else {
            budgetFields.forEach(fieldName => {
                const input = document.querySelector(`#AddEventModal input[name="${fieldName}"]`);
                if (input) {
                    input.readOnly = false;
                    input.disabled = false;
                }
            });
            if (volumeFinInput) volumeFinInput.readOnly = true;
            if (paybackInput) paybackInput.readOnly = true;
        }
    }

    function updateCalculations() {
        if (!ratesLoaded) {
            return;
        }

        if (planUsdRate === null || costPerToeUsd === null) {
            return;
        }

        validateEffCurrYear();

        const eventTypeInput = document.querySelector('#AddEventModal input[name="event_type"]');
        const eventType = eventTypeInput ? eventTypeInput.value : null;
        const directionType = getSelectedDirectionType();
        const isDouble = (directionType === 'double');
        
        updateFinancingFieldsReadonly(isDouble, eventType);
        
        if (isDouble && eventType === 'saving') {
            const effTut = parseNumber(document.querySelector('#AddEventModal input[name="EffTut"]')?.value);
            const effRub = Math.round(effTut * costPerToeUsd * planUsdRate);
            const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
            if (effRubInput) effRubInput.value = formatNumber(effRub, 0);
            return;
        }
        
        const budgetState = parseNumber(document.querySelector('#AddEventModal input[name="BudgetState"]')?.value);
        const budgetRep = parseNumber(document.querySelector('#AddEventModal input[name="BudgetRep"]')?.value);
        const budgetLoc = parseNumber(document.querySelector('#AddEventModal input[name="BudgetLoc"]')?.value);
        const budgetOther = parseNumber(document.querySelector('#AddEventModal input[name="BudgetOther"]')?.value);
        const moneyOwn = parseNumber(document.querySelector('#AddEventModal input[name="MoneyOwn"]')?.value);
        const moneyLoan = parseNumber(document.querySelector('#AddEventModal input[name="MoneyLoan"]')?.value);
        const moneyOther = parseNumber(document.querySelector('#AddEventModal input[name="MoneyOther"]')?.value);
        
        const volumeFin = budgetState + budgetRep + budgetLoc + budgetOther + moneyOwn + moneyLoan + moneyOther;
        const volumeFinInput = document.querySelector('#AddEventModal input[name="VolumeFin"]');
        if (volumeFinInput) volumeFinInput.value = formatNumber(volumeFin, 0);
        
        const effTut = parseNumber(document.querySelector('#AddEventModal input[name="EffTut"]')?.value);
        
        let effRub = Math.round(effTut * costPerToeUsd * planUsdRate);
        const effRubInput = document.querySelector('#AddEventModal input[name="EffRub"]');
        if (effRubInput) effRubInput.value = formatNumber(effRub, 0);
        
        let payback = 0;
        if (effRub > 0) payback = volumeFin / effRub;
        const paybackInput = document.querySelector('#AddEventModal input[name="Payback"]');
        if (paybackInput) paybackInput.value = formatNumber(payback, 1);
    }

    function bindEventCalculations() {
        const fieldsToWatch = [
            '#AddEventModal input[name="EffTut"]',
            '#AddEventModal input[name="EffCurrYear"]',
            '#AddEventModal input[name="BudgetState"]',
            '#AddEventModal input[name="BudgetRep"]',
            '#AddEventModal input[name="BudgetLoc"]',
            '#AddEventModal input[name="BudgetOther"]',
            '#AddEventModal input[name="MoneyOwn"]',
            '#AddEventModal input[name="MoneyLoan"]',
            '#AddEventModal input[name="MoneyOther"]'
        ];
        
        fieldsToWatch.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.removeEventListener('input', updateCalculations);
                el.addEventListener('input', updateCalculations);
            });
        });
        
        const rows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        rows.forEach(row => {
            row.removeEventListener('click', onRowClick);
            row.addEventListener('click', onRowClick);
        });
    }
    
    function onRowClick() {
        setTimeout(updateCalculations, 50);
    }
    
    function initStep2NextButton() {
        const step2NextBtn = document.querySelector('#AddEventModal #step2-next-btn');
        if (step2NextBtn) {
            step2NextBtn.addEventListener('click', function() {
                setTimeout(updateCalculations, 100);
            });
        }
    }
    
    function initStep3BackButton() {
        const step3BackBtn = document.querySelector('#AddEventModal #step3-back-btn');
        if (step3BackBtn) {
            step3BackBtn.addEventListener('click', function() {
                setTimeout(updateCalculations, 100);
            });
        }
    }
    
    function initModalOpen() {
        const addEventModal = document.getElementById('AddEventModal');
        if (addEventModal) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                        if (addEventModal.style.display !== 'none') {
                            setTimeout(function() {
                                if (!ratesLoaded) {
                                    fetchPlanRates();
                                }
                                bindEventCalculations();
                                updateCalculations();
                            }, 100);
                        }
                    }
                });
            });
            observer.observe(addEventModal, { attributes: true });
        }
    }
    
    function initSearchDirections() {
        const searchInput = document.querySelector('#AddEventModal [data-action="search-directions"]');
        if (!searchInput) return;
        
        searchInput.addEventListener('input', function(e) {
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
        });
    }
    
    function initDirectionRowClick() {
        const rows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
        rows.forEach(row => {
            row.addEventListener('click', function() {
                const allRows = document.querySelectorAll('#AddEventModal .modal-table-main tbody tr');
                allRows.forEach(r => r.classList.remove('active-row'));
                this.classList.add('active-row');
                
                const nextButton = document.getElementById('step1-next-btn');
                if (nextButton) {
                    nextButton.disabled = false;
                }
                
                const idDirection = this.querySelector('td:first-child')?.textContent;
                const directionInput = document.querySelector('#AddEventModal input[name="id_direction"]');
                if (directionInput && idDirection) {
                    directionInput.value = idDirection;
                }
            });
        });
    }
    
    if (document.getElementById('AddEventModal')) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', async function() {
                await fetchPlanRates();
                bindEventCalculations();
                initStep2NextButton();
                initStep3BackButton();
                initModalOpen();
                initSearchDirections();
                initDirectionRowClick();
                setTimeout(updateCalculations, 500);
            });
        } else {
            (async function() {
                await fetchPlanRates();
                bindEventCalculations();
                initStep2NextButton();
                initStep3BackButton();
                initModalOpen();
                initSearchDirections();
                initDirectionRowClick();
                setTimeout(updateCalculations, 500);
            })();
        }
    }
})();