// NumericInputHandler определён и инициализируется в base.js (который
// подключается раньше) — здесь раньше была устаревшая копия этого же
// объекта, которая просто молча перезаписывала var NumericInputHandler
// из base.js (ничего своего не вызывала — ни одного NumericInputHandler.init
// во всём plan.js), из-за чего на КАЖДОЙ странице сайта реально работала
// эта, более старая и багованная версия: она прогоняла значение через
// parseFloat/toFixed на каждое нажатие клавиши, из-за чего ввести, например,
// "-0,5" посимвольно было невозможно (после "-0" toFixed схлопывал в "0,0").

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
        this.initAjaxForms();
        this.initTeoCellClicks();
    }

    initTeoCellClicks() {
        const table = document.getElementById('eventTable');
        if (!table) return;

        // Каждая <tr> таблицы уже имеет свой click-листенер
        // (TableContextMenu.onRowLeftClick — выбор строки + открытие модалки
        // редактирования), который сам вызывает event.stopPropagation() и
        // делает это раньше, чем событие дошло бы всплытием до делегированного
        // листенера на #eventTable. Поэтому здесь используется фаза
        // перехвата (capture) — она выполняется до того, как событие вообще
        // достигнет строки, и stopPropagation() на этом этапе гарантированно
        // не даёт клику по скрепке/загрузке открыть модалку редактирования.
        table.addEventListener('click', (e) => {
            const btn = e.target.closest('.teo-cell-icon');
            const uploadLabel = e.target.closest('.teo-cell-upload');
            if (!btn && !uploadLabel) return;

            e.stopPropagation();

            if (btn) {
                e.preventDefault();
                window.TeoViewer?.open(btn.dataset.teoId, btn.dataset.teoName);
            }
            // для uploadLabel preventDefault не вызывается — нужно, чтобы
            // клик по <label> штатно открыл системный диалог выбора файла
        }, true);

        table.addEventListener('change', async (e) => {
            const input = e.target.closest('.teo-cell-upload-input');
            if (!input) return;

            const label = input.closest('.teo-cell-upload');
            const eventId = label?.dataset.teoUploadId;
            const file = input.files[0];
            if (!eventId || !file) return;

            await this.uploadTeoFile(eventId, file);
        });
    }

    async uploadTeoFile(eventId, file) {
        await this.withScrollPreserved(async () => {
            try {
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const formData = new FormData();
                formData.append('teo_file', file);
                if (csrfMeta) formData.append('csrf_token', csrfMeta.content);

                const response = await fetch(`/plans/plan/event/${eventId}/teo`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfMeta ? csrfMeta.content : ''
                    },
                    body: formData
                });
                const data = await response.json();

                this.notify(data.message, data.success);

                if (data.success) {
                    await this.refreshTable();
                }
            } catch (e) {
                console.error('[PlanEvents] teo upload error', e);
                this.notify('Не удалось прикрепить файл ТЭО', false);
            }
        });
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
                ? 'Нет мероприятий по экономии ТЭР (первоначальная редакция)' 
                : 'Нет мероприятий по увеличению использования местных ТЭР (первоначальная редакция)';
            tbody.innerHTML = `<tr class="no-results-row"><td colspan="20">${emptyMessage}</tr>`;
            return;
        }
        
        this.originalEvents.forEach((row, index) => {
            const tr = this.createEventRow(row, index);
            tbody.appendChild(tr);
        });
        
        this.addTotalRow(tbody, this.originalEvents, false);
    }

    renderEventsWithChanges() {
        const tbody = document.getElementById('local-content');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (!this.eventsWithChanges || this.eventsWithChanges.length === 0) {
            const emptyMessage = this.eventType === 'saving'
                ? 'Отсутствуют мероприятия по экономии ТЭР (включенные в план при внесении в него изменений)'
                : 'Отсутствуют мероприятия по увеличению использования местных ТЭР (включенные в перечень при внесении в него изменений)';
            tbody.innerHTML = `<tr class="no-results-row"><td colspan="20">${emptyMessage}</tr>`;
            return;
        }
        
        this.eventsWithChanges.forEach((row, index) => {
            const tr = this.createEventRow(row, index);
            tbody.appendChild(tr);
        });
        
        this.addTotalRow(tbody, this.eventsWithChanges, true);
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
            <td style="text-align: center;" class="teo-cell no-print-col">${this.renderTeoCell(row)}</td>
        `;

        return tr;
    }

    teoPaperclipSvg() {
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">`
            + `<path d="M21.44 11.05l-9.19 9.19a5.5 5.5 0 0 1-7.78-7.78l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.19 9.19a1.5 1.5 0 0 1-2.12-2.12l8.49-8.49"/>`
            + `</svg>`;
    }

    renderTeoCell(row) {
        if (row.has_teo) {
            const name = this.escapeHtml(row.teo_original_name || 'ТЭО');
            return `<button type="button" class="teo-cell-icon" data-teo-id="${row.id}" data-teo-name="${name}" title="${name}">`
                + this.teoPaperclipSvg()
                + `</button>`;
        }

        // Файл не прикреплён — ячейка внешне пустая, но кликабельная зона
        // (скрытый input[type=file]) позволяет прикрепить ТЭО прямо из
        // таблицы, без открытия модалки редактирования.
        return `<label class="teo-cell-upload" data-teo-upload-id="${row.id}" title="Прикрепить ТЭО">`
            + `<input type="file" class="teo-cell-upload-input" accept=".doc,.docx,.pdf">`
            + this.teoPaperclipSvg()
            + `</label>`;
    }

    getSectionTitle(isCorrected) {
        const partNumber = this.getPartNumber();
        if (this.eventType === 'saving') {
            if (isCorrected) {
                return `Итого по разделу 2.2`;
            } else {
                return `Итого по разделу 2.1`;
            }
        } else {
            if (isCorrected) {
                return `Итого по разделу 3.2`;
            } else {
                return `Итого по разделу 3.1`;
            }
        }
    }

    addTotalRow(tbody, events, isCorrected = false) {
        if (events.length === 0) return;

        const sectionTitle = this.getSectionTitle(isCorrected);
        const totalRow = document.createElement('tr');

        totalRow.className = 'total-row';
        totalRow.style.borderBottom = '1px solid var(--border-color) !important;';
        totalRow.innerHTML = `
            <td style="text-align: left; padding-left: 60px;" colspan="3">${sectionTitle}</td>
            <td style="text-align: end;">-</td>
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
            <td></td>
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

        const borderStyle = 'border-top: 1px solid #f1f5f9;';
        const endAlign = 'text-align: end;';

        const cells = [
            { text: `Всего по части ${partNumber}, в том числе:`, colSpan: 3 },
            { text: '-' },
            { text: '-' },
            { text: this.sumEvents(allEvents, 'EffTut').toFixed(2).replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'EffRub') || 0).toString().replace('.', ',') },
            { text: '-' },
            { text: this.sumEvents(allEvents, 'EffCurrYear').toFixed(2).replace('.', ',') },
            { text: '-' },
            { text: (this.sumEvents(allEvents, 'ObchVolumeFin') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'VolumeFinCurrentYear') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'BudgetState') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'BudgetRep') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'BudgetLoc') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'BudgetOther') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'MoneyOwn') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'MoneyLoan') || 0).toString().replace('.', ',') },
            { text: (this.sumEvents(allEvents, 'MoneyOther') || 0).toString().replace('.', ',') },
            { text: '' }
        ];

        totalRow.innerHTML = cells.map((cell, index) => {
            const styles = `${borderStyle} ${endAlign}`;
            const colspan = cell.colSpan ? ` colspan="${cell.colSpan}"` : '';
            const isFirst = index === 0;
            const align = isFirst ? '' : endAlign;
            return `<td${colspan} style="${borderStyle} ${align}">${cell.text}</td>`;
        }).join('');

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
                <td colspan="11"></td>
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
                removeCallback: (rowId) => this.deleteEventAjax(rowId),
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

    // Добавление/редактирование/удаление мероприятия раньше были обычными
    // POST-формами с редиректом на ту же страницу — из-за этого после
    // сохранения строки в конце длинной таблицы страница перезагружалась
    // целиком и прокрутка сбрасывалась в начало (см. тот же фикс для
    // показателей в indicator-calc.js). Теперь эти действия шлются через
    // fetch, а обновляется только сама таблица (см. refreshTable).
    initAjaxForms() {
        const addForm = document.getElementById('addEventForm');
        if (addForm) {
            addForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitEventForm(addForm, 'AddEventModal');
            });
        }

        const editForm = document.getElementById('editEventeForm');
        if (editForm) {
            editForm.addEventListener('submit', (e) => {
                e.preventDefault();

                // При редактировании периодной (квартальной) строки значение
                // берётся из отдельного поля-инпута и переносится в скрытое
                // поле формы перед отправкой.
                const editType = document.getElementById('edit-event-type')?.value;
                if (editType === 'period') {
                    const effCurrYearInput = document.getElementById('period-EffCurrYear-edit');
                    const hiddenEffCurrYear = document.getElementById('change-EffCurrYear-edit-model');
                    if (effCurrYearInput && hiddenEffCurrYear) {
                        hiddenEffCurrYear.value = effCurrYearInput.value.replace(',', '.');
                    }
                }

                this.submitEventForm(editForm, 'EditEventModal');
            });
        }
    }

    async submitEventForm(form, modalId) {
        await this.withScrollPreserved(async () => {
            const submitBtn = form.querySelector('button[type="submit"]');
            const wasDisabled = submitBtn ? submitBtn.disabled : null;
            const submitBtnText = submitBtn?.querySelector('.btn-text');
            const originalBtnText = submitBtnText?.textContent;
            if (submitBtn) submitBtn.disabled = true;

            try {
                const data = await this.submitFormWithProgress(form, (percent) => {
                    if (submitBtnText) {
                        submitBtnText.textContent = percent < 100
                            ? `Загрузка... ${percent}%`
                            : 'Сохранение...';
                    }
                });

                this.notify(data.message, data.success);

                if (data.success) {
                    const modal = document.getElementById(modalId);
                    if (modal) modal.classList.remove('active');
                    // Раньше страница целиком перезагружалась после отправки,
                    // из-за чего модалка сама "сбрасывалась" на первый шаг.
                    // Теперь модалка не пересоздаётся — сбрасываем шаги
                    // мастера вручную, иначе при повторном открытии он
                    // окажется там же, где был при закрытии (а у EditEventModal
                    // счётчик шага внутри EventModal вообще не совпадёт с тем,
                    // что показывает showEventStep(), и "Далее" перестанет
                    // работать).
                    if (modalId === 'AddEventModal') {
                        form.reset();
                        window.addEventModalWizard?.resetForm();
                    } else if (modalId === 'EditEventModal') {
                        window.editEventModalWizard?.resetForm();
                    }

                    if (!document.getElementById('eventTable')) {
                        // Самое первое мероприятие плана этого типа — на
                        // странице ещё нет самой таблицы (она рендерится
                        // только когда есть хотя бы одно мероприятие), её
                        // некуда AJAX-обновлять. Перезагружаем страницу —
                        // сервер отрисует уже появившуюся таблицу.
                        window.location.reload();
                        return;
                    }
                    await this.refreshTable();
                }
            } catch (e) {
                console.error('[PlanEvents] submit error', e);
                this.notify('Не удалось сохранить мероприятие', false);
            } finally {
                if (submitBtn) submitBtn.disabled = wasDisabled;
                if (submitBtnText && originalBtnText !== undefined) submitBtnText.textContent = originalBtnText;
            }
        });
    }

    // fetch() не даёт отследить прогресс именно ОТПРАВКИ (upload), только
    // получения ответа — на медленном канале с файлом 20 МБ это выглядело
    // бы как "зависшая" кнопка без обратной связи. XMLHttpRequest умеет
    // upload.onprogress, поэтому POST с файлом идёт через него.
    submitFormWithProgress(form, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', form.action, true);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    onProgress(Math.round((e.loaded / e.total) * 100));
                }
            });

            xhr.onload = () => {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch (err) {
                    reject(err);
                }
            };
            xhr.onerror = () => reject(new Error('network error'));

            xhr.send(new FormData(form));
        });
    }

    async deleteEventAjax(id) {
        await this.withScrollPreserved(async () => {
            try {
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const formData = new FormData();
                if (csrfMeta) formData.append('csrf_token', csrfMeta.content);

                const response = await fetch(`/plans/plan/delete-eventes/${id}`, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData
                });
                const data = await response.json();

                this.notify(data.message, data.success);

                if (data.success) {
                    await this.refreshTable();
                }
            } catch (e) {
                console.error('[PlanEvents] delete error', e);
                this.notify('Не удалось удалить мероприятие', false);
            }
        });
    }

    async withScrollPreserved(fn) {
        const scrollY = window.scrollY;
        let active = true;

        const onScroll = () => {
            if (active && window.scrollY !== scrollY) {
                window.scrollTo(0, scrollY);
            }
        };
        window.addEventListener('scroll', onScroll);

        try {
            return await fn();
        } finally {
            if (window.scrollY !== scrollY) window.scrollTo(0, scrollY);
            setTimeout(() => {
                active = false;
                window.removeEventListener('scroll', onScroll);
            }, 1500);
        }
    }

    notify(message, success) {
        if (typeof messageFlash !== 'undefined' && message) {
            messageFlash.addMessage(message, success ? 'success' : 'error');
        } else if (message && !success) {
            alert(message);
        }
    }

    // Общее место обновления таблицы после add/edit/delete: перерисовывает
    // только тело таблицы (loadEvents), затем заново навешивает контекстное
    // меню — оно завязано на конкретные DOM-узлы строк, которые
    // renderOriginalEvents/renderEventsWithChanges каждый раз создают заново.
    async refreshTable() {
        await this.loadEvents();
        this.initTableContextMenu();
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
        if (value === null || value === undefined || value === '') {
            return '0,00';
        }
        
        let strValue = String(value).trim().replace(/\s/g, '');
        
        if (strValue === '') {
            return '0,00';
        }
        
        strValue = strValue.replace(',', '.');
        
        const num = parseFloat(strValue);
        
        if (isNaN(num) || !isFinite(num)) {
            return '0,00';
        }
        
        return num.toFixed(2).replace('.', ',');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        // innerHTML экранирует <, > и & в тексте, но не кавычки — а
        // результат этой функции местами подставляется и внутрь HTML-
        // атрибутов (например data-teo-name="${name}"), где значение может
        // быть неконтролируемым вводом пользователя (оригинальное имя
        // загруженного файла) — без этого кавычка в имени файла сломала бы
        // атрибут и позволила бы внедрить произвольный HTML/JS.
        return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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

        // Кнопки постоянной панели инструментов (Добавить/Редактировать/
        // Удалить над таблицей) — не всплывающее окно, их по-прежнему
        // просто гасим, а не убираем из разметки.
        [this.tableEditButton, this.tableDeleteButton].forEach(button => {
            if (!button) return;
            const disabled = !isActive || (button === this.tableEditButton ? isEditDisabled : isDeleteDisabled);
            button.classList.toggle('btn-disabled', disabled);
        });

        // Пункты всплывающего контекстного меню — если действие для строки
        // недоступно, пункт вообще не показываем (а не показываем серым).
        if (this.contextEditButton) {
            this.contextEditButton.style.display = (isActive && !isEditDisabled) ? '' : 'none';
        }
        if (this.contextDeleteButton) {
            this.contextDeleteButton.style.display = (isActive && !isDeleteDisabled) ? '' : 'none';
        }
    }

    onRowLeftClick(event, row) {
        event.stopPropagation();
        
        const hasDataId = row.getAttribute('data-id') && row.getAttribute('data-id') !== 'null';
        
        if (!hasDataId) {
            return;
        }
        
        if (row.classList.contains('active-row')) {
            row.classList.remove('active-row');
            this.selectedRow = null;
            this.updateButtonsState();
            this.hideContextMenu();
            return;
        }
        
        this.table.querySelectorAll('.active-row').forEach(r => {
            r.classList.remove('active-row');
        });
        
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

        // Ни редактировать, ни удалить эту строку нельзя — всплывающему
        // меню в этом случае показывать нечего.
        if (this.isEditDisabled(row) && this.isDeleteDisabled(row)) {
            this.hideContextMenu();
            return;
        }

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

        const yesBtn = modal.querySelector('#confirmYes');
        const noBtn = modal.querySelector('#confirmNo');
        const textEl = modal.querySelector('#modal-text');
        const textSecondEl = modal.querySelector('#modal-text-second');
        const yesTextEl = yesBtn.querySelector('#confirm-yes-text');

        if (textEl) textEl.textContent = 'Вы действительно хотите удалить данные?';
        if (textSecondEl) textSecondEl.textContent = 'Это действие нельзя будет отменить.';
        if (yesTextEl) yesTextEl.textContent = 'Да, удалить';

        modal.classList.add('active');
        modal._currentForm = null;

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

// Логика отправки плана на рассмотрение (SendModalPreview / CertificateUploadHandler)
// перенесена на отдельную страницу — см. website/static/js/plan_send.js и
// website/templates/plan_send.html. Раньше это было модальное окно поверх
// plan_review.html.

function initDeletePlanConfirmModal() {
    if (document.querySelector('[data-modal-trigger="deletePlanconfirm"]')) {
        initConfirmModal({
            triggerButton: '[data-modal-trigger="deletePlanconfirm"]',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы уверены, что хотите безвозвратно удалить этот план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.',
            yesText: 'Да, удалить'
        });
    }
}

class PlansLoader {
    constructor(options = {}) {
        this.currentStatus = options.initialStatus || 'all';
        this.currentYear = options.initialYear || 'all';
        this.currentRegion = options.initialRegion || 'all';
        this.currentSearchName = '';
        this.currentSearchYnp = '';
        this.currentSearchApproverOrg = '';
        this.currentPage = 1;
        this.totalPages = 1;
        this.isLoading = false;
        this.searchTimeout = null;
        this.perPage = options.perPage || 50;
        this.isAuditor = options.isAuditor || false;

        this.containerId = options.containerId || 'plans-container';
        this.searchNameId = options.searchNameId || 'search-name';
        this.searchYnp = options.searchYnp || 'search-ynp';
        this.searchApproverOrgId = options.searchApproverOrgId || 'search-approver-org';
        this.paginationAreaId = 'pagination-area';
        this.prevPageBtnId = 'prev-page-btn';
        this.nextPageBtnId = 'next-page-btn';
        this.currentPageSpanId = 'current-page';
        this.totalPagesSpanId = 'total-pages';
        
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
        if (this.currentSearchYnp) {
            params.set('search_ynp', this.currentSearchYnp);
        }
        if (this.currentSearchApproverOrg) {
            params.set('search_approver_org', this.currentSearchApproverOrg);
        }
        if (this.currentPage > 1) {
            params.set('page', this.currentPage);
        }

        const newUrl = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
        window.history.pushState({}, '', newUrl);
    }

    async loadPlans() {
        if (this.isLoading) return;

        this.isLoading = true;
        const container = document.getElementById(this.containerId);

        if (container) {
            container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div></div>';
        }

        this.updateUrl();

        try {
            let url = `/api/plans?page=${this.currentPage}&per_page=${this.perPage}&status=${this.currentStatus}&year=${this.currentYear}&region=${this.currentRegion}&show_checkboxes=${this.showCheckboxes || false}`;
            if (this.currentSearchName) {
                url += `&search_name=${encodeURIComponent(this.currentSearchName)}`;
            }
            if (this.currentSearchYnp) {
                url += `&search_ynp=${encodeURIComponent(this.currentSearchYnp)}`;
            }
            if (this.currentSearchApproverOrg) {
                url += `&search_approver_org=${encodeURIComponent(this.currentSearchApproverOrg)}`;
            }

            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                if (container) {
                    container.innerHTML = `<div class="plans-area">${data.html}</div>`;
                }
                
                this.totalPages = data.pagination.total_pages || 1;
                this.currentPage = data.pagination.current_page || 1;
                
                this.updatePagination();
                this.updateCountsDisplay(data.counts);
                this.attachCheckboxListeners();
                initDeletePlanConfirmModal();

                if (typeof initStatusProgress === 'function') {
                    setTimeout(initStatusProgress, 100);
                }
            }
        } catch (error) {
            console.error('Error loading plans:', error);
            if (container) {
                container.innerHTML = '<div class="plans-error" style="text-align: center; padding: 40px; color: red;">Ошибка загрузки планов</div>';
            }
        } finally {
            this.isLoading = false;
        }
    }

    updatePagination() {
        const paginationArea = document.getElementById(this.paginationAreaId);
        const currentPageSpan = document.getElementById(this.currentPageSpanId);
        const totalPagesSpan = document.getElementById(this.totalPagesSpanId);
        const prevBtn = document.getElementById(this.prevPageBtnId);
        const nextBtn = document.getElementById(this.nextPageBtnId);
        
        if (paginationArea) {
            if (this.totalPages > 1) {
                paginationArea.style.display = 'flex';
                paginationArea.style.justifyContent = 'center';
            } else {
                paginationArea.style.display = 'none';
            }
        }
        
        if (currentPageSpan) {
            currentPageSpan.textContent = this.currentPage;
        }
        
        if (totalPagesSpan) {
            totalPagesSpan.textContent = this.totalPages;
        }
        
        if (prevBtn) {
            if (this.currentPage <= 1) {
                prevBtn.disabled = true;
                prevBtn.classList.add('disabled');
            } else {
                prevBtn.disabled = false;
                prevBtn.classList.remove('disabled');
            }
        }
        
        if (nextBtn) {
            if (this.currentPage >= this.totalPages) {
                nextBtn.disabled = true;
                nextBtn.classList.add('disabled');
            } else {
                nextBtn.disabled = false;
                nextBtn.classList.remove('disabled');
            }
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
        const statSogl = document.querySelector('.stat-number-sogl');
        const statInTransit = document.querySelector('.stat-number-transit');

        if (statAll) statAll.textContent = counts.all || '-';
        if (statDraft) statDraft.textContent = counts.draft || '-';
        if (statControl) statControl.textContent = counts.control || '-';
        if (statSent) statSent.textContent = counts.sent || '-';
        if (statError) statError.textContent = counts.error || '-';
        if (statApproved) statApproved.textContent = counts.approved || '-';
        if (statSogl) statSogl.textContent = counts.sogl || '-';
        if (statInTransit) statInTransit.textContent = counts.in_transit || '-';
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
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.loadPlans();
    }
    
    goToPrevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    }
    
    goToNextPage() {
        if (this.currentPage < this.totalPages) {
            this.goToPage(this.currentPage + 1);
        }
    }
    
    handleSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.currentSearchName = document.getElementById(this.searchNameId)?.value || '';
            this.currentSearchYnp = document.getElementById(this.searchYnp)?.value || '';
            this.currentSearchApproverOrg = document.getElementById(this.searchApproverOrgId)?.value || '';
            this.currentPage = 1;
            this.updateUrl();
            this.loadPlans();
        }, 500);
    }

    initFilters() {
        const searchNameInput = document.getElementById(this.searchNameId);
        const searchOkpoInput = document.getElementById(this.searchYnp);
        const searchApproverOrgInput = document.getElementById(this.searchApproverOrgId);

        if (searchNameInput) {
            searchNameInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchOkpoInput) {
            searchOkpoInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchApproverOrgInput) {
            searchApproverOrgInput.addEventListener('input', () => this.handleSearch());
        }

        const statusDropdown = document.querySelector('[data-filter-type="status"]');
        const yearDropdown = document.querySelector('[data-filter-type="year"]');
        const regionDropdown = document.querySelector('[data-filter-type="region"]');
        
        if (statusDropdown) {
            const toggleBtn = statusDropdown.querySelector('.dropdown-toggle');
            const items = statusDropdown.querySelectorAll('.dropdown-item');

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
                    statusDropdown.classList.remove('active');
                    this.applyStatusFilter(item.dataset.value);
                });
            });
        }

        const statTiles = document.querySelectorAll('.stat-and-dot[data-value]');
        statTiles.forEach(tile => {
            tile.addEventListener('click', () => {
                this.applyStatusFilter(tile.dataset.value);
            });
        });
        
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
                    this.currentPage = 1;
                    if (selectedSpan) {
                        if (value === 'all') {
                            selectedSpan.textContent = 'Год';
                        } else {
                            selectedSpan.textContent = value;
                        }
                    }
                    yearDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans();
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
                    this.currentPage = 1;
                    if (selectedSpan) selectedSpan.textContent = item.textContent;
                    regionDropdown.classList.remove('active');
                    this.updateUrl();
                    this.loadPlans();
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
        
        const prevBtn = document.getElementById(this.prevPageBtnId);
        const nextBtn = document.getElementById(this.nextPageBtnId);
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.goToPrevPage());
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goToNextPage());
        }
        
        window.addEventListener('popstate', (event) => {
            const params = new URLSearchParams(window.location.search);
            const newStatus = params.get('status') || 'all';
            const newYear = params.get('year') || 'all';
            const newRegion = params.get('region') || 'all';
            const newSearchName = params.get('search_name') || '';
            const newSearchOkpo = params.get('search_ynp') || '';
            const newSearchApproverOrg = params.get('search_approver_org') || '';
            const newPage = parseInt(params.get('page')) || 1;

            if (newStatus !== this.currentStatus || newYear !== this.currentYear || newRegion !== this.currentRegion ||
                newSearchName !== this.currentSearchName || newSearchOkpo !== this.currentSearchYnp ||
                newSearchApproverOrg !== this.currentSearchApproverOrg ||
                newPage !== this.currentPage) {

                this.currentStatus = newStatus;
                this.currentYear = newYear;
                this.currentRegion = newRegion;
                this.currentSearchName = newSearchName;
                this.currentSearchYnp = newSearchOkpo;
                this.currentSearchApproverOrg = newSearchApproverOrg;
                this.currentPage = newPage;

                if (searchNameInput) searchNameInput.value = newSearchName;
                if (searchOkpoInput) searchOkpoInput.value = newSearchOkpo;
                if (searchApproverOrgInput) searchApproverOrgInput.value = newSearchApproverOrg;

                this.updateFilterDisplay();
                this.loadPlans();
            }
        });
    }
    
    updateFilterDisplay() {
        let statusMap;
        
        if (this.isAuditor) {
            statusMap = {
                'all': 'Статус',
                'sent': 'На рассмотрении',
                'in_transit': 'Ожидание очереди',
                'sogl': 'Согласованные',
                'error': 'Есть ошибки',
                'approved': 'Утвержденные'
            };
        } else {
            statusMap = {
                'all': 'Статус',
                'draft': 'В редакции',
                'control': 'Контроль пройден',
                'sent': 'На согласовании',
                'error': 'Есть ошибки',
                'approved': 'Согласованные'
            };
        }
        
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

        this.updateActiveStatTile();
    }

    updateActiveStatTile() {
        document.querySelectorAll('.stat-and-dot[data-value]').forEach(tile => {
            tile.classList.toggle('active', tile.dataset.value === this.currentStatus);
        });
    }

    applyStatusFilter(value) {
        this.currentStatus = value;
        this.currentPage = 1;
        this.updateFilterDisplay();
        this.updateUrl();
        this.loadPlans();
    }

    init() {
        this.selectedPlans = new Set();
        this.selectedFormat = null;
        this.initFilters();
        this.updateFilterDisplay();
        this.loadPlans();
    }
}

class ExportPlansLoader {
    constructor(options = {}) {
        this.preselectPlanId = options.preselectPlanId ? String(options.preselectPlanId) : null;
        this.preselectFormat = options.preselectFormat || null;

        this.currentStatus = options.initialStatus || 'all';
        this.currentYear = options.preselectYear ? String(options.preselectYear) : (options.initialYear || 'all');
        this.currentRegion = options.initialRegion || 'all';
        this.currentSearchName = '';
        this.currentSearchYnp = '';
        this.currentSearchApproverOrg = '';
        this.currentPage = 1;
        this.totalPages = 1;
        this.isLoading = false;
        this.searchTimeout = null;
        this.perPage = options.perPage || 50;
        this.selectedPlans = new Set();
        this.selectedFormat = null;
        this.exportInProgress = false;
        this.currentTaskId = null;
        this.progressInterval = null;
        this.isInitialLoad = true;

        if (this.preselectPlanId) {
            this.selectedPlans.add(this.preselectPlanId);
        }
        
        this.containerId = options.containerId || 'plans-container';
        this.loadMoreBtnId = options.loadMoreBtnId || 'load-more-btn';
        this.searchNameId = options.searchNameId || 'search-name';
        this.searchYnp = options.searchYnp || 'search-ynp';
        this.searchApproverOrgId = options.searchApproverOrgId || 'search-approver-org';
        this.selectAllId = options.selectAllId || 'selectAllBtn';
        this.clearAllId = 'clearAllBtn';
        this.exportFormId = options.exportFormId || 'exportForm';
        this.paginationAreaId = 'pagination-area';
        this.prevPageBtnId = 'prev-page-btn';
        this.nextPageBtnId = 'next-page-btn';
        this.currentPageSpanId = 'current-page';
        this.totalPagesSpanId = 'total-pages';
        
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
        if (this.currentSearchYnp) {
            params.set('search_ynp', this.currentSearchYnp);
        }
        if (this.currentSearchApproverOrg) {
            params.set('search_approver_org', this.currentSearchApproverOrg);
        }
        if (this.currentPage > 1) {
            params.set('page', this.currentPage);
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
        const container = document.getElementById(this.containerId);
        
        if (reset && container) {
            container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div></div>';
        }
        
        this.updateUrl();
        
        try {
            let url = `/api/plans?page=${this.currentPage}&per_page=${this.perPage}&status=${this.currentStatus}&year=${this.currentYear}&region=${this.currentRegion}&show_checkboxes=${this.showCheckboxes || true}`;
            if (this.currentSearchName) {
                url += `&search_name=${encodeURIComponent(this.currentSearchName)}`;
            }
            if (this.currentSearchYnp) {
                url += `&search_ynp=${encodeURIComponent(this.currentSearchYnp)}`;
            }
            if (this.currentSearchApproverOrg) {
                url += `&search_approver_org=${encodeURIComponent(this.currentSearchApproverOrg)}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                if (container) {
                    container.innerHTML = `<div class="plans-area">${data.html}</div>`;
                }
                
                this.totalPages = data.pagination.total_pages || 1;
                this.currentPage = data.pagination.current_page || 1;
                
                this.updatePagination();
                this.attachCheckboxListeners();
                this.applyPreselectPlanCheckbox();
                this.updateButtons();
                this.updateExportButton();

                if (typeof initStatusProgress === 'function') {
                    setTimeout(initStatusProgress, 100);
                }
            }
        } catch (error) {
            console.error('Error loading plans:', error);
            if (reset && container) {
                container.innerHTML = '<div class="plans-error" style="text-align: center; padding: 40px; color: red;">Ошибка загрузки планов</div>';
            }
        } finally {
            this.isLoading = false;
        }
    }
    
    updatePagination() {
        const paginationArea = document.getElementById(this.paginationAreaId);
        const currentPageSpan = document.getElementById(this.currentPageSpanId);
        const totalPagesSpan = document.getElementById(this.totalPagesSpanId);
        const prevBtn = document.getElementById(this.prevPageBtnId);
        const nextBtn = document.getElementById(this.nextPageBtnId);
        
        if (paginationArea) {
            if (this.totalPages > 1) {
                paginationArea.style.display = 'flex';
                paginationArea.style.justifyContent = 'center';
            } else {
                paginationArea.style.display = 'none';
            }
        }
        
        if (currentPageSpan) {
            currentPageSpan.textContent = this.currentPage;
        }
        
        if (totalPagesSpan) {
            totalPagesSpan.textContent = this.totalPages;
        }
        
        if (prevBtn) {
            if (this.currentPage <= 1) {
                prevBtn.disabled = true;
                prevBtn.classList.add('disabled');
            } else {
                prevBtn.disabled = false;
                prevBtn.classList.remove('disabled');
            }
        }
        
        if (nextBtn) {
            if (this.currentPage >= this.totalPages) {
                nextBtn.disabled = true;
                nextBtn.classList.add('disabled');
            } else {
                nextBtn.disabled = false;
                nextBtn.classList.remove('disabled');
            }
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

    applyPreselectPlanCheckbox() {
        if (!this.preselectPlanId) return;
        const checkbox = document.querySelector(`.plans-area input[type="checkbox"][value="${this.preselectPlanId}"]`);
        if (checkbox) {
            checkbox.checked = true;
        }
        // Плана может не быть на текущей странице/с текущими фильтрами —
        // экспорт всё равно должен сработать, т.к. id уже в selectedPlans
        // (добавлен в конструкторе), чекбокс здесь только для визуальной синхронизации.
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
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.loadPlans(true);
    }
    
    goToPrevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    }
    
    goToNextPage() {
        if (this.currentPage < this.totalPages) {
            this.goToPage(this.currentPage + 1);
        }
    }
    
    handleSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.currentSearchName = document.getElementById(this.searchNameId)?.value || '';
            this.currentSearchYnp = document.getElementById(this.searchYnp)?.value || '';
            this.currentSearchApproverOrg = document.getElementById(this.searchApproverOrgId)?.value || '';
            this.currentPage = 1;
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
        const searchOkpoInput = document.getElementById(this.searchYnp);
        const searchApproverOrgInput = document.getElementById(this.searchApproverOrgId);

        if (searchNameInput) {
            searchNameInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchOkpoInput) {
            searchOkpoInput.addEventListener('input', () => this.handleSearch());
        }
        if (searchApproverOrgInput) {
            searchApproverOrgInput.addEventListener('input', () => this.handleSearch());
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
                    this.currentPage = 1;
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
                    this.currentPage = 1;
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
                    this.currentPage = 1;
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
        
        const prevBtn = document.getElementById(this.prevPageBtnId);
        const nextBtn = document.getElementById(this.nextPageBtnId);
        
        if (prevBtn) {
            prevBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.goToPrevPage();
            }.bind(this));
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.goToNextPage();
            }.bind(this));
        }
        
        window.addEventListener('popstate', (event) => {
            const params = new URLSearchParams(window.location.search);
            const newStatus = params.get('status') || 'all';
            const newYear = params.get('year') || 'all';
            const newRegion = params.get('region') || 'all';
            const newSearchName = params.get('search_name') || '';
            const newSearchOkpo = params.get('search_ynp') || '';
            const newSearchApproverOrg = params.get('search_approver_org') || '';
            const newPage = parseInt(params.get('page')) || 1;

            if (newStatus !== this.currentStatus || newYear !== this.currentYear || newRegion !== this.currentRegion ||
                newSearchName !== this.currentSearchName || newSearchOkpo !== this.currentSearchYnp ||
                newSearchApproverOrg !== this.currentSearchApproverOrg ||
                newPage !== this.currentPage) {

                this.currentStatus = newStatus;
                this.currentYear = newYear;
                this.currentRegion = newRegion;
                this.currentSearchName = newSearchName;
                this.currentSearchYnp = newSearchOkpo;
                this.currentSearchApproverOrg = newSearchApproverOrg;
                this.currentPage = newPage;

                if (searchNameInput) searchNameInput.value = newSearchName;
                if (searchOkpoInput) searchOkpoInput.value = newSearchOkpo;
                if (searchApproverOrgInput) searchApproverOrgInput.value = newSearchApproverOrg;

                this.updateFilterDisplay();
                this.loadPlans(true);
            }
        });
        
        const loadMoreBtn = document.getElementById(this.loadMoreBtnId);
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', function(e) {
                e.preventDefault();
                this.loadPlans(false);
            }.bind(this));
        }
    }
    
    updateFilterDisplay() {
        const statusMap = {
            'all': 'Статус',
            'draft': 'В редакции',
            'control': 'Контроль пройден',
            'sent': 'На согласовании',
            'error': 'Есть ошибки',
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
        this.applyPreselectFormat();
        this.initFormSubmit();
        this.isInitialLoad = true;
        this.loadPlans(true);
    }

    applyPreselectFormat() {
        if (!this.preselectFormat) return;
        const item = document.querySelector(`.export-choose[data-format="${this.preselectFormat}"]`);
        if (item && !item.classList.contains('disabled')) {
            item.click();
        }
    }
}

