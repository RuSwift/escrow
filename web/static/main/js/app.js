/**
 * Точка входа Vue 2 приложения main (авторизованный вид).
 * Загружать после vue.min.js и всех компонентов.
 * Ожидает: <div id="app-main" data-initial-page="dashboard" data-escrow-id="" data-space=""></div>
 */
(function() {
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
    window.__SPACE_ROLE__ = spaceRole;
    window.__SPACE_SUBS_COUNT__ = spaceSubsCount;

    var initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
    var validPages = ['dashboard', 'my-trusts', 'how-it-works', 'api', 'settings', 'support', 'detail'];
    if (spaceRole === 'owner') validPages.push('space-roles');
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
