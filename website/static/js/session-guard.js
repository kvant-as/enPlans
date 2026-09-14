// Site-wide idle-session guard: runs on every page for an authenticated user
// (included from base.html), independent of the "Сессии" card that only exists
// on the profile page.
//
// Activity = page navigations and ordinary server calls. It does NOT include
// pure client-side interaction (scrolling, clicking, typing) and it does NOT
// include /api data loads (the header polls /api/notifications every 60s).
// A full page load re-reads a fresh baseline from the server.
(function () {
    var INFO_URL = '/api/session-info';
    var LOGOUT_URL = '/logout';
    var IGNORE = ['/api', '/_session', '/_forms'];

    var expiresAt = null;
    var timeoutMs = null;
    var lastSlide = 0;
    var checking = false;
    var stopped = false;

    function pathOf(url) {
        try { return new URL(url, window.location.origin).pathname; }
        catch (e) { return typeof url === 'string' ? url : ''; }
    }
    function isIgnored(url) {
        var p = pathOf(url);
        for (var i = 0; i < IGNORE.length; i++) if (p.indexOf(IGNORE[i]) === 0) return true;
        return false;
    }
    function format(ms) {
        var t = Math.max(0, Math.floor(ms / 1000));
        var h = Math.floor(t / 3600);
        var m = Math.floor((t % 3600) / 60);
        var s = t % 60;
        return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }

    function updateCard() {
        var card = document.getElementById('sessionCard');
        if (!card || expiresAt === null) return;
        var valueEl = document.getElementById('sessionTimerValue');
        var fillEl = document.getElementById('sessionTimerFill');
        var remaining = Math.max(0, expiresAt - Date.now());
        if (valueEl) valueEl.textContent = format(remaining);
        var ratio = timeoutMs ? Math.min(1, Math.max(0, remaining / timeoutMs)) : 1;
        if (fillEl) fillEl.style.width = (ratio * 100) + '%';
        card.classList.toggle('glass-surface--warning', ratio <= 0.2 && ratio > 0.05);
        card.classList.toggle('glass-surface--danger', ratio <= 0.05);
    }

    function slide() {
        if (!timeoutMs || stopped) return;
        var now = Date.now();
        if (now - lastSlide < 2000) return;
        lastSlide = now;
        expiresAt = now + timeoutMs;
        updateCard();
    }

    function goLogout() {
        if (stopped) return;
        stopped = true;
        window.location.href = LOGOUT_URL;
    }

    function verifyThenMaybeLogout() {
        if (checking || stopped) return;
        checking = true;
        fetch(INFO_URL, { credentials: 'same-origin', redirect: 'manual',
                          headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { if (!r || !r.ok) { goLogout(); return null; } return r.json(); })
            .then(function (d) {
                checking = false;
                if (!d || !d.success) return;
                var offset = new Date(d.server_time).getTime() - Date.now();
                var exp = new Date(d.expires_at).getTime() - offset;
                if (exp <= Date.now()) { goLogout(); return; }
                expiresAt = exp;
                if (d.timeout_minutes) timeoutMs = d.timeout_minutes * 60 * 1000;
                updateCard();
            })
            .catch(function () { checking = false; goLogout(); });
    }

    function tick() {
        if (expiresAt === null || stopped) return;
        if (Date.now() >= expiresAt) { verifyThenMaybeLogout(); return; }
        updateCard();
    }

    function hookRequests() {
        var origFetch = window.fetch;
        if (origFetch) {
            window.fetch = function (input) {
                var url = typeof input === 'string' ? input : (input && input.url);
                var p = origFetch.apply(this, arguments);
                if (!isIgnored(url)) p.then(function () { slide(); }, function () {});
                return p;
            };
        }
        var XHR = window.XMLHttpRequest;
        if (XHR) {
            var origOpen = XHR.prototype.open;
            XHR.prototype.open = function (method, url) {
                this.__cmIgnored = isIgnored(url);
                return origOpen.apply(this, arguments);
            };
            var origSend = XHR.prototype.send;
            XHR.prototype.send = function () {
                var self = this;
                this.addEventListener('loadend', function () { if (!self.__cmIgnored) slide(); });
                return origSend.apply(this, arguments);
            };
        }
    }

    function start(timeoutMinutes, initialExpiresAt) {
        timeoutMs = (timeoutMinutes || 60) * 60 * 1000;
        expiresAt = initialExpiresAt;
        hookRequests();
        updateCard();
        setInterval(tick, 1000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var card = document.getElementById('sessionCard');
        if (card && card.dataset.timeoutMinutes && card.dataset.expiresAt && card.dataset.serverTime) {
            var offset = new Date(card.dataset.serverTime).getTime() - Date.now();
            start(parseInt(card.dataset.timeoutMinutes, 10) || 60,
                  new Date(card.dataset.expiresAt).getTime() - offset);
            return;
        }
        fetch(INFO_URL, { credentials: 'same-origin',
                          headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (res) { return res.ok ? res.json() : null; })
            .then(function (data) {
                if (!data || !data.success) return;
                var offset = new Date(data.server_time).getTime() - Date.now();
                start(data.timeout_minutes || 60,
                      new Date(data.expires_at).getTime() - offset);
            })
            .catch(function () {});
    });
})();
