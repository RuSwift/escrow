/**
 * Точка входа Vue 2 приложения main (авторизованный вид).
 * Загружать после vue.min.js и всех компонентов.
 * Ожидает: <div id="app-main" data-initial-page="dashboard" data-escrow-id="" data-space=""></div>
 */
(function() {
    var INVITE_REMINDER_KEY = 'main_invite_wallet_reminder';
    (function initInviteWalletReminderModal() {
        if (typeof window.showInviteWalletReminderModal !== 'function') return;
        var raw = null;
        try {
            raw = sessionStorage.getItem(INVITE_REMINDER_KEY);
        } catch (e) {}
        if (!raw) return;
        var parsed = null;
        try {
            parsed = JSON.parse(raw);
        } catch (e) {}
        if (!parsed || (!parsed.previous && !parsed.masked)) return;

        window.showInviteWalletReminderModal({
            previous: parsed.previous || parsed.masked,
            masked: parsed.masked,
            onContinue: function() {
                try {
                    sessionStorage.removeItem(INVITE_REMINDER_KEY);
                } catch (e) {}
            },
            onRelogin: function() {
                try {
                    sessionStorage.removeItem(INVITE_REMINDER_KEY);
                } catch (e) {}
                fetch('/v1/auth/logout', { method: 'POST', credentials: 'same-origin' }).finally(function() {
                    try {
                        var k = window.main_auth_token_key || 'main_auth_token';
                        localStorage.removeItem(k);
                    } catch (e) {}
                    window.location.href = '/';
                });
            }
        });
    })();

    var el = document.getElementById('app-main');
    if (!el) return;

    var spaceFromPath = (el.getAttribute('data-space') || '').trim();
    var savedSpace = null;
    try { savedSpace = localStorage.getItem('main_current_space'); } catch (e) {}
    if (spaceFromPath && savedSpace && savedSpace !== spaceFromPath && typeof window.showConfirm === 'function') {
        var t = window.__TRANSLATIONS__ || {};
        var title = (t['main.space.switch_confirm_title'] !== undefined) ? t['main.space.switch_confirm_title'] : 'Different space';
        var message = (t['main.space.switch_confirm_message'] !== undefined) ? t['main.space.switch_confirm_message'] : 'You are switching to another space. Continue?';
        window.showConfirm({
            title: title,
            message: message,
            onConfirm: function() {
                try { localStorage.setItem('main_current_space', spaceFromPath); } catch (e) {}
                window.__CURRENT_SPACE__ = spaceFromPath;
            },
            onCancel: function() {
                window.location.href = '/' + encodeURIComponent(savedSpace);
            }
        });
    } else if (spaceFromPath) {
        try { localStorage.setItem('main_current_space', spaceFromPath); } catch (e) {}
        window.__CURRENT_SPACE__ = spaceFromPath;
    }

    var spaceRole = (el.getAttribute('data-space-role') || '').trim();
    var spaceSubsCount = parseInt(el.getAttribute('data-space-subs-count'), 10);
    if (isNaN(spaceSubsCount)) spaceSubsCount = -1;
    var spaceProfileFilled = (el.getAttribute('data-space-profile-filled') || 'false') === 'true';
    window.__SPACE_ROLE__ = spaceRole;
    window.__SPACE_SUBS_COUNT__ = spaceSubsCount;
    window.__SPACE_PROFILE_FILLED__ = spaceProfileFilled;
    window.__SPACE_OWNER_TRON__ = (el.getAttribute('data-space-owner-tron') || '').trim();

    var initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
    var validPages = [
        'dashboard',
        'my-trusts',
        'how-it-works',
        'api',
        'settings',
        'support',
        'detail',
    ];
    if (spaceRole === 'owner') {
        validPages.push('space-roles', 'space-profile', 'my-business', 'guarantor');
    }
    if (validPages.indexOf(initialPage) === -1) {
        initialPage = 'dashboard';
    }
    var escrowIdFromUrl = (el.getAttribute('data-escrow-id') || '').trim();
    if (initialPage === 'detail' && !escrowIdFromUrl) {
        initialPage = 'dashboard';
    }

    var vm = new Vue({
        el: '#app-main',
        delimiters: ['[[', ']]'],
        data: {
            currentPage: initialPage,
            selectedEscrowId: initialPage === 'detail' ? escrowIdFromUrl : null
        },
        computed: {
            detailKey: function() {
                return this.currentPage === 'detail' ? 'detail-' + (this.selectedEscrowId || '') : this.currentPage;
            }
        },
        template: '<transition name="fade" mode="out-in"><component :is="currentPage" :key="detailKey" :escrow-id="selectedEscrowId" /></transition>'
    });
    window.__mainApp = vm;
    if (vm.currentPage === 'detail') {
        var sidebarEl = document.querySelector('#sidebar-main');
        if (sidebarEl && sidebarEl.__vue__) sidebarEl.__vue__.currentPage = 'dashboard';
    }
})();
