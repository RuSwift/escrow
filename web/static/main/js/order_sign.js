/**
 * Публичная страница подписи заявки на вывод /o/{token}.
 * Использует ту же Vue-модалку деталей, что и кабинет, в embedded-режиме.
 */
(function() {
    var root = document.getElementById('order-sign-root');
    if (!root) return;
    var invalid = root.getAttribute('data-invalid') === 'true';
    var token = (root.getAttribute('data-token') || '').trim();
    if (invalid || !token) return;
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

    var el = document.getElementById('order-sign-app');
    if (!el) return;

    new Vue({
        el: el,
        data: function() {
            return {
                order: {
                    dedupe_key: 'withdrawal:' + token,
                    payload: { kind: 'withdrawal_request' }
                }
            };
        },
        render: function(h) {
            return h('withdrawal-order-detail-modal', {
                props: {
                    show: true,
                    order: this.order,
                    embedded: true,
                    fetchLabels: false,
                    canManage: false
                }
            });
        }
    });
})();
