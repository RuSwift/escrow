/**
 * Модалка настройки Multisig (подписанты, пороги, обновление статуса).
 * Подключать после vue.min.js, до my_business.js.
 */
(function() {
    Vue.component('multisig-config-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false },
            wallet: { type: Object, default: null }
        },
        data: function() {
            return {
                localWallet: null,
                participants: [],
                selectedAddresses: [],
                wizardN: 2,
                wizardM: 2,
                thresholdPreset: 'two_of_n',
                participantsLoading: false,
                saving: false,
                refreshing: false,
                silentMaintenanceRefreshing: false,
                error: null,
                wizardUiForceStep: null,
                multisigPollTimerId: null,
                tronLinkFundingBusy: false,
                tronLinkFundError: null,
                multisigFundingAddressCopied: false,
                multisigFundingAddressCopyTimerId: null
            };
        },
        watch: {
            show: function(v) {
                if (v && this.wallet) {
                    this.bootstrap();
                } else if (!v) {
                    this.teardown();
                }
            },
            wallet: function() {
                if (this.show && this.wallet) {
                    this.bootstrap();
                }
            },
            multisigWizardDisplayStep: function(to, from) {
                if (to === 2 && this.show) {
                    if (from !== 2) {
                        this.refreshMultisigWizard({ silent: true });
                    }
                    this.startMultisigFundingPoll();
                } else {
                    this.stopMultisigFundingPoll();
                }
            }
        },
        computed: {
            multisigWizardBackendStep: function() {
                var st = (this.localWallet && this.localWallet.multisig_setup_status)
                    ? String(this.localWallet.multisig_setup_status)
                    : '';
                if (st === 'reconfigure') return 1;
                if (st === 'awaiting_funding') return 2;
                if (
                    st === 'ready_for_permissions'
                    || st === 'permissions_submitted'
                    || st === 'failed'
                    || st === 'active'
                ) {
                    return 3;
                }
                return 1;
            },
            multisigWizardDisplayStep: function() {
                if (!this.localWallet) return 1;
                if (this.localWallet.multisig_setup_status === 'active') return 3;
                if (this.wizardUiForceStep === 1) return 1;
                return this.multisigWizardBackendStep;
            },
            multisigWizardStepCaption: function() {
                var n = this.multisigWizardDisplayStep;
                var k = 'main.my_business.multisig_wizard_step' + n + '_caption';
                var t = this.$t(k);
                return t !== k ? t : '';
            },
            multisigFundingShortfallTrx: function() {
                var m = (this.localWallet && this.localWallet.multisig_setup_meta) || {};
                var minS = Number(m.min_trx_sun);
                var balS = Number(m.last_trx_balance_sun);
                if (!isFinite(minS)) return '';
                if (!isFinite(balS)) balS = 0;
                var d = Math.max(0, minS - balS);
                if (d <= 0) return '';
                return (d / 1e6).toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                    minimumFractionDigits: 2
                });
            },
            multisigMinTrxKnown: function() {
                var m = (this.localWallet && this.localWallet.multisig_setup_meta) || {};
                var minS = Number(m.min_trx_sun);
                return isFinite(minS) && minS > 0;
            },
            multisigFundingMinRefinedByMaintenance: function() {
                var m = (this.localWallet && this.localWallet.multisig_setup_meta) || {};
                return !!m.last_chain_check_at;
            },
            multisigReconfigureCancelPending: function() {
                var rw = this.localWallet;
                if (!rw) return false;
                var meta = rw.multisig_setup_meta || {};
                if (!meta.reconfigure_previous_status) return false;
                var st = String(rw.multisig_setup_status || '');
                return st === 'reconfigure'
                    || st === 'awaiting_funding'
                    || st === 'ready_for_permissions'
                    || st === 'permissions_submitted';
            },
            multisigWizardReconfigureNoopSuccess: function() {
                var rw = this.localWallet;
                if (!rw || rw.multisig_setup_status !== 'active') return false;
                return !!(rw.multisig_setup_meta || {}).reconfigure_unchanged;
            },
            multisigWizardManagerSignerRows: function() {
                var self = this;
                var rw = this.localWallet;
                var main = rw && rw.tron_address ? String(rw.tron_address).trim() : '';
                var ownerTron = (typeof window !== 'undefined' && window.__SPACE_OWNER_TRON__)
                    ? String(window.__SPACE_OWNER_TRON__).trim() : '';
                var managers = [];
                (this.participants || []).forEach(function(p) {
                    if ((p.blockchain || '').toLowerCase() !== 'tron') return;
                    if (p.is_blocked) return;
                    if (!self.isParticipantMultisigManager(p)) return;
                    var addr = (p.wallet_address || '').trim();
                    if (!addr || addr === main) return;
                    if (ownerTron && addr === ownerTron) return;
                    managers.push({
                        kind: 'participant',
                        address: addr,
                        nickname: (p.nickname || '').trim(),
                        roles: Array.isArray(p.roles) ? p.roles : (p.roles ? [p.roles] : []),
                        is_verified: !!p.is_verified,
                        selectable: !!p.is_verified
                    });
                });
                managers.sort(function(a, b) {
                    if (a.selectable !== b.selectable) return a.selectable ? -1 : 1;
                    return (a.nickname || a.address).localeCompare(b.nickname || b.address, undefined, { sensitivity: 'base' });
                });
                var out = [];
                if (ownerTron && ownerTron !== main) {
                    out.push({
                        kind: 'space_owner',
                        address: ownerTron,
                        nickname: '',
                        roles: [],
                        is_verified: true,
                        selectable: true
                    });
                }
                return out.concat(managers);
            },
            multisigWizardActorCount: function() {
                var rw = this.localWallet;
                if (!rw) return 0;
                var main = (rw.tron_address || '').trim();
                if (!main) return 0;
                var allowed = this.multisigWizardSelectableManagerAddressSet();
                var extra = (this.selectedAddresses || [])
                    .map(function(a) { return (a || '').trim(); })
                    .filter(Boolean)
                    .filter(function(a) { return allowed[a] && a !== main; });
                var seen = {};
                return extra.filter(function(a) {
                    if (seen[a]) return false;
                    seen[a] = true;
                    return true;
                }).length;
            },
            multisigWizardSignerRowsTooFew: function() {
                return (this.multisigWizardManagerSignerRows || []).length < 2;
            },
            multisigWizardManualNInvalid: function() {
                if (this.thresholdPreset !== 'manual') return false;
                var Lf = this.multisigWizardActorCount;
                var n = parseInt(this.wizardN, 10);
                var m = parseInt(this.wizardM, 10);
                if (Lf < 1) return false;
                if (isNaN(n)) return false;
                if (n < 1 || n > Lf) return true;
                return !isNaN(m) && n > m;
            },
            multisigWizardManualMInvalid: function() {
                if (this.thresholdPreset !== 'manual') return false;
                var Lf = this.multisigWizardActorCount;
                var m = parseInt(this.wizardM, 10);
                if (Lf < 1) return false;
                return isNaN(m) || m < 1 || m !== Lf;
            },
            multisigWizardSaveDisabled: function() {
                if (this.participantsLoading) return true;
                var allowed = this.multisigWizardSelectableManagerAddressSet();
                var allowedK = Object.keys(allowed);
                var extra = (this.selectedAddresses || [])
                    .map(function(a) { return (a || '').trim(); })
                    .filter(Boolean);
                if (allowedK.length > 0 && extra.length < 1) return true;
                if (this.multisigWizardSignerRowsTooFew) return true;
                var Lfull = this.multisigWizardActorCount;
                var p = this.thresholdPreset;
                if (p === 'two_of_n' && Lfull < 2) return true;
                if (p === 'manual') {
                    var n = parseInt(this.wizardN, 10);
                    var m = parseInt(this.wizardM, 10);
                    if (isNaN(n) || isNaN(m) || n < 1 || m < 1 || m !== Lfull || n > m) return true;
                }
                return false;
            }
        },
        methods: {
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
            formatSunAsTrx: function(sun) {
                var n = Number(sun);
                if (!isFinite(n)) return '—';
                return (n / 1e6).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            },
            multisigSetupStatusLabel: function(rw) {
                var st = (rw && rw.multisig_setup_status) ? String(rw.multisig_setup_status) : '';
                if (!st) return '';
                var k = 'main.my_business.multisig_status_' + st;
                var t = this.$t(k);
                return (t && t !== k) ? t : st;
            },
            teardown: function() {
                this.stopMultisigFundingPoll();
                this.localWallet = null;
                this.participants = [];
                this.selectedAddresses = [];
                this.participantsLoading = false;
                this.thresholdPreset = 'two_of_n';
                this.error = null;
                this.saving = false;
                this.refreshing = false;
                this.silentMaintenanceRefreshing = false;
                this.wizardUiForceStep = null;
                this.tronLinkFundingBusy = false;
                this.tronLinkFundError = null;
                this.multisigFundingAddressCopied = false;
                if (this.multisigFundingAddressCopyTimerId != null) {
                    clearTimeout(this.multisigFundingAddressCopyTimerId);
                    this.multisigFundingAddressCopyTimerId = null;
                }
            },
            startMultisigFundingPoll: function() {
                if (!this.show || this.multisigWizardDisplayStep !== 2) return;
                if (this.multisigPollTimerId != null) return;
                var self = this;
                this.multisigPollTimerId = setInterval(function() {
                    if (!self.show || self.multisigWizardDisplayStep !== 2) {
                        self.stopMultisigFundingPoll();
                        return;
                    }
                    self.refreshMultisigWizard({ silent: true });
                }, 12000);
            },
            stopMultisigFundingPoll: function() {
                if (this.multisigPollTimerId != null) {
                    clearInterval(this.multisigPollTimerId);
                    this.multisigPollTimerId = null;
                }
            },
            applyMultisigResponseToLocalState: function(data) {
                if (!data) return;
                this.localWallet = Object.assign({}, data, {
                    multisig_setup_meta: Object.assign({}, data.multisig_setup_meta || {})
                });
                var meta = this.localWallet.multisig_setup_meta || {};
                var actors = Array.isArray(meta.actors) ? meta.actors : [];
                var main = (data.tron_address || '').trim();
                this.selectedAddresses = actors
                    .map(function(a) { return (a || '').trim(); })
                    .filter(function(a) { return a && a !== main; });
                this.applyMultisigWizardSelectionPolicy();
                this.thresholdPreset = this.inferMultisigThresholdPreset(meta);
                if (this.thresholdPreset === 'manual') {
                    this.wizardN = meta.threshold_n != null ? Number(meta.threshold_n) : this.wizardN;
                    this.syncMultisigWizardManualMFromSelection();
                } else {
                    this.syncMultisigWizardThresholdInputsForPreset();
                }
            },
            backToMultisigConfigStep: function() {
                this.wizardUiForceStep = 1;
                this.error = null;
            },
            getTronWebForFunding: function() {
                if (window.tronLink && window.tronLink.request) {
                    return window.tronLink.request({ method: 'tron_requestAccounts' }).then(function(res) {
                        if (res && res.code === 4001) return Promise.reject(new Error('USER_REJECTED'));
                        var tw = window.tronLink.tronWeb || window.tronWeb;
                        if (tw && tw.defaultAddress && tw.defaultAddress.base58) return tw;
                        return Promise.reject(new Error('NO_ADDRESS'));
                    });
                }
                if (window.tronWeb && window.tronWeb.defaultAddress && window.tronWeb.defaultAddress.base58) {
                    return Promise.resolve(window.tronWeb);
                }
                return Promise.reject(new Error('NO_TRONLINK'));
            },
            fundMultisigViaTronLink: function() {
                var self = this;
                /** Запас SUN на комиссию / сжигание bandwidth при нехватке ресурсов (≈ несколько TRX). */
                var FEE_BUFFER_SUN = 3000000;
                var to = (this.localWallet && this.localWallet.tron_address) ? String(this.localWallet.tron_address).trim() : '';
                if (!to) return;
                var meta = this.localWallet.multisig_setup_meta || {};
                var minSun = parseInt(meta.min_trx_sun, 10);
                if (!isFinite(minSun) || minSun < 1) minSun = 150000000;
                var bal = parseInt(meta.last_trx_balance_sun, 10);
                if (!isFinite(bal)) bal = 0;
                var shortage = Math.max(0, minSun - bal);
                var amountSun = shortage > 0 ? shortage : 1000000;
                if (amountSun < 1000000) amountSun = 1000000;
                this.tronLinkFundError = null;
                this.tronLinkFundingBusy = true;
                this.getTronWebForFunding()
                    .then(function(tw) {
                        var from = (tw.defaultAddress && tw.defaultAddress.base58) ? tw.defaultAddress.base58 : '';
                        if (!from) throw new Error('NO_ADDRESS');
                        function fmtTrx(sun) {
                            var n = Number(sun);
                            if (!isFinite(n)) n = 0;
                            return (n / 1e6).toLocaleString(undefined, {
                                maximumFractionDigits: 2,
                                minimumFractionDigits: 2
                            });
                        }
                        function buildAndBroadcast() {
                            return tw.transactionBuilder.sendTrx(to, amountSun, from).then(function(tx) {
                                return tw.trx.sign(tx);
                            }).then(function(signed) {
                                return tw.trx.sendRawTransaction(signed);
                            });
                        }
                        if (!tw.trx || typeof tw.trx.getBalance !== 'function') {
                            return buildAndBroadcast();
                        }
                        return tw.trx.getBalance(from).then(function(senderBalRaw) {
                            var sb = Number(senderBalRaw);
                            if (!isFinite(sb)) {
                                sb = parseInt(senderBalRaw, 10);
                                if (!isFinite(sb)) sb = 0;
                            }
                            var needSun = amountSun + FEE_BUFFER_SUN;
                            if (sb < needSun) {
                                var insuff = new Error('INSUFFICIENT_SENDER_TRX');
                                insuff.neededTrx = fmtTrx(needSun);
                                insuff.availableTrx = fmtTrx(sb);
                                insuff.transferTrx = fmtTrx(amountSun);
                                throw insuff;
                            }
                            return buildAndBroadcast();
                        }).catch(function(e) {
                            if (e && e.message === 'INSUFFICIENT_SENDER_TRX') throw e;
                            return buildAndBroadcast();
                        });
                    })
                    .then(function(res) {
                        var ok = res && (res.result === true || res.result === 'SUCCESS' || res.code === 'SUCCESS' || !!res.txid);
                        if (ok) return self.refreshMultisigWizard({ silent: true });
                        throw new Error((res && (res.message || res.code)) ? String(res.message || res.code) : 'broadcast');
                    })
                    .catch(function(e) {
                        var code = e && e.message ? e.message : '';
                        if (code === 'NO_TRONLINK') {
                            self.tronLinkFundError = self.$t('main.tron.install_tronlink');
                        } else if (code === 'USER_REJECTED') {
                            self.tronLinkFundError = self.$t('main.tron.unlock_try_again');
                        } else if (code === 'INSUFFICIENT_SENDER_TRX' && e && e.neededTrx) {
                            self.tronLinkFundError = self.$t('main.my_business.multisig_funding_sender_insufficient_trx', {
                                needed: e.neededTrx,
                                available: e.availableTrx,
                                amount: e.transferTrx
                            });
                        } else {
                            self.tronLinkFundError = (e && e.message) ? e.message : self.$t('main.dialog.error_title');
                        }
                    })
                    .finally(function() {
                        self.tronLinkFundingBusy = false;
                    });
            },
            copyMultisigFundingAddress: function() {
                var self = this;
                var a = (this.localWallet && this.localWallet.tron_address)
                    ? String(this.localWallet.tron_address).trim()
                    : '';
                if (!a) return;
                if (typeof navigator === 'undefined' || !navigator.clipboard || !navigator.clipboard.writeText) return;
                navigator.clipboard.writeText(a)
                    .then(function() {
                        self.multisigFundingAddressCopied = true;
                        if (self.multisigFundingAddressCopyTimerId != null) {
                            clearTimeout(self.multisigFundingAddressCopyTimerId);
                        }
                        self.multisigFundingAddressCopyTimerId = setTimeout(function() {
                            self.multisigFundingAddressCopied = false;
                            self.multisigFundingAddressCopyTimerId = null;
                        }, 2000);
                    })
                    .catch(function() {});
            },
            onMultisigModalBackdrop: function() {
                if (this.saving) return;
                this.closeModal();
            },
            closeModal: function() {
                if (this.saving) return;
                if (this.multisigReconfigureCancelPending) {
                    this.cancelReconfigureAndClose();
                    return;
                }
                this.$emit('close');
            },
            cancelReconfigureAndClose: function() {
                if (this.saving) return;
                var self = this;
                var rw = this.localWallet;
                var base = this.rampApiBase();
                if (!rw || !rw.id || !base) {
                    this.$emit('close');
                    return;
                }
                if (!this.multisigReconfigureCancelPending) {
                    this.$emit('close');
                    return;
                }
                this.saving = true;
                this.error = null;
                fetch(base + '/' + rw.id, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ multisig_cancel_reconfigure: true })
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
                    .then(function() {
                        self.$emit('saved', { walletId: rw.id });
                        self.$emit('close');
                    })
                    .catch(function(e) {
                        self.error = (e && e.message) ? e.message : self.$t('main.dialog.error_title');
                    })
                    .finally(function() {
                        self.saving = false;
                    });
            },
            bootstrap: function() {
                var rw = this.wallet;
                if (!rw) return;
                this.wizardUiForceStep = null;
                this.localWallet = Object.assign({}, rw, {
                    multisig_setup_meta: Object.assign({}, rw.multisig_setup_meta || {})
                });
                var m = this.localWallet.multisig_setup_meta || {};
                var actors = Array.isArray(m.actors) ? m.actors : [];
                var main = (rw.tron_address || '').trim();
                var withoutMain = actors
                    .map(function(a) { return (a || '').trim(); })
                    .filter(function(a) { return a && a !== main; });
                this.selectedAddresses = withoutMain.slice();
                this.thresholdPreset = this.inferMultisigThresholdPreset(m);
                this.wizardN = m.threshold_n != null ? Number(m.threshold_n) : 2;
                this.wizardM = m.threshold_m != null ? Number(m.threshold_m) : 2;
                this.error = null;
                this.saving = false;
                this.refreshing = false;
                this.participantsLoading = true;
                var self = this;
                var url = this.rampSpaceParticipantsUrl();
                if (!url) {
                    this.participantsLoading = false;
                    this.applyMultisigWizardSelectionPolicy();
                    this.thresholdPreset = this.inferMultisigThresholdPreset(m);
                    if (this.thresholdPreset === 'manual') {
                        this.wizardN = m.threshold_n != null ? Number(m.threshold_n) : this.wizardN;
                        this.syncMultisigWizardManualMFromSelection();
                    } else {
                        this.syncMultisigWizardThresholdInputsForPreset();
                    }
                    return;
                }
                fetch(url, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) throw new Error('load');
                        return r.json();
                    })
                    .then(function(data) {
                        self.participants = Array.isArray(data) ? data : [];
                    })
                    .catch(function() {
                        self.error = self.$t('main.my_business.multisig_signers_load_error');
                    })
                    .finally(function() {
                        self.participantsLoading = false;
                        self.applyMultisigWizardSelectionPolicy();
                        self.thresholdPreset = self.inferMultisigThresholdPreset(m);
                        if (self.thresholdPreset === 'manual') {
                            self.wizardN = m.threshold_n != null ? Number(m.threshold_n) : self.wizardN;
                            self.syncMultisigWizardManualMFromSelection();
                        } else {
                            self.syncMultisigWizardThresholdInputsForPreset();
                        }
                    });
            },
            isParticipantMultisigManager: function(p) {
                var roles = p && p.roles ? p.roles : [];
                if (!Array.isArray(roles)) roles = [roles];
                return roles.some(function(r) {
                    return r === 'operator' || r === 'owner';
                });
            },
            multisigWizardSelectableManagerAddressSet: function() {
                var map = {};
                var main = (this.localWallet && this.localWallet.tron_address) ? String(this.localWallet.tron_address).trim() : '';
                (this.multisigWizardManagerSignerRows || []).forEach(function(row) {
                    if (row.selectable && row.address && row.address !== main) map[row.address] = true;
                });
                return map;
            },
            applyMultisigWizardSelectionPolicy: function() {
                var rw = this.localWallet;
                if (!rw) return;
                var main = (rw.tron_address || '').trim();
                var allowed = this.multisigWizardSelectableManagerAddressSet();
                var sel = (this.selectedAddresses || []).slice();
                sel = sel.map(function(a) { return (a || '').trim(); }).filter(Boolean);
                sel = sel.filter(function(a) { return a !== main && allowed[a]; });
                var seen = {};
                sel = sel.filter(function(a) {
                    if (seen[a]) return false;
                    seen[a] = true;
                    return true;
                });
                this.selectedAddresses = sel;
                this.ensureMultisigWizardSignersAtLeastOneChecked();
                this.syncMultisigWizardThresholdInputsForPreset();
                this.syncMultisigWizardManualMFromSelection();
            },
            syncMultisigWizardManualMFromSelection: function() {
                if (this.thresholdPreset !== 'manual') return;
                var Lf = this.multisigWizardActorCount;
                this.wizardM = Lf;
                var nx = parseInt(this.wizardN, 10);
                if (!isNaN(nx) && Lf >= 1 && nx > Lf) this.wizardN = Lf;
            },
            multisigWizardGetSelectableSignerAddressList: function() {
                var allowed = this.multisigWizardSelectableManagerAddressSet();
                var rows = this.multisigWizardManagerSignerRows || [];
                var out = [];
                var seenAddr = {};
                var i;
                for (i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    if (!row || !row.selectable) continue;
                    var a = (row.address || '').trim();
                    if (!a || !allowed[a] || seenAddr[a]) continue;
                    seenAddr[a] = true;
                    out.push(a);
                }
                return out;
            },
            multisigWizardSelectionIntersectsSelectableSigners: function(addressList) {
                var allSelectable = this.multisigWizardGetSelectableSignerAddressList();
                if (allSelectable.length === 0) return true;
                var cur = (addressList || []).map(function(x) { return (x || '').trim(); }).filter(Boolean);
                var i;
                for (i = 0; i < allSelectable.length; i++) {
                    if (cur.indexOf(allSelectable[i]) !== -1) return true;
                }
                return false;
            },
            ensureMultisigWizardSignersAtLeastOneChecked: function() {
                var allSelectable = this.multisigWizardGetSelectableSignerAddressList();
                if (allSelectable.length === 0) return;
                var cur = (this.selectedAddresses || []).map(function(x) { return (x || '').trim(); }).filter(Boolean);
                var i;
                for (i = 0; i < allSelectable.length; i++) {
                    if (cur.indexOf(allSelectable[i]) !== -1) return;
                }
                this.selectedAddresses = allSelectable.slice();
            },
            inferMultisigThresholdPreset: function(meta) {
                meta = meta || {};
                var raw = Array.isArray(meta.actors) ? meta.actors : [];
                var seen = {};
                var L = 0;
                var i;
                for (i = 0; i < raw.length; i++) {
                    var s = (raw[i] || '').trim();
                    if (!s || seen[s]) continue;
                    seen[s] = true;
                    L++;
                }
                var tn = meta.threshold_n != null ? Number(meta.threshold_n) : NaN;
                var tm = meta.threshold_m != null ? Number(meta.threshold_m) : NaN;
                if (L >= 2 && tn === 2 && tm === L) return 'two_of_n';
                if (L >= 2 && tn === L && tm === L) return 'all';
                if (!isNaN(tn) && !isNaN(tm) && L >= 1) return 'manual';
                return 'two_of_n';
            },
            syncMultisigWizardThresholdInputsForPreset: function() {
                var L = this.multisigWizardActorCount;
                var p = this.thresholdPreset;
                if (p === 'two_of_n') {
                    this.wizardN = 2;
                    this.wizardM = L;
                } else if (p === 'all') {
                    this.wizardN = L;
                    this.wizardM = L;
                }
            },
            onMultisigThresholdPresetChange: function() {
                this.syncMultisigWizardThresholdInputsForPreset();
                if (this.thresholdPreset === 'manual') {
                    this.syncMultisigWizardManualMFromSelection();
                }
            },
            isMultisigManagerSignerSelected: function(addr) {
                var a = (addr || '').trim();
                if (!a) return false;
                return (this.selectedAddresses || []).indexOf(a) !== -1;
            },
            toggleMultisigManagerSignerRowClick: function(row) {
                if (!row || !row.selectable) return;
                var addr = (row.address || '').trim();
                if (!addr) return;
                var arr = (this.selectedAddresses || []).slice();
                var i = arr.indexOf(addr);
                if (i !== -1) {
                    var after = arr.slice();
                    after.splice(i, 1);
                    if (!this.multisigWizardSelectionIntersectsSelectableSigners(after)) return;
                    arr.splice(i, 1);
                } else {
                    arr.push(addr);
                }
                this.selectedAddresses = arr;
                this.applyMultisigWizardSelectionPolicy();
            },
            multisigWizardRolesLabel: function(roles) {
                var r = Array.isArray(roles) ? roles : (roles ? [roles] : []);
                return r.map(function(x) {
                    var k = 'main.space.role_' + String(x);
                    var t = this.$t(k);
                    return t && t !== k ? t : x;
                }, this).join(', ');
            },
            saveMultisigWizard: function() {
                var self = this;
                var rw = this.localWallet;
                var base = this.rampApiBase();
                if (!rw || !rw.id || !base) return;
                var main = (rw.tron_address || '').trim();
                if (!main) {
                    this.error = this.$t('main.dialog.error_title');
                    return;
                }
                var allowed = this.multisigWizardSelectableManagerAddressSet();
                var extra = (this.selectedAddresses || [])
                    .map(function(a) { return (a || '').trim(); })
                    .filter(Boolean);
                if (Object.keys(allowed).length > 0 && extra.length < 1) {
                    this.error = this.$t('main.my_business.multisig_signers_select_one');
                    return;
                }
                var i;
                for (i = 0; i < extra.length; i++) {
                    if (!allowed[extra[i]]) {
                        this.error = this.$t('main.my_business.multisig_signers_invalid');
                        return;
                    }
                }
                var actors = [];
                var seen = {};
                for (i = 0; i < extra.length; i++) {
                    var rawA = (extra[i] || '').trim();
                    if (!rawA || rawA === main) continue;
                    if (seen[rawA]) continue;
                    if (!allowed[rawA]) continue;
                    seen[rawA] = true;
                    actors.push(rawA);
                }
                if ((this.multisigWizardManagerSignerRows || []).length < 2) {
                    this.error = this.$t('main.my_business.multisig_signers_too_few');
                    return;
                }
                var Lfull = actors.length;
                var preset = this.thresholdPreset;
                var n;
                var mPayload;
                if (preset === 'two_of_n') {
                    if (Lfull < 2) {
                        this.error = this.$t('main.dialog.error_title');
                        return;
                    }
                    n = 2;
                    mPayload = Lfull;
                } else if (preset === 'all') {
                    n = Lfull;
                    mPayload = Lfull;
                } else {
                    n = parseInt(this.wizardN, 10);
                    var mForm = parseInt(this.wizardM, 10);
                    if (
                        actors.length < 1
                        || isNaN(n)
                        || isNaN(mForm)
                        || n < 1
                        || mForm < 1
                        || mForm !== Lfull
                        || n > mForm
                    ) {
                        this.error = this.$t('main.dialog.error_title');
                        return;
                    }
                    mPayload = mForm;
                }
                this.saving = true;
                this.error = null;
                fetch(base + '/' + rw.id, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({
                        multisig_actors: actors,
                        multisig_threshold_n: n,
                        multisig_threshold_m: mPayload
                    })
                })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(j) { throw new Error((j && j.detail) || String(r.status)); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.wizardUiForceStep = null;
                        self.applyMultisigResponseToLocalState(data);
                        self.$emit('saved', { walletId: rw.id });
                    })
                    .catch(function(e) {
                        self.error = (e && e.message) ? e.message : 'Error';
                    })
                    .finally(function() {
                        self.saving = false;
                    });
            },
            refreshMultisigWizard: function(opts) {
                opts = opts || {};
                var silent = !!opts.silent;
                var self = this;
                var rw = this.localWallet;
                var base = this.rampApiBase();
                if (!rw || !rw.id || !base) return Promise.resolve();
                if (!silent) {
                    this.refreshing = true;
                    this.saving = true;
                } else {
                    this.silentMaintenanceRefreshing = true;
                }
                this.error = null;
                return fetch(base + '/' + rw.id + '/multisig-maintenance', {
                    method: 'POST',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include'
                })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.applyMultisigResponseToLocalState(data);
                        if (!silent) self.$emit('saved', { walletId: rw.id });
                    })
                    .catch(function(e) {
                        if (!silent) self.error = (e && e.message) ? e.message : 'Error';
                    })
                    .finally(function() {
                        if (!silent) {
                            self.saving = false;
                            self.refreshing = false;
                        } else {
                            self.silentMaintenanceRefreshing = false;
                        }
                    });
            },
            retryMultisigWizard: function() {
                var self = this;
                var rw = this.localWallet;
                var base = this.rampApiBase();
                if (!rw || !rw.id || !base) return;
                this.saving = true;
                this.error = null;
                fetch(base + '/' + rw.id, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ multisig_retry: true })
                })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.applyMultisigResponseToLocalState(data);
                        self.$emit('saved', { walletId: rw.id });
                        self.refreshMultisigWizard();
                    })
                    .catch(function(e) {
                        self.error = (e && e.message) ? e.message : 'Error';
                        self.saving = false;
                    });
            }
        },
        template: [
            '<div v-if="show && localWallet" class="fixed inset-0 z-[110] flex items-center justify-center p-4">',
            '  <div class="absolute inset-0 bg-black/60" @click="onMultisigModalBackdrop"></div>',
            '  <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden max-h-[90vh] overflow-y-auto">',
            '    <div class="p-5 sm:p-6 border-b border-[#eff2f5] flex items-center justify-between gap-2">',
            '      <div class="min-w-0 flex-1 pr-2">',
            '        <h3 class="text-lg sm:text-xl font-bold text-[#191d23]">[[ $t(\'main.my_business.multisig_wizard_title\') ]]</h3>',
            '        <p class="text-xs text-[#58667e] mt-0.5">[[ $t(\'main.my_business.multisig_wizard_step_of\', { current: multisigWizardDisplayStep, total: 3 }) ]]<template v-if="multisigWizardStepCaption"> — [[ multisigWizardStepCaption ]]</template></p>',
            '      </div>',
            '      <button type="button" @click="closeModal" :disabled="saving" class="p-2 hover:bg-gray-100 rounded-full shrink-0 disabled:opacity-45"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '    </div>',
            '    <div class="p-5 sm:p-6 space-y-4">',
            '      <div>',
            '        <p class="text-xs text-[#58667e] leading-snug"><span class="font-mono break-all">[[ localWallet.tron_address ]]</span></p>',
            '        <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">',
            '          <span class="text-xs font-semibold text-[#30384a] shrink-0 max-w-[min(100%,14rem)] truncate" :title="localWallet.multisig_setup_status || \'\'">[[ multisigSetupStatusLabel(localWallet) || localWallet.multisig_setup_status || \'—\' ]]</span>',
            '          <span v-if="silentMaintenanceRefreshing" class="text-[11px] text-[#58667e] inline-flex items-center gap-1"><svg class="w-3.5 h-3.5 animate-spin text-[#3861fb]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg></span>',
            '        <button type="button" @click="refreshMultisigWizard()" :disabled="saving" :aria-label="$t(\'main.my_business.multisig_refresh\')" class="inline-flex items-center gap-2 rounded-lg border border-[#eff2f5] bg-white px-3 py-2 text-xs font-bold text-[#3861fb] hover:bg-blue-50/80 disabled:opacity-45 disabled:cursor-not-allowed transition-colors shrink-0">',
            '          <svg v-if="!refreshing" class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>',
            '          <svg v-else class="w-4 h-4 shrink-0 animate-spin text-[#3861fb]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
            '          <span>[[ $t(\'main.my_business.multisig_refresh\') ]]</span>',
            '        </button>',
            '        </div>',
            '      </div>',
            '      <template v-if="multisigWizardDisplayStep === 1">',
            '      <div>',
            '        <div v-if="localWallet.multisig_setup_status === \'reconfigure\'" class="rounded-xl border border-violet-200 bg-violet-50/90 px-3 py-2.5 text-[11px] text-[#30384a] leading-snug mb-2" role="status">[[ $t(\'main.my_business.multisig_wizard_reconfigure_hint\') ]]</div>',
            '        <div class="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2.5 text-sm text-[#191d23] mb-2" role="status">[[ $t(\'main.my_business.multisig_owners_all_admins_hint\') ]]</div>',
            '        <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5">[[ $t(\'main.my_business.multisig_actors_label\') ]]</label>',
            '        <div v-if="participantsLoading" class="text-sm text-[#58667e] py-4 text-center rounded-xl border border-dashed border-[#eff2f5]">…</div>',
            '        <div v-else class="max-h-52 overflow-y-auto rounded-xl border border-[#eff2f5] bg-white divide-y divide-[#eff2f5]">',
            '          <div v-for="row in multisigWizardManagerSignerRows" :key="(row.kind || \'participant\') + \'-\' + row.address" class="flex items-start gap-3 p-3 transition-colors" :class="row.selectable ? \'cursor-pointer hover:bg-[#fafbfd]\' : \'opacity-65 cursor-default\'" @click="toggleMultisigManagerSignerRowClick(row)">',
            '            <input type="checkbox" class="mt-1 shrink-0 rounded border-[#cfd6e4] text-[#3861fb] pointer-events-none" tabindex="-1" :disabled="!row.selectable" :checked="isMultisigManagerSignerSelected(row.address)" />',
            '            <div class="min-w-0 flex-1 pointer-events-none">',
            '              <div class="text-sm font-semibold text-[#191d23]">[[ row.kind === \'space_owner\' ? $t(\'main.my_business.multisig_signers_space_owner\') : (row.nickname || row.address) ]]</div>',
            '              <div class="font-mono text-[11px] text-[#58667e] break-all mt-0.5">[[ row.address ]]</div>',
            '              <div v-if="row.kind !== \'space_owner\' && row.roles && row.roles.length" class="text-[10px] text-[#58667e] mt-1">[[ multisigWizardRolesLabel(row.roles) ]]</div>',
            '              <div v-if="row.kind !== \'space_owner\' && !row.is_verified" class="text-[11px] text-amber-800 mt-1">[[ $t(\'main.my_business.multisig_signers_not_verified\') ]]</div>',
            '            </div>',
            '          </div>',
            '          <div v-if="!multisigWizardManagerSignerRows.length" class="p-4 text-xs text-[#58667e] text-center">[[ $t(\'main.my_business.multisig_signers_no_managers\') ]]</div>',
            '        </div>',
            '      </div>',
            '      <div>',
            '        <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5">[[ $t(\'main.my_business.multisig_threshold_preset_label\') ]]</label>',
            '        <select v-model="thresholdPreset" @change="onMultisigThresholdPresetChange" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]">',
            '          <option value="two_of_n">[[ $t(\'main.my_business.multisig_threshold_preset_two_of_n\') ]]</option>',
            '          <option value="all">[[ $t(\'main.my_business.multisig_threshold_preset_all\') ]]</option>',
            '          <option value="manual">[[ $t(\'main.my_business.multisig_threshold_preset_manual\') ]]</option>',
            '        </select>',
            '        <div v-if="thresholdPreset === \'manual\'" class="mt-3 space-y-2">',
            '          <p class="text-[11px] text-[#58667e]">[[ $t(\'main.my_business.multisig_threshold_manual_hint\') ]]</p>',
            '          <div class="grid grid-cols-2 gap-3">',
            '            <div><label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5">[[ $t(\'main.my_business.multisig_threshold_n\') ]]</label><input type="number" min="1" :max="multisigWizardActorCount >= 1 ? multisigWizardActorCount : undefined" v-model.number="wizardN" :class="[\'w-full px-4 py-3 bg-gray-50 rounded-xl text-sm focus:outline-none\', multisigWizardManualNInvalid ? \'border-2 border-red-500\' : \'border border-[#eff2f5] focus:border-[#3861fb]\']" /></div>',
            '            <div><label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5">[[ $t(\'main.my_business.multisig_threshold_m\') ]]</label><input type="number" min="1" :max="multisigWizardActorCount >= 1 ? multisigWizardActorCount : undefined" v-model.number="wizardM" readonly tabindex="-1" :class="[\'w-full px-4 py-3 rounded-xl text-sm cursor-default text-[#30384a]\', multisigWizardManualMInvalid ? \'border-2 border-red-500 bg-red-50/60\' : \'border border-[#e1e5eb] bg-[#eef1f6]\']" /></div>',
            '          </div>',
            '          <p v-if="thresholdPreset === \'manual\' && multisigWizardManualNInvalid" class="text-xs text-red-600">[[ $t(\'main.my_business.multisig_threshold_manual_n_invalid\') ]]</p>',
            '          <p v-if="thresholdPreset === \'manual\' && multisigWizardManualMInvalid" class="text-xs text-red-600">[[ $t(\'main.my_business.multisig_threshold_manual_m_invalid\') ]]</p>',
            '        </div>',
            '        <p v-if="!participantsLoading && multisigWizardSignerRowsTooFew" class="text-xs text-red-600 mt-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2">[[ $t(\'main.my_business.multisig_signers_too_few\') ]]</p>',
            '      </div>',
            '      </template>',
            '      <template v-else-if="multisigWizardDisplayStep === 2">',
            '      <div class="rounded-xl border border-amber-100 bg-amber-50/80 px-4 py-3 space-y-3 text-sm text-[#191d23]">',
            '        <div><span class="text-[10px] font-bold text-[#58667e] uppercase tracking-wide">[[ $t(\'main.my_business.multisig_funding_min_required\') ]]</span><div class="font-mono text-lg font-bold text-[#191d23] mt-0.5">[[ multisigMinTrxKnown ? formatSunAsTrx((localWallet.multisig_setup_meta || {}).min_trx_sun) : \'—\' ]]</div><p v-if="!multisigFundingMinRefinedByMaintenance" class="text-[11px] text-[#58667e] mt-1.5 leading-snug">[[ $t(\'main.my_business.multisig_funding_min_pending_hint\') ]]</p></div>',
            '        <div class="border-t border-amber-100/80 pt-2"><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.multisig_balance_current\') ]]</span><div class="font-mono font-semibold text-emerald-700">[[ formatSunAsTrx((localWallet.multisig_setup_meta || {}).last_trx_balance_sun) ]]</div></div>',
            '        <p v-if="multisigFundingShortfallTrx" class="text-xs font-semibold text-amber-900">[[ $t(\'main.my_business.multisig_funding_shortfall\', { amount: multisigFundingShortfallTrx }) ]]</p>',
            '        <p class="text-[11px] text-[#58667e] leading-snug">[[ $t(\'main.my_business.multisig_funding_polling_hint\') ]]</p>',
            '        <p v-if="tronLinkFundError" class="text-xs text-red-600 leading-snug">[[ tronLinkFundError ]]</p>',
            '        <button type="button" @click="fundMultisigViaTronLink" :disabled="tronLinkFundingBusy || saving" class="w-full py-3 rounded-xl text-sm font-bold text-white bg-[#ef8a2e] hover:opacity-95 disabled:opacity-50 shadow-sm">[[ tronLinkFundingBusy ? $t(\'main.my_business.multisig_funding_tronlink_busy\') : $t(\'main.my_business.multisig_funding_send_tronlink\') ]]</button>',
            '        <button type="button" @click="copyMultisigFundingAddress" :disabled="!localWallet.tron_address" class="w-full py-2.5 rounded-xl text-sm font-bold text-[#3861fb] border border-[#cfd6e4] bg-white hover:bg-blue-50/60 disabled:opacity-45">[[ multisigFundingAddressCopied ? $t(\'main.copied\') : $t(\'main.my_business.multisig_funding_copy_address\') ]]</button>',
            '        <button type="button" @click="backToMultisigConfigStep" class="text-xs font-bold text-[#3861fb] hover:underline">[[ $t(\'main.my_business.multisig_wizard_back_config\') ]]</button>',
            '      </div>',
            '      </template>',
            '      <template v-else>',
            '      <div class="rounded-xl border border-[#eff2f5] bg-[#fafbfd] px-4 py-3 text-sm space-y-3">',
            '        <div v-if="localWallet.multisig_setup_status === \'active\'" role="status" class="rounded-xl bg-emerald-50 border border-emerald-100 px-3 py-2.5">',
            '          <p class="text-sm font-bold text-emerald-900">[[ $t(\'main.my_business.multisig_wizard_success_title\') ]]</p>',
            '          <p class="text-[11px] text-emerald-800/95 leading-snug mt-1">[[ multisigWizardReconfigureNoopSuccess ? $t(\'main.my_business.multisig_wizard_reconfigure_noop_hint\') : $t(\'main.my_business.multisig_wizard_success_hint\') ]]</p>',
            '        </div>',
            '        <div v-else-if="localWallet.multisig_setup_status === \'permissions_submitted\'" role="status" class="rounded-xl bg-blue-50/90 border border-blue-100 px-3 py-2.5">',
            '          <p class="text-[11px] text-[#1e3a5f] leading-snug font-semibold">[[ $t(\'main.my_business.multisig_wizard_step3_tx_pending_hint\') ]]</p>',
            '        </div>',
            '        <div v-else-if="localWallet.multisig_setup_status === \'ready_for_permissions\'" role="status" class="rounded-xl bg-[#f0f4ff] border border-[#dbe4ff] px-3 py-2.5">',
            '          <p class="text-[11px] text-[#30384a] leading-snug">[[ $t(\'main.my_business.multisig_wizard_step3_ready_hint\') ]]</p>',
            '        </div>',
            '        <div v-else-if="localWallet.multisig_setup_status === \'failed\'" role="alert" class="rounded-xl bg-amber-50/90 border border-amber-100 px-3 py-2.5">',
            '          <p class="text-[11px] text-amber-950/90 leading-snug">[[ $t(\'main.my_business.multisig_wizard_step3_failed_hint\') ]]</p>',
            '        </div>',
            '        <p v-else class="text-[11px] text-[#58667e] leading-snug">[[ $t(\'main.my_business.multisig_wizard_finish_hint\') ]]</p>',
            '        <div><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.multisig_balance_current\') ]]</span><div class="font-mono font-semibold text-emerald-600">[[ formatSunAsTrx((localWallet.multisig_setup_meta || {}).last_trx_balance_sun) ]]</div></div>',
            '      </div>',
            '      <div v-if="(localWallet.multisig_setup_meta || {}).last_error" class="text-xs text-red-600 rounded-xl bg-red-50 border border-red-100 px-3 py-2">[[ $t(\'main.my_business.multisig_last_error\') ]]: [[ (localWallet.multisig_setup_meta || {}).last_error ]]</div>',
            '      <div v-if="(localWallet.multisig_setup_meta || {}).permission_tx_id" class="text-xs text-[#58667e]">',
            '        <span class="font-bold">[[ $t(\'main.my_business.multisig_tx\') ]]:</span> ',
            '        <a :href="\'https://tronscan.org/#/transaction/\' + encodeURIComponent((localWallet.multisig_setup_meta || {}).permission_tx_id)" target="_blank" rel="noopener noreferrer" class="text-[#3861fb] font-mono break-all hover:underline">[[ (localWallet.multisig_setup_meta || {}).permission_tx_id ]]</a>',
            '      </div>',
            '      <button v-if="localWallet.multisig_setup_status !== \'active\' && localWallet.multisig_setup_status !== \'failed\'" type="button" @click="backToMultisigConfigStep" class="text-xs font-bold text-[#3861fb] hover:underline">[[ $t(\'main.my_business.multisig_wizard_back_config\') ]]</button>',
            '      </template>',
            '      <p v-if="error" class="text-xs text-red-600">[[ error ]]</p>',
            '    </div>',
            '    <div class="p-5 sm:p-6 bg-gray-50 border-t border-[#eff2f5] flex flex-col sm:flex-row gap-2 sm:gap-3">',
            '      <button v-if="localWallet.multisig_setup_status === \'active\'" type="button" @click="closeModal" :disabled="saving" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 transition-all order-last sm:order-none disabled:opacity-45">[[ $t(\'main.my_business.multisig_wizard_close\') ]]</button>',
            '      <button v-else-if="multisigReconfigureCancelPending" type="button" @click="closeModal" :disabled="saving" class="flex-1 py-3 border border-[#cfd6e4] rounded-xl text-sm font-bold text-[#3861fb] bg-blue-50/50 hover:bg-blue-50 transition-all order-last sm:order-none disabled:opacity-45">[[ $t(\'main.my_business.multisig_wizard_cancel_reconfigure\') ]]</button>',
            '      <button v-else type="button" @click="closeModal" :disabled="saving" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all order-last sm:order-none disabled:opacity-45">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '      <button v-if="multisigWizardDisplayStep === 1" type="button" @click="saveMultisigWizard" :disabled="saving || multisigWizardSaveDisabled" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 inline-flex items-center justify-center gap-1.5">[[ $t(\'main.my_business.multisig_save_config\') ]]<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg></button>',
            '      <button v-if="localWallet.multisig_setup_status === \'failed\'" type="button" @click="retryMultisigWizard" :disabled="saving" class="flex-1 py-3 border border-amber-200 rounded-xl text-sm font-bold text-amber-900 bg-amber-50 hover:bg-amber-100 disabled:opacity-50">[[ $t(\'main.my_business.multisig_retry\') ]]</button>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
