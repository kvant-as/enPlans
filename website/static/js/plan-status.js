function initStatusProgress() {
    const planElements = document.querySelectorAll('.plan-cont');
    const progressLine = document.querySelector('.progress-line-active');
    const statusDots = document.querySelectorAll('.status-dot');

    if (!planElements.length || !progressLine || !statusDots.length) {
        console.warn('Plan status progress elements not found');
        return;
    }

    // «Проверяющая» раскладка — когда нет вкладки «В редакции» (организация
    // только согласует/утверждает). Раньше определялось по наличию
    // «Согласованных», но теперь эта вкладка бывает и у организации,
    // которая сама разрабатывает планы и ещё согласует чужие.
    const isAuditor = document.querySelector('body')?.dataset?.isAuditor === 'true' ||
                      !document.querySelector('.stat-and-dot[data-value="draft"]');

    // dotIndex раньше был зашит числом и предполагал фиксированный порядок
    // тайлов в DOM (.stat-and-dot) — при любой перестановке тайлов
    // (см. components.html::plan_count) заливка и точки съезжали на чужой
    // статус. Вместо номера — data-value тайла, которому принадлежит
    // точка; реальный индекс среди statusDots ищем на лету ниже, так что
    // порядок тайлов в разметке можно менять не трогая этот файл.
    let statusConfig;

    if (isAuditor) {
        statusConfig = {
            'plan-cont-sent': { width: '33%', color: 'var(--color-sented)', dataValue: 'sent' },
            'plan-cont-transit': { width: '50%', color: '#35a6d0', dataValue: 'in_transit' },
            'plan-cont-sogl': { width: '66%', color: 'var(--color-sogl)', dataValue: 'sogl' },
            'plan-cont-eror': { width: '83%', color: 'var(--color-erorsed)', dataValue: 'error' },
            'plan-cont-sub': { width: '100%', color: 'var(--color-submited)', dataValue: 'approved' }
        };
    } else {
        statusConfig = {
            'plan-cont-redac': { width: '16%', color: 'var(--color-redaced)', dataValue: 'draft' },
            'plan-cont-control': { width: '33%', color: 'var(--color-controled)', dataValue: 'control' },
            'plan-cont-signing': { width: '50%', color: '#35a6d0', dataValue: 'signing' },
            'plan-cont-sent': { width: '66%', color: 'var(--color-sented)', dataValue: 'sent' },
            // Гибридная организация: чужой план в её очереди — вкладка
            // «В ожидании» (у обычной организации-разработчика её нет —
            // dotIndexFor тогда просто не найдёт тайл).
            'plan-cont-transit': { width: '75%', color: '#35a6d0', dataValue: 'in_transit' },
            // …и «Согласованные» — у той, что ещё и согласует чужие планы.
            'plan-cont-sogl': { width: '85%', color: 'var(--color-sogl)', dataValue: 'sogl' },
            'plan-cont-eror': { width: '92%', color: 'var(--color-erorsed)', dataValue: 'error' },
            'plan-cont-sub': { width: '100%', color: 'var(--color-submited)', dataValue: 'approved' }
        };
    }

    function dotIndexFor(dataValue) {
        const tile = document.querySelector('.stat-and-dot[data-value="' + dataValue + '"]');
        if (!tile) return -1;
        const dot = tile.querySelector('.status-dot');
        if (!dot) return -1;
        return Array.prototype.indexOf.call(statusDots, dot);
    }

    // Точки сопоставляются с тайлами по data-value (dotIndexFor), а не по
    // числу записей statusConfig — у гибридной организации тайлов больше,
    // чем записей, и иначе пропадала бы последняя точка.
    const totalDots = statusDots.length;

    let activePlan = null;
    let isHovering = false;

    function resetProgress() {
        progressLine.style.width = '0%';
        progressLine.style.background = 'var(--color-sented)';
        statusDots.forEach((dot, index) => {
            if (index < totalDots) {
                dot.classList.remove('active');
                dot.style.background = 'var(--border-color)';
                dot.style.display = '';
            } else {
                dot.style.display = 'none';
            }
        });
    }

    function updateProgress(className) {
        const config = statusConfig[className];
        if (!config) return;
        const dotIndex = dotIndexFor(config.dataValue);
        if (dotIndex === -1) return;

        // Тайлы теперь разной ширины (размер по тексту), поэтому точки
        // статусов больше не стоят на равных % от трека — процент из
        // statusConfig.width тут был бы неверным. Меряем позицию
        // реальной точки-цели в DOM и ставим ширину полосы в px.
        const lineContainer = progressLine.parentElement;
        const targetDot = statusDots[dotIndex];
        if (lineContainer && targetDot) {
            const containerRect = lineContainer.getBoundingClientRect();
            const dotRect = targetDot.getBoundingClientRect();
            const width = (dotRect.left + dotRect.width / 2) - containerRect.left;
            progressLine.style.width = Math.max(0, width) + 'px';
        } else {
            progressLine.style.width = config.width;
        }
        progressLine.style.background = config.color;

        statusDots.forEach((dot, index) => {
            if (index < totalDots) {
                dot.style.display = '';
                if (index <= dotIndex) {
                    dot.classList.add('active');
                    dot.style.background = config.color;
                } else {
                    dot.classList.remove('active');
                    dot.style.background = 'var(--border-color)';
                }
            } else {
                dot.style.display = 'none';
            }
        });
    }

    planElements.forEach(plan => {
        plan.removeEventListener('mouseenter', plan._mouseEnterHandler);
        plan.removeEventListener('mouseleave', plan._mouseLeaveHandler);
    });

    planElements.forEach(plan => {
        const mouseEnterHandler = function() {
            isHovering = true;
            const className = Array.from(this.classList).find(cls =>
                cls.startsWith('plan-cont-')
            );
            if (className && statusConfig[className]) {
                activePlan = this;
                updateProgress(className);
            }
        };

        const mouseLeaveHandler = function() {
            isHovering = false;
            resetProgress();
        };

        plan.addEventListener('mouseenter', mouseEnterHandler);
        plan.addEventListener('mouseleave', mouseLeaveHandler);

        plan._mouseEnterHandler = mouseEnterHandler;
        plan._mouseLeaveHandler = mouseLeaveHandler;
    });

    statusDots.forEach((dot, index) => {
        if (index >= totalDots) {
            dot.style.display = 'none';
        }
    });

    resetProgress();
    syncProgressLineToTrack();
}

