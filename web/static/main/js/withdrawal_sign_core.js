/**
 * Общая логика подписи заявки на вывод (TronLink): /v1/order-sign/{token}.
 * Используется страницей /o/{token} и модалкой деталей заявки.
 */
(function() {
    var W = window.EscrowWithdrawalSign = window.EscrowWithdrawalSign || {};

    function tr(key, params) {
        var dict = window.__TRANSLATIONS__ || {};
        var s = dict[key] !== undefined ? dict[key] : key;
        if (params && typeof s === 'string') {
            Object.keys(params).forEach(function(k) {
                s = s.replace(new RegExp('\\{\\{\\s*' + k + '\\s*\\}\\}', 'g'), params[k]);
            });
        }
        return s;
    }

    W.formatWithdrawalDisplayAmount = function(data) {
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
    };

    W.expirationMs = function(longExp) {
        if (longExp) return Date.now() + 24 * 60 * 60 * 1000;
        return Date.now() + 2 * 60 * 1000;
    };

    /** Ссылка на tx в Tronscan (сеть из window.__TRON_NETWORK__: mainnet | shasta | nile). */
    W.tronTxExplorerUrl = function(txid) {
        var t = String(txid || '').trim();
        if (!t) return '';
        var net = 'mainnet';
        try {
            if (typeof window !== 'undefined' && window.__TRON_NETWORK__) {
                net = String(window.__TRON_NETWORK__).trim().toLowerCase() || 'mainnet';
            }
        } catch (e) {}
        if (net !== 'shasta' && net !== 'nile') net = 'mainnet';
        var base = 'https://tronscan.org';
        if (net === 'shasta') base = 'https://shasta.tronscan.org';
        else if (net === 'nile') base = 'https://nile.tronscan.org';
        return base + '/#/transaction/' + encodeURIComponent(t);
    };

    W.fetchSignContext = function(token) {
        var t = (token || '').trim();
        if (!t) return Promise.reject(new Error('no_token'));
        return fetch('/v1/order-sign/' + encodeURIComponent(t), {
            method: 'GET',
            headers: { Accept: 'application/json' },
            credentials: 'same-origin'
        }).then(function(r) {
            if (!r.ok) throw new Error(String(r.status));
            return r.json();
        });
    };

    W.waitTronLinkReady = function() {
        if (!window.tronLink || window.tronLink.ready === true) {
            return Promise.resolve();
        }
        return new Promise(function(resolve) {
            var done = false;
            function fin() {
                if (done) return;
                done = true;
                resolve();
            }
            window.addEventListener('tronLink#initialized', fin, { once: true });
            setTimeout(fin, 5000);
        });
    };

    W.getTronWeb = function() {
        return W.waitTronLinkReady().then(function() {
            if (window.tronLink && window.tronLink.request) {
                return window.tronLink.request({ method: 'tron_requestAccounts' }).then(function(res) {
                    if (res && res.code === 4001) return Promise.reject(new Error('USER_REJECTED'));
                    var tw = window.tronLink.tronWeb || window.tronWeb;
                    var addr = tw && tw.defaultAddress && tw.defaultAddress.base58 ? tw.defaultAddress.base58 : '';
                    if (addr) return tw;
                    return Promise.reject(new Error('NO_TRONLINK'));
                });
            }
            if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                return Promise.resolve(window.tronWeb);
            }
            return Promise.reject(new Error('NO_TRONLINK'));
        });
    };

    /**
     * Owner в raw_data: для external — адрес из TronLink (должен совпадать с tron_address заявки);
     * для multisig — адрес кошельца в заявке (контракт), подпись через права активного ключа.
     */
    W.resolveWithdrawalOwnerForTronLink = function(tw, c) {
        var ownerInRequest = (c.tron_address || '').trim();
        if (!ownerInRequest) {
            throw new Error(tr('main.withdrawal_detail.sign_missing_source'));
        }
        var role = (c.wallet_role || '').trim();
        var wallet = (tw.defaultAddress && tw.defaultAddress.base58) ? String(tw.defaultAddress.base58).trim() : '';
        if (role === 'multisig') {
            return ownerInRequest;
        }
        if (!wallet) {
            throw new Error(tr('main.tron.install_tronlink'));
        }
        if (ownerInRequest !== wallet) {
            throw new Error(tr('main.withdrawal_detail.sign_wallet_mismatch', {
                expected: ownerInRequest,
                current: wallet
            }));
        }
        return wallet;
    };

    W.buildAndSign = function(tw, c) {
        var from;
        try {
            from = W.resolveWithdrawalOwnerForTronLink(tw, c);
        } catch (e) {
            return Promise.reject(e);
        }
        var to = (c.destination_address || '').trim();
        var ar = c.amount_raw;
        var amount = typeof ar === 'number' && isFinite(ar) ? Math.floor(ar) : parseInt(String(ar), 10);
        if (!isFinite(amount) || amount < 1) {
            return Promise.reject(new Error(tr('main.withdrawal_detail.sign_build_failed')));
        }
        var tok = c.token || {};
        var longExp = !!c.long_expiration_ms;
        var exp = W.expirationMs(longExp);
        var baseOpts = { expiration: exp };

        var ttype = (tok.type || '').trim().toLowerCase();
        if (ttype === 'native') {
            return tw.transactionBuilder.sendTrx(to, amount, from, baseOpts).then(function(tx) {
                if (!tx) throw new Error(tr('main.withdrawal_detail.sign_build_failed'));
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
                { type: 'uint256', value: String(amount) }
            ],
            from
        ).then(function(res) {
            if (!res || !res.result || res.result.result !== true) {
                throw new Error(tr('main.withdrawal_detail.sign_build_failed'));
            }
            var tx = res.transaction;
            if (!tx || !tx.raw_data) {
                throw new Error(tr('main.withdrawal_detail.sign_build_failed'));
            }
            return tw.trx.sign(tx);
        });
    };

    W.submitSigned = function(token, signed) {
        var t = (token || '').trim();
        var addr = '';
        try {
            var twl = window.tronLink && window.tronLink.tronWeb;
            if (twl && twl.defaultAddress && twl.defaultAddress.base58) {
                addr = twl.defaultAddress.base58;
            } else if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                addr = window.tronWeb.defaultAddress.base58;
            }
        } catch (e) {}
        return fetch('/v1/order-sign/' + encodeURIComponent(t) + '/submit', {
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
    };

    W.signAndBroadcast = function(token, ctx) {
        return W.getTronWeb().then(function(tw) {
            return W.buildAndSign(tw, ctx).then(function(signed) {
                return W.submitSigned(token, signed).then(function() {
                    return tw.trx.sendRawTransaction(signed);
                });
            });
        });
    };
})();
