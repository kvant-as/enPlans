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

const messageFlash = (function() {
    const containerId = 'flash-container';
    let container;
    let messages = []; 
    const DISPLAY_TIME = 30000; 

    function init() {
        container = document.getElementById(containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = containerId;
            document.body.appendChild(container);
        }

        const storedMessages = JSON.parse(localStorage.getItem('flashMessages') || '[]');
        const now = Date.now();
        messages = storedMessages.filter(msg => now - msg.createdAt < DISPLAY_TIME);

        localStorage.setItem('flashMessages', JSON.stringify(messages));
        renderMessages();
    }

    function _showMessage(msgObj) {
        const alertBox = document.createElement('div');
        alertBox.className = `custom-alert ${msgObj.type === 'error' ? 'alert-danger' : 'alert-success'} collapsed`;

        const imgSrc = msgObj.type === 'error'
            ? '/static/img/Error.svg'
            : '/static/img/Checkmark.svg';

        let messageText = msgObj.msg;
        let isLong = messageText && messageText.length > 80;
        let displayText = isLong ? messageText.substring(0, 80) + '...' : messageText;

        alertBox.innerHTML = `
            <img src="${imgSrc}" class="alert-icon" alt="">
            <div class="p_message_cont">
                <p>${displayText}</p>
                ${isLong ? '<span class="expand-hint">нажмите для развертывания</span>' : ''}
            </div>
            <button class="alert-close">&times;</button>
        `;

        if (isLong) {
            const fullText = messageText;
            const pElement = alertBox.querySelector('.p_message_cont p');
            const hintElement = alertBox.querySelector('.expand-hint');
            
            alertBox.addEventListener('click', (e) => {
                if (e.target.classList.contains('alert-close')) return;
                
                if (alertBox.classList.contains('collapsed')) {
                    pElement.textContent = fullText;
                    hintElement.textContent = 'нажмите для сворачивания';
                    alertBox.classList.remove('collapsed');
                    alertBox.classList.add('expanded');
                } else if (alertBox.classList.contains('expanded')) {
                    pElement.textContent = displayText;
                    hintElement.textContent = 'нажмите для развертывания';
                    alertBox.classList.remove('expanded');
                    alertBox.classList.add('collapsed');
                }
            });
        }

        alertBox.querySelector('.alert-close').addEventListener('click', e => {
            e.stopPropagation();
            removeMessage(alertBox, msgObj);
        });

        container.appendChild(alertBox);

        const now = Date.now();
        const elapsed = now - msgObj.createdAt;
        const remaining = Math.max(DISPLAY_TIME - elapsed, 0);

        if (remaining > 0) {
            setTimeout(() => {
                if (container.contains(alertBox)) {
                    removeMessage(alertBox, msgObj);
                }
            }, remaining);
        } else {
            removeMessage(alertBox, msgObj);
        }
    }

    function removeMessage(alertBox, msgObj) {
        alertBox.classList.add('removing');
        setTimeout(() => {
            if (container.contains(alertBox)) container.removeChild(alertBox);
            messages = messages.filter(m => m.msg !== msgObj.msg);
            localStorage.setItem('flashMessages', JSON.stringify(messages));
            renderMessages();
        }, 300);
    }

    function addMessage(msg, type='success') {
        const msgObj = { msg, type, createdAt: Date.now() };
        messages.push(msgObj);
        localStorage.setItem('flashMessages', JSON.stringify(messages));
        renderMessages();
    }

    function renderMessages() {
        container.innerHTML = '';
        messages.forEach(_showMessage);
        container.querySelectorAll('.custom-alert').forEach((el, index) => {
            if (index !== container.children.length - 1) {
                el.classList.add('collapsed');
            }
        });
    }

    return { init, addMessage };
})();

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
    allNotifications: [],

    async load(reset = true) {
        if (this.isLoading) return;
        if (!reset && !this.hasMore) return;
        
        this.isLoading = true;
        
        if (reset) {
            this.page = 1;
            this.allNotifications = [];
            this.hasMore = true;
            this.notifListEl.innerHTML = '';
        }
        
        try {
            const response = await fetch(`/api/notifications?page=${this.page}&per_page=${this.perPage}`);
            const data = await response.json();
            
            this.hasMore = data.has_next;
            this.allNotifications = reset ? data.notifications : [...this.allNotifications, ...data.notifications];
            
            this.render(this.allNotifications);
            
            if (this.hasMore) {
                this.showLoadMore();
            } else {
                this.hideLoadMore();
            }
            
        } catch (err) {
            console.error("Ошибка загрузки уведомлений:", err);
        } finally {
            this.isLoading = false;
        }
    },

    render(data) {
        this.notifListEl.innerHTML = ""; 

        if (!data || data.length === 0) {
            this.notifListEl.innerHTML = "<div class='notif empty'>Нет уведомлений</div>";
            this.hideCounter();
            this.hideLoadMore();
            return;
        }

        let unreadCount = 0;

        data.forEach(n => {
            const notif = document.createElement("div");
            notif.classList.add("notif");
            if (!n.is_read) {
                notif.classList.add("unread");
                unreadCount++;
            }

            const formattedTime = this.formatNotificationTime(n.created_at);
            
            notif.innerHTML = `
                <div class="notif-message">${n.message}</div>
                <div class="notif-time">${formattedTime}</div>
                <div class="notif-divider-line"></div>
            `;
            
            notif.addEventListener('click', () => {
                if (!n.is_read) {
                    this.markAsRead(n.id);
                }
            });
            
            this.notifListEl.appendChild(notif);
        });

        this.updateCounter(unreadCount);
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
                if (notification) {
                    notification.is_read = true;
                    this.render(this.allNotifications);
                }
            }
        } catch (err) {
            console.error("Ошибка при отметке уведомления:", err);
        }
    },

    async loadMore() {
        this.page++;
        await this.load(false);
    },

    showLoadMore() {
        if (!this.loadMoreBtn) {
            this.loadMoreBtn = document.createElement("button");
            this.loadMoreBtn.className = "load-more-notifications";
            this.loadMoreBtn.textContent = "Загрузить предыдущие";
            this.loadMoreBtn.addEventListener("click", () => this.loadMore());
            this.notifListEl.parentNode.appendChild(this.loadMoreBtn);
        }
        this.loadMoreBtn.style.display = "block";
    },

    hideLoadMore() {
        if (this.loadMoreBtn) {
            this.loadMoreBtn.style.display = "none";
        }
    },

    updateCounter(count) {
        if (count > 0) {
            this.notifCountEl.innerText = count;
            this.notifCountEl.style.display = "flex";
            this.notifCountEl.classList.add("active");
        } else {
            this.notifCountEl.classList.remove("active");
            this.notifCountEl.style.display = "none";
            this.notifCountEl.innerText = "";
        }
    },

    hideCounter() {
        this.notifCountEl.classList.remove("active");
        this.notifCountEl.style.display = "none";
        this.notifCountEl.innerText = "";
    },

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

            const result = await response.json();
            
            this.allNotifications.forEach(n => n.is_read = true);
            this.render(this.allNotifications);
            
        } catch (err) {
            console.error("Ошибка при отметке уведомлений:", err);
        }
    },

    init() {
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
    const requiredFields = ['#name', '#secondname', '#phone'];

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

    window.addEventListener('click', function(event) {
        if (event.target === modalElement) {
            modalElement.classList.remove('active');
        }
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

NumericInputHandler.init('.app-numeric-input-negative-one-decimal', {
    allowNegative: true,
    decimalPlaces: 1,
    defaultValue: '0,0'
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

        this.initSearch();
        this.initSelection();

        if (this.nextButton) {
            this.nextButton.disabled = true;
        }
    }

    createNoInfoRow() {
        const noResultsRow = document.createElement("tr");
        noResultsRow.className = "no-results-row";
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.style.textAlign = "center";
        cell.style.padding = "40px 20px";
        
        const container = document.createElement("div");
        container.style.display = "flex";
        container.style.flexDirection = "column";
        container.style.alignItems = "center";
        container.style.gap = "12px";
        
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", "38");
        svg.setAttribute("height", "38");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        svg.style.opacity = "0.5";
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z");
        path.setAttribute("stroke", "#999");
        path.setAttribute("stroke-width", "1.5");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        path.setAttribute("fill", "none");
        
        svg.appendChild(path);
        
        const text = document.createElement("span");
        text.textContent = "Нет похожей информации";
        text.style.fontSize = "13px";
        text.style.color = "#999";
        
        container.appendChild(svg);
        container.appendChild(text);
        cell.appendChild(container);
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
            higherOrganizationsApiUrl: '/api/higher-organizations',
            oblispolkomGorispolkomApiUrl: '/api/oblispolkom-gorispolkoms',
            regionsApiUrl: '/api/regions',
            
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
        this.highlightActiveTypeButton();
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

        if (this.typeButtons.length > 0) {
            this.typeButtons.forEach(button => {
                button.addEventListener('click', (e) => {
                    const type = e.target.dataset.type || e.target.closest('button').dataset.type;
                    if (type && type !== this.selectedItemType) {
                        this.selectItemType(type);
                    }
                });
            });
        }

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
                case 'higher_organization':
                    apiUrl = this.config.higherOrganizationsApiUrl;
                    break;
                case 'oblispolkom_gorispolkom':
                    apiUrl = this.config.oblispolkomGorispolkomApiUrl;
                    break;
                case 'region':
                    apiUrl = this.config.regionsApiUrl;
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
            case 'higher_organization':
                return data.higher_organizations || [];
            case 'oblispolkom_gorispolkom':
                return data.oblispolkom_gorispolkoms || [];
            case 'region':
                return data.regions || [];
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
                case 'higher_organization':
                    html += `
                        <td style="width: 100%;">${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;"></td>
                        <td style="text-align: center;"></td>
                    `;
                    break;
                case 'oblispolkom_gorispolkom':
                    html += `
                        <td style="width: 100%;">${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;"></td>
                        <td style="text-align: center;"></td>
                    `;
                    break;
                case 'region':
                    html += `
                        <td style="width: 100%;">${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;"></td>
                        <td style="text-align: center;"></td>
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
            case 'higher_organization':
                headersHTML += `
                    <th style="width: 100%;">Наименование вышестоящей организации</th>
                    <th style="text-align: center;"></th>
                    <th style="text-align: center;"></th>
                `;
                break;
            case 'oblispolkom_gorispolkom':
                headersHTML += `
                    <th style="width: 100%;">Наименование обл/горисполкома</th>
                    <th style="text-align: center;"></th>
                    <th style="text-align: center;"></th>
                `;
                break;
            case 'region':
                headersHTML += `
                    <th style="width: 100%;">Наименование региона</th>
                    <th style="text-align: center;"></th>
                    <th style="text-align: center;"></th>
                `;
                break;
        }
        
        headersHTML += `</tr>`;
        thead.innerHTML = headersHTML;
    }

    selectItemType(type) {
        this.selectedItemType = type;
        this.selectedItemId = null;
        this.currentPage = 1;
        this.currentQuery = '';
        
        this.typeButtons.forEach(btn => {
            if (btn.dataset.type === type) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        this.updateSearchPlaceholder(type);
        this.updateSubmitButtonText();
        this.updateModalTitle(type);
        
        if (this.searchInput) {
            this.searchInput.value = '';
            if (this.clearSearchButton) {
                this.clearSearchButton.style.display = 'none';
            }
        }
        
        this.updateSubmitButtonState(false);
        this.loadData();
    }

    updateSearchPlaceholder(type) {
        if (!this.searchInput) return;
        
        const placeholders = {
            'organization': 'Наименование/окпо/унп организации',
            'higher_organization': 'Наименование вышестоящей организации',
            'oblispolkom_gorispolkom': 'Наименование обл/горисполкома',
            'region': 'Наименование региона',
        };
        
        this.searchInput.placeholder = placeholders[type] || 'Поиск...';
        
        const searchLabel = document.getElementById('search-label');
        if (searchLabel) {
            const labels = {
                'organization': 'Поиск организации',
                'higher_organization': 'Поиск вышестоящей организации',
                'oblispolkom_gorispolkom': 'Поиск обл/горисполкома',
                'region': 'Поиск региона',
            };
            searchLabel.textContent = labels[type] || 'Поиск';
        }
    }

    updateSubmitButtonText() {
        if (!this.submitButton) return;
        
        const buttonTexts = {
            'organization': 'Сохранить организацию',
            'higher_organization': 'Сохранить вышестоящую организацию',
            'oblispolkom_gorispolkom': 'Сохранить обл/горисполком',
            'region': 'Сохранить регион',
        };
        
        const text = buttonTexts[this.selectedItemType] || 'Сохранить изменения';
        
        const btnTextSpan = this.submitButton.querySelector('.btn-text');
        if (btnTextSpan) {
            btnTextSpan.textContent = text;
        }
    }

    updateModalTitle(type) {
        const modalTitle = document.getElementById('modal-title');
        if (!modalTitle) return;
        
        const titles = {
            'organization': 'Выберите организацию',
            'higher_organization': 'Выберите вышестоящую организацию',
            'oblispolkom_gorispolkom': 'Выберите обл/горисполком',
            'region': 'Выберите регион',
        };
        
        modalTitle.textContent = titles[type] || 'Выберите элемент';
    }

    highlightActiveTypeButton() {
        this.typeButtons.forEach(btn => {
            if (btn.dataset.type === this.selectedItemType) {
                btn.classList.add('active');
            }
        });
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
            'higher_organization': plural ? 'вышестоящих организаций' : 'вышестоящая организация',
            'oblispolkom_gorispolkom': plural ? 'обл/горисполкомов' : 'обл/горисполком',
            'region': plural ? 'регионов' : 'регион',
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
                    <div style="font-size: 24px; margin-bottom: 12px;">⚠️</div>
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

    yesButton.addEventListener('click', function () {
        modalElement.classList.remove('active');
        if (modalElement._currentForm) {
            modalElement._currentForm.submit();
        }
    });

    noButton.addEventListener('click', function () {
        modalElement.classList.remove('active');
    });

    modalElement.addEventListener('click', function (event) {
        if (event.target === modalElement) {
            modalElement.classList.remove('active');
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modalElement.classList.contains('active')) {
            modalElement.classList.remove('active');
        }
    });
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
            endpoints: {
                organization: '/api/organizations',
                controlling_body: '/api/controlling-bodies'
            },
            ...options
        };

        this.currentEntityType = 'respondent';
        this.selectedItem = null;
        this.searchData = {
            organization: { page: 1, query: '', hasMore: false, loading: false },
            controlling_body: { page: 1, query: '', hasMore: false, loading: false }
        };
        this.debounceTimers = {};
        this.init();
    }

    init() {
        this.elements = {};
        this.getElementReferences();
        this.bindEvents();
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
        
        this.elements.entityBlocks = {
            respondent: document.getElementById('respondent-block'),
            auditor: document.getElementById('auditor-block')
        };
        
        this.elements.searchInputs = {
            respondent: document.getElementById('respondent-search'),
            auditor: document.getElementById('auditor-search')
        };
        
        this.elements.hiddenInputs = {
            respondent: document.getElementById('organization_id'),
            auditor: document.getElementById('controlling_body_id')
        };
        
        this.elements.dropdowns = {
            respondent: document.getElementById('organization-dropdown'),
            auditor: document.getElementById('controlling-body-dropdown')
        };
        
        this.elements.lists = {
            organization: document.getElementById('organization-list'),
            controlling_body: document.getElementById('controlling-body-list')
        };
        
        this.elements.loadings = {
            respondent: document.getElementById('organization-loading'),
            auditor: document.getElementById('controlling-body-loading')
        };
        
        this.elements.moreButtons = {
            respondent: document.getElementById('organization-more'),
            auditor: document.getElementById('controlling-body-more')
        };
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
        
        Object.keys(this.elements.searchInputs).forEach(type => {
            const input = this.elements.searchInputs[type];
            if (input) {
                input.addEventListener('input', (e) => this.handleSearchInput(e, type));
                input.addEventListener('focus', () => this.handleSearchFocus(type));
                input.addEventListener('blur', () => setTimeout(() => this.hideDropdown(type), 200));
                input.addEventListener('keydown', (e) => this.handleSearchKeydown(e, type));
            }
        });
        
        Object.keys(this.elements.moreButtons).forEach(type => {
            const button = this.elements.moreButtons[type];
            if (button) {
                const loadMoreBtn = button.querySelector('.load-more-btn');
                if (loadMoreBtn) {
                    loadMoreBtn.addEventListener('click', () => this.handleLoadMore(type));
                }
            }
        });
        
        if (this.elements.form) {
            this.elements.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
        
        document.addEventListener('click', (e) => this.handleDocumentClick(e));
        
        this.setupStep1Validation();
    }

    getApiType(type) {
        if (type === 'respondent') return 'organization';
        if (type === 'auditor') return 'controlling_body';
        return type;
    }

    getDataKey(type) {
        if (type === 'respondent') return 'organizations';
        if (type === 'auditor') return 'controlling_bodies';
        return `${type}s`;
    }

    getListKey(type) {
        if (type === 'respondent') return 'organization';
        if (type === 'auditor') return 'controlling_body';
        return type;
    }

    handleEntityTypeChange(e) {
        this.currentEntityType = e.target.value;
        
        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }
        
        this.updateStep3Content();
    }

    updateStep3Content() {
        const blocks = {
            respondent: 'respondent-block',
            auditor: 'auditor-block'
        };
        
        Object.values(blocks).forEach(blockId => {
            const block = document.getElementById(blockId);
            if (block) block.style.display = 'none';
        });
        
        const currentBlockId = blocks[this.currentEntityType];
        const currentBlock = document.getElementById(currentBlockId);
        if (currentBlock) {
            currentBlock.style.display = 'block';
        }
        
        this.selectedItem = null;
        this.resetHiddenFields();
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        
        this.clearSearchResults(this.currentEntityType);
        
        const searchInput = this.elements.searchInputs[this.currentEntityType];
        if (searchInput) {
            setTimeout(() => {
                searchInput.value = '';
                searchInput.focus();
            }, 100);
        }
    }

    selectItem(item, type) {
        document.querySelectorAll('.search-item').forEach(el => {
            el.classList.remove('selected');
        });
        
        const clickedElement = document.querySelector(`.search-item[data-id="${item.id}"]`);
        if (clickedElement) {
            clickedElement.classList.add('selected');
        }
        
        const input = this.elements.searchInputs[type];
        if (input) {
            input.value = item.name;
        }
        
        const hiddenInput = this.elements.hiddenInputs[type];
        if (hiddenInput) {
            hiddenInput.value = item.id;
        }
        
        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }
        
        this.hideDropdown(type);
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = false;
        }
        
        this.selectedItem = item;
    }

    handleFormSubmit(e) {
        e.preventDefault();
        
        if (!this.validateForm()) {
            alert('Пожалуйста, заполните все обязательные поля и выберите структуру');
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
        
        const entityType = this.currentEntityType;
        if (!entityType) return false;
        
        const hiddenInput = this.elements.hiddenInputs[entityType];
        if (!hiddenInput || !hiddenInput.value) return false;
        
        return true;
    }

    setupStep1Validation() {
        const requiredFields = ['#name', '#secondname', '#phone'];
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
        const requiredFields = ['secondname', 'name', 'phone'];
        return requiredFields.every(fieldId => {
            const input = document.getElementById(fieldId);
            return input && input.value.trim() !== '';
        });
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
                this.updateStep3Content();
                if (this.elements.step3) {
                    this.elements.step3.style.display = 'block';
                    if (this.elements.step1) this.elements.step1.classList.remove('active');
                    if (this.elements.step2) this.elements.step2.classList.remove('active');
                    this.elements.step3.classList.add('active');
                }
                break;
        }
    }

    handleSearchInput(e, type) {
        const query = e.target.value.trim();
        
        this.selectedItem = null;
        
        if (this.elements.hiddenInputs[type]) {
            this.elements.hiddenInputs[type].value = '';
        }
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        
        const apiType = this.getApiType(type);
        this.searchData[apiType].query = query;
        this.searchData[apiType].page = 1;
        
        if (this.debounceTimers[type]) {
            clearTimeout(this.debounceTimers[type]);
        }
        
        if (query.length >= this.config.minSearchLength) {
            this.debounceTimers[type] = setTimeout(() => {
                this.searchEntities(query, type, 1, false);
            }, this.config.debounceDelay);
        } else {
            this.hideDropdown(type);
            this.clearSearchResults(type);
        }
    }

    handleSearchFocus(type) {
        const apiType = this.getApiType(type);
        const query = this.searchData[apiType].query;
        const dropdown = this.elements.dropdowns[type];
        const listKey = this.getListKey(type);
        const list = this.elements.lists[listKey];
        
        if (query && query.length >= this.config.minSearchLength && 
            dropdown && list && list.children.length > 0) {
            dropdown.style.display = 'block';
        }
    }

    handleSearchKeydown(e, type) {
        if (e.key === 'Escape') {
            this.hideDropdown(type);
        }
    }

    handleLoadMore(type) {
        const apiType = this.getApiType(type);
        const data = this.searchData[apiType];
        if (data.hasMore && data.query && !data.loading) {
            data.page += 1;
            this.searchEntities(data.query, type, data.page, true);
        }
    }

    handleDocumentClick(e) {
        Object.keys(this.elements.searchInputs).forEach(type => {
            const input = this.elements.searchInputs[type];
            const dropdown = this.elements.dropdowns[type];
            
            if (input && dropdown && 
                !input.contains(e.target) && 
                !dropdown.contains(e.target)) {
                this.hideDropdown(type);
            }
        });
    }

    async searchEntities(query, type, page = 1, append = false) {
        const apiType = this.getApiType(type);
        
        if (this.searchData[apiType].loading) return;
        
        this.searchData[apiType].loading = true;
        
        if (!append) {
            this.showLoading(type, true);
            this.clearSearchResults(type);
        }
        
        try {
            const endpoint = this.config.endpoints[apiType] || `/api/${apiType}`;
            const url = `${endpoint}?q=${encodeURIComponent(query)}&page=${page}`;
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.handleSearchResponse(data, type, append);
        } catch (error) {
            console.error(`Error fetching ${type}:`, error);
            this.showError(type, error.message);
        } finally {
            this.searchData[apiType].loading = false;
            this.showLoading(type, false);
        }
    }

    handleSearchResponse(data, type, append = false) {
        const listKey = this.getListKey(type);
        const list = this.elements.lists[listKey];
        const dropdown = this.elements.dropdowns[type];
        const moreButton = this.elements.moreButtons[type];
        
        if (!list || !dropdown) {
            console.error(`Elements not found for ${type}:`, { list, dropdown });
            return;
        }
        
        const dataKey = this.getDataKey(type);
        const items = data[dataKey] || [];
        const apiType = this.getApiType(type);
        
        if (!append) {
            list.innerHTML = '';
        }
        
        if (items.length > 0) {
            items.forEach(item => {
                const itemElement = this.createListItem(item, apiType);
                list.appendChild(itemElement);
            });
            
            this.searchData[apiType].hasMore = data.has_next || false;
            if (moreButton) {
                moreButton.style.display = data.has_next ? 'block' : 'none';
            }
            
            dropdown.style.display = 'block';
        } else if (!append) {
            list.innerHTML = '<div class="no-results">Ничего не найдено</div>';
            dropdown.style.display = 'block';
            if (moreButton) moreButton.style.display = 'none';
        }
    }

    createListItem(item, type) {
        const div = document.createElement('div');
        div.className = 'search-item';
        div.dataset.id = item.id;
        
        switch(type) {
            case 'organization':
                div.innerHTML = `
                    <div class="item-name">${this.escapeHtml(item.name)}</div>
                    <div class="item-details">
                        <span class="item-okpo">ОКПО: ${this.escapeHtml(item.okpo || '—')}</span>
                        <span class="item-ynp">УНП: ${this.escapeHtml(item.ynp || '—')}</span>
                        ${item.ministry ? `<span class="item-ministry">Министерство: ${this.escapeHtml(item.ministry)}</span>` : ''}
                    </div>
                `;
                break;
            case 'controlling_body':
                div.innerHTML = `
                    <div class="item-name">${this.escapeHtml(item.name)}</div>
                    <div class="item-details">
                        <span class="item-type">${this.escapeHtml(item.type || 'Контролирующий орган')}</span>
                    </div>
                `;
                break;
        }
        
        div.addEventListener('click', () => {
            this.selectItem(item, type === 'organization' ? 'respondent' : 'auditor');
        });
        
        return div;
    }

    showLoading(type, show) {
        const loading = this.elements.loadings[type];
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    clearSearchResults(type) {
        const listKey = this.getListKey(type);
        const list = this.elements.lists[listKey];
        if (list) {
            list.innerHTML = '';
        }
        const moreButton = this.elements.moreButtons[type];
        if (moreButton) {
            moreButton.style.display = 'none';
        }
    }

    hideDropdown(type) {
        const dropdown = this.elements.dropdowns[type];
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }

    showError(type, message = 'Ошибка загрузки данных') {
        const listKey = this.getListKey(type);
        const list = this.elements.lists[listKey];
        const dropdown = this.elements.dropdowns[type];
        
        if (list && dropdown) {
            list.innerHTML = `<div class="error">${message}</div>`;
            dropdown.style.display = 'block';
        }
        
        this.showLoading(type, false);
    }

    resetHiddenFields() {
        Object.values(this.elements.hiddenInputs).forEach(input => {
            if (input) input.value = '';
        });
    }

    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    destroy() {
        Object.values(this.debounceTimers).forEach(timer => {
            if (timer) clearTimeout(timer);
        });
    }

    reset() {
        this.currentEntityType = 'respondent';
        this.selectedItem = null;
        this.resetHiddenFields();
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        
        Object.keys(this.searchData).forEach(type => {
            this.searchData[type] = { 
                page: 1, 
                query: '', 
                hasMore: false, 
                loading: false 
            };
        });
        
        Object.values(this.elements.searchInputs).forEach(input => {
            if (input) input.value = '';
        });
        
        this.goToStep(1);
    }
}

class TicketInfo {
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
                        <span class="ticket-info-label">Роль</span>
                        <span class="ticket-info-value">${data.is_owner ? 'Система' : 'Аудитор'}</span>
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
                            <a href="tel:${data.user_phone}" class="ticket-info-link">
                                ${data.user_phone || '---'}
                            </a>
                        </span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Статус сообщения</span>
                        <span class="ticket-info-value ticket-info-status ${data.luck ? 'success' : 'error'}">
                            ${data.luck ? '✓ Успешно' : '✗ Ошибка'}
                        </span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Время отправки</span>
                        <span class="ticket-info-value">${time}</span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Дата отправки</span>
                        <span class="ticket-info-value">${date || 'Не указана'}</span>
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
        if (panelContent) panelContent.style.animation = 'scaleOut 0.3s ease';
        
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

window.TicketInfo = TicketInfo;

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
            Notifications.init();
        }, 60000);
    }

    if (document.querySelectorAll('.tickets-container')) {
        window.TicketInfo = TicketInfo;
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

if (document.getElementById('dots-profile-org')) {
    initDropdownMenu('dots-profile-org', 'menu-profile-org');
}

if (document.getElementById('dots-profile-user')) {
    initDropdownMenu('dots-profile-user', 'menu-profile-user');
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
    
    const bgGrid = document.querySelector('.bg-grid');
    
    if (bgGrid) {
        window.addEventListener('mousemove', (e) => {
            const x = (e.clientX / window.innerWidth) * 20;
            const y = (e.clientY / window.innerHeight) * 20;
            
            bgGrid.style.transform = `translate(${x}px, ${y}px)`;
        });
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