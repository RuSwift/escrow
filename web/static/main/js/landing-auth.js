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
    if (headerEl) {
        new Vue({
            el: '#landing-header-auth',
            delimiters: ['[[', ']]'],
            data: { currentUser: null },
            mounted: function() {
                var self = this;
                var getCurrent = window.get_current_user;
                if (getCurrent) getCurrent().then(function(u) { self.currentUser = u; });
            },
            methods: {
                openLogin: function() {
                    window.dispatchEvent(new CustomEvent('open-landing-login'));
                }
            },
            template:
                '<div class="flex items-center gap-3">' +
                '  <template v-if="currentUser">' +
                '    <a href="/app" class="px-6 py-2.5 bg-white text-black rounded-full font-bold hover:bg-main-blue hover:text-white transition-all duration-300 inline-flex items-center gap-2">' +
                '      [[ $t(\'main.landing.go_to_app\') ]]' +
                '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>' +
                '    </a>' +
                '    <span class="text-xs text-white/50 font-mono max-w-[140px] truncate" :title="currentUser.did">[[ currentUser.did ]]</span>' +
                '  </template>' +
                '  <button v-else type="button" @click="openLogin" class="px-6 py-2.5 bg-white text-black rounded-full font-bold hover:bg-main-blue hover:text-white transition-all duration-300 inline-flex items-center gap-2">' +
                '    [[ $t(\'main.login\') ]]' +
                '    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>' +
                '  </button>' +
                '</div>'
        });
    }

    var modalEl = document.getElementById('landing-login-modal');
    if (!modalEl) return;

    new Vue({
        el: '#landing-login-modal',
        delimiters: ['[[', ']]'],
        data: {
            showLogin: false,
            viewport: { w: 0, h: 0 }
        },
        mounted: function() {
            var self = this;
            window.addEventListener('open-landing-login', function() { self.openLogin(); });
            document.addEventListener('keydown', this._onKeydown);
            window.addEventListener('resize', this._onResize);
        },
        beforeDestroy: function() {
            document.removeEventListener('keydown', this._onKeydown);
            window.removeEventListener('resize', this._onResize);
            document.body.style.overflow = '';
        },
        methods: {
            _onKeydown: function(e) {
                if (e.key === 'Escape' && this.showLogin) this.closeLogin();
            },
            _onResize: function() {
                if (this.showLogin) this._setViewport();
            },
            _setViewport: function() {
                this.viewport = { w: window.innerWidth, h: window.innerHeight };
            },
            onTronSuccess: function(payload) {
                var key = window.main_auth_token_key || 'main_auth_token';
                try { localStorage.setItem(key, payload.token); } catch (e) {}
                window.location.href = '/app';
            },
            openLogin: function() {
                this._setViewport();
                this.showLogin = true;
                document.body.style.overflow = 'hidden';
            },
            closeLogin: function() {
                this.showLogin = false;
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
            '<div v-if="showLogin" :style="overlayStyle()" @click.self="closeLogin" role="dialog" aria-modal="true">' +
            '  <div class="rounded-2xl bg-[#0a0a0a] border border-white/10 shadow-2xl p-6 overflow-x-hidden box-border" :style="cardStyle()" @click.stop>' +
            '    <div class="flex justify-end mb-2">' +
            '      <button type="button" @click="closeLogin" class="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors" :aria-label="$t(\'main.landing.docs_close\')">' +
            '        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>' +
            '      </button>' +
            '    </div>' +
            '    <tron-login @success="onTronSuccess"></tron-login>' +
            '  </div>' +
            '</div>'
    });
})();