function initEditableHeaders() {
    const LABEL_OPTIONS = ['отчет', 'оценка', 'прогноз'];
    const editIcons = document.querySelectorAll('.edit-header-icon');
    const planYearAttr = document.querySelector('#indicatorsTable')?.dataset?.planYear;
    const planYear = planYearAttr ? parseInt(planYearAttr, 10) : null;

    // Карточки "Добавление/Редактирование показателя" рисуют свои подписи
    // года (value-label) один раз при загрузке страницы из plan.column_configs
    // — без этой синхронизации они оставались бы со старым наименованием
    // (отчет/оценка/прогноз) до перезагрузки страницы, даже если шапку
    // таблицы только что переименовали через этот же дропдаун.
    function syncModalValueLabels(yearNum, newLabel) {
        if (planYear === null) return;
        let slot = null;
        if (yearNum === planYear - 2) slot = 'before';
        else if (yearNum === planYear - 1) slot = 'prev';
        else if (yearNum === planYear) slot = 'current';
        if (!slot) return;

        const labelText = `${newLabel} ${yearNum} г.`;
        const addLabel = document.getElementById(`add-value-label-${slot}`);
        const editLabel = document.getElementById(`edit-value-label-${slot}`);
        if (addLabel) addLabel.textContent = labelText;
        if (editLabel) editLabel.textContent = labelText;
    }

    // .table-container скроллится (overflow: auto), поэтому меню дропдауна,
    // позиционированное как потомок ячейки заголовка, обрезалось бы рамкой
    // контейнера. Вместо этого рендерим меню отдельным элементом в
    // document.body с position:fixed и координатами, посчитанными от
    // кнопки-триггера — тогда оно всегда поверх таблицы и никогда не режется.
    let closeActiveDropdown = null;

    editIcons.forEach(icon => {
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            if (closeActiveDropdown) closeActiveDropdown();

            const th = icon.closest('.colspan-header');
            const link = th.querySelector('a');
            const currentText = link.textContent;
            const configId = icon.dataset.configId;
            const currentYear = icon.dataset.year;
            const currentLabel = icon.dataset.label;

            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'dropdown-toggle header-label-toggle';
            toggle.innerHTML = `
                <span class="selected-option">${currentLabel}</span>
                <svg class="dropdown-arrow" width="12" height="8" viewBox="0 0 12 8" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1 1L6 6L11 1" stroke="#666" stroke-width="2" stroke-linecap="round"/></svg>
            `;

            const menu = document.createElement('div');
            menu.className = 'dropdown-menu-filter header-label-menu';
            menu.innerHTML = LABEL_OPTIONS.map(opt => `<div class="dropdown-item" data-value="${opt}">${opt}</div>`).join('');

            link.textContent = '';
            link.appendChild(toggle);
            document.body.appendChild(menu);
            toggle.classList.add('active');

            function positionMenu() {
                const rect = toggle.getBoundingClientRect();
                menu.style.top = `${rect.bottom + 4}px`;
                menu.style.left = `${rect.left}px`;
                menu.style.minWidth = `${rect.width}px`;
            }
            positionMenu();

            function cleanup(restoreText) {
                closeActiveDropdown = null;
                document.removeEventListener('click', outsideClickHandler);
                document.removeEventListener('scroll', scrollHandler, true);
                window.removeEventListener('resize', positionMenu);
                if (menu.parentNode) menu.parentNode.removeChild(menu);
                link.textContent = restoreText;
            }

            const saveChanges = async (newLabel) => {
                if (newLabel === currentLabel) {
                    cleanup(currentText);
                    return;
                }
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
                        cleanup(`${currentYear} г. ${newLabel}`);
                        icon.dataset.label = newLabel;
                        syncModalValueLabels(parseInt(currentYear, 10), newLabel);
                    } else {
                        cleanup(currentText);
                    }
                } catch (error) {
                    console.error('Error:', error);
                    cleanup(currentText);
                }
            };

            menu.querySelectorAll('.dropdown-item').forEach(item => {
                item.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    saveChanges(item.dataset.value);
                });
            });

            function outsideClickHandler(ev) {
                if (!menu.contains(ev.target) && !toggle.contains(ev.target)) {
                    cleanup(currentText);
                }
            }
            function scrollHandler() {
                cleanup(currentText);
            }

            closeActiveDropdown = () => cleanup(currentText);

            setTimeout(() => {
                document.addEventListener('click', outsideClickHandler);
                document.addEventListener('scroll', scrollHandler, true);
                window.addEventListener('resize', positionMenu);
            }, 0);
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const tokencolumnIndicator = document.querySelector('#indicatorsTable')?.dataset?.token;
    if (tokencolumnIndicator) {
        window.planToken = tokencolumnIndicator;
        initEditableHeaders();
    }
    
    const plans_container = document.getElementById('plans-container');
    if(plans_container){
        const selectAllBtn = document.getElementById('selectAllBtn');
        if (selectAllBtn) {
            window.exportPlansLoader = new ExportPlansLoader({
                initialStatus: window.initialStatus || 'all',
                initialYear: window.initialYear || 'all',
                preselectPlanId: window.preselectPlanId || null,
                preselectFormat: window.preselectFormat || null,
                preselectYear: window.preselectYear || null,
                perPage: 50,
                containerId: 'plans-container',
                loadMoreBtnId: 'load-more-btn',
                searchNameId: 'search-name',
                searchYnp: 'search-ynp',
                selectAllId: 'selectAllBtn',
                exportFormId: 'exportForm'
            });
        } else {
            window.plansLoader = new PlansLoader({
                initialStatus: window.initialStatus || 'all',
                initialYear: window.initialYear || 'all',
                perPage: 50,
                containerId: 'plans-container',
                loadMoreBtnId: 'load-more-btn',
                searchNameId: 'search-name',
                searchYnp: 'search-ynp'
            });
        }
    }

    // Обработка отправки editEventeForm (включая перенос значения периодного
    // поля EffCurrYear перед отправкой) теперь выполняется через AJAX внутри
    // PlanEvents.initAjaxForms() — см. ниже, где создаётся window.planEvents.

    if (document.getElementById('indicatorsTable') && document.getElementById('indicators-tbody')) {
        const token = document.getElementById('indicatorsTable')?.dataset?.token;
        if (token) {
            window.planIndicators = new PlanIndicators(token);
        }
    }
    
    // #eventTable рендерится только когда в плане уже ЕСТЬ хотя бы одно
    // мероприятие этого типа (has_events в plan_bp.py) — модалка же
    // "Добавить мероприятие" существует всегда. Раньше PlanEvents (а вместе
    // с ним и AJAX-перехват сабмита формы, см. initAjaxForms) создавался
    // только при наличии таблицы — из-за этого самое первое мероприятие
    // плана отправлялось обычной навигацией браузера, а не через fetch, и
    // прикреплённый файл ТЭО до сервера не доходил (enctype у формы не был
    // указан — см. тот же фикс в шаблоне). Методы рендера таблицы сами
    // по себе no-op, если нужных элементов в DOM нет, поэтому PlanEvents
    // безопасно создавать и без таблицы — только чтобы заработал AJAX-сабмит.
    const addEventForm = document.getElementById('addEventForm');
    if (document.getElementById('eventTable') || addEventForm) {
        const token = document.getElementById('eventTable')?.dataset?.token
            || document.getElementById('plan-token')?.value;
        const eventType = document.getElementById('eventTable')?.dataset?.eventType
            || addEventForm?.querySelector('[name="event_type"]')?.value
            || (window.location.pathname.includes('saving') ? 'saving' : 'increase');
        if (token) {
            window.planEvents = new PlanEvents(token, eventType);
        }
    }

    // sentPlanButton теперь просто ссылка на /plans/plan/send/<token>
    // (plan_review.html) — своей логики тут больше нет, см. plan_send.js.

    if (document.getElementById('editPlanButton')) {
        initConfirmModal({
            triggerId: 'editPlanButton',
            formId: 'editPlanForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.',
            yesText: 'Да, редактировать'
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
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            textSecondId: 'modal-text-second',
            modalText: modalText,
            modalTextSecond: modalTextSecond,
            yesText: 'Да, пройти контроль'
        });
    }

    if (document.querySelector('[data-modal-trigger="deletePlan"]')) {
        initConfirmModal({
            triggerButton: '[data-modal-trigger="deletePlan"]',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы уверены, что хотите безвозвратно удалить этот план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.',
            yesText: 'Да, удалить'
        });
    }

    initDeletePlanConfirmModal();

    // Отправка сообщения больше не требует подтверждения — шлётся сразу по
    // клику/Enter через AJAX (см. plan_actions.html), без промежуточного
    // "Вы действительно хотите отправить?".

    if (document.getElementById('to_deletePlanButton')) {
        initConfirmModal({
            triggerId: 'to_deletePlanButton',
            formId: 'to_deletePlanForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите сменить статус плана на "Есть ошибки"?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус для последующего исправления ошибок.',
            yesText: 'Да, есть ошибки'
        });
    }

    if (document.getElementById('confirmPlanButton')) {
        initConfirmModal({
            triggerId: 'confirmPlanButton',
            formId: 'confirmPlanForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите одобрить план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус и не будет подлежать последующей редакции или удалению со всех сторон.',
            yesText: 'Да, одобрить'
        });
    }

    if (document.getElementById('cancelSentPlanButton')) {
        initConfirmModal({
            triggerId: 'cancelSentPlanButton',
            formId: 'cancelsentPlanForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отменить отправку плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План вернётся в статус "В редакции", путь согласования будет прерван.',
            yesText: 'Да, отменить отправку'
        });
    }

    if (document.getElementById('cancel_auditPlanButton')) {
        initConfirmModal({
            triggerId: 'cancel_auditPlanButton',
            formId: 'cancel_auditPlanForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отменить изменения в статусе плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус обратно на "На рассмотрении". Отменить изменния можно только в течении 3-ех месяцев.',
            yesText: 'Да, отменить'
        });
    }

    if (document.getElementById('logoutButton')) {
        initConfirmModal({
            triggerId: 'logoutButton',
            formId: 'logout_form',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите выйти из системы EnPlans?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить. Убедитесь, что вы сохранили свою работу.',
            yesText: 'Да, выйти'
        });
    }

    if (document.getElementById('editprofileButton')) {
        initConfirmModal({
            triggerId: 'editprofileButton',
            formId: 'editprofileForm',
            modalId: 'confirmModal',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные профиля?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.',
            yesText: 'Да, редактировать'
        });

        const editPhoneList = document.getElementById('edit-phone-group-list');
        if (editPhoneList) {
            const editPhoneHidden = document.getElementById('edit-telephone');
            const editAddPhoneBtn = document.getElementById('edit-add-phone-row');
            const editProfileButton = document.getElementById('editprofileButton');

            const editPhoneInput = new PhoneGroupInput(editPhoneList, editPhoneHidden, editAddPhoneBtn, {
                maxCount: 2,
                inputClass: 'app-input',
                onChange: () => {
                    if (editProfileButton) {
                        editProfileButton.disabled = !editPhoneInput.validate();
                    }
                }
            });

            if (editProfileButton) {
                editProfileButton.disabled = !editPhoneInput.validate();
            }
        }
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
    window.addEventModalWizard = addEventModal1;
    if (addEventModal && addEventModal1) {
        handleModal(addEventModal, document.getElementById('AddEventsModalBtn'), addEventModal.querySelector('.close'));
    }

    const editEventModal = document.getElementById('EditEventModal');
    const eventModal = new EventModal('EditEventModal');
    window.editEventModalWizard = eventModal;

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
    window.addIndicatorModalWizard = IndicatorModal;
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
