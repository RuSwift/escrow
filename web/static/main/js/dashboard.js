/**
 * Vue 2 компонент: Дашборд (main)
 */
(function() {
    function authHeadersMain() {
        var h = { Accept: 'application/json' };
        var key = (typeof window !== 'undefined' && window.main_auth_token_key) ? window.main_auth_token_key : 'main_auth_token';
        var token = null;
        try {
            token = localStorage.getItem(key);
        } catch (e) {}
        if (token) h['Authorization'] = 'Bearer ' + token;
        return h;
    }

    function buildRatiosPivot(apiData) {
        if (!apiData || typeof apiData !== 'object') return { engines: [], rows: [] };
        var engines = Object.keys(apiData).filter(function(k) {
            return Array.isArray(apiData[k]);
        }).sort();
        var pairMap = {};
        engines.forEach(function(eng) {
            apiData[eng].forEach(function(row) {
                var key = row.base + '/' + row.quote;
                if (!pairMap[key]) {
                    pairMap[key] = { base: row.base, quote: row.quote, ratios: {}, utcMax: null };
                }
                var r = row.pair && typeof row.pair.ratio === 'number' ? row.pair.ratio : null;
                pairMap[key].ratios[eng] = r;
                var u = row.pair && typeof row.pair.utc === 'number' ? row.pair.utc : null;
                if (r != null && u != null && isFinite(u)) {
                    if (pairMap[key].utcMax == null || u > pairMap[key].utcMax) {
                        pairMap[key].utcMax = u;
                    }
                }
            });
        });
        var rows = Object.keys(pairMap).sort().map(function(k) {
            return pairMap[k];
        }).filter(function(row) {
            return engines.some(function(eng) {
                var v = row.ratios[eng];
                return v != null && typeof v === 'number';
            });
        });
        return { engines: engines, rows: rows };
    }

Vue.component('dashboard', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            searchQuery: '',
            statusFilter: 'all',
            participantFilter: '',
            escrows: [
                { id: 'esc-001', title: 'Domain crypto-vault.com', description: 'Domain purchase agreement', amount: 2.5, currency: 'USDT', status: 'funded', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-10T14:30:00' },
                { id: 'esc-002', title: 'OTC 50K USDT', description: 'High-value OTC trade', amount: 50000, currency: 'USDT', status: 'pending', buyer_id: '0x33C...7788F', seller_id: '0x55D...9900A', created_at: '2026-03-11T09:15:00' },
                { id: 'esc-003', title: 'NFT #4421', description: 'Art piece transfer', amount: 0.8, currency: 'ETH', status: 'released', buyer_id: '0x99B...3344D', seller_id: '0x11A...5566E', created_at: '2026-03-08T16:00:00' },
                { id: 'esc-004', title: 'Software license', description: 'Annual enterprise license', amount: 12000, currency: 'USDT', status: 'disputed', buyer_id: '0x22B...4455C', seller_id: '0x77E...6677F', created_at: '2026-03-09T11:20:00' },
                { id: 'esc-005', title: 'Hardware batch', description: 'Miners delivery', amount: 150000, currency: 'USDT', status: 'funded', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-12T08:45:00' }
            ],
            mockLoading: false,
            apiOrders: [],
            ordersLoading: false,
            ordersError: null,
            ordersSearch: '',
            ratiosRaw: null,
            ratiosLoading: false,
            ratiosError: null,
            ratiosModalOpen: false,
            showDashboardMultisigWizard: false,
            dashboardMultisigWizardWallet: null,
            dashboardMultisigFetching: false,
            driftDetailModalOpen: false,
            driftDetailOrder: null,
            spaceRole: '',
            showWithdrawalModal: false,
            showWithdrawalDetailModal: false,
            withdrawalDetailOrder: null,
            rampWalletByTron: {},
            rampWalletById: {},
            signatoryTronLabelByAddress: {},
            ordersSignLinkCopiedId: null,
            _ordersSignLinkCopyTimer: null
        };
    },
    computed: {
        canCreateWithdrawal: function() {
            var r = (this.spaceRole || '').trim();
            return r === 'owner' || r === 'operator';
        },
        ratiosPivot: function() {
            return buildRatiosPivot(this.ratiosRaw);
        },
        marqueeSegments: function() {
            var pivot = this.ratiosPivot;
            var rows = pivot.rows || [];
            if (!rows.length) return [];
            return rows.map(function(r) {
                var vals = [];
                (pivot.engines || []).forEach(function(e) {
                    var x = r.ratios[e];
                    if (x != null && typeof x === 'number') vals.push(x);
                });
                var maxVal = vals.length ? Math.max.apply(null, vals) : null;
                var ratioText = maxVal != null ? String(Number(maxVal).toFixed(2)).replace(/\.?0+$/, '') : '—';
                return { pair: r.base + '/' + r.quote, ratioText: ratioText };
            });
        },
        filteredApiOrders: function() {
            var self = this;
            var q = (this.ordersSearch || '').toLowerCase();
            var items = this.apiOrders || [];
            if (!q) return items;
            return items.filter(function(row) {
                var p = row.payload || {};
                var blob = [
                    String(row.dedupe_key || ''),
                    String(p.kind || ''),
                    String(p.wallet_name || ''),
                    String(p.multisig_setup_status || ''),
                    String(p.tron_address || ''),
                    String(p.status || ''),
                    String(p.destination_address || ''),
                    String((p.token && p.token.symbol) || ''),
                    String(self.withdrawalSignatoriesDisplay(row) || '')
                ].join(' ').toLowerCase();
                return blob.indexOf(q) !== -1;
            });
        },
        filteredEscrows: function() {
            var self = this;
            var query = (this.searchQuery || '').toLowerCase();
            var statusFilter = this.statusFilter;
            var participantFilter = (this.participantFilter || '').toLowerCase();
            return this.escrows.filter(function(escrow) {
                var matchesSearch = !query ||
                    (escrow.title || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.description || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.id || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.status || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.buyer_id || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.seller_id || '').toLowerCase().indexOf(query) !== -1;
                var matchesStatus = statusFilter === 'all' || escrow.status === statusFilter;
                var matchesParticipant = !participantFilter ||
                    (escrow.buyer_id || '').toLowerCase().indexOf(participantFilter) !== -1 ||
                    (escrow.seller_id || '').toLowerCase().indexOf(participantFilter) !== -1;
                return matchesSearch && matchesStatus && matchesParticipant;
            });
        },
        /** Блоки расхождений в модалке — только если есть ненулевые списки отличий */
        driftModalShowOwnersBlock: function() {
            var p = this.driftDetailOrder && this.driftDetailOrder.payload;
            if (!p || !p.owners_drift) return false;
            var m = p.owners_only_in_meta;
            var s = p.owners_only_in_space;
            return (Array.isArray(m) && m.length > 0) || (Array.isArray(s) && s.length > 0);
        },
        driftModalActorsOnlyInMetaArr: function() {
            var p = this.driftDetailOrder && this.driftDetailOrder.payload;
            if (!p) return [];
            return Array.isArray(p.actors_only_in_meta) ? p.actors_only_in_meta : (Array.isArray(p.only_in_meta) ? p.only_in_meta : []);
        },
        driftModalActorsOnlyInSpaceArr: function() {
            var p = this.driftDetailOrder && this.driftDetailOrder.payload;
            if (!p) return [];
            return Array.isArray(p.actors_only_in_space) ? p.actors_only_in_space : (Array.isArray(p.only_in_space) ? p.only_in_space : []);
        },
        driftModalShowActorsBlock: function() {
            var p = this.driftDetailOrder && this.driftDetailOrder.payload;
            if (!p || !p.actors_drift) return false;
            return this.driftModalActorsOnlyInMetaArr.length > 0 || this.driftModalActorsOnlyInSpaceArr.length > 0;
        }
    },
    mounted: function() {
        if (typeof window !== 'undefined' && window.__SPACE_ROLE__) {
            this.spaceRole = String(window.__SPACE_ROLE__).trim();
        }
        this.fetchRatios();
        this.fetchOrders();
    },
    methods: {
        fetchRatios: function() {
            var self = this;
            self.ratiosLoading = true;
            self.ratiosError = null;
            fetch('/v1/dashboard/ratios', {
                method: 'GET',
                headers: authHeadersMain(),
                credentials: 'include'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    if (data && data.root && typeof data.root === 'object') {
                        data = data.root;
                    }
                    self.ratiosRaw = data;
                })
                .catch(function() {
                    self.ratiosError = true;
                    self.ratiosRaw = null;
                })
                .finally(function() {
                    self.ratiosLoading = false;
                });
        },
        fetchOrders: function() {
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? String(window.__CURRENT_SPACE__).trim() : '';
            if (!space) {
                self.apiOrders = [];
                self.rampWalletByTron = {};
                self.rampWalletById = {};
                self.signatoryTronLabelByAddress = {};
                return;
            }
            self.ordersLoading = true;
            self.ordersError = null;
            var walletsPromise = self.fetchRampWalletsForSignatories();
            var labelsPromise = self.fetchSignatoryTronLabels();
            var ordersPromise = fetch('/v1/spaces/' + encodeURIComponent(space) + '/orders', {
                method: 'GET',
                headers: authHeadersMain(),
                credentials: 'include'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    self.apiOrders = (data && data.items && Array.isArray(data.items)) ? data.items : [];
                })
                .catch(function() {
                    self.ordersError = true;
                    self.apiOrders = [];
                });
            Promise.all([ordersPromise, walletsPromise, labelsPromise]).finally(function() {
                self.ordersLoading = false;
            });
        },
        fetchSignatoryTronLabels: function() {
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? String(window.__CURRENT_SPACE__).trim() : '';
            if (!space) {
                self.signatoryTronLabelByAddress = {};
                return Promise.resolve();
            }
            return fetch('/v1/spaces/' + encodeURIComponent(space) + '/signatory-tron-labels', {
                method: 'GET',
                headers: authHeadersMain(),
                credentials: 'include'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    var items = (data && data.items && Array.isArray(data.items)) ? data.items : [];
                    var m = {};
                    items.forEach(function(row) {
                        var addr = (row.tron_address || '').trim();
                        var nick = (row.nickname || '').trim();
                        if (addr && nick) m[addr] = nick;
                    });
                    self.signatoryTronLabelByAddress = m;
                })
                .catch(function() {
                    self.signatoryTronLabelByAddress = {};
                });
        },
        fetchRampWalletsForSignatories: function() {
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? String(window.__CURRENT_SPACE__).trim() : '';
            if (!space) {
                self.rampWalletByTron = {};
                self.rampWalletById = {};
                return Promise.resolve();
            }
            return fetch('/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets', {
                method: 'GET',
                headers: authHeadersMain(),
                credentials: 'include'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    var items = (data && data.items) ? data.items : [];
                    var byTron = {};
                    var byId = {};
                    items.forEach(function(w) {
                        var t = (w.tron_address || '').trim();
                        if (t) byTron[t] = w;
                        if (w.id != null) byId[Number(w.id)] = w;
                    });
                    self.rampWalletByTron = byTron;
                    self.rampWalletById = byId;
                })
                .catch(function() {
                    self.rampWalletByTron = {};
                    self.rampWalletById = {};
                });
        },
        /** Как в my_business.multisigStatusLabel — те же ключи main.my_business.multisig_status_* */
        ephemeralMultisigStatusLabel: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.multisig_setup_status != null) ? String(p.multisig_setup_status) : '';
            if (!st) return '—';
            var key = 'main.my_business.multisig_status_' + st;
            var t = this.$t(key);
            return (t && t !== key) ? t : st;
        },
        ephemeralMultisigBadgeClass: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'multisig_space_drift') {
                return 'bg-violet-50 text-violet-900 border border-violet-100';
            }
            return 'bg-amber-50 text-amber-900 border border-amber-100';
        },
        ephemeralMultisigSpinnerVisible: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.multisig_setup_status != null) ? String(p.multisig_setup_status) : '';
            if (!st) return false;
            if (st === 'failed' || st === 'reconfigure') return false;
            if (st === 'active') return false;
            return true;
        },
        isMultisigEphemeralOrder: function(order) {
            var k = order && order.payload && order.payload.kind;
            return k === 'multisig_pipeline' || k === 'multisig_space_drift';
        },
        isWithdrawalOrder: function(order) {
            return order && order.payload && order.payload.kind === 'withdrawal_request';
        },
        withdrawalAmountDisplay: function(order) {
            var p = (order && order.payload) || {};
            var raw = p.amount_raw;
            if (raw == null) return '—';
            var tok = p.token || {};
            var ttype = (tok.type || '').toLowerCase();
            var dec = typeof tok.decimals === 'number' && tok.decimals >= 0 ? tok.decimals : 6;
            var sym = (tok.symbol || '').toUpperCase() || (ttype === 'native' ? 'TRX' : 'TOKEN');
            var human = Number(raw) / Math.pow(10, dec);
            var formatted = human.toLocaleString(undefined, {
                maximumFractionDigits: dec,
                minimumFractionDigits: 0
            });
            return formatted + ' ' + sym;
        },
        withdrawalStatusLabel: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.status || '').trim();
            if (!st) return '—';
            var key = 'main.dashboard.withdrawal_status_' + st;
            var t = this.$t(key);
            return (t && t !== key) ? t : st;
        },
        withdrawalBadgeClass: function() {
            return 'bg-sky-50 text-sky-900 border border-sky-100';
        },
        withdrawalSpinnerVisible: function(order) {
            if (!this.isWithdrawalOrder(order)) return false;
            var p = (order && order.payload) || {};
            var st = (p.status || '').trim();
            if (st === 'confirmed' || st === 'failed') return false;
            return true;
        },
        shortenAddress: function(addr) {
            var s = String(addr || '').trim();
            if (!s) return '—';
            if (s.length <= 12) return s;
            return s.slice(0, 4) + '…' + s.slice(-4);
        },
        displayNameForTronAddress: function(addr) {
            var a = String(addr || '').trim();
            if (!a) return '—';
            var w = this.rampWalletByTron[a];
            if (w && (w.name || '').trim()) return (w.name || '').trim();
            var lab = this.signatoryTronLabelByAddress[a];
            if (lab) return lab;
            return this.shortenAddress(a);
        },
        withdrawalSignatoriesDisplay: function(order) {
            if (!this.isWithdrawalOrder(order)) return '—';
            var p = order.payload || {};
            var role = (p.wallet_role || '').trim();
            if (role === 'external') {
                var wid = order.space_wallet_id;
                if (wid != null && this.rampWalletById[Number(wid)]) {
                    var rw = this.rampWalletById[Number(wid)];
                    if ((rw.name || '').trim()) return (rw.name || '').trim();
                }
                var extAddr = (p.tron_address || '').trim();
                return extAddr ? this.displayNameForTronAddress(extAddr) : '—';
            }
            if (role === 'multisig') {
                var actors = Array.isArray(p.actors_snapshot) ? p.actors_snapshot : [];
                if (!actors.length) return '—';
                var self = this;
                var parts = actors.map(function(a) {
                    return self.displayNameForTronAddress(a);
                });
                return parts.join(', ');
            }
            return '—';
        },
        withdrawalSignatoriesTitle: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var p = order.payload || {};
            var role = (p.wallet_role || '').trim();
            if (role === 'external') {
                return (p.tron_address || '').trim() || '';
            }
            if (role === 'multisig') {
                var actors = Array.isArray(p.actors_snapshot) ? p.actors_snapshot : [];
                return actors.map(function(a) { return String(a || '').trim(); }).filter(Boolean).join(', ');
            }
            return '';
        },
        /** Полная цепочка адресов/тикера для подсказки в описании вывода. */
        withdrawalRowDescTitle: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var p = order.payload || {};
            var src = (p.tron_address || '').trim();
            var dest = (p.destination_address || '').trim();
            var tok = (p.token && p.token.symbol) ? String(p.token.symbol) : '';
            var parts = [];
            if (src) parts.push(src);
            if (tok) parts.push(tok);
            if (dest) parts.push(dest);
            return parts.join(' → ');
        },
        /** Токен публичной страницы подписи: dedupe_key = withdrawal:{token}. */
        withdrawalSignTokenFromOrder: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var dk = String((order && order.dedupe_key) || '').trim();
            var prefix = 'withdrawal:';
            if (dk.indexOf(prefix) !== 0) return '';
            var t = dk.slice(prefix.length).trim();
            return t || '';
        },
        withdrawalSignHref: function(order) {
            var t = this.withdrawalSignTokenFromOrder(order);
            if (!t) return '#';
            return '/o/' + encodeURIComponent(t);
        },
        withdrawalSignAbsoluteUrl: function(order) {
            var path = this.withdrawalSignHref(order);
            if (!path || path === '#') return '';
            if (typeof window !== 'undefined' && window.location && window.location.origin) {
                return window.location.origin + path;
            }
            return path;
        },
        withdrawalBroadcastTxId: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var p = (order && order.payload) || {};
            return String((p.broadcast_tx_id || '')).trim();
        },
        withdrawalTxExplorerUrl: function(order) {
            var tx = this.withdrawalBroadcastTxId(order);
            if (!tx || !window.EscrowWithdrawalSign || typeof window.EscrowWithdrawalSign.tronTxExplorerUrl !== 'function') {
                return '';
            }
            return window.EscrowWithdrawalSign.tronTxExplorerUrl(tx);
        },
        withdrawalTxExplorerVisible: function(order) {
            if (!this.withdrawalBroadcastTxId(order)) return false;
            var p = (order && order.payload) || {};
            var st = String((p.status || '')).trim();
            return st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed';
        },
        withdrawalDeleteAllowed: function(order) {
            if (!this.isWithdrawalOrder(order)) return false;
            var st = String((((order || {}).payload || {}).status || '')).trim();
            if (st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed') return false;
            return true;
        },
        copyWithdrawalSignLink: function(order, ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            var url = this.withdrawalSignAbsoluteUrl(order);
            if (!url) return;
            var self = this;
            function afterCopy() {
                self.ordersSignLinkCopiedId = order.id;
                if (self._ordersSignLinkCopyTimer) clearTimeout(self._ordersSignLinkCopyTimer);
                self._ordersSignLinkCopyTimer = setTimeout(function() {
                    self.ordersSignLinkCopiedId = null;
                }, 2000);
            }
            if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(afterCopy).catch(function() {
                    self.copyWithdrawalSignLinkFallback(url, afterCopy);
                });
            } else {
                this.copyWithdrawalSignLinkFallback(url, afterCopy);
            }
        },
        copyWithdrawalSignLinkFallback: function(text, done) {
            try {
                var ta = document.createElement('textarea');
                ta.value = text;
                ta.setAttribute('readonly', '');
                ta.style.position = 'fixed';
                ta.style.left = '-9999px';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                if (done) done();
            } catch (e) {}
        },
        onNewRequestSelect: function(e) {
            var el = e && e.target;
            var v = el ? el.value : '';
            if (v === 'withdrawal') {
                this.showWithdrawalModal = true;
            }
            if (el) el.value = '';
        },
        closeWithdrawalModal: function() {
            this.showWithdrawalModal = false;
        },
        closeWithdrawalDetailModal: function() {
            this.showWithdrawalDetailModal = false;
            this.withdrawalDetailOrder = null;
        },
        onWithdrawalDetailDeleted: function() {
            this.fetchOrders();
            this.closeWithdrawalDetailModal();
        },
        onWithdrawalDetailUpdated: function() {
            this.fetchOrders();
        },
        deleteWithdrawalOrder: function(order, ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            if (!this.isWithdrawalOrder(order) || !this.canCreateWithdrawal || !this.withdrawalDeleteAllowed(order)) return;
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? String(window.__CURRENT_SPACE__).trim() : '';
            if (!space) return;
            function runDelete() {
                fetch('/v1/spaces/' + encodeURIComponent(space) + '/orders/' + encodeURIComponent(order.id), {
                    method: 'DELETE',
                    headers: authHeadersMain(),
                    credentials: 'include'
                })
                    .then(function(res) {
                        if (res.ok) {
                            self.fetchOrders();
                            return;
                        }
                        if (res.status === 400) {
                            return res.json().then(function(d) {
                                var msg = (d && typeof d.detail === 'string') ? d.detail : self.$t('main.withdrawal_detail.delete_order_forbidden');
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
                        throw new Error('HTTP ' + res.status);
                    })
                    .catch(function() {
                        if (typeof window.showAlert === 'function') {
                            window.showAlert({
                                title: self.$t('main.dialog.error_title'),
                                message: self.$t('main.dashboard.orders_delete_error')
                            });
                        } else {
                            alert(self.$t('main.dashboard.orders_delete_error'));
                        }
                    });
            }
            if (typeof window.showConfirm === 'function') {
                window.showConfirm({
                    title: self.$t('main.dashboard.orders_delete_confirm_title'),
                    message: self.$t('main.dashboard.orders_delete_confirm'),
                    danger: true,
                    onConfirm: runDelete
                });
            } else {
                if (!confirm(self.$t('main.dashboard.orders_delete_confirm'))) return;
                runDelete();
            }
        },
        onApiOrderRowClick: function(order) {
            if (this.isWithdrawalOrder(order)) {
                this.withdrawalDetailOrder = order;
                this.showWithdrawalDetailModal = true;
                return;
            }
            if (!this.isMultisigEphemeralOrder(order) || this.dashboardMultisigFetching) return;
            if (this.isDriftOrder(order)) {
                this.openDriftDetailModal(order);
                return;
            }
            this.openDashboardMultisigWizardFromOrder(order);
        },
        openDashboardMultisigWizardFromOrder: function(order) {
            var p = (order && order.payload) || {};
            var wid = order.space_wallet_id != null ? order.space_wallet_id : p.wallet_id;
            if (wid == null) return;
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                ? String(window.__CURRENT_SPACE__).trim()
                : '';
            if (!space) return;
            self.dashboardMultisigFetching = true;
            fetch(
                '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets?role=multisig',
                {
                    method: 'GET',
                    headers: authHeadersMain(),
                    credentials: 'include'
                }
            )
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    var items = (data && data.items) || [];
                    var rw = null;
                    for (var i = 0; i < items.length; i++) {
                        if (items[i].id === wid) {
                            rw = items[i];
                            break;
                        }
                    }
                    if (!rw) {
                        if (typeof window.showAlert === 'function') {
                            window.showAlert({
                                title: self.$t('main.dialog.error_title'),
                                message: self.$t('main.dashboard.multisig_modal_load_error')
                            });
                        }
                        return;
                    }
                    self.dashboardMultisigWizardWallet = rw;
                    self.showDashboardMultisigWizard = true;
                })
                .catch(function() {
                    if (typeof window.showAlert === 'function') {
                        window.showAlert({
                            title: self.$t('main.dialog.error_title'),
                            message: self.$t('main.dashboard.multisig_modal_load_error')
                        });
                    }
                })
                .finally(function() {
                    self.dashboardMultisigFetching = false;
                });
        },
        closeDashboardMultisigWizard: function() {
            this.showDashboardMultisigWizard = false;
            this.dashboardMultisigWizardWallet = null;
        },
        onDashboardMultisigConfigSaved: function() {
            this.fetchOrders();
        },
        isDriftOrder: function(order) {
            return !!(order && order.payload && order.payload.kind === 'multisig_space_drift');
        },
        openDriftDetailModal: function(order) {
            if (!this.isDriftOrder(order)) return;
            this.driftDetailOrder = order;
            this.driftDetailModalOpen = true;
        },
        closeDriftDetailModal: function() {
            this.driftDetailModalOpen = false;
            this.driftDetailOrder = null;
        },
        /** PATCH multisig_begin_reconfigure, затем открыть multisig-config-modal (как beginMultisigReconfigure в my_business.js). */
        beginDashboardMultisigReconfigureFromDrift: function() {
            var order = this.driftDetailOrder;
            var p = (order && order.payload) || {};
            var wid = order && order.space_wallet_id != null ? order.space_wallet_id : p.wallet_id;
            if (wid == null) return;
            var self = this;
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                ? String(window.__CURRENT_SPACE__).trim()
                : '';
            if (!space) return;
            self.dashboardMultisigFetching = true;
            var headers = Object.assign({}, authHeadersMain(), { 'Content-Type': 'application/json' });
            fetch(
                '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets/' + encodeURIComponent(String(wid)),
                {
                    method: 'PATCH',
                    headers: headers,
                    credentials: 'include',
                    body: JSON.stringify({ multisig_begin_reconfigure: true })
                }
            )
                .then(function(res) {
                    if (!res.ok) {
                        return res.json().then(function(j) {
                            var d = j && j.detail;
                            var msg = typeof d === 'string' ? d : (d ? JSON.stringify(d) : String(res.status));
                            throw new Error(msg);
                        });
                    }
                    return res.json();
                })
                .then(function(data) {
                    self.closeDriftDetailModal();
                    self.dashboardMultisigWizardWallet = data;
                    self.showDashboardMultisigWizard = true;
                })
                .catch(function(e) {
                    if (typeof window.showAlert === 'function') {
                        window.showAlert({
                            title: self.$t('main.dialog.error_title'),
                            message: (e && e.message) ? e.message : self.$t('main.dashboard.multisig_modal_load_error')
                        });
                    }
                })
                .finally(function() {
                    self.dashboardMultisigFetching = false;
                });
        },
        driftAddrList: function(arr) {
            if (!arr || !Array.isArray(arr) || !arr.length) return '—';
            return arr.join(', ');
        },
        orderRowTitle: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'withdrawal_request') {
                return this.$t('main.dashboard.order_kind_withdrawal');
            }
            var wid = order.space_wallet_id != null ? order.space_wallet_id : (p.wallet_id != null ? p.wallet_id : null);
            return (p.wallet_name || '').trim() || ('#' + (wid != null ? wid : (order.id || '')));
        },
        orderRowDesc: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'withdrawal_request') {
                var dest = (p.destination_address || '').trim();
                var tok = (p.token && p.token.symbol) ? String(p.token.symbol) : '';
                var destDisp = dest ? this.shortenAddress(dest) : '';
                var tail = tok + (destDisp ? ' → ' + destDisp : '');
                var srcRaw = (p.tron_address || '').trim();
                var srcDisp = srcRaw ? this.shortenAddress(srcRaw) : '';
                if (srcDisp && srcDisp !== '—') {
                    return srcDisp + ' → ' + tail;
                }
                return tail;
            }
            if (p.kind === 'multisig_space_drift') {
                if (p.owners_drift == null && p.actors_drift == null) {
                    var om0 = (p.only_in_meta && p.only_in_meta.length) ? p.only_in_meta.join(', ') : '';
                    var os0 = (p.only_in_space && p.only_in_space.length) ? p.only_in_space.join(', ') : '';
                    return this.$t('main.dashboard.order_drift_summary', { only_in_meta: om0 || '—', only_in_space: os0 || '—' });
                }
                var parts = [];
                if (p.owners_drift) {
                    var oim = (p.owners_only_in_meta && p.owners_only_in_meta.length) ? p.owners_only_in_meta.join(', ') : '';
                    var ois = (p.owners_only_in_space && p.owners_only_in_space.length) ? p.owners_only_in_space.join(', ') : '';
                    parts.push(this.$t('main.dashboard.order_drift_owners_line', { only_in_meta: oim || '—', only_in_space: ois || '—' }));
                }
                if (p.actors_drift) {
                    var aim = (p.actors_only_in_meta && p.actors_only_in_meta.length) ? p.actors_only_in_meta.join(', ') : '';
                    var ais = (p.actors_only_in_space && p.actors_only_in_space.length) ? p.actors_only_in_space.join(', ') : '';
                    parts.push(this.$t('main.dashboard.order_drift_actors_line', { only_in_meta: aim || '—', only_in_space: ais || '—' }));
                }
                if (parts.length) return parts.join(' · ');
                var om = (p.only_in_meta && p.only_in_meta.length) ? p.only_in_meta.join(', ') : '';
                var os = (p.only_in_space && p.only_in_space.length) ? p.only_in_space.join(', ') : '';
                return this.$t('main.dashboard.order_drift_summary', { only_in_meta: om || '—', only_in_space: os || '—' });
            }
            var tr = (p.tron_address || '').trim();
            return tr || '';
        },
        formatRatioCell: function(val) {
            if (val == null || typeof val !== 'number') return '—';
            return String(Number(val).toFixed(2)).replace(/\.?0+$/, '');
        },
        formatUtcCell: function(tsSeconds) {
            if (tsSeconds == null || typeof tsSeconds !== 'number' || !isFinite(tsSeconds)) return '—';
            var d = new Date(tsSeconds * 1000);
            if (isNaN(d.getTime())) return '—';
            return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
        },
        formatDate: function(created_at) {
            if (!created_at) return '—';
            var d = new Date(created_at);
            if (isNaN(d.getTime())) return '—';
            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return months[d.getMonth()] + ' ' + d.getDate() + ', ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        },
        formatUsd: function(amount, currency) {
            if (currency === 'USDT' && amount) return '≈ $' + (amount).toLocaleString();
            if (currency === 'ETH' && amount) return '≈ $' + (Math.round(amount * 3500)).toLocaleString();
            return '—';
        },
        statusClass: function(status) {
            return status === 'pending' ? 'bg-amber-100 text-amber-700' : status === 'funded' ? 'bg-blue-100 text-blue-700' : status === 'released' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700';
        },
        statusDotClass: function(status) {
            return status === 'pending' ? 'bg-amber-500' : status === 'funded' ? 'bg-blue-500' : status === 'released' ? 'bg-emerald-500' : 'bg-rose-500';
        },
        goToDetail: function(escrowId) {
            if (!escrowId || !window.__mainApp) return;
            window.__mainApp.selectedEscrowId = escrowId;
            window.__mainApp.currentPage = 'detail';
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) {
                sidebar.__vue__.currentPage = 'dashboard';
            }
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            var url = base + '?initial_page=detail&escrow_id=' + encodeURIComponent(escrowId);
            history.pushState({ page: 'detail', escrowId: escrowId }, '', url);
        },
        rolesPageHref: function() {
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            return base + '?initial_page=space-roles';
        },
        goToRoles: function() {
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('space-roles');
            if (window.__mainApp) window.__mainApp.currentPage = 'space-roles';
        },
        profilePageHref: function() {
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            return base + '?initial_page=space-profile';
        },
        goToProfile: function() {
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('space-profile');
            if (window.__mainApp) window.__mainApp.currentPage = 'space-profile';
        }
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div v-if="typeof window !== \'undefined\' && window.__SPACE_ROLE__ === \'owner\' && window.__SPACE_SUBS_COUNT__ === 0" class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-amber-800 text-sm font-medium flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>[[ $t(\'main.dashboard.no_roles_warning\') ]]</span>
        <a :href="rolesPageHref()" @click.prevent="goToRoles()" class="font-semibold text-main-blue hover:underline">[[ $t(\'main.dashboard.go_to_roles\') ]]</a>
      </div>
      <div v-if="typeof window !== \'undefined\' && window.__SPACE_ROLE__ === \'owner\' && window.__SPACE_PROFILE_FILLED__ === false" class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-amber-800 text-sm font-medium flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>[[ $t(\'main.dashboard.no_profile_warning\') ]]</span>
        <a :href="profilePageHref()" @click.prevent="goToProfile()" class="font-semibold text-main-blue hover:underline">[[ $t(\'main.dashboard.go_to_profile\') ]]</a>
      </div>
      <div v-if="ratiosLoading" class="mb-6 h-10 rounded-lg bg-[#eff2f5] animate-pulse border border-[#eff2f5]" aria-hidden="true"></div>
      <div v-else-if="ratiosError" class="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-800">[[ $t('main.dashboard.ratios_load_error') ]]</div>
      <div v-else-if="ratiosPivot.rows.length" class="mb-6 flex rounded-lg border border-[#eff2f5] bg-white overflow-hidden shadow-sm cursor-pointer group" @click="ratiosModalOpen = true" role="button" :aria-label="$t('main.dashboard.ratios_modal_title')">
        <div class="flex-1 min-w-0 overflow-hidden py-2">
          <div class="dashboard-ratios-marquee-track">
            <div class="flex items-center shrink-0">
              <span v-for="(seg, i) in marqueeSegments" :key="'m1-' + i" class="inline-flex items-center px-4 text-sm whitespace-nowrap border-r border-[#eff2f5]">
                <span class="font-bold text-[#191d23]">[[ seg.pair ]]</span>
                <span class="mx-2 text-cmc-muted">[[ seg.ratioText ]]</span>
              </span>
            </div>
            <div class="flex items-center shrink-0">
              <span v-for="(seg, i) in marqueeSegments" :key="'m2-' + i" class="inline-flex items-center px-4 text-sm whitespace-nowrap border-r border-[#eff2f5]">
                <span class="font-bold text-[#191d23]">[[ seg.pair ]]</span>
                <span class="mx-2 text-cmc-muted">[[ seg.ratioText ]]</span>
              </span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-1.5 px-3 sm:px-4 shrink-0 border-l border-[#eff2f5] bg-[#fafbfd] text-xs font-bold text-main-blue group-hover:bg-main-blue/5 transition-colors">
          <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
          <span class="hidden sm:inline">[[ $t('main.dashboard.ratios_expand') ]]</span>
        </div>
      </div>
      <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div class="flex flex-wrap items-center gap-2 min-w-0">
          <h1 class="text-2xl font-bold">[[ $t('main.dashboard.title') ]]</h1>
          <button
            type="button"
            @click="fetchOrders"
            :disabled="ordersLoading"
            class="inline-flex items-center gap-1.5 rounded-lg border border-[#eff2f5] bg-white px-3 py-1.5 text-xs font-bold text-[#3861fb] hover:bg-[#f8fafd] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
            :aria-label="$t('main.dashboard.orders_refresh')"
          >
            <svg class="w-4 h-4 shrink-0" :class="ordersLoading ? 'animate-spin text-[#3861fb]' : 'text-[#3861fb]'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>[[ $t('main.dashboard.orders_refresh') ]]</span>
          </button>
        </div>
        <div class="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
          <div class="relative flex-1 md:w-80">
            <input v-model="ordersSearch" type="text" :placeholder="$t('main.dashboard.orders_search_placeholder')" class="w-full pl-10 pr-4 py-2 bg-white border border-[#eff2f5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
          </div>
          <button type="button" class="cmc-btn-primary flex items-center justify-center gap-2 whitespace-nowrap py-2 px-4">
            [[ $t('main.dashboard.create_escrow') ]]
          </button>
        </div>
      </div>
      <div v-if="canCreateWithdrawal" class="flex flex-wrap items-center gap-2 mb-4">
        <label class="text-xs font-semibold text-[#58667e] shrink-0" for="dash-new-request-select">[[ $t('main.dashboard.new_request_label') ]]</label>
        <select
          id="dash-new-request-select"
          @change="onNewRequestSelect"
          class="max-w-xs rounded-lg border border-[#eff2f5] bg-white px-3 py-2 text-sm text-[#191d23] focus:outline-none focus:ring-2 focus:ring-main-blue/20"
        >
          <option value="">[[ $t('main.dashboard.new_request_placeholder') ]]</option>
          <option value="withdrawal">[[ $t('main.dashboard.new_request_withdrawal') ]]</option>
          <option value="invoice" disabled>[[ $t('main.dashboard.new_request_invoice') ]]</option>
        </select>
      </div>
      <div v-if="ordersError" class="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-800">[[ $t('main.dashboard.orders_load_error') ]]</div>
      <div class="cmc-card overflow-hidden mb-10">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="cmc-table-header w-12">#</th>
                <th class="cmc-table-header whitespace-nowrap min-w-[11rem] sm:min-w-[13rem]">[[ $t('main.dashboard.table_col_link') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_title') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_amount') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_status') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_created') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_signatories') ]]</th>
                <th class="cmc-table-header text-right">[[ $t('main.dashboard.table_col_action') ]]</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="ordersLoading">
                <tr v-for="i in 5" :key="'ord-sk-' + i" class="animate-pulse">
                  <td colspan="8" class="cmc-table-cell h-16 bg-gray-50/50"></td>
                </tr>
              </template>
              <tr v-else-if="filteredApiOrders.length === 0">
                <td colspan="8" class="cmc-table-cell text-center py-12 text-cmc-muted">[[ $t('main.dashboard.ephemeral_no_orders') ]]</td>
              </tr>
              <tr v-else v-for="(order, i) in filteredApiOrders" :key="'api-ord-' + order.id"
                class="border-b border-[#eff2f5] last:border-0 transition-all duration-200"
                :class="(isMultisigEphemeralOrder(order) || isWithdrawalOrder(order)) ? 'hover:bg-[#f0f6ff] cursor-pointer' : 'hover:bg-[#f8fafd]'"
                :tabindex="(isMultisigEphemeralOrder(order) || isWithdrawalOrder(order)) ? 0 : -1"
                @click="onApiOrderRowClick(order)"
                @keydown.enter.prevent="onApiOrderRowClick(order)"
              >
                <td class="cmc-table-cell text-cmc-muted font-medium">[[ i + 1 ]]</td>
                <td class="cmc-table-cell align-middle" @click.stop>
                  <div v-if="isWithdrawalOrder(order) && withdrawalSignTokenFromOrder(order)" class="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    <a
                      :href="withdrawalSignHref(order)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1.5 text-xs font-semibold text-main-blue hover:opacity-90 shrink-0"
                      :aria-label="$t('main.dashboard.orders_sign_link') + ' — ' + withdrawalSignHref(order)"
                      @click.stop
                    >
                      <svg class="w-4 h-4 shrink-0 text-main-blue" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                      <span>[[ $t('main.dashboard.orders_link_label') ]]</span>
                    </a>
                    <button
                      type="button"
                      class="shrink-0 rounded-md border border-[#eff2f5] bg-white px-2 py-1 text-[10px] sm:text-xs font-semibold text-[#58667e] hover:bg-[#f8fafd] hover:border-[#cfd6e4] focus:outline-none focus:ring-2 focus:ring-main-blue/25"
                      :aria-label="$t('main.dashboard.orders_copy_sign_link')"
                      @click="copyWithdrawalSignLink(order, $event)"
                    >
                      [[ ordersSignLinkCopiedId === order.id ? $t('main.copied') : $t('main.dashboard.orders_copy_sign_link') ]]
                    </button>
                    <a
                      v-if="withdrawalTxExplorerVisible(order)"
                      :href="withdrawalTxExplorerUrl(order)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-[10px] sm:text-xs font-semibold text-main-green hover:text-emerald-700 shrink-0 rounded-md px-1.5 py-0.5 bg-main-green/12 hover:bg-main-green/20 transition-colors"
                      :aria-label="$t('main.dashboard.withdrawal_tx_explorer')"
                      @click.stop
                    >
                      <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0 text-main-green" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3z"/>
                        <path d="M12 12 4 7.5M12 12l8-4.5M12 12v9"/>
                      </svg>
                      <span>[[ $t('main.dashboard.withdrawal_tx_explorer_short') ]]</span>
                    </a>
                  </div>
                  <span v-else class="text-cmc-muted text-xs">—</span>
                </td>
                <td class="cmc-table-cell">
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
                      <svg class="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div class="min-w-0">
                      <div class="font-bold truncate">[[ orderRowTitle(order) ]]</div>
                      <div class="text-xs text-cmc-muted truncate max-w-[240px] sm:max-w-md" :title="isWithdrawalOrder(order) ? withdrawalRowDescTitle(order) : ''">[[ orderRowDesc(order) ]]</div>
                    </div>
                  </div>
                </td>
                <td class="cmc-table-cell text-cmc-muted">
                  <span v-if="isWithdrawalOrder(order)">[[ withdrawalAmountDisplay(order) ]]</span>
                  <span v-else>—</span>
                </td>
                <td class="cmc-table-cell">
                  <div v-if="isWithdrawalOrder(order)" class="flex items-center gap-1 min-w-0">
                    <div :class="['inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md pl-2 pr-1.5 py-0.5', withdrawalBadgeClass()]">
                      <span class="text-[10px] font-bold uppercase truncate">[[ withdrawalStatusLabel(order) ]]</span>
                      <svg v-if="withdrawalSpinnerVisible(order)" class="w-3.5 h-3.5 shrink-0 animate-spin opacity-90 text-sky-800" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </div>
                  </div>
                  <div v-else class="flex items-center gap-1 min-w-0">
                    <div :class="['inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md pl-2 pr-1.5 py-0.5', ephemeralMultisigBadgeClass(order)]">
                      <span class="text-[10px] font-bold uppercase truncate">[[ ephemeralMultisigStatusLabel(order) ]]</span>
                      <svg v-if="ephemeralMultisigSpinnerVisible(order)" class="w-3.5 h-3.5 shrink-0 animate-spin opacity-90" :class="(order.payload && order.payload.kind) === 'multisig_space_drift' ? 'text-violet-800' : 'text-amber-800'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </div>
                  </div>
                </td>
                <td class="cmc-table-cell text-cmc-muted">[[ formatDate(order.updated_at) ]]</td>
                <td class="cmc-table-cell text-cmc-muted text-xs min-w-0 max-w-[220px]">
                  <span v-if="isWithdrawalOrder(order)" class="block truncate" :title="withdrawalSignatoriesTitle(order)">[[ withdrawalSignatoriesDisplay(order) ]]</span>
                  <span v-else>—</span>
                </td>
                <td class="cmc-table-cell text-right align-middle" @click.stop>
                  <button
                    v-if="isWithdrawalOrder(order) && canCreateWithdrawal"
                    type="button"
                    class="px-2 py-1 text-xs font-semibold rounded-md border border-rose-200 text-rose-800 bg-white hover:bg-rose-50 disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-white"
                    :disabled="!withdrawalDeleteAllowed(order)"
                    :title="withdrawalDeleteAllowed(order) ? '' : $t('main.withdrawal_detail.delete_order_forbidden_hint')"
                    @click="deleteWithdrawalOrder(order, $event)"
                  >[[ $t('main.dashboard.orders_delete') ]]</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-2 border-t border-[#eff2f5] text-xs text-cmc-muted">[[ $t('main.dashboard.showing_api_orders', { count: filteredApiOrders.length, total: apiOrders.length }) ]]</div>
      </div>
      <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_multisig_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_multisig') ]]</p>
          </div>
        </div>
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-green/10 flex items-center justify-center text-main-green shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_ai_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_ai') ]]</p>
          </div>
        </div>
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-red/10 flex items-center justify-center text-main-red shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_arbitration_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_arbitration') ]]</p>
          </div>
        </div>
      </div>
      <div class="mt-14">
        <h2 class="text-lg font-bold text-[#191d23] mb-2">[[ $t('main.dashboard.mocker_orders_title') ]]</h2>
        <p class="text-xs text-cmc-muted mb-4">[[ $t('main.dashboard.mocker_orders_subtitle') ]]</p>
        <div class="flex flex-wrap items-center gap-4 mb-6">
          <div class="flex items-center gap-2 bg-white border border-[#eff2f5] rounded-lg p-1">
            <button v-for="s in ['all','pending','funded','released','disputed']" :key="'mock-' + s" type="button" @click="statusFilter = s" :class="['px-3 py-1 rounded-md text-xs font-bold capitalize transition-all', statusFilter === s ? 'bg-main-blue text-white shadow-sm' : 'text-cmc-muted hover:bg-[#f8fafd]']">[[ $t('main.dashboard.filter_' + s) ]]</button>
          </div>
          <div class="relative flex-1 max-w-xs">
            <input v-model="searchQuery" type="text" :placeholder="$t('main.dashboard.search_placeholder')" class="w-full pl-9 pr-4 py-1.5 bg-white border border-[#eff2f5] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
          </div>
          <div class="relative flex-1 max-w-xs min-w-[140px]">
            <input v-model="participantFilter" type="text" :placeholder="$t('main.dashboard.filter_participant')" class="w-full pl-9 pr-4 py-1.5 bg-white border border-[#eff2f5] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
          </div>
          <div class="ml-auto text-xs text-cmc-muted font-medium">[[ $t('main.dashboard.showing_orders', { count: filteredEscrows.length, total: escrows.length }) ]]</div>
        </div>
        <div class="cmc-card overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="bg-gray-50">
                  <th class="cmc-table-header w-12">#</th>
                  <th class="cmc-table-header">[[ $t('main.dashboard.table_col_title') ]]</th>
                  <th class="cmc-table-header">[[ $t('main.dashboard.table_col_amount') ]]</th>
                  <th class="cmc-table-header">[[ $t('main.dashboard.table_col_status') ]]</th>
                  <th class="cmc-table-header">[[ $t('main.dashboard.table_col_created') ]]</th>
                  <th class="cmc-table-header">[[ $t('main.dashboard.table_col_participants') ]]</th>
                  <th class="cmc-table-header text-right">[[ $t('main.dashboard.table_col_action') ]]</th>
                </tr>
              </thead>
              <tbody>
                <template v-if="mockLoading">
                  <tr v-for="i in 5" :key="'mock-skeleton-' + i" class="animate-pulse">
                    <td colspan="7" class="cmc-table-cell h-16 bg-gray-50/50"></td>
                  </tr>
                </template>
                <tr v-else-if="filteredEscrows.length === 0">
                  <td colspan="7" class="cmc-table-cell text-center py-12 text-cmc-muted">[[ $t('main.dashboard.no_orders_match') ]]</td>
                </tr>
                <tr v-else v-for="(escrow, i) in filteredEscrows" :key="escrow.id" class="hover:bg-[#f8fafd] cursor-pointer transition-all duration-200 group border-b border-[#eff2f5] last:border-0" @click="goToDetail(escrow.id)">
                  <td class="cmc-table-cell text-cmc-muted font-medium">[[ i + 1 ]]</td>
                  <td class="cmc-table-cell">
                    <div class="flex items-center gap-3">
                      <div class="w-8 h-8 rounded-full bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
                        <svg class="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                      </div>
                      <div>
                        <div class="font-bold">[[ escrow.title ]]</div>
                        <div class="text-xs text-cmc-muted truncate max-w-[200px]">[[ escrow.description ]]</div>
                      </div>
                    </div>
                  </td>
                  <td class="cmc-table-cell">
                    <div class="font-bold">[[ escrow.amount ]] [[ escrow.currency ]]</div>
                    <div class="text-xs text-cmc-muted">[[ formatUsd(escrow.amount, escrow.currency) ]]</div>
                  </td>
                  <td class="cmc-table-cell">
                    <div :class="['inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider', statusClass(escrow.status)]">
                      <span :class="['w-1.5 h-1.5 rounded-full shrink-0', statusDotClass(escrow.status)]"></span>
                      [[ escrow.status ]]
                    </div>
                  </td>
                  <td class="cmc-table-cell text-cmc-muted">[[ formatDate(escrow.created_at) ]]</td>
                  <td class="cmc-table-cell">
                    <div class="flex -space-x-2">
                      <div class="w-6 h-6 rounded-full bg-indigo-500 border-2 border-white flex items-center justify-center text-[10px] text-white font-bold" title="Buyer">B</div>
                      <div class="w-6 h-6 rounded-full bg-emerald-500 border-2 border-white flex items-center justify-center text-[10px] text-white font-bold" title="Seller">S</div>
                    </div>
                  </td>
                  <td class="cmc-table-cell text-right">
                    <span class="text-[10px] font-bold text-main-blue">[[ $t('main.dashboard.view_details') ]]</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <transition name="fade">
        <div v-if="ratiosModalOpen" class="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="ratiosModalOpen = false">
          <div class="bg-white rounded-xl shadow-xl border border-[#eff2f5] w-full max-w-5xl max-h-[85vh] flex flex-col" role="dialog" aria-modal="true" @click.stop>
            <div class="flex items-center justify-between gap-4 px-4 py-3 border-b border-[#eff2f5] shrink-0">
              <h2 class="text-lg font-bold text-[#191d23]">[[ $t('main.dashboard.ratios_modal_title') ]]</h2>
              <button type="button" class="p-2 rounded-lg text-[#58667e] hover:bg-[#eff2f5] transition-colors" @click="ratiosModalOpen = false" :aria-label="$t('main.dashboard.ratios_close')">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div class="dashboard-ratios-modal-scroll overflow-auto p-4 flex-1 min-h-0">
              <div v-if="!ratiosPivot.rows.length" class="text-sm text-cmc-muted py-8 text-center">[[ $t('main.dashboard.ratios_empty') ]]</div>
              <table v-else class="dashboard-ratios-modal-table w-full text-left text-sm">
                <thead>
                  <tr class="bg-gray-50">
                    <th class="cmc-table-header dashboard-ratios-sticky-col min-w-[100px]">[[ $t('main.dashboard.ratios_col_pair') ]]</th>
                    <th v-for="eng in ratiosPivot.engines" :key="eng" class="cmc-table-header whitespace-nowrap">[[ eng ]]</th>
                    <th class="cmc-table-header whitespace-nowrap">[[ $t('main.dashboard.ratios_col_utc') ]]</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in ratiosPivot.rows" :key="ri" class="hover:bg-[#f8fafd]">
                    <td class="cmc-table-cell dashboard-ratios-sticky-col text-[#191d23] font-semibold">[[ row.base ]]/[[ row.quote ]]</td>
                    <td v-for="eng in ratiosPivot.engines" :key="eng" class="cmc-table-cell text-cmc-muted font-mono text-xs tabular-nums">[[ formatRatioCell(row.ratios[eng]) ]]</td>
                    <td class="cmc-table-cell text-cmc-muted text-xs tabular-nums whitespace-nowrap">[[ formatUtcCell(row.utcMax) ]]</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="px-4 py-3 border-t border-[#eff2f5] flex justify-end shrink-0">
              <button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg bg-main-blue text-white hover:opacity-90 transition-opacity" @click="ratiosModalOpen = false">[[ $t('main.dashboard.ratios_close') ]]</button>
            </div>
          </div>
        </div>
      </transition>
      <transition name="fade">
        <div v-if="driftDetailModalOpen && driftDetailOrder" class="fixed inset-0 z-[95] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="closeDriftDetailModal">
          <div class="bg-white rounded-xl shadow-xl border border-[#eff2f5] w-full max-w-lg max-h-[85vh] flex flex-col" role="dialog" aria-modal="true" @click.stop>
            <div class="flex items-center justify-between gap-4 px-4 py-3 border-b border-[#eff2f5] shrink-0">
              <h2 class="text-lg font-bold text-[#191d23] pr-2">[[ $t('main.dashboard.drift_modal_title') ]]</h2>
              <button type="button" class="p-2 rounded-lg text-[#58667e] hover:bg-[#eff2f5] transition-colors shrink-0" @click="closeDriftDetailModal" :aria-label="$t('main.dashboard.drift_modal_close')">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div class="overflow-auto p-4 flex-1 min-h-0 space-y-5">
              <p class="text-xs text-[#58667e] leading-relaxed">[[ $t('main.dashboard.drift_modal_intro') ]]</p>
              <div class="text-xs text-[#58667e]">
                <span class="font-semibold text-[#191d23]">[[ orderRowTitle(driftDetailOrder) ]]</span>
                <span v-if="driftDetailOrder.payload && driftDetailOrder.payload.tron_address" class="font-mono break-all block mt-1">[[ driftDetailOrder.payload.tron_address ]]</span>
              </div>
              <div v-if="driftModalShowOwnersBlock" class="rounded-xl border border-violet-100 bg-violet-50/90 p-3 space-y-2">
                <h3 class="text-xs font-bold text-violet-900 uppercase tracking-wide">[[ $t('main.dashboard.drift_modal_section_owners') ]]</h3>
                <p class="text-xs text-[#58667e] leading-relaxed">[[ $t('main.dashboard.drift_modal_owners_comment') ]]</p>
                <dl class="mt-2 space-y-2 text-xs">
                  <div v-if="(driftDetailOrder.payload.owners_only_in_meta || []).length">
                    <dt class="font-semibold text-[#191d23]">[[ $t('main.dashboard.drift_modal_owners_diff_meta') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.owners_only_in_meta) ]]</dd>
                  </div>
                  <div v-if="(driftDetailOrder.payload.owners_only_in_space || []).length">
                    <dt class="font-semibold text-[#191d23]">[[ $t('main.dashboard.drift_modal_owners_diff_space') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.owners_only_in_space) ]]</dd>
                  </div>
                  <div>
                    <dt class="font-semibold text-[#58667e]">[[ $t('main.dashboard.drift_modal_snapshot_meta_owners') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.meta_owners) ]]</dd>
                  </div>
                  <div>
                    <dt class="font-semibold text-[#58667e]">[[ $t('main.dashboard.drift_modal_snapshot_space_admins') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.space_tron_admins) ]]</dd>
                  </div>
                </dl>
              </div>
              <div v-if="driftModalShowActorsBlock" class="rounded-xl border border-violet-100 bg-violet-50/90 p-3 space-y-2">
                <h3 class="text-xs font-bold text-violet-900 uppercase tracking-wide">[[ $t('main.dashboard.drift_modal_section_actors') ]]</h3>
                <p class="text-xs text-[#58667e] leading-relaxed">[[ $t('main.dashboard.drift_modal_actors_comment') ]]</p>
                <dl class="mt-2 space-y-2 text-xs">
                  <div v-if="driftModalActorsOnlyInMetaArr.length">
                    <dt class="font-semibold text-[#191d23]">[[ $t('main.dashboard.drift_modal_actors_diff_meta') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftModalActorsOnlyInMetaArr) ]]</dd>
                  </div>
                  <div v-if="driftModalActorsOnlyInSpaceArr.length">
                    <dt class="font-semibold text-[#191d23]">[[ $t('main.dashboard.drift_modal_actors_diff_space') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftModalActorsOnlyInSpaceArr) ]]</dd>
                  </div>
                  <div>
                    <dt class="font-semibold text-[#58667e]">[[ $t('main.dashboard.drift_modal_snapshot_meta_actors') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.actors) ]]</dd>
                  </div>
                  <div>
                    <dt class="font-semibold text-[#58667e]">[[ $t('main.dashboard.drift_modal_snapshot_space_signers') ]]</dt>
                    <dd class="font-mono text-[11px] text-[#30384a] break-all mt-0.5">[[ driftAddrList(driftDetailOrder.payload.space_tron_owner_operator) ]]</dd>
                  </div>
                </dl>
              </div>
            </div>
            <div class="px-4 py-3 border-t border-[#eff2f5] flex flex-wrap justify-end gap-2 shrink-0">
              <button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg border border-[#eff2f5] bg-white text-[#191d23] hover:bg-[#f8fafd] disabled:opacity-50 disabled:cursor-not-allowed transition-colors" :disabled="dashboardMultisigFetching" @click="beginDashboardMultisigReconfigureFromDrift">[[ $t('main.dashboard.drift_modal_edit_multisig') ]]</button>
              <button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg bg-main-blue text-white hover:opacity-90 transition-opacity" @click="closeDriftDetailModal">[[ $t('main.dashboard.drift_modal_close') ]]</button>
            </div>
          </div>
        </div>
      </transition>
      <multisig-config-modal
        :show="showDashboardMultisigWizard"
        :wallet="dashboardMultisigWizardWallet"
        @close="closeDashboardMultisigWizard"
        @saved="onDashboardMultisigConfigSaved"
      ></multisig-config-modal>
      <withdrawal-order-modal
        :show="showWithdrawalModal"
        @close="closeWithdrawalModal"
      ></withdrawal-order-modal>
      <withdrawal-order-detail-modal
        :show="showWithdrawalDetailModal"
        :order="withdrawalDetailOrder"
        :can-manage="canCreateWithdrawal"
        @close="closeWithdrawalDetailModal"
        @deleted="onWithdrawalDetailDeleted"
        @updated="onWithdrawalDetailUpdated"
      ></withdrawal-order-detail-modal>
    </div>
    `
});
})();
