/**
 * Vue 2 компонент: авторизация пользователя через TronLink (main app).
 * Подключение через tron_requestAccounts (или опрос tronWeb для старых версий).
 * Запрос nonce → подпись в TronLink → verify → emit('success', { token, wallet_address }).
 * API: POST /v1/auth/tron/nonce, POST /v1/auth/tron/verify.
 * Подключать после vue.min.js. При @success сохранять payload.token в localStorage под ключом main_auth_token (см. auth.js).
 */
(function() {
    var AUTH_API = '/v1/auth';

    function getTronWeb() {
        if (window.tronLink) {
            if (window.tronLink.ready && window.tronLink.tronWeb && window.tronLink.tronWeb.defaultAddress && window.tronLink.tronWeb.defaultAddress.base58) {
                return Promise.resolve(window.tronLink.tronWeb);
            }
            return window.tronLink.request({ method: 'tron_requestAccounts' }).then(function(res) {
                if (res && res.code === 200) {
                    var tw = window.tronLink.tronWeb;
                    if (tw && tw.defaultAddress && tw.defaultAddress.base58) return tw;
                    if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                        return window.tronWeb;
                    }
                }
                if (res && res.code === 4001) {
                    return Promise.reject(new Error('USER_REJECTED'));
                }
                return null;
            });
        }
        if (window.tronWeb) {
            return new Promise(function(resolve) {
                var attempts = 0;
                var maxAttempts = 100;
                var iv = setInterval(function() {
                    if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                        clearInterval(iv);
                        resolve(window.tronWeb);
                        return;
                    }
                    attempts++;
                    if (attempts >= maxAttempts) {
                        clearInterval(iv);
                        resolve(null);
                    }
                }, 50);
            });
        }
        return Promise.resolve(null);
    }

    Vue.component('tron-login', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                loading: false,
                error: ''
            };
        },
        methods: {
            connect: function() {
                var self = this;
                self.loading = true;
                self.error = '';
                getTronWeb().then(function(tronWeb) {
                    if (!tronWeb || !tronWeb.defaultAddress || !tronWeb.defaultAddress.base58) {
                        var hasExtension = !!(window.tronLink || window.tronWeb);
                        self.error = hasExtension ? self.$t('main.tron.unlock_try_again') : self.$t('main.tron.install_tronlink');
                        return;
                    }
                    var walletAddress = tronWeb.defaultAddress.base58;
                    return fetch(AUTH_API + '/tron/nonce', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ wallet_address: walletAddress }),
                        credentials: 'same-origin'
                    }).then(function(r) { return r.json(); }).then(function(data) {
                        var message = data.message || data.nonce || '';
                        if (!message) {
                            throw new Error(data.detail || 'No nonce');
                        }
                        return tronWeb.trx.signMessageV2(message).then(function(signature) {
                            return fetch(AUTH_API + '/tron/verify', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    wallet_address: walletAddress,
                                    signature: signature,
                                    message: message
                                }),
                                credentials: 'same-origin'
                            });
                        });
                    }).then(function(r) { return r.json(); }).then(function(data) {
                        if (data.token) {
                            self.$emit('success', { token: data.token, wallet_address: data.wallet_address });
                        } else {
                            self.error = data.detail || self.$t('main.tron.error_verify');
                        }
                    });
                }).catch(function(err) {
                    if (err && err.message === 'USER_REJECTED') {
                        self.error = self.$t('main.tron.user_rejected');
                    } else {
                        self.error = self.$t('main.tron.error_prefix') + (err.message || String(err));
                    }
                }).finally(function() {
                    self.loading = false;
                });
            }
        },
        template: '<div class="space-y-3">' +
            '<p class="text-[13px] text-zinc-600">[[ $t(\'main.tron.tron_hint\') ]]</p>' +
            '<div v-if="error" class="p-3 rounded-lg bg-red-50 text-red-800 text-sm">' +
            '  <p>[[ error ]]</p>' +
            '  <button type="button" @click="error = \'\'" class="mt-2 text-xs underline text-red-600 hover:text-red-800">[[ $t(\'main.tron.try_again\') ]]</button>' +
            '</div>' +
            '<button type="button" :disabled="loading" @click="connect" class="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600 disabled:opacity-50 flex items-center justify-center gap-2">' +
            '  <span v-if="loading">[[ $t(\'main.tron.connecting\') ]]</span>' +
            '  <span v-else>[[ $t(\'main.tron.connect_tron\') ]]</span>' +
            '</button>' +
            '</div>'
    });
})();
