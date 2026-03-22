/**
 * Страница верификации приглашения /v/{token}.
 * Кнопка «Подписать»: запрос nonce → подпись в TronLink → confirm → редирект в спейс.
 * TronLink only. Адрес должен совпадать с приглашённым.
 */
(function() {
    var STORAGE_SNAPSHOT = 'main_invite_tron_snapshot';
    var STORAGE_REMINDER = 'main_invite_wallet_reminder';

    var root = document.getElementById('invite-verify-root');
    if (!root) return;
    var invalid = root.getAttribute('data-invite-invalid') === 'true';
    var token = (root.getAttribute('data-invite-token') || '').trim();
    var invite = null;
    try {
        var raw = root.getAttribute('data-invite');
        if (raw) {
            var decoded = raw.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
            invite = JSON.parse(decoded);
        }
    } catch (e) {}
    if (invalid || !token || !invite) return;

    var signBtn = document.getElementById('invite-sign-btn');
    var errEl = document.getElementById('invite-error');
    var loadingEl = document.getElementById('invite-loading');
    var t = window.__TRANSLATIONS__ || {};

    function tKey(key) {
        return t[key] !== undefined ? t[key] : key;
    }

    function tParams(key, params) {
        var s = tKey(key);
        if (params && typeof s === 'string') {
            Object.keys(params).forEach(function(k) {
                s = s.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
            });
        }
        return s;
    }

    function maskAddress(addr) {
        if (!addr || addr.length < 6) return addr || '—';
        return addr.slice(0, 2) + '…' + addr.slice(-4);
    }

    function captureTronSnapshot() {
        try {
            var tw = window.tronWeb;
            if (tw && tw.defaultAddress && tw.defaultAddress.base58) {
                var a = (tw.defaultAddress.base58 || '').trim();
                if (a) sessionStorage.setItem(STORAGE_SNAPSHOT, a);
            }
        } catch (e) {}
    }

    captureTronSnapshot();
    window.addEventListener('load', captureTronSnapshot);

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

    function showError(msg) {
        if (errEl) {
            errEl.textContent = msg || '';
            errEl.classList.toggle('hidden', !msg);
        }
    }
    function setLoading(on) {
        if (loadingEl) loadingEl.classList.toggle('hidden', !on);
        if (signBtn) signBtn.disabled = on;
    }

    function walletMismatchMessage(currentAddress, expectedAddress) {
        var detail = tParams('main.invite.wallet_mismatch_detail', {
            current: maskAddress(currentAddress),
            expected: maskAddress(expectedAddress)
        });
        if (!detail || detail === 'main.invite.wallet_mismatch_detail') {
            return tKey('main.invite.wallet_mismatch');
        }
        return detail;
    }

    if (signBtn) {
        signBtn.addEventListener('click', function() {
            showError('');
            setLoading(true);
            getTronWeb()
                .then(function(tronWeb) {
                    var currentAddress = ((tronWeb.defaultAddress && tronWeb.defaultAddress.base58) ? tronWeb.defaultAddress.base58 : '').trim();
                    var expectedAddress = ((invite && invite.wallet_address) ? invite.wallet_address : '').trim();
                    if (currentAddress !== expectedAddress) {
                        throw new Error(walletMismatchMessage(currentAddress, expectedAddress));
                    }
                    return fetch('/v1/invite/' + encodeURIComponent(token) + '/nonce', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin'
                    }).then(function(r) {
                        if (!r.ok) {
                            throw new Error(tKey('main.invite.error_nonce'));
                        }
                        return r.json();
                    }).then(function(data) {
                        var message = data.message || ('Nonce: ' + (data.nonce || ''));
                        return tronWeb.trx.signMessageV2(message).then(function(signature) {
                            return { signature: signature, message: message };
                        });
                    });
                })
                .then(function(params) {
                    return fetch('/v1/invite/' + encodeURIComponent(token) + '/confirm', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ signature: params.signature })
                    }).then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || tKey('main.invite.error_confirm')); });
                        return r.json();
                    });
                })
                .then(function(data) {
                    var url = (data && data.redirect_url) ? data.redirect_url : '/';
                    if (data && data.token) {
                        try { localStorage.setItem('main_auth_token', data.token); } catch (e) {}
                    }
                    try {
                        var snap = (sessionStorage.getItem(STORAGE_SNAPSHOT) || '').trim();
                        var exp = ((invite && invite.wallet_address) ? invite.wallet_address : '').trim();
                        if (snap && exp && snap !== exp) {
                            sessionStorage.setItem(STORAGE_REMINDER, JSON.stringify({
                                previous: snap,
                                masked: maskAddress(snap)
                            }));
                        }
                    } catch (e) {}
                    window.location.href = url;
                })
                .catch(function(err) {
                    if (err && err.message === 'USER_REJECTED') {
                        showError(tKey('main.tron.user_rejected'));
                    } else if (err && err.message === 'NO_TRONLINK') {
                        showError(tKey('main.tron.install_tronlink'));
                    } else {
                        showError(err.message || tKey('main.invite.error_confirm'));
                    }
                })
                .finally(function() {
                    setLoading(false);
                });
        });
    }
})();
