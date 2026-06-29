// website/static/js/stats-control.js

class StatValidator {
    constructor(token, organizationId, year) {
        this.token = token;
        this.organizationId = organizationId;
        this.year = year;
        this.mapping = null;
        this.statData = null;
        this.planData = null;
        this.validationResults = {};
        this.isInitialized = false;
    }

    async init() {
        try {
            await this.loadMapping();
            await this.loadStatData();
            this.planData = this.extractPlanData();
            this.validate();
            this.isInitialized = true;
            return true;
        } catch (error) {
            console.error('StatValidator initialization error:', error);
            return false;
        }
    }

    async loadMapping() {
        try {
            const response = await fetch(`/api/stat-data/mapping`);
            const data = await response.json();
            
            if (data.success) {
                this.mapping = data.mapping;
            } else {
                throw new Error('Failed to load mapping');
            }
        } catch (error) {
            console.error('Error loading mapping:', error);
            throw error;
        }
    }

    async loadStatData() {
        try {
            const response = await fetch(
                `/api/stat-data/${this.organizationId}/${this.year}`
            );
            const data = await response.json();
            
            if (data.success) {
                this.statData = data.data;
            } else {
                throw new Error(data.message || 'Failed to load statistical data');
            }
        } catch (error) {
            console.error('Error loading stat data:', error);
            throw error;
        }
    }

    extractPlanData() {
        const planData = {};
        const tbody = document.getElementById('indicators-tbody');
        
        if (!tbody) {
            console.warn('Indicators table not found');
            return planData;
        }

        const rows = tbody.querySelectorAll('tr.menu-row');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 12) return;

            const codeCell = cells[10];
            if (!codeCell) return;
            
            const code = codeCell.textContent.trim();
            if (!code) return;

            const value2024 = this.parseNumeric(cells[3]?.textContent.trim() || '');
            const value2025 = this.parseNumeric(cells[5]?.textContent.trim() || '');
            const value2026 = this.parseNumeric(cells[8]?.textContent.trim() || '');
            const value2026_tut = this.parseNumeric(cells[9]?.textContent.trim() || '');
            
            const rowNumCell = cells[0];
            let planRow = null;
            if (rowNumCell) {
                const text = rowNumCell.textContent.trim();
                if (text && !isNaN(parseFloat(text))) {
                    planRow = parseFloat(text);
                }
            }

            planData[code] = {
                code: code,
                row: planRow,
                value2024: value2024,
                value2025: value2025,
                value2026: value2026,
                value2026_tut: value2026_tut,
                element: row
            };
        });

        return planData;
    }

    parseNumeric(value) {
        if (!value || value === 'x' || value === 'X' || value === '-') {
            return null;
        }
        
        const cleaned = value.replace(/,/g, '.').replace(/\s/g, '');
        const num = parseFloat(cleaned);
        return isNaN(num) ? null : num;
    }

    validate() {
        if (!this.mapping || !this.statData || !this.planData) {
            console.warn('Cannot validate: missing data');
            return;
        }

        if (this.mapping['12-tek']) {
            this.validate12Tek();
        }

        if (this.mapping['4-tek']) {
            this.validate4Tek();
        }

        this.applyValidationResults();
    }

    validate12Tek() {
        const mapping12 = this.mapping['12-tek'];
        const stat12 = this.statData['12-tek'];
        
        if (!stat12) {
            console.warn('12-TEK data not found');
            return;
        }

        for (const [key, mappingInfo] of Object.entries(mapping12)) {
            const parts = key.split('_');
            if (parts.length < 3) continue;
            
            const rowCode = parts[1];
            const colCode = parts[2];
            
            const statKey = `${rowCode}_${colCode}`;
            const statValue = stat12.values[statKey];
            
            const planRow = mappingInfo.plan_row;
            
            let planValue = null;
            let planCode = null;
            
            for (const [code, data] of Object.entries(this.planData)) {
                if (data.row === planRow) {
                    planValue = data.value2024;
                    planCode = code;
                    break;
                }
            }
            
            this.validationResults[key] = {
                type: '12-tek',
                rowCode: rowCode,
                colCode: colCode,
                planRow: planRow,
                planCode: planCode,
                statValue: statValue,
                planValue: planValue,
                description: mappingInfo.description,
                isValid: this.isEqual(statValue, planValue),
                statExists: statValue !== null && statValue !== undefined,
                planExists: planValue !== null && planValue !== undefined
            };
        }
    }

    validate4Tek() {
        const mapping4 = this.mapping['4-tek'];
        const stat4 = this.statData['4-tek'];
        
        if (!stat4) {
            console.warn('4-TEK data not found');
            return;
        }

        for (const [key, mappingInfo] of Object.entries(mapping4)) {
            let rowCode = null;
            let colCode = null;
            
            const match = key.match(/row_([\d+]+)_col_(\d+)/);
            if (match) {
                rowCode = match[1];
                colCode = match[2];
            } else {
                continue;
            }
            
            let statValue = null;
            if (rowCode.includes('+')) {
                const rows = rowCode.split('+');
                let sum = 0;
                let hasValue = false;
                for (const r of rows) {
                    const statKey = `${r}_${colCode}`;
                    const val = stat4.values[statKey];
                    if (val !== null && val !== undefined) {
                        sum += val;
                        hasValue = true;
                    }
                }
                if (hasValue) {
                    statValue = sum;
                }
            } else {
                const statKey = `${rowCode}_${colCode}`;
                statValue = stat4.values[statKey];
            }
            
            const planRow = mappingInfo.plan_row;
            let planValue = null;
            let planCode = null;
            
            for (const [code, data] of Object.entries(this.planData)) {
                if (data.row === planRow) {
                    planValue = data.value2024;
                    planCode = code;
                    break;
                }
            }
            
            this.validationResults[key] = {
                type: '4-tek',
                rowCode: rowCode,
                colCode: colCode,
                planRow: planRow,
                planCode: planCode,
                statValue: statValue,
                planValue: planValue,
                description: mappingInfo.description,
                isValid: this.isEqual(statValue, planValue),
                statExists: statValue !== null && statValue !== undefined,
                planExists: planValue !== null && planValue !== undefined
            };
        }
    }

    isEqual(statValue, planValue) {
        if (statValue === null || statValue === undefined || planValue === null || planValue === undefined) {
            return false;
        }
        
        const tolerance = 0.001;
        return Math.abs(statValue - planValue) <= tolerance;
    }

    applyValidationResults() {
        for (const [key, result] of Object.entries(this.validationResults)) {
            if (!result.planCode) continue;
            
            const planData = this.planData[result.planCode];
            if (!planData || !planData.element) continue;
            
            const row = planData.element;
            const cells = row.querySelectorAll('td');
            if (cells.length <= 3) continue;
            
            const valueCell = cells[3];
            
            valueCell.classList.remove('stat-valid', 'stat-invalid', 'stat-no-data');
            
            if (!result.statExists) {
                valueCell.classList.add('stat-no-data');
                valueCell.title = 'No statistical data available';
            } else if (result.isValid) {
                valueCell.classList.add('stat-valid');
                valueCell.title = 'Matches statistics: ' + result.statValue;
            } else {
                valueCell.classList.add('stat-invalid');
                valueCell.title = 'Does not match: plan=' + result.planValue + ', stat=' + result.statValue;
            }
        }
    }
}

