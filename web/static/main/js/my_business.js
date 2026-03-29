/**
 * Vue 2 компонент: Мой Бизнес. Интерфейс из _temp/MyBusiness.vue.
 * Управление платежными сервисами (направления) и контрагентами (партнерская сеть).
 * Модалка multisig: multisig_config_modal.js → <multisig-config-modal>.
 */
(function() {
    var FIAT_OPTIONS = ['RUB', 'USD', 'EUR', 'GBP', 'KZT', 'UAH', 'TRY', 'AED'];
    var CRYPTO_OPTIONS = ['USDT TRC20', 'A7A5 TRC20'];

    Vue.component('my-business', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                services: [
                    { id: '1', type: 'onRamp', fiatCurrency: 'RUB', cryptoCurrency: 'USDT TRC20', rateType: 'forex', commission: 1.5, status: 'active' },
                    { id: '2', type: 'offRamp', fiatCurrency: 'USD', cryptoCurrency: 'A7A5 TRC20', rateType: 'request', commission: 2.0, status: 'active' }
                ],
                partners: [
                    { id: 'p1', name: 'GlobalPay Solutions', serviceType: 'onRamp (EUR/USDT)', baseCommission: 0.5, myCommission: 0.3, status: 'connected' },
                    { id: 'p2', name: 'CryptoBridge Ltd', serviceType: 'offRamp (GBP/USDT)', baseCommission: 0.8, myCommission: 0.5, status: 'connected' }
                ],
                showCreateModal: false,
                showPartnerModal: false,
                newService: {
                    type: 'onRamp',
                    fiatCurrency: '',
                    cryptoCurrency: 'USDT TRC20',
                    rateType: 'forex',
                    commission: 1.0
                },
                newPartner: {
                    name: '',
                    serviceType: '',
                    baseCommission: 0.5,
                    myCommission: 0.3
                },
                cryptoOptions: ['USDT TRC20', 'A7A5 TRC20'],
                rampWallets: [],
                rampLoading: false,
                rampError: null,
                showRampModal: false,
                rampEditingId: null,
                rampForm: {
                    name: '',
                    role: 'external',
                    blockchain: 'tron',
                    tron_address: '',
                    ethereum_address: '',
                    mnemonic: '',
                    participant_sub_id: null
                },
                rampSaving: false,
                rampParticipants: [],
                rampAddrOpen: false,
                rampAddrBlurTimer: null,
                rampExternalCustom: false,
                rampBalancesByWalletId: {},
                rampBalancesLoading: false,
                rampBalancesError: null,
                rampBalancesRowRefreshingId: null,
                showRampMultisigWizard: false,
                rampMultisigWizardWallet: null
            };
        },
        mounted: function() {
            this.fetchRampWallets();
        },
        computed: {
            filteredFiats: function() {
                var q = (this.newService.fiatCurrency || '').toLowerCase();
                if (!q) return [];
                return FIAT_OPTIONS.filter(function(f) { return f.toLowerCase().indexOf(q) !== -1; });
            },
            onRampCount: function() { return this.services.filter(function(s) { return s.type === 'onRamp'; }).length; },
            offRampCount: function() { return this.services.filter(function(s) { return s.type === 'offRamp'; }).length; },
            rampParticipantCandidates: function() {
                var taken = {};
                (this.rampWallets || []).forEach(function(w) {
                    var a = (w.tron_address || '').trim();
                    if (a) taken[a] = true;
                });
                return (this.rampParticipants || []).filter(function(p) {
                    if ((p.blockchain || '').toLowerCase() !== 'tron') return false;
                    var addr = (p.wallet_address || '').trim();
                    return addr && !taken[addr];
                });
            },
            rampAddressPickerParticipants: function() {
                var list = (this.rampParticipantCandidates || []).slice();
                var sid = this.rampForm.participant_sub_id;
                if (sid == null) return list;
                var found = list.some(function(p) { return p.id === sid; });
                if (found) return list;
                (this.rampParticipants || []).forEach(function(p) {
                    if (p.id === sid) list.unshift(p);
                });
                return list;
            },
            rampSaveAddDisabled: function() {
                if (this.rampEditingId) return false;
                if (this.rampForm.role === 'multisig') {
                    return !(this.rampForm.name || '').trim();
                }
                if (this.rampForm.participant_sub_id != null) return false;
                if (!this.rampExternalCustom) return true;
                return !(this.rampForm.name || '').trim() || !(this.rampForm.tron_address || '').trim();
            },
            rampSaveEditDisabled: function() {
                if (!this.rampEditingId) return false;
                return !(this.rampForm.name || '').trim()
                    || !(this.rampForm.tron_address || '').trim();
            }
        },
        methods: {
            selectFiat: function(fiat) { this.newService.fiatCurrency = fiat; },
            addService: function() {
                if (!(this.newService.fiatCurrency || '').trim()) return;
                this.services.push({
                    id: String(Date.now()),
                    type: this.newService.type,
                    fiatCurrency: this.newService.fiatCurrency.trim(),
                    cryptoCurrency: this.newService.cryptoCurrency,
                    rateType: this.newService.rateType,
                    commission: parseFloat(this.newService.commission) || 1,
                    status: 'active'
                });
                this.showCreateModal = false;
                this.newService = { type: 'onRamp', fiatCurrency: '', cryptoCurrency: 'USDT TRC20', rateType: 'forex', commission: 1.0 };
            },
            toggleStatus: function(id) {
                var s = this.services.find(function(x) { return x.id === id; });
                if (s) s.status = s.status === 'active' ? 'paused' : 'active';
            },
            openPartnerModal: function() {
                this.newPartner = { name: '', serviceType: '', baseCommission: 0.5, myCommission: 0.3 };
                this.showPartnerModal = true;
            },
            addPartner: function() {
                if (!(this.newPartner.name || '').trim()) return;
                this.partners.push({
                    id: 'p' + Date.now(),
                    name: this.newPartner.name.trim(),
                    serviceType: (this.newPartner.serviceType || '').trim() || '—',
                    baseCommission: parseFloat(this.newPartner.baseCommission) || 0,
                    myCommission: parseFloat(this.newPartner.myCommission) || 0,
                    status: 'connected'
                });
                this.showPartnerModal = false;
            },
            rampApiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets';
            },
            rampSpaceParticipantsUrl: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/participants';
            },
            fetchRampParticipants: function() {
                var self = this;
                var url = this.rampSpaceParticipantsUrl();
                if (!url) {
                    this.rampParticipants = [];
                    return;
                }
                fetch(url, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) return [];
                        return r.json();
                    })
                    .then(function(data) {
                        self.rampParticipants = Array.isArray(data) ? data : [];
                    })
                    .catch(function() {
                        self.rampParticipants = [];
                    });
            },
            clearRampAddrBlurTimer: function() {
                if (this.rampAddrBlurTimer) {
                    clearTimeout(this.rampAddrBlurTimer);
                    this.rampAddrBlurTimer = null;
                }
            },
            openRampAddrDropdown: function() {
                if (this.rampEditingId || this.rampForm.role !== 'external') return;
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = true;
            },
            onRampAddrFocus: function() {
                this.openRampAddrDropdown();
            },
            onRampAddrInputClick: function() {
                this.openRampAddrDropdown();
            },
            onRampTronAddressInput: function() {
                // Пользователь вручную вводит/вставляет внешний TRON-адрес.
                // Если participant_sub_id не выбран — включаем режим custom, чтобы кнопка сохранения стала доступна.
                if (this.rampForm.participant_sub_id != null) return;
                this.rampExternalCustom = true;
                var tr = (this.rampForm.tron_address || '').trim();
                // Для custom-address backend требует name, поэтому подставим имя из адреса при пустом поле.
                if (!(this.rampForm.name || '').trim() && tr) {
                    this.rampForm.name = tr;
                }
            },
            onRampAddrFocusOut: function(e) {
                var self = this;
                if (this.rampEditingId) return;
                var rel = e.relatedTarget;
                if (rel && e.currentTarget.contains(rel)) {
                    return;
                }
                this.clearRampAddrBlurTimer();
                this.rampAddrBlurTimer = setTimeout(function() {
                    self.rampAddrOpen = false;
                    self.rampAddrBlurTimer = null;
                }, 200);
            },
            toggleRampAddrDropdown: function() {
                if (this.rampEditingId || this.rampForm.role !== 'external') return;
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = !this.rampAddrOpen;
            },
            pickRampCustomAddress: function() {
                this.clearRampAddrBlurTimer();
                this.rampForm.participant_sub_id = null;
                this.rampExternalCustom = true;
                this.rampForm.tron_address = '';
                this.rampForm.name = '';
                this.rampAddrOpen = false;
            },
            pickRampParticipantSub: function(p) {
                this.clearRampAddrBlurTimer();
                if (!p || !p.id) return;
                this.rampForm.participant_sub_id = p.id;
                this.rampExternalCustom = false;
                this.rampForm.tron_address = (p.wallet_address || '').trim();
                this.rampForm.name = ((p.nickname || '').trim()) || this.rampForm.tron_address;
                this.rampAddrOpen = false;
            },
            onRampRoleChange: function() {
                if (this.rampEditingId) return;
                this.rampForm.participant_sub_id = null;
                this.rampExternalCustom = false;
                this.rampForm.tron_address = '';
                if (this.rampForm.role === 'multisig') {
                    this.rampForm.name = '';
                }
                this.rampAddrOpen = false;
            },
            rampAuthHeaders: function() {
                var token = null;
                try {
                    var key = (typeof window !== 'undefined' && window.main_auth_token_key)
                        ? window.main_auth_token_key
                        : 'main_auth_token';
                    token = localStorage.getItem(key);
                } catch (e) {}
                var h = { 'Content-Type': 'application/json' };
                if (token) h.Authorization = 'Bearer ' + token;
                return h;
            },
            fetchRampWallets: function(opts) {
                var self = this;
                opts = opts || {};
                var skipBalances = !!opts.skipBalances;
                var base = this.rampApiBase();
                if (!base) {
                    this.rampLoading = false;
                    this.rampError = null;
                    this.rampWallets = [];
                    return Promise.resolve();
                }
                this.rampLoading = true;
                this.rampError = null;
                return fetch(base, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (r.status === 403) throw new Error('403');
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.rampWallets = (data && data.items) ? data.items : [];
                    })
                    .catch(function() {
                        self.rampError = self.$t('main.my_business.ramp_loading_error');
                        self.rampWallets = [];
                    })
                    .finally(function() {
                        self.rampLoading = false;
                        if (!self.rampError) {
                            if (!skipBalances) {
                                self.fetchRampBalances();
                            }
                        } else {
                            self.rampBalancesByWalletId = {};
                            self.rampBalancesLoading = false;
                            self.rampBalancesError = null;
                        }
                    });
            },
            openRampModal: function(editWallet) {
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = false;
                this.rampEditingId = editWallet ? editWallet.id : null;
                if (editWallet) {
                    this.rampForm = {
                        name: editWallet.name || '',
                        role: editWallet.role === 'multisig' ? 'multisig' : 'external',
                        blockchain: 'tron',
                        tron_address: editWallet.tron_address || '',
                        ethereum_address: editWallet.ethereum_address || '',
                        mnemonic: '',
                        participant_sub_id: null
                    };
                    this.rampExternalCustom = false;
                } else {
                    this.rampForm = {
                        name: '',
                        role: 'external',
                        blockchain: 'tron',
                        tron_address: '',
                        ethereum_address: '',
                        mnemonic: '',
                        participant_sub_id: null
                    };
                    this.rampExternalCustom = false;
                    this.fetchRampParticipants();
                }
                this.showRampModal = true;
            },
            closeRampModal: function() {
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = false;
                this.showRampModal = false;
                this.rampEditingId = null;
            },
            saveRampWallet: function() {
                var self = this;
                var base = this.rampApiBase();
                if (!base) return;
                var name = (this.rampForm.name || '').trim();
                var tron = (this.rampForm.tron_address || '').trim();
                var url = base;
                var method = 'POST';
                var body;

                if (this.rampEditingId) {
                    if (!name || !tron) return;
                    method = 'PATCH';
                    url = base + '/' + this.rampEditingId;
                    body = { name: name, tron_address: tron };
                } else {
                    if (this.rampSaveAddDisabled) return;
                    if (this.rampForm.role === 'multisig') {
                        body = {
                            role: 'multisig',
                            blockchain: 'tron',
                            name: name
                        };
                    } else {
                        body = { role: 'external', blockchain: 'tron' };
                        if (this.rampForm.participant_sub_id != null) {
                            body.participant_sub_id = this.rampForm.participant_sub_id;
                        } else {
                            body.name = name;
                            body.tron_address = tron;
                        }
                    }
                }

                this.rampSaving = true;
                fetch(url, {
                    method: method,
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        if (r.status === 403) {
                            return Promise.reject(new Error('403'));
                        }
                        if (!r.ok) {
                            return r.text().then(function(t) {
                                var msg = self.$t('main.my_business.ramp_loading_error');
                                try {
                                    var j = JSON.parse(t);
                                    if (j && typeof j.detail === 'string') {
                                        msg = j.detail;
                                    } else if (j && Array.isArray(j.detail) && j.detail[0] && j.detail[0].msg) {
                                        msg = j.detail[0].msg;
                                    }
                                } catch (e) { /* ignore */ }
                                return Promise.reject(new Error(msg));
                            });
                        }
                        return r.json();
                    })
                    .then(function() {
                        self.closeRampModal();
                        self.fetchRampWallets();
                    })
                    .catch(function(err) {
                        var msg = err && err.message ? err.message : self.$t('main.my_business.ramp_loading_error');
                        if (msg === '403') {
                            msg = self.$t('main.my_business.ramp_error_forbidden');
                        }
                        if (typeof window.showAlert === 'function') {
                            window.showAlert({
                                title: self.$t('main.dialog.error_title'),
                                message: msg
                            });
                        } else {
                            alert(msg);
                        }
                    })
                    .finally(function() {
                        self.rampSaving = false;
                    });
            },
            deleteRampWallet: function(w) {
                var self = this;
                if (!w || !w.id) return;
                var base = this.rampApiBase();
                if (!base) return;

                function runDelete() {
                    fetch(base + '/' + w.id, {
                        method: 'DELETE',
                        headers: self.rampAuthHeaders(),
                        credentials: 'include'
                    })
                        .then(function(r) {
                            if (!r.ok && r.status !== 204) throw new Error();
                            self.fetchRampWallets();
                        })
                        .catch(function() {
                            var msg = self.$t('main.my_business.ramp_loading_error');
                            if (typeof window.showAlert === 'function') {
                                window.showAlert({
                                    title: self.$t('main.dialog.error_title'),
                                    message: msg
                                });
                            } else {
                                alert(msg);
                            }
                        });
                }

                var msgConfirm = self.$t('main.my_business.ramp_delete_confirm');
                if (typeof window.showConfirm === 'function') {
                    window.showConfirm({
                        title: self.$t('main.dialog.confirm_title'),
                        message: msgConfirm,
                        danger: true,
                        onConfirm: function() {
                            runDelete();
                        }
                    });
                } else if (window.confirm(msgConfirm)) {
                    runDelete();
                }
            },
            copyRampAddress: function(addr) {
                var a = (addr || '').trim();
                if (!a || !navigator.clipboard) return;
                navigator.clipboard.writeText(a).then(function() {}).catch(function() {});
            },
            tronscanUrl: function(tronAddress) {
                var a = (tronAddress || '').trim();
                if (!a) return '#';
                return 'https://tronscan.org/#/address/' + encodeURIComponent(a);
            },
            truncateMiddle: function(s, left, right) {
                var t = (s || '').trim();
                if (t.length <= left + right + 3) return t;
                return t.slice(0, left) + '...' + t.slice(-right);
            },
            collateralTronTokens: function() {
                try {
                    var raw = (typeof window !== 'undefined' && window.__COLLATERAL_STABLECOIN_TOKENS__)
                        ? window.__COLLATERAL_STABLECOIN_TOKENS__
                        : [];
                    if (!Array.isArray(raw)) return [];
                    return raw.filter(function(t) {
                        return (t.network || '').toUpperCase() === 'TRON';
                    });
                } catch (e) {
                    return [];
                }
            },
            formatRawTokenAmount: function(rawStr, decimals) {
                var d = parseInt(decimals, 10);
                if (isNaN(d) || d < 0) d = 6;
                var s = String(rawStr == null ? '0' : rawStr).replace(/\s/g, '');
                if (!/^\d+$/.test(s)) return '0';
                try {
                    var bi = BigInt(s);
                    var base = BigInt(10) ** BigInt(d);
                    var whole = bi / base;
                    var frac = bi % base;
                    if (frac === BigInt(0)) return whole.toString();
                    var fs = frac.toString().padStart(d, '0').replace(/0+$/, '');
                    return fs ? whole.toString() + '.' + fs : whole.toString();
                } catch (e) {
                    return s;
                }
            },
            /** Округление до 2 знаков и разделители как 5,240.50 (для UI). */
            formatCollateralAmountDisplay: function(amountStr) {
                var n = parseFloat(String(amountStr == null ? '0' : amountStr).replace(/,/g, ''), 10);
                if (!isFinite(n)) return '0.00';
                var rounded = Math.round(n * 100) / 100;
                return rounded.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            },
            collateralStablecoinIconUrl: function(symbol) {
                var s = String(symbol || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
                if (!s) return '';
                return '/static/main/img/collateral_stablecoin/' + encodeURIComponent(s) + '.svg';
            },
            rampBalancesUrl: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/balances';
            },
            fetchRampBalances: function(opts) {
                var self = this;
                opts = opts || {};
                var singleWalletId = opts.walletId;
                var forceUpdate = !!opts.forceUpdate;
                var url = this.rampBalancesUrl();
                if (!url) {
                    this.rampBalancesByWalletId = {};
                    this.rampBalancesLoading = false;
                    this.rampBalancesError = null;
                    this.rampBalancesRowRefreshingId = null;
                    return;
                }
                var payloadItems = [];
                var walletIds = [];
                (this.rampWallets || []).forEach(function(rw) {
                    var tr = (rw.tron_address || '').trim();
                    if (!tr) return;
                    if (singleWalletId != null && rw.id !== singleWalletId) return;
                    payloadItems.push({
                        address: tr,
                        blockchain: 'TRON',
                        force_update: forceUpdate
                    });
                    walletIds.push(rw.id);
                });
                if (!payloadItems.length) {
                    if (singleWalletId == null) {
                        this.rampBalancesByWalletId = {};
                        this.rampBalancesLoading = false;
                        this.rampBalancesError = null;
                    }
                    this.rampBalancesRowRefreshingId = null;
                    return;
                }
                if (singleWalletId != null) {
                    this.rampBalancesRowRefreshingId = singleWalletId;
                } else {
                    this.rampBalancesLoading = true;
                    this.rampBalancesError = null;
                }
                fetch(url, {
                    method: 'POST',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ items: payloadItems })
                })
                    .then(function(r) {
                        if (r.status === 401 || r.status === 403) throw new Error('auth');
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        var meta = self.collateralTronTokens();
                        var itemsOut = (data && data.items) ? data.items : [];
                        var rowsFromApiRow = function(row) {
                            var rawMap = row.balances_raw || {};
                            var nb = row.native_balances || {};
                            var rows = [];
                            if (nb.TRX != null && String(nb.TRX).trim() !== '') {
                                rows.push({
                                    symbol: 'TRX',
                                    amount: self.formatRawTokenAmount(String(nb.TRX), 6)
                                });
                            }
                            meta.forEach(function(t) {
                                var c = (t.contract_address || '').trim();
                                var raw = rawMap[c] != null ? String(rawMap[c]) : '0';
                                rows.push({
                                    symbol: (t.symbol || c || '?').toUpperCase(),
                                    amount: self.formatRawTokenAmount(raw, t.decimals)
                                });
                            });
                            return rows;
                        };
                        var mapOne = function(row, wid) {
                            if (wid == null) return;
                            self.$set(self.rampBalancesByWalletId, wid, {
                                rows: rowsFromApiRow(row),
                                itemError: row.error || null
                            });
                        };
                        if (singleWalletId != null) {
                            if (itemsOut.length && itemsOut[0]) {
                                mapOne(itemsOut[0], walletIds[0]);
                            }
                        } else {
                            var byId = {};
                            itemsOut.forEach(function(row, i) {
                                var wid = walletIds[i];
                                if (wid == null) return;
                                byId[wid] = {
                                    rows: rowsFromApiRow(row),
                                    itemError: row.error || null
                                };
                            });
                            self.rampBalancesByWalletId = byId;
                        }
                    })
                    .catch(function() {
                        if (singleWalletId != null) {
                            if (typeof window.showAlert === 'function') {
                                window.showAlert({
                                    title: self.$t('main.dialog.error_title'),
                                    message: self.$t('main.my_business.ramp_balances_error')
                                });
                            }
                        } else {
                            self.rampBalancesError = self.$t('main.my_business.ramp_balances_error');
                            self.rampBalancesByWalletId = {};
                        }
                    })
                    .finally(function() {
                        if (singleWalletId != null) {
                            self.rampBalancesRowRefreshingId = null;
                        } else {
                            self.rampBalancesLoading = false;
                        }
                    });
            },
            refreshRampBalancesForWallet: function(rw) {
                if (!rw || !rw.id) return;
                if (this.rampBalancesRowRefreshingId != null) return;
                this.fetchRampBalances({ walletId: rw.id, forceUpdate: true });
            },
            rampBalanceItemErrorMessage: function(entry) {
                if (!entry || !entry.itemError) return '';
                if (entry.itemError === 'eth_balances_not_implemented') {
                    return this.$t('main.my_business.ramp_balances_eth_pending');
                }
                return entry.itemError;
            },
            multisigStatusLabel: function(rw) {
                var st = (rw && rw.multisig_setup_status) ? String(rw.multisig_setup_status) : '';
                if (!st) return '';
                var k = 'main.my_business.multisig_status_' + st;
                var t = this.$t(k);
                return (t && t !== k) ? t : st;
            },
            openMultisigWizard: function(rw) {
                if (!rw) return;
                this.rampMultisigWizardWallet = rw;
                this.showRampMultisigWizard = true;
            },
            beginMultisigReconfigure: function(rw) {
                var self = this;
                if (!rw || !rw.id) return;
                var base = this.rampApiBase();
                if (!base) return;
                fetch(base + '/' + rw.id, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ multisig_begin_reconfigure: true })
                })
                    .then(function(r) {
                        if (!r.ok) {
                            return r.json().then(function(j) {
                                var d = j && j.detail;
                                var msg = typeof d === 'string' ? d : (d ? JSON.stringify(d) : String(r.status));
                                throw new Error(msg);
                            });
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.fetchRampWallets({ skipBalances: true });
                        self.openMultisigWizard(data);
                    })
                    .catch(function(e) {
                        self.rampError = (e && e.message) ? e.message : self.$t('main.my_business.ramp_loading_error');
                    });
            },
            closeMultisigWizard: function() {
                this.showRampMultisigWizard = false;
                this.rampMultisigWizardWallet = null;
            },
            onMultisigConfigModalSaved: function(payload) {
                var self = this;
                var wid = payload && payload.walletId != null ? payload.walletId : null;
                this.fetchRampWallets({ skipBalances: true }).then(function() {
                    if (wid != null && !self.rampError) {
                        self.fetchRampBalances({ walletId: wid, forceUpdate: true });
                    }
                });
            }
        },
        template: [
            '<div class="max-w-7xl mx-auto px-4 py-8 space-y-8">',
            '  <div>',
            '    <h1 class="text-2xl font-bold text-[#191d23] flex items-center gap-3">',
            '      <svg class="w-8 h-8 text-[#3861fb]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>',
            '      [[ $t(\'main.my_business.title\') ]]',
            '    </h1>',
            '    <p class="text-[#58667e] text-sm mt-1">[[ $t(\'main.my_business.subtitle\') ]]</p>',
            '  </div>',

            '  <section class="bg-white rounded-2xl border border-[#eff2f5] p-5 md:p-6 shadow-sm">',
            '    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">',
            '      <div class="flex items-start gap-3">',
            '        <div class="p-2 rounded-xl bg-blue-50 text-[#3861fb] shrink-0">',
            '          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>',
            '        </div>',
            '        <div>',
            '          <h2 class="text-lg font-bold text-[#191d23]">[[ $t(\'main.my_business.ramp_section_title\') ]]</h2>',
            '          <p class="text-xs text-[#58667e] mt-0.5">[[ $t(\'main.my_business.ramp_network\') ]]</p>',
            '        </div>',
            '      </div>',
            '      <button type="button" @click="openRampModal(null)" class="border-2 border-dashed border-[#eff2f5] rounded-xl inline-flex items-center justify-center gap-2 text-sm font-bold py-2 px-3 sm:py-2.5 sm:px-4 text-[#58667e] hover:border-[#3861fb] hover:bg-blue-50/30 hover:text-[#3861fb] transition-all self-start sm:self-center shrink-0">',
            '        <svg class="w-4 h-4 sm:w-5 sm:h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '        [[ $t(\'main.my_business.ramp_add_wallet\') ]]',
            '      </button>',
            '    </div>',
            '    <p v-if="rampError" class="text-sm text-red-600 mb-4">[[ rampError ]]</p>',
            '    <div v-if="rampLoading" class="text-sm text-[#58667e] py-6 text-center">…</div>',
            '    <div v-else-if="!rampWallets.length" class="text-sm text-[#58667e] py-6 text-center border border-dashed border-[#eff2f5] rounded-xl">[[ $t(\'main.my_business.ramp_empty\') ]]</div>',
            '    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">',
            '      <div v-for="rw in rampWallets" :key="rw.id" class="bg-[#fafbfc] rounded-2xl border border-[#eff2f5] p-3 md:p-4 relative">',
            '        <div class="flex items-start justify-between gap-2 mb-2">',
            '          <div class="flex items-center gap-2 min-w-0">',
            '            <span class="w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex items-center justify-center shrink-0">U</span>',
            '            <div class="min-w-0">',
            '              <div class="font-bold text-[#191d23] truncate">[[ rw.name ]]</div>',
            '              <span v-if="rw.role === \'external\'" class="inline-block mt-0.5 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-100">[[ $t(\'main.my_business.ramp_badge_external\') ]]</span>',
            '              <span v-else class="inline-block mt-0.5 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-100">[[ $t(\'main.my_business.ramp_badge_multisig\') ]]</span>',
            '            </div>',
            '          </div>',
            '          <div class="flex items-center gap-1 shrink-0">',
            '            <button type="button" @click="openRampModal(rw)" :title="$t(\'main.my_business.ramp_edit\')" class="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-[#eff2f5] text-[#58667e]">',
            '              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>',
            '            </button>',
            '            <button type="button" @click="copyRampAddress(rw.tron_address || \'\')" :title="$t(\'main.my_business.ramp_copy\')" class="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-[#eff2f5] text-[#58667e]">',
            '              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>',
            '            </button>',
            '          </div>',
            '        </div>',
            '        <div v-if="rw.role === \'multisig\' && rw.multisig_setup_status === \'active\'" class="mb-2 flex flex-wrap items-center gap-2">',
            '          <button type="button" @click="beginMultisigReconfigure(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_reconfigure_begin\') ]]</button>',
            '        </div>',
            '        <div v-if="rw.role === \'multisig\' && rw.multisig_setup_status && rw.multisig_setup_status !== \'active\'" class="mb-2 flex flex-wrap items-center gap-2">',
            '          <span class="inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md bg-amber-50 text-amber-900 border border-amber-100 pl-2 pr-1.5 py-0.5">',
            '            <span class="text-[10px] font-bold uppercase truncate">[[ multisigStatusLabel(rw) ]]</span>',
            '            <svg v-if="rw.multisig_setup_status !== \'failed\' && rw.multisig_setup_status !== \'reconfigure\'" class="w-3.5 h-3.5 shrink-0 animate-spin text-amber-800 opacity-90" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
            '          </span>',
            '          <button type="button" @click="openMultisigWizard(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_wizard_open\') ]]</button>',
            '          <button v-if="rw.multisig_setup_status === \'failed\'" type="button" @click="beginMultisigReconfigure(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_reconfigure_begin\') ]]</button>',
            '        </div>',
            '        <div class="mb-2 rounded-xl border border-[#eff2f5] bg-white px-3 py-2.5">',
            '          <div v-if="rampBalancesLoading" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_loading\') ]]</div>',
            '          <p v-else-if="rampBalancesError" class="text-xs text-red-600">[[ rampBalancesError ]]</p>',
            '          <p v-else-if="(rw.ethereum_address || \'\').trim() && !(rw.tron_address || \'\').trim()" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_tron_only_hint\') ]]</p>',
            '          <p v-else-if="!(rw.tron_address || \'\').trim()" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balance_no_tron\') ]]</p>',
            '          <template v-else>',
            '            <p v-if="rampBalancesByWalletId[rw.id] && rampBalanceItemErrorMessage(rampBalancesByWalletId[rw.id])" class="text-xs text-amber-700 mb-2">[[ rampBalanceItemErrorMessage(rampBalancesByWalletId[rw.id]) ]]</p>',
            '            <div v-if="rampBalancesByWalletId[rw.id] && rampBalancesByWalletId[rw.id].rows && rampBalancesByWalletId[rw.id].rows.length" class="flex flex-wrap items-center justify-between gap-2">',
            '              <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm font-semibold text-emerald-600 min-w-0 flex-1">',
            '                <span v-for="br in rampBalancesByWalletId[rw.id].rows" :key="rw.id + \'-bal-\' + br.symbol" class="inline-flex items-center gap-1.5 min-w-0">',
            '                  <img :src="collateralStablecoinIconUrl(br.symbol)" :alt="br.symbol" width="16" height="16" class="w-4 h-4 rounded-full object-contain shrink-0 bg-white ring-1 ring-emerald-100" @error="$event.target.style.display=\'none\'" />',
            '                  <span class="font-mono tabular-nums tracking-tight">[[ formatCollateralAmountDisplay(br.amount) ]] [[ br.symbol ]]</span>',
            '                </span>',
            '              </div>',
            '              <button type="button" @click="refreshRampBalancesForWallet(rw)" :disabled="rampBalancesRowRefreshingId === rw.id || rampBalancesLoading" :title="$t(\'main.my_business.ramp_balances_refresh\')" :aria-label="$t(\'main.my_business.ramp_balances_refresh\')" class="shrink-0 p-1.5 rounded-lg border border-[#eff2f5] bg-white text-[#58667e] hover:text-[#3861fb] hover:border-[#3861fb]/30 disabled:opacity-50 disabled:pointer-events-none">',
            '                <svg class="w-4 h-4" :class="{\'animate-spin\': rampBalancesRowRefreshingId === rw.id}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>',
            '              </button>',
            '            </div>',
            '            <p v-else-if="!rampBalancesLoading && !rampBalancesError" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_empty\') ]]</p>',
            '          </template>',
            '        </div>',
            '        <div class="flex items-center gap-2 bg-white border border-[#eff2f5] rounded-xl px-2 py-1.5 text-[11px] font-mono text-[#191d23]">',
            '          <span class="truncate flex-1 min-w-0 sm:hidden">[[ truncateMiddle(rw.tron_address || \'\', 6, 4) ]]</span>',
            '          <span class="truncate flex-1 min-w-0 hidden sm:inline">[[ rw.tron_address || \'\' ]]</span>',
            '          <a :href="tronscanUrl(rw.tron_address || \'\')" target="_blank" rel="noopener noreferrer" class="shrink-0 p-1 text-[#3861fb] hover:opacity-80" :title="$t(\'main.my_business.ramp_open_explorer\')">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>',
            '          </a>',
            '        </div>',
            '        <button type="button" @click="deleteRampWallet(rw)" class="mt-2 text-xs font-bold text-[#58667e] hover:text-red-600">[[ $t(\'main.my_business.ramp_delete\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </section>',

            '  <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">',
            '    <div class="lg:col-span-2 space-y-6">',
            '      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">',
            '        <div class="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">',
            '          <h2 class="text-lg font-bold text-[#191d23]">[[ $t(\'main.my_business.my_services\') ]]</h2>',
            '          <button type="button" @click="showCreateModal = true" class="border-2 border-dashed border-[#eff2f5] rounded-xl inline-flex items-center justify-center gap-2 text-sm font-bold py-2 px-3 sm:py-2.5 sm:px-4 text-[#58667e] hover:border-[#3861fb] hover:bg-blue-50/30 hover:text-[#3861fb] transition-all shrink-0">',
            '            <svg class="w-4 h-4 sm:w-5 sm:h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '            [[ $t(\'main.my_business.create_service\') ]]',
            '          </button>',
            '        </div>',
            '        <div class="flex flex-wrap gap-2 shrink-0">',
            '          <span class="text-xs font-medium px-2 py-1 rounded-lg bg-blue-50 text-blue-600 border border-blue-100">onRamp: [[ onRampCount ]]</span>',
            '          <span class="text-xs font-medium px-2 py-1 rounded-lg bg-purple-50 text-purple-600 border border-purple-100">offRamp: [[ offRampCount ]]</span>',
            '        </div>',
            '      </div>',
            '      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">',
            '        <div v-for="service in services" :key="service.id" class="bg-white rounded-2xl border border-[#eff2f5] p-5 hover:border-[#3861fb] transition-all relative overflow-hidden group">',
            '          <div :class="[\'absolute top-0 right-0 w-24 h-24 -mr-8 -mt-8 rounded-full opacity-5 group-hover:opacity-10 transition-opacity\', service.type === \'onRamp\' ? \'bg-blue-500\' : \'bg-purple-500\']"></div>',
            '          <div class="flex items-center justify-between mb-4">',
            '            <div :class="[\'p-2 rounded-xl\', service.type === \'onRamp\' ? \'bg-blue-50 text-blue-600\' : \'bg-purple-50 text-purple-600\']">',
            '              <!-- onRamp: Lucide arrow-up-right (lucide-icons/lucide) -->',
            '              <svg v-if="service.type === \'onRamp\'" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>',
            '              <!-- offRamp: Lucide arrow-down-left, −90° (против часовой) относительно onRamp -->',
            '              <svg v-else class="w-5 h-5 -rotate-90" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M17 7 7 17"/><path d="M17 17H7V7"/></svg>',
            '            </div>',
            '            <div class="flex items-center gap-2">',
            '              <span :class="[\'text-[10px] font-bold uppercase px-2 py-0.5 rounded-full\', service.status === \'active\' ? \'bg-emerald-50 text-emerald-600\' : \'bg-orange-50 text-orange-600\']">[[ service.status === \'active\' ? $t(\'main.my_business.status_active\') : $t(\'main.my_business.status_paused\') ]]</span>',
            '              <button type="button" @click="toggleStatus(service.id)" class="p-1.5 hover:bg-gray-100 rounded-lg"><svg class="w-3.5 h-3.5 text-[#58667e]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg></button>',
            '            </div>',
            '          </div>',
            '          <div class="space-y-3">',
            '            <div class="flex items-end justify-between">',
            '              <div>',
            '                <div class="text-xs text-[#58667e] uppercase font-bold tracking-wider">[[ $t(\'main.my_business.direction\') ]]</div>',
            '                <div class="text-lg font-bold text-[#191d23] flex items-center gap-2">[[ service.fiatCurrency ]] <svg class="w-3.5 h-3.5 text-[#eff2f5]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg> [[ service.cryptoCurrency ]]</div>',
            '              </div>',
            '              <div class="text-right">',
            '                <div class="text-xs text-[#58667e] uppercase font-bold tracking-wider">[[ $t(\'main.my_business.commission\') ]]</div>',
            '                <div class="text-lg font-bold text-[#3861fb]">[[ service.commission ]]%</div>',
            '              </div>',
            '            </div>',
            '            <div class="pt-3 border-t border-[#eff2f5] flex items-center justify-between">',
            '              <div class="flex items-center gap-1.5 text-xs text-[#58667e]"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0h.5a2.5 2.5 0 002.5-2.5V3.935M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> [[ $t(\'main.my_business.rate_label\') ]]: [[ service.rateType === \'forex\' ? $t(\'main.my_business.rate_forex\') : $t(\'main.my_business.rate_request\') ]]</div>',
            '              <button type="button" class="text-xs font-bold text-[#3861fb] hover:underline flex items-center gap-1">[[ $t(\'main.my_business.integration\') ]] <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg></button>',
            '            </div>',
            '          </div>',
            '        </div>',
            '        <button type="button" @click="showCreateModal = true" class="border-2 border-dashed border-[#eff2f5] rounded-2xl p-5 flex flex-col items-center justify-center gap-3 hover:border-[#3861fb] hover:bg-blue-50/30 transition-all group">',
            '          <div class="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center text-[#58667e] group-hover:bg-[#3861fb] group-hover:text-white transition-all"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></div>',
            '          <span class="text-sm font-bold text-[#58667e] group-hover:text-[#3861fb]">[[ $t(\'main.my_business.add_service\') ]]</span>',
            '        </button>',
            '      </div>',
            '    </div>',

            '    <div class="space-y-6">',
            '      <h2 class="text-lg font-bold text-[#191d23] flex items-center gap-2">[[ $t(\'main.my_business.partner_network\') ]] <span class="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">[[ partners.length ]]</span></h2>',
            '      <div class="space-y-3">',
            '        <div v-for="partner in partners" :key="partner.id" class="bg-white border border-[#eff2f5] rounded-2xl p-4 hover:shadow-sm transition-all">',
            '          <div class="flex items-center gap-3 mb-3">',
            '            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center text-[#3861fb] font-bold">[[ (partner.name || \'\').charAt(0) ]]</div>',
            '            <div class="flex-1 min-w-0">',
            '              <div class="text-sm font-bold text-[#191d23] truncate">[[ partner.name ]]</div>',
            '              <div class="text-[10px] text-[#58667e] truncate">[[ partner.serviceType ]]</div>',
            '            </div>',
            '            <div class="w-2 h-2 rounded-full bg-emerald-500"></div>',
            '          </div>',
            '          <div class="grid grid-cols-2 gap-2 mb-3">',
            '            <div class="bg-gray-50 rounded-xl p-2"><div class="text-[8px] text-[#58667e] uppercase font-bold">[[ $t(\'main.my_business.base_commission\') ]]</div><div class="text-xs font-bold text-[#191d23]">[[ partner.baseCommission ]]%</div></div>',
            '            <div class="bg-blue-50 rounded-xl p-2"><div class="text-[8px] text-[#3861fb] uppercase font-bold">[[ $t(\'main.my_business.my_margin\') ]]</div><div class="text-xs font-bold text-[#3861fb]">+[[ partner.myCommission ]]%</div></div>',
            '          </div>',
            '          <button type="button" class="w-full py-2 text-[10px] font-bold text-[#58667e] hover:text-[#3861fb] hover:bg-blue-50 rounded-lg transition-all flex items-center justify-center gap-2 border border-transparent hover:border-blue-100"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg> [[ $t(\'main.my_business.configure_resale\') ]]</button>',
            '        </div>',
            '        <button type="button" @click="openPartnerModal" class="w-full py-4 border-2 border-dashed border-[#eff2f5] rounded-2xl text-xs font-bold text-[#58667e] hover:border-[#3861fb] hover:text-[#3861fb] transition-all">+ [[ $t(\'main.my_business.add_partner\') ]]</button>',
            '      </div>',
            '      <div class="bg-gradient-to-br from-[#3861fb] to-indigo-600 rounded-2xl p-5 text-white shadow-lg" style="box-shadow: 0 10px 40px -10px rgba(56,97,251,0.3);">',
            '        <div class="flex items-center gap-3 mb-3"><div class="p-2 bg-white/20 rounded-xl"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg></div><div class="text-sm font-bold">[[ $t(\'main.my_business.help_title\') ]]</div></div>',
            '        <p class="text-xs text-white/80 leading-relaxed mb-4">[[ $t(\'main.my_business.help_text\') ]]</p>',
            '        <button type="button" class="w-full py-2 bg-white text-[#3861fb] rounded-xl text-xs font-bold hover:bg-blue-50 transition-colors">[[ $t(\'main.my_business.contact_support\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <div v-if="showCreateModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="showCreateModal = false"></div>',
            '    <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ $t(\'main.my_business.modal_new_service_title\') ]]</h3>',
            '        <button type="button" @click="showCreateModal = false" class="p-2 hover:bg-gray-100 rounded-full"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="p-6 space-y-6">',
            '        <div class="grid grid-cols-2 gap-4">',
            '          <button type="button" @click="newService.type = \'onRamp\'" :class="[\'p-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-2\', newService.type === \'onRamp\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']">',
            '            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>',
            '            <span class="text-xs font-bold uppercase">[[ $t(\'main.my_business.on_ramp\') ]]</span>',
            '            <span class="text-[10px] opacity-60">[[ $t(\'main.my_business.on_ramp_desc\') ]]</span>',
            '          </button>',
            '          <button type="button" @click="newService.type = \'offRamp\'" :class="[\'p-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-2\', newService.type === \'offRamp\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']">',
            '            <svg class="w-6 h-6 -rotate-90" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M17 7 7 17"/><path d="M17 17H7V7"/></svg>',
            '            <span class="text-xs font-bold uppercase">[[ $t(\'main.my_business.off_ramp\') ]]</span>',
            '            <span class="text-[10px] opacity-60">[[ $t(\'main.my_business.off_ramp_desc\') ]]</span>',
            '          </button>',
            '        </div>',
            '        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">',
            '          <div class="relative">',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.fiat_label\') ]]</label>',
            '            <div class="relative">',
            '              <input type="text" v-model="newService.fiatCurrency" :placeholder="$t(\'main.my_business.fiat_placeholder\')" class="w-full pl-9 pr-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '              <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#58667e]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>',
            '            </div>',
            '            <div v-if="filteredFiats.length > 0" class="absolute z-10 w-full mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-xl overflow-hidden">',
            '              <button type="button" v-for="fiat in filteredFiats" :key="fiat" @click="selectFiat(fiat)" class="w-full px-4 py-2.5 text-left text-sm hover:bg-blue-50 flex items-center justify-between">[[ fiat ]]</button>',
            '            </div>',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.crypto_label\') ]]</label>',
            '            <select v-model="newService.cryptoCurrency" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] appearance-none">',
            '              <option v-for="opt in cryptoOptions" :key="opt" :value="opt">[[ opt ]]</option>',
            '            </select>',
            '          </div>',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-3 ml-1">[[ $t(\'main.my_business.rate_type_label\') ]]</label>',
            '          <div class="flex gap-4">',
            '            <label class="flex-1 cursor-pointer">',
            '              <input type="radio" v-model="newService.rateType" value="forex" class="hidden" />',
            '              <div :class="[\'p-3 rounded-xl border-2 text-center transition-all\', newService.rateType === \'forex\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']"><div class="text-xs font-bold">[[ $t(\'main.my_business.rate_forex\') ]]</div><div class="text-[10px] opacity-60">[[ $t(\'main.my_business.rate_forex_desc\') ]]</div></div>',
            '            </label>',
            '            <label class="flex-1 cursor-pointer">',
            '              <input type="radio" v-model="newService.rateType" value="request" class="hidden" />',
            '              <div :class="[\'p-3 rounded-xl border-2 text-center transition-all\', newService.rateType === \'request\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']"><div class="text-xs font-bold">[[ $t(\'main.my_business.rate_request\') ]]</div><div class="text-[10px] opacity-60">[[ $t(\'main.my_business.rate_request_desc\') ]]</div></div>',
            '            </label>',
            '          </div>',
            '        </div>',
            '        <div>',
            '          <div class="flex items-center justify-between mb-1.5 ml-1"><label class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.commission_label\') ]]</label><span class="text-sm font-bold text-[#3861fb]">[[ newService.commission ]]%</span></div>',
            '          <input type="range" v-model.number="newService.commission" min="0.1" max="10" step="0.1" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer" style="accent-color: #3861fb;" />',
            '          <div class="flex justify-between mt-2 text-[10px] text-[#58667e] font-bold"><span>0.1%</span><span>5.0%</span><span>10.0%</span></div>',
            '        </div>',
            '      </div>',
            '      <div class="p-6 bg-gray-50 border-t border-[#eff2f5] flex gap-3">',
            '        <button type="button" @click="showCreateModal = false" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="addService" :disabled="!(newService.fiatCurrency || \'\').trim()" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ $t(\'main.my_business.launch_service\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <div v-if="showPartnerModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="showPartnerModal = false"></div>',
            '    <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ $t(\'main.my_business.modal_new_partner_title\') ]]</h3>',
            '        <button type="button" @click="showPartnerModal = false" class="p-2 hover:bg-gray-100 rounded-full"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="p-6 space-y-4">',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.partner_name\') ]]</label>',
            '          <input type="text" v-model="newPartner.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" placeholder="GlobalPay Solutions" />',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.service_type\') ]]</label>',
            '          <input type="text" v-model="newPartner.serviceType" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" placeholder="onRamp (EUR/USDT)" />',
            '        </div>',
            '        <div class="grid grid-cols-2 gap-4">',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.base_commission_label\') ]]</label>',
            '            <input type="number" v-model.number="newPartner.baseCommission" min="0" step="0.1" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.my_commission_label\') ]]</label>',
            '            <input type="number" v-model.number="newPartner.myCommission" min="0" step="0.1" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '        </div>',
            '      </div>',
            '      <div class="p-6 bg-gray-50 border-t border-[#eff2f5] flex gap-3">',
            '        <button type="button" @click="showPartnerModal = false" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="addPartner" :disabled="!(newPartner.name || \'\').trim()" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ $t(\'main.my_business.connect_btn\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <div v-if="showRampModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="closeRampModal"></div>',
            '    <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden max-h-[90vh] overflow-y-auto">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ rampEditingId ? $t(\'main.my_business.ramp_modal_edit_title\') : $t(\'main.my_business.ramp_modal_add_title\') ]]</h3>',
            '        <button type="button" @click="closeRampModal" class="p-2 hover:bg-gray-100 rounded-full"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="p-6 space-y-4">',
            '        <template v-if="!rampEditingId">',
            '          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">',
            '            <div class="flex-1 min-w-0">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_role\') ]]</label>',
            '              <select v-model="rampForm.role" @change="onRampRoleChange" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]">',
            '                <option value="external">[[ $t(\'main.my_business.ramp_role_external\') ]]</option>',
            '                <option value="multisig">[[ $t(\'main.my_business.ramp_role_multisig\') ]]</option>',
            '              </select>',
            '            </div>',
            '            <div class="flex-1 min-w-0">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_blockchain\') ]]</label>',
            '              <select v-model="rampForm.blockchain" disabled class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm text-[#58667e] cursor-not-allowed">',
            '                <option value="tron">[[ $t(\'main.my_business.ramp_blockchain_tron\') ]]</option>',
            '              </select>',
            '            </div>',
            '          </div>',
            '          <template v-if="rampForm.role === \'multisig\'">',
            '            <div>',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '              <input type="text" v-model="rampForm.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '            </div>',
            '            <div class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">[[ $t(\'main.my_business.ramp_multisig_warning\') ]]</div>',
            '          </template>',
            '          <template v-else>',
            '            <div class="relative ramp-addr-combo" @focusout="onRampAddrFocusOut">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_address\') ]]</label>',
            '              <div class="relative">',
            '                <input type="text" v-model="rampForm.tron_address" :readonly="rampForm.participant_sub_id != null" autocomplete="off" @focus="onRampAddrFocus" @click="onRampAddrInputClick" @input="onRampTronAddressInput" class="w-full pl-4 pr-11 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm font-mono focus:outline-none focus:border-[#3861fb] read-only:bg-gray-100 read-only:text-[#191d23] read-only:cursor-pointer" :placeholder="$t(\'main.my_business.ramp_address_placeholder\')" />',
            '                <button type="button" tabindex="-1" :aria-expanded="rampAddrOpen ? \'true\' : \'false\'" :title="$t(\'main.my_business.ramp_address_toggle_list\')" @mousedown.prevent="toggleRampAddrDropdown" class="absolute right-1 top-1/2 -translate-y-1/2 p-2 rounded-lg text-[#58667e] hover:bg-gray-200/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3861fb]/40">',
            '                  <svg class="w-4 h-4 transition-transform duration-150" :class="rampAddrOpen ? \'rotate-180\' : \'\'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>',
            '                </button>',
            '              </div>',
            '              <div v-if="rampAddrOpen" class="absolute z-20 left-0 right-0 mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-lg max-h-52 overflow-y-auto">',
            '                <button type="button" class="w-full text-left px-4 py-3 text-sm hover:bg-blue-50 border-b border-[#eff2f5] font-medium text-[#3861fb]" @mousedown.prevent="pickRampCustomAddress">[[ $t(\'main.my_business.ramp_pick_custom_address\') ]]</button>',
            '                <button type="button" v-for="p in rampAddressPickerParticipants" :key="p.id" class="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 border-b border-[#eff2f5] last:border-0" @mousedown.prevent="pickRampParticipantSub(p)">',
            '                  <span class="font-mono text-xs text-[#191d23] block truncate">[[ p.wallet_address ]]</span>',
            '                  <div class="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1">',
            '                    <span v-if="p.nickname" class="text-[11px] text-[#58667e]">[[ p.nickname ]]</span>',
            '                    <span v-if="p.is_verified !== true" class="inline-flex text-[10px] font-bold uppercase tracking-wide text-amber-900 bg-amber-100 border border-amber-200 px-1.5 py-0.5 rounded-md">[[ $t(\'main.my_business.ramp_participant_not_verified\') ]]</span>',
            '                  </div>',
            '                </button>',
            '              </div>',
            '            </div>',
            '            <div>',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '              <input type="text" v-model="rampForm.name" :disabled="rampForm.participant_sub_id != null" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] disabled:bg-gray-100" />',
            '              <p v-if="rampForm.participant_sub_id != null" class="text-[10px] text-[#58667e] mt-1 ml-1">[[ $t(\'main.my_business.ramp_name_from_manager\') ]]</p>',
            '            </div>',
            '          </template>',
            '        </template>',
            '        <template v-else>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '            <input type="text" v-model="rampForm.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_role\') ]]</label>',
            '            <select v-model="rampForm.role" disabled tabindex="-1" class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm text-[#58667e] cursor-not-allowed">',
            '              <option value="external">[[ $t(\'main.my_business.ramp_role_external\') ]]</option>',
            '              <option value="multisig">[[ $t(\'main.my_business.ramp_role_multisig\') ]]</option>',
            '            </select>',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_tron\') ]]</label>',
            '            <input type="text" v-model="rampForm.tron_address" readonly class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm font-mono text-[#191d23] cursor-default focus:outline-none" />',
            '          </div>',
            '        </template>',
            '      </div>',
            '      <div class="p-6 bg-gray-50 border-t border-[#eff2f5] flex gap-3">',
            '        <button type="button" @click="closeRampModal" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="saveRampWallet" :disabled="rampSaving || (rampEditingId ? rampSaveEditDisabled : rampSaveAddDisabled)" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ $t(\'main.my_business.ramp_save\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <multisig-config-modal :show="showRampMultisigWizard" :wallet="rampMultisigWizardWallet" @close="closeMultisigWizard" @saved="onMultisigConfigModalSaved"></multisig-config-modal>',
            '</div>'
        ].join('')
    });
})();
