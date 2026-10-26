// toggle password
const togglePassword = {
  init: function() {
    document.querySelectorAll('.toggle-password').forEach(button => {
      button.addEventListener('click', function() {
        const passwordInput = this.closest('.password-input-wrapper').querySelector('input');
        const eyeVisible = this.querySelector('.eye-visible');
        const eyeHidden = this.querySelector('.eye-hidden');
        
        if (passwordInput.type === 'password') {
          passwordInput.type = 'text';
          eyeVisible.style.display = 'none';
          eyeHidden.style.display = 'block';
          this.setAttribute('aria-label', 'Скрыть пароль');
        } else {
          passwordInput.type = 'password';
          eyeVisible.style.display = 'block';
          eyeHidden.style.display = 'none';
          this.setAttribute('aria-label', 'Показать пароль');
        }
      });
    });
  }
};

// messageFlash теперь общий модуль из common-models (один источник для
// enPlans и erespondentN, чтобы не расходиться) — см.
// common_models/static_assets/js/message-flash.js, подключается в
// base.html отдельным <script> перед этим файлом.

// notif modal show
const NotificationPopup = {
    init: function (options) {
        this.button = document.querySelector(options.button);
        this.popup = document.querySelector(options.popup);

        if (!this.button || !this.popup) {
            console.error("NotificationPopup: элемент(ы) не найдены");
            return;
        }

        this.bindEvents();
    },

    bindEvents: function () {
        this.button.addEventListener("click", (e) => {
            e.stopPropagation();
            this.toggle();
        });

        document.addEventListener("click", (e) => {
            if (!this.popup.contains(e.target) && !this.button.contains(e.target)) {
                this.hide();
            }
        });
    },

    toggle: function () {
        this.popup.classList.toggle("show");
        // Каждое открытие подтягивает свежий первый экран уведомлений —
        // иначе бейдж и список могли разойтись, если что-то пришло, пока
        // попап был закрыт (а фоновое обновление раз в минуту теперь
        // трогает только сам бейдж, не список — см. Notifications.refreshBadge).
        if (this.popup.classList.contains("show") && typeof Notifications !== 'undefined') {
            Notifications.load();
        }
    },

    hide: function () {
        this.popup.classList.remove("show");
    },

    show: function () {
        this.popup.classList.add("show");
    }
};