function initStatValidation() {
    try {
        const table = document.querySelector('#indicatorsTable');
        if (!table) {
            console.warn('Indicators table not found');
            return;
        }

        const token = table.dataset.token;
        if (!token) {
            console.warn('Token not found for stat validation');
            return;
        }

        const organizationId = window.organizationId || table.dataset.organizationId;
        const year = window.reportYear || table.dataset.planYear;

        if (!organizationId || !year) {
            console.warn('Organization ID or Year not found');
            return;
        }

        const tbody = document.getElementById('indicators-tbody');
        if (!tbody) {
            console.warn('Indicators tbody not found');
            return;
        }

        const checkTableLoaded = setInterval(() => {
            const rows = tbody.querySelectorAll('tr.menu-row');
            if (rows.length > 0) {
                clearInterval(checkTableLoaded);
                loadValidator(token, parseInt(organizationId), parseInt(year));
            }
        }, 500);

        setTimeout(() => {
            clearInterval(checkTableLoaded);
        }, 10000);

    } catch (error) {
        console.error('Error initializing stat validation:', error);
    }
}

async function loadValidator(token, organizationId, year) {
    try {
        const validator = new StatValidator(token, organizationId, year);
        const success = await validator.init();
        
        if (success) {
            window.statValidator = validator;
            console.log('Stat validation completed successfully');
            if (window.isAuditor === true) {
                setTimeout(addStatContextMenu, 500);
            }
        }
    } catch (error) {
        console.error('Error loading validator:', error);
    }
}

function addStatContextMenu() {
    if (window.isAuditor !== true) {
        return;
    }

    const tbody = document.getElementById('indicators-tbody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr.menu-row');
    rows.forEach(row => {
        row.removeEventListener('contextmenu', onRowContextMenu);
        row.addEventListener('contextmenu', onRowContextMenu);
    });
}

function onRowContextMenu(event) {
    event.preventDefault();
    const row = event.currentTarget;
    const cells = row.querySelectorAll('td');
    if (cells.length < 3) return;

    const codeCell = cells[10];
    if (!codeCell) return;
    
    const code = codeCell.textContent.trim();
    if (!code) return;

    const valueCell = cells[3];
    if (!valueCell) return;

    showStatValidationPopup(event, code, valueCell);
}

