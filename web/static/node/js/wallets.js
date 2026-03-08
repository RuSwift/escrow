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
                activeTab: 'wallets',
                searchQuery: '',
                walletList: [],
                managerList: [],
                loading: false,
                loadError: '',
                showAddWalletModal: false,
                showEditModal: false,
                showDeleteModal: false,
                addForm: { name: '', mnemonic: '' },
                editForm: { name: '' },
                editWallet: null,
                deleteWallet: null,
                submitting: false,
                submitError: ''
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
                fetch(WALLETS_API + '/managers', { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || ''); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.managerList = data.managers || [];
                    })
                    .catch(function() {
                        self.managerList = [];
                    });
            },
            shortAddress: function(addr) {
                if (!addr || addr.length < 14) return addr;
                return addr.substring(0, 6) + '...' + addr.substring(addr.length - 4);
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
                if (!this.addForm.name.trim()) return;
                if (!this.addForm.mnemonic.trim()) return;
                self.submitting = true;
                self.submitError = '';
                fetch(WALLETS_API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: self.addForm.name.trim(), mnemonic: self.addForm.mnemonic.trim() })
                })
                    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data.id) {
                            self.walletList.unshift(result.data);
                            self.closeAddWallet();
                        } else {
                            self.submitError = (result.data.detail || self.$t('node.wallets.error_create'));
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallets.error_create');
                    });
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
                            self.submitError = (result.data.detail || self.$t('node.wallets.error_update'));
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
                            return r.json().then(function(d) { self.submitError = d.detail || self.$t('node.wallets.error_delete'); });
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
                  <input type="text" v-model="searchQuery" :placeholder="$t('node.wallets.search_placeholder')" class="px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] w-64 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
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
                        <span :title="w.tron_address">[[ shortAddress(w.tron_address) ]]</span>
                        <span v-if="w.ethereum_address" class="block text-[11px] text-zinc-400" :title="w.ethereum_address">[[ shortAddress(w.ethereum_address) ]]</span>
                      </td>
                      <td class="px-4 py-3">
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">TRON</span>
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800 ml-1">Ethereum</span>
                      </td>
                      <td class="px-4 py-3">
                        <button type="button" @click="openEdit(w)" class="p-1.5 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallets.edit')">
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        </button>
                        <button type="button" @click="openDelete(w)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" :title="$t('node.wallets.delete')">
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
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
              <div class="flex flex-wrap items-center gap-3">
                <input type="text" v-model="searchQuery" :placeholder="$t('node.wallets.search_placeholder')" class="px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] w-64 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              </div>
              <div v-if="filteredManagers.length === 0" class="py-8 text-center text-zinc-500 text-[13px]">[[ $t('node.wallets.managers_empty') ]]</div>
              <div v-else class="overflow-x-auto rounded-xl border border-zinc-200">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_name') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_address') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallets.col_blockchain') ]]</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="m in filteredManagers" :key="m.id" class="border-b border-zinc-100 hover:bg-zinc-50/80">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ m.nickname ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">[[ shortAddress(m.wallet_address) ]]</td>
                      <td class="px-4 py-3">
                        <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-800">[[ m.blockchain ]]</span>
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
            <input type="text" v-model="addForm.name" :placeholder="$t('node.wallets.modal_add_name_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.wallets.modal_add_mnemonic_label') ]]</label>
            <textarea v-model="addForm.mnemonic" rows="4" :placeholder="$t('node.wallets.modal_add_mnemonic_placeholder')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"></textarea>
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
    </div>
    `
    });
})();
