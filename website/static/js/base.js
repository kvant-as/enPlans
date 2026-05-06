

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
    const DISPLAY_TIME = 10000; 

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

        alertBox.innerHTML = `
            <img src="${imgSrc}" class="alert-icon" alt="">
            <div class="p_message_cont">
                <p>${msgObj.msg}</p>
            </div>
            <button class="alert-close">&times;</button>
        `;

        alertBox.querySelector('.alert-close').addEventListener('click', e => {
            e.stopPropagation();
            removeMessage(alertBox, msgObj);
        });

        alertBox.addEventListener('click', () => {
            container.querySelectorAll('.custom-alert').forEach((el, index) => {
                if (index === container.children.length - 1) {
                    el.classList.toggle('expanded');
                    el.classList.toggle('collapsed');
                } else {
                    el.classList.remove('expanded');
                    el.classList.add('collapsed');
                }
            });
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

// notif in header modal load
const Notifications = {
    notifListEl: null,
    notifCountEl: null,
    markAllBtn: null,

    async load() {
        try {
            const response = await fetch("/api/notifications");
            const data = await response.json();
            this.render(data);
        } catch (err) {
            console.error("Ошибка загрузки уведомлений:", err);
        }
    },

    render(data) {
        this.notifListEl.innerHTML = ""; 

        if (!data || data.length === 0) {
            this.notifListEl.innerHTML = "<div class='notif empty'>Нет уведомлений</div>";
            this.hideCounter();
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

            notif.innerHTML = `
                <div class="notif-message">${n.message}</div>
                <div class="notif-time">${n.created_at}</div>
                <div class="notif-divider-line"></div>
            `;
            this.notifListEl.appendChild(notif);
        });

        this.updateCounter(unreadCount);
    },

    updateCounter(count) {
        if (count > 0) {
            this.notifCountEl.innerText = count;
            this.notifCountEl.classList.add("active");
        } else {
            this.notifCountEl.classList.remove("active");
            this.notifCountEl.innerText = "";
        }
    },

    hideCounter() {
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
                },
                body: "{}"
            });

            if (!response.ok) throw new Error("Ошибка запроса");

            const result = await response.json();
            console.log(result.message);

            this.load();
        } catch (err) {
            console.error("Ошибка при отметке уведомлений:", err);
        }
    },

    init() {
        this.notifListEl = document.getElementById("notifList");
        this.notifCountEl = document.getElementById("notifCount");
        this.markAllBtn  = document.getElementById("markAllRead");

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
        // Обработчик отправки формы повторной отправки кода
        this.resendForm.addEventListener('submit', (e) => {
            if (this.resendBtn.classList.contains('disabled')) {
                e.preventDefault();
                return;
            }
        });
        
        // Настройка автоперехода между полями ввода кода
        this.setupCodeInputs();
        
        // Очищаем localStorage при успешной отправке основной формы
        const mainForm = document.querySelector('.auth-form');
        if (mainForm) {
            mainForm.addEventListener('submit', () => {
                localStorage.removeItem('codeResendEndTime');
            });
        }
    }
    
    // Публичные методы для внешнего управления
    destroy() {
        this.clearTimer();
        localStorage.removeItem('codeResendEndTime');
        
        // Удаляем все обработчики событий
        this.resendForm.removeEventListener('submit', this.handleResendSubmit);
        
        // Восстанавливаем исходное состояние кнопки
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

// Класс для управления несколькими экземплярами таймеров
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

// language modal
function initLanguageDropdown() {
  const button = document.querySelector('.language-button');
  const dropdown = document.querySelector('.language-dropdown-content');

  if (!button || !dropdown) return;

  button.addEventListener('click', function(e) {
    e.stopPropagation();
    dropdown.classList.toggle('show');
  });

  window.addEventListener('click', function() {
    if (dropdown.classList.contains('show')) {
      dropdown.classList.remove('show');
    }
  });
}

// dropdown Module
const customDropdown = {
    init: function() {
        this.dropdowns = document.querySelectorAll('.custom-dropdown');
        
        if (this.dropdowns.length === 0) return;
        
        this.setupDropdowns();
        this.setupDocumentClick();
        this.setupFilterListeners();
    },
    
    setupDropdowns: function() {
        this.dropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.dropdown-toggle');
            const menu = dropdown.querySelector('.dropdown-menu-filter');
            const items = dropdown.querySelectorAll('.dropdown-item');
            const selectedOption = dropdown.querySelector('.selected-option');
            
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown(dropdown);
            });
            
            items.forEach(item => {
                item.addEventListener('click', () => {
                    this.selectItem(item, selectedOption);
                    this.closeDropdown(dropdown);
                });
            });
        });
    },
    
    setupFilterListeners: function() {
        this.dropdowns.forEach(dropdown => {
            const items = dropdown.querySelectorAll('.dropdown-item');
            const filterType = dropdown.getAttribute('data-filter-type');
            
            items.forEach(item => {
                item.addEventListener('click', () => {
                    const value = item.getAttribute('data-value');
                    this.submitFilterForm(filterType, value);
                });
            });
        });
    },
    
    submitFilterForm: function(filterType, value) {
        const form = document.getElementById(filterType + 'Filter');
        const input = document.getElementById(filterType + 'Input');
        
        if (form && input) {
            input.value = value;
            
            const urlParams = new URLSearchParams(window.location.search);
            ['status', 'year'].forEach(param => {
                if (param !== filterType && urlParams.has(param)) {
                    const hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = param;
                    hiddenInput.value = urlParams.get(param);
                    form.appendChild(hiddenInput);
                }
            });
            
            form.submit();
        }
    },
    
    setupDocumentClick: function() {
        document.addEventListener('click', () => {
            this.closeAllDropdowns();
        });
    },
    
    toggleDropdown: function(dropdown) {
        this.closeAllDropdowns();
        dropdown.classList.toggle('active');
    },
    
    closeDropdown: function(dropdown) {
        dropdown.classList.remove('active');
    },
    
    closeAllDropdowns: function() {
        this.dropdowns.forEach(dropdown => {
            this.closeDropdown(dropdown);
        });
    },
    
    selectItem: function(item, selectedOption) {
        selectedOption.textContent = item.textContent;
    }
};

// status row
const STATUS_CONFIG = {
  'plan-cont-redac': {
    width: '20%',
    color: 'var(--color-redaced)'
  },
  'plan-cont-control': {
    width: '40%', 
    color: 'var(--color-controled)'
  },
  'plan-cont-sent': {
    width: '60%',
    color: 'var(--color-sented)'
  },
  'plan-cont-eror': {
    width: '80%',
    color: 'var(--color-erorsed)'
  },
  'plan-cont-sub': {
    width: '100%',
    color: 'var(--color-submited)'
  }
};

const elements = {
  planConts: document.querySelectorAll('.plan-cont'),
  progressLine: document.querySelector('.progress-line-active'),
  dots: document.querySelectorAll('.status-dot')
};

const checkElements = () => {
  if (!elements.planConts.length || !elements.progressLine || !elements.dots.length) {
    console.warn('Не найдены необходимые элементы для прогресс-бара');
    return false;
  }
  return true;
};

const setupEventHandlers = () => {
  elements.planConts.forEach(planCont => {
    planCont.addEventListener('mouseenter', handleMouseEnter);
    planCont.addEventListener('mouseleave', handleMouseLeave);
  });
};

const handleMouseEnter = (event) => {
  const planCont = event.currentTarget;
  
  for (const [className, config] of Object.entries(STATUS_CONFIG)) {
    if (planCont.classList.contains(className)) {
      updateProgressBar(config);
      updateDots(className);
      break;
    }
  }
};

const updateProgressBar = (config) => {
  elements.progressLine.style.width = config.width;
  elements.progressLine.style.background = config.color;
};

const updateDots = (activeClass) => {
  const activeIndex = Object.keys(STATUS_CONFIG).indexOf(activeClass);
  const activeColor = STATUS_CONFIG[activeClass].color;
  
  elements.dots.forEach((dot, index) => {
    dot.style.background = index <= activeIndex ? activeColor : 'var(--border-color)';
  });
};

const handleMouseLeave = () => {
  elements.progressLine.style.width = '0';
  elements.dots.forEach(dot => {
    dot.style.background = 'var(--border-color)';
  });
};

const initStatusProgress = () => {
  if (!checkElements()) return;
  
  setupEventHandlers();

  return () => {
    elements.planConts.forEach(planCont => {
      planCont.removeEventListener('mouseenter', handleMouseEnter);
      planCont.removeEventListener('mouseleave', handleMouseLeave);
    });
  };
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

// event modal
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

  submitForm() {
  }

  close() {
    this.modal.style.display = 'none';
  }

  resetForm() {
    this.stepEls.forEach((el, i) => el.style.display = i === 0 ? 'block' : 'none');
    this.currentStep = 1;
    this.updateProgressBar();
  }
}