const Notifications = {
    notifListEl: null,
    notifCountEl: null,
    markAllBtn: null,
    loadMoreBtn: null,
    page: 1,
    perPage: 3,
    hasMore: true,
    isLoading: false,
    unreadTotal: 0,
    allNotifications: [],
    initialized: false,

    // Полная (пере)загрузка первой страницы — при первом заходе на
    // страницу и при каждом открытии попапа. Список действительно
    // перерисовывается целиком, но это ожидаемо: пользователь ещё не
    // успел никуда прокрутить только что открытый попап.
    async load() {
        if (this.isLoading) return;
        this.isLoading = true;
        this.page = 1;
        this.hasMore = true;

        try {
            const response = await fetch(`/api/notifications?page=1&per_page=${this.perPage}`);
            const data = await response.json();

            this.allNotifications = data.notifications;
            this.hasMore = data.has_next;
            this.renderAll(this.allNotifications);
            this.updateCounter(data.unread_total);
            this.updateLoadMoreVisibility();
        } catch (err) {
            console.error("Ошибка загрузки уведомлений:", err);
        } finally {
            this.isLoading = false;
        }
    },

    // Дозагрузка "предыдущих" — дописывает новые карточки в конец списка,
    // не трогая уже отрисованные, чтобы не сбрасывать прокрутку попапа
    // (раньше весь список каждый раз перерисовывался заново, и попап
    // всегда прыгал наверх — из-за этого дозагрузка и выглядела странно).
    async loadMore() {
        if (this.isLoading || !this.hasMore) return;
        this.isLoading = true;
        this.setLoadMoreState('loading');
        const nextPage = this.page + 1;

        try {
            const response = await fetch(`/api/notifications?page=${nextPage}&per_page=${this.perPage}`);
            const data = await response.json();

            this.page = nextPage;
            this.hasMore = data.has_next;
            this.allNotifications = [...this.allNotifications, ...data.notifications];
            this.appendNotifications(data.notifications);
            this.updateCounter(data.unread_total);
        } catch (err) {
            console.error("Ошибка загрузки уведомлений:", err);
        } finally {
            this.isLoading = false;
            this.updateLoadMoreVisibility();
        }
    },

    // Лёгкое периодическое обновление (раз в минуту) — только счётчик на
    // колокольчике. Раньше сюда вызывался полный init(), который заново
    // сбрасывал список на первую страницу и навешивал ещё один обработчик
    // на кнопку "Отметить все" при каждом тике — если попап был открыт,
    // его содержимое каждую минуту дёргалось и терялась прокрутка.
    async refreshBadge() {
        try {
            const response = await fetch(`/api/notifications?page=1&per_page=1`);
            const data = await response.json();
            this.updateCounter(data.unread_total);
        } catch (err) {
            console.error("Ошибка обновления счётчика уведомлений:", err);
        }
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    buildNotifNode(n) {
        const notif = document.createElement("div");
        notif.classList.add("notif");
        notif.dataset.id = n.id;
        if (!n.is_read) {
            notif.classList.add("unread");
        }

        const formattedTime = this.formatNotificationTime(n.created_at);

        notif.innerHTML = `
            <div class="notif-message">${this.escapeHtml(n.message)}</div>
            <div class="notif-time">${formattedTime}</div>
        `;

        notif.addEventListener('click', () => {
            if (!n.is_read) {
                this.markAsRead(n.id);
            }
        });

        return notif;
    },

    renderAll(data) {
        this.notifListEl.innerHTML = "";

        if (!data || data.length === 0) {
            this.notifListEl.innerHTML = `
                <div class='empty-state'>
                    <h1>Нет уведомлений</h1>
                </div>
            `;
            return;
        }

        const fragment = document.createDocumentFragment();
        data.forEach(n => fragment.appendChild(this.buildNotifNode(n)));
        this.notifListEl.appendChild(fragment);
    },

    appendNotifications(items) {
        if (!items || items.length === 0) return;

        const fragment = document.createDocumentFragment();
        items.forEach(n => fragment.appendChild(this.buildNotifNode(n)));
        this.notifListEl.appendChild(fragment);
    },

    formatNotificationTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMin = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMin < 1) {
            return 'Только что';
        } else if (diffMin < 60) {
            return `${diffMin} мин. назад`;
        } else if (diffHours < 24) {
            return `${diffHours} ч. назад`;
        } else if (diffDays < 7) {
            return `${diffDays} дн. назад`;
        } else {
            const options = { 
                day: '2-digit', 
                month: '2-digit', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            };
            return date.toLocaleDateString('ru-RU', options);
        }
    },

    // Точечно обновляет только сам кликнутый элемент (снимает "unread"),
    // а не перерисовывает весь список — иначе прокрутка попапа сбрасывалась
    // в начало при каждом клике по уведомлению.
    async markAsRead(notificationId) {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute("content");

            const response = await fetch(`/api/notifications/mark-read/${notificationId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                }
            });

            if (response.ok) {
                const notification = this.allNotifications.find(n => n.id === notificationId);
                if (notification) notification.is_read = true;

                const node = this.notifListEl.querySelector(`.notif[data-id="${notificationId}"]`);
                if (node) node.classList.remove('unread');

                this.updateCounter(Math.max(0, this.unreadTotal - 1));
            }
        } catch (err) {
            console.error("Ошибка при отметке уведомления:", err);
        }
    },

    ensureLoadMoreButton() {
        if (this.loadMoreBtn) return;
        this.loadMoreBtn = document.createElement("button");
        this.loadMoreBtn.type = "button";
        this.loadMoreBtn.className = "load-more-notifications";
        this.loadMoreBtn.textContent = "Загрузить предыдущие";
        this.loadMoreBtn.addEventListener("click", () => this.loadMore());
        this.notifListEl.parentNode.appendChild(this.loadMoreBtn);
    },

    // Вызывается уже ПОСЛЕ завершения загрузки (успешной или нет) — всегда
    // возвращает кнопку в обычное (не "загрузка") состояние и просто
    // показывает/прячет её по факту наличия следующей страницы.
    updateLoadMoreVisibility() {
        this.ensureLoadMoreButton();
        this.setLoadMoreState('idle');
        this.loadMoreBtn.style.display = this.hasMore ? "flex" : "none";
    },

    setLoadMoreState(state) {
        this.ensureLoadMoreButton();
        const isLoading = state === 'loading';
        this.loadMoreBtn.disabled = isLoading;
        this.loadMoreBtn.classList.toggle('is-loading', isLoading);
        this.loadMoreBtn.textContent = isLoading ? "Загрузка…" : "Загрузить предыдущие";
    },

    updateCounter(count) {
        this.unreadTotal = count;
        if (count > 0) {
            this.notifCountEl.innerText = count > 99 ? '99+' : count;
            this.notifCountEl.style.display = "flex";
            this.notifCountEl.classList.add("active");
        } else {
            this.notifCountEl.classList.remove("active");
            this.notifCountEl.style.display = "none";
            this.notifCountEl.innerText = "";
        }
    },

    // Снимает "unread" только с уже отрисованных карточек — не трогает
    // остальной список (см. комментарий у markAsRead).
    async markAllRead() {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute("content");

            const response = await fetch("/api/notifications/mark-all-read", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                }
            });

            if (!response.ok) throw new Error("Ошибка запроса");

            this.allNotifications.forEach(n => n.is_read = true);
            this.notifListEl.querySelectorAll('.notif.unread').forEach(el => el.classList.remove('unread'));
            this.updateCounter(0);

        } catch (err) {
            console.error("Ошибка при отметке уведомлений:", err);
        }
    },

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.notifListEl = document.getElementById("notifList");
        this.notifCountEl = document.getElementById("notifCount");
        this.markAllBtn = document.getElementById("markAllRead");

        if (this.markAllBtn) {
            this.markAllBtn.addEventListener("click", () => this.markAllRead());
        }

        this.load();
    }
};

// activation code
const activationCode = {
  init: function() {
    const inputs = document.querySelectorAll('.activation_code_input');
        inputs.forEach((input, index) => {
            input.addEventListener('input', () => {
                if (input.value && index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }
                else if (!input.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });
    
            input.addEventListener('keydown', (e) => {
                if (e.key === "Backspace" && index > 0 && !input.value) {
                    inputs[index - 1].focus();
                }
            });
        });
    
        inputs[0].addEventListener('paste', (e) => {
            e.preventDefault();
            const pasteData = e.clipboardData.getData('text');
        
            pasteData.split('').forEach((char, i) => {
                if (i < inputs.length) {
                    inputs[i].value = char;
                }
            });

            inputs[Math.min(pasteData.length - 1, inputs.length - 1)].focus();
        });
  }
};

// resend cod
class CodeVerificationTimer {
    constructor(options = {}) {
        this.resendBtn = document.getElementById(options.resendBtnId || 'resend-code-btn');
        this.resendForm = document.getElementById(options.resendFormId || 'resend-form');
        this.countdownElement = document.getElementById(options.countdownElementId || 'countdown');
        this.countdownDuration = options.duration || 60;
        this.countdown = this.countdownDuration;
        this.timer = null;
        
        this.init();
    }
    
    init() {
        if (!this.resendBtn || !this.resendForm || !this.countdownElement) {
            console.error('Required elements not found');
            return;
        }
        
        this.setupEventListeners();
        this.startCountdown();
    }
    
    getSavedCountdown() {
        const savedEndTime = localStorage.getItem('codeResendEndTime');
        if (savedEndTime) {
            const now = Date.now();
            const endTime = parseInt(savedEndTime);
            const remaining = Math.max(0, Math.ceil((endTime - now) / 1000));
            
            if (remaining > 0) {
                return remaining;
            } else {
                localStorage.removeItem('codeResendEndTime');
            }
        }
        return this.countdownDuration;
    }
    
    saveCountdownEndTime() {
        const endTime = Date.now() + (this.countdown * 1000);
        localStorage.setItem('codeResendEndTime', endTime.toString());
    }
    
    startCountdown() {
        this.countdown = this.getSavedCountdown();
        
        this.resendBtn.classList.add('disabled');
        this.resendBtn.style.cursor = 'not-allowed';
        this.resendBtn.style.opacity = '0.5';
        
        this.countdownElement.textContent = this.countdown;
        
        if (this.countdown <= 0) {
            this.activateButton();
            return;
        }
        
        this.saveCountdownEndTime();
        
        this.timer = setInterval(() => {
            this.countdown--;
            this.countdownElement.textContent = this.countdown;
            
            if (this.countdown <= 0) {
                this.clearTimer();
                this.activateButton();
                localStorage.removeItem('codeResendEndTime');
            } else {
                this.saveCountdownEndTime();
            }
        }, 1000);
    }
    
    activateButton() {
        this.resendBtn.classList.remove('disabled');
        this.resendBtn.style.cursor = 'pointer';
        this.resendBtn.style.opacity = '1';
        this.countdownElement.textContent = '';
    }
    
    clearTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }
    
    resetCountdown() {
        this.clearTimer();
        this.countdown = this.countdownDuration;
        localStorage.removeItem('codeResendEndTime');
        this.startCountdown();
    }
    
    setupCodeInputs() {
        const inputs = document.querySelectorAll('.activation_code_input');
        inputs.forEach((input, index) => {
            input.addEventListener('input', () => {
                if (input.value.length === 1 && index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }
            });
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && input.value.length === 0 && index > 0) {
                    inputs[index - 1].focus();
                }
            });
        });
    }
    
    setupEventListeners() {
        this.resendForm.addEventListener('submit', (e) => {
            if (this.resendBtn.classList.contains('disabled')) {
                e.preventDefault();
                return;
            }
        });
        
        this.setupCodeInputs();
        
        const mainForm = document.querySelector('.auth-form');
        if (mainForm) {
            mainForm.addEventListener('submit', () => {
                localStorage.removeItem('codeResendEndTime');
            });
        }
    }
    
    destroy() {
        this.clearTimer();
        localStorage.removeItem('codeResendEndTime');
        
        this.resendForm.removeEventListener('submit', this.handleResendSubmit);
        
        this.resendBtn.classList.remove('disabled');
        this.resendBtn.style.cursor = 'pointer';
        this.resendBtn.style.opacity = '1';
        this.countdownElement.textContent = '';
    }
    
    getRemainingTime() {
        return this.countdown;
    }
    
    isActive() {
        return this.timer !== null;
    }
}

class CodeVerificationManager {
    constructor() {
        this.instances = new Map();
    }
    
    createInstance(containerId, options = {}) {
        const defaultOptions = {
            resendBtnId: 'resend-code-btn',
            resendFormId: 'resend-form', 
            countdownElementId: 'countdown',
            duration: 60,
            ...options
        };
        
        const instance = new CodeVerificationTimer(defaultOptions);
        this.instances.set(containerId, instance);
        return instance;
    }
    
    getInstance(containerId) {
        return this.instances.get(containerId);
    }
    
    destroyInstance(containerId) {
        const instance = this.instances.get(containerId);
        if (instance) {
            instance.destroy();
            this.instances.delete(containerId);
        }
    }
    
    destroyAll() {
        this.instances.forEach(instance => instance.destroy());
        this.instances.clear();
    }
}

function createCodeVerification(options = {}) {
    return new CodeVerificationTimer(options);
}

// steps in forms
const formSteps = {
  init: function () {
    const step1 = document.querySelector('.auth-step-1');
    const step2 = document.querySelector('.auth-step-2');
    const nextBtn = document.getElementById('next-btn');
    const prevBtn = document.getElementById('prev-btn');
    const requiredFields = ['#name', '#secondname', '#telephone'];

    if (!step1 || !step2 || !nextBtn) return;

    function checkFields() {
      return requiredFields.every(field => {
        const input = document.querySelector(field);
        return input && input.value.trim() !== '';
      });
    }

    function updateNextButtonState() {
      nextBtn.disabled = !checkFields();
    
      if (nextBtn.disabled) {
        nextBtn.classList.add('disabled');
      } else {
        nextBtn.classList.remove('disabled');
      }
    }

    requiredFields.forEach(field => {
      const input = document.querySelector(field);
      if (input) {
        input.addEventListener('input', updateNextButtonState);
        input.addEventListener('change', updateNextButtonState);
        input.addEventListener('paste', updateNextButtonState);
        input.addEventListener('cut', updateNextButtonState);
      }
    });

    updateNextButtonState();

    nextBtn.addEventListener('click', (e) => {
      if (!checkFields()) {
        e.preventDefault();
        return;
      }
      step1.classList.remove('active');
      step2.classList.add('active');
    });

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        step2.classList.remove('active');
        step1.classList.add('active');
      });
    }
  }
};

// func to show modals
function handleModal(modalElement, openLink, closeLink) {
    openLink.addEventListener('click', function(event) {
        if (openLink.style.opacity === '0.5') {
            event.preventDefault();
        } else {
            modalElement.classList.add('active');
        }
    });

    closeLink.addEventListener('click', function() {
        modalElement.classList.remove('active');
    });
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
    
    // Отфильтровывает недопустимые символы, не трогая то, что пользователь
    // ещё не дописал (в отличие от прежней версии, которая на каждое
    // нажатие клавиши прогоняла значение через parseFloat/toFixed — из-за
    // этого набрать, например, "-3,3" посимвольно было невозможно: после
    // ввода запятой поле тут же откатывалось обратно к "-3,0"). Полное
    // округление/дополнение нулями по-прежнему происходит один раз, при
    // потере фокуса — см. handleBlur.
    sanitize: function(value, settings) {
        var allowedRegex = settings.allowNegative ? /[^\d,.-]/g : /[^\d,.]/g;
        var raw = value.replace(allowedRegex, '');

        var negative = false;
        if (settings.allowNegative) {
            negative = /-/.test(raw);
            raw = raw.replace(/-/g, '');
        }

        raw = raw.replace(/\./g, ',');
        var commaIndex = raw.indexOf(',');
        if (commaIndex !== -1) {
            var intPart = raw.slice(0, commaIndex);
            var fracPart = raw.slice(commaIndex + 1).replace(/,/g, '');
            raw = settings.decimalPlaces > 0
                ? intPart + ',' + fracPart.slice(0, settings.decimalPlaces)
                : intPart;
        }

        return (negative ? '-' : '') + raw;
    },

    handleInput: function(e, settings) {
        var input = e.target;
        var cursorPos = input.selectionStart;
        var oldValue = input.value;
        var newValue = NumericInputHandler.sanitize(oldValue, settings);

        if (newValue === oldValue) return;

        // курсор пересчитываем по тому, сколько допустимых символов
        // осталось перед прежней позицией курсора — так он не «убегает»
        // при удалении лишних символов
        var newCursorPos = NumericInputHandler.sanitize(oldValue.slice(0, cursorPos), settings).length;

        input.value = newValue;
        input.setSelectionRange(newCursorPos, newCursorPos);
    },

    handleFocus: function(e, settings) {
        var input = e.target;
        if (input.value === '' || input.value === '-') {
            input.value = settings.defaultValue;
        }
        // Всегда выделяем значение целиком: раньше для полей без
        // allowNegative курсор просто ставился перед запятой, не трогая
        // остальное — из-за этого печатание нового числа в поле со
        // значением "0,0" вставляло цифры ПЕРЕД этим нулём вместо замены
        // (например, набор "34,5" превращался в "345,0"). select() этого
        // не делает: первое же нажатие клавиши заменяет всё значение.
        input.select();
    },

    handleBlur: function(e, settings) {
        var input = e.target;
        if (input.value === '' || input.value === '-' || input.value === null) {
            input.value = settings.defaultValue;
        } else {
            var valueWithDot = input.value.replace(',', '.');
            var num = parseFloat(valueWithDot);
            if (!isNaN(num)) {
                // Только отрицательное число либо 0 — положительное вводить
                // нельзя (см. "целевой показатель энергосбережения"). Раньше
                // такое значение молча обнулялось; теперь показываем ошибку,
                // чтобы пользователь понимал, почему поле не сохранило то,
                // что он ввёл.
                if (settings.negativeOnly && num > 0) {
                    if (typeof messageFlash !== 'undefined') {
                        messageFlash.addMessage(
                            settings.negativeOnlyMessage || 'Значение должно быть отрицательным числом или 0',
                            'error'
                        );
                    }
                    num = 0;
                }
                var formatted = num.toFixed(settings.decimalPlaces);
                input.value = formatted.replace('.', ',');
            } else {
                input.value = settings.defaultValue;
            }
        }
    }
};


NumericInputHandler.init('.app-numeric-input', {
    allowNegative: false,
    decimalPlaces: 2,
    defaultValue: '0,00'
});


NumericInputHandler.init('.app-numeric-input-coeff', {
    allowNegative: false,
    decimalPlaces: 3,
    defaultValue: '0,000'
});

NumericInputHandler.init('.app-numeric-input-negative', {
    allowNegative: true,
    decimalPlaces: 2,
    defaultValue: '0,00'
});

NumericInputHandler.init('.app-numeric-input-one-decimal', {
    allowNegative: false,
    decimalPlaces: 1,
    defaultValue: '0,0'
});

// Используется только для "Целевой показатель энергосбережения" — по
// смыслу это цель СНИЖЕНИЯ потребления, поэтому допускается только
// отрицательное число или 0,0, положительное — нет.
NumericInputHandler.init('.app-numeric-input-negative-one-decimal', {
    allowNegative: true,
    negativeOnly: true,
    decimalPlaces: 1,
    defaultValue: '0,0',
    negativeOnlyMessage: 'Целевой показатель энергосбережения должен быть отрицательным числом или 0 — это цель снижения потребления'
});

NumericInputHandler.init('.app-numeric-input-integer', {
    allowNegative: false,
    decimalPlaces: 0,
    defaultValue: '0'
});

class DirectionsTable {
    constructor({ searchSelector, tableSelector, hiddenInputSelector, nextButtonSelector }) {
        this.searchInput = document.querySelector(`[data-action="${searchSelector}"]`);
        this.table = document.querySelector(`[data-action="${tableSelector}"]`);
        this.tbody = this.table ? this.table.querySelector('tbody') : null;
        this.hiddenInput = document.querySelector(`[data-action="${hiddenInputSelector}"]`);
        this.nextButton = document.querySelector(`[data-action="${nextButtonSelector}"]`);
        this.selectedId = null;

        if (!this.searchInput || !this.tbody) return;

        this.noInfoRow = this.createNoInfoRow();
        this.tbody.appendChild(this.noInfoRow);
        this.noInfoRow.style.display = "none";

        this.sortColumn = null;
        this.sortDirection = "asc";

        this.initSearch();
        this.initSelection();
        this.initSort();

        if (this.nextButton) {
            this.nextButton.disabled = true;
        }
    }

    // Тот же .empty-state, что и везде в приложении (уведомления,
    // список планов и т.д.) — вместо самодельной серой иконки с текстом,
    // чтобы пустое состояние поиска выглядело частью общего стиля.
    createNoInfoRow() {
        const noResultsRow = document.createElement("tr");
        noResultsRow.className = "no-results-row";

        const cell = document.createElement("td");
        cell.colSpan = this.table.querySelectorAll("thead th").length || 5;

        cell.innerHTML = `
            <div class="empty-state table-empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="10" cy="10" r="6.5"/>
                    <path d="M19 19l-4.35-4.35"/>
                </svg>
                <h1>Ничего не найдено</h1>
                <p>Попробуйте изменить запрос — код или наименование</p>
            </div>
        `;

        noResultsRow.appendChild(cell);
        return noResultsRow;
    }

    initSearch() {
        this.searchInput.addEventListener("input", () => {
            const filter = this.searchInput.value.toLowerCase();
            const rows = this.tbody.querySelectorAll("tr:not(.no-results-row)");
            let visibleCount = 0;

            rows.forEach(row => {
                const code = row.cells[1]?.textContent.toLowerCase() || "";
                const name = row.cells[2]?.textContent.toLowerCase() || "";
                const isVisible = code.includes(filter) || name.includes(filter);
                
                row.style.display = isVisible ? "" : "none";
                if (isVisible) visibleCount++;
            });

            if (visibleCount === 0 && filter !== "") {
                this.noInfoRow.style.display = "";
            } else {
                this.noInfoRow.style.display = "none";
            }
        });
    }

    initSelection() {
        this.tbody.addEventListener("click", (e) => {
            const row = e.target.closest("tr");
            if (!row || row.classList.contains("no-results-row")) return;

            this.tbody.querySelectorAll("tr").forEach(r => r.classList.remove("selected"));
            row.classList.add("selected");

            this.selectedId = row.cells[0].textContent.trim();

            if (this.hiddenInput) {
                this.hiddenInput.value = this.selectedId;
            }
            if (this.nextButton) {
                this.nextButton.disabled = false;
            }
        });
    }

    // Клик по заголовку столбца сортирует строки по нему (повторный клик
    // меняет направление). Строки уже все в DOM (без пагинации), поэтому
    // просто переставляем существующие <tr> — так не теряются обработчики
    // событий и текущая видимость строк (после поиска).
    initSort() {
        const headerRow = this.table.querySelector("thead tr");
        if (!headerRow) return;

        const sortIconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6-6 6 6"/></svg>`;

        Array.from(headerRow.children).forEach((th, index) => {
            if (th.style.display === "none") return;

            const indicator = document.createElement("span");
            indicator.className = "sort-indicator";
            indicator.innerHTML = sortIconSvg;
            th.appendChild(indicator);

            th.addEventListener("click", () => this.sortByColumn(index, th, headerRow));
        });
    }

    sortByColumn(index, th, headerRow) {
        const rows = Array.from(this.tbody.querySelectorAll("tr")).filter(
            (row) => row !== this.noInfoRow
        );
        const isCheckboxColumn = rows.some((row) => row.cells[index]?.querySelector('input[type="checkbox"]'));

        let direction;
        if (this.sortColumn === index) {
            direction = this.sortDirection === "asc" ? "desc" : "asc";
        } else {
            // для чекбокс-столбцов первый клик сразу показывает отмеченные
            // сверху — иначе на столбцах, где отмечено почти всё (как
            // "Эко."), сортировка "по возрастанию" визуально ничего не
            // меняет и кажется нерабочей
            direction = isCheckboxColumn ? "desc" : "asc";
        }
        this.sortColumn = index;
        this.sortDirection = direction;

        Array.from(headerRow.children).forEach((h) => h.classList.remove("sort-active", "sort-desc"));
        th.classList.add("sort-active");
        if (direction === "desc") th.classList.add("sort-desc");

        rows.sort((rowA, rowB) => {
            const valueA = this.getCellSortValue(rowA.cells[index]);
            const valueB = this.getCellSortValue(rowB.cells[index]);

            let result;
            if (typeof valueA === "number" && typeof valueB === "number") {
                result = valueA - valueB;
            } else {
                result = String(valueA).localeCompare(String(valueB), "ru", { numeric: true });
            }
            return direction === "asc" ? result : -result;
        });

        rows.forEach((row) => this.tbody.appendChild(row));
        this.tbody.appendChild(this.noInfoRow);

        const container = this.table.closest(".modal-table-conteiner");
        if (container) container.scrollTop = 0;
    }

    getCellSortValue(cell) {
        if (!cell) return "";

        const checkbox = cell.querySelector('input[type="checkbox"]');
        if (checkbox) return checkbox.checked ? 1 : 0;

        const text = cell.textContent.trim();
        if (/^-?\d+([.,]\d+)?$/.test(text)) {
            return parseFloat(text.replace(",", "."));
        }
        return text.toLowerCase();
    }
}

