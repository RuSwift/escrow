/**
 * Общая логика подписи заявки на вывод (TronLink): /v1/order-sign/{token}.
 * Используется страницей /o/{token} и модалкой деталей заявки.
 *
 * External: одна подпись trx.sign → submit → sendRaw.
 * Multisig: сборка tx с permission_id, trx.multiSign по шагам; submit без broadcast до порога N.
 * Срок жизни tx: после TransactionBuilder вызывается extendExpiration (opts.expiration TronWeb часто игнорирует).
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

    /** Интервал жизни tx в сети TRON: не больше 24 ч от raw_data.timestamp (док. Tron). */
    W.TRON_MAX_TX_LIFETIME_MS = 24 * 60 * 60 * 1000;

    W.expirationMs = function(longExp) {
        if (longExp) return Date.now() + W.TRON_MAX_TX_LIFETIME_MS;
        return Date.now() + 2 * 60 * 1000;
    };

    /**
     * TronWeb часто не применяет expiration из opts к unsigned tx (tronweb issue #430),
     * остаётся дефолт ~60 с. Доводим raw_data.expiration до целевого окна через extendExpiration.
     * Цель ограничивается timestamp + 24 ч — иначе интервал жизни может превысить лимит протокола.
     */
    W.applyWithdrawalExpirationToUnsignedTx = function(tw, tx, longExp) {
        var raw = tx && tx.raw_data;
        if (!raw || typeof raw !== 'object') return Promise.resolve(tx);
        var cur = raw.expiration != null ? Number(raw.expiration) : NaN;
        if (!isFinite(cur)) return Promise.resolve(tx);
        var ts = raw.timestamp != null ? Number(raw.timestamp) : NaN;
        var targetMs = W.expirationMs(longExp);
        var capMs = null;
        if (isFinite(ts)) {
            capMs = ts + W.TRON_MAX_TX_LIFETIME_MS;
            if (targetMs > capMs) {
                targetMs = capMs;
            }
        }
        var wantDeltaSec = Math.ceil((targetMs - cur) / 1000);
        var deltaSec = wantDeltaSec;
        if (capMs != null) {
            var maxDeltaSec = Math.floor((capMs - cur) / 1000);
            if (maxDeltaSec >= 0 && deltaSec > maxDeltaSec) {
                deltaSec = maxDeltaSec;
            }
        }
        if (deltaSec <= 0) return Promise.resolve(tx);
        var tb = tw.transactionBuilder;
        if (tb && typeof tb.extendExpiration === 'function') {
            var out = tb.extendExpiration(tx, deltaSec);
            return Promise.resolve(out).then(function(ext) {
                return ext || tx;
            });
        }
        raw.expiration = targetMs;
        return Promise.resolve(tx);
    };

    /**
     * Ссылка на tx в Tronscan (сеть из window.__TRON_NETWORK__: mainnet | shasta | nile).
     * Форматирование мс с epoch в строку UTC (для raw_data Tron).
     */
    W.formatUtcFromMs = function(ms) {
        if (ms == null || ms === '') return '';
        var n = Number(ms);
        if (!isFinite(n)) return '';
        var d = new Date(n);
        if (isNaN(d.getTime())) return '';
        return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    };

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
     * Owner в raw_data: для external — адрес из TronLink (= tron_address заявки);
     * для multisig — адрес мультисиг-счёта; подпись через active permission (multiSign).
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

    /** TRON active permission id для multiSign (из снимка цепи при создании заявки). */
    W.multisigPermissionId = function(c) {
        var raw = c && c.active_permission_id;
        if (raw == null || raw === '') return null;
        var n = parseInt(String(raw), 10);
        return isFinite(n) && n >= 0 ? n : null;
    };

    W.assertMultisigSignerWallet = function(tw, c) {
        var wallet = (tw.defaultAddress && tw.defaultAddress.base58) ? String(tw.defaultAddress.base58).trim() : '';
        if (!wallet) {
            throw new Error(tr('main.tron.install_tronlink'));
        }
        var actors = (c && c.actors_snapshot) ? c.actors_snapshot : [];
        var set = {};
        if (Array.isArray(actors)) {
            actors.forEach(function(a) {
                var s = String(a || '').trim();
                if (s) set[s] = true;
            });
        }
        if (!set[wallet]) {
            var err = new Error(tr('main.withdrawal_detail.sign_multisig_not_actor'));
            err.escrowWithdrawalCode = 'SIGNER_NOT_IN_ACTORS';
            throw err;
        }
    };

    /**
     * Транзакция с максимальным числом подписей (накопление multisig между участниками).
     */
    W.pickBestMultisigBaseTransaction = function(c) {
        var sigs = (c && c.signatures) ? c.signatures : [];
        var best = null;
        var bestLen = -1;
        if (!Array.isArray(sigs)) return null;
        sigs.forEach(function(row) {
            var sd = row && row.signature_data;
            var tx = sd && sd.signed_transaction;
            if (!tx || typeof tx !== 'object') return;
            var sig = tx.signature;
            var len = Array.isArray(sig) ? sig.length : 0;
            if (len > bestLen) {
                bestLen = len;
                best = tx;
            }
        });
        return best;
    };

    W.buildUnsignedMultisigTx = function(tw, c) {
        var from;
        try {
            from = W.resolveWithdrawalOwnerForTronLink(tw, c);
        } catch (e) {
            return Promise.reject(e);
        }
        var pid = W.multisigPermissionId(c);
        if (pid == null) {
            return Promise.reject(new Error(tr('main.withdrawal_detail.sign_multisig_no_permission_id')));
        }
        var to = (c.destination_address || '').trim();
        var ar = c.amount_raw;
        var amount = typeof ar === 'number' && isFinite(ar) ? Math.floor(ar) : parseInt(String(ar), 10);
        if (!isFinite(amount) || amount < 1) {
            return Promise.reject(new Error(tr('main.withdrawal_detail.sign_build_failed')));
        }
        var tok = c.token || {};
        var role = (c.wallet_role || '').trim();
        var longExp = role === 'multisig' || !!c.long_expiration_ms;
        var exp = W.expirationMs(longExp);
        var baseOpts = { expiration: exp, permission_id: pid, permissionId: pid };

        var ttype = (tok.type || '').trim().toLowerCase();
        if (ttype === 'native') {
            return tw.transactionBuilder.sendTrx(to, amount, from, baseOpts).then(function(tx) {
                if (!tx) throw new Error(tr('main.withdrawal_detail.sign_build_failed'));
                return W.applyWithdrawalExpirationToUnsignedTx(tw, tx, longExp);
            });
        }
        var contract = (tok.contract_address || '').trim();
        if (!contract) return Promise.reject(new Error('no_contract'));
        var opts = {
            feeLimit: 150000000,
            callValue: 0,
            expiration: exp,
            permission_id: pid,
            permissionId: pid
        };
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
            return W.applyWithdrawalExpirationToUnsignedTx(tw, tx, longExp);
        });
    };

    W.multiSignWithdrawal = function(tw, tx, c) {
        var pid = W.multisigPermissionId(c);
        if (pid == null) {
            return Promise.reject(new Error(tr('main.withdrawal_detail.sign_multisig_no_permission_id')));
        }
        if (!tw.trx || typeof tw.trx.multiSign !== 'function') {
            return Promise.reject(new Error(tr('main.withdrawal_detail.sign_multisig_multi_sign_unsupported')));
        }
        var unsigned = tx;
        try {
            unsigned = JSON.parse(JSON.stringify(tx));
        } catch (e) {}
        return tw.trx.multiSign(unsigned, undefined, pid);
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
                return W.applyWithdrawalExpirationToUnsignedTx(tw, tx, longExp);
            }).then(function(tx) {
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
            return W.applyWithdrawalExpirationToUnsignedTx(tw, tx, longExp);
        }).then(function(tx) {
            return tw.trx.sign(tx);
        });
    };

    /** Срок off-chain tx из контекста (предыдущие подписи). */
    W.assertMultisigOffchainNotExpiredFromContext = function(c) {
        var raw = c && c.offchain_expiration_ms;
        if (raw == null || raw === '') return;
        var n = Number(raw);
        if (!isFinite(n)) return;
        if (Date.now() > n) {
            throw new Error(tr('main.withdrawal_detail.sign_multisig_offchain_expired'));
        }
    };

    W.assertRawTxNotExpired = function(tx) {
        var raw = tx && tx.raw_data;
        if (!raw || typeof raw !== 'object') return;
        var exp = raw.expiration;
        if (exp == null) return;
        var n = Number(exp);
        if (!isFinite(n)) return;
        if (Date.now() > n) {
            throw new Error(tr('main.withdrawal_detail.sign_multisig_offchain_expired'));
        }
    };

    /** Multisig: взять лучший накопленный tx или собрать новый, затем multiSign. */
    W.buildAndMultiSign = function(tw, c) {
        W.assertMultisigSignerWallet(tw, c);
        var base = W.pickBestMultisigBaseTransaction(c);
        if (base) {
            W.assertMultisigOffchainNotExpiredFromContext(c);
            return W.multiSignWithdrawal(tw, base, c);
        }
        return W.buildUnsignedMultisigTx(tw, c).then(function(tx) {
            W.assertRawTxNotExpired(tx);
            return W.multiSignWithdrawal(tw, tx, c);
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
        var role = (ctx && ctx.wallet_role) ? String(ctx.wallet_role).trim() : '';
        if (role === 'multisig') {
            return W.getTronWeb().then(function(tw) {
                return W.buildAndMultiSign(tw, ctx).then(function(signed) {
                    return W.submitSigned(token, signed);
                });
            });
        }
        return W.getTronWeb().then(function(tw) {
            return W.buildAndSign(tw, ctx).then(function(signed) {
                return W.submitSigned(token, signed).then(function() {
                    return tw.trx.sendRawTransaction(signed);
                });
            });
        });
    };
})();
