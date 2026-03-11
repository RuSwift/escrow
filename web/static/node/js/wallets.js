/**
 * Vue 2 компонент: Кошельки (таблица адресов с фильтрацией и CRUD).
 * Табы: кошельки для операций, менеджеры. Логика по аналогии с garantex.
 */
(function() {
    var API_BASE = '/v1';
    var WALLETS_API = API_BASE + '/wallets';

    Vue.component('wallets', {
        delimiters: ['[[', ']]'],
        props: { isNodeInitialized: { type: Boolean, default: false } },
        data: function() {
            return {
                WALLETS_API: WALLETS_API,
                activeTab: 'wallets',
                searchQuery: '',
                walletList: [],
                managerList: [],
                loading: false,
                loadError: '',
                showAddWalletModal: false,
                showEditModal: false,
                showDeleteModal: false,
                showDidDocModal: false,
                didDocWallet: null,
                managerLoadError: '',
                showManagerDidDocModal: false,
                managerDidDocManager: null,
                showRevokeManagerModal: false,
                revokeManagerTarget: null,
                showAddManagerModal: false,
                addManagerForm: { wallet_address: '', blockchain: 'tron', nickname: '' },
                addForm: { name: '', mnemonic: '' },
                editForm: { name: '' },
                editWallet: null,
                deleteWallet: null,
                submitting: false,
                submitError: '',
                copyFeedback: '',
                _copyFeedbackTimer: null
            };
        },
        computed: {
            filteredWallets: function() {
                var q = (this.searchQuery || '').trim().toLowerCase();
                if (!q) return this.walletList;
                return this.walletList.filter(function(w) {
                    var name = (w.name || '').toLowerCase();
                    var tron = (w.tron_address || '').toLowerCase();
                    var eth = (w.ethereum_address || '').toLowerCase();
                    return name.indexOf(q) !== -1 || tron.indexOf(q) !== -1 || eth.indexOf(q) !== -1;
                });
            },
            filteredManagers: function() {
                var q = (this.searchQuery || '').trim().toLowerCase();
                if (!q) return this.managerList;
                return this.managerList.filter(function(m) {
                    var nick = (m.nickname || '').toLowerCase();
                    var addr = (m.wallet_address || '').toLowerCase();
                    return nick.indexOf(q) !== -1 || addr.indexOf(q) !== -1;
                });
            }
        },
        watch: {
            activeTab: function(tab) {
                if (tab === 'managers' && this.managerList.length === 0) this.loadManagers();
            }
        },
        mounted: function() {
            this.loadWallets();
        },
        methods: {
            _walletErrorDetail: function(data) {
                if (!data) return '';
                var d = data.detail;
                if (typeof d === 'string') return d;
                if (Array.isArray(d) && d.length > 0) {
                    return d.map(function(x) { return x.msg || (x.loc ? (x.loc.join('.') + ': ' + (x.msg || '')) : JSON.stringify(x)); }).join('; ');
                }
                return '';
            },
            _walletCreateErrorDetail: function(data) {
                var raw = this._walletErrorDetail(data);
                if (!raw) return '';
                var lower = raw.toLowerCase();
                if (lower.indexOf('name already exists') !== -1 || (lower.indexOf('this name') !== -1 && lower.indexOf('already') !== -1)) return this.$t('node.wallets.error_duplicate_name');
                if (lower.indexOf('addresses already') !== -1) return this.$t('node.wallets.error_duplicate_addresses');
                if (lower.indexOf('invalid mnemonic') !== -1 || (lower.indexOf('мнемоническ') !== -1 && lower.indexOf('неверн') !== -1)) return this.$t('node.wallets.error_invalid_mnemonic');
                if (lower.indexOf('mnemonic') !== -1 && lower.indexOf('required') !== -1) return this.$t('node.wallets.error_mnemonic_required');
                if (lower.indexOf('name') !== -1 && lower.indexOf('required') !== -1) return this.$t('node.wallets.error_name_required');
                return raw;
            },
            loadWallets: function() {
                var self = this;
                self.loading = true;
                self.loadError = '';
                fetch(WALLETS_API, { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || self.$t('node.wallets.load_error')); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.walletList = data.wallets || [];
                        self.loading = false;
                    })
                    .catch(function(err) {
                        self.loadError = err.message || self.$t('node.wallets.load_error');
                        self.loading = false;
                    });
            },
            loadManagers: function() {
                var self = this;
                self.managerLoadError = '';
                fetch(WALLETS_API + '/managers', { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || self.$t('node.wallets.managers_load_error')); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.managerList = data.managers || [];
                    })
                    .catch(function(err) {
                        self.managerLoadError = err.message || self.$t('node.wallets.managers_load_error');
                        self.managerList = [];
                    });
            },
            openManagerDidDoc: function(m) {
                this.managerDidDocManager = m;
                this.showManagerDidDocModal = true;
            },
            closeManagerDidDoc: function() {
                this.showManagerDidDocModal = false;
                this.managerDidDocManager = null;
            },
            openAddManager: function() {
                this.addManagerForm = { wallet_address: '', blockchain: 'tron', nickname: '' };
                this.submitError = '';
                this.showAddManagerModal = true;
            },
            closeAddManagerModal: function() {
                this.showAddManagerModal = false;
            },
            submitAddManager: function() {
                var self = this;
                self.submitError = '';
                var addr = (this.addManagerForm.wallet_address || '').trim();
                var nick = (this.addManagerForm.nickname || '').trim();
                if (!addr) {
                    self.submitError = this.$t('node.wallets.manager_add_error_address');
                    return;
                }
                if (!nick) {
                    self.submitError = this.$t('node.wallets.manager_add_error_nickname');
                    return;
                }
                var chain = (this.addManagerForm.blockchain || 'tron').toLowerCase();
                if (chain !== 'tron' && chain !== 'ethereum') chain = 'tron';
                self.submitting = true;
                fetch(WALLETS_API + '/managers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ wallet_address: addr, blockchain: chain, nickname: nick })
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, status: r.status, data: d };
                        }).catch(function() { return { ok: false, status: r.status, data: { detail: r.statusText } }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data && result.data.id != null) {
                            self.managerList.unshift(result.data);
                            self.closeAddManagerModal();
                        } else {
                            self.submitError = (result.data && result.data.detail) || self.$t('node.wallets.manager_add_error');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.manager_add_error');
                    });
            },
            openRevokeManager: function(m) {
                this.revokeManagerTarget = m;
                this.submitError = '';
                this.showRevokeManagerModal = true;
            },
            closeRevokeManager: function() {
                this.showRevokeManagerModal = false;
                this.revokeManagerTarget = null;
            },
            confirmRevokeManager: function() {
                var self = this;
                if (!this.revokeManagerTarget) { self.closeRevokeManager(); return; }
                var id = this.revokeManagerTarget.id;
                self.submitting = true;
                self.submitError = '';
                fetch(WALLETS_API + '/managers/' + id, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ access_to_admin_panel: false })
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, data: d };
                        }).catch(function() { return { ok: false, data: { detail: r.statusText } }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok) {
                            self.managerList = self.managerList.filter(function(m) { return m.id !== id; });
                            self.closeRevokeManager();
                        } else {
                            self.submitError = (result.data && result.data.detail) || self.$t('node.wallets.manager_revoke_error');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.manager_revoke_error');
                    });
            },
            shortAddress: function(addr) {
                if (!addr || addr.length < 14) return addr;
                return addr.substring(0, 6) + '...' + addr.substring(addr.length - 4);
            },
            copyToClipboard: function(text, label) {
                var self = this;
                if (!text) return;
                function showFeedback() {
                    self.copyFeedback = label || 'OK';
                    if (self._copyFeedbackTimer) clearTimeout(self._copyFeedbackTimer);
                    self._copyFeedbackTimer = setTimeout(function() { self.copyFeedback = ''; }, 2000);
                }
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(showFeedback).catch(function() {
                        fallbackCopy();
                    });
                } else {
                    fallbackCopy();
                }
                function fallbackCopy() {
                    var ta = document.createElement('textarea');
                    ta.value = text;
                    ta.style.position = 'fixed';
                    ta.style.opacity = '0';
                    document.body.appendChild(ta);
                    ta.select();
                    try {
                        document.execCommand('copy');
                        showFeedback();
                    } catch (e) {}
                    document.body.removeChild(ta);
                }
            },
            blockchainForAddress: function(addr) {
                if (!addr) return '';
                if (addr.startsWith('T') && addr.length === 34) return 'TRON';
                if (addr.startsWith('0x') && addr.length === 42) return 'Ethereum';
                return '';
            },
            openAddWallet: function() {
                this.addForm = { name: '', mnemonic: '' };
                this.submitError = '';
                this.showAddWalletModal = true;
            },
            closeAddWallet: function() {
                this.showAddWalletModal = false;
            },
            submitAddWallet: function() {
                var self = this;
                self.submitError = '';
                if (!this.addForm.name.trim()) {
                    self.submitError = this.$t('node.wallets.error_name_required');
                    return;
                }
                if (!this.addForm.mnemonic.trim()) {
                    self.submitError = this.$t('node.wallets.error_mnemonic_required');
                    return;
                }
                self.submitting = true;
                fetch(WALLETS_API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: self.addForm.name.trim(), mnemonic: self.addForm.mnemonic.trim() })
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, status: r.status, data: d };
                        }).catch(function() {
                            return { ok: false, status: r.status, data: { detail: r.statusText || self.$t('node.wallets.error_create') } };
                        });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data && result.data.id != null) {
                            self.walletList.unshift(result.data);
                            self.closeAddWallet();
                        } else {
                            self.submitError = self._walletCreateErrorDetail(result.data) || self.$t('node.wallets.error_create');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.error_create');
                    });
            },
            openDidDoc: function(w) {
                this.didDocWallet = w;
                this.showDidDocModal = true;
            },
            closeDidDoc: function() {
                this.showDidDocModal = false;
                this.didDocWallet = null;
            },
            openEdit: function(w) {
                this.editWallet = w;
                this.editForm = { name: w.name || '' };
                this.submitError = '';
                this.showEditModal = true;
            },
            closeEdit: function() {
                this.showEditModal = false;
                this.editWallet = null;
            },
            submitEdit: function() {
                var self = this;
                if (!this.editWallet || !this.editForm.name.trim()) return;
                self.submitting = true;
                self.submitError = '';
                fetch(WALLETS_API + '/' + this.editWallet.id + '/name', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: this.editForm.name.trim() })
                })
                    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data.id) {
                            var idx = self.walletList.findIndex(function(w) { return w.id === result.data.id; });
                            if (idx !== -1) self.walletList.splice(idx, 1, result.data);
                            self.closeEdit();
                        } else {
                            self.submitError = self._walletErrorDetail(result.data) || self.$t('node.wallets.error_update');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.error_update');
                    });
            },
            openDelete: function(w) {
                this.deleteWallet = w;
                this.showDeleteModal = true;
            },
            closeDelete: function() {
                this.showDeleteModal = false;
                this.deleteWallet = null;
            },
            confirmDelete: function() {
                var self = this;
                if (!this.deleteWallet) { self.closeDelete(); return; }
                var id = this.deleteWallet.id;
                self.submitting = true;
                fetch(WALLETS_API + '/' + id, {
                    method: 'DELETE',
                    credentials: 'same-origin'
                })
                    .then(function(r) {
                        self.submitting = false;
                        if (r.ok) {
                            self.walletList = self.walletList.filter(function(w) { return w.id !== id; });
                            self.closeDelete();
                        } else {
                            return r.json().then(function(d) { self.submitError = self._walletErrorDetail(d) || self.$t('node.wallets.error_delete'); });
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.error_delete');
                    });
            }
        },
        template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">[[ $t('node.page.wallets') ]]</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.wallets.title') ]]</span>
          </div>
          <div class="p-6">
            <div class="flex flex-wrap items-center gap-4 border-b border-zinc-200 mb-6">
              <button type="button" @click="activeTab = 'wallets'" :class="activeTab === 'wallets' ? 'text-blue-600 border-b-2 border-blue-600 pb-2 -mb-px font-semibold' : 'text-zinc-500 hover:text-zinc-700'" class="text-[13px] uppercase tracking-tight">
                [[ $t('node.wallets.tab_operations') ]]
              </button>
              <button type="button" @click="activeTab = 'managers'" :class="activeTab === 'managers' ? 'text-blue-600 border-b-2 border-blue-600 pb-2 -mb-px font-semibold' : 'text-zinc-500 hover:text-zinc-700'" class="text-[13px] uppercase tracking-tight">
                [[ $t('node.wallets.tab_managers') ]]
              </button>
            </div>

            <div v-show="activeTab === 'wallets'" class="space-y-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative flex items-center w-64">
                    <input type="text" v-model="searchQuery" :placeholder="$t('node.wallets.search_placeholder')" class="w-full pl-4 pr-9 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
                    <button type="button" v-show="searchQuery" @click="searchQuery = ''" class="absolute right-2 p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-200/80 shrink-0" :title="$t('node.search_clear')" :aria-label="$t('node.search_clear')">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                  <span class="text-[13px] text-zinc-500">[[ $t('node.wallets.all_wallets') ]]</span>
                </div>
                <button type="button" @click="openAddWallet" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  [[ $t('node.wallets.add_wallet') ]]
                </button>
              </div>
              <p v-if="loadError" class="text-red-600 text-[13px]">[[ loadError ]]</p>
              <p v-if="loading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
              <div v-else class="overflow-x-auto rounded-xl border border-zinc-200">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_name') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_address') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_blockchain') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider w-24">[[ $t('node.wallets.col_actions') ]]</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="w in filteredWallets" :key="w.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ w.name ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">
                        <div class="flex flex-col gap-0.5">
                          <div class="flex items-center gap-1.5">
                            <span :title="w.tron_address">[[ shortAddress(w.tron_address) ]]</span>
                            <button type="button" @click.stop="copyToClipboard(w.tron_address, 'TRON')" class="p-1 text-zinc-400 hover:text-amber-600 rounded" :title="$t('node.wallets.copy_address')">
                              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                            </button>
                          </div>
                          <div v-if="w.ethereum_address" class="flex items-center gap-1.5">
                            <span class="text-[11px] text-zinc-400" :title="w.ethereum_address">[[ shortAddress(w.ethereum_address) ]]</span>
                            <button type="button" @click.stop="copyToClipboard(w.ethereum_address, 'ETH')" class="p-1 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallets.copy_address')">
                              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                            </button>
                          </div>
                        </div>
                      </td>
                      <td class="px-4 py-3">
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">TRON</span>
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800 ml-1">Ethereum</span>
                      </td>
                      <td class="px-4 py-3">
                        <div class="flex items-center gap-0.5">
                          <button type="button" @click="openDidDoc(w)" class="p-1.5 text-zinc-400 hover:text-indigo-600 rounded shrink-0" :title="$t('node.wallets.view_diddoc')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                          </button>
                          <button type="button" @click="openEdit(w)" class="p-1.5 text-zinc-400 hover:text-blue-600 rounded shrink-0" :title="$t('node.wallets.edit')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                          </button>
                          <button type="button" @click="openDelete(w)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded shrink-0" :title="$t('node.wallets.delete')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                    <tr v-if="!loading && filteredWallets.length === 0">
                      <td colspan="4" class="px-4 py-8 text-center text-zinc-500 text-[13px]">—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-show="activeTab === 'managers'" class="space-y-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative flex items-center w-64">
                    <input type="text" v-model="searchQuery" :placeholder="$t('node.wallets.search_placeholder')" class="w-full pl-4 pr-9 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
                    <button type="button" v-show="searchQuery" @click="searchQuery = ''" class="absolute right-2 p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-200/80 shrink-0" :title="$t('node.search_clear')" :aria-label="$t('node.search_clear')">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                </div>
                <button type="button" @click="openAddManager" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  [[ $t('node.wallets.add_manager') ]]
                </button>
              </div>
              <p v-if="managerLoadError" class="text-red-600 text-[13px]">[[ managerLoadError ]]</p>
              <div v-if="!managerLoadError && filteredManagers.length === 0" class="py-8 text-center text-zinc-500 text-[13px]">[[ $t('node.wallets.managers_empty') ]]</div>
              <div v-else-if="!managerLoadError" class="overflow-x-auto rounded-xl border border-zinc-200">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_name') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_address') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_blockchain') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider w-24">[[ $t('node.wallets.col_actions') ]]</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="m in filteredManagers" :key="m.id" class="border-b border-zinc-100 hover:bg-zinc-50/80">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ m.nickname ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">
                        <div class="flex items-center gap-1.5">
                          <span :title="m.wallet_address">[[ shortAddress(m.wallet_address) ]]</span>
                          <button type="button" @click.stop="copyToClipboard(m.wallet_address, 'OK')" class="p-1 text-zinc-400 hover:text-blue-600 rounded shrink-0" :title="$t('node.wallets.copy_address')">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                          </button>
                        </div>
                      </td>
                      <td class="px-4 py-3">
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-800">[[ m.blockchain ]]</span>
                      </td>
                      <td class="px-4 py-3">
                        <div class="flex items-center gap-0.5">
                          <button type="button" @click="openManagerDidDoc(m)" class="p-1.5 text-zinc-400 hover:text-indigo-600 rounded shrink-0" :title="$t('node.wallets.view_diddoc')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                          </button>
                          <button type="button" @click="openRevokeManager(m)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded shrink-0" :title="$t('node.wallets.manager_revoke_btn')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <modal :show="showAddWalletModal" :title="$t('node.wallets.modal_add_title')" @close="closeAddWallet">
        <div class="space-y-4">
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_name_label') ]]</label>
            <input type="text" v-model="addForm.name" @input="submitError = ''" :placeholder="$t('node.wallets.modal_add_name_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_mnemonic_label') ]]</label>
            <textarea v-model="addForm.mnemonic" @input="submitError = ''" rows="4" :placeholder="$t('node.wallets.modal_add_mnemonic_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"></textarea>
            <p class="mt-1.5 text-[12px] text-zinc-400">[[ $t('node.wallets.modal_add_mnemonic_hint') ]]</p>
          </div>
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
        </div>
        <template slot="footer">
          <button type="button" @click="closeAddWallet" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">[[ $t('node.wallets.cancel') ]]</button>
          <button type="button" @click="submitAddWallet" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-60">[[ $t('node.wallets.create') ]]</button>
        </template>
      </modal>

      <modal :show="showEditModal" :title="$t('node.wallets.modal_edit_title')" @close="closeEdit">
        <div class="space-y-4">
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_edit_name_label') ]]</label>
            <input type="text" v-model="editForm.name" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
        </div>
        <template slot="footer">
          <button type="button" @click="closeEdit" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">[[ $t('node.wallets.cancel') ]]</button>
          <button type="button" @click="submitEdit" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-60">[[ $t('node.wallets.save') ]]</button>
        </template>
      </modal>

      <modal :show="showDeleteModal" :title="$t('node.wallets.delete_confirm_title')" @close="closeDelete">
        <p class="text-zinc-700">[[ deleteWallet ? $t('node.wallets.delete_confirm_message', { name: deleteWallet.name }) : '' ]]</p>
        <p v-if="submitError" class="mt-2 text-red-600 text-[13px]">[[ submitError ]]</p>
        <template slot="footer">
          <button type="button" @click="closeDelete" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">[[ $t('node.wallets.cancel') ]]</button>
          <button type="button" @click="confirmDelete" :disabled="submitting" class="px-4 py-2 bg-red-600 text-white rounded-lg text-[13px] font-semibold hover:bg-red-700 disabled:opacity-60">[[ $t('node.wallets.delete') ]]</button>
        </template>
      </modal>

      <diddoc-modal :show="showDidDocModal" :title="$t('node.wallets.diddoc_modal_title')" :subtitle="didDocWallet ? ($t('node.wallets.diddoc_modal_wallet') + ': ' + didDocWallet.name) : ''" :fetch-url="didDocWallet ? (WALLETS_API + '/' + didDocWallet.id + '/did-documents') : ''" @close="closeDidDoc"></diddoc-modal>
      <diddoc-modal :show="showManagerDidDocModal" :title="$t('node.wallets.manager_diddoc_modal_title')" :subtitle="managerDidDocManager ? ($t('node.wallets.manager_nickname') + ': ' + managerDidDocManager.nickname) : ''" :fetch-url="managerDidDocManager ? (WALLETS_API + '/managers/' + managerDidDocManager.id + '/did-document') : ''" @close="closeManagerDidDoc"></diddoc-modal>

      <modal :show="showAddManagerModal" :title="$t('node.wallets.modal_add_manager_title')" @close="closeAddManagerModal">
        <div class="space-y-4">
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_manager_address_label') ]]</label>
            <input type="text" v-model="addManagerForm.wallet_address" @input="submitError = ''" :placeholder="$t('node.wallets.modal_add_manager_address_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] font-mono placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_manager_blockchain_label') ]]</label>
            <select v-model="addManagerForm.blockchain" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              <option value="tron">TRON</option>
              <option value="ethereum">Ethereum</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_manager_nickname_label') ]]</label>
            <input type="text" v-model="addManagerForm.nickname" @input="submitError = ''" :placeholder="$t('node.wallets.modal_add_manager_nickname_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
        </div>
        <template slot="footer">
          <button type="button" @click="closeAddManagerModal" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">[[ $t('node.wallets.cancel') ]]</button>
          <button type="button" @click="submitAddManager" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-60">[[ $t('node.wallets.add_manager') ]]</button>
        </template>
      </modal>

      <modal :show="showRevokeManagerModal" :title="$t('node.wallets.manager_revoke_title')" @close="closeRevokeManager">
        <p class="text-zinc-700">[[ revokeManagerTarget ? $t('node.wallets.manager_revoke_message', { name: revokeManagerTarget.nickname }) : '' ]]</p>
        <p v-if="submitError" class="mt-2 text-red-600 text-[13px]">[[ submitError ]]</p>
        <template slot="footer">
          <button type="button" @click="closeRevokeManager" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">[[ $t('node.wallets.cancel') ]]</button>
          <button type="button" @click="confirmRevokeManager" :disabled="submitting" class="px-4 py-2 bg-red-600 text-white rounded-lg text-[13px] font-semibold hover:bg-red-700 disabled:opacity-60">[[ $t('node.wallets.manager_revoke_btn') ]]</button>
        </template>
      </modal>

      <div v-if="copyFeedback" class="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 bg-zinc-800 text-white text-[13px] rounded-lg shadow-lg">[[ $t('node.wallets.copied') ]]</div>
    </div>
    `
    });
})();