class MultiTypeSearchManager {
    constructor(config = {}) {
        this.config = {
            searchInputSelector: 'input[data-action="search-organization"]',
            tableBodySelector: 'table[data-action="organization-table"] tbody',
            selectedOrgInputSelector: 'input[data-action="selected-org"]',
            selectedItemTypeInputSelector: 'input[data-action="selected-item-type"]',
            submitButtonSelector: 'button[data-action="submit"]',
            typeButtonsSelector: '[data-action="select-type"]',
            paginationAreaSelector: '#paginationArea',
            prevPageBtnSelector: '#prevPageBtn',
            nextPageBtnSelector: '#nextPageBtn',
            currentPageSelector: '#currentPage',
            totalPagesSelector: '#totalPages',
            clearSearchSelector: 'button[data-action="clear-search"]',
            
            organizationsApiUrl: '/api/organizations',
            
            itemsPerPage: 10,
            debounceTime: 300,
            ...config
        };

        this.currentPage = 1;
        this.totalPages = 1;
        this.totalItems = 0;
        this.currentQuery = '';
        this.selectedItemType = 'organization';
        this.selectedItemId = null;
        this.init();
    }

    init() {
        this.searchInput = document.querySelector(this.config.searchInputSelector);
        this.tableBody = document.querySelector(this.config.tableBodySelector);
        this.selectedOrgInput = document.querySelector(this.config.selectedOrgInputSelector);
        this.selectedItemTypeInput = document.querySelector(this.config.selectedItemTypeInputSelector);
        this.submitButton = document.querySelector(this.config.submitButtonSelector);
        this.typeButtons = document.querySelectorAll(this.config.typeButtonsSelector);
        this.paginationArea = document.querySelector(this.config.paginationAreaSelector);
        this.prevPageBtn = document.querySelector(this.config.prevPageBtnSelector);
        this.nextPageBtn = document.querySelector(this.config.nextPageBtnSelector);
        this.currentPageSpan = document.querySelector(this.config.currentPageSelector);
        this.totalPagesSpan = document.querySelector(this.config.totalPagesSelector);
        this.clearSearchButton = document.querySelector(this.config.clearSearchSelector);

        this.bindEvents();
        this.updateSubmitButtonState();
        this.loadData();
        this.hideTypeButtons();
    }

