/**
 * Блок авторизации на лендинге: кнопка «Войти» → событие → модалка на уровне body (tron-login) → редирект в /app.
 * Модалка монтируется в #landing-login-modal (прямой вызов JS, без рендера внутри header).
 * Подключать после vue.min.js, auth.js, tron-login.js.
 */
(function() {
    if (typeof Vue === 'undefined') return;
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

    var headerEl = document.getElementById('landing-header-auth');
    var headerVue = null;
    if (headerEl) {
        headerVue = new Vue({
            el: '#landing-header-auth',
            delimiters: ['[[', ']]'],
            data: {
                currentUser: null,
                showSpacePicker: false
            },
            mounted: function() {
                var self = this;
                var getCurrent = window.get_current_user;
                if (getCurrent) getCurrent().then(function(u) { self.currentUser = u; });
                document.addEventListener('click', function(e) {
                    if (self.showSpacePicker && !self.$el.contains(e.target)) self.showSpacePicker = false;
                });
                window.addEventListener('open-landing-go-to-app', function() {
                    if (self.currentUser) self.showSpacePicker = true;
                    else self.openLogin();
                });
            },
            methods: {
                openLogin: function() {
                    window.dispatchEvent(new CustomEvent('open-landing-login'));
                },
            goToSpace: function(space) {
                if (!space) return;
                var next = (new URLSearchParams(window.location.search)).get('next');
                // Если в next указан именно этот спейс, переходим по нему (там может быть initial_page)
                if (next && next.startsWith('/') && decodeURIComponent(next.split('/')[1]) === space) {
                    window.location.href = next;
                } else {
                    window.location.href = '/' + encodeURIComponent(space);
                }
            },
            truncateMiddle: function(str, maxLen) {
                    if (!str || str.length <= maxLen) return str || '';
                    var half = Math.floor((maxLen - 3) / 2);
                    return str.slice(0, half) + '...' + str.slice(-(maxLen - 3 - half));
                }
            },
            computed: {
                spaces: function() {
                    return (this.currentUser && this.currentUser.spaces && Array.isArray(this.currentUser.spaces)) ? this.currentUser.spaces : [];
                }
            },
            template:
                '<div class="flex items-center gap-3">' +
                '  <template v-if="currentUser">' +
                '    <div class="flex flex-col items-center gap-1 relative">' +
                '      <button type="button" @click.stop="showSpacePicker = !showSpacePicker" class="px-6 py-2.5 bg-white text-black rounded-full font-bold hover:bg-main-blue hover:text-white transition-all duration-300 inline-flex items-center gap-2">' +
                '        [[ $t(\'main.landing.go_to_app\') ]]' +
                '        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>' +
                '      </button>' +
                '      <div v-if="showSpacePicker && spaces.length" class="absolute top-full left-1/2 -translate-x-1/2 mt-2 z-50 bg-white rounded-xl shadow-lg border border-gray-200 p-3 min-w-[180px]">' +
                '        <p class="text-xs text-gray-500 mb-2">[[ $t(\'main.space.choose_space\') ]]</p>' +
                '        <div class="space-y-1.5">' +
                '          <button v-for="s in spaces" :key="s" type="button" @click="goToSpace(s)" class="w-full px-3 py-2 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600 text-left">[[ s ]]</button>' +
                '        </div>' +
                '      </div>' +
                '      <span class="text-xs text-white/50 font-mono max-w-[140px] text-center" :title="currentUser.did">[[ truncateMiddle(currentUser.did, 28) ]]</span>' +
                '    </div>' +
                '  </template>' +
                '  <button v-else type="button" @click="openLogin" class="px-6 py-2.5 bg-white text-black rounded-full font-bold hover:bg-main-blue hover:text-white transition-all duration-300 inline-flex items-center gap-2">' +
                '    [[ $t(\'main.login\') ]]' +
                '    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>' +
                '  </button>' +
                '</div>'
        });
        window.landing_go_to_app = function() {
            console.log('[landing-auth] landing_go_to_app called, headerVue:', !!headerVue, 'currentUser:', headerVue ? !!headerVue.currentUser : '-');
            if (headerVue) {
                if (headerVue.currentUser) {
                    var spaces = (headerVue.currentUser.spaces && Array.isArray(headerVue.currentUser.spaces)) ? headerVue.currentUser.spaces : [];
                    if (spaces.length) {
                        window.dispatchEvent(new CustomEvent('open-landing-space-picker', { detail: { spaces: spaces } }));
                        console.log('[landing-auth] dispatched open-landing-space-picker');
                    } else {
                        headerVue.showSpacePicker = true;
                        console.log('[landing-auth] showSpacePicker=true (no spaces in user)');
                    }
                } else {
                    headerVue.openLogin();
                    console.log('[landing-auth] openLogin()');
                }
            } else {
                window.dispatchEvent(new CustomEvent('open-landing-login'));
                console.log('[landing-auth] dispatched open-landing-login');
            }
        };
    }
    document.addEventListener('click', function(e) {
        var t = e.target;
        if (!t) return;
        var isStart = t.id === 'landing-cta-start' || (t.closest && t.closest('#landing-cta-start'));
        if (isStart) {
            console.log('[landing-auth] click on landing-cta-start (delegated), landing_go_to_app:', typeof window.landing_go_to_app);
            if (window.landing_go_to_app) window.landing_go_to_app();
        }
    });

    var modalEl = document.getElementById('landing-login-modal');
    if (!modalEl) return;

    new Vue({
        el: '#landing-login-modal',
        delimiters: ['[[', ']]'],
        data: {
            showLogin: false,
            showSpacePickerOnly: false,
            spacePickerSpaces: [],
            viewport: { w: 0, h: 0 },
            afterSuccess: null,
            spaces: [],
            token: '',
            initNickname: '',
            initError: '',
            initLoading: false
        },
        mounted: function() {
            var self = this;
            window.addEventListener('open-landing-login', function() { self.openLogin(); });
            window.addEventListener('open-landing-space-picker', function(e) {
                var list = (e.detail && e.detail.spaces && Array.isArray(e.detail.spaces)) ? e.detail.spaces : [];
                self._setViewport();
                self.spacePickerSpaces = list;
                self.showSpacePickerOnly = true;
                document.body.style.overflow = 'hidden';
            });
            document.addEventListener('keydown', this._onKeydown);
            window.addEventListener('resize', this._onResize);
        },
        beforeDestroy: function() {
            document.removeEventListener('keydown', this._onKeydown);
            window.removeEventListener('resize', this._onResize);
            document.body.style.overflow = '';
            this.showSpacePickerOnly = false;
        },
        methods: {
            _onKeydown: function(e) {
                if (e.key === 'Escape') {
                    if (this.showSpacePickerOnly) this.closeSpacePickerOnly();
                    else if (this.showLogin) this.closeLogin();
                }
            },
            _onResize: function() {
                if (this.showLogin || this.showSpacePickerOnly) this._setViewport();
            },
            closeSpacePickerOnly: function() {
                this.showSpacePickerOnly = false;
                this.spacePickerSpaces = [];
                document.body.style.overflow = '';
            },
            _setViewport: function() {
                this.viewport = { w: window.innerWidth, h: window.innerHeight };
            },
            onTronSuccess: function(payload) {
                console.log('[landing-auth] onTronSuccess payload:', payload);
                var key = window.main_auth_token_key || 'main_auth_token';
                try { localStorage.setItem(key, payload.token); } catch (e) {}
                this.token = payload.token || '';
                this.spaces = payload.spaces || [];
                console.log('[landing-auth] afterSuccess will be:', this.spaces.length > 0 ? 'choose' : 'init', 'spaces:', this.spaces);
                if (this.spaces.length > 0) {
                    this.afterSuccess = 'choose';
                } else {
                    this.afterSuccess = 'init';
                }
            },
            goToSpace: function(space) {
                if (!space) return;
                var next = (new URLSearchParams(window.location.search)).get('next');
                // Если в next указан именно этот спейс, переходим по нему (там может быть initial_page)
                if (next && next.startsWith('/') && decodeURIComponent(next.split('/')[1]) === space) {
                    window.location.href = next;
                } else {
                    window.location.href = '/' + encodeURIComponent(space);
                }
            },
            submitInit: function() {
                var self = this;
                var nick = (this.initNickname || '').trim();
                if (!nick) {
                    this.initError = this.$t('main.space.init_nickname_required');
                    return;
                }
                this.initError = '';
                this.initLoading = true;
                var token = this.token || (window.main_auth_token_key && localStorage.getItem(window.main_auth_token_key));
                fetch('/v1/auth/tron/init', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': token ? 'Bearer ' + token : ''
                    },
                    body: JSON.stringify({ nickname: nick }),
                    credentials: 'same-origin'
                }).then(function(r) { return r.json().then(function(data) { return { status: r.status, data: data }; }); }).then(function(res) {
                    self.initLoading = false;
                    if (res.status === 200 && res.data.space) {
                        window.location.href = '/' + encodeURIComponent(res.data.space);
                    } else {
                        self.initError = (res.data && res.data.detail) || self.$t('main.space.init_error');
                    }
                }).catch(function() {
                    self.initLoading = false;
                    self.initError = self.$t('main.space.init_error');
                });
            },
            openLogin: function() {
                console.log('[landing-auth] openLogin, showLogin=true');
                this._setViewport();
                this.afterSuccess = null;
                this.spaces = [];
                this.token = '';
                this.initNickname = '';
                this.initError = '';
                this.showLogin = true;
                document.body.style.overflow = 'hidden';
            },
            closeLogin: function() {
                console.log('[landing-auth] closeLogin, showLogin=false');
                this.showLogin = false;
                this.afterSuccess = null;
                document.body.style.overflow = '';
            },
            overlayStyle: function() {
                return {
                    position: 'fixed',
                    left: '0',
                    top: '0',
                    width: this.viewport.w + 'px',
                    height: this.viewport.h + 'px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '1rem',
                    background: 'rgba(0,0,0,0.8)',
                    backdropFilter: 'blur(4px)',
                    WebkitBackdropFilter: 'blur(4px)',
                    pointerEvents: 'auto',
                    zIndex: 60
                };
            },
            cardStyle: function() {
                var maxW = Math.min(384, this.viewport.w - 32);
                return {
                    maxWidth: maxW + 'px',
                    width: '100%',
                    minWidth: 0
                };
            }
        },
        template:
            '<div style="position:fixed;left:0;top:0;width:0;height:0;overflow:visible;z-index:60;pointer-events:none">' +
            '<div v-if="showSpacePickerOnly" :style="overlayStyle()" @click.self="closeSpacePickerOnly" role="dialog" aria-modal="true">' +
            '  <div class="rounded-2xl bg-[#0a0a0a] border border-white/10 shadow-2xl p-6 overflow-x-hidden box-border" :style="cardStyle()" @click.stop>' +
            '    <div class="flex justify-end mb-2">' +
            '      <button type="button" @click="closeSpacePickerOnly" class="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors" :aria-label="$t(\'main.landing.docs_close\')">' +
            '        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>' +
            '      </button>' +
            '    </div>' +
            '    <p class="text-sm text-white/80 mb-3">[[ $t(\'main.space.choose_space\') ]]</p>' +
            '    <div class="space-y-2">' +
            '      <button v-for="s in spacePickerSpaces" :key="s" type="button" @click="goToSpace(s)" class="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600">[[ s ]]</button>' +
            '    </div>' +
            '  </div>' +
            '</div>' +
            '<div v-if="showLogin" :style="overlayStyle()" @click.self="closeLogin" role="dialog" aria-modal="true">' +
            '  <div class="rounded-2xl bg-[#0a0a0a] border border-white/10 shadow-2xl p-6 overflow-x-hidden box-border" :style="cardStyle()" @click.stop>' +
            '    <div class="flex justify-end mb-2">' +
            '      <button type="button" @click="closeLogin" class="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors" :aria-label="$t(\'main.landing.docs_close\')">' +
            '        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>' +
            '      </button>' +
            '    </div>' +
            '    <template v-if="afterSuccess === \'choose\'">' +
            '      <p class="text-sm text-white/80 mb-3">[[ $t(\'main.space.choose_space\') ]]</p>' +
            '      <div class="space-y-2">' +
            '        <button v-for="s in spaces" :key="s" type="button" @click="goToSpace(s)" class="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600">[[ s ]]</button>' +
            '      </div>' +
            '    </template>' +
            '    <template v-else-if="afterSuccess === \'init\'">' +
            '      <p class="text-sm text-white/80 mb-3">[[ $t(\'main.space.init_prompt\') ]]</p>' +
            '      <div class="space-y-3">' +
            '        <input v-model="initNickname" type="text" :placeholder="$t(\'main.space.nickname_placeholder\')" maxlength="100" class="w-full px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/50 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />' +
            '        <p v-if="initError" class="text-red-400 text-xs">[[ initError ]]</p>' +
            '        <button type="button" :disabled="initLoading" @click="submitInit" class="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600 disabled:opacity-50">[[ initLoading ? $t(\'main.space.init_creating\') : $t(\'main.space.init_submit\') ]]</button>' +
            '      </div>' +
            '    </template>' +
            '    <tron-login v-else @success="onTronSuccess"></tron-login>' +
            '  </div>' +
            '</div>' +
            '</div>'
    });
})();
