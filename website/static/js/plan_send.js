/* Страница «Путь согласования» (plan_send.html) — один экран без шагов.
 *
 * Слева — выбор организаций (вкладки «Утверждающая» / «Согласующие»).
 * Справа — панель: маршрут плана, который собирается по мере выбора
 * (renderRoute): региональное управление (всегда первое, автоматически) →
 * отмеченные согласующие (порядок можно менять) → Департамент по
 * энергоэффективности (если план проходит порог) → утверждающая; под ним —
 * «Кто подпишет» (выбор руководителя) и «Отправить на подпись».
 *
 * Порядок согласующих = порядок ключей selectedCoordinators (Map) — именно
 * в нём id уходят на сервер в coordinator_ids.
 */
class PlanSendWizard {
    constructor(rootId) {
        this.root = document.getElementById(rootId);
        if (!this.root) {
            console.error('[PlanSendWizard] Root element not found:', rootId);
            return;
        }

        this.selectedCoordinators = new Map();
        this.selectedApprover = null;
        this.selectedApproverName = '';

        this.coordinatorSearch = this.root.querySelector('#coordinator-search');
        this.approverSearch = this.root.querySelector('#approver-search');
        this.coordinatorTbody = this.root.querySelector('#coordinator-tbody');
        this.approverTbody = this.root.querySelector('#approver-tbody');
        this.coordinatorIdsInput = this.root.querySelector('#coordinator-ids-input');
        this.approverIdInput = this.root.querySelector('#approver-id-input');
        this.coordinatorCount = this.root.querySelector('#coordinator-count');
        this.approverCount = this.root.querySelector('#approver-count');

        this.tabs = Array.from(this.root.querySelectorAll('.ps-tab'));
        this.pickerPanels = Array.from(this.root.querySelectorAll('[data-picker-panel]'));

        this.routeEl = this.root.querySelector('#ps-route');
        this.routeList = this.root.querySelector('#ps-route-list');
        this.routeNote = this.root.querySelector('#ps-route-note');
        this.signerSelect = this.root.querySelector('#signer-select');
        this.submitButton = this.root.querySelector('#submit-sent-button');

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

        // Изначально без сортировки — на кнопке «Сортировка».
        this.coordinatorSort = { field: null, dir: 'asc' };
        this.approverSort = { field: null, dir: 'asc' };

        this.regionNumber = window.regionNumber || '';
        this.regionNames = {
            1: 'Брестское областное управление по надзору за рациональным использованием ТЭР',
            2: 'Витебское областное управление по надзору за рациональным использованием ТЭР',
            3: 'Гомельское областное управление по надзору за рациональным использованием ТЭР',
            4: 'Гродненское областное управление по надзору за рациональным использованием ТЭР',
            5: 'Управление г. Минск по надзору за рациональным использованием ТЭР',
            6: 'Минское областное управление по надзору за рациональным использованием ТЭР',
            7: 'Могилевское областное управление по надзору за рациональным использованием ТЭР'
        };

        this.init();
    }

    init() {
        this.initPrefill();
        this.loadCoordinators();
        this.loadApprovers();
        this.initTabs();
        this.initSearch();
        this.initNavigation();
        this.initScrollLoading();
        this.initSort();
        this.updateCounts();
        this.renderRoute();
        this.updateButtonsState();
    }

    /* ---------- вкладки «Согласующие» / «Утверждающая» ---------- */

    initTabs() {
        this.tabs.forEach((tab) => {
            tab.addEventListener('click', () => this.showPicker(tab.dataset.picker));
        });
    }