    bindEvents() {
        let debounceTimer;

        this.searchInput.addEventListener('input', (e) => {
            if (this.clearSearchButton) {
                this.clearSearchButton.style.display = e.target.value ? 'block' : 'none';
            }
            
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();
            debounceTimer = setTimeout(() => {
                this.currentPage = 1;
                this.currentQuery = query;
                this.loadData();
            }, this.config.debounceTime);
        });

        if (this.clearSearchButton) {
            this.clearSearchButton.addEventListener('click', () => {
                this.searchInput.value = '';
                this.clearSearchButton.style.display = 'none';
                this.currentPage = 1;
                this.currentQuery = '';
                this.loadData();
            });
        }

        this.tableBody.addEventListener('click', (e) => {
            const row = e.target.closest('tr');
            if (row && row.dataset.id) {
                this.selectItem(row);
            }
        });

        if (this.prevPageBtn) {
            this.prevPageBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.loadData();
                }
            });
        }

        if (this.nextPageBtn) {
            this.nextPageBtn.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.loadData();
                }
            });
        }

        const form = this.selectedOrgInput.closest('form');
        if (form) {
            form.addEventListener('submit', (e) => {
                if (!this.selectedItemId) {
                    e.preventDefault();
                    return;
                }
                
                this.selectedOrgInput.value = this.selectedItemId;
                if (this.selectedItemTypeInput) {
                    this.selectedItemTypeInput.value = this.selectedItemType;
                }
            });
        }
    }

    async loadData() {
        try {
            this.showLoading();

            let apiUrl;
            
            switch(this.selectedItemType) {
                case 'organization':
                    apiUrl = this.config.organizationsApiUrl;
                    break;
                default:
                    apiUrl = this.config.organizationsApiUrl;
            }

            const url = `${apiUrl}?q=${encodeURIComponent(this.currentQuery)}&page=${this.currentPage}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            const items = this.extractItems(data, this.selectedItemType);
            this.totalPages = data.total_pages || 1;
            this.totalItems = data.total_items || 0;
            
            this.renderItems(items);
            this.updatePagination();
            
        } catch (error) {
            console.error('MultiTypeSearchManager: Ошибка загрузки данных:', error);
            this.showError(`Ошибка загрузки ${this.getTypeLabel(this.selectedItemType, true)}`);
        } finally {
            this.hideLoading();
        }
    }

    extractItems(data, type) {
        switch(type) {
            case 'organization':
                return data.organizations || [];
            default:
                return [];
        }
    }

    renderItems(items) {
        if (!items || items.length === 0) {
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; padding: 40px; color: #6b7280;">
                        <div style="font-size: 48px; margin-bottom: 16px;"></div>
                        <div>${this.currentQuery ? 'По вашему запросу ничего не найдено' : 'Нет данных для отображения'}</div>
                    </td>
                </tr>
            `;
            this.paginationArea.style.display = 'none';
            return;
        }

        this.tableBody.innerHTML = '';

        items.forEach(item => {
            const row = document.createElement('tr');
            row.dataset.id = item.id;
            row.dataset.type = this.selectedItemType;
            
            if (this.selectedItemId == item.id) {
                row.classList.add('selected');
            }
            
            let html = `<td style="display: none;">${this.escapeHtml(item.id)}</td>`;
            
            switch(this.selectedItemType) {
                case 'organization':
                    html += `
                        <td>${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;">${this.escapeHtml(item.ynp || '-')}</td>
                        <td style="text-align: center;">${this.escapeHtml(item.okpo || '-')}</td>
                    `;
                    break;
                default:
                    html += `
                        <td style="width: 100%;">${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;"></td>
                        <td style="text-align: center;"></td>
                    `;
            }
            
            row.innerHTML = html;
            this.tableBody.appendChild(row);
        });

        this.updateTableHeaders();
        this.paginationArea.style.display = this.totalPages > 1 ? 'block' : 'none';
    }

    updatePagination() {
        if (this.currentPageSpan) {
            this.currentPageSpan.textContent = this.currentPage;
        }
        
        if (this.totalPagesSpan) {
            this.totalPagesSpan.textContent = this.totalPages;
        }
        
        if (this.prevPageBtn) {
            this.prevPageBtn.disabled = this.currentPage === 1;
        }
        
        if (this.nextPageBtn) {
            this.nextPageBtn.disabled = this.currentPage === this.totalPages;
        }
    }

    updateTableHeaders() {
        const table = this.tableBody.closest('table');
        if (!table) return;
        
        const thead = table.querySelector('thead');
        if (!thead) return;
        
        let headersHTML = `
            <tr>
                <th style="display: none;">id</th>
        `;
        
        switch(this.selectedItemType) {
            case 'organization':
                headersHTML += `
                    <th>Наименование предприятия</th>
                    <th style="text-align: center;">УНП</th>
                    <th style="text-align: center;">ОКПО</th>
                `;
                break;
            // case 'higher_organization':
            //     headersHTML += `
            //         <th style="width: 100%;">Наименование вышестоящей организации</th>
            //         <th style="text-align: center;"></th>
            //         <th style="text-align: center;"></th>
            //     `;
            //     break;
            // case 'oblispolkom_gorispolkom':
            //     headersHTML += `
            //         <th style="width: 100%;">Наименование обл/горисполкома</th>
            //         <th style="text-align: center;"></th>
            //         <th style="text-align: center;"></th>
            //     `;
            //     break;
            // case 'region':
            //     headersHTML += `
            //         <th style="width: 100%;">Наименование региона</th>
            //         <th style="text-align: center;"></th>
            //         <th style="text-align: center;"></th>
            //     `;
            //     break;
        }
        
        headersHTML += `</tr>`;
        thead.innerHTML = headersHTML;
    }

    // selectItemType(type) {
    //     this.selectedItemType = type;
    //     this.selectedItemId = null;
    //     this.currentPage = 1;
    //     this.currentQuery = '';
        
    //     this.typeButtons.forEach(btn => {
    //         if (btn.dataset.type === type) {
    //             btn.classList.add('active');
    //         } else {
    //             btn.classList.remove('active');
    //         }
    //     });
        
    //     this.updateSearchPlaceholder(type);
    //     this.updateSubmitButtonText();
    //     this.updateModalTitle(type);
        
    //     if (this.searchInput) {
    //         this.searchInput.value = '';
    //         if (this.clearSearchButton) {
    //             this.clearSearchButton.style.display = 'none';
    //         }
    //     }
        
    //     this.updateSubmitButtonState(false);
    //     this.loadData();
    // }

    // updateSearchPlaceholder(type) {
    //     if (!this.searchInput) return;
        
    //     const placeholders = {
    //         'organization': 'Наименование/окпо/унп организации',
    //         'higher_organization': 'Наименование вышестоящей организации',
    //         'oblispolkom_gorispolkom': 'Наименование обл/горисполкома',
    //         'region': 'Наименование региона',
    //     };
        
    //     this.searchInput.placeholder = placeholders[type] || 'Поиск...';
        
    //     const searchLabel = document.getElementById('search-label');
    //     if (searchLabel) {
    //         const labels = {
    //             'organization': 'Поиск организации',
    //             'higher_organization': 'Поиск вышестоящей организации',
    //             'oblispolkom_gorispolkom': 'Поиск обл/горисполкома',
    //             'region': 'Поиск региона',
    //         };
    //         searchLabel.textContent = labels[type] || 'Поиск';
    //     }
    // }

    // updateSubmitButtonText() {
    //     if (!this.submitButton) return;
        
    //     const buttonTexts = {
    //         'organization': 'Сохранить организацию',
    //         'higher_organization': 'Сохранить вышестоящую организацию',
    //         'oblispolkom_gorispolkom': 'Сохранить обл/горисполком',
    //         'region': 'Сохранить регион',
    //     };
        
    //     const text = buttonTexts[this.selectedItemType] || 'Сохранить изменения';
        
    //     const btnTextSpan = this.submitButton.querySelector('.btn-text');
    //     if (btnTextSpan) {
    //         btnTextSpan.textContent = text;
    //     }
    // }

    // updateModalTitle(type) {
    //     const modalTitle = document.getElementById('modal-title');
    //     if (!modalTitle) return;
        
    //     const titles = {
    //         'organization': 'Выберите организацию',
    //         'higher_organization': 'Выберите вышестоящую организацию',
    //         'oblispolkom_gorispolkom': 'Выберите обл/горисполком',
    //         'region': 'Выберите регион',
    //     };
        
    //     modalTitle.textContent = titles[type] || 'Выберите элемент';
    // }

    // highlightActiveTypeButton() {
    //     this.typeButtons.forEach(btn => {
    //         if (btn.dataset.type === this.selectedItemType) {
    //             btn.classList.add('active');
    //         }
    //     });
    // }

    hideTypeButtons() {
        if (this.typeButtons.length > 0) {
            this.typeButtons.forEach(btn => {
                btn.style.display = 'none';
            });
        }
    }

    selectItem(row) {
        this.selectedItemId = row.dataset.id;
        
        this.selectedOrgInput.value = this.selectedItemId;
        if (this.selectedItemTypeInput) {
            this.selectedItemTypeInput.value = this.selectedItemType;
        }
        
        this.highlightSelectedRow(row);
        this.updateSubmitButtonState(true);
    }

    highlightSelectedRow(selectedRow) {
        this.tableBody.querySelectorAll('tr').forEach(row => {
            row.classList.remove('selected');
        });
        
        selectedRow.classList.add('selected');
    }

    updateSubmitButtonState(isActive = false) {
        if (!this.submitButton) return;
        
        if (isActive && this.selectedItemId) {
            this.submitButton.disabled = false;
            this.submitButton.classList.remove('disabled');
        } else {
            this.submitButton.disabled = true;
            this.submitButton.classList.add('disabled');
        }
    }

    getTypeLabel(type, plural = false) {
        const labels = {
            'organization': plural ? 'организаций' : 'организация',
            // 'higher_organization': plural ? 'вышестоящих организаций' : 'вышестоящая организация',
            // 'oblispolkom_gorispolkom': plural ? 'обл/горисполкомов' : 'обл/горисполком',
            // 'region': plural ? 'регионов' : 'регион',
        };
        return labels[type] || (plural ? 'данных' : 'данные');
    }

    showLoading() {
        this.tableBody.innerHTML = `
            <tr>
                <td colspan="3" style="text-align: center; padding: 60px;">
                    <div class="loading-spinner"></div>
                    <div style="margin-top: 16px;">Загрузка ${this.getTypeLabel(this.selectedItemType, true)}...</div>
                </td>
            </tr>
        `;
        
        this.paginationArea.style.display = 'none';
    }

    hideLoading() {}

    showError(message) {
        this.tableBody.innerHTML = `
            <tr>
                <td colspan="3" style="text-align: center; padding: 40px; color: #dc2626;">
                    <div style="font-weight: 500; margin-bottom: 8px;">Ошибка</div>
                    <div style="color: #6b7280; font-size: 14px;">${message}</div>
                </td>
            </tr>
        `;
        
        this.paginationArea.style.display = 'none';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

function initConfirmModal(config) {
    const triggerButtons = config.triggerButton ? 
                         document.querySelectorAll(config.triggerButton) : 
                         (config.triggerId ? [document.getElementById(config.triggerId)] : []);
    
    const formElement = config.formElement ||
                       (config.formId ? document.getElementById(config.formId) : null);
    
    const modalElement = config.modalId ? document.getElementById(config.modalId) : null;
    const yesButton = config.yesId ? document.getElementById(config.yesId) : null;
    const noButton = config.noId ? document.getElementById(config.noId) : null;
    const textElement = config.textId ? document.getElementById(config.textId) : null;
    const textElementSecond = config.textSecondId ? document.getElementById(config.textSecondId) : null;

    if (triggerButtons.length === 0 || !modalElement || !yesButton || !noButton) {
        console.error('Modal initialization error: required elements not found', config);
        return;
    }

    triggerButtons.forEach(triggerButton => {
        triggerButton.addEventListener('click', function (e) {
            e.preventDefault();
            const planId = this.getAttribute('data-plan-id');
            
            if (textElement && config.modalText) {
                let text = config.modalText;
                if (planId && text.includes('{id}')) {
                    text = text.replace('{id}', planId);
                }
                textElement.innerHTML = text;
            }
            
            if (textElementSecond && config.modalTextSecond) {
                textElementSecond.innerHTML = config.modalTextSecond;
            }   
            
            modalElement.classList.add('active');
            let currentForm = null;
            
            if (formElement) {
                currentForm = formElement;
            } else if (config.formSelector) {
                currentForm = document.querySelector(config.formSelector);
            } else {
                currentForm = this.closest('form');
            }
            modalElement._currentForm = currentForm;
        });
    });

    if (!yesButton.dataset.confirmModalBound) {
        yesButton.dataset.confirmModalBound = 'true';
        yesButton.addEventListener('click', function () {
            modalElement.classList.remove('active');
            if (modalElement._currentForm) {
                // requestSubmit() (в отличие от submit()) реально диспатчит
                // событие 'submit' — без этого любой addEventListener('submit', ...)
                // на форме (например AJAX-перехват в plan_audit.html) никогда
                // не сработает, и форма просто отправляется нативно с
                // перезагрузкой страницы.
                if (typeof modalElement._currentForm.requestSubmit === 'function') {
                    modalElement._currentForm.requestSubmit();
                } else {
                    modalElement._currentForm.submit();
                }
            }
        });
    }

    if (!noButton.dataset.confirmModalBound) {
        noButton.dataset.confirmModalBound = 'true';
        noButton.addEventListener('click', function () {
            modalElement.classList.remove('active');
        });
    }

    if (!modalElement.dataset.confirmModalBound) {
        modalElement.dataset.confirmModalBound = 'true';
    }
}

class PhoneGroupInput {
    static CODES = [
        { code: '29', label: 'A1', group: 'Операторы' },
        { code: '33', label: 'МТС', group: 'Операторы' },
        { code: '44', label: 'life:)', group: 'Операторы' },
        { code: '25', label: 'МТС', group: 'Операторы' },
        { code: '17', label: 'Минск', group: 'Города' },
        { code: '162', label: 'Брест', group: 'Города' },
        { code: '212', label: 'Витебск', group: 'Города' },
        { code: '232', label: 'Гомель', group: 'Города' },
        { code: '152', label: 'Гродно', group: 'Города' },
        { code: '222', label: 'Могилёв', group: 'Города' }
    ];

    constructor(listEl, hiddenInput, addButton, options = {}) {
        this.listEl = listEl;
        this.hiddenInput = hiddenInput;
        this.addButton = addButton;
        this.options = {
            countryCode: '+375',
            totalDigits: 12,
            maxCount: 2,
            inputClass: 'auth-input',
            onChange: null,
            ...options
        };
        this.countryDigits = this.options.countryCode.replace(/\D/g, '');

        if (!this.listEl) return;

        this.bindEvents();
        this.init();
    }

    notifyChange() {
        if (typeof this.options.onChange === 'function') {
            this.options.onChange();
        }
    }

    init() {
        const existing = this.listEl.dataset.existingPhones;
        if (existing !== undefined) {
            this.listEl.innerHTML = '';
            const numbers = existing.split(';').map(s => s.trim()).filter(Boolean);
            if (numbers.length === 0) {
                this.listEl.appendChild(this.createRow());
            } else {
                numbers.slice(0, this.options.maxCount).forEach(num => {
                    this.listEl.appendChild(this.createRow(this.parseExistingNumber(num)));
                });
            }
        }

        this.listEl.querySelectorAll('.phone-row').forEach(row => this.updateRowConstraints(row));
        this.refreshControls();
        this.validate();
    }

    parseExistingNumber(num) {
        const digitsOnly = num.replace(/\D/g, '');
        let rest = digitsOnly;
        if (rest.startsWith(this.countryDigits)) {
            rest = rest.slice(this.countryDigits.length);
        }
        const sortedCodes = [...PhoneGroupInput.CODES].sort((a, b) => b.code.length - a.code.length);
        const match = sortedCodes.find(c => rest.startsWith(c.code));
        if (match) {
            return { code: match.code, digits: rest.slice(match.code.length) };
        }
        return { code: PhoneGroupInput.CODES[0].code, digits: rest };
    }

    bindEvents() {
        if (this.addButton) {
            this.addButton.addEventListener('click', () => this.addRow());
        }

        this.listEl.addEventListener('input', (e) => {
            if (e.target.classList.contains('phone-digits-input')) {
                this.sanitizeDigitsInput(e.target);
            }
            this.validate();
            this.notifyChange();
        });

        this.listEl.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.phone-row-remove');
            if (removeBtn) {
                this.removeRow(removeBtn.closest('.phone-row'));
                return;
            }

            const option = e.target.closest('.phone-code-option');
            if (option) {
                this.selectCode(option);
                return;
            }

            const trigger = e.target.closest('.phone-code-trigger');
            if (trigger) {
                this.toggleDropdown(trigger.closest('.phone-code-select'));
                return;
            }

            this.closeAllDropdowns();
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.phone-code-select')) {
                this.closeAllDropdowns();
            }
        });
    }

    sanitizeDigitsInput(input) {
        const cleaned = input.value.replace(/\D/g, '');
        if (cleaned !== input.value) {
            input.value = cleaned;
        }
    }

    getRowCode(row) {
        const select = row.querySelector('.phone-code-select');
        if (!select) return '';
        return select.dataset.code || '';
    }

    updateRowConstraints(row) {
        if (!row) return;
        const input = row.querySelector('.phone-digits-input');
        if (!input) return;
        const code = this.getRowCode(row);
        const maxDigits = Math.max(0, this.options.totalDigits - this.countryDigits.length - code.length);
        input.maxLength = maxDigits;
    }

    validate() {
        const rows = Array.from(this.listEl.querySelectorAll('.phone-row'));
        const validNumbers = [];
        let allFilledValid = true;
        let hasAtLeastOne = false;

        rows.forEach(row => {
            const input = row.querySelector('.phone-digits-input');
            if (!input) return;

            const digitsOnly = input.value.replace(/\D/g, '');
            row.classList.remove('invalid');

            if (!digitsOnly) {
                return;
            }

            hasAtLeastOne = true;
            const code = this.getRowCode(row);
            const totalDigits = this.countryDigits.length + code.length + digitsOnly.length;

            if (totalDigits === this.options.totalDigits) {
                validNumbers.push(this.options.countryCode + code + digitsOnly);
            } else {
                row.classList.add('invalid');
                allFilledValid = false;
            }
        });

        const isValid = hasAtLeastOne && allFilledValid;
        if (this.hiddenInput) {
            this.hiddenInput.value = isValid ? validNumbers.join('; ') : '';
        }
        return isValid;
    }

    addRow() {
        const currentCount = this.listEl.querySelectorAll('.phone-row').length;
        if (currentCount >= this.options.maxCount) return;

        const row = this.createRow();
        this.listEl.appendChild(row);
        this.updateRowConstraints(row);
        this.refreshControls();
        this.validate();
        this.notifyChange();
    }

    removeRow(row) {
        if (!row) return;
        row.remove();
        this.refreshControls();
        this.validate();
        this.notifyChange();
    }

    refreshControls() {
        const rows = this.listEl.querySelectorAll('.phone-row');
        rows.forEach(row => {
            const removeBtn = row.querySelector('.phone-row-remove');
            if (removeBtn) {
                removeBtn.style.display = rows.length > 1 ? 'inline-flex' : 'none';
            }
        });

        if (this.addButton) {
            const atMax = rows.length >= this.options.maxCount;
            this.addButton.style.display = atMax ? 'none' : 'inline-flex';
        }
    }

    toggleDropdown(select) {
        if (!select) return;
        const isOpen = select.classList.contains('open');
        this.closeAllDropdowns();
        if (!isOpen) {
            select.classList.add('open');
            const trigger = select.querySelector('.phone-code-trigger');
            if (trigger) trigger.setAttribute('aria-expanded', 'true');
        }
    }

    closeAllDropdowns() {
        this.listEl.querySelectorAll('.phone-code-select.open').forEach(select => {
            select.classList.remove('open');
            const trigger = select.querySelector('.phone-code-trigger');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        });
    }

    selectCode(optionEl) {
        const select = optionEl.closest('.phone-code-select');
        if (!select) return;

        const code = optionEl.dataset.code;
        select.dataset.code = code;

        select.querySelectorAll('.phone-code-option').forEach(opt => {
            opt.classList.toggle('selected', opt === optionEl);
        });

        const valueEl = select.querySelector('.phone-code-value');
        if (valueEl) {
            valueEl.textContent = `${this.options.countryCode} ${code}`;
        }

        this.closeAllDropdowns();

        const row = select.closest('.phone-row');
        this.updateRowConstraints(row);
        this.validate();
        this.notifyChange();
    }

    buildDropdownHtml(selectedCode) {
        let html = '';
        let currentGroup = null;
        PhoneGroupInput.CODES.forEach(({ code, label, group }) => {
            if (group !== currentGroup) {
                html += `<div class="phone-code-group-label">${group}</div>`;
                currentGroup = group;
            }
            const selectedClass = code === selectedCode ? ' selected' : '';
            html += `
                <button type="button" class="phone-code-option${selectedClass}" data-code="${code}" role="option">
                    <span>${this.options.countryCode} ${code}</span><span class="phone-code-hint">${label}</span>
                </button>
            `;
        });
        return html;
    }

    createRow(prefill) {
        const codeEntry = prefill
            ? (PhoneGroupInput.CODES.find(c => c.code === prefill.code) || PhoneGroupInput.CODES[0])
            : PhoneGroupInput.CODES[0];
        const digitsValue = prefill ? prefill.digits : '';

        const row = document.createElement('div');
        row.className = 'phone-row';
        row.setAttribute('data-phone-row', '');
        row.innerHTML = `
            <div class="phone-code-select" data-code="${codeEntry.code}">
                <button type="button" class="phone-code-trigger" aria-haspopup="listbox" aria-expanded="false">
                    <span class="phone-code-value">${this.options.countryCode} ${codeEntry.code}</span>
                    <svg class="phone-code-chevron" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M6 9l6 6 6-6" />
                    </svg>
                </button>
                <div class="phone-code-dropdown" role="listbox">
                    ${this.buildDropdownHtml(codeEntry.code)}
                </div>
            </div>
            <input type="text" class="phone-digits-input ${this.options.inputClass}" inputmode="numeric" autocomplete="off" placeholder="Номер телефона" value="${digitsValue}" />
            <button type="button" class="phone-row-remove" aria-label="Удалить номер">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
        `;
        return row;
    }
}