/* numbers + dot only */
var numeric_input = document.querySelectorAll('.app-numeric-input');
numeric_input.forEach(function(input) {
    input.addEventListener('input', function(event) {
        var oldValue = this.value;
        var selectionStart = this.selectionStart;
        var selectionEnd = this.selectionEnd;
        
        var value = oldValue.replace(/[^\d.]/g, '');
        var parts = value.split('.');
        if (parts.length > 1) {
            value = parts[0] + '.' + parts[1].slice(0, 3);
        }
        
        if (value.startsWith('0') && value.length > 1 && value[1] !== '.') {
            value = value.substring(1);
        }

        if (!value.includes('.')) {
            value += '.000';
        }

        var oldDotIndex = oldValue.indexOf('.');
        var newDotIndex = value.indexOf('.');

        this.value = value;

        if (selectionEnd - selectionStart > 1) {
            this.setSelectionRange(selectionEnd, selectionEnd);
        } else if (selectionStart <= oldDotIndex) {
            var cursorPos = selectionStart + (newDotIndex - oldDotIndex);
            this.setSelectionRange(cursorPos, cursorPos);
        } else {
            this.setSelectionRange(selectionStart, selectionStart);
        }
    });

    input.addEventListener('focus', function(event) {
        if (this.value === '') {
            this.value = '0.000';
        }

        var dotIndex = this.value.indexOf('.');
        if (dotIndex !== -1) {
            this.setSelectionRange(dotIndex, dotIndex);
        }
    });

    input.addEventListener('click', function(event) {
        this.select();
    });
});
/* end numbers + dot only */

/* numbers + dot + minys only */
var numeric_input_negative = document.querySelectorAll('.app-numeric-input-negative');
numeric_input_negative.forEach(function(input) {
    input.addEventListener('input', function(event) {
        var oldValue = this.value;
        var selectionStart = this.selectionStart;
        var selectionEnd = this.selectionEnd;
        
        var value = oldValue.replace(/[^\d.-]/g, '');
        
        var minusCount = (value.match(/-/g) || []).length;
        if (minusCount > 1) {
            value = value.replace(/-/g, '');
            value = '-' + value;
        } else if (minusCount === 1 && !value.startsWith('-')) {
            value = value.replace(/-/g, '');
            value = '-' + value;
        }
        
        var parts = value.split('.');
        if (parts.length > 1) {
            value = parts[0] + '.' + parts[1].slice(0, 3);
        }
        
        if (!value.startsWith('-')) {
            if (value.startsWith('0') && value.length > 1 && value[1] !== '.') {
                value = value.substring(1);
            }
        } 
        else {
            if (value.startsWith('-0') && value.length > 2 && value[2] !== '.') {
                value = '-' + value.substring(2);
            }
        }

        if (!value.includes('.')) {
            if (value === '' || value === '-') {
                value += '0.000';
            } else {
                value += '.000';
            }
        }

        var oldDotIndex = oldValue.indexOf('.');
        var newDotIndex = value.indexOf('.');

        this.value = value;

        if (selectionEnd - selectionStart > 1) {
            this.setSelectionRange(selectionEnd, selectionEnd);
        } else if (selectionStart <= oldDotIndex) {
            var cursorPos = selectionStart + (newDotIndex - oldDotIndex);
            this.setSelectionRange(cursorPos, cursorPos);
        } else {
            this.setSelectionRange(selectionStart, selectionStart);
        }
    });

    input.addEventListener('focus', function(event) {
        if (this.value === '') {
            this.value = '0.000';
        }

        var dotIndex = this.value.indexOf('.');
        if (dotIndex !== -1) {
            this.setSelectionRange(dotIndex, dotIndex);
        }
    });

    input.addEventListener('click', function(event) {
        this.select();
    });
});
/* end numbers + dot + minys only */

class DirectionsTable {
    constructor({ searchSelector, tableSelector, hiddenInputSelector, nextButtonSelector }) {
        this.searchInput = document.querySelector(`[data-action="${searchSelector}"]`);
        this.table = document.querySelector(`[data-action="${tableSelector}"] tbody`);
        this.hiddenInput = document.querySelector(`[data-action="${hiddenInputSelector}"]`);
        this.nextButton = document.querySelector(`[data-action="${nextButtonSelector}"]`);
        this.selectedId = null;

        if (!this.searchInput || !this.table) return;

        this.noInfoRow = this.createNoInfoRow();
        this.table.appendChild(this.noInfoRow);
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
        cell.colSpan = 6;
        cell.textContent = "Нет похожей информации";
        cell.style.textAlign = "center";
        cell.style.padding = "20px";
        cell.style.paddingLeft = "70px";
        noResultsRow.appendChild(cell);
        return noResultsRow;
    }

