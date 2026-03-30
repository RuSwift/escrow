/**
 * Публичная страница подписи заявки на вывод /o/{token}.
 * TronLink: sendTrx / triggerSmartContract с expiration (24ч при multisig N>1).
 */
(function() {
    var root = document.getElementById('order-sign-root');
    if (!root) return;
    var invalid = root.getAttribute('data-invalid') === 'true';
    var token = (root.getAttribute('data-token') || '').trim();
    if (invalid || !token) return;

    var loadingEl = document.getElementById('order-sign-loading');
    var bodyEl = document.getElementById('order-sign-body');
    var errEl = document.getElementById('order-sign-error');
    var btn = document.getElementById('order-sign-btn');
    var t = window.__TRANSLATIONS__ || {};

    function tKey(key) {
        return t[key] !== undefined ? t[key] : key;
    }

    function formatWithdrawalDisplayAmount(data) {
        if (!data || data.amount_raw == null) return '—';
        var tok = data.token || {};
        var raw = Number(data.amount_raw);
        if (!isFinite(raw)) return '—';
        var ttype = (tok.type || '').toLowerCase();
        var dec = typeof tok.decimals === 'number' && tok.decimals >= 0 ? tok.decimals : 6;
        var sym = (tok.symbol || '').toUpperCase() || (ttype === 'native' ? 'TRX' : '—');
        var human = raw / Math.pow(10, dec);
        return human.toLocaleString(undefined, {
            maximumFractionDigits: dec,
            minimumFractionDigits: 0
        }) + ' ' + sym;
    }

    var ctx = null;

    function showErr(msg) {
        if (errEl) {
            errEl.textContent = msg || '';
            errEl.classList.toggle('hidden', !msg);
        }
    }

    function getTronWeb() {
        if (window.tronLink && window.tronLink.request) {
            return window.tronLink.request({ method: 'tron_requestAccounts' }).then(function(res) {
                if (res && res.code === 4001) return Promise.reject(new Error('USER_REJECTED'));
                var tw = window.tronLink.tronWeb || window.tronWeb;
                var addr = tw && tw.defaultAddress && tw.defaultAddress.base58 ? tw.defaultAddress.base58 : '';
                if (addr) return tw;
                return null;
            });
        }
        if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
            return Promise.resolve(window.tronWeb);
        }
        return Promise.reject(new Error('NO_TRONLINK'));
    }

    function expirationMs(longExp) {
        if (longExp) return Date.now() + 24 * 60 * 60 * 1000;
        return Date.now() + 2 * 60 * 1000;
    }

    function fetchContext() {
        return fetch('/v1/order-sign/' + encodeURIComponent(token), {
            method: 'GET',
            headers: { Accept: 'application/json' },
            credentials: 'same-origin'
        }).then(function(r) {
            if (!r.ok) throw new Error(String(r.status));
            return r.json();
        });
    }

    function buildAndSign(tw, c) {
        var from = (c.tron_address || '').trim();
        var to = (c.destination_address || '').trim();
        var amount = parseInt(c.amount_raw, 10);
        var tok = c.token || {};
        var longExp = !!c.long_expiration_ms;
        var exp = expirationMs(longExp);
        var baseOpts = { expiration: exp };

        var ttype = (tok.type || '').toLowerCase();
        if (ttype === 'native') {
            return tw.transactionBuilder.sendTrx(to, amount, from, baseOpts).then(function(tx) {
                return tw.trx.sign(tx);
            });
        }
        var contract = (tok.contract_address || '').trim();
        if (!contract) return Promise.reject(new Error('no_contract'));
        var opts = { feeLimit: 150000000, callValue: 0, expiration: exp };
        return tw.transactionBuilder.triggerSmartContract(
            contract,
            'transfer(address,uint256)',
            opts,
            [
                { type: 'address', value: to },
                { type: 'uint256', value: amount }
            ],
            from
        ).then(function(res) {
            var tx = res && (res.transaction || res);
            if (!tx) throw new Error('build_failed');
            return tw.trx.sign(tx);
        });
    }

    function submitSigned(signed) {
        var addr = '';
        try {
            if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                addr = window.tronWeb.defaultAddress.base58;
            }
        } catch (e) {}
        return fetch('/v1/order-sign/' + encodeURIComponent(token) + '/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                signer_address: addr,
                signed_transaction: signed
            })
        }).then(function(r) {
            if (!r.ok) {
                return r.json().then(function(d) {
                    throw new Error(typeof d.detail === 'string' ? d.detail : 'submit');
                });
            }
            return r.json();
        });
    }

    fetchContext()
        .then(function(data) {
            ctx = data;
            if (loadingEl) loadingEl.classList.add('hidden');
            if (bodyEl) bodyEl.classList.remove('hidden');
            var st = document.getElementById('order-sign-status');
            if (st) st.textContent = (data.status || '—');
            var am = document.getElementById('order-sign-amount');
            if (am) am.textContent = formatWithdrawalDisplayAmount(data);
            var de = document.getElementById('order-sign-dest');
            if (de) de.textContent = (data.destination_address || '—');
            var fr = document.getElementById('order-sign-from');
            if (fr) fr.textContent = (data.tron_address || '—');
        })
        .catch(function() {
            if (loadingEl) loadingEl.textContent = tKey('main.order_sign.load_error');
        });

    if (btn) {
        btn.addEventListener('click', function() {
            showErr('');
            if (!ctx) return;
            btn.disabled = true;
            getTronWeb()
                .then(function(tw) {
                    return buildAndSign(tw, ctx).then(function(signed) {
                        return submitSigned(signed).then(function() {
                            return tw.trx.sendRawTransaction(signed);
                        });
                    });
                })
                .then(function() {
                    showErr('');
                    var el = document.getElementById('order-sign-status');
                    if (el) el.textContent = tKey('main.order_sign.done');
                })
                .catch(function(e) {
                    showErr(String(e && e.message ? e.message : e));
                })
                .finally(function() {
                    btn.disabled = false;
                });
        });
    }
})();