class MultiStepForm {
    constructor(options = {}) {
        this.config = {
            step1Selector: '.auth-step-1',
            step2Selector: '.auth-step-2',
            step3Selector: '.auth-step-3',
            formSelector: '#registration-form',
            nextBtn1Id: 'next-btn-1',
            nextBtn2Id: 'next-btn-2',
            prevBtn2Id: 'prev-btn-2',
            prevBtn3Id: 'prev-btn-3',
            submitBtnId: 'submit-btn',
            minSearchLength: 2,
            debounceDelay: 300,
            perPage: 10,
            ...options
        };

        this.currentEntityType = 'respondent';
        this.selectedItem = null;
        this.searchData = {
            page: 1,
            query: '',
            hasMore: false,
            loading: false
        };
        this.debounceTimer = null;
        this.init();
    }

    init() {
        this.elements = {};
        this.getElementReferences();
        this.bindEvents();
        this.phoneInput = new PhoneGroupInput(this.elements.phoneList, this.elements.telephoneHidden, this.elements.addPhoneBtn, {
            maxCount: 2,
            onChange: () => this.updateNextButtonState()
        });
        this.updateNextButtonState();
        this.updateSelectedRoleDisplay();
    }

    getElementReferences() {
        this.elements.step1 = document.querySelector(this.config.step1Selector);
        this.elements.step2 = document.querySelector(this.config.step2Selector);
        this.elements.step3 = document.querySelector(this.config.step3Selector);
        this.elements.form = document.querySelector(this.config.formSelector);
        
        this.elements.nextBtn1 = document.getElementById(this.config.nextBtn1Id);
        this.elements.nextBtn2 = document.getElementById(this.config.nextBtn2Id);
        this.elements.prevBtn2 = document.getElementById(this.config.prevBtn2Id);
        this.elements.prevBtn3 = document.getElementById(this.config.prevBtn3Id);
        this.elements.submitBtn = document.getElementById(this.config.submitBtnId);
        this.elements.entityTypeInput = document.getElementById('entity_type');

        this.elements.entityTypeRadioInputs = document.querySelectorAll('input[name="entity_type"]');
        
        this.elements.searchInput = document.getElementById('organization-search');
        this.elements.hiddenInput = document.getElementById('organization_id');
        this.elements.dropdown = document.getElementById('organization-dropdown');
        this.elements.list = document.getElementById('organization-list');
        this.elements.loading = document.getElementById('organization-loading');
        this.elements.empty = document.getElementById('organization-empty');
        this.elements.tableWrap = document.querySelector('.org-results-table-wrap');
        this.elements.step3Container = document.querySelector('.auth-step-3');

        this.elements.phoneList = document.getElementById('phone-group-list');
        this.elements.addPhoneBtn = document.getElementById('add-phone-row');
        this.elements.telephoneHidden = document.getElementById('telephone');
    }