    showPicker(kind, focusSearch = false) {
        this.tabs.forEach((tab) => {
            const active = tab.dataset.picker === kind;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        this.pickerPanels.forEach((panel) => {
            panel.hidden = panel.dataset.pickerPanel !== kind;
        });
        if (focusSearch) {
            (kind === 'approver' ? this.approverSearch : this.coordinatorSearch)?.focus();
        }
        // список только что стал видимым — догрузить, если он короче окна
        if (kind === 'approver') {
            this.fillIfShort(this.approverTbody, () => this.approverHasMore && !this.approverLoading, () => this.loadApprovers(false));
        } else {
            this.fillIfShort(this.coordinatorTbody, () => this.coordinatorHasMore && !this.coordinatorLoading, () => this.loadCoordinators(false));
        }
    }

    /* ---------- маршрут прошлого раза ---------- */

    // window.previousRoute (plan_bp._previous_route): kind 'this' — этот
    // же план уже отправляли, маршрут подставляется сразу; 'previous' —
    // маршрут другого плана организации, подставляется по кнопке.
    initPrefill() {
        const route = window.previousRoute;
        const box = this.root.querySelector('#ps-prefill');
        if (!route || !box) return;
        const text = box.querySelector('#ps-prefill-text');

        if (route.kind === 'this') this.applyRoute(route, false);

        box.querySelector('#ps-prefill-apply')?.addEventListener('click', (e) => {
            this.applyRoute(route);
            if (text) text.textContent = `Маршрут из плана на ${route.year} год подставлен. Его можно изменить.`;
            e.currentTarget.remove();
        });
        box.querySelector('#ps-prefill-clear')?.addEventListener('click', () => {
            this.applyRoute(null);
            box.remove();
        });
    }

    applyRoute(route, render = true) {
        this.selectedCoordinators = new Map((route?.coordinators || []).map((c) => [String(c.id), c.name]));
        this.selectedApprover = route?.approver ? String(route.approver.id) : null;
        this.selectedApproverName = route?.approver ? route.approver.name : '';
        this.syncCheckboxes();
        if (render) this.onSelectionChange();
    }

    // Отметки в уже загруженных списках — по текущему выбору.
    syncCheckboxes() {
        this.coordinatorTbody?.querySelectorAll('.org-picker-row').forEach((row) => {
            const on = this.selectedCoordinators.has(String(row.dataset.id));
            const cb = row.querySelector('.coordinator-checkbox');
            if (cb) cb.checked = on;
            row.classList.toggle('active-row', on);
        });
        this.approverTbody?.querySelectorAll('.org-picker-row').forEach((row) => {
            const on = this.selectedApprover === String(row.dataset.id);
            const cb = row.querySelector('.approver-checkbox');
            if (cb) cb.checked = on;
            row.classList.toggle('active-row', on);
        });
    }

    /* ---------- сортировка ---------- */

    // Выпадающий список «Сортировка» (.custom-dropdown, как фильтры в
    // списке планов; позиционирование меню — base.js). Пункт «Без
    // сортировки» возвращает подпись «Сортировка».
    initSort() {
        const dropdowns = Array.from(this.root.querySelectorAll('.ps-sort'));
        const close = (dd) => {
            dd.classList.remove('active');
            dd.querySelector('.dropdown-toggle')?.setAttribute('aria-expanded', 'false');
        };

        dropdowns.forEach((dd) => {
            const toggle = dd.querySelector('.dropdown-toggle');
            const label = dd.querySelector('.selected-option');
            const items = Array.from(dd.querySelectorAll('.dropdown-item'));
            const isApprover = dd.dataset.sortFor === 'approver';

            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const open = !dd.classList.contains('active');
                dropdowns.forEach(close);
                if (open) {
                    dd.classList.add('active');
                    toggle.setAttribute('aria-expanded', 'true');
                    (items.find((i) => i.classList.contains('is-selected')) || items[0])?.focus();
                }
            });

            items.forEach((item, idx) => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const field = item.dataset.value || null;
                    const state = isApprover ? this.approverSort : this.coordinatorSort;
                    items.forEach((i) => i.classList.toggle('is-selected', i === item && !!field));
                    label.textContent = field ? item.textContent.trim() : label.dataset.placeholder;
                    dd.classList.toggle('has-value', !!field);
                    close(dd);
                    toggle.focus();
                    if (state.field === field) return;
                    state.field = field;
                    state.dir = 'asc';
                    if (isApprover) this.loadApprovers(true);
                    else this.loadCoordinators(true);
                });
                item.addEventListener('keydown', (e) => {
                    if (e.key === 'ArrowDown') { e.preventDefault(); items[Math.min(idx + 1, items.length - 1)].focus(); }
                    if (e.key === 'ArrowUp') { e.preventDefault(); items[Math.max(idx - 1, 0)].focus(); }
                    if (e.key === 'Escape') { close(dd); toggle.focus(); }
                });
            });
        });

        document.addEventListener('click', (e) => {
            dropdowns.forEach((dd) => { if (!dd.contains(e.target)) close(dd); });
        });
    }

    buildSortParams(sortState) {
        if (!sortState || !sortState.field) return '';
        return `&sort=${encodeURIComponent(sortState.field)}&order=${sortState.dir}`;
    }

    /* ---------- загрузка списков ---------- */

    async loadCoordinators(reset = true) {
        if (this.coordinatorLoading) return;

        if (reset) {
            this.coordinatorPage = 1;
            this.coordinatorHasMore = true;
            this.coordinatorTbody.innerHTML = '';
            this.coordinatorTbody.scrollTop = 0;
        }

        if (!this.coordinatorHasMore) {
            this.removeLoading(this.coordinatorTbody);
            return;
        }

        this.coordinatorLoading = true;
        this.showLoading(this.coordinatorTbody);

        try {
            const url = `/api/organizations?type=auditor&page=${this.coordinatorPage}&per_page=10&q=${encodeURIComponent(this.coordinatorSearchQuery)}&hide_rm=true${this.buildSortParams(this.coordinatorSort)}`;
            const response = await fetch(url);
            const data = await response.json();

            this.removeLoading(this.coordinatorTbody);
            if (data.error) {
                console.error('Error loading coordinators:', data.error);
                return;
            }

            if (data.organizations && data.organizations.length > 0) {
                this.renderOrganizations(this.coordinatorTbody, data.organizations, 'coordinator');
            } else if (reset) {
                this.showEmptyMessage(this.coordinatorTbody);
            }

            this.coordinatorHasMore = data.has_next || false;
            this.coordinatorPage = data.page + 1;
        } catch (error) {
            console.error('Error loading coordinators:', error);
            this.removeLoading(this.coordinatorTbody);
        } finally {
            this.coordinatorLoading = false;
        }
        this.fillIfShort(this.coordinatorTbody, () => this.coordinatorHasMore, () => this.loadCoordinators(false));
    }

    async loadApprovers(reset = true) {
        if (this.approverLoading) return;

        if (reset) {
            this.approverPage = 1;
            this.approverHasMore = true;
            this.approverTbody.innerHTML = '';
            this.approverTbody.scrollTop = 0;
        }

        if (!this.approverHasMore) {
            this.removeLoading(this.approverTbody);
            return;
        }

        this.approverLoading = true;
        this.showLoading(this.approverTbody);

        try {
            const url = `/api/organizations?type=approver&page=${this.approverPage}&per_page=10&q=${encodeURIComponent(this.approverSearchQuery)}${this.buildSortParams(this.approverSort)}`;
            const response = await fetch(url);
            const data = await response.json();

            this.removeLoading(this.approverTbody);
            if (data.error) {
                console.error('Error loading approvers:', data.error);
                return;
            }

            if (data.organizations && data.organizations.length > 0) {
                this.renderOrganizations(this.approverTbody, data.organizations, 'approver');
            } else if (reset) {
                this.showEmptyMessage(this.approverTbody);
            }

            this.approverHasMore = data.has_next || false;
            this.approverPage = data.page + 1;
        } catch (error) {
            console.error('Error loading approvers:', error);
            this.removeLoading(this.approverTbody);
        } finally {
            this.approverLoading = false;
        }
        this.fillIfShort(this.approverTbody, () => this.approverHasMore, () => this.loadApprovers(false));
    }

    // Список теперь по высоте содержимого (до --ps-list-max): если порция
    // поместилась без прокрутки, событие scroll не случится и остальные
    // организации не подгрузятся — дозагружаем, пока список не заполнится.
    // Скрытая вкладка (offsetParent === null) не меряется — догрузится при
    // прокрутке после переключения.
    fillIfShort(list, hasMore, load) {
        if (!list || list.offsetParent === null || !hasMore()) return;
        if (list.scrollHeight <= list.clientHeight + 4) load();
    }

    renderOrganizations(list, organizations, type) {
        if (!list || !organizations || organizations.length === 0) return;

        organizations.forEach(org => {
            const isCoordinator = type === 'coordinator';
            const checkboxType = isCoordinator ? 'coordinator-checkbox' : 'approver-checkbox';
            const isChecked = isCoordinator ? this.selectedCoordinators.has(String(org.id)) : this.selectedApprover === String(org.id);

            // <label> оборачивает чекбокс — клик по всей строке переключает выбор.
            const row = document.createElement('label');
            row.className = 'org-picker-row';
            row.dataset.id = org.id;
            row.dataset.name = org.name;
            row.innerHTML = `
                <input type="checkbox" class="${checkboxType}" value="${org.id}" data-name="${this.escapeHtml(org.name)}" ${isChecked ? 'checked' : ''}>
                <span class="org-picker-check"></span>
                <span class="org-picker-info">
                    <span class="org-picker-name">${this.escapeHtml(org.name)}</span>
                    <span class="org-picker-meta">
                        ${org.ynp ? `<span class="org-picker-meta-item">УНП ${this.escapeHtml(org.ynp)}</span>` : ''}
                        ${org.okpo ? `<span class="org-picker-meta-item">ОКПО ${this.escapeHtml(org.okpo)}</span>` : ''}
                        ${org.region ? `<span class="org-picker-meta-item">${this.escapeHtml(org.region)}</span>` : ''}
                    </span>
                </span>
            `;

            if (isChecked) row.classList.add('active-row');
            list.appendChild(row);

            if (isCoordinator) {
                this.initCoordinatorRow(row, row.querySelector('.coordinator-checkbox'));
            } else {
                this.initApproverRow(row, row.querySelector('.approver-checkbox'));
            }
        });
    }

    initCoordinatorRow(row, checkbox) {
        if (!checkbox) return;
        checkbox.addEventListener('change', (e) => {
            const id = e.target.value;
            if (e.target.checked) {
                this.selectedCoordinators.set(id, e.target.dataset.name);
                row.classList.add('active-row');
            } else {
                this.selectedCoordinators.delete(id);
                row.classList.remove('active-row');
            }
            this.onSelectionChange();
        });
    }

    initApproverRow(row, checkbox) {
        if (!checkbox) return;
        // Визуально радио (org-picker-list--radio) — снимаем остальные.
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.approverTbody.querySelectorAll('.org-picker-row').forEach(r => {
                    const cb = r.querySelector('.approver-checkbox');
                    if (cb && cb !== e.target) {
                        cb.checked = false;
                        r.classList.remove('active-row');
                    }
                });
                this.selectedApprover = e.target.value;
                this.selectedApproverName = e.target.dataset.name;
                row.classList.add('active-row');
            } else {
                this.selectedApprover = null;
                this.selectedApproverName = '';
                row.classList.remove('active-row');
            }
            this.onSelectionChange();
        });
    }

    onSelectionChange() {
        this.updateCounts();
        this.renderRoute();
        this.updateButtonsState();
    }

    updateCounts() {
        const setCount = (el, n) => {
            if (!el) return;
            el.textContent = n;
            el.classList.toggle('is-zero', n === 0);
        };
        setCount(this.coordinatorCount, this.selectedCoordinators.size);
        setCount(this.approverCount, this.selectedApprover ? 1 : 0);
    }

    showLoading(list) {
        if (!list) return;
        let loadingRow = list.querySelector('.org-picker-loading-row');
        if (!loadingRow) {
            loadingRow = document.createElement('div');
            loadingRow.className = 'org-picker-loading-row';
            loadingRow.innerHTML = `<span class="loading-spinner"></span> Загрузка...`;
            list.appendChild(loadingRow);
        }
        loadingRow.style.display = '';
    }

    removeLoading(list) {
        list?.querySelector('.org-picker-loading-row')?.remove();
    }

    showEmptyMessage(list) {
        if (!list || list.querySelector('.org-picker-empty-row')) return;
        const row = document.createElement('div');
        row.className = 'org-picker-empty-row';
        row.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="10.5" cy="10.5" r="6.5"></circle>
                <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                <line x1="8" y1="10.5" x2="13" y2="10.5"></line>
            </svg>
            <span>Организация не найдена. Проверьте название или введите УНП.</span>
        `;
        list.appendChild(row);
    }

    initScrollLoading() {
        const bind = (list, isLoading, hasMore, load) => {
            list?.addEventListener('scroll', (e) => {
                const c = e.target;
                if (c.scrollTop + c.clientHeight >= c.scrollHeight - 50 && !isLoading() && hasMore()) load();
            });
        };
        bind(this.coordinatorTbody, () => this.coordinatorLoading, () => this.coordinatorHasMore, () => this.loadCoordinators(false));
        bind(this.approverTbody, () => this.approverLoading, () => this.approverHasMore, () => this.loadApprovers(false));
    }

    initSearch() {
        this.coordinatorSearch?.addEventListener('input', (e) => {
            clearTimeout(this.coordinatorSearchTimeout);
            this.coordinatorSearchTimeout = setTimeout(() => {
                const q = e.target.value.trim();
                if (q !== this.coordinatorSearchQuery) {
                    this.coordinatorSearchQuery = q;
                    this.loadCoordinators(true);
                }
            }, 300);
        });

        this.approverSearch?.addEventListener('input', (e) => {
            clearTimeout(this.approverSearchTimeout);
            this.approverSearchTimeout = setTimeout(() => {
                const q = e.target.value.trim();
                if (q !== this.approverSearchQuery) {
                    this.approverSearchQuery = q;
                    this.loadApprovers(true);
                }
            }, 300);
        });
    }

    /* ---------- маршрут справа ---------- */

    renderRoute() {
        const list = this.routeList;
        if (!list) return;
        const items = [];

        items.push({
            kind: 'auto',
            // полное название из базы (plan_send_page), запасной вариант — по номеру области
            name: window.regionOrgName || this.regionNames[this.regionNumber] || 'Региональное управление по надзору за рациональным использованием ТЭР',
            sub: 'Добавляется автоматически',
        });

        const coordinators = Array.from(this.selectedCoordinators.entries());
        coordinators.forEach(([id, name], i) => {
            items.push({ kind: 'coordinator', id, name, index: i, total: coordinators.length });
        });
        if (!coordinators.length) {
            items.push({ kind: 'pick-coordinator' });
        }

        if (window.energyDepartmentName) {
            items.push({
                kind: 'auto',
                name: window.energyDepartmentName,
                sub: 'Добавлен автоматически: потребление от 25 тыс. т у.т.',
            });
        }

        items.push(this.selectedApprover
            ? { kind: 'approver', name: this.selectedApproverName || `ID ${this.selectedApprover}` }
            : { kind: 'pick-approver' });

        let number = 0;
        list.innerHTML = '';
        items.forEach((item) => {
            const li = document.createElement('li');
            li.className = 'ps-route-item';
            const isStage = item.kind === 'auto' || item.kind === 'coordinator' || item.kind === 'approver';
            if (isStage) number += 1;

            if (item.kind === 'pick-coordinator') {
                li.classList.add('ps-route-item--empty');
                li.innerHTML = `
                    <span class="ps-route-marker" aria-hidden="true">+</span>
                    <div class="ps-route-body">
                        <button type="button" class="ps-route-pick" data-pick="coordinator">Добавить согласующие организации</button>
                        <span class="ps-route-sub">Необязательно</span>
                    </div>`;
            } else if (item.kind === 'pick-approver') {
                li.classList.add('ps-route-item--empty', 'ps-route-item--approver');
                li.innerHTML = `
                    <span class="ps-route-marker" aria-hidden="true">${number + 1}</span>
                    <div class="ps-route-body">
                        <button type="button" class="ps-route-pick" data-pick="approver">Выбрать утверждающую организацию</button>
                    </div>`;
            } else {
                li.classList.add(`ps-route-item--${item.kind}`);
                const sub = item.kind === 'approver' ? 'Утверждает план' : (item.sub || '');
                li.innerHTML = `
                    <span class="ps-route-marker" aria-hidden="true">${number}</span>
                    <div class="ps-route-body">
                        <span class="ps-route-name">${this.escapeHtml(item.name)}</span>
                        ${sub ? `<span class="ps-route-sub">${this.escapeHtml(sub)}</span>` : ''}
                    </div>`;
                if (item.kind === 'coordinator' || item.kind === 'approver') {
                    li.appendChild(this.routeTools(item));
                }
            }
            list.appendChild(li);
        });

        list.querySelectorAll('[data-pick]').forEach((btn) => {
            btn.addEventListener('click', () => this.showPicker(btn.dataset.pick, true));
        });
    }

    routeTools(item) {
        const tools = document.createElement('div');
        tools.className = 'ps-route-tools';
        const icon = {
            up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 15l6-6 6 6"/></svg>',
            down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
            remove: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
        };
        const add = (action, label, disabled = false) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'ps-route-tool';
            b.title = label;
            b.setAttribute('aria-label', `${label}: ${item.name}`);
            b.disabled = disabled;
            b.innerHTML = icon[action];
            b.addEventListener('click', () => {
                if (item.kind === 'approver') this.removeApprover();
                else if (action === 'remove') this.removeCoordinator(item.id);
                else this.moveCoordinator(item.id, action === 'up' ? -1 : 1);
            });
            tools.appendChild(b);
        };
        if (item.kind === 'coordinator' && item.total > 1) {
            add('up', 'Выше', item.index === 0);
            add('down', 'Ниже', item.index === item.total - 1);
        }
        add('remove', 'Убрать из маршрута');
        return tools;
    }

    moveCoordinator(id, delta) {
        const entries = Array.from(this.selectedCoordinators.entries());
        const i = entries.findIndex(([key]) => key === id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= entries.length) return;
        [entries[i], entries[j]] = [entries[j], entries[i]];
        this.selectedCoordinators = new Map(entries);
        this.renderRoute();
        // фокус остаётся на той же кнопке перемещённой организации
        const btn = this.routeList.querySelectorAll('.ps-route-item--coordinator')[j]
            ?.querySelector(`.ps-route-tool[title="${delta < 0 ? 'Выше' : 'Ниже'}"]`);
        (btn && !btn.disabled ? btn : this.routeList.querySelectorAll('.ps-route-item--coordinator')[j]?.querySelector('.ps-route-tool'))?.focus();
    }

    removeCoordinator(id) {
        const checkbox = this.coordinatorTbody?.querySelector(`.coordinator-checkbox[value="${id}"]`);
        if (checkbox) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        } else {
            this.selectedCoordinators.delete(id);
            this.onSelectionChange();
        }
    }

    removeApprover() {
        const checkbox = this.approverTbody?.querySelector(`.approver-checkbox[value="${this.selectedApprover}"]`);
        if (checkbox) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        } else {
            this.selectedApprover = null;
            this.selectedApproverName = '';
            this.onSelectionChange();
        }
    }

    /* ---------- руководитель и отправка ---------- */

    initNavigation() {
        this.root.querySelector('#sentForm')?.addEventListener('submit', (e) => {
            if (!this.selectedApprover || !this.signerSelect?.value) {
                e.preventDefault();
                this.updateButtonsState();
                return;
            }
            if (this.coordinatorIdsInput) {
                this.coordinatorIdsInput.value = Array.from(this.selectedCoordinators.keys()).join(',');
            }
            if (this.approverIdInput) {
                this.approverIdInput.value = this.selectedApprover;
            }
        });

        const signerSelect = this.signerSelect;
        signerSelect?.addEventListener('change', () => this.updateButtonsState());

        // Свой выпадающий список вместо <select> — клик по пункту пишет id
        // в скрытый #signer-select и шлёт 'change'.
        const signerPicker = this.root.querySelector('#signer-picker');
        const signerToggle = this.root.querySelector('#signer-picker-toggle');
        const signerValue = this.root.querySelector('#signer-picker-value');
        const signerMenu = this.root.querySelector('#signer-picker-menu');
        if (signerPicker && signerToggle && signerValue && signerMenu && signerSelect) {
            signerToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                if (signerToggle.disabled) return;
                signerPicker.classList.toggle('active');
            });

            signerMenu.querySelectorAll('.signer-picker-item').forEach((item) => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    signerMenu.querySelectorAll('.signer-picker-item').forEach((i) => i.classList.remove('is-selected'));
                    item.classList.add('is-selected');
                    signerValue.textContent = item.dataset.name.trim();
                    signerSelect.value = item.dataset.id;
                    signerSelect.dispatchEvent(new Event('change'));
                    signerPicker.classList.remove('active');
                });
            });

            document.addEventListener('click', (e) => {
                if (!signerPicker.contains(e.target)) signerPicker.classList.remove('active');
            });

            // Подписать может только один человек — выбираем его сразу.
            const items = signerMenu.querySelectorAll('.signer-picker-item');
            if (items.length === 1) items[0].click();
        }
    }

    // «Отправить на подпись» — когда выбраны утверждающая и руководитель
    // (согласующие необязательны: региональное управление добавляется
    // автоматически). Под кнопкой — чего ещё не хватает.
    updateButtonsState() {
        const hasApprover = !!this.selectedApprover;
        const hasSigner = !!this.signerSelect?.value;
        if (this.submitButton) this.submitButton.disabled = !(hasApprover && hasSigner);
        if (this.routeNote) {
            let note = '';
            if (!hasApprover && !hasSigner) note = 'Выберите утверждающую организацию и руководителя.';
            else if (!hasApprover) note = 'Выберите утверждающую организацию.';
            else if (!hasSigner) note = 'Выберите руководителя, который подпишет план.';
            this.routeNote.textContent = note;
            this.routeNote.hidden = !note;
        }
    }

    // Экранирует и для текста, и для атрибутов: textContent→innerHTML не
    // трогает кавычки, а в названиях они почти всегда (ОАО "Лидское
    // пиво") — в data-name="..." название обрывалось на первой кавычке, и
    // в маршрут попадало только «ОАО».
    escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('planSendRoot')) {
        window.planSendWizard = new PlanSendWizard('planSendRoot');
    }
});
