/**
 * Модалка деталей заявки на вывод: read-only, удаление, подписание (как /o/{token}), сброс off-chain для multisig.
 */
(function() {
    function authHeadersMain() {
        var h = { Accept: 'application/json' };
        var key = (typeof window !== 'undefined' && window.main_auth_token_key) ? window.main_auth_token_key : 'main_auth_token';
        var token = null;
        try {
            token = localStorage.getItem(key);
        } catch (e) {}
        if (token) h.Authorization = 'Bearer ' + token;
        return h;
    }

    Vue.component('withdrawal-order-detail-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false },
            order: { type: Object, default: null },
            canManage: { type: Boolean, default: false },
            /** Встроенная карточка на /o/{token} без оверлея и кнопки «Закрыть». */
            embedded: { type: Boolean, default: false },
            /** false на публичной странице (без JWT для ramp / signatory-tron-labels). */
            fetchLabels: { type: Boolean, default: true }
        },
        data: function() {
            return {
                signContext: null,
                contextLoading: false,
                contextError: null,
                signBusy: false,
                signError: null,
                clearBusy: false,
                rampWalletByTron: {},
                signatoryTronLabelByAddress: {},
                /** Интервал опроса статуса на /o/{token} (embedded). */
                statusPollTimer: null
            };
        },
        computed: {
            p: function() {
                return (this.order && this.order.payload) ? this.order.payload : {};
            },
            /** Источник / назначение: сначала публичный контекст, иначе payload заявки. */
            displaySourceAddr: function() {
                var c = this.signContext;
                if (c && (c.tron_address || '').trim()) return (c.tron_address || '').trim();
                return String((this.p.tron_address || '')).trim();
            },
            displayDestAddr: function() {
                var c = this.signContext;
                if (c && (c.destination_address || '').trim()) return (c.destination_address || '').trim();
                return String((this.p.destination_address || '')).trim();
            },
            displayPurpose: function() {
                var c = this.signContext;
                if (c && c.purpose != null && String(c.purpose).trim()) return String(c.purpose).trim();
                return String((this.p.purpose || '')).trim();
            },
            signToken: function() {
                if (!this.order) return '';
                var dk = String((this.order.dedupe_key || '')).trim();
                var prefix = 'withdrawal:';
                if (dk.indexOf(prefix) !== 0) return '';
                return dk.slice(prefix.length).trim() || '';
            },
            walletRole: function() {
                var c = this.signContext;
                if (c && (c.wallet_role || '').trim()) return String(c.wallet_role).trim();
                return String((this.p.wallet_role || '')).trim();
            },
            isMultisig: function() {
                return this.walletRole === 'multisig';
            },
            thresholdN: function() {
                var c = this.signContext;
                var raw = c && c.threshold_n != null ? c.threshold_n : this.p.threshold_n;
                var n = parseInt(raw, 10);
                return isFinite(n) && n > 0 ? n : 1;
            },
            thresholdM: function() {
                var c = this.signContext;
                var raw = c && c.threshold_m != null ? c.threshold_m : this.p.threshold_m;
                var m = parseInt(raw, 10);
                return isFinite(m) && m > 0 ? m : this.thresholdN;
            },
            signatures: function() {
                var s = this.signContext && this.signContext.signatures;
                return Array.isArray(s) ? s : [];
            },
            uniqueSignedAddresses: function() {
                var seen = {};
                var out = [];
                this.signatures.forEach(function(row) {
                    var a = String((row && row.signer_address) || '').trim();
                    if (a && !seen[a]) {
                        seen[a] = true;
                        out.push(a);
                    }
                });
                return out;
            },
            signedAddressSet: function() {
                var o = {};
                this.uniqueSignedAddresses.forEach(function(a) {
                    o[a] = true;
                });
                return o;
            },
            actorsList: function() {
                var raw = this.signContext && this.signContext.actors_snapshot;
                if (Array.isArray(raw) && raw.length) return raw;
                var pr = this.p.actors_snapshot;
                return Array.isArray(pr) ? pr : [];
            },
            pendingActors: function() {
                var self = this;
                return this.actorsList.map(function(a) {
                    return String(a || '').trim();
                }).filter(Boolean).filter(function(a) {
                    return !self.signedAddressSet[a];
                });
            },
            liveStatus: function() {
                if (this.signContext && this.signContext.status) return String(this.signContext.status).trim();
                return String((this.p.status || '')).trim();
            },
            amountDisplay: function() {
                var S = window.EscrowWithdrawalSign;
                var src = this.signContext || this.p;
                if (S && S.formatWithdrawalDisplayAmount) {
                    var fake = {
                        amount_raw: src.amount_raw != null ? src.amount_raw : this.p.amount_raw,
                        token: src.token || this.p.token || {}
                    };
                    return S.formatWithdrawalDisplayAmount(fake);
                }
                return '—';
            },
            canSign: function() {
                if (!this.signToken || !window.EscrowWithdrawalSign) return false;
                var st = this.liveStatus;
                if (st !== 'awaiting_signatures' && st !== 'ready_to_broadcast') return false;
                if (st === 'confirmed' || st === 'failed' || st === 'broadcast_submitted') return false;
                return true;
            },
            canClearOffchain: function() {
                if (!this.isMultisig || !this.canManage || !this.signToken) return false;
                var st = this.liveStatus;
                if (st !== 'awaiting_signatures' && st !== 'ready_to_broadcast') return false;
                if (this.signatures.length > 0) return true;
                return st === 'ready_to_broadcast';
            },
            thresholdLabel: function() {
                return this.$t('main.withdrawal_detail.multisig_threshold', {
                    n: this.thresholdN,
                    m: this.thresholdM
                });
            },
            progressLabel: function() {
                return this.$t('main.withdrawal_detail.multisig_signed_progress', {
                    signed: this.uniqueSignedAddresses.length,
                    needed: this.thresholdN
                });
            },
            broadcastTxIdRaw: function() {
                var c = this.signContext;
                var fromCtx = c && c.broadcast_tx_id != null ? String(c.broadcast_tx_id).trim() : '';
                if (fromCtx) return fromCtx;
                return String((this.p.broadcast_tx_id || '')).trim();
            },
            broadcastTxExplorerUrl: function() {
                var tx = this.broadcastTxIdRaw;
                if (!tx || !window.EscrowWithdrawalSign || typeof window.EscrowWithdrawalSign.tronTxExplorerUrl !== 'function') {
                    return '';
                }
                return window.EscrowWithdrawalSign.tronTxExplorerUrl(tx);
            },
            showBroadcastTxLink: function() {
                if (!this.broadcastTxExplorerUrl) return false;
                var st = this.liveStatus;
                return st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed';
            },
            /** Удаление только до отправки tx в сеть (не broadcast_submitted / confirmed / failed). */
            canDeleteWithdrawal: function() {
                var st = this.liveStatus;
                if (st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed') return false;
                return true;
            },
            withdrawalStatusLabel: function() {
                var st = this.liveStatus;
                if (!st) return '\u2014';
                var key = 'main.dashboard.withdrawal_status_' + st;
                var t = this.$t(key);
                return (t && t !== key) ? t : st;
            },
            withdrawalStatusBadgeClass: function() {
                var st = this.liveStatus;
                if (st === 'confirmed') {
                    return 'bg-main-green/12 text-main-green border border-main-green/25';
                }
                if (st === 'failed') {
                    return 'bg-main-red/10 text-main-red border border-main-red/25';
                }
                if (st === 'broadcast_submitted' || st === 'awaiting_signatures' || st === 'ready_to_broadcast') {
                    return 'bg-main-blue/12 text-main-blue border border-main-blue/25';
                }
                if (st) {
                    return 'bg-main-blue/10 text-main-blue border border-main-blue/20';
                }
                return 'bg-gray-100 text-[#58667e] border border-[#eff2f5]';
            },
            withdrawalStatusSpinnerVisible: function() {
                var st = this.liveStatus;
                if (!st) return false;
                if (st === 'confirmed' || st === 'failed') return false;
                return true;
            },
            withdrawalStatusErrorDetail: function() {
                if (this.liveStatus !== 'failed') return '';
                var c = this.signContext;
                var fromCtx = c && c.last_error != null ? String(c.last_error).trim() : '';
                if (fromCtx) return fromCtx;
                return String((this.p.last_error || '')).trim();
            }
        },
        watch: {
            show: {
                immediate: true,
                handler: function(v) {
                    if (v) {
                        this.contextError = null;
                        this.signError = null;
                        if (this.fetchLabels) this.fetchWalletLabelMaps();
                        else {
                            this.rampWalletByTron = {};
                            this.signatoryTronLabelByAddress = {};
                        }
                        this.refreshContext();
                        if (this.embedded) this.startStatusPoll();
                    } else {
                        this.stopStatusPoll();
                        if (!this.embedded) {
                            this.signContext = null;
                            this.rampWalletByTron = {};
                            this.signatoryTronLabelByAddress = {};
                        }
                    }
                }
            },
            order: function() {
                if (this.show) this.refreshContext();
            }
        },
        beforeDestroy: function() {
            this.stopStatusPoll();
        },
        methods: {
            startStatusPoll: function() {
                if (!this.embedded || !this.show || !this.signToken) return;
                this.stopStatusPoll();
                var self = this;
                this.statusPollTimer = setInterval(function() {
                    if (!self.embedded || !self.show || !self.signToken) {
                        self.stopStatusPoll();
                        return;
                    }
                    self.refreshContext(true);
                }, 5000);
            },
            stopStatusPoll: function() {
                if (this.statusPollTimer != null) {
                    clearInterval(this.statusPollTimer);
                    this.statusPollTimer = null;
                }
            },
            close: function() {
                if (this.embedded) return;
                this.$emit('close');
            },
            fetchWalletLabelMaps: function() {
                var self = this;
                if (!self.fetchLabels) {
                    self.rampWalletByTron = {};
                    self.signatoryTronLabelByAddress = {};
                    return;
                }
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) {
                    self.rampWalletByTron = {};
                    self.signatoryTronLabelByAddress = {};
                    return;
                }
                var h = authHeadersMain();
                var wUrl = '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets';
                var lUrl = '/v1/spaces/' + encodeURIComponent(space) + '/signatory-tron-labels';
                Promise.all([
                    fetch(wUrl, { method: 'GET', headers: h, credentials: 'include' })
                        .then(function(r) { return r.ok ? r.json() : null; })
                        .catch(function() { return null; }),
                    fetch(lUrl, { method: 'GET', headers: h, credentials: 'include' })
                        .then(function(r) { return r.ok ? r.json() : null; })
                        .catch(function() { return null; })
                ]).then(function(pair) {
                    var byTron = {};
                    var dataW = pair[0];
                    var items = (dataW && dataW.items && Array.isArray(dataW.items)) ? dataW.items : [];
                    items.forEach(function(w) {
                        var t = (w.tron_address || '').trim();
                        if (t) byTron[t] = w;
                    });
                    self.rampWalletByTron = byTron;
                    var byLab = {};
                    var dataL = pair[1];
                    var rows = (dataL && dataL.items && Array.isArray(dataL.items)) ? dataL.items : [];
                    rows.forEach(function(row) {
                        var addr = (row.tron_address || '').trim();
                        var nick = (row.nickname || '').trim();
                        if (addr && nick) byLab[addr] = nick;
                    });
                    self.signatoryTronLabelByAddress = byLab;
                });
            },
            refreshContext: function(silent) {
                var self = this;
                silent = !!silent;
                var tok = self.signToken;
                if (!silent) self.contextError = null;
                if (!tok) {
                    self.signContext = null;
                    return;
                }
                var S = window.EscrowWithdrawalSign;
                if (!S || !S.fetchSignContext) {
                    if (!silent) self.contextError = self.$t('main.withdrawal_detail.load_error');
                    return;
                }
                if (!silent) self.contextLoading = true;
                S.fetchSignContext(tok)
                    .then(function(data) {
                        self.signContext = data;
                        if (self.embedded && data) {
                            var st = String((data.status || '')).trim();
                            if (st === 'confirmed' || st === 'failed') self.stopStatusPoll();
                        }
                    })
                    .catch(function() {
                        if (!silent) {
                            self.signContext = null;
                            self.contextError = self.$t('main.withdrawal_detail.load_error');
                        }
                    })
                    .finally(function() {
                        if (!silent) self.contextLoading = false;
                    });
            },
            shortenAddr: function(addr) {
                var s = String(addr || '').trim();
                if (!s) return '—';
                if (s.length <= 22) return s;
                return s.slice(0, 10) + '…' + s.slice(-8);
            },
            labelForTron: function(addr) {
                var a = String(addr || '').trim();
                if (!a) return '';
                var w = this.rampWalletByTron[a];
                if (w && (w.name || '').trim()) return (w.name || '').trim();
                var lab = this.signatoryTronLabelByAddress[a];
                if (lab) return lab;
                return '';
            },
            runSign: function() {
                var self = this;
                var S = window.EscrowWithdrawalSign;
                var tok = self.signToken;
                self.signError = null;
                if (!S || !tok || !self.signContext) return;
                self.signBusy = true;
                S.signAndBroadcast(tok, self.signContext)
                    .then(function() {
                        self.refreshContext();
                        self.$emit('updated');
                    })
                    .catch(function(e) {
                        self.signError = String(e && e.message ? e.message : e);
                    })
                    .finally(function() {
                        self.signBusy = false;
                    });
            },
            clearOffchain: function() {
                var self = this;
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space || !self.order || self.order.id == null) return;
                function runClear() {
                    self.clearBusy = true;
                    fetch(
                        '/v1/spaces/' + encodeURIComponent(space) + '/orders/' + encodeURIComponent(self.order.id) + '/withdrawal-signatures',
                        { method: 'DELETE', headers: authHeadersMain(), credentials: 'include' }
                    )
                        .then(function(res) {
                            if (!res.ok) throw new Error('HTTP ' + res.status);
                            return res.json();
                        })
                        .then(function() {
                            self.fetchWalletLabelMaps();
                            self.refreshContext();
                            self.$emit('updated');
                        })
                        .catch(function() {
                            if (typeof window.showAlert === 'function') {
                                window.showAlert({
                                    title: self.$t('main.dialog.error_title'),
                                    message: self.$t('main.withdrawal_detail.load_error')
                                });
                            }
                        })
                        .finally(function() {
                            self.clearBusy = false;
                        });
                }
                if (typeof window.showConfirm === 'function') {
                    window.showConfirm({
                        title: self.$t('main.withdrawal_detail.clear_signatures_confirm_title'),
                        message: self.$t('main.withdrawal_detail.clear_signatures_confirm'),
                        danger: true,
                        onConfirm: runClear
                    });
                } else {
                    if (confirm(self.$t('main.withdrawal_detail.clear_signatures_confirm'))) runClear();
                }
            },
            deleteOrder: function() {
                var self = this;
                if (!self.canManage || !self.canDeleteWithdrawal || !self.order || self.order.id == null) return;
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return;
                function runDelete() {
                    fetch('/v1/spaces/' + encodeURIComponent(space) + '/orders/' + encodeURIComponent(self.order.id), {
                        method: 'DELETE',
                        headers: authHeadersMain(),
                        credentials: 'include'
                    })
                        .then(function(res) {
                            if (res.ok) {
                                self.$emit('deleted');
                                self.close();
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
                    if (confirm(self.$t('main.dashboard.orders_delete_confirm'))) runDelete();
                }
            }
        },
        template: '' +
            '<transition name="fade">' +
            '<div v-if="show && order">' +
            '<div' +
            ' :class="embedded ? \'\' : \'fixed inset-0 z-[95] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm\'"' +
            ' @click.self="embedded ? undefined : close()"' +
            '>' +
            '<div' +
            ' :class="embedded ? \'bg-white rounded-xl shadow-sm border border-[#eff2f5] w-full flex flex-col\' : \'bg-white rounded-xl shadow-xl border border-[#eff2f5] w-full max-w-xl max-h-[92vh] flex flex-col\'"' +
            ' class="flex flex-col"' +
            ' role="dialog" :aria-modal="!embedded" @click.stop' +
            '>' +
            '<div class="flex items-center justify-between gap-4 px-4 py-3 border-b border-[#eff2f5] shrink-0">' +
            '<h2 class="text-lg font-bold text-[#191d23]">[[ embedded ? $t(\'main.order_sign.title\') : $t(\'main.withdrawal_detail.title\') ]]</h2>' +
            '<button v-if="!embedded" type="button" class="p-2 rounded-lg text-[#58667e] hover:bg-[#eff2f5]" @click="close" :aria-label="$t(\'main.withdrawal_detail.close\')">' +
            '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>' +
            '</button></div>' +
            '<div class="overflow-auto p-4 flex-1 min-h-0 space-y-4 text-sm">' +
            '<p v-if="!signToken" class="text-amber-800 text-xs rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">[[ $t(\'main.withdrawal_detail.no_sign_token\') ]]</p>' +
            '<p v-if="contextLoading" class="text-cmc-muted text-xs">[[ $t(\'main.withdrawal_detail.context_loading\') ]]</p>' +
            '<p v-if="contextError" class="text-main-red text-xs">[[ contextError ]]</p>' +
            '<p v-if="signError" class="text-main-red text-xs">[[ signError ]]</p>' +
            '<dl class="space-y-2 text-xs">' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_wallet_role\') ]]</dt>' +
            '<dd class="text-[#191d23] font-medium">[[ isMultisig ? $t(\'main.withdrawal_detail.role_multisig\') : $t(\'main.withdrawal_detail.role_external\') ]]</dd></div>' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_status\') ]]</dt>' +
            '<dd class="space-y-2 min-w-0">' +
            '<div v-if="liveStatus" class="inline-flex items-center gap-1.5 max-w-full rounded-md pl-2 pr-1.5 py-1" :class="withdrawalStatusBadgeClass">' +
            '<svg v-if="liveStatus === \'confirmed\'" class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>' +
            '<svg v-else-if="liveStatus === \'failed\'" class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>' +
            '<span class="text-[10px] font-bold uppercase tracking-wide truncate">[[ withdrawalStatusLabel ]]</span>' +
            '<svg v-if="withdrawalStatusSpinnerVisible" class="w-3.5 h-3.5 shrink-0 animate-spin opacity-90" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>' +
            '</div>' +
            '<span v-else class="text-[#58667e] text-xs">\u2014</span>' +
            '<p v-if="withdrawalStatusErrorDetail" class="text-main-red text-xs leading-snug rounded-lg bg-main-red/5 border border-main-red/15 px-2.5 py-1.5 break-words">[[ withdrawalStatusErrorDetail ]]</p>' +
            '</dd></div>' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_amount\') ]]</dt>' +
            '<dd class="text-[#191d23] font-mono">[[ amountDisplay ]]</dd></div>' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_purpose\') ]]</dt>' +
            '<dd class="text-[#191d23] text-xs leading-relaxed break-words whitespace-pre-wrap">[[ displayPurpose || \'\u2014\' ]]</dd></div>' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_source\') ]]</dt>' +
            '<dd class="text-[#191d23] text-xs leading-relaxed break-words" :title="displaySourceAddr">' +
            '<span class="font-semibold text-[#30384a]" v-if="labelForTron(displaySourceAddr)">[[ labelForTron(displaySourceAddr) ]]</span>' +
            '<span v-if="labelForTron(displaySourceAddr)" class="text-[#58667e] mx-1">\u2014</span>' +
            '<span class="font-mono">[[ shortenAddr(displaySourceAddr) ]]</span></dd></div>' +
            '<div class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_destination\') ]]</dt>' +
            '<dd class="text-[#191d23] text-xs leading-relaxed break-words" :title="displayDestAddr">' +
            '<span class="font-semibold text-[#30384a]" v-if="labelForTron(displayDestAddr)">[[ labelForTron(displayDestAddr) ]]</span>' +
            '<span v-if="labelForTron(displayDestAddr)" class="text-[#58667e] mx-1">\u2014</span>' +
            '<span class="font-mono">[[ shortenAddr(displayDestAddr) ]]</span></dd></div>' +
            '<div v-if="showBroadcastTxLink" class="flex flex-col gap-0.5"><dt class="text-[#58667e] font-semibold">[[ $t(\'main.withdrawal_detail.field_transaction\') ]]</dt>' +
            '<dd class="min-w-0">' +
            '<a :href="broadcastTxExplorerUrl" target="_blank" rel="noopener noreferrer"' +
            ' :aria-label="$t(\'main.dashboard.withdrawal_tx_explorer\')"' +
            ' class="inline-flex items-center gap-1 text-xs font-semibold text-main-green hover:text-emerald-700 rounded-md px-1.5 py-0.5 bg-main-green/12 hover:bg-main-green/20 transition-colors">' +
            '<svg class="w-3.5 h-3.5 shrink-0 text-main-green" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true">' +
            '<path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3z"/>' +
            '<path d="M12 12 4 7.5M12 12l8-4.5M12 12v9"/>' +
            '</svg>' +
            '<span>[[ $t(\'main.dashboard.withdrawal_tx_explorer_short\') ]]</span>' +
            '</a></dd></div>' +
            '</dl>' +
            '<div v-if="isMultisig" class="rounded-xl border border-[#eff2f5] bg-[#f8fafd] p-3 space-y-2">' +
            '<p class="text-xs font-bold text-[#191d23] uppercase tracking-wide">[[ thresholdLabel ]]</p>' +
            '<div class="rounded-lg border border-sky-100 bg-sky-50/80 p-3 space-y-2">' +
            '<p class="text-xs font-semibold text-sky-900">[[ $t(\'main.withdrawal_detail.multisig_offchain_title\') ]]</p>' +
            '<p class="text-sm font-mono text-sky-950">[[ progressLabel ]]</p>' +
            '<div v-if="uniqueSignedAddresses.length">' +
            '<p class="text-[11px] font-semibold text-[#58667e]">[[ $t(\'main.withdrawal_detail.multisig_signed_list\') ]]</p>' +
            '<ul class="list-disc list-inside text-xs font-mono text-[#30384a] space-y-0.5">' +
            '<li v-for="(a, idx) in uniqueSignedAddresses" :key="\'sig-\' + idx" class="text-[#30384a] text-xs leading-relaxed break-words" :title="a">' +
            '<span class="font-semibold" v-if="labelForTron(a)">[[ labelForTron(a) ]]</span><span v-if="labelForTron(a)" class="text-[#58667e] mx-1">\u2014</span><span class="font-mono">[[ shortenAddr(a) ]]</span></li>' +
            '</ul></div>' +
            '<div v-if="pendingActors.length">' +
            '<p class="text-[11px] font-semibold text-[#58667e] mt-2">[[ $t(\'main.withdrawal_detail.multisig_pending_list\') ]]</p>' +
            '<ul class="list-disc list-inside text-xs font-mono text-[#30384a] space-y-0.5">' +
            '<li v-for="(a, idx) in pendingActors" :key="\'pend-\' + idx" class="text-xs leading-relaxed break-words" :title="a">' +
            '<span class="font-semibold" v-if="labelForTron(a)">[[ labelForTron(a) ]]</span><span v-if="labelForTron(a)" class="text-[#58667e] mx-1">\u2014</span><span class="font-mono">[[ shortenAddr(a) ]]</span></li>' +
            '</ul></div></div></div>' +
            '</div>' +
            '<div class="px-4 py-3 border-t border-[#eff2f5] flex flex-wrap justify-end gap-2 shrink-0">' +
            '<button v-if="canManage" type="button" class="px-3 py-2 text-sm font-semibold rounded-lg border border-rose-200 text-rose-800 bg-white hover:bg-rose-50 disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-white" :disabled="!canDeleteWithdrawal" :title="canDeleteWithdrawal ? \'\' : $t(\'main.withdrawal_detail.delete_order_forbidden_hint\')" @click="deleteOrder">[[ $t(\'main.withdrawal_detail.delete_order\') ]]</button>' +
            '<button v-if="canClearOffchain" type="button" class="px-3 py-2 text-sm font-semibold rounded-lg border border-amber-200 text-amber-900 bg-white hover:bg-amber-50 disabled:opacity-50" :disabled="clearBusy" @click="clearOffchain">[[ $t(\'main.withdrawal_detail.clear_signatures\') ]]</button>' +
            '<button v-if="canSign" type="button" class="px-4 py-2 text-sm font-semibold rounded-lg bg-main-blue text-white hover:opacity-90 disabled:opacity-50" :disabled="signBusy" @click="runSign">[[ $t(\'main.withdrawal_detail.sign_button\') ]]</button>' +
            '<button v-if="!embedded" type="button" class="px-4 py-2 text-sm font-semibold rounded-lg border border-[#eff2f5] bg-white text-[#191d23] hover:bg-[#f8fafd]" @click="close">[[ $t(\'main.withdrawal_detail.close\') ]]</button>' +
            '</div></div></div></div>' +
            '</transition>'
    });
})();
