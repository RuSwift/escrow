/**
 * Страница входа админа: логин/пароль и TronLink.
 * Подключать после vue.min.js и tron-login.js.
 * При успешном входе выставляет cookie admin_token и перенаправляет на /.
 */
(function() {
    var API_BASE = '/v1';
    var ADMIN_API = API_BASE + '/admin';

    function setAdminCookie(token) {
        var d = new Date();
        d.setTime(d.getTime() + 24 * 60 * 60 * 1000);
        document.cookie = 'admin_token=' + token + '; expires=' + d.toUTCString() + '; path=/; SameSite=Lax';
    }

    function redirectAfterLogin() {
        var returnTo = (typeof window !== 'undefined' && window.location && window.location.search)
            ? new URLSearchParams(window.location.search).get('next') || '/'
            : '/';
        window.location.href = returnTo;
    }

    if (typeof Vue === 'undefined') return;
    var el = document.getElementById('admin-login-app');
    if (!el) return;

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

    new Vue({
        el: '#admin-login-app',
        delimiters: ['[[', ']]'],
        data: {
            loginForm: { username: '', password: '' },
            loginError: '',
            loginSubmitting: false
        },
        methods: {
            doPasswordLogin: function() {
                var self = this;
                if (!this.loginForm.username.trim() || !this.loginForm.password) {
                    this.loginError = this.$t('node.login.invalid_credentials');
                    return;
                }
                this.loginError = '';
                this.loginSubmitting = true;
                fetch(ADMIN_API + '/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: this.loginForm.username.trim(),
                        password: this.loginForm.password
                    }),
                    credentials: 'same-origin'
                }).then(function(r) {
                    return r.json().then(function(data) {
                        if (r.ok && data.token) {
                            setAdminCookie(data.token);
                            redirectAfterLogin();
                            return;
                        }
                        self.loginError = data.detail || self.$t('node.login.invalid_credentials');
                    });
                }).catch(function() {
                    self.loginError = self.$t('node.login.invalid_credentials');
                }).finally(function() {
                    self.loginSubmitting = false;
                });
            },
            onTronSuccess: function(token) {
                setAdminCookie(token);
                redirectAfterLogin();
            }
        }
    });
})();
