// Кастомная панель выбора года плана (создание/редактирование).
// Разметку генерирует macros/components.html :: year_picker().
(function () {
    function initYearPicker(root) {
        var trigger = root.querySelector('.year-picker-trigger');
        var valueEl = root.querySelector('.year-picker-value');
        var hiddenInput = root.querySelector('#year');
        if (!trigger || !valueEl || !hiddenInput) return;

        function close() {
            root.classList.remove('open');
            trigger.setAttribute('aria-expanded', 'false');
        }

        function open() {
            root.classList.add('open');
            trigger.setAttribute('aria-expanded', 'true');
            var selected = root.querySelector('.year-picker-option.selected');
            if (selected) selected.scrollIntoView({ block: 'center' });
        }

        trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            if (root.classList.contains('open')) {
                close();
            } else {
                open();
            }
        });

        root.querySelectorAll('.year-picker-option:not(.disabled)').forEach(function (option) {
            option.addEventListener('click', function () {
                var year = option.getAttribute('data-year');

                root.querySelectorAll('.year-picker-option').forEach(function (o) {
                    o.classList.remove('selected');
                    o.setAttribute('aria-selected', 'false');
                });
                option.classList.add('selected');
                option.setAttribute('aria-selected', 'true');

                valueEl.textContent = year;
                hiddenInput.value = year;
                close();

                var event = document.createEvent('Event');
                event.initEvent('change', true, true);
                hiddenInput.dispatchEvent(event);
            });
        });

        document.addEventListener('click', function (e) {
            if (!root.contains(e.target)) close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') close();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.year-picker').forEach(initYearPicker);
    });
})();
