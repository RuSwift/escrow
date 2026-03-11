/**
 * Точка входа Vue 2 приложения main (авторизованный вид).
 * Загружать после vue.min.js и всех компонентов.
 * Ожидает: <div id="app-main" data-initial-page="dashboard"></div>
 */
(function() {
    var el = document.getElementById('app-main');
    if (!el) return;

    var initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
    var validPages = ['dashboard', 'my-trusts', 'how-it-works', 'api', 'settings', 'support'];
    if (validPages.indexOf(initialPage) === -1) {
        initialPage = 'dashboard';
    }

    var vm = new Vue({
        el: '#app-main',
        delimiters: ['[[', ']]'],
        data: {
            currentPage: initialPage
        },
        template: '<transition name="fade" mode="out-in"><component :is="currentPage" :key="currentPage" /></transition>'
    });
    window.__mainApp = vm;
})();