    initSearch() {
        this.searchInput.addEventListener("input", () => {
            const filter = this.searchInput.value.toLowerCase();
            const rows = this.table.querySelectorAll("tr:not(.no-results-row)");
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
        this.table.addEventListener("click", (e) => {
            const row = e.target.closest("tr");
            if (!row || row.classList.contains("no-results-row")) return;

            this.table.querySelectorAll("tr").forEach(r => r.classList.remove("selected"));
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

class TableContextMenu {
    constructor(tableId, menuId, options = {}) {
        this.table = document.getElementById(tableId);
        this.menu = document.getElementById(menuId);
        this.selectedRow = null;
        
        // Кнопки в контекстном меню
        this.contextDeleteButton = options.contextDeleteButtonId ? document.getElementById(options.contextDeleteButtonId) : null;
        this.contextEditButton = options.contextEditButtonId ? document.getElementById(options.contextEditButtonId) : null;
        
        // Кнопки над таблицей
        this.tableDeleteButton = options.tableDeleteButtonId ? document.getElementById(options.tableDeleteButtonId) : null;
        this.tableEditButton = options.tableEditButtonId ? document.getElementById(options.tableEditButtonId) : null;
        
        // Callback функции
        this.editCallback = options.editCallback || null;
        this.removeCallback = options.removeCallback || null;
        this.removeUrlTemplate = options.removeUrlTemplate || null;
        
        // Параметры для неизменяемых строк
        this.immutableCodes = options.immutableCodes || []; // Коды, которые нельзя изменять/удалять
        this.immutableEditCodes = options.immutableEditCodes || []; // Коды, которые нельзя редактировать
        this.immutableDeleteCodes = options.immutableDeleteCodes || []; // Коды, которые нельзя удалять
        this.codeColumnIndex = options.codeColumnIndex || 0; // Индекс столбца с кодом
        this.hideCodeColumn = options.hideCodeColumn !== false; // Скрывать ли столбец с кодом

        if (!this.table || !this.menu) return;
        this.init();
    }

    init() {
        if (this.hideCodeColumn) {
            this.hideCodeColumnInTable();
        }

        this.table.querySelectorAll('tbody.rows tr.menu-row').forEach(row => {
            row.addEventListener('contextmenu', (event) => this.onRowRightClick(event, row));
            row.addEventListener('click', (event) => this.onRowLeftClick(event, row));
        });
        
        document.addEventListener('click', (event) => {
            if (!this.menu.contains(event.target)) {
                this.hideMenu();
            }
        });

        // Обработчики для кнопок в контекстном меню
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

        // Обработчики для кнопок над таблицей
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
        
        const allButtons = [
            this.contextEditButton,
            this.contextDeleteButton,
            this.tableEditButton,
            this.tableDeleteButton
        ];
        
        allButtons.forEach(button => {
            if (button) {
                if (!isActive) {
                    button.classList.add('btn-disabled');
                } else {
                    const isEditButton = button === this.contextEditButton || button === this.tableEditButton;
                    const isDeleteButton = button === this.contextDeleteButton || button === this.tableDeleteButton;
                    
                    if (isEditButton && isEditDisabled) {
                        button.classList.add('btn-disabled');
                    } else if (isEditButton && !isEditDisabled) {
                        button.classList.remove('btn-disabled');
                    } else if (isDeleteButton && isDeleteDisabled) {
                        button.classList.add('btn-disabled');
                    } else if (isDeleteButton && !isDeleteDisabled) {
                        button.classList.remove('btn-disabled');
                    }
                }
            }
        });
    }

    onRowLeftClick(event, row) {
        event.stopPropagation();
        
        if (row.classList.contains('active-row')) {
            row.classList.remove('active-row');
            this.selectedRow = null;
        } else {
            if (this.selectedRow && this.selectedRow !== row) {
                this.selectedRow.classList.remove('active-row');
            }
            row.classList.add('active-row');
            this.selectedRow = row;
        }

        const editDirectionModal = document.getElementById('EditDirectionModal');
        if (editDirectionModal) {
            Edit_econmeasure_modal();
        }
        
        const editEventModal = document.getElementById('EditEventModal');
        if (editEventModal) {
            Edit_econexece_modal();
        }

        const editIndicatorModal = document.getElementById('EditIndicatorModal');
        if (editIndicatorModal) {
            Edit_indicator_modal();
        }

        this.updateButtonsState();
        this.hideContextMenu();
    }

    onRowRightClick(event, row) {
        event.preventDefault();
        event.stopPropagation();

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

        const editDirectionModal = document.getElementById('EditDirectionModal');
        if (editDirectionModal) {
            Edit_econmeasure_modal();
        }
        
        const editEventModal = document.getElementById('EditEventModal');
        if (editEventModal) {
            Edit_econexece_modal();
        }

        const editIndicatorModal = document.getElementById('EditIndicatorModal');
        if (editIndicatorModal) {
            Edit_indicator_modal();
        }
        
        this.updateButtonsState();
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

        const yesBtn = modal.querySelector('#confirmYesdelete');
        const noBtn = modal.querySelector('#confirmNodelete');

        modal.classList.add('active');

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

        window.onclick = (event) => {
            if (event.target === modal) {
                modal.classList.remove('active');
            }
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

function initExportPage() {
    const form = document.getElementById("exportForm");
    const formatInput = document.getElementById("selectedFormat");
    const checkboxes = document.querySelectorAll('input[name="ids"]');
    const exportBtn = document.getElementById("exportBtn");
    const selectAllBtn = document.getElementById("selectAllBtn");

    function updateButtonState() {
        const formatSelected = !!formatInput.value;
        const planSelected = Array.from(checkboxes).some(cb => cb.checked);
        exportBtn.disabled = !(formatSelected && planSelected);

        form.action = formatSelected ? `/export-to/${formatInput.value}` : "";
    }

    document.querySelectorAll(".choose-conteiner").forEach(item => {
        item.addEventListener("click", () => {
            document.querySelectorAll(".choose-conteiner").forEach(el => el.classList.remove("active"));
            item.classList.add("active");
            formatInput.value = item.dataset.format;
            updateButtonState();
        });
    });

    if (selectAllBtn) {
        selectAllBtn.addEventListener("change", () => {
            checkboxes.forEach(cb => cb.checked = selectAllBtn.checked);
            updateButtonState();
        });
    }

    checkboxes.forEach(cb => cb.addEventListener("change", updateButtonState));

    updateButtonState();
}

function Edit_econmeasure_modal() {
    const EditDirectionsModal = document.getElementById('EditDirectionModal');
    if (!EditDirectionsModal) {
        console.error('Модальное окно не найдено');
        return;
    }

    var activeRow = document.querySelector('.rows .active-row');
    if (!activeRow) {
        // console.error('Активная строка не найдена');
        return;
    }

    var idEvent = activeRow.getAttribute('data-id');
    if (!idEvent) {
        console.error('ID мероприятия не найден');
        return;
    }

    showLoadingIndicator(true);

    fetch(`/get-econmeasure/${idEvent}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка сети: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            setValueIfExists('change-year-econ', data.year_econ || '');
            setValueIfExists('change-estim-econ', data.estim_econ || '');
            
            var form = document.getElementById('editEconForm');
            if (form) {
                form.action = `/edit-econmeasure/${idEvent}`;
            } else {
                console.error('Форма editEconForm не найдена');
            }
        })
        .catch(error => {
            console.error('Error fetching econexece data:', error);
            alert('Ошибка при загрузке данных мероприятия: ' + error.message);
        })
        .finally(() => {
            showLoadingIndicator(false);
        });
}

function Edit_econexece_modal(){
    const EditEventModal = document.getElementById('EditEventModal');
    if (!EditEventModal) {
        console.error('Модальное окно не найдено');
        return;
    }

    var activeRow = document.querySelector('.rows .active-row');
    if (!activeRow) {
        // console.error('Активная строка не найдена');
        return;
    }

    var idEvent = activeRow.getAttribute('data-id');
    if (!idEvent) {
        console.error('ID мероприятия не найден');
        return;
    }

    showLoadingIndicator(true);

    fetch(`/get-econexece/${idEvent}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка сети: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            setValueIfExists('change-name-edit-model', data.name || '');
            setValueIfExists('change-Volume-edit-model', data.Volume || '');
            setValueIfExists('change-EffTut-edit-model', data.EffTut || '');
            setValueIfExists('change-EffRub-edit-model', data.EffRub || '');
            setValueIfExists('change-ExpectedQuarter-edit-model', data.ExpectedQuarter || '');
            setValueIfExists('change-EffCurrYear-edit-model', data.EffCurrYear || '');
            setValueIfExists('change-Payback-edit-model', data.Payback || '');
            setValueIfExists('change-VolumeFin-edit-model', data.VolumeFin || '');
            setValueIfExists('change-BudgetState-edit-model', data.BudgetState || '');
            setValueIfExists('change-BudgetRep-edit-model', data.BudgetRep || '');
            setValueIfExists('change-BudgetLoc-edit-model', data.BudgetLoc || '');
            setValueIfExists('change-BudgetOther-edit-model', data.BudgetOther || '');
            setValueIfExists('change-MoneyOwn-edit-model', data.MoneyOwn || '');
            setValueIfExists('change-MoneyLoan-edit-model', data.MoneyLoan || '');
            setValueIfExists('change-MoneyOther-edit-model', data.MoneyOther || '');
            
            var form = document.getElementById('editEconexeceForm');
            if (form) {
                form.action = `/edit-econexeces/${idEvent}`;
            } else {
                console.error('Форма editEconexeceForm не найдена');
            }
        })
        .catch(error => {
            console.error('Error fetching econexece data:', error);
            alert('Ошибка при загрузке данных мероприятия: ' + error.message);
        })
        .finally(() => {
            showLoadingIndicator(false);
        });
}

function Edit_indicator_modal(){
    const EditIndicatorModal = document.getElementById('EditIndicatorModal');
    if (!EditIndicatorModal) {
        console.error('Модальное окно EditIndicatorModal не найдено');
        return;
    }

    var activeRow = document.querySelector('.rows .active-row');
    if (!activeRow) {
        return;
    }

    var idIndicator = activeRow.getAttribute('data-id');
    if (!idIndicator) {
        console.error('ID не найден');
        return;
    }

    // Получаем значение Group - несколько вариантов поиска для надежности
    let groupValue = '';
    
    // Вариант 1: Ищем по data-атрибуту (если добавили data-group)
    const groupDataCell = activeRow.querySelector('td[data-group]');
    if (groupDataCell) {
        groupValue = groupDataCell.getAttribute('data-group');
    } 
    // Вариант 2: Ищем по классу (если добавили class="group-cell")
    else {
        const groupClassCell = activeRow.querySelector('td.group-cell');
        if (groupClassCell) {
            groupValue = groupClassCell.textContent.trim();
        }
        // Вариант 3: Ищем по стилю display: none (оригинальный способ)
        else {
            const groupStyleCell = activeRow.querySelector('td[style*="display: none"]');
            if (groupStyleCell) {
                groupValue = groupStyleCell.textContent.trim();
            }
        }
    }

    const isGroup5 = groupValue === '5.0';
    const isGroup6 = groupValue === '6.0';
    
    // Для групп 5 и 6 показываем только последнее поле
    const isSpecialGroup = isGroup5 || isGroup6;

    // Управляем видимостью элементов
    const qYearCurrNoDisplay = document.getElementById('QYearCurr-edit-nodisplay');
    const qYearPrevNoDisplay = document.getElementById('QYearPrev-edit-nodisplay');
    
    // Находим input поля внутри этих контейнеров
    const qYearCurrInput = qYearCurrNoDisplay ? qYearCurrNoDisplay.querySelector('input') : null;
    const qYearPrevInput = qYearPrevNoDisplay ? qYearPrevNoDisplay.querySelector('input') : null;
    
    // Скрываем поля QYearPrev и QYearCurr для групп 5 и 6
    if (qYearCurrNoDisplay) {
        qYearCurrNoDisplay.style.display = isSpecialGroup ? 'none' : '';
    }
    
    if (qYearPrevNoDisplay) {
        qYearPrevNoDisplay.style.display = isSpecialGroup ? 'none' : '';
    }

    // Управляем обязательностью полей
    if (qYearCurrInput) {
        if (isSpecialGroup) {
            qYearCurrInput.removeAttribute('required');
        } else {
            qYearCurrInput.setAttribute('required', 'required');
        }
    }
    
    if (qYearPrevInput) {
        if (isSpecialGroup) {
            qYearPrevInput.removeAttribute('required');
        } else {
            qYearPrevInput.setAttribute('required', 'required');
        }
    }

    showLoadingIndicator(true);

    fetch(`/get-indicator/${idIndicator}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка сети: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            // Для групп 5 и 6 не заполняем QYearPrev и QYearCurr
            if (!isSpecialGroup) {
                setValueIfExists('QYearPrev-edit', data.QYearPrev ? (data.QYearPrev / data.CoeffToTut).toFixed(3) : '');
                setValueIfExists('QYearCurr-edit', data.QYearCurr ? (data.QYearCurr / data.CoeffToTut).toFixed(3) : '');
            } else {
                // Очищаем значения для групп 5 и 6
                setValueIfExists('QYearPrev-edit', '');
                setValueIfExists('QYearCurr-edit', '');
            }
            
            // QYearNext заполняем всегда
            setValueIfExists('QYearNext-edit', data.QYearNext ? (data.QYearNext / data.CoeffToTut).toFixed(3) : '');
            
            const predictionElements = document.querySelectorAll('.prediction-value');
            predictionElements.forEach(element => {
                if (data.CoeffToTut) {
                    element.dataset.multiplier = data.CoeffToTut;
                }
            });

            var form = document.getElementById('editIndicatorForm');
            if (form) {
                form.action = `/edit-indicator/${idIndicator}`;
            } else {
                console.error('Форма не найдена');
            }
        })
        .catch(error => {
            console.error('Error fetching econexece data:', error);
            alert('Ошибка при загрузке данных: ' + error.message);
        })
        .finally(() => {
            showLoadingIndicator(false);
        });
}

function setValueIfExists(elementId, value) {
    var element = document.getElementById(elementId);
    if (element) {
        element.value = value;
        // console.log(`Установлено значение для ${elementId}:`, value);
    } else {
        console.error(`Элемент с ID '${elementId}' не найден`);
    }
}

function showLoadingIndicator(show) {
    var loader = document.getElementById('loading-indicator');
    if (loader) {
        loader.style.display = show ? 'block' : 'none';
    }
}

function initColumnResize() {
    const table = document.querySelector('.main-table');
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
        if (isResizing) {
            const newWidth = startWidth + (e.clientX - startX);
            currentTh.style.width = newWidth + 'px';
            currentTh.style.minWidth = newWidth + 'px';
        }
    });

    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = '';
        }
    });
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
            
            // API endpoints
            organizationsApiUrl: '/api/organizations',
            ministriesApiUrl: '/api/ministries',
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

        // if (!this.searchInput || !this.tableBody || !this.selectedOrgInput) {
        //     console.error('MultiTypeSearchManager: Не найдены необходимые элементы');
        //     return;
        // }

        this.bindEvents();
        this.updateSubmitButtonState();
        this.loadData();
    }

    bindEvents() {
        let debounceTimer;

        // Обработка поиска
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

        // Очистка поиска
        if (this.clearSearchButton) {
            this.clearSearchButton.addEventListener('click', () => {
                this.searchInput.value = '';
                this.clearSearchButton.style.display = 'none';
                this.currentPage = 1;
                this.currentQuery = '';
                this.loadData();
            });
        }

        // Выбор элемента в таблице
        this.tableBody.addEventListener('click', (e) => {
            const row = e.target.closest('tr');
            if (row && row.dataset.id) {
                this.selectItem(row);
            }
        });

        // Переключение типа (организации/министерства/регионы)
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

        // Пагинация: предыдущая страница
        if (this.prevPageBtn) {
            this.prevPageBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.loadData();
                }
            });
        }

        // Пагинация: следующая страница
        if (this.nextPageBtn) {
            this.nextPageBtn.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.loadData();
                }
            });
        }

        // Отправка формы
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
                
                console.log('Отправка формы:', {
                    id_org: this.selectedItemId,
                    item_type: this.selectedItemType
                });
            });
        }
    }

    async loadData() {
        try {
            this.showLoading();

            let apiUrl, dataKey;
            
            // Определяем API endpoint и ключ данных
            switch(this.selectedItemType) {
                case 'organization':
                    apiUrl = this.config.organizationsApiUrl;
                    dataKey = 'organizations';
                    break;
                case 'ministry':
                    apiUrl = this.config.ministriesApiUrl;
                    dataKey = 'ministrys'; // Ваш API использует 'ministrys'
                    break;
                case 'region':
                    apiUrl = this.config.regionsApiUrl;
                    dataKey = 'regions';
                    break;
                default:
                    apiUrl = this.config.organizationsApiUrl;
                    dataKey = 'organizations';
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
            
            const items = data[dataKey] || [];
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

    renderItems(items) {
        if (!items || items.length === 0) {
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; padding: 40px; color: #6b7280;">
                        <div style="font-size: 48px; margin-bottom: 16px;">📭</div>
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
            
            // Проверяем, выбран ли этот элемент
            if (this.selectedItemId == item.id) {
                row.classList.add('selected');
            }
            
            let html = `<td style="display: none;">${this.escapeHtml(item.id)}</td>`;
            
            // Разный рендеринг для разных типов
            switch(this.selectedItemType) {
                case 'organization':
                    html += `
                        <td>${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;">${this.escapeHtml(item.okpo || '-')}</td>
                    `;
                    break;
                case 'ministry':
                case 'region':
                    html += `
                        <td style = "width: 100%;">${this.escapeHtml(item.name)}</td>
                        <td style="text-align: center;"></td>
                    `;
                    break;
                default:
                    html += `
                        <td style = "width: 100%;">${this.escapeHtml(item.name)}</td>
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
                    <th>Наименование</th>
                    <th style="text-align: center;">ОКПО</th>
                `;
                break;
            case 'ministry':
                headersHTML += `
                    <th>Наименование министерства</th>
                    <th style="text-align: center;"></th>
                `;
                break;
            case 'region':
                headersHTML += `
                    <th>Наименование региона</th>
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
            'organization': 'Код или наименование организации',
            'ministry': 'Наименование министерства',
            'region': 'Наименование региона'
        };
        
        this.searchInput.placeholder = placeholders[type] || 'Поиск...';
        
        const searchLabel = document.getElementById('search-label');
        if (searchLabel) {
            const labels = {
                'organization': 'Поиск организации',
                'ministry': 'Поиск министерства',
                'region': 'Поиск региона'
            };
            searchLabel.textContent = labels[type] || 'Поиск';
        }
    }

    updateSubmitButtonText() {
        if (!this.submitButton) return;
        
        const buttonTexts = {
            'organization': 'Сохранить организацию',
            'ministry': 'Сохранить министерство',
            'region': 'Сохранить регион'
        };
        
        const text = buttonTexts[this.selectedItemType] || 'Сохранить изменения';
        
        const btnTextSpan = this.submitButton.querySelector('.btn-text');
        if (btnTextSpan) {
            btnTextSpan.textContent = text;
        }
    }

    selectItem(row) {
        this.selectedItemId = row.dataset.id;
        
        // Обновляем скрытые поля формы
        this.selectedOrgInput.value = this.selectedItemId;
        if (this.selectedItemTypeInput) {
            this.selectedItemTypeInput.value = this.selectedItemType;
        }
        
        // Подсвечиваем выбранную строку
        this.highlightSelectedRow(row);
        
        // Активируем кнопку отправки
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
            'ministry': plural ? 'министерств' : 'министерство',
            'region': plural ? 'регионов' : 'регион'
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

    hideLoading() {

    }

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

document.addEventListener('DOMContentLoaded', function() {
    const searchManager = new MultiTypeSearchManager();
});

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
    
    // Публичный API
    return {
        init: function(options = {}) {
            if (isInitialized) {
                console.warn('TableCollapseManager уже инициализирован');
                return;
            }
            
            const config = {
                autoInit: options.autoInit !== false,
                initiallyCollapsed: options.initiallyCollapsed || [''], //other-content
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
            if (header) {
                toggleContent(header);
            }
        },
        
        expandSection: function(sectionId) {
            const header = document.querySelector(`[data-target="${sectionId}"]`);
            const target = document.getElementById(sectionId);
            
            if (header && target) {
                target.style.display = 'table-row-group';
                const arrow = header.querySelector('.dropdown-arrow');
                if (arrow) arrow.style.transform = 'rotate(0deg)';
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
        
        addSection: function(headerElement, contentElement) {
            if (!headerElement || !contentElement) {
                console.error('Необходимо передать и header и content элементы');
                return;
            }
            
            headerElement.style.cursor = 'pointer';
            headerElement.addEventListener('click', function() {
                toggleContent(this);
            });
            
            headerElement.addEventListener('mouseenter', function() {
                this.style.backgroundColor = '#f5f5f5';
            });
            
            headerElement.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
            
            groupHeaders = document.querySelectorAll('.group-header');
        },
        

        destroy: function() {
            groupHeaders.forEach(header => {
                const newHeader = header.cloneNode(true);
                header.parentNode.replaceChild(newHeader, header);
            });
            
            groupHeaders = [];
            isInitialized = false;
            console.log('TableCollapseManager уничтожен');
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

(function() {
    function filterPlans(nameInput, okpoInput, plans, noResultsContainer) {
        const nameFilter = nameInput ? nameInput.value.toLowerCase() : "";
        const okpoFilter = okpoInput ? okpoInput.value.toLowerCase() : "";
        
        let visibleCount = 0;
        
        plans.forEach(plan => {
            const planName = plan.dataset.name || "";
            const planOkpo = plan.dataset.okpo || "";

            const matchName = planName.includes(nameFilter);
            const matchOkpo = planOkpo.includes(okpoFilter);

            const isVisible = (matchName && matchOkpo);
            plan.style.display = isVisible ? "" : "none";
            
            if (isVisible) visibleCount++;
        });
        
        if (noResultsContainer) {
            noResultsContainer.style.display = visibleCount === 0 ? "block" : "none";
        }
    }

    function initPlansFilter(config = {}) {
        const {
            nameInputSelector = "#search-name",
            okpoInputSelector = "#search-okpo",
            plansSelector = '[data-plan="choose"]',
            noResultsSelector = "#no-results",
            createIfNotExists = true
        } = config;

        const nameInput = document.querySelector(nameInputSelector);
        const okpoInput = document.querySelector(okpoInputSelector);
        const plans = document.querySelectorAll(plansSelector);
        let noResultsContainer = document.querySelector(noResultsSelector);

        if (!plans.length) return;
        
        if (!noResultsContainer && createIfNotExists) {
            const plansContainer = plans[0].parentNode;
            noResultsContainer = document.createElement("div");
            noResultsContainer.id = noResultsSelector.replace("#", "");
            noResultsContainer.className = "no-results";
            noResultsContainer.innerHTML = `
                <div class="choose-plan">
                    <div class="no-info-conteiner">
                        <div class="empty-state">
                        {{ icons.icon_no_info() }}
                        <h1>{{ _('По вашему запросу ничего не найдено') }}</h1>
                        <p>Попробуйте изменить параметры поиска.</p>
                        </div>
                    </div>
                </div>
            `;
            noResultsContainer.style.display = "none";
            plansContainer.appendChild(noResultsContainer);
        }

        const handler = () => filterPlans(nameInput, okpoInput, plans, noResultsContainer);

        if (nameInput) nameInput.addEventListener("input", handler);
        if (okpoInput) okpoInput.addEventListener("input", handler);
        setTimeout(handler, 100);
    }

    window.initPlansFilter = initPlansFilter;
})();

// class OrganizationsSearch {
//   constructor(options = {}) {
//     this.config = {
//       step1Selector: '.auth-step-1',
//       step2Selector: '.auth-step-2',
//       nextBtnId: 'next-btn',
//       prevBtnId: 'prev-btn',
//       searchInputId: 'organization-search',
//       dropdownId: 'organizations-dropdown',
//       listId: 'organizations-list',
//       loadingId: 'organizations-loading',
//       loadMoreBtnId: 'load-more-organizations',
//       organizationIdInputId: 'organization_id',
//       submitBtnId: 'submit-btn',
//       requiredFields: ['secondname', 'name', 'phone'],
//       apiEndpoint: '/api/organizations',
//       minSearchLength: 2,
//       debounceDelay: 300,
//       ...options
//     };

//     this.currentPage = 1;
//     this.hasMore = false;
//     this.currentSearchQuery = '';
//     this.debounceTimer = null;

//     this.init();
//   }

//   init() {
//     this.elements = {};
//     this.getElementReferences();
//     this.bindEvents();
//   }

//   getElementReferences() {
//     // Основные элементы
//     this.elements.step1 = document.querySelector(this.config.step1Selector);
//     this.elements.step2 = document.querySelector(this.config.step2Selector);
//     this.elements.nextBtn = document.getElementById(this.config.nextBtnId);
//     this.elements.prevBtn = document.getElementById(this.config.prevBtnId);
    
//     // Элементы поиска организаций
//     this.elements.searchInput = document.getElementById(this.config.searchInputId);
//     this.elements.dropdown = document.getElementById(this.config.dropdownId);
//     this.elements.organizationsList = document.getElementById(this.config.listId);
//     this.elements.loadingIndicator = document.getElementById(this.config.loadingId);
//     this.elements.loadMoreBtn = document.getElementById(this.config.loadMoreBtnId);
//     this.elements.organizationIdInput = document.getElementById(this.config.organizationIdInputId);
//     this.elements.submitBtn = document.getElementById(this.config.submitBtnId);

//     // Проверка наличия всех необходимых элементов
//     this.validateRequiredElements();
//   }

//   validateRequiredElements() {
//     const requiredElements = [
//       'step1', 'step2', 'nextBtn', 'prevBtn', 'searchInput', 
//       'dropdown', 'organizationsList', 'loadingIndicator', 
//       'loadMoreBtn', 'organizationIdInput', 'submitBtn'
//     ];

//     // requiredElements.forEach(elementName => {
//     //   if (!this.elements[elementName]) {
//     //     console.warn(`Element ${elementName} not found`);
//     //   }
//     // });
//   }

//   bindEvents() {
//     // События для шагов формы
//     if (this.elements.nextBtn) {
//       this.elements.nextBtn.addEventListener('click', () => this.handleNextStep());
//     }
    
//     if (this.elements.prevBtn) {
//       this.elements.prevBtn.addEventListener('click', () => this.handlePrevStep());
//     }

//     // События для поиска организаций
//     if (this.elements.searchInput) {
//       this.elements.searchInput.addEventListener('input', (e) => this.handleSearchInput(e));
//       this.elements.searchInput.addEventListener('focus', () => this.handleSearchFocus());
//       this.elements.searchInput.addEventListener('keydown', (e) => this.handleSearchKeydown(e));
//     }

//     if (this.elements.loadMoreBtn) {
//       this.elements.loadMoreBtn.addEventListener('click', () => this.handleLoadMore());
//     }

//     // Закрытие dropdown при клике вне области
//     document.addEventListener('click', (e) => this.handleDocumentClick(e));
//   }

//   handleNextStep() {
//     const isValid = this.validateRequiredFields();
    
//     if (isValid) {
//       this.elements.step1.style.display = 'none';
//       this.elements.step2.style.display = 'block';
//     } else {
//       alert('Пожалуйста, заполните все обязательные поля');
//     }
//   }

//   handlePrevStep() {
//     this.elements.step2.style.display = 'none';
//     this.elements.step1.style.display = 'block';
//   }

//   validateRequiredFields() {
//     let isValid = true;
    
//     this.config.requiredFields.forEach(field => {
//       const input = document.getElementById(field);
//       if (input && !input.value.trim()) {
//         isValid = false;
//         input.style.borderColor = 'red';
//       } else if (input) {
//         input.style.borderColor = '';
//       }
//     });

//     return isValid;
//   }

//   handleSearchInput(e) {
//     const query = e.target.value.trim();
//     this.currentSearchQuery = query;
    
//     this.elements.organizationIdInput.value = '';
//     this.elements.submitBtn.disabled = true;
    
//     clearTimeout(this.debounceTimer);
    
//     if (query.length >= this.config.minSearchLength) {
//       this.debounceTimer = setTimeout(() => {
//         this.currentPage = 1;
//         this.searchOrganizations(query, 1, false);
//       }, this.config.debounceDelay);
//     } else {
//       this.elements.dropdown.style.display = 'none';
//       this.elements.organizationsList.innerHTML = '';
//     }
//   }

//   handleSearchFocus() {
//     if (this.currentSearchQuery && this.currentSearchQuery.length >= this.config.minSearchLength) {
//       this.elements.dropdown.style.display = 'block';
//     }
//   }

//   handleSearchKeydown(e) {
//     if (e.key === 'Escape') {
//       this.elements.dropdown.style.display = 'none';
//     }
//     if (e.key === 'Enter') {
//       e.preventDefault();
//       const firstItem = this.elements.organizationsList.querySelector('.organization-item');
//       if (firstItem) {
//         firstItem.click();
//       }
//     }
//   }

//   handleLoadMore() {
//     if (this.hasMore && this.currentSearchQuery) {
//       this.searchOrganizations(this.currentSearchQuery, this.currentPage + 1, true);
//     }
//   }

//   handleDocumentClick(e) {
//     if (!this.elements.searchInput.contains(e.target) && !this.elements.dropdown.contains(e.target)) {
//       this.elements.dropdown.style.display = 'none';
//     }
//   }

//   async searchOrganizations(query, page = 1, append = false) {
//     if (!append) {
//       this.elements.loadingIndicator.style.display = 'block';
//       this.elements.organizationsList.innerHTML = '';
//     }

//     try {
//       const response = await fetch(`${this.config.apiEndpoint}?q=${encodeURIComponent(query)}&page=${page}`);
      
//       if (!response.ok) {
//         throw new Error('Network response was not ok');
//       }

//       const data = await response.json();
//       this.handleSearchResponse(data, append);
//     } catch (error) {
//       console.error('Error fetching organizations:', error);
//       this.handleSearchError();
//     }
//   }

//   handleSearchResponse(data, append) {
//     this.elements.loadingIndicator.style.display = 'none';
    
//     if (!append) {
//       this.elements.organizationsList.innerHTML = '';
//     }

//     if (data.organizations && data.organizations.length > 0) {
//       data.organizations.forEach(org => {
//         this.createOrganizationElement(org);
//       });

//       this.hasMore = data.has_next;
//       if (this.hasMore) {
//         this.elements.loadMoreBtn.style.display = 'block';
//         this.currentPage = data.page;
//       } else {
//         this.elements.loadMoreBtn.style.display = 'none';
//       }
//     } else {
//       this.elements.organizationsList.innerHTML = '<div class="organization-item">Организации не найдены</div>';
//       this.elements.loadMoreBtn.style.display = 'none';
//     }
    
//     this.elements.dropdown.style.display = 'block';
//   }

//   handleSearchError() {
//     this.elements.loadingIndicator.style.display = 'none';
//     this.elements.organizationsList.innerHTML = '<div class="organization-item">Ошибка загрузки</div>';
//   }

//   createOrganizationElement(org) {
//     const orgElement = document.createElement('div');
//     orgElement.className = 'organization-item';
//     orgElement.innerHTML = `
//       <div class="organization-name">${this.escapeHtml(org.name)}</div>
//       <div class="organization-okpo">${this.escapeHtml(org.okpo)}</div>
//     `;
    
//     orgElement.addEventListener('click', () => {
//       this.selectOrganization(org, orgElement);
//     });
    
//     this.elements.organizationsList.appendChild(orgElement);
//   }

//   selectOrganization(org, element) {
//     document.querySelectorAll('.organization-item').forEach(item => {
//       item.classList.remove('selected');
//     });

//     element.classList.add('selected');

//     this.elements.searchInput.value = `${org.name} (ОКПО: ${org.okpo})`;
//     this.elements.organizationIdInput.value = org.id;
    
//     this.elements.dropdown.style.display = 'none'; 
//     this.elements.submitBtn.disabled = false;
//   }

//   escapeHtml(unsafe) {
//     if (typeof unsafe !== 'string') return unsafe;
//     return unsafe
//       .replace(/&/g, "&amp;")
//       .replace(/</g, "&lt;")
//       .replace(/>/g, "&gt;")
//       .replace(/"/g, "&quot;")
//       .replace(/'/g, "&#039;");
//   }

//   // Публичные методы для управления извне
//   destroy() {
//     // Очистка событий и таймеров
//     clearTimeout(this.debounceTimer);
    
//     // Удаление всех привязанных событий
//     if (this.elements.nextBtn) {
//       this.elements.nextBtn.replaceWith(this.elements.nextBtn.cloneNode(true));
//     }
//     if (this.elements.prevBtn) {
//       this.elements.prevBtn.replaceWith(this.elements.prevBtn.cloneNode(true));
//     }
//     if (this.elements.searchInput) {
//       this.elements.searchInput.replaceWith(this.elements.searchInput.cloneNode(true));
//     }
//     if (this.elements.loadMoreBtn) {
//       this.elements.loadMoreBtn.replaceWith(this.elements.loadMoreBtn.cloneNode(true));
//     }
    
//     document.removeEventListener('click', this.handleDocumentClick);
//   }

//   reset() {
//     this.currentPage = 1;
//     this.hasMore = false;
//     this.currentSearchQuery = '';
//     clearTimeout(this.debounceTimer);
    
//     if (this.elements.searchInput) {
//       this.elements.searchInput.value = '';
//     }
//     if (this.elements.organizationIdInput) {
//       this.elements.organizationIdInput.value = '';
//     }
//     if (this.elements.organizationsList) {
//       this.elements.organizationsList.innerHTML = '';
//     }
//     if (this.elements.dropdown) {
//       this.elements.dropdown.style.display = 'none';
//     }
//     if (this.elements.submitBtn) {
//       this.elements.submitBtn.disabled = true;
//     }
//   }
// }

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
                ministry: '/api/ministries',
                region: '/api/regions'
            },
            
            ...options
        };

        this.currentEntityType = 'organization';
        this.selectedItem = null;
        this.searchData = {
            organization: { page: 1, query: '', hasMore: false, loading: false },
            ministry: { page: 1, query: '', hasMore: false, loading: false },
            region: { page: 1, query: '', hasMore: false, loading: false }
        };
        this.debounceTimers = {};
        this.init();
    }

    init() {
        this.elements = {};
        this.getElementReferences();
        this.bindEvents();
        // console.log('MultiStepForm initialized');
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
            organization: document.getElementById('organization-block'),
            ministry: document.getElementById('ministry-block'),
            region: document.getElementById('region-block')
        };
        
        this.elements.searchInputs = {
            organization: document.getElementById('organization-search'),
            ministry: document.getElementById('ministry-search'),
            region: document.getElementById('region-search')
        };
        
        this.elements.hiddenInputs = {
            organization: document.getElementById('organization_id'),
            ministry: document.getElementById('ministry_id'),
            region: document.getElementById('region_id')
        };
        
        this.elements.dropdowns = {
            organization: document.getElementById('organization-dropdown'),
            ministry: document.getElementById('ministry-dropdown'),
            region: document.getElementById('region-dropdown')
        };
        
        this.elements.lists = {
            organization: document.getElementById('organization-list'),
            ministry: document.getElementById('ministry-list'),
            region: document.getElementById('region-list')
        };
        
        this.elements.loadings = {
            organization: document.getElementById('organization-loading'),
            ministry: document.getElementById('ministry-loading'),
            region: document.getElementById('region-loading')
        };
        
        this.elements.moreButtons = {
            organization: document.getElementById('organization-more'),
            ministry: document.getElementById('ministry-more'),
            region: document.getElementById('region-more')
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
        
        // console.log('All events bound');
    }

    handleEntityTypeChange(e) {
        this.currentEntityType = e.target.value;
        console.log('Entity type changed to:', this.currentEntityType);
        
        // Обновляем скрытое поле entity_type
        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }
        
        this.updateStep3Content();
    }

    updateStep3Content() {
        Object.values(this.elements.entityBlocks).forEach(block => {
            if (block) block.style.display = 'none';
        });
        
        const currentBlock = this.elements.entityBlocks[this.currentEntityType];
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
        
        // Устанавливаем скрытое поле entity_type
        if (this.elements.entityTypeInput) {
            this.elements.entityTypeInput.value = this.currentEntityType;
        }
        
        this.hideDropdown(type);
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = false;
        }
        this.selectedItem = item;
        
        console.log(`Selected ${type}:`, item);
        console.log(`Entity type: ${this.currentEntityType}`);
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
        

        console.log('Form data to submit:');
        for (let [key, value] of formData.entries()) {
            console.log(`${key}: ${value}`);
        }
        
        fetch(this.elements.form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            console.log('Response status:', response.status);
            if (response.redirected) {
                window.location.href = response.url;
            } else if (response.ok) {
                return response.json().then(data => {
                    console.log('Response data:', data);
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
        if (!step1Valid) {
            console.error('Step 1 validation failed');
            return false;
        }
        
        const entityType = this.currentEntityType;
        if (!entityType) {
            console.error('Entity type not selected');
            return false;
        }
        
        const hiddenInput = this.elements.hiddenInputs[entityType];
        if (!hiddenInput || !hiddenInput.value) {
            console.error(`${entityType} not selected`);
            return false;
        }
        
        console.log('Form validation passed');
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
        [this.elements.step1, this.elements.step2, this.elements.step3].forEach(step => {
            if (step) step.style.display = 'none';
        });
        
        switch(stepNumber) {
            case 1:
                if (this.elements.step1) {
                    this.elements.step1.style.display = 'block';
                    this.elements.step1.classList.add('active');
                    this.elements.step2.classList.remove('active');
                    this.elements.step3.classList.remove('active');
                }
                break;
            case 2:
                if (this.validateStep1()) {
                    if (this.elements.step2) {
                        this.elements.step2.style.display = 'block';
                        this.elements.step1.classList.remove('active');
                        this.elements.step2.classList.add('active');
                        this.elements.step3.classList.remove('active');
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
                    this.elements.step1.classList.remove('active');
                    this.elements.step2.classList.remove('active');
                    this.elements.step3.classList.add('active');
                }
                break;
        }
    }

    handleEntityTypeChange(e) {
        this.currentEntityType = e.target.value;
        console.log('Entity type changed to:', this.currentEntityType);
        this.updateStep3Content();
    }

    updateStep3Content() {
        Object.values(this.elements.entityBlocks).forEach(block => {
            if (block) block.style.display = 'none';
        });
        
        const currentBlock = this.elements.entityBlocks[this.currentEntityType];
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

    handleSearchInput(e, type) {
        const query = e.target.value.trim();
        
        this.selectedItem = null;
        if (this.elements.hiddenInputs[type]) {
            this.elements.hiddenInputs[type].value = '';
        }
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = true;
        }
        
        this.searchData[type].query = query;
        this.searchData[type].page = 1;
        
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
        const query = this.searchData[type].query;
        const dropdown = this.elements.dropdowns[type];
        const list = this.elements.lists[type];
        
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
        const data = this.searchData[type];
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
        if (this.searchData[type].loading) return;
        
        this.searchData[type].loading = true;
        
        if (!append) {
            this.showLoading(type, true);
            this.clearSearchResults(type);
        }
        
        try {
            const endpoint = this.config.endpoints[type] || `/api/${type}`;
            const url = `${endpoint}?q=${encodeURIComponent(query)}&page=${page}`;
            
            console.log(`Fetching ${type}:`, url);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`Response for ${type}:`, data);
            
            this.handleSearchResponse(data, type, append);
        } catch (error) {
            console.error(`Error fetching ${type}:`, error);
            this.showError(type, error.message);
        } finally {
            this.searchData[type].loading = false;
            this.showLoading(type, false);
        }
    }

    handleSearchResponse(data, type, append = false) {
        const list = this.elements.lists[type];
        const dropdown = this.elements.dropdowns[type];
        const moreButton = this.elements.moreButtons[type];
        
        if (!list || !dropdown) {
            console.error(`Elements not found for ${type}:`, { list, dropdown });
            return;
        }
        
        const dataKey = `${type}s`; // organizations, ministries, regions
        const items = data[dataKey] || [];
        
        console.log(`Found ${items.length} items for ${type}`);
        
        if (!append) {
            list.innerHTML = '';
        }
        
        if (items.length > 0) {
            items.forEach(item => {
                const itemElement = this.createListItem(item, type);
                list.appendChild(itemElement);
            });
            
            this.searchData[type].hasMore = data.has_next || false;
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
            case 'ministry':
                div.innerHTML = `
                    <div class="item-name">${this.escapeHtml(item.name)}</div>
                `;
                break;
            case 'region':
                div.innerHTML = `
                    <div class="item-name">${this.escapeHtml(item.name)}</div>
                `;
                break;
        }
        
        div.addEventListener('click', () => {
            this.selectItem(item, type);
        });
        
        return div;
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
        
        this.hideDropdown(type);
        
        if (this.elements.submitBtn) {
            this.elements.submitBtn.disabled = false;
        }
        this.selectedItem = item;
        
        console.log(`Selected ${type}:`, item);
    }

    showLoading(type, show) {
        const loading = this.elements.loadings[type];
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    clearSearchResults(type) {
        const list = this.elements.lists[type];
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
        const list = this.elements.lists[type];
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
        if (text === null || text === undefined) {
            return '';
        }
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    destroy() {
        // Очистка всех таймеров
        Object.values(this.debounceTimers).forEach(timer => {
            if (timer) clearTimeout(timer);
        });
        
        console.log('MultiStepForm destroyed');
    }

    reset() {
        this.currentEntityType = 'organization';
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
        
        Object.keys(this.elements.lists).forEach(type => {
            this.clearSearchResults(type);
            this.hideDropdown(type);
        });
        
        this.goToStep(1);
        
        console.log('MultiStepForm reset');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        const multiStepForm = new MultiStepForm();
        window.multiStepForm = multiStepForm; 
        // console.log('MultiStepForm ready');
    } catch (error) {
        console.error('Failed to initialize MultiStepForm:', error);
    }
});

class CertificateUploadHandler {
    constructor() {
        this.form = document.getElementById('sentForm');
        this.dropArea = document.getElementById('drop-area');
        this.fileInput = document.getElementById('certificate_to_check');
        this.submitButton = document.getElementById('submit_sent_button');
        
        this.init();
    }

    init() {
        if (!this.form || !this.dropArea || !this.fileInput || !this.submitButton) {
            console.error('Required elements not found');
            return;
        }

        this.bindEvents();
        this.updateSubmitButtonState();
    }

    bindEvents() {
        this.dropArea.addEventListener('dragover', this.handleDragOver.bind(this));
        this.dropArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        this.dropArea.addEventListener('drop', this.handleDrop.bind(this));
        this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));
        this.removeDropAreaClick();
    }

    removeDropAreaClick() {
        this.dropArea.style.cursor = 'default';
        const fileInputLabel = this.dropArea.querySelector('.file-input-label');
        if (fileInputLabel) {
            fileInputLabel.style.cursor = 'pointer';
            fileInputLabel.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
    }

    handleDragOver(e) {
        e.preventDefault();
        this.dropArea.classList.add('drag-over');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.dropArea.classList.remove('drag-over');
    }

    handleDrop(e) {
        e.preventDefault();
        this.dropArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processFile(files[0]);

            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(files[0]);
            this.fileInput.files = dataTransfer.files;
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processFile(file);
        }
    }

    processFile(file) {
        this.clearError();


        if (!this.isValidFile(file)) {
            this.showError('Неверный формат файла. Разрешены только файлы .cer');
            this.fileInput.value = '';
            return;
        }

        this.showFileName(file.name);
        this.updateSubmitButtonState(true);
    }

    isValidFile(file) {
        const fileName = file.name.toLowerCase();
        return fileName.endsWith('.cer');
    }

    showFileName(fileName) {
        const label = this.dropArea.querySelector('p');
        if (label) {
            label.innerHTML = `<strong>${this.escapeHtml(fileName)}</strong>`;
        }
    }

    updateSubmitButtonState(isEnabled = false) {
        this.submitButton.disabled = !isEnabled;
        
        if (isEnabled) {
            this.submitButton.classList.remove('disabled');
        } else {
            this.submitButton.classList.add('disabled');
        }
    }

    showError(message) {
        this.updateSubmitButtonState(false);
    }

    clearError() {
        // this.errorMessage.textContent = '';
        // this.errorMessage.hidden = true;
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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
                        <span class="ticket-info-value">${data.user_fio || 'Не указано'}</span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Email</span>
                        <span class="ticket-info-value">
                            <a href="mailto:${data.user_email}" class="ticket-info-link">
                                ${data.user_email || 'Не указано'}
                            </a>
                        </span>
                    </div>
                    <div class="ticket-info-item">
                        <span class="ticket-info-label">Телефон</span>
                        <span class="ticket-info-value">
                            <a href="tel:${data.user_phone}" class="ticket-info-link">
                                ${data.user_phone || 'Не указано'}
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

function initCertificateUpload() {
    document.addEventListener('DOMContentLoaded', function() {
        const sentModal = document.getElementById('sentmodal');
        if (sentModal) {
            new CertificateUploadHandler();
            
            const style = document.createElement('style');
            style.textContent = `
                .drop-area {
                    cursor: default;
                }
                
                .drop-area.drag-over {
                    border-color: #007bff;
                    background-color: #f8f9fa;
                }
                
                .file-input-label {
                    cursor: pointer;
                    color: #007bff;
                    text-decoration: underline;
                }
                
                .submit-button:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                }
                
                .error-message {
                    color: #dc3545;
                    font-size: 14px;
                    margin-top: 8px;
                }
            `;
            document.head.appendChild(style);
        }
    });
}

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

document.addEventListener('DOMContentLoaded', initSections);
window.reinitSections = initSections;
initCertificateUpload();

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

  initLanguageDropdown();

  customDropdown.init();
  
  if (document.querySelector('.plan-cont')) {
    const cleanup = initStatusProgress();
  }

  new DirectionsTable({
      searchSelector: "search-directions",
      tableSelector: "directions-table",
      hiddenInputSelector: "selected-direction",
      nextButtonSelector: "directions-next"
  });

  if (document.querySelector('.main-table')) {
    setTimeout(initColumnResize, 100);    
    TableCollapseManager.init();  
  }

  const directionTable = document.getElementById('directionTable');
  const directionMenu = document.getElementById('MenuMainTable');
  if (directionTable && directionMenu) {
      const tableMenu = new TableContextMenu('directionTable', 'MenuMainTable', {
          contextEditButtonId: 'contextEditButton',
          contextDeleteButtonId: 'contextDeleteButton',
          
          tableEditButtonId: 'tableEditButton',
          tableDeleteButtonId: 'tableDeleteButton',
          removeUrlTemplate: '/delete-econmeasure/{id}',
          
          immutableCodes: [], // Коды, которые нельзя изменять/удалять
          immutableEditCodes: [], // Коды, которые нельзя редактировать (но можно удалять)
          immutableDeleteCodes: [], // Коды, которые нельзя удалять (но можно редактировать)

          codeColumnIndex: 11, 
          hideCodeColumn: true
      });
  }

  const eventsTable = document.getElementById('eventsTable');
  const eventsMenu = document.getElementById('MenuMainTable');
  if (eventsTable && eventsMenu) {
      const tableMenu = new TableContextMenu('eventsTable', 'MenuMainTable', {
          contextEditButtonId: 'contextEditButton',
          contextDeleteButtonId: 'contextDeleteButton',
          
          tableEditButtonId: 'tableEditButton',
          tableDeleteButtonId: 'tableDeleteButton',
          removeUrlTemplate: '/delete-econexeces/{id}',
          
          immutableCodes: [], // Коды, которые нельзя изменять/удалять
          immutableEditCodes: [], // Коды, которые нельзя редактировать (но можно удалять)
          immutableDeleteCodes: [], // Коды, которые нельзя удалять (но можно редактировать)

          codeColumnIndex: 11, 
          hideCodeColumn: true
      });
  }

  const indicatorsTable = document.getElementById('indicatorsTable');
  const indicatorsMenu = document.getElementById('MenuMainTable');
  if (indicatorsTable && indicatorsMenu) {
      const tableMenu = new TableContextMenu('indicatorsTable', 'MenuMainTable', {
          contextEditButtonId: 'contextEditButton',
          contextDeleteButtonId: 'contextDeleteButton',
          
          tableEditButtonId: 'tableEditButton',
          tableDeleteButtonId: 'tableDeleteButton',
          removeUrlTemplate: '/delete-indicator/{id}',
          
          immutableCodes: ['260', '9900', '9999', '1000'], // Коды, которые нельзя изменять/удалять
          immutableEditCodes: [],
          immutableDeleteCodes: ['9911', '9910', '9912', '9913', '9914', '1404', '1104', '1424', '1105', '1405', '1425', '1445', '9915', '9916', '9917'], // Коды, которые нельзя удалять (но можно редактировать)

          codeColumnIndex: 11, 
          hideCodeColumn: true
      });
  }

  // Добавление Direction
  const addDirectionModal = document.getElementById('AddDirectionModal');
  const DirectionModal = new EventModal('AddDirectionModal');
  if (addDirectionModal && DirectionModal) {
    handleModal(
      addDirectionModal, 
      document.getElementById('AddDirectionModalButton'), 
      addDirectionModal.querySelector('.close')
    );
  }

  // Добавление Event
  const addEventModal = document.getElementById('AddEventModal');
  const addEventModal1 = new EventModal('AddEventModal');
  if (addEventModal && addEventModal1) {
    handleModal(
      addEventModal, 
      document.getElementById('AddEventModalButton'), 
      addEventModal.querySelector('.close')
    );
  }

  // Добавление Indicator
  const addIndicatorModal = document.getElementById('AddIndicatorModal');
  const IndicatorModal = new EventModal('AddIndicatorModal');
  if (addIndicatorModal && IndicatorModal) {
    handleModal(
      addIndicatorModal,
      document.getElementById('AddIndicatorModalButton'), 
      addIndicatorModal.querySelector('.close')
    );
  }

  // Редактирование Direction
  const editDirectionModal = document.getElementById('EditDirectionModal');
  if (editDirectionModal) {
    handleModal(
      editDirectionModal, 
      document.getElementById('tableEditButton'), 
      editDirectionModal.querySelector('.close')
    );
    handleModal(
      editDirectionModal, 
      document.getElementById('contextEditButton'), 
      editDirectionModal.querySelector('.close')
    );
  }

  // Редактирование Event
  const editEventModal = document.getElementById('EditEventModal');
  const eventModal = new EventModal('EditEventModal');
  if (editEventModal && eventModal) {
    handleModal(
      editEventModal, 
      document.getElementById('tableEditButton'), 
      editEventModal.querySelector('.close')
    );
    handleModal(
      editEventModal, 
      document.getElementById('contextEditButton'), 
      editEventModal.querySelector('.close')
    );
  }
  
    // Редактирование Organizattion
  const orgUserModal = document.getElementById('orgUserModal');
  if (orgUserModal) {
    handleModal(
      orgUserModal, 
      document.getElementById('orgUserbutton'), 
      orgUserModal.querySelector('.close')
    );
  }

  // Редактирование Indicator
  const editIndicatorModal = document.getElementById('EditIndicatorModal');
  if (editIndicatorModal) {
    handleModal(
      editIndicatorModal, 
      document.getElementById('tableEditButton'), 
      editIndicatorModal.querySelector('.close')
    );
    handleModal(
      editIndicatorModal, 
      document.getElementById('contextEditButton'), 
      editIndicatorModal.querySelector('.close')
    );
  }

    const questions = document.querySelectorAll('.faq-question');
    questions.forEach(question => {
        question.addEventListener('click', function() {
            const allAnswers = document.querySelectorAll('.faq-answer');
            const allQuestions = document.querySelectorAll('.faq-question');
            if (this.classList.contains('active')) {
                const answer = this.nextElementSibling;
                answer.classList.remove('active');
                this.classList.remove('active');
                return;
            }

            allAnswers.forEach(answer => {
                answer.classList.remove('active');
            });
            
            allQuestions.forEach(q => {
                q.classList.remove('active');
            });
            
            const answer = this.nextElementSibling;
            answer.classList.add('active');
            this.classList.add('active');
        });
    });

    //edit profile
    if (document.getElementById('editprofileButton')) {
        initConfirmModal({
            triggerId: 'editprofileButton',
            formId: 'editprofileForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные профиля?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    //logout
    if (document.getElementById('logoutButton')) {
        initConfirmModal({
            triggerId: 'logoutButton',
            formId: 'logout_form',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите выйти из системы enPlans?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить. Убедитесь, что вы сохранили свою работу.'
        });
    }

    //deletePlan
    if (document.querySelector('[data-modal-trigger="deletePlan"]')) {
        initConfirmModal({
            triggerButton: '[data-modal-trigger="deletePlan"]',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите удалить план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    //edit plan
    if (document.getElementById('editPlanButton')) {
        initConfirmModal({
            triggerId: 'editPlanButton',
            formId: 'editPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отредактировать данные плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }

    //control plan
    if (document.getElementById('controlPlanButton')) {
        const button = document.getElementById('controlPlanButton');
        const form = document.getElementById('controlPlanForm');
        const planType = form.dataset.planType;
        
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
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            textSecondId: 'modal-text-second',
            modalText: modalText,
            modalTextSecond: modalTextSecond
        });
    }

    //sent plan
    // if (document.getElementById('sentPlanButton')) {
    //     initConfirmModal({
    //         triggerId: 'sentPlanButton',
    //         formId: 'sentPlanForm',
    //         modalId: 'confirmModal2',
    //         yesId: 'confirmYes',
    //         noId: 'confirmNo',
    //         textId: 'modal-text',
    //         modalText: 'Вы действительно хотите отправить план на проверку?',
    //         textSecondId: 'modal-text-second',
    //         modalTextSecond: 'План сменит статус и на время проверки его нельзя будет редактировать.'
    //     });
    // }    

    const sentPlanButton = document.getElementById('sentPlanButton');
    const sentmodal = document.getElementById('sentmodal');
    if (sentmodal) {
        handleModal(
            sentmodal, 
            sentPlanButton, 
            sentmodal.querySelector('.close')
        );
    }


    //cancel sent plan
    // if (document.getElementById('sentPlanButton')) {
    //     initConfirmModal({
    //         triggerId: 'cancelsentPlanButton',
    //         formId: 'cancelsentPlanForm',
    //         modalId: 'confirmModal2',
    //         yesId: 'confirmYes',
    //         noId: 'confirmNo',
    //         textId: 'modal-text',
    //         modalText: 'Вы действительно хотите отменить отправку?',
    //         textSecondId: 'modal-text-second',
    //         modalTextSecond: 'План сменит статус обратно на "В редакции".'
    //     });
    // }

    //sent audit message plan
    if (document.getElementById('sent_mesPlanButton')) {
        initConfirmModal({
            triggerId: 'sent_mesPlanButton',
            formId: 'sent_mesPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отправить сообщение об ошибках пользователю?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Описывайте ошибки максимально подробно, для наилучшего восприятия со стороны пользователя.'
        });
    }

    //to_delete plan
    if (document.getElementById('to_deletePlanButton')) {
        initConfirmModal({
            triggerId: 'to_deletePlanButton',
            formId: 'to_deletePlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите сменить статус плана на "Есть ошибки"?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус для последующего исправления ошибок.'
        });
    }

    //confirm plan
    if (document.getElementById('confirmPlanButton')) {
        initConfirmModal({
            triggerId: 'confirmPlanButton',
            formId: 'confirmPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите одобрить план?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус и не будет подлежать последующей редакции или удалению со всех сторон.'
        });
    }

    //cancel_audit plan
    if (document.getElementById('cancel_auditPlanButton')) {
        initConfirmModal({
            triggerId: 'cancel_auditPlanButton',
            formId: 'cancel_auditPlanForm',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите отменить изменения в статусе плана?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'План сменит статус обратно на "Не просмотренный". Отменить изменния можно только в течении 1-го часа.'
        });
    }

    if (tickets_conteiner = document.querySelector('.tickets-conteiner')) {
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
        
        customSmoothScroll(tickets_conteiner, tickets_conteiner.scrollHeight);
        
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
        
    if (document.getElementById('exportForm')) {
        initExportPage();
    }


    if (document.querySelectorAll('.plan-cont')) {
        initPlansFilter();
    }

    if (document.getElementById('notifBtn')) {
        NotificationPopup.init({
            button: "#notifBtn",
            popup: "#notifPopup"
        });
        Notifications.init();
        // setInterval(() => {
        //     Notifications.init();
        // }, 60000);

    }

    if(document.getElementById('organization-search')){
        try {
            const organizationsSearch = new OrganizationsSearch();
            console.log('OrganizationsSearch initialized successfully', organizationsSearch);
            window.orgSearch = organizationsSearch;
        } catch (error) {
            console.error('Error initializing OrganizationsSearch:', error);
        }
    }

    new DropNavigation();

    if (document.querySelectorAll('.tickets-conteiner')) {
        window.TicketInfo = TicketInfo;
    }
    
});
 

// Кнопка далее в modal plan events add and edit
function validateAndEnableButton() {
    // Для AddEventModal
    const addModal = document.getElementById('AddEventModal');
    if (addModal && addModal.style.display !== 'none') {
        const addFields = addModal.querySelectorAll('#step2 [name="name"], #step2 [name="Volume"], #step2 [name="ExpectedQuarter"]');
        const addButton = addModal.querySelector('#step2-next-btn[data-action="next-step-2"]');
        
        if (addFields.length === 3 && addButton) {
            const allFilled = Array.from(addFields).every(field => {
                const value = field.value.trim();
                if (field.name === 'name') return value !== '';
                if (field.name === 'Volume') return value !== '' && parseFloat(value) > 0;
                if (field.name === 'ExpectedQuarter') return value !== '' && parseInt(value) >= 1 && parseInt(value) <= 4;
                return false;
            });
            
            addButton.disabled = !allFilled;
            // console.log('AddModal validation:', allFilled);
        }
    }
    
    // Для EditEventModal
    const editModal = document.getElementById('EditEventModal');
    if (editModal && editModal.style.display !== 'none') {
        const editFields = editModal.querySelectorAll('#step1 [name="name"], #step1 [name="Volume"], #step1 [name="ExpectedQuarter"]');
        const editButton = editModal.querySelector('#step1-next-btn[data-action="next-step-2"]');
        
        if (editFields.length === 3 && editButton) {
            const allFilled = Array.from(editFields).every(field => {
                const value = field.value.trim();
                if (field.name === 'name') return value !== '';
                if (field.name === 'Volume') return value !== '' && parseFloat(value) > 0;
                if (field.name === 'ExpectedQuarter') return value !== '' && parseInt(value) >= 1 && parseInt(value) <= 4;
                return false;
            });
            
            editButton.disabled = !allFilled;
            // console.log('EditModal validation:', allFilled);
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    validateAndEnableButton();
    
    setInterval(validateAndEnableButton, 300);
    
    document.addEventListener('input', function(e) {
        if (e.target.matches('[name="name"], [name="Volume"], [name="ExpectedQuarter"]')) {
            validateAndEnableButton();
        }
    });
});


document.write('<script src="/static/js/chat.js"></script>');
document.addEventListener('DOMContentLoaded', function() {
    if (window.ChatModule) {
        const userId = document.body.dataset.userId || 1;
        ChatModule.init(userId);
        // console.log('Base.js: Chat module loaded and initialized');
    }
});


// COOKIE INIT
document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.initCookieBanner === 'function') {
        window.initCookieBanner();
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


const menuDotsBtn = document.getElementById('menuDotsBtn');
const planActionsMenu = document.getElementById('planActionsMenu');

// Функция для закрытия меню
function closeMenu() {
    if (planActionsMenu) {
        planActionsMenu.classList.remove('show');
    }
}

// Функция для открытия меню
function openMenu() {
    if (planActionsMenu) {
        // Закрываем все другие меню
        document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
            if (menu !== planActionsMenu) {
                menu.classList.remove('show');
            }
        });
        
        planActionsMenu.classList.add('show');
    }
}

// Клик по кнопке с точками
if (menuDotsBtn && planActionsMenu) {
    menuDotsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        
        if (planActionsMenu.classList.contains('show')) {
            closeMenu();
        } else {
            openMenu();
        }
    });
    
    // Закрытие при клике вне меню
    document.addEventListener('click', (e) => {
        if (!menuDotsBtn.contains(e.target) && !planActionsMenu.contains(e.target)) {
            closeMenu();
        }
    });
    
    // Закрытие при нажатии Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && planActionsMenu.classList.contains('show')) {
            closeMenu();
        }
    });
    
    // Закрытие при скролле (опционально)
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (planActionsMenu.classList.contains('show')) {
            // Не закрываем сразу, а с небольшой задержкой
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                closeMenu();
            }, 100);
        }
    });
    
    // Обработка отправки форм внутри меню
    const forms = planActionsMenu.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', () => {
            closeMenu();
        });
    });
    
    // Обработка кликов по кнопкам внутри меню
    const buttons = planActionsMenu.querySelectorAll('button:not([type="submit"])');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            closeMenu();
        });
    });
}