    bindEvents() {
        if (this.elements.nextBtn1) {
            this.elements.nextBtn1.addEventListener('click', () => this.goToStep(2));
        }
        
        if (this.elements.nextBtn2) {
            this.elements.nextBtn2.addEventListener('click', () => this.goToStep(3));
        }
        
        if (this.elements.prevBtn2) {
            this.elements.prevBtn2.addEventListener('click', () => this.goToStep(1));
        }
        
        if (this.elements.prevBtn3) {
            this.elements.prevBtn3.addEventListener('click', () => this.goToStep(2));
        }
        
        if (this.elements.entityTypeRadioInputs) {
            this.elements.entityTypeRadioInputs.forEach(input => {
                input.addEventListener('change', (e) => this.handleEntityTypeChange(e));
            });
        }
        
        if (this.elements.searchInput) {
            this.elements.searchInput.addEventListener('input', (e) => this.handleSearchInput(e));
            this.elements.searchInput.addEventListener('focus', () => this.handleSearchFocus());
            this.elements.searchInput.addEventListener('blur', () => setTimeout(() => this.hideDropdown(), 200));
            this.elements.searchInput.addEventListener('keydown', (e) => this.handleSearchKeydown(e));
        }
        
        if (this.elements.tableWrap) {
            this.elements.tableWrap.addEventListener('scroll', () => this.handleTableScroll());
        }

        if (this.elements.form) {
            this.elements.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
        
        document.addEventListener('click', (e) => this.handleDocumentClick(e));
        
        this.setupStep1Validation();
    }

    handleEntityTypeChange(e) {
        this.currentEntityType = e.target.value;
        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }
        
        this.updateSelectedRoleDisplay();
        
        this.selectedItem = null;
        if (this.elements.hiddenInput) {
            this.elements.hiddenInput.value = '';
        }
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        if (this.elements.searchInput) {
            this.elements.searchInput.value = '';
            this.elements.searchInput.placeholder = this.getPlaceholder();
        }
        this.clearSearchResults();
        this.hideDropdown();
    }

    updateSelectedRoleDisplay() {
        const roles = {
            'respondent': {
                title: 'Организация-разработчик',
                subtitle: 'Юридическое лицо, создающее, редактирующее и направляющее планы на согласование'
            },
            'auditor': {
                title: 'Согласовывающая организация',
                subtitle: 'Проверяющее юридическое лицо, по результатам рассмотрения которого документ согласовывается либо не согласовывается'
            },
            'approver': {
                title: 'Утверждающая организация',
                subtitle: 'Проверяющее юридическое лицо, по результатам рассмотрения которого документ утверждается'
            }
        };
        
        const role = roles[this.currentEntityType] || roles['respondent'];
        
        const titleElement = document.getElementById('selected-role-title');
        const subtitleElement = document.getElementById('selected-role-subtitle');
        
        if (titleElement) titleElement.textContent = role.title;
        if (subtitleElement) subtitleElement.textContent = role.subtitle;
    }

    getPlaceholder() {
        const placeholders = {
            'respondent': 'Введите наименование или УНП',
            'auditor': 'Введите наименование или УНП',
            'approver': 'Введите наименование или УНП'
        };
        return placeholders[this.currentEntityType] || 'Введите наименование или УНП';
    }

    selectItem(item) {
        document.querySelectorAll('.org-result-row').forEach(el => {
            el.classList.remove('selected');
        });

        const clickedElement = document.querySelector(`.org-result-row[data-id="${item.id}"]`);
        if (clickedElement) {
            clickedElement.classList.add('selected');
        }

        // Строка результата просто подсвечивается — поле поиска не трогаем
        // (раньше туда подставлялось полное наименование организации,
        // перетирая то, что ввёл пользователь).
        if (this.elements.hiddenInput) {
            this.elements.hiddenInput.value = item.id;
        }

        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }

        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = false;
        }

        this.selectedItem = item;
    }

    handleFormSubmit(e) {
        e.preventDefault();
        
        if (!this.validateForm()) {
            alert('Пожалуйста, заполните все обязательные поля и выберите организацию');
            return;
        }
        
        const originalText = this.elements.submitBtn.querySelector('.btn-text').textContent;
        this.elements.submitBtn.querySelector('.btn-text').textContent = 'Отправка...';
        this.elements.submitBtn.disabled = true;
        
        const formData = new FormData(this.elements.form);
        
        fetch(this.elements.form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (response.redirected) {
                window.location.href = response.url;
            } else if (response.ok) {
                return response.json().then(data => {
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else if (data.success) {
                        alert('Регистрация успешно завершена!');
                        window.location.reload();
                    } else {
                        throw new Error(data.error || 'Неизвестная ошибка');
                    }
                });
            } else {
                return response.json().then(data => {
                    throw new Error(data.error || `HTTP ${response.status}`);
                });
            }
        })
        .catch(error => {
            console.error('Form submission error:', error);
            alert(`Ошибка при отправке формы: ${error.message}`);
        })
        .finally(() => {
            this.elements.submitBtn.querySelector('.btn-text').textContent = originalText;
            this.elements.submitBtn.disabled = false;
        });
    }

    validateForm() {
        const step1Valid = this.validateStep1();
        if (!step1Valid) return false;
        
        if (!this.elements.hiddenInput || !this.elements.hiddenInput.value) return false;
        
        return true;
    }

    setupStep1Validation() {
        const requiredFields = ['#name', '#secondname', '#patronymic'];
        requiredFields.forEach(selector => {
            const input = document.querySelector(selector);
            if (input) {
                input.addEventListener('input', () => this.updateNextButtonState());
                input.addEventListener('change', () => this.updateNextButtonState());
            }
        });
        this.updateNextButtonState();
    }

    updateNextButtonState() {
        const isStep1Valid = this.validateStep1();
        if (this.elements.nextBtn1) {
            this.elements.nextBtn1.disabled = !isStep1Valid;
            if (isStep1Valid) {
                this.elements.nextBtn1.classList.remove('disabled');
            } else {
                this.elements.nextBtn1.classList.add('disabled');
            }
        }
    }

    validateStep1() {
        const requiredFields = ['secondname', 'name', 'patronymic', 'post'];
        const textFieldsValid = requiredFields.every(fieldId => {
            const input = document.getElementById(fieldId);
            return input && input.value.trim() !== '';
        });
        return textFieldsValid && (this.phoneInput ? this.phoneInput.validate() : false);
    }


    goToStep(stepNumber) {
        if (this.elements.step1) this.elements.step1.style.display = 'none';
        if (this.elements.step2) this.elements.step2.style.display = 'none';
        if (this.elements.step3) this.elements.step3.style.display = 'none';
        
        switch(stepNumber) {
            case 1:
                if (this.elements.step1) {
                    this.elements.step1.style.display = 'block';
                    this.elements.step1.classList.add('active');
                    if (this.elements.step2) this.elements.step2.classList.remove('active');
                    if (this.elements.step3) this.elements.step3.classList.remove('active');
                }
                break;
            case 2:
                if (this.validateStep1()) {
                    if (this.elements.step2) {
                        this.elements.step2.style.display = 'block';
                        if (this.elements.step1) this.elements.step1.classList.remove('active');
                        this.elements.step2.classList.add('active');
                        if (this.elements.step3) this.elements.step3.classList.remove('active');
                    }
                } else {
                    alert('Пожалуйста, заполните все обязательные поля');
                    if (this.elements.step1) {
                        this.elements.step1.style.display = 'block';
                    }
                }
                break;
            case 3:
                if (this.elements.step3) {
                    this.elements.step3.style.display = 'block';
                    if (this.elements.step1) this.elements.step1.classList.remove('active');
                    if (this.elements.step2) this.elements.step2.classList.remove('active');
                    this.elements.step3.classList.add('active');
                }
                break;
        }
    }

    handleSearchInput(e) {
        const query = e.target.value.trim();
        
        this.selectedItem = null;
        if (this.elements.hiddenInput) {
            this.elements.hiddenInput.value = '';
        }
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        
        this.searchData.query = query;
        this.searchData.page = 1;
        
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        if (query.length >= this.config.minSearchLength) {
            this.debounceTimer = setTimeout(() => {
                this.searchEntities(query, 1, false);
            }, this.config.debounceDelay);
        } else {
            this.hideDropdown();
            this.clearSearchResults();
        }
    }

    handleSearchFocus() {
        const query = this.searchData.query;
        if (query && query.length >= this.config.minSearchLength &&
            this.elements.dropdown && this.elements.list && this.elements.list.children.length > 0) {
            this.showDropdown();
        }
    }

    showDropdown() {
        if (this.elements.dropdown) {
            this.elements.dropdown.classList.add('active');
        }
        if (this.elements.step3Container) {
            this.elements.step3Container.classList.add('has-results');
        }
    }

    handleSearchKeydown(e) {
        if (e.key === 'Escape') {
            this.hideDropdown();
        }
    }

    handleLoadMore() {
        if (this.searchData.hasMore && this.searchData.query && !this.searchData.loading) {
            this.searchData.page += 1;
            this.searchEntities(this.searchData.query, this.searchData.page, true);
        }
    }

    handleTableScroll() {
        const el = this.elements.tableWrap;
        if (!el) return;
        const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
        if (nearBottom) {
            this.handleLoadMore();
        }
    }

    handleDocumentClick(e) {
        if (this.elements.searchInput && this.elements.dropdown &&
            !this.elements.searchInput.contains(e.target) &&
            !this.elements.dropdown.contains(e.target)) {
            this.hideDropdown();
        }
    }

    async searchEntities(query, page = 1, append = false) {
        if (this.searchData.loading) return;
        
        this.searchData.loading = true;
        
        if (!append) {
            this.showLoading(true);
            this.clearSearchResults();
        }
        
        try {
            const url = `/api/organizations?q=${encodeURIComponent(query)}&page=${page}&type=${this.currentEntityType}&exclude_registered=true`;
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.handleSearchResponse(data, append);
        } catch (error) {
            console.error('Error fetching organizations:', error);
            this.showError(error.message);
        } finally {
            this.searchData.loading = false;
            this.showLoading(false);
        }
    }

    handleSearchResponse(data, append = false) {
        if (!this.elements.list || !this.elements.dropdown) return;

        const items = data.organizations || [];

        if (!append) {
            this.elements.list.innerHTML = '';
        }

        if (items.length > 0) {
            items.forEach(item => {
                const itemElement = this.createListItem(item);
                this.elements.list.appendChild(itemElement);
            });

            this.searchData.hasMore = data.has_next || false;
            if (this.elements.empty) {
                this.elements.empty.style.display = 'none';
            }

            this.showDropdown();
        } else if (!append) {
            this.searchData.hasMore = false;
            if (this.elements.empty) {
                this.elements.empty.textContent = 'Ничего не найдено';
                this.elements.empty.style.display = 'block';
            }
            this.showDropdown();
        }
    }

    createListItem(item) {
        const tr = document.createElement('tr');
        tr.className = 'org-result-row';
        tr.dataset.id = item.id;

        tr.innerHTML = `
            <td class="item-name">${this.escapeHtml(item.name)}</td>
            <td class="item-okpo">${this.escapeHtml(item.okpo || '—')}</td>
            <td class="item-ynp">${this.escapeHtml(item.ynp || '—')}</td>
        `;

        tr.addEventListener('click', () => {
            this.selectItem(item);
        });

        return tr;
    }

    showLoading(show) {
        if (this.elements.loading) {
            this.elements.loading.style.display = show ? 'block' : 'none';
        }
    }

    clearSearchResults() {
        if (this.elements.list) {
            this.elements.list.innerHTML = '';
        }
        if (this.elements.empty) {
            this.elements.empty.style.display = 'none';
        }
        this.searchData.hasMore = false;
    }

    hideDropdown() {
        // Пока организация выбрана (this.selectedItem), таблица результатов
        // остаётся открытой — иначе клик по строке сам уводит фокус с
        // инпута поиска, который через blur дёргает hideDropdown() и тут же
        // схлопывает панель с результатами (.active убирает display:flex у
        // самой панели, .has-results — сужает контейнер), из-за чего
        // подсвеченную строку не видно. Сбрасывается в handleSearchInput()
        // при новом вводе.
        if (this.selectedItem) return;

        if (this.elements.dropdown) {
            this.elements.dropdown.classList.remove('active');
        }
        if (this.elements.step3Container) {
            this.elements.step3Container.classList.remove('has-results');
        }
    }

    showError(message = 'Ошибка загрузки данных') {
        if (this.elements.list && this.elements.dropdown) {
            this.elements.list.innerHTML = '';
            if (this.elements.empty) {
                this.elements.empty.textContent = message;
                this.elements.empty.style.display = 'block';
            }
            this.showDropdown();
        }
        this.showLoading(false);
    }

    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    destroy() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
    }

    reset() {
        this.currentEntityType = 'respondent';
        this.selectedItem = null;
        
        if (this.elements.hiddenInput) {
            this.elements.hiddenInput.value = '';
        }
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        if (this.elements.searchInput) {
            this.elements.searchInput.value = '';
        }
        
        this.searchData = {
            page: 1,
            query: '',
            hasMore: false,
            loading: false
        };
        
        this.goToStep(1);
    }
}

