(function () {
    const dataEl = document.getElementById('cabinetData');
    if (!dataEl) return;
    const data = JSON.parse(dataEl.textContent || '{}');
    const members = new Map((data.members || []).map((m) => [String(m.id), m]));
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const ROLE_SINGLE = ['org_head', 'org_head_deputy'];

    const notify = (msg, kind) => {
        if (typeof messageFlash !== 'undefined') messageFlash.addMessage(msg, kind);
        else alert(msg);
    };

    function request(url, body, method) {
        return fetch(url, {
            method: method || 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: body ? JSON.stringify(body) : undefined,
        }).then((r) => r.json().catch(() => ({})).then((d) => {
            if (!r.ok || d.success === false) throw new Error(d.error || 'Не удалось выполнить действие');
            return d;
        }));
    }

    function reloadOnTab() {
        const url = new URL(window.location.href);
        url.searchParams.set('profileTabs', 'cabinet');
        window.location.replace(url.toString());
    }

    function openModal(modal) {
        modal.classList.add('active');
        const focusable = modal.querySelector('input:not([type="radio"]):not([hidden]), button[type="submit"], .main-btn');
        if (focusable) setTimeout(() => focusable.focus(), 60);
    }
    function closeModal(modal) {
        modal.classList.remove('active');
        if (modal._onClose) {
            const cb = modal._onClose;
            modal._onClose = null;
            cb();
        }
    }
    document.querySelectorAll('#cabinetEmployeeModal, #cabinetPasswordModal, #cabinetCredentialsModal, #cabinetConfirmModal').forEach((modal) => {
        modal.querySelector('.modal-header .close')?.addEventListener('click', () => closeModal(modal));
        modal.querySelectorAll('[data-cabinet-close]').forEach((b) => b.addEventListener('click', () => closeModal(modal)));
        modal.addEventListener('mousedown', (e) => { if (e.target === modal) closeModal(modal); });
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        const picker = document.querySelector('.cabinet-picker.active');
        if (picker) {
            closePicker(picker);
            picker.querySelector('.signer-picker-toggle').focus();
            return;
        }
        const open = document.querySelector('[id^="cabinet"].modal.active');
        if (open) closeModal(open);
    });

    function closePicker(picker) {
        picker.classList.remove('active');
        picker.querySelector('.signer-picker-toggle').setAttribute('aria-expanded', 'false');
    }
    function pickerItems(picker) {
        return Array.from(picker.querySelectorAll('.signer-picker-item'));
    }
    function setPicker(picker, hidden, value) {
        const wanted = value === null || value === undefined ? '' : String(value);
        let label = picker.dataset.placeholder;
        pickerItems(picker).forEach((item) => {
            const selected = item.dataset.value === wanted && (wanted !== '' || !hidden.dataset.required);
            item.classList.toggle('is-selected', selected);
            item.setAttribute('aria-selected', selected ? 'true' : 'false');
            if (selected) label = item.dataset.name;
        });
        hidden.value = wanted;
        const valueEl = picker.querySelector('.signer-picker-value');
        valueEl.textContent = label;
        picker.classList.toggle('has-value', wanted !== '');
    }
    function initPicker(picker, hidden, onPick) {
        const toggle = picker.querySelector('.signer-picker-toggle');
        const enabledItems = () => pickerItems(picker).filter((i) => !i.classList.contains('is-disabled'));
        const open = () => {
            document.querySelectorAll('.cabinet-picker.active').forEach((p) => p !== picker && closePicker(p));
            picker.classList.add('active');
            toggle.setAttribute('aria-expanded', 'true');
            const target = picker.querySelector('.signer-picker-item.is-selected') || enabledItems()[0];
            if (target) target.focus();
        };
        const choose = (item) => {
            if (item.classList.contains('is-disabled')) return;
            setPicker(picker, hidden, item.dataset.value);
            closePicker(picker);
            toggle.focus();
            if (onPick) onPick(item.dataset.value);
        };
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (picker.classList.contains('active')) closePicker(picker); else open();
        });
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); }
        });
        picker.querySelector('.signer-picker-menu').addEventListener('click', (e) => {
            e.stopPropagation();
            const item = e.target.closest('.signer-picker-item');
            if (item) choose(item);
        });
        picker.querySelector('.signer-picker-menu').addEventListener('keydown', (e) => {
            const items = enabledItems();
            const idx = items.indexOf(document.activeElement);
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                const next = items[(idx + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length];
                if (next) next.focus();
            } else if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (document.activeElement.classList.contains('signer-picker-item')) choose(document.activeElement);
            } else if (e.key === 'Tab') {
                closePicker(picker);
            }
        });
        document.addEventListener('click', (e) => {
            if (!picker.contains(e.target)) closePicker(picker);
        });
    }

    function setBusy(button, busy) {
        if (!button) return;
        button.disabled = busy;
        button.classList.toggle('is-checking', busy);
    }
    function showError(form, message) {
        const el = form.querySelector('.cabinet-form-error');
        if (!el) return notify(message, 'error');
        el.textContent = message || '';
        el.hidden = !message;
    }

    function bindPasswordMode(form) {
        const input = form.querySelector('input[name="password"]');
        const wrap = form.querySelector('.cabinet-password-input');
        const sync = () => {
            const manual = form.querySelector('input[name="password_mode"]:checked')?.value === 'manual';
            wrap.hidden = !manual;
            input.required = manual;
            if (manual) input.focus();
        };
        form.querySelectorAll('input[name="password_mode"]').forEach((r) => r.addEventListener('change', sync));
        return () => {
            form.querySelector('input[name="password_mode"][value="generate"]').checked = true;
            input.value = '';
            wrap.hidden = true;
            input.required = false;
        };
    }
    function readPassword(form) {
        const mode = form.querySelector('input[name="password_mode"]:checked')?.value || 'generate';
        const password = form.querySelector('input[name="password"]').value;
        if (mode === 'manual' && password.length < 8) return { error: 'Пароль не короче 8 символов' };
        return { password_mode: mode, password: mode === 'manual' ? password : '' };
    }

    const credModal = document.getElementById('cabinetCredentialsModal');
    function showCredentials(title, who, creds) {
        document.getElementById('cabinetCredentialsTitle').textContent = title;
        document.getElementById('cabinetCredentialsWho').textContent = who;
        document.getElementById('cabinetCredLogin').textContent = creds.login;
        document.getElementById('cabinetCredPassword').textContent = creds.password;
        credModal._onClose = reloadOnTab;
        openModal(credModal);
    }
    async function copyText(text, button) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (e) {
            const t = document.createElement('textarea');
            t.value = text;
            t.style.position = 'fixed';
            t.style.opacity = '0';
            document.body.appendChild(t);
            t.select();
            document.execCommand('copy');
            t.remove();
        }
        button.classList.add('copied');
        clearTimeout(button._copiedTimer);
        button._copiedTimer = setTimeout(() => button.classList.remove('copied'), 1500);
    }
    credModal.querySelectorAll('[data-copy-target]').forEach((btn) => {
        btn.addEventListener('click', () => copyText(document.getElementById(btn.dataset.copyTarget).textContent, btn));
    });
    credModal.querySelector('[data-copy-both]').addEventListener('click', (e) => {
        const login = document.getElementById('cabinetCredLogin').textContent;
        const password = document.getElementById('cabinetCredPassword').textContent;
        copyText(`Логин: ${login}\nПароль: ${password}`, e.currentTarget);
    });

    const empModal = document.getElementById('cabinetEmployeeModal');
    const empForm = document.getElementById('cabinetEmployeeForm');
    const empSubmit = document.getElementById('cabinetEmployeeSubmit');
    const loginInput = empForm.querySelector('input[name="login"]');
    const loginHint = document.getElementById('cabLoginHint');
    const loginHintDefault = loginHint.textContent;
    const resetEmpPassword = bindPasswordMode(empForm);
    const rolePicker = document.getElementById('cabRolePicker');
    const roleInput = document.getElementById('cabRole');
    const deptPicker = document.getElementById('cabDepartmentPicker');
    const deptInput = document.getElementById('cabDepartment');
    roleInput.dataset.required = '1';
    initPicker(rolePicker, roleInput);
    initPicker(deptPicker, deptInput);
    const phoneList = document.getElementById('cabPhoneList');
    const phoneHidden = document.getElementById('cabPhone');
    const phoneInput = new PhoneGroupInput(phoneList, phoneHidden, document.getElementById('cabPhoneAdd'), {
        maxCount: 2,
        inputClass: 'app-input',
    });
    let editingId = null;
    let loginTouched = false;
    let suggestTimer = null;
    let checkTimer = null;

    function roleHolders(excludeId) {
        const taken = {};
        members.forEach((m) => {
            if (m.is_active && ROLE_SINGLE.includes(m.org_role) && String(m.id) !== String(excludeId)) taken[m.org_role] = m;
        });
        return taken;
    }
    function syncRoleOptions(excludeId, currentRole) {
        const taken = roleHolders(excludeId);
        pickerItems(rolePicker).forEach((item) => {
            const holder = taken[item.dataset.value];
            const blocked = !!holder && item.dataset.value !== currentRole;
            item.classList.toggle('is-disabled', blocked);
            item.setAttribute('aria-disabled', blocked ? 'true' : 'false');
            const hint = item.querySelector('[data-role-taken]');
            hint.hidden = !blocked;
            if (blocked) hint.textContent = 'Уже назначен: ' + (holder.full_name || holder.login);
        });
    }

    function setLoginHint(text, state) {
        loginHint.textContent = text || loginHintDefault;
        loginHint.classList.toggle('is-error', state === 'error');
        loginHint.classList.toggle('is-ok', state === 'ok');
    }
    function suggestLogin() {
        if (loginTouched) return;
        clearTimeout(suggestTimer);
        const first = empForm.first_name.value.trim();
        const last = empForm.last_name.value.trim();
        if (!first || !last) return;
        suggestTimer = setTimeout(() => {
            const qs = new URLSearchParams({ first_name: first, last_name: last });
            if (editingId) qs.set('user_id', editingId);
            fetch('/cabinet/employees/login-suggest?' + qs, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then((r) => r.json())
                .then((d) => {
                    if (loginTouched || !d.login) return;
                    loginInput.value = d.login;
                    setLoginHint('Логин свободен', 'ok');
                })
                .catch(() => {});
        }, 300);
    }
    function checkLogin() {
        clearTimeout(checkTimer);
        const value = loginInput.value.trim();
        if (!value) {
            loginTouched = false;
            setLoginHint();
            suggestLogin();
            return;
        }
        checkTimer = setTimeout(() => {
            const qs = new URLSearchParams({ login: value });
            if (editingId) qs.set('user_id', editingId);
            fetch('/cabinet/employees/login-suggest?' + qs, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then((r) => r.json())
                .then((d) => setLoginHint(d.available ? 'Логин свободен' : d.error, d.available ? 'ok' : 'error'))
                .catch(() => {});
        }, 300);
    }
    empForm.first_name.addEventListener('input', suggestLogin);
    empForm.last_name.addEventListener('input', suggestLogin);
    loginInput.addEventListener('input', () => { loginTouched = true; checkLogin(); });

    function openEmployeeModal(member) {
        empForm.reset();
        resetEmpPassword();
        showError(empForm, '');
        editingId = member ? member.id : null;
        loginTouched = !!member;
        setLoginHint(member ? 'Изменение логина: сотрудник войдёт уже с новым логином' : '');
        document.getElementById('cabinetEmployeeTitle').textContent = member ? 'Редактирование сотрудника' : 'Новый сотрудник';
        empSubmit.querySelector('.btn-text').textContent = member ? 'Сохранить изменения' : 'Создать учётную запись';
        empForm.querySelector('[data-password-block]').hidden = !!member;
        if (member) {
            ['last_name', 'first_name', 'patronymic_name', 'post', 'login'].forEach((k) => {
                empForm[k].value = member[k] || '';
            });
        }
        phoneList.dataset.existingPhones = member ? (member.telephone || '') : '';
        phoneInput.init();
        syncRoleOptions(editingId, member ? member.org_role : null);
        setPicker(rolePicker, roleInput, member ? member.org_role : 'executor');
        setPicker(deptPicker, deptInput, member ? member.department_id : '');
        document.querySelectorAll('.cabinet-picker.active').forEach(closePicker);
        openModal(empModal);
    }

    empForm.addEventListener('submit', (e) => {
        e.preventDefault();
        showError(empForm, '');
        const body = {
            last_name: empForm.last_name.value.trim(),
            first_name: empForm.first_name.value.trim(),
            patronymic_name: empForm.patronymic_name.value.trim(),
            post: empForm.post.value.trim(),
            telephone: phoneInput.validate() ? phoneHidden.value : '',
            department_id: deptInput.value || null,
            org_role: roleInput.value,
            login: loginInput.value.trim(),
        };
        if (!body.last_name || !body.first_name) return showError(empForm, 'Укажите фамилию и имя');
        if (!body.post) return showError(empForm, 'Укажите должность');
        if (!body.telephone) return showError(empForm, 'Укажите телефон: 12 цифр вместе с кодом +375');
        if (!body.org_role) return showError(empForm, 'Выберите роль');
        if (!editingId) {
            const pwd = readPassword(empForm);
            if (pwd.error) return showError(empForm, pwd.error);
            Object.assign(body, pwd);
        }
        setBusy(empSubmit, true);
        const url = editingId ? `/cabinet/employees/${editingId}` : '/cabinet/employees';
        request(url, body)
            .then((d) => {
                if (editingId) {
                    empModal._onClose = null;
                    empModal.classList.remove('active');
                    reloadOnTab();
                    return;
                }
                empModal.classList.remove('active');
                showCredentials('Учётная запись создана', d.employee.full_name, d.credentials);
            })
            .catch((err) => showError(empForm, err.message))
            .finally(() => setBusy(empSubmit, false));
    });

    const pwdModal = document.getElementById('cabinetPasswordModal');
    const pwdForm = document.getElementById('cabinetPasswordForm');
    const resetPwdForm = bindPasswordMode(pwdForm);
    let passwordFor = null;
    function openPasswordModal(member) {
        passwordFor = member;
        resetPwdForm();
        showError(pwdForm, '');
        document.getElementById('cabinetPasswordWho').textContent =
            `${member.full_name || member.login} (${member.login}). Старый пароль перестанет действовать сразу.`;
        openModal(pwdModal);
    }
    pwdForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const pwd = readPassword(pwdForm);
        if (pwd.error) return showError(pwdForm, pwd.error);
        const submit = pwdForm.querySelector('button[type="submit"]');
        setBusy(submit, true);
        request(`/cabinet/employees/${passwordFor.id}/password`, pwd)
            .then((d) => {
                pwdModal.classList.remove('active');
                showCredentials('Новый пароль', passwordFor.full_name || passwordFor.login, d.credentials);
            })
            .catch((err) => showError(pwdForm, err.message))
            .finally(() => setBusy(submit, false));
    });

    const confirmModal = document.getElementById('cabinetConfirmModal');
    const confirmYes = document.getElementById('cabinetConfirmYes');
    function confirmAction({ title, text, yes, danger }) {
        return new Promise((resolve) => {
            document.getElementById('cabinetConfirmTitle').textContent = title;
            document.getElementById('cabinetConfirmText').textContent = text;
            confirmYes.querySelector('.btn-text').textContent = yes;
            confirmYes.classList.toggle('red', !!danger);
            confirmYes.classList.toggle('cabinet-confirm-primary', !danger);
            let done = false;
            const finish = (value) => {
                if (done) return;
                done = true;
                confirmYes.removeEventListener('click', onYes);
                resolve(value);
            };
            const onYes = () => {
                confirmModal._onClose = null;
                confirmModal.classList.remove('active');
                finish(true);
            };
            confirmYes.addEventListener('click', onYes);
            confirmModal._onClose = () => finish(false);
            openModal(confirmModal);
        });
    }

    const ACTIONS = {
        edit: (m) => openEmployeeModal(m),
        password: (m) => openPasswordModal(m),
        deactivate: (m) => confirmAction({
            title: 'Деактивировать учётную запись?',
            text: `${m.full_name || m.login} больше не сможет войти. Планы, подписи и история сохранятся. Учётную запись можно будет активировать снова.`,
            yes: 'Деактивировать',
            danger: true,
        }).then((ok) => ok && request(`/cabinet/employees/${m.id}/status`, { active: false }).then(reloadOnTab)),
        activate: (m) => confirmAction({
            title: 'Активировать учётную запись?',
            text: `${m.full_name || m.login} снова сможет войти со своим логином и паролем.`,
            yes: 'Активировать',
        }).then((ok) => ok && request(`/cabinet/employees/${m.id}/status`, { active: true }).then(reloadOnTab)),
        'owner-on': (m) => confirmAction({
            title: 'Назначить ответственным за кабинет?',
            text: `${m.full_name || m.login} сможет создавать и деактивировать учётные записи, сбрасывать пароли и назначать других ответственных.`,
            yes: 'Назначить',
        }).then((ok) => ok && request(`/cabinet/employees/${m.id}/owner`, { owner: true }).then(reloadOnTab)),
        'owner-off': (m) => {
            const self = String(m.id) === String(data.me);
            return confirmAction({
                title: 'Снять права ответственного?',
                text: self
                    ? 'Вы потеряете доступ к разделу «Сотрудники». Вернуть права сможет другой ответственный за кабинет.'
                    : `${m.full_name || m.login} больше не сможет управлять учётными записями сотрудников.`,
                yes: 'Снять права',
                danger: self,
            }).then((ok) => ok && request(`/cabinet/employees/${m.id}/owner`, { owner: false }).then((d) => {
                if (d.self_revoked) {
                    const url = new URL(window.location.href);
                    url.searchParams.set('profileTabs', 'org');
                    window.location.replace(url.toString());
                } else {
                    reloadOnTab();
                }
            }));
        },
    };

    function closeMenus(except) {
        document.querySelectorAll('.cabinet-menu.show').forEach((menu) => {
            if (menu === except) return;
            menu.classList.remove('show');
            menu.closest('.cabinet-row')?.classList.remove('menu-open');
            menu.parentElement.querySelector('[data-cabinet-menu]')?.setAttribute('aria-expanded', 'false');
        });
    }
    document.querySelectorAll('[data-cabinet-menu]').forEach((btn) => {
        const menu = btn.parentElement.querySelector('.cabinet-menu');
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = !menu.classList.contains('show');
            closeMenus(menu);
            menu.classList.toggle('show', open);
            btn.closest('.cabinet-row')?.classList.toggle('menu-open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    });
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.cabinet-menu')) closeMenus();
    });
    document.querySelectorAll('[data-cabinet-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
            closeMenus();
            const member = members.get(btn.closest('.cabinet-row').dataset.id);
            const action = ACTIONS[btn.dataset.cabinetAction];
            if (!member || !action) return;
            const result = action(member);
            if (result && typeof result.catch === 'function') result.catch((err) => notify(err.message, 'error'));
        });
    });
    document.querySelector('[data-cabinet-create]')?.addEventListener('click', () => openEmployeeModal(null));

    const filters = { role: '', status: '' };
    const rows = Array.from(document.querySelectorAll('.cabinet-row'));
    const emptyRow = document.querySelector('.cabinet-empty');
    function applyFilters() {
        let visible = 0;
        rows.forEach((row) => {
            const show = (!filters.role || row.dataset.role === filters.role)
                && (!filters.status || row.dataset.status === filters.status);
            row.hidden = !show;
            if (show) visible += 1;
        });
        emptyRow.hidden = visible > 0;
    }
    document.querySelectorAll('[data-cabinet-filter]').forEach((dd) => {
        const toggle = dd.querySelector('.dropdown-toggle');
        const label = dd.querySelector('.selected-option');
        const items = Array.from(dd.querySelectorAll('.dropdown-item'));
        const close = () => {
            dd.classList.remove('active');
            toggle.setAttribute('aria-expanded', 'false');
        };
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = !dd.classList.contains('active');
            document.querySelectorAll('[data-cabinet-filter].active').forEach((o) => o.classList.remove('active'));
            dd.classList.toggle('active', open);
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        items.forEach((item) => {
            item.tabIndex = 0;
            const pick = () => {
                filters[dd.dataset.cabinetFilter] = item.dataset.value;
                items.forEach((i) => i.classList.toggle('is-selected', i === item));
                label.textContent = item.dataset.value ? item.textContent.trim() : label.dataset.placeholder;
                dd.classList.toggle('has-value', !!item.dataset.value);
                close();
                applyFilters();
            };
            item.addEventListener('click', (e) => { e.stopPropagation(); pick(); });
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); toggle.focus(); }
            });
        });
        document.addEventListener('click', close);
    });

    const deptForm = document.getElementById('cabinetDepartmentAdd');
    if (deptForm) {
        const input = deptForm.querySelector('input[name="name"]');
        const submit = deptForm.querySelector('button[type="submit"]');
        input.addEventListener('input', () => { submit.disabled = !input.value.trim(); });
        deptForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = input.value.trim();
            if (!name) return;
            setBusy(submit, true);
            request('/cabinet/departments', { name })
                .then(reloadOnTab)
                .catch((err) => { notify(err.message, 'error'); setBusy(submit, false); });
        });
    }

    document.querySelectorAll('.cabinet-department').forEach((li) => {
        const id = li.dataset.id;
        const nameEl = li.querySelector('.cabinet-department-name');
        li.querySelector('[data-department-rename]')?.addEventListener('click', () => {
            if (li.classList.contains('is-editing')) return;
            const original = nameEl.textContent;
            li.classList.add('is-editing');
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'app-input cabinet-department-input';
            input.maxLength = 255;
            input.value = original;
            nameEl.replaceWith(input);
            input.focus();
            input.select();
            let finished = false;
            const restore = () => {
                input.replaceWith(nameEl);
                li.classList.remove('is-editing');
            };
            const save = () => {
                if (finished) return;
                finished = true;
                const value = input.value.trim();
                if (!value || value === original) return restore();
                request(`/cabinet/departments/${id}`, { name: value })
                    .then(reloadOnTab)
                    .catch((err) => { notify(err.message, 'error'); restore(); });
            };
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); save(); }
                if (e.key === 'Escape') { e.stopPropagation(); finished = true; restore(); }
            });
            input.addEventListener('blur', save);
        });
        li.querySelector('[data-department-delete]')?.addEventListener('click', () => {
            confirmAction({
                title: 'Удалить подразделение?',
                text: `«${nameEl.textContent}» исчезнет из справочника.`,
                yes: 'Удалить',
                danger: true,
            }).then((ok) => ok && request(`/cabinet/departments/${id}/delete`).then(reloadOnTab))
                .catch((err) => notify(err.message, 'error'));
        });
    });
})();