function showStatValidationPopup(event, code, valueCell) {
    const existingPopup = document.querySelector('.stat-popup');
    if (existingPopup) {
        existingPopup.remove();
    }

    let result = null;
    let key = null;

    if (window.statValidator) {
        for (const [k, r] of Object.entries(window.statValidator.validationResults)) {
            if (r.planCode === code) {
                result = r;
                key = k;
                break;
            }
        }
    }

    const popup = document.createElement('div');
    popup.className = 'stat-popup';
    popup.style.cssText = `
        position: fixed;
        background: #2d2d2d;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 12px 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        z-index: 9999;
        min-width: 220px;
        max-width: 350px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.5;
        border: 1px solid #444;
        pointer-events: none;
        animation: popupFadeIn 0.15s ease;
    `;

    let content = '';
    
    if (!result || !result.statExists) {
        content = `
            <div style="color: #ffd93d; font-weight: 500; margin-bottom: 4px;">No statistical data</div>
            <div style="color: #999; font-size: 12px;">Code: ${code}</div>
        `;
    } else {
        const statusColor = result.isValid ? '#6bcb77' : '#ff6b6b';
        const statusText = result.isValid ? 'Matches' : 'Does not match';
        
        content = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="color: #aaa; font-size: 12px;">${result.description || code}</span>
                <span style="color: ${statusColor}; font-weight: 600; font-size: 12px;">${statusText}</span>
            </div>
            <div style="display: grid; grid-template-columns: auto 1fr; gap: 2px 16px; font-size: 13px;">
                <span style="color: #999;">Plan:</span>
                <span style="color: #fff;">${result.planValue !== null ? result.planValue.toFixed(2) : '-'}</span>
                <span style="color: #999;">Statistics:</span>
                <span style="color: #fff;">${result.statValue !== null ? result.statValue.toFixed(2) : '-'}</span>
                <span style="color: #999;">Difference:</span>
                <span style="color: ${statusColor};">
                    ${result.planValue !== null && result.statValue !== null ? (result.statValue - result.planValue).toFixed(2) : '-'}
                </span>
            </div>
        `;
    }

    popup.innerHTML = content;

    const x = event.clientX;
    const y = event.clientY;
    const popupWidth = 280;
    const popupHeight = 130;

    let left = x + 15;
    let top = y - 10;

    if (left + popupWidth > window.innerWidth) {
        left = x - popupWidth - 15;
    }
    if (top + popupHeight > window.innerHeight) {
        top = window.innerHeight - popupHeight - 10;
    }
    if (top < 10) top = 10;
    if (left < 10) left = 10;

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';

    document.body.appendChild(popup);

    setTimeout(() => {
        document.addEventListener('click', function removePopup() {
            popup.remove();
            document.removeEventListener('click', removePopup);
        });
        document.addEventListener('scroll', function removePopup() {
            popup.remove();
            document.removeEventListener('scroll', removePopup);
        }, { once: true });
    }, 50);
}

function checkAndAddStatContextMenu() {
    if (window.isAuditor !== true) {
        return;
    }

    const tbody = document.getElementById('indicators-tbody');
    if (!tbody) return;

    const checkRows = setInterval(() => {
        const rows = tbody.querySelectorAll('tr.menu-row');
        if (rows.length > 0) {
            clearInterval(checkRows);
            addStatContextMenu();
            
            const observer = new MutationObserver(() => {
                addStatContextMenu();
            });
            observer.observe(tbody, { childList: true, subtree: true });
        }
    }, 500);

    setTimeout(() => {
        clearInterval(checkRows);
    }, 10000);
}

window.refreshStatValidation = async function() {
    if (window.statValidator) {
        const table = document.querySelector('#indicatorsTable');
        if (!table) return;
        
        const token = table.dataset.token;
        const organizationId = window.organizationId || table.dataset.organizationId;
        const year = window.reportYear || table.dataset.planYear;
        
        if (token && organizationId && year) {
            const newValidator = new StatValidator(token, parseInt(organizationId), parseInt(year));
            await newValidator.init();
            window.statValidator = newValidator;
            
            if (window.isAuditor === true) {
                addStatContextMenu();
            }
        }
    }
};

const style = document.createElement('style');
style.textContent = `
    .stat-popup {
        pointer-events: none;
        user-select: none;
    }
    @keyframes popupFadeIn {
        from { opacity: 0; transform: scale(0.95); }
        to { opacity: 1; transform: scale(1); }
    }
    td.stat-valid {
        background-color: rgba(107, 203, 119, 0.15) !important;
    }
    td.stat-invalid {
        background-color: rgba(255, 107, 107, 0.15) !important;
    }
    td.stat-no-data {
        background-color: rgba(255, 217, 61, 0.10) !important;
    }
`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (window.isAuditor === true) {
            initStatValidation();
            setTimeout(checkAndAddStatContextMenu, 3000);
        }
    }, 1500);
});

document.addEventListener('indicatorsLoaded', function() {
    if (window.isAuditor === true) {
        initStatValidation();
        setTimeout(checkAndAddStatContextMenu, 1000);
    }
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StatValidator, initStatValidation, checkAndAddStatContextMenu, refreshStatValidation };
}