class PlanTicketInfo {
    constructor(options = {}) {
        this.options = {
            animationDuration: 300,
            overlayClass: 'ticket-info-overlay',
            panelClass: 'ticket-info-panel',
            closeOnEscape: true,
            closeOnOverlayClick: true,
            ...options
        };
        
        this.currentPanel = null;
        this.init();
    }
    
    init() {
        this.injectStyles();
        if (this.options.closeOnEscape) {
            this.escapeHandler = this.handleEscapeKey.bind(this);
        }
    }
    
    async show(ticketId, element = null) {
        if (this.currentPanel) {
            this.close();
            return;
        }
        
        try {
            const loadingOverlay = this.createLoadingOverlay();
            document.body.appendChild(loadingOverlay);
            
            const response = await fetch(`/api/ticket/${ticketId}/details`);
            if (!response.ok) throw new Error('Ошибка загрузки данных');
            const data = await response.json();
            
            loadingOverlay.remove();
            const context = element ? this.extractContextFromElement(element) : {};
            this.currentPanel = this.createPanel({...data, ...context});
            this.addEventListeners();
            
        } catch (error) {
            console.error('Error loading ticket details:', error);
            this.showError('Ошибка загрузки данных о сообщении');
        }
    }
    
    createPanel(data) {
        const overlay = document.createElement('div');
        overlay.className = this.options.overlayClass;
        overlay.style.animation = 'fadeIn 0.3s ease';
        
        const panel = document.createElement('div');
        panel.className = this.options.panelClass;
        panel.innerHTML = this.generatePanelHTML(data);
        
        overlay.appendChild(panel);
        document.body.appendChild(overlay);
        
        return overlay;
    }
    
