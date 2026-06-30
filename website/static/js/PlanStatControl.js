class PlanStatControl {
    constructor(tableId) {
        this.table = document.getElementById(tableId);
        if (!this.table) {
            console.error('[STAT CONTROL] table not found', tableId);
            return;
        }
        this.tbody = this.table.querySelector('tbody');
        this.organizationId = Number(this.table.dataset.organizationId);
        this.planYear = Number(this.table.dataset.planYear);
        this.tooltipElement = null;
        this.mapping = null;
        this.statData = null;
        this.statYears = [];
        this.yearColumns = {};
        this.load();
    }

    createTooltip() {
        if (this.tooltipElement) return;
        
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.style.cssText = `
            display: none;
            position: fixed;
            background: white;
            padding: 20px 30px;
            border-radius: 8px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
            z-index: 9999;
            min-width: 200px;
            text-align: center;
            font-size: 14px;
            color: #333;
            pointer-events: none;
            border: 1px solid #e0e0e0;
        `;
        
        this.tooltipElement.innerHTML = `
            <div style="font-weight: bold; font-size: 13px; color: #666; margin-bottom: 8px;">Статистика</div>
            <div id="stat-value-display" style="font-size: 28px; font-weight: bold; color: #d32f2f; margin: 10px 0;"></div>
            <div id="stat-year-display" style="font-size: 13px; color: #888;"></div>
            <div id="stat-code-display" style="font-size: 13px; color: #888; margin-top: 3px;"></div>
            <div id="stat-report-display" style="font-size: 12px; color: #aaa; margin-top: 3px;"></div>
        `;
        
        document.body.appendChild(this.tooltipElement);
    }

    showTooltip(statValue, year, code, report, event) {
        this.createTooltip();
        
        const valueDisplay = this.tooltipElement.querySelector('#stat-value-display');
        const yearDisplay = this.tooltipElement.querySelector('#stat-year-display');
        const codeDisplay = this.tooltipElement.querySelector('#stat-code-display');
        const reportDisplay = this.tooltipElement.querySelector('#stat-report-display');
        
        valueDisplay.textContent = statValue;
        yearDisplay.textContent = `Год: ${year}`;
        codeDisplay.textContent = `Код: ${code}`;
        reportDisplay.textContent = `Отчет: ${report}`;
        
        this.tooltipElement.style.display = 'block';
        this.updateTooltipPosition(event);
    }

    updateTooltipPosition(event) {
        if (!this.tooltipElement) return;
        
        const x = event.clientX + 15;
        const y = event.clientY + 15;
        
        const tooltipRect = this.tooltipElement.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        let left = x;
        let top = y;
        
        if (x + tooltipRect.width > windowWidth) {
            left = event.clientX - tooltipRect.width - 15;
        }
        
        if (y + tooltipRect.height > windowHeight) {
            top = event.clientY - tooltipRect.height - 15;
        }
        
        this.tooltipElement.style.left = left + 'px';
        this.tooltipElement.style.top = top + 'px';
    }

    hideTooltip() {
        if (this.tooltipElement) {
            this.tooltipElement.style.display = 'none';
        }
    }

    async load() {
        try {
            const response = await fetch(`/api/stat-data/${this.organizationId}`);
            const data = await response.json();
            
            if (!data.success) {
                console.error('stat error', data.message);
                return;
            }
            
            this.mapping = data.mapping;
            this.statData = data.data;
            this.statYears = data.years.map(Number).filter(y => y < this.planYear);
            
            await this.waitForTableReady();
            this.buildYearColumns();
            this.check();
        } catch (e) {
            console.error('[STAT CONTROL] load error', e);
        }
    }

    waitForTableReady() {
        return new Promise((resolve) => {
            const checkTable = () => {
                const rows = this.tbody?.querySelectorAll('tr') || [];
                const hasRealRows = rows.length > 0 && !rows[0].textContent.includes('loading-spinner');
                const hasDataCode = rows.length > 0 && rows[0].dataset.code !== undefined;
                
                if (hasRealRows && hasDataCode) {
                    resolve();
                } else {
                    setTimeout(checkTable, 300);
                }
            };
            checkTable();
        });
    }

    buildYearColumns() {
        this.yearColumns = {};
        
        const headerRow = this.table.querySelector('thead tr:last-child');
        if (!headerRow) {
            console.warn('[STAT CONTROL] no header row with column numbers');
            return;
        }
        
        const ths = headerRow.querySelectorAll('th');
        
        ths.forEach((th, index) => {
            const colNumber = parseInt(th.textContent.trim());
            if (!isNaN(colNumber)) {
                if (colNumber === 5) {
                    this.yearColumns[this.planYear - 2] = index;
                } else if (colNumber === 7) {
                    this.yearColumns[this.planYear - 1] = index;
                } else if (colNumber === 9) {
                    this.yearColumns[this.planYear] = index;
                }
            }
        });
    }

    check() {
        if (Object.keys(this.yearColumns).length === 0) {
            console.warn('[STAT CONTROL] no year columns found');
            return;
        }
        
        Object.entries(this.mapping).forEach(([planCode, mappingItem]) => {
            const planTr = this.findPlanRow(planCode);
            if (!planTr) return;
            
            this.statYears.forEach(year => {
                const column = this.yearColumns[year];
                if (column === undefined) return;
                
                const planValue = this.getCellValue(planTr, column);
                const statValue = this.getStatValue(year, mappingItem);
                
                this.paint(planTr, column, planValue, statValue, year, planCode, mappingItem.report);
            });
        });
    }

    findPlanRow(code) {
        const rows = this.tbody?.querySelectorAll('tr');
        if (!rows || rows.length === 0) return null;
        
        for (const row of rows) {
            const rowCode = row.dataset.code;
            if (String(rowCode) === String(code)) {
                return row;
            }
        }
        return null;
    }

    getStatValue(year, mappingItem) {
        const reportType = mappingItem.report;
        const values = this.statData[year]?.[reportType];
        if (!values) return 0;
        
        let result = 0;
        let total = 0;
        
        if (mappingItem.row.includes('+')) {
            const rows = mappingItem.row.split('+');
            rows.forEach(row => {
                const found = values.find(x => String(x.row) === String(row.trim()) && String(x.column) === String(mappingItem.col));
                if (found) total += Number(found.value);
            });
        } else {
            const found = values.find(x => String(x.row) === String(mappingItem.row) && String(x.column) === String(mappingItem.col));
            if (found) total = Number(found.value);
        }
        
        if (mappingItem.subtract && mappingItem.subtract.length > 0) {
            let subtract = 0;
            mappingItem.subtract.forEach(sub => {
                const [row, col] = sub.split('_');
                const found = values.find(x => String(x.row) === String(row) && String(x.column) === String(col));
                if (found) subtract += Number(found.value);
            });
            result = total - subtract;
        } else {
            result = total;
        }
        
        return Math.round(result * 1000) / 1000;
    }

    getCellValue(row, column) {
        const cells = row.querySelectorAll('td');
        const cell = cells[column];
        if (!cell) return 0;
        return this.normalize(cell.textContent);
    }

    normalize(value) {
        if (!value || value === 'x' || value === 'X') return 0;
        return Number(String(value).replace(/\s/g, '').replace(',', '.'));
    }

    paint(row, column, plan, stat, year, code, report) {
        const cells = row.querySelectorAll('td');
        const cell = cells[column];
        if (!cell) return;
        
        if (Number(plan) === Number(stat)) {
            cell.style.backgroundColor = '#9cff9c';
            cell.removeAttribute('title');
        } else {
            cell.style.backgroundColor = '#ff8c8c';
            cell.style.cursor = 'pointer';
            cell.removeAttribute('title');
            
            const showTooltip = (e) => {
                this.showTooltip(stat, year, code, report, e);
            };
            
            const updatePosition = (e) => {
                this.updateTooltipPosition(e);
            };
            
            const hideTooltip = () => {
                this.hideTooltip();
            };
            
            cell.removeEventListener('mouseenter', showTooltip);
            cell.removeEventListener('mousemove', updatePosition);
            cell.removeEventListener('mouseleave', hideTooltip);
            
            cell.addEventListener('mouseenter', showTooltip);
            cell.addEventListener('mousemove', updatePosition);
            cell.addEventListener('mouseleave', hideTooltip);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const tbody = document.querySelector('#indicators-tbody');
        const rows = tbody?.querySelectorAll('tr');
        
        if (rows && rows.length > 0 && rows[0].dataset.code) {
            new PlanStatControl('indicatorsTable');
        } else {
            setTimeout(() => {
                new PlanStatControl('indicatorsTable');
            }, 1000);
        }
    }, 500);
});