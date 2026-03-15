/**
 * Сайдбар ноды: клиентская навигация и анимированный индикатор-шарик.
 * Монтируется в #sidebar-app. Связывается с основным приложением через window.__nodeApp.
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
        { page: 'dashboard', label: 'Дашборд', section: 'tools' },
        { page: 'wallet-users', label: 'Пользователи', section: 'marketplace' },
        { page: 'arbiter', label: 'Арбитр', section: 'marketplace' },
        { page: 'wallets', label: 'Кошельки', section: 'admin' },
        { page: 'node', label: 'Нода', section: 'admin' },
        { page: 'admin', label: 'Админ', section: 'admin' },
        { page: 'support', label: 'Поддержка', section: 'footer' }
    ];

    var PAGE_TO_PATH = {
        'dashboard': '/',
        'wallet-users': '/wallet-users',
        'arbiter': '/arbiter',
        'wallets': '/wallets',
        'node': '/node',
        'admin': '/admin'
    };

    function pathToPage(path) {
        if (!path || path === '/') return 'dashboard';
        var p = path.replace(/^\//, '');
        return PAGE_TO_PATH[p] !== undefined ? p : 'dashboard';
    }

    new Vue({
        el: '#sidebar-app',
        delimiters: ['[[', ']]'],
        data: {
            appName: 'Escrow Node',
            currentPage: 'dashboard',
            ballTop: 0,
            ballVisible: false,
            showSupportModal: false,
            sidebarOpen: false
        },
        mounted: function() {
            var el = this.$el;
            var name = el.getAttribute('data-app-name');
            if (name) this.appName = name;
            // При прямой загрузке по URL синхронизируем с pathname, иначе — с data-initial-page
            var pageFromUrl = pathToPage(window.location.pathname);
            if (SIDEBAR_ITEMS.some(function(item) { return item.page === pageFromUrl; })) {
                this.currentPage = pageFromUrl;
            } else {
                var initial = (el.getAttribute('data-initial-page') || 'dashboard').trim();
                if (SIDEBAR_ITEMS.some(function(item) { return item.page === initial; })) {
                    this.currentPage = initial;
                }
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
            window.addEventListener('popstate', function(e) {
                var page = e.state && e.state.page ? e.state.page : pathToPage(window.location.pathname);
                self.currentPage = page;
                if (window.__nodeApp) window.__nodeApp.currentPage = page;
                self.$nextTick(function() { self.updateBallPosition(); });
            });
            window.addEventListener('resize', function() {
                self.$nextTick(function() { self.updateBallPosition(); });
                self.syncDrawerDisplay();
            });
            var navEl = this.$el.querySelector('.sidebar-nav');
            if (navEl) navEl.addEventListener('scroll', function() { self.updateBallPosition(); });
            var toggleBtn = document.getElementById('sidebar-toggle');
            if (toggleBtn) toggleBtn.addEventListener('click', function() { self.sidebarOpen = true; });
            this.syncDrawerDisplay();
        },
        updated: function() {
            this.$nextTick(this.updateBallPosition);
            this.syncDrawerDisplay();
        },
        methods: {
            syncDrawerDisplay: function() {
                if (!this.$el || !this.$el.style) return;
                if (window.innerWidth < 768) {
                    this.$el.style.display = this.sidebarOpen ? 'block' : 'none';
                } else {
                    this.$el.style.display = '';
                }
            },
            go: function(page) {
                if (this.currentPage === page) return;
                this.currentPage = page;
                this.sidebarOpen = false;
                var path = PAGE_TO_PATH[page] || '/';
                history.pushState({ page: page }, '', path);
                if (window.__nodeApp) window.__nodeApp.currentPage = page;
            },
            updateBallPosition: function() {
                var link = this.$el.querySelector('[data-page="' + this.currentPage + '"]');
                if (!link) return;
                var wrap = this.$el.querySelector('.sidebar-wrap');
                var wrapRect = wrap ? wrap.getBoundingClientRect() : this.$el.getBoundingClientRect();
                var linkRect = link.getBoundingClientRect();
                this.ballTop = (linkRect.top - wrapRect.top) + (link.offsetHeight / 2) - 3;
            }
        },
        template: [
            '<div class="sidebar-root">',
            '  <div v-show="sidebarOpen" class="sidebar-overlay fixed inset-0 bg-black/50 z-30 md:hidden transition-opacity" @click="sidebarOpen = false" aria-hidden="true"></div>',
            '  <div class="sidebar-wrap w-64 bg-zinc-950 h-screen flex flex-col border-r border-zinc-800/50 shrink-0 relative fixed md:relative inset-y-0 left-0 z-40 -translate-x-full md:translate-x-0 transition-transform duration-200 ease-out" :class="{ \'translate-x-0\': sidebarOpen }">',
            '  <div :style="{ top: ballVisible ? (ballTop + \'px\') : \'-999px\' }" class="sidebar-ball"></div>',
            '  <div class="p-6 flex items-center justify-between gap-3">',
            '    <div class="flex items-center gap-3 min-w-0">',
            '      <div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20 shrink-0">',
            '        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>',
            '      </div>',
            '      <h1 class="text-white font-bold text-base tracking-tight truncate">[[ appName ]]</h1>',
            '    </div>',
            '    <button type="button" class="md:hidden p-2 -mr-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors shrink-0" :aria-label="$t(\'node.sidebar.close_menu\')" @click="sidebarOpen = false">',
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>',
            '    </button>',
            '  </div>',
            '  <nav class="sidebar-nav flex-1 overflow-y-auto py-2 px-2">',
            '    <div class="px-6 py-4 mt-2 text-[10px] font-bold text-zinc-500 uppercase tracking-[0.15em]">[[ $t(\'node.sidebar.section_tools\') ]]</div>',
            '    <a href="/" data-page="dashboard" @click.prevent="go(\'dashboard\')" :class="currentPage === \'dashboard\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.dashboard\') ]]</span>',
            '    </a>',
            '    <div class="px-6 py-4 mt-2 text-[10px] font-bold text-zinc-500 uppercase tracking-[0.15em]">[[ $t(\'node.sidebar.section_marketplace\') ]]</div>',
            '    <a href="/wallet-users" data-page="wallet-users" @click.prevent="go(\'wallet-users\')" :class="currentPage === \'wallet-users\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.wallet-users\') ]]</span>',
            '    </a>',
            '    <a href="/arbiter" data-page="arbiter" @click.prevent="go(\'arbiter\')" :class="currentPage === \'arbiter\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.arbiter\') ]]</span>',
            '    </a>',
            '    <div class="px-6 py-4 mt-2 text-[10px] font-bold text-zinc-500 uppercase tracking-[0.15em]">[[ $t(\'node.sidebar.section_admin\') ]]</div>',
            '    <a href="/wallets" data-page="wallets" @click.prevent="go(\'wallets\')" :class="currentPage === \'wallets\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.wallets\') ]]</span>',
            '    </a>',
            '    <a href="/node" data-page="node" @click.prevent="go(\'node\')" :class="currentPage === \'node\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.node\') ]]</span>',
            '    </a>',
            '    <a href="/admin" data-page="admin" @click.prevent="go(\'admin\')" :class="currentPage === \'admin\' ? \'sidebar-item active\' : \'sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.admin\') ]]</span>',
            '    </a>',
            '  </nav>',
            '  <div class="p-4 border-t border-zinc-900">',
            '    <a href="#" class="sidebar-item" @click.prevent="sidebarOpen = false; showSupportModal = true">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'node.sidebar.support\') ]]</span>',
            '    </a>',
            '  </div>',
            '  <modal :show="showSupportModal" :title="$t(\'node.sidebar.support\')" @close="showSupportModal = false">',
            '    <p class="text-[13px] text-zinc-700 mb-3">[[ $t(\'node.support.description\') ]]</p>',
            '    <p class="text-[13px] text-zinc-700">[[ $t(\'node.support.telegram_text\') ]] <a href="https://t.me/ruswift_support" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline font-medium">@ruswift_support</a></p>',
            '  </modal>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