    generatePanelHTML(data) {
        const time = data.time || this.extractTime(data);
        const text = data.text || data.note || '';
        const date = data.date || '';
        
        return `
            <div class="ticket-info-content-wrapper">
                <div class="ticket-info-header">
                    <h3 class="ticket-info-title">Информация о сообщении</h3>
                    <button class="ticket-info-close" onclick="window.ticketInfoInstance.close()">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/>
                        </svg>
                    </button>
                </div>
                <div class="ticket-info-content">
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Организация</span>
                        <span class="ticket-info-value" title="${data.organization || 'Система'}">${data.organization || 'Система'}</span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">ФИО</span>
                        <span class="ticket-info-value">${data.user_fio || '---'}</span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Email</span>
                        <span class="ticket-info-value">
                            <a href="mailto:${data.user_email}" class="ticket-info-link">
                                ${data.user_email || '---'}
                            </a>
                        </span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Телефон</span>
                        <span class="ticket-info-value">
                            <a href="tel:${data.user_telephone}" class="ticket-info-link">
                                ${data.user_telephone || '---'}
                            </a>
                        </span>
                    </div>
               
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Время создания</span>
                        <span class="ticket-info-value">${date || 'Не указана'} - ${time}</span>
                    </div>
                    <div class="ticket-info-item full-width">
                        <span class="ticket-info-label">Текст сообщения</span>
                        <div class="ticket-message-container">
                            <span class="ticket-message-text">${text}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
        //  <div class="ticket-info-item">
        //                 <span class="ticket-info-label">Статус сообщения</span>
        //                 <span class="ticket-info-value ticket-info-status ${data.luck ? 'success' : 'error'}">
        //                     ${data.luck ? '✓ Согласовано' : '✗ Есть ошибки'}
        //                 </span>
        //             </div>
    extractContextFromElement(element) {
        const context = {};
        if (!element) return context;
        
        const messageElement = element.closest('.tickets-message');
        if (messageElement) {
            const timeEl = messageElement.querySelector('.message-time');
            const textEl = messageElement.querySelector('.text-ticket');
            const dateEl = messageElement.querySelector('.message-date');
            
            context.time = timeEl ? timeEl.textContent : '';
            context.text = textEl ? textEl.textContent : '';
            context.date = dateEl ? dateEl.textContent : '';
        }
        
        return context;
    }
    
    extractTime(data) {
        return data.begin_time ? new Date(data.begin_time).toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'}) : '--:--';
    }
    
    createLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.className = this.options.overlayClass + ' loading';
        overlay.innerHTML = `
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 16px;">
                Загрузка...
            </div>
        `;
        return overlay;
    }
    
    addEventListeners() {
        if (this.options.closeOnOverlayClick && this.currentPanel) {
            this.currentPanel.addEventListener('click', (e) => {
                if (e.target === this.currentPanel) this.close();
            });
        }
        
        if (this.options.closeOnEscape) {
            document.addEventListener('keydown', this.escapeHandler);
        }
    }
    
    handleEscapeKey(event) {
        if (event.key === 'Escape') this.close();
    }
    
    showError(message) {
        alert(message);
    }
    
    close() {
        if (!this.currentPanel) return;
        
        this.currentPanel.style.animation = 'fadeOut 0.3s ease';
        const panelContent = this.currentPanel.querySelector(`.${this.options.panelClass}`);
        if (panelContent) panelContent.style.animation = '';
        
        setTimeout(() => {
            this.currentPanel.remove();
            this.currentPanel = null;
            document.removeEventListener('keydown', this.escapeHandler);
        }, this.options.animationDuration);
    }
    
    injectStyles() {
        const style = document.createElement('style');
        style.textContent = this.getStyles();
        document.head.appendChild(style);
    }
    
    getStyles() {
        return `
            .ticket-info-item.full-width {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            
            .ticket-message-container {
                background: #F5F5F5;
                padding: 12px;
                border-radius: 8px;
                width: 100%;
                box-sizing: border-box;
            }
            
            .ticket-message-text {
                text-align: left;
                display: block;
                color: #333;
                font-size: 14px;
                line-height: 1.5;
                word-break: break-word;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
            
            @keyframes scaleIn {
                from {
                    opacity: 0;
                    transform: scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: scale(1);
                }
            }
            
            @keyframes scaleOut {
                from {
                    opacity: 1;
                    transform: scale(1);
                }
                to {
                    opacity: 0;
                    transform: scale(0.95);
                }
            }
        `;
    }
}

window.PlanTicketInfo = PlanTicketInfo;

function initSections() {
    const sections = document.querySelectorAll('.user-info-section:not([data-initialized])');
    
    sections.forEach(section => {
        const action = section.getAttribute('data-action');
        const toggleIcon = section.querySelector('.toggle-icon');
        
        if (action === 'close') {
            section.classList.add('collapsed');
            toggleIcon.textContent = '+';
        } else {
            section.classList.remove('collapsed');
            toggleIcon.textContent = '−';
        }
        
        const header = section.querySelector('.section-header');
        header.addEventListener('click', function() {
            section.classList.toggle('collapsed');
            toggleIcon.textContent = section.classList.contains('collapsed') ? '+' : '−';
        });
        
        section.setAttribute('data-initialized', 'true');
    });
}

function initDropdownMenu(buttonId, menuId) {
    const button = document.getElementById(buttonId);
    const menu = document.getElementById(menuId);
    
    if (!button || !menu) {
        console.warn(`Dropdown menu not initialized: button with id "${buttonId}" or menu with id "${menuId}" not found`);
        return;
    }
    
    function closeMenu() {
        menu.classList.remove('show');
    }
    
    function openMenu() {
        document.querySelectorAll('.dropdown-menu.show').forEach(otherMenu => {
            if (otherMenu !== menu) {
                otherMenu.classList.remove('show');
            }
        });
        menu.classList.add('show');
    }
    
    button.addEventListener('click', (e) => {
        e.stopPropagation();
        
        if (menu.classList.contains('show')) {
            closeMenu();
        } else {
            openMenu();
        }
    });
    
    document.addEventListener('click', (e) => {
        if (!button.contains(e.target) && !menu.contains(e.target)) {
            closeMenu();
        }
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && menu.classList.contains('show')) {
            closeMenu();
        }
    });
    
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (menu.classList.contains('show')) {
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                closeMenu();
            }, 100);
        }
    });
    
    const forms = menu.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', () => {
            closeMenu();
        });
    });
    
    const buttons = menu.querySelectorAll('button:not([type="submit"])');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            closeMenu();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.toggle-password')) {
        togglePassword.init();
    }

    if (document.querySelector('.activation_code_input')) {
        activationCode.init();
    }

    if (document.getElementById('resend-code-btn') && 
        document.getElementById('resend-form') && 
        document.getElementById('countdown')) {
        window.codeVerification = createCodeVerification();
    }

    if (document.querySelector('.auth-step-1') && document.querySelector('.auth-step-2')) {
        formSteps.init();
    }

    new DirectionsTable({
        searchSelector: "search-directions",
        tableSelector: "modal-table-main",
        hiddenInputSelector: "selected-direction",
        nextButtonSelector: "directions-next"
    });

    if (document.getElementById('paginationArea')) {
        const searchManager = new MultiTypeSearchManager();
    }

    if (document.getElementById('notifBtn')) {
        NotificationPopup.init({
            button: "#notifBtn",
            popup: "#notifPopup"
        });
        Notifications.init();
        setInterval(() => {
            Notifications.refreshBadge();
        }, 60000);
    }

    if (document.querySelectorAll('.tickets-container')) {
        window.PlanTicketInfo = PlanTicketInfo;
    }
    
    initSections();
});

document.write('<script src="/static/js/chat.js"></script>');
document.addEventListener('DOMContentLoaded', function() {
    if (window.ChatModule) {
        const userId = document.body.dataset.userId || 1;
        ChatModule.init(userId);
    }
});

// document.addEventListener('DOMContentLoaded', function() {
//     if (typeof window.initCookieBanner === 'function') {
//         window.initCookieBanner();
//     }
// });

// Вкладки в стиле личного кабинета (.profile-tabs/.profile-tab-panel) —
// общий инициализатор для любой страницы, где они встречаются (профиль,
// проверка плана и т.д.), поддерживает несколько независимых групп вкладок
// на одной странице (панели ищутся среди соседей самого блока вкладок).
function initProfileTabs() {
    document.querySelectorAll('.profile-tabs').forEach((tabsEl) => {
        const tabButtons = tabsEl.querySelectorAll('.profile-tab');
        const container = tabsEl.parentElement;
        if (!container) return;
        const tabPanels = container.querySelectorAll(':scope > .profile-tab-panel');

        function activateTab(tabName) {
            tabButtons.forEach((btn) => {
                const isActive = btn.dataset.tab === tabName;
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            tabPanels.forEach((panel) => {
                panel.classList.toggle('active', panel.dataset.tabPanel === tabName);
            });
        }

        tabButtons.forEach((btn) => {
            btn.addEventListener('click', () => activateTab(btn.dataset.tab));
        });
    });
}
document.addEventListener('DOMContentLoaded', initProfileTabs);

if (document.getElementById('dots-profile-org')) {
    initDropdownMenu('dots-profile-org', 'menu-profile-org');
}

if (document.getElementById('dots-profile-user')) {
    initDropdownMenu('dots-profile-user', 'menu-profile-user');
}

if (document.getElementById('dots-profile-password')) {
    initDropdownMenu('dots-profile-password', 'menu-profile-password');
}

if (document.getElementById('dots-profile-session')) {
    initDropdownMenu('dots-profile-session', 'menu-profile-session');
}

if (document.getElementById('dots-profile-verification')) {
    initDropdownMenu('dots-profile-verification', 'menu-profile-verification');
}

if (document.getElementById('menuDotsBtn')) {
    initDropdownMenu('menuDotsBtn', 'planActionsMenu');
}

const triggerSideBar = document.getElementById("user-profile-panel-trigger");
const sidebarUser = document.getElementById("user-profile-panel");
const sidebarOverlay = document.getElementById("sidebar-overlay");

function closeSidebar() {
    if (sidebarUser) {
        sidebarUser.classList.remove("show");
    }
    if (sidebarOverlay) {
        sidebarOverlay.classList.remove("show");
    }
}

function openSidebar() {
    if (sidebarUser) {
        sidebarUser.classList.add("show");
    }
    if (sidebarOverlay) {
        sidebarOverlay.classList.add("show");
    }
}

if (triggerSideBar && sidebarUser) {
    triggerSideBar.addEventListener("click", (e) => {
        e.stopPropagation();
        if (sidebarUser.classList.contains("show")) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", closeSidebar);
}

document.addEventListener("click", (e) => {
    if (sidebarUser && sidebarUser.classList.contains("show")) {
        if (!sidebarUser.contains(e.target) && !triggerSideBar.contains(e.target)) {
            closeSidebar();
        }
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const statNumbers = document.querySelectorAll('.stat-numbers');
    
    if (statNumbers.length > 0) {
        const animateCounter = (element) => {
            const target = parseInt(element.getAttribute('data-count'));
            const duration = 2000;
            const start = 0;
            const increment = target / (duration / 16);
            let current = start;
            
            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    current = target;
                    clearInterval(timer);
                }
                element.textContent = Math.floor(current);
            }, 16);
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        statNumbers.forEach(stat => observer.observe(stat));
    }
    
    const ticket_container = document.querySelector('.tickets-messages-list');
    if (ticket_container) {
        setTimeout(() => {
            ticket_container.scrollTo({
                top: ticket_container.scrollHeight,
                behavior: 'smooth'
            });
        }, 100);
    }

});

document.addEventListener('DOMContentLoaded', () => {
    try {
        const multiStepForm = new MultiStepForm();
        window.multiStepForm = multiStepForm;
    } catch (error) {
        console.error('Failed to initialize MultiStepForm:', error);
    }
});

/* ============================================
   FILTER DROPDOWNS
   .filters-area can scroll horizontally on narrow
   screens (fixed-width filter controls). Once a
   container scrolls on one axis, the browser clips
   the other axis too, which hides an absolutely
   positioned .dropdown-menu-filter behind whatever
   comes after it (e.g. .plans-area). Fix: while a
   dropdown is open, position its menu with `fixed`
   using the toggle button's real viewport coordinates,
   so it escapes any scrolling/clipping ancestor.
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
    function positionDropdownMenu(dropdown) {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu-filter');
        if (!toggle || !menu) return;

        const rect = toggle.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.top = (rect.bottom + 4) + 'px';
        menu.style.left = rect.left + 'px';
        menu.style.right = 'auto';

        requestAnimationFrame(() => {
            const menuRect = menu.getBoundingClientRect();
            const overflowRight = menuRect.right - window.innerWidth;
            if (overflowRight > 0) {
                menu.style.left = Math.max(8, rect.left - overflowRight - 8) + 'px';
            }
        });
    }

    function resetDropdownMenu(dropdown) {
        const menu = dropdown.querySelector('.dropdown-menu-filter');
        if (!menu) return;
        menu.style.position = '';
        menu.style.top = '';
        menu.style.left = '';
        menu.style.right = '';
    }

    document.querySelectorAll('.custom-dropdown').forEach(dropdown => {
        const observer = new MutationObserver(() => {
            if (dropdown.classList.contains('active')) {
                positionDropdownMenu(dropdown);
            } else {
                resetDropdownMenu(dropdown);
            }
        });
        observer.observe(dropdown, { attributes: true, attributeFilter: ['class'] });
    });

    window.addEventListener('resize', () => {
        document.querySelectorAll('.custom-dropdown.active').forEach(positionDropdownMenu);
    });
});

// Копирование ОКПО/УНП по клику на карточке организации
// (см. macros/components.html :: organization_view_card).
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.org-code-copy').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const value = btn.dataset.copyValue || '';
            if (!value) return;

            try {
                await navigator.clipboard.writeText(value);
            } catch (e) {
                const input = document.createElement('textarea');
                input.value = value;
                input.style.position = 'fixed';
                input.style.opacity = '0';
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                document.body.removeChild(input);
            }

            btn.classList.add('copied');
            clearTimeout(btn._copyResetTimeout);
            btn._copyResetTimeout = setTimeout(() => {
                btn.classList.remove('copied');
            }, 1600);
        });
    });
});

// Подтверждение/отмена этапа согласования плана администратором
// (см. macros/components.html :: plan_agree_slider) — предупреждаем о
// каскадном эффекте (см. handle_admin_confirm_step/handle_admin_cancel_step
// в status_plan.py) перед реальной отправкой формы.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.enplans-approval-admin-form').forEach((form) => {
        form.addEventListener('submit', (e) => {
            const button = e.submitter;
            const action = button ? button.dataset.confirmAction : null;
            const orgName = form.dataset.orgName || '';

            const question = action === 'cancel'
                ? `Отменить подтверждение этапа «${orgName}»? Все последующие подтверждённые этапы тоже будут отменены.`
                : `Подтвердить этап «${orgName}» в обход обычного порядка? Все предыдущие непройденные этапы будут подтверждены автоматически.`;

            if (!confirm(question)) {
                e.preventDefault();
            }
        });
    });
});