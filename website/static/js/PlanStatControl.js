class PlanStatControl {
    constructor(tableId, isRegionManagement, isAdmin) {
        this.table = document.getElementById(tableId);
        if (!this.table) {
            console.error('[STAT CONTROL] table not found', tableId);
            return;
        }
        this.isRegionManagement = isRegionManagement || false;
        this.isAdmin = isAdmin || false;
        
        if (!this.isRegionManagement && !this.isAdmin) {
            console.log('[STAT CONTROL] Access denied - not region management or admin');
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
        this.logContainer = null;
        this.logs = [];
        this.indicatorsEnabled = this.getCookie('stat_indicators_enabled') !== 'false';
        this.logsVisible = this.getCookie('stat_logs_visible') === 'true';
        this.isInitialized = false;
        this.hasStatData = false;
        this.load();
    }

    getCookie(name) {
        const value = '; ' + document.cookie;
        const parts = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    setCookie(name, value, days) {
        days = days || 365;
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = name + '=' + value + '; expires=' + date.toUTCString() + '; path=/';
    }

    addLog(message, type) {
        type = type || 'info';
        const timestamp = new Date().toLocaleTimeString();
        this.logs.push({ timestamp, message, type });
        this.renderLogs();
    }

    renderLogs() {
        if (!this.logContainer) return;
        const textarea = this.logContainer.querySelector('#logs-textarea');
        if (!textarea) return;
        textarea.value = '';
        if (this.logs.length === 0) {
            textarea.value = 'Нет замечаний. Все значения совпадают.';
            return;
        }
        this.logs.forEach(log => {
            const color = log.type === 'error' ? '🔴' : log.type === 'warn' ? '🟡' : '🟢';
            textarea.value += `[${log.timestamp}] ${color} ${log.message}\n`;
        });
        textarea.scrollTop = textarea.scrollHeight;
    }

    clearLogs() {
        this.logs = [];
        this.renderLogs();
        if (this.logContainer) {
            this.hideLogContainer();
            this.logsVisible = false;
            this.setCookie('stat_logs_visible', 'false');
            const logToggleBtn = document.getElementById('statLogToggleBtn');
            if (logToggleBtn) {
                logToggleBtn.classList.remove('active');
                const status = document.getElementById('statLogStatus');
                if (status) {
                    status.textContent = 'Выкл';
                    status.className = 'toggle-status status-off';
                }
            }
        }
    }

    showLogContainer() {
        if (!this.logContainer) return;
        this.logContainer.classList.remove('hidden');
        this.logContainer.style.display = 'block';
        void this.logContainer.offsetWidth;
        this.logContainer.classList.add('visible');
        this.logsVisible = true;
        this.setCookie('stat_logs_visible', 'true');
        const logToggleBtn = document.getElementById('statLogToggleBtn');
        if (logToggleBtn) {
            logToggleBtn.classList.add('active');
            const status = document.getElementById('statLogStatus');
            if (status) {
                status.textContent = 'Вкл';
                status.className = 'toggle-status status-on';
            }
        }
    }

    hideLogContainer() {
        if (!this.logContainer) return;
        this.logContainer.classList.remove('visible');
        this.logContainer.classList.add('hidden');
        setTimeout(() => {
            this.logContainer.style.display = 'none';
            this.logContainer.classList.remove('hidden');
        }, 300);
        this.logsVisible = false;
        this.setCookie('stat_logs_visible', 'false');
        const logToggleBtn = document.getElementById('statLogToggleBtn');
        if (logToggleBtn) {
            logToggleBtn.classList.remove('active');
            const status = document.getElementById('statLogStatus');
            if (status) {
                status.textContent = 'Выкл';
                status.className = 'toggle-status status-off';
            }
        }
    }

    toggleLogContainer() {
        if (!this.logContainer) return;
        if (this.logContainer.style.display === 'block' && !this.logContainer.classList.contains('hidden')) {
            this.hideLogContainer();
        } else {
            this.showLogContainer();
        }
    }

    createLogContainer() {
        if (this.logContainer) return;
        
        this.logContainer = document.createElement('div');
        this.logContainer.className = 'stat-log-popup';
        this.logContainer.style.display = 'none';
        
        this.logContainer.innerHTML = `
            <div class="stat-log-header">
                <span class="stat-log-title">Логи контроля</span>
                <button class="stat-log-clear-btn" title="Очистить логи">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18 6L6 18"/>
                        <path d="M6 6L18 18"/>
                    </svg>
                </button>
            </div>
            <textarea id="logs-textarea" class="stat-log-textarea" readonly></textarea>
        `;
        
        document.body.appendChild(this.logContainer);
        
        const clearBtn = this.logContainer.querySelector('.stat-log-clear-btn');
        clearBtn.addEventListener('click', () => {
            this.clearLogs();
        });
    }

    initUI() {
        const logToggleBtn = document.getElementById('statLogToggleBtn');
        const logStatus = document.getElementById('statLogStatus');
        if (logToggleBtn) {
            if (this.logsVisible) {
                logToggleBtn.classList.add('active');
                if (logStatus) {
                    logStatus.textContent = 'Вкл';
                    logStatus.className = 'toggle-status status-on';
                }
            } else {
                logToggleBtn.classList.remove('active');
                if (logStatus) {
                    logStatus.textContent = 'Выкл';
                    logStatus.className = 'toggle-status status-off';
                }
            }
            logToggleBtn.addEventListener('click', () => {
                this.toggleLogContainer();
            });
        }

        const indicatorToggleBtn = document.getElementById('statIndicatorToggleBtn');
        const indicatorStatus = document.getElementById('statIndicatorStatus');
        if (indicatorToggleBtn) {
            if (!this.hasStatData) {
                indicatorToggleBtn.classList.add('non');
                indicatorToggleBtn.style.opacity = '0.5';
                indicatorToggleBtn.style.cursor = 'not-allowed';
                if (indicatorStatus) {
                    indicatorStatus.textContent = 'Нет данных';
                    indicatorStatus.className = 'toggle-status status-off';
                }
                return;
            }
            
            if (this.indicatorsEnabled) {
                indicatorToggleBtn.classList.add('active');
                if (indicatorStatus) {
                    indicatorStatus.textContent = 'Вкл';
                    indicatorStatus.className = 'toggle-status status-on';
                }
            } else {
                indicatorToggleBtn.classList.remove('active');
                if (indicatorStatus) {
                    indicatorStatus.textContent = 'Выкл';
                    indicatorStatus.className = 'toggle-status status-off';
                }
            }
            indicatorToggleBtn.addEventListener('click', () => {
                if (!this.hasStatData) return;
                this.indicatorsEnabled = !this.indicatorsEnabled;
                this.setCookie('stat_indicators_enabled', String(this.indicatorsEnabled));
                this.toggleIndicators(this.indicatorsEnabled);
                if (this.indicatorsEnabled) {
                    indicatorToggleBtn.classList.add('active');
                    if (indicatorStatus) {
                        indicatorStatus.textContent = 'Вкл';
                        indicatorStatus.className = 'toggle-status status-on';
                    }
                } else {
                    indicatorToggleBtn.classList.remove('active');
                    if (indicatorStatus) {
                        indicatorStatus.textContent = 'Выкл';
                        indicatorStatus.className = 'toggle-status status-off';
                    }
                }
            });
        }
    }

    toggleIndicators(enabled) {
        const indicators = document.querySelectorAll('.stat-indicator');
        indicators.forEach(ind => {
            ind.style.display = enabled ? 'block' : 'none';
        });
        if (enabled) {
            document.querySelectorAll('.stat-cell.match, .stat-cell.mismatch').forEach(el => {
                el.style.backgroundColor = '';
            });
        } else {
            document.querySelectorAll('.stat-cell.match, .stat-cell.mismatch').forEach(el => {
                el.style.backgroundColor = 'transparent';
            });
        }
    }

    async load() {
        try {
            const response = await fetch(`/api/stat-data/${this.organizationId}`);
            const data = await response.json();
            
            await this.waitForTableReady();
            this.createLogContainer();
            
            if (!data.success) {
                console.error('stat error', data.message);
                this.hasStatData = false;
                this.addLog(`Статистические данные не найдены для организации ${this.organizationId}`, 'error');
                this.initUI();
                this.renderLogs();
                return;
            }
            
            this.hasStatData = true;
            this.mapping = data.mapping;
            this.statData = data.data;
            this.statYears = data.years.map(Number).filter(y => y < this.planYear);
            
            if (this.statYears.length === 0) {
                this.addLog(`Нет данных статистики за годы, предшествующие ${this.planYear}`, 'warn');
            }
            
            this.buildYearColumns();
            this.initUI();
            this.check();
            this.toggleIndicators(this.indicatorsEnabled);
            this.isInitialized = true;
        } catch (e) {
            console.error('[STAT CONTROL] load error', e);
            this.hasStatData = false;
            this.addLog(`Ошибка загрузки статистических данных: ${e.message}`, 'error');
            await this.waitForTableReady();
            this.createLogContainer();
            this.initUI();
            this.renderLogs();
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
            this.addLog('Столбцы для проверки не найдены', 'warn');
            return;
        }
        
        const statCodes = Object.keys(this.mapping);
        const planCodes = [];
        const rows = this.tbody?.querySelectorAll('tr') || [];
        rows.forEach(row => {
            const code = row.dataset.code;
            if (code) planCodes.push(code);
        });
        
        statCodes.forEach(code => {
            if (!planCodes.includes(code)) {
                this.addLog(`Код ${code} есть в статистике, но отсутствует в плане`, 'warn');
            }
        });
        
        Object.entries(this.mapping).forEach(([planCode, mappingItem]) => {
            const planTr = this.findPlanRow(planCode);
            if (!planTr) {
                this.addLog(`Строка с кодом ${planCode} не найдена в таблице`, 'error');
                return;
            }
            
            this.statYears.forEach(year => {
                const column = this.yearColumns[year];
                if (column === undefined) {
                    this.addLog(`Столбец для года ${year} не найден`, 'warn');
                    return;
                }
                
                const planValue = this.getCellValue(planTr, column);
                const statValue = this.getStatValue(year, mappingItem);
                
                this.paint(planTr, column, planValue, statValue, year, planCode, mappingItem.report);
            });
        });
        
        if (this.logs.length === 0) {
            this.addLog('Все значения совпадают', 'info');
        } else {
            this.addLog(`Проверка завершена. Найдено ${this.logs.length} замечаний`, 'info');
        }
        
        this.renderLogs();
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
        
        cell.style.position = 'relative';
        cell.removeAttribute('title');
        
        const existingIndicator = cell.querySelector('.stat-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
        
        const indicator = document.createElement('div');
        indicator.className = 'stat-indicator';
        cell.appendChild(indicator);
        
        if (Number(plan) === Number(stat)) {
            cell.classList.add('stat-cell', 'match');
            cell.classList.remove('mismatch');
            indicator.title = 'Совпадает';
        } else {
            cell.classList.add('stat-cell', 'mismatch');
            cell.classList.remove('match');
            indicator.title = `Не совпадает: план ${plan} != статистика ${stat}`;
            
            this.addLog(`Не совпадает: код ${code}, год ${year}, план ${plan}, статистика ${stat}`, 'error');
            
            const showTooltip = (e) => {
                this.showTooltip(stat, year, code, report, e, plan);
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
        
        if (!this.indicatorsEnabled) {
            indicator.style.display = 'none';
        }
    }

    createTooltip() {
        if (this.tooltipElement) {
            this.tooltipElement.remove();
            this.tooltipElement = null;
        }
        
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.className = 'stat-tooltip';
        this.tooltipElement.innerHTML = `
            <div class="tooltip-title">Статистика</div>
            <div class="tooltip-value" id="stat-value-display"></div>
            <div class="tooltip-divider"></div>
            <div class="tooltip-details">
                <span id="stat-year-display"></span>
                <span>·</span>
                <span id="stat-code-display"></span>
                <span>·</span>
                <span id="stat-report-display"></span>
            </div>
            <div class="tooltip-plan">
                План: <strong id="stat-plan-display"></strong>
            </div>
        `;
        
        document.body.appendChild(this.tooltipElement);
    }

    showTooltip(statValue, year, code, report, event, planValue) {
        this.createTooltip();
        
        const valueDisplay = this.tooltipElement.querySelector('#stat-value-display');
        const yearDisplay = this.tooltipElement.querySelector('#stat-year-display');
        const codeDisplay = this.tooltipElement.querySelector('#stat-code-display');
        const reportDisplay = this.tooltipElement.querySelector('#stat-report-display');
        const planDisplay = this.tooltipElement.querySelector('#stat-plan-display');
        
        valueDisplay.textContent = statValue;
        yearDisplay.textContent = year;
        codeDisplay.textContent = `Код ${code}`;
        reportDisplay.textContent = report;
        planDisplay.textContent = planValue;
        
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
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const tbody = document.querySelector('#indicators-tbody');
        const rows = tbody?.querySelectorAll('tr');
        const table = document.getElementById('indicatorsTable');
        const isRegionManagement = table?.dataset?.isRegionManagement === 'true';
        const isAdmin = table?.dataset?.isAdmin === 'true';
        
        if (rows && rows.length > 0 && rows[0].dataset.code) {
            new PlanStatControl('indicatorsTable', isRegionManagement, isAdmin);
        } else {
            setTimeout(() => {
                new PlanStatControl('indicatorsTable', isRegionManagement, isAdmin);
            }, 1000);
        }
    }, 500);
});