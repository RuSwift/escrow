/**
 * Точка входа Vue 2 приложения ноды.
 * Загружать после vue.min.js и всех компонентов (dashboard.js, wallet-users.js, ...).
 *
 * Ожидает в разметке: <div id="app" data-initial-page="dashboard" data-is-node-initialized="false"></div>
 */
(function() {
    var el = document.getElementById('app');
    if (!el) return;

    var initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
    var isNodeInitialized = el.getAttribute('data-is-node-initialized') === 'true';

    var validPages = ['dashboard', 'wallet-users', 'arbiter', 'wallets', 'node', 'admin', 'settings', 'support'];
    if (validPages.indexOf(initialPage) === -1) {
        initialPage = 'dashboard';
    }

    var vm = new Vue({
        el: '#app',
        delimiters: ['[[', ']]'],
        data: {
            currentPage: initialPage,
            isNodeInitialized: isNodeInitialized
        },
        template: '<transition name="fade" mode="out-in"><component :is="currentPage" :key="currentPage" :is-node-initialized="isNodeInitialized" /></transition>'
    });
    window.__nodeApp = vm;
})();
