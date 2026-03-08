/**
 * Vue 2 компонент: авторизация админа через TronLink.
 * Запрос nonce → подпись в TronLink → verify → emit('success', token).
 * Подключать после vue.min.js. Используется на странице node/login.html.
 */
(function() {
    var API_BASE = '/v1';
    var ADMIN_API = API_BASE + '/admin';

    Vue.component('admin-tron-login', {
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
                if (!window.tronWeb || !window.tronWeb.defaultAddress || !window.tronWeb.defaultAddress.base58) {
                    self.error = self.$t('node.login.install_tronlink');
                    return;
                }
                var tronAddress = window.tronWeb.defaultAddress.base58;
                self.loading = true;
                self.error = '';
                fetch(ADMIN_API + '/tron/nonce', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tron_address: tronAddress }),
                    credentials: 'same-origin'
                }).then(function(r) { return r.json(); }).then(function(data) {
                    var message = data.message || data.nonce || '';
                    if (!message) {
                        throw new Error(data.detail || 'No nonce');
                    }
                    return window.tronWeb.trx.signMessageV2(message).then(function(signature) {
                        return fetch(ADMIN_API + '/tron/verify', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                tron_address: tronAddress,
                                signature: signature,
                                message: message
                            }),
                            credentials: 'same-origin'
                        });
                    });
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.token) {
                        self.$emit('success', data.token);
                    } else {
                        self.error = data.detail || self.$t('node.login.error_verify');
                    }
                }).catch(function(err) {
                    self.error = self.$t('node.login.error_prefix') + (err.message || String(err));
                }).finally(function() {
                    self.loading = false;
                });
            }
        },
        template: '<div class="space-y-3">' +
            '<p class="text-[13px] text-zinc-600">[[ $t(\'node.init.tron_hint\') ]]</p>' +
            '<div v-if="error" class="p-3 rounded-lg bg-red-50 text-red-800 text-sm">[[ error ]]</div>' +
            '<button type="button" :disabled="loading" @click="connect" class="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg text-[13px] font-semibold hover:bg-amber-600 disabled:opacity-50 flex items-center justify-center gap-2">' +
            '  <span v-if="loading">[[ $t(\'node.login.connecting\') ]]</span>' +
            '  <span v-else>[[ $t(\'node.login.connect_tron\') ]]</span>' +
            '</button>' +
            '</div>'
    });
})();
