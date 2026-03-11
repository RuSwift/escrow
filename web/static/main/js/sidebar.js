/**
 * Сайдбар main-приложения: навигация и индикатор.
 * Монтируется в #sidebar-main. Связь с приложением через window.__mainApp.
 */
(function() {
    if (typeof Vue !== "undefined") {
        Vue.prototype.$t = function(key, params) {
            var t = window.__TRANSLATIONS__;
            var s = (t && t[key] !== undefined) ? t[key] : key;
            if (params && typeof s === 'string') {
                Object.keys(params).forEach(function(k) {
                    s = s.replace(new RegExp('\\{\\{\\s*' + k + '\\s*\\}\\}', 'g'), params[k]);
                });
            }
            return s;
        };
    }
    var SIDEBAR_ITEMS = [
        { page: 'dashboard', labelKey: 'main.sidebar.dashboard', section: 'tools' },
        { page: 'my-trusts', labelKey: 'main.sidebar.my_trusts', section: 'tools' },
        { page: 'how-it-works', labelKey: 'main.sidebar.how_it_works', section: 'docs' },
        { page: 'api', labelKey: 'main.sidebar.api', section: 'docs' },
        { page: 'settings', labelKey: 'main.sidebar.settings', section: 'bottom' },
        { page: 'support', labelKey: 'main.sidebar.support', section: 'bottom' }
    ];

    var PAGE_TO_PATH = {
        'dashboard': '/app',
        'my-trusts': '/app?initial_page=my-trusts',
        'how-it-works': '/app?initial_page=how-it-works',
        'api': '/app?initial_page=api',
        'settings': '/app?initial_page=settings',
        'support': '/app?initial_page=support'
    };

    function pathToPage(path) {
        if (!path || path === '/app') return 'dashboard';
        var match = path && path.indexOf('initial_page=') !== -1 && path.split('initial_page=')[1];
        var page = match ? match.split('&')[0] : 'dashboard';
        return SIDEBAR_ITEMS.some(function(item) { return item.page === page; }) ? page : 'dashboard';
    }

    new Vue({
        el: '#sidebar-main',
        delimiters: ['[[', ']]'],
        data: {
            appName: 'Escrow',
            currentPage: 'dashboard',
            ballTop: 0,
            ballVisible: false
        },
        mounted: function() {
            var el = this.$el;
            if (el.getAttribute('data-app-name')) this.appName = el.getAttribute('data-app-name');
            var pageFromUrl = pathToPage(window.location.search);
            var initial = (el.getAttribute('data-initial-page') || 'dashboard').trim();
            if (SIDEBAR_ITEMS.some(function(item) { return item.page === pageFromUrl; })) {
                this.currentPage = pageFromUrl;
            } else if (SIDEBAR_ITEMS.some(function(item) { return item.page === initial; })) {
                this.currentPage = initial;
            }
            var self = this;
            function showBallAfterLayout() {
                requestAnimationFrame(function() {
                    requestAnimationFrame(function() {
                        self.updateBallPosition();
                        self.ballVisible = true;
                        setTimeout(function() { self.updateBallPosition(); }, 100);
                    });
                });
            }
            this.$nextTick(showBallAfterLayout);
            window.addEventListener('popstate', function() {
                var page = pathToPage(window.location.search) || pathToPage(window.location.pathname + window.location.search);
                self.currentPage = page;
                if (window.__mainApp) window.__mainApp.currentPage = page;
                self.$nextTick(function() { self.updateBallPosition(); });
            });
            window.addEventListener('resize', function() { self.$nextTick(function() { self.updateBallPosition(); }); });
            var navEl = this.$el.querySelector('.sidebar-nav');
            if (navEl) navEl.addEventListener('scroll', function() { self.updateBallPosition(); });
        },
        updated: function() {
            this.$nextTick(this.updateBallPosition);
        },
        methods: {
            go: function(page) {
                if (this.currentPage === page) return;
                this.currentPage = page;
                var path = PAGE_TO_PATH[page] || '/app';
                history.pushState({ page: page }, '', path);
                if (window.__mainApp) window.__mainApp.currentPage = page;
            },
            updateBallPosition: function() {
                var link = this.$el.querySelector('[data-page="' + this.currentPage + '"]');
                if (!link) return;
                var linkRect = link.getBoundingClientRect();
                var wrapRect = this.$el.getBoundingClientRect();
                this.ballTop = (linkRect.top - wrapRect.top) + (link.offsetHeight / 2) - 3;
            }
        },
        template: [
            '<div class="sidebar-wrap w-64 bg-[#0a0b0d] text-white flex flex-col border-r border-white/5 shrink-0 relative h-screen overflow-y-auto">',
            '  <div :style="{ top: ballVisible ? (ballTop + \'px\') : \'-999px\' }" class="sidebar-ball main-sidebar-ball"></div>',
            '  <div class="p-6 flex items-center gap-3">',
            '    <div class="w-8 h-8 bg-main-blue rounded-lg flex items-center justify-center shadow-lg shrink-0">',
            '      <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>',
            '    </div>',
            '    <h1 class="text-white font-bold text-base tracking-tight">[[ appName ]]</h1>',
            '  </div>',
            '  <nav class="sidebar-nav flex-1 overflow-y-auto py-2 px-2">',
            '    <div class="px-3 mb-4 text-[10px] font-bold text-white/30 uppercase tracking-widest">[[ $t(\'main.sidebar.section_tools\') ]]</div>',
            '    <a href="/app" data-page="dashboard" @click.prevent="go(\'dashboard\')" :class="currentPage === \'dashboard\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.dashboard\') ]]</span>',
            '    </a>',
            '    <a href="/app?initial_page=my-trusts" data-page="my-trusts" @click.prevent="go(\'my-trusts\')" :class="currentPage === \'my-trusts\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.my_trusts\') ]]</span>',
            '    </a>',
            '    <div class="px-3 mb-4 mt-6 text-[10px] font-bold text-white/30 uppercase tracking-widest">[[ $t(\'main.sidebar.section_docs\') ]]</div>',
            '    <a href="/app?initial_page=how-it-works" data-page="how-it-works" @click.prevent="go(\'how-it-works\')" :class="currentPage === \'how-it-works\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.how_it_works\') ]]</span>',
            '    </a>',
            '    <a href="/app?initial_page=api" data-page="api" @click.prevent="go(\'api\')" :class="currentPage === \'api\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.api\') ]]</span>',
            '    </a>',
            '  </nav>',
            '  <div class="p-4 border-t border-white/5 space-y-1">',
            '    <a href="/app?initial_page=settings" data-page="settings" @click.prevent="go(\'settings\')" :class="currentPage === \'settings\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.settings\') ]]</span>',
            '    </a>',
            '    <a href="/app?initial_page=support" data-page="support" @click.prevent="go(\'support\')" :class="currentPage === \'support\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.support\') ]]</span>',
            '    </a>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
