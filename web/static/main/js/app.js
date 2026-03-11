/**
 * Точка входа Vue 2 приложения main (авторизованный вид).
 * Загружать после vue.min.js и всех компонентов.
 * Ожидает: <div id="app-main" data-initial-page="dashboard" data-escrow-id=""></div>
 */
(function() {
    var el = document.getElementById('app-main');
    if (!el) return;

    var initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
    var validPages = ['dashboard', 'my-trusts', 'how-it-works', 'api', 'settings', 'support', 'detail'];
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