// На мобильном .stats-track листается по горизонтали и точки статусов
// (внутри трека) уезжают вместе со скроллом, а .progress-line-container —
// его сосед, абсолютно спозиционированный относительно НЕскроллящегося
// .stats-container — оставался на месте. Из-за этого заливка (её ширина
// считается в % от .progress-line-container) визуально не совпадала с
// тем, под какой именно точкой/статом она должна заканчиваться.
// Решение: растягиваем .progress-line-container до полной scrollWidth
// трека и двигаем его тем же transform, что и скролл — тогда линия и
// точки всегда остаются друг под другом, а .stats-container обрезает
// лишнее через overflow: hidden (см. base.css).
function syncProgressLineToTrack() {
    const track = document.querySelector('.stats-track');
    const lineContainer = document.querySelector('.progress-line-container');
    if (!track || !lineContainer) return;

    function sync() {
        const isScrollable = track.scrollWidth - track.clientWidth > 1;
        if (isScrollable) {
            lineContainer.style.width = track.scrollWidth + 'px';
            lineContainer.style.transform = `translateX(${-track.scrollLeft}px)`;
        } else {
            lineContainer.style.width = '';
            lineContainer.style.transform = '';
        }
    }

    if (!track.dataset.progressSyncBound) {
        track.dataset.progressSyncBound = 'true';
        track.addEventListener('scroll', sync, { passive: true });
        window.addEventListener('resize', sync);
    }

    sync();
}
