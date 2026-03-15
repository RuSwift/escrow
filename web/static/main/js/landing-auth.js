/**
 * Блок авторизации на лендинге: кнопка «Войти» → tron-login → редирект в /app.
 * Если пользователь уже авторизован — ссылка «Перейти в приложение» и DID.
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

    var el = document.getElementById('landing-header-auth');
    if (!el) return;

    new Vue({
        el: '#landing-header-auth',
        delimiters: ['[[', ']]'],
        data: {
            currentUser: null,
            showLogin: false
        },
        mounted: function() {
            var self = this;
            var getCurrent = window.get_current_user;
            if (getCurrent) getCurrent().then(function(u) { self.currentUser = u; });
        },
        methods: {
            onTronSuccess: function(payload) {
                var key = window.main_auth_token_key || 'main_auth_token';
                try { localStorage.setItem(key, payload.token); } catch (e) {}
                window.location.href = '/app';
            },
            openLogin: function() { this.showLogin = true; },
            closeLogin: function() { this.showLogin = false; }
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
            '  <template v-else>' +
            '    <button v-if="!showLogin" type="button" @click="openLogin" class="px-6 py-2.5 bg-white text-black rounded-full font-bold hover:bg-main-blue hover:text-white transition-all duration-300 inline-flex items-center gap-2">' +
            '      [[ $t(\'main.login\') ]]' +
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>' +
            '    </button>' +
            '    <div v-if="showLogin" class="flex flex-col items-end gap-2">' +
            '      <button type="button" @click="closeLogin" class="text-xs text-white/50 hover:text-white">[[ $t(\'main.landing.cancel\') ]]</button>' +
            '      <div class="min-w-[260px] p-4 rounded-xl bg-white/5 border border-white/10"><tron-login @success="onTronSuccess"></tron-login></div>' +
            '    </div>' +
            '  </template>' +
            '</div>'
    });
})();
