// Переключатель светлой/тёмной темы.
// Фактическая тема уже выставлена инлайн-скриптом в <head> (до отрисовки,
// чтобы не мигало) — по умолчанию светлая, системные настройки не влияют;
// здесь только обвязка самой кнопки + синхронизация между вкладками сайта.
(function () {
    var STORAGE_KEY = 'enplans-theme';

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
    }

    function current() {
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }

    function setTheme(theme, persist) {
        apply(theme);
        if (persist) {
            try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('themeToggle');
        if (btn) {
            btn.setAttribute('aria-pressed', current() === 'dark');
            btn.addEventListener('click', function () {
                var next = current() === 'dark' ? 'light' : 'dark';
                setTheme(next, true);
                btn.setAttribute('aria-pressed', next === 'dark');
            });
        }
    });

    // Синхронизация темы между открытыми вкладками сайта.
    window.addEventListener('storage', function (e) {
        if (e.key === STORAGE_KEY && e.newValue) {
            apply(e.newValue);
        }
    });
})();
