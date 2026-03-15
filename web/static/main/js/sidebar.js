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
        { page: 'space-roles', labelKey: 'main.sidebar.roles', section: 'tools', ownerOnly: true },
        { page: 'how-it-works', labelKey: 'main.sidebar.how_it_works', section: 'docs' },
        { page: 'api', labelKey: 'main.sidebar.api', section: 'docs' },
        { page: 'settings', labelKey: 'main.sidebar.settings', section: 'bottom' },
        { page: 'support', labelKey: 'main.sidebar.support', section: 'bottom' }
    ];

    function pathToPage(path, search, spaceRole) {
        if (!path) return 'dashboard';
        var searchStr = search || (typeof window !== 'undefined' ? window.location.search : '');
        var match = searchStr.indexOf('initial_page=') !== -1 && searchStr.split('initial_page=')[1];
        var page = match ? match.split('&')[0].split('#')[0] : 'dashboard';
        if (!SIDEBAR_ITEMS.some(function(item) { return item.page === page; })) return 'dashboard';
        if (page === 'space-roles' && spaceRole !== 'owner') return 'dashboard';
        return page;
    }

    function getPathForPage(space, page) {
        var base = space ? '/' + encodeURIComponent(space) : '/app';
        return page === 'dashboard' ? base : base + '?initial_page=' + encodeURIComponent(page);
    }

    function truncateMiddle(str, maxLen) {
        if (!str || str.length <= maxLen) return str || '';
        var half = Math.floor((maxLen - 3) / 2);
        return str.slice(0, half) + '...' + str.slice(-(maxLen - 3 - half));
    }

    function setupHeaderDid(el, did) {
        if (!el) return;
        if (!did) {
            el.textContent = '';
            el.title = '';
            el.removeAttribute('data-did');
            el.onclick = null;
            return;
        }
        el.setAttribute('data-did', did);
        el.title = did;
        el.textContent = truncateMiddle(did, 36);
        el.onclick = function() {
            var d = el.getAttribute('data-did');
            if (!d) return;
            navigator.clipboard.writeText(d).then(function() {
                var label = el.getAttribute('data-copy-label') || 'Copied!';
                var orig = el.textContent;
                el.textContent = label;
                el.title = label;
                setTimeout(function() {
                    el.textContent = orig;
                    el.title = d;
                }, 2000);
            });
        };
    }

    new Vue({
        el: '#sidebar-main',
        delimiters: ['[[', ']]'],
        data: {
            appName: 'Escrow',
            currentPage: 'dashboard',
            currentSpace: '',
            spaceRole: '',
            ballTop: 0,
            ballVisible: false,
            sidebarOpen: false,
            currentUser: null
        },
        beforeMount: function() {
            var el = this.$el;
            if (el.getAttribute('data-app-name')) this.appName = el.getAttribute('data-app-name');
            this.currentSpace = (el.getAttribute('data-space') || '').trim();
            this.spaceRole = (el.getAttribute('data-space-role') || '').trim();
            this._initialPage = (el.getAttribute('data-initial-page') || 'dashboard').trim();
        },
        mounted: function() {
            var el = this.$el;
            if (!this.currentSpace && window.location.pathname) {
                var segments = window.location.pathname.split('/').filter(Boolean);
                if (segments.length > 0) this.currentSpace = segments[0];
            }
            if (this.currentSpace) window.__CURRENT_SPACE__ = this.currentSpace;
            var pageFromUrl = pathToPage(window.location.pathname, window.location.search, this.spaceRole);
            var initial = this._initialPage || 'dashboard';
            if (initial === 'space-roles' && this.spaceRole !== 'owner') initial = 'dashboard';
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
            var auth = this.get_current_user;
            if (auth) auth().then(function(u) {
                self.currentUser = u;
                setupHeaderDid(document.getElementById('header-user-did'), u && u.did ? u.did : '');
            });
            window.addEventListener('popstate', function() {
                var params = new URLSearchParams(window.location.search);
                var page = params.get('initial_page') || 'dashboard';
                var escrowId = params.get('escrow_id') || '';
                if (page === 'detail' && escrowId) {
                    self.currentPage = 'dashboard';
                    if (window.__mainApp) {
                        window.__mainApp.currentPage = 'detail';
                        window.__mainApp.selectedEscrowId = escrowId;
                    }
                } else {
                    if (page !== 'dashboard' && !SIDEBAR_ITEMS.some(function(item) { return item.page === page; })) page = 'dashboard';
                    if (page === 'space-roles' && self.spaceRole !== 'owner') page = 'dashboard';
                    self.currentPage = page;
                    if (window.__mainApp) {
                        window.__mainApp.currentPage = page;
                        window.__mainApp.selectedEscrowId = null;
                    }
                }
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
                var path = getPathForPage(this.currentSpace, page);
                history.pushState({ page: page }, '', path);
                if (window.__mainApp) {
                    window.__mainApp.currentPage = page;
                    if (page === 'dashboard') window.__mainApp.selectedEscrowId = null;
                }
            },
            basePath: function() {
                return this.currentSpace ? '/' + encodeURIComponent(this.currentSpace) : '/app';
            },
            pageHref: function(page) {
                return getPathForPage(this.currentSpace, page);
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
            '<div id="sidebar-main" class="sidebar-root">',
            '  <div v-show="sidebarOpen" class="sidebar-overlay fixed inset-0 bg-black/50 z-30 md:hidden transition-opacity" @click="sidebarOpen = false" aria-hidden="true"></div>',
            '  <div class="sidebar-wrap w-64 bg-[#0a0b0d] text-white flex flex-col border-r border-white/5 shrink-0 relative h-screen overflow-y-auto fixed md:relative inset-y-0 left-0 z-40 -translate-x-full md:translate-x-0 transition-transform duration-200 ease-out" :class="{ \'translate-x-0\': sidebarOpen }">',
            '  <div :style="{ top: ballVisible ? (ballTop + \'px\') : \'-999px\' }" class="sidebar-ball main-sidebar-ball"></div>',
            '  <div class="p-6 flex items-center justify-between gap-3">',
            '    <div class="flex items-center gap-3 min-w-0">',
            '      <div class="w-8 h-8 bg-main-blue rounded-lg flex items-center justify-center shadow-lg shrink-0">',
            '        <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>',
            '      </div>',
            '      <h1 class="text-white font-bold text-base tracking-tight truncate">[[ appName ]]</h1>',
            '    </div>',
            '    <button type="button" class="md:hidden p-2 -mr-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors shrink-0" :aria-label="$t(\'main.sidebar.close_menu\')" @click="sidebarOpen = false">',
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>',
            '    </button>',
            '  </div>',
            '  <nav class="sidebar-nav flex-1 overflow-y-auto py-2 px-2">',
            '    <div class="px-3 mb-4 text-[10px] font-bold text-white/30 uppercase tracking-widest">[[ $t(\'main.sidebar.section_tools\') ]]</div>',
            '    <a :href="pageHref(\'dashboard\')" data-page="dashboard" @click.prevent="go(\'dashboard\')" :class="currentPage === \'dashboard\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.dashboard\') ]]</span>',
            '    </a>',
            '    <a :href="pageHref(\'my-trusts\')" data-page="my-trusts" @click.prevent="go(\'my-trusts\')" :class="currentPage === \'my-trusts\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.my_trusts\') ]]</span>',
            '    </a>',
            '    <a v-if="spaceRole === \'owner\'" :href="pageHref(\'space-roles\')" data-page="space-roles" @click.prevent="go(\'space-roles\')" :class="currentPage === \'space-roles\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.roles\') ]]</span>',
            '    </a>',
            '    <div class="px-3 mb-4 mt-6 text-[10px] font-bold text-white/30 uppercase tracking-widest">[[ $t(\'main.sidebar.section_docs\') ]]</div>',
            '    <a :href="pageHref(\'how-it-works\')" data-page="how-it-works" @click.prevent="go(\'how-it-works\')" :class="currentPage === \'how-it-works\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.how_it_works\') ]]</span>',
            '    </a>',
            '    <a :href="pageHref(\'api\')" data-page="api" @click.prevent="go(\'api\')" :class="currentPage === \'api\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.api\') ]]</span>',
            '    </a>',
            '  </nav>',
            '  <div class="py-4 px-2 border-t border-white/5 space-y-1">',
            '    <a :href="pageHref(\'settings\')" data-page="settings" @click.prevent="go(\'settings\')" :class="currentPage === \'settings\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.settings\') ]]</span>',
            '    </a>',
            '    <a :href="pageHref(\'support\')" data-page="support" @click.prevent="go(\'support\')" :class="currentPage === \'support\' ? \'sidebar-item main-sidebar-item active\' : \'sidebar-item main-sidebar-item\'">',
            '      <svg class="w-[18px] h-[18px] mr-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '      <span class="text-[13px] font-medium tracking-tight">[[ $t(\'main.sidebar.support\') ]]</span>',
            '    </a>',
            '  </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
