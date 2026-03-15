/**
 * Страница верификации приглашения /v/{token}.
 * Кнопка «Подписать»: запрос nonce → подпись в TronLink → confirm → редирект в спейс.
 * TronLink only. Адрес должен совпадать с приглашённым.
 */
(function() {
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

    console.log('[invite-verify] token (first 8):', token ? token.substring(0, 8) + '...' : '');
    console.log('[invite-verify] expected wallet_address from invite:', invite.wallet_address || '', 'length:', (invite.wallet_address || '').length);

    var signBtn = document.getElementById('invite-sign-btn');
    var errEl = document.getElementById('invite-error');
    var loadingEl = document.getElementById('invite-loading');
    var t = window.__TRANSLATIONS__ || {};

    function tKey(key) {
        return t[key] !== undefined ? t[key] : key;
    }

    function getTronWeb() {
        if (window.tronLink && window.tronLink.request) {
            return window.tronLink.request({ method: 'tron_requestAccounts' }).then(function(res) {
                console.log('[invite-verify] tron_requestAccounts response:', res ? { code: res.code } : res);
                if (res && res.code === 4001) return Promise.reject(new Error('USER_REJECTED'));
                var tw = window.tronLink.tronWeb || window.tronWeb;
                var addr = tw && tw.defaultAddress && tw.defaultAddress.base58 ? tw.defaultAddress.base58 : '';
                console.log('[invite-verify] tronWeb.defaultAddress.base58 after request:', addr, 'length:', addr.length);
                if (addr) return tw;
                return null;
            });
        }
        if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
            console.log('[invite-verify] using existing window.tronWeb.defaultAddress');
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

    if (signBtn) {
        signBtn.addEventListener('click', function() {
            showError('');
            setLoading(true);
            getTronWeb()
                .then(function(tronWeb) {
                    var currentAddress = ((tronWeb.defaultAddress && tronWeb.defaultAddress.base58) ? tronWeb.defaultAddress.base58 : '').trim();
                    var expectedAddress = ((invite && invite.wallet_address) ? invite.wallet_address : '').trim();
                    console.log('[invite-verify] currentAddress (TronLink):', currentAddress, 'length:', currentAddress.length);
                    console.log('[invite-verify] expectedAddress (invite):', expectedAddress, 'length:', expectedAddress.length);
                    console.log('[invite-verify] match:', currentAddress === expectedAddress, 'strict eq:', currentAddress === expectedAddress);
                    if (currentAddress !== expectedAddress) {
                        console.warn('[invite-verify] address mismatch, throwing wallet_mismatch');
                        throw new Error(tKey('main.invite.wallet_mismatch'));
                    }
                    console.log('[invite-verify] requesting nonce...');
                    return fetch('/v1/invite/' + encodeURIComponent(token) + '/nonce', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin'
                    }).then(function(r) {
                        if (!r.ok) {
                            console.error('[invite-verify] nonce request failed:', r.status);
                            throw new Error(tKey('main.invite.error_nonce'));
                        }
                        return r.json();
                    }).then(function(data) {
                        var message = data.message || ('Nonce: ' + (data.nonce || ''));
                        console.log('[invite-verify] nonce received, message length:', message.length);
                        return tronWeb.trx.signMessageV2(message).then(function(signature) {
                            console.log('[invite-verify] signature received, sending confirm...');
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
                    console.log('[invite-verify] confirm success, redirect_url:', url);
                    if (data && data.token) {
                        try { localStorage.setItem('main_auth_token', data.token); } catch (e) {}
                    }
                    window.location.href = url;
                })
                .catch(function(err) {
                    console.error('[invite-verify] error:', err && err.message ? err.message : err);
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
