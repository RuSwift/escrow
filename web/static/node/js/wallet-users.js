/**
 * Vue 2 компонент: Пользователи (загрузка с API, CRUD, баланс, история, DID Document).
 */
(function() {
    var API_BASE = '/v1';
    var USERS_API = API_BASE + '/users';

    Vue.component('wallet-users', {
        delimiters: ['[[', ']]'],
        props: { isNodeInitialized: { type: Boolean, default: false } },
        data: function() {
            return {
                USERS_API: USERS_API,
                userList: [],
                total: 0,
                loading: false,
                loadError: '',
                currentPage: 1,
                pageSize: 20,
                searchQuery: '',
                blockchainFilter: 'all',
                showAddModal: false,
                showEditModal: false,
                showBalanceModal: false,
                showHistoryModal: false,
                showDeleteModal: false,
                showDidDocModal: false,
                addForm: { wallet_address: '', blockchain: 'tron', nickname: '', is_verified: false, access_to_admin_panel: false },
                editForm: { nickname: '', is_verified: false, access_to_admin_panel: false },
                balanceForm: { operation_type: 'replenish', amount: '' },
                editUser: null,
                balanceUser: null,
                historyUser: null,
                historyList: [],
                historyLoading: false,
                deleteUser: null,
                didDocUser: null,
                submitting: false,
                submitError: ''
            };
        },
        computed: {
            totalPages: function() {
                return Math.max(1, Math.ceil(this.total / this.pageSize));
            },
            fromCount: function() {
                if (this.total === 0) return 0;
                return (this.currentPage - 1) * this.pageSize + 1;
            },
            toCount: function() {
                return Math.min(this.currentPage * this.pageSize, this.total);
            }
        },
        watch: {
            currentPage: function() { this.loadUsers(); },
            searchQuery: function() { this.currentPage = 1; this.loadUsers(); },
            blockchainFilter: function() { this.currentPage = 1; this.loadUsers(); }
        },
        mounted: function() {
            this.loadUsers();
        },
        methods: {
            formatDate: function(isoStr) {
                if (!isoStr) return '—';
                try {
                    var d = new Date(isoStr);
                    if (isNaN(d.getTime())) return isoStr;
                    var day = ('0' + d.getDate()).slice(-2);
                    var month = ('0' + (d.getMonth() + 1)).slice(-2);
                    var year = d.getFullYear();
                    var h = ('0' + d.getHours()).slice(-2);
                    var m = ('0' + d.getMinutes()).slice(-2);
                    var s = ('0' + d.getSeconds()).slice(-2);
                    return day + '.' + month + '.' + year + ', ' + h + ':' + m + ':' + s;
                } catch (e) {
                    return isoStr;
                }
            },
            formatBalance: function(val) {
                if (val == null) return '0,00';
                var n = Number(val);
                if (isNaN(n)) return String(val);
                return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            },
            _errorDetail: function(data) {
                if (!data) return '';
                var d = data.detail;
                if (typeof d === 'string') return d;
                if (Array.isArray(d) && d.length > 0) {
                    return d.map(function(x) { return x.msg || (x.loc ? (x.loc.join('.') + ': ' + (x.msg || '')) : JSON.stringify(x)); }).join('; ');
                }
                return '';
            },
            loadUsers: function() {
                var self = this;
                self.loading = true;
                self.loadError = '';
                var params = new URLSearchParams();
                params.set('page', String(this.currentPage));
                params.set('page_size', String(this.pageSize));
                if (this.searchQuery && this.searchQuery.trim()) params.set('search', this.searchQuery.trim());
                if (this.blockchainFilter && this.blockchainFilter !== 'all') params.set('blockchain', this.blockchainFilter);
                var url = USERS_API + '?' + params.toString();
                fetch(url, { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(self._errorDetail(d) || self.$t('node.wallet_users.load_error')); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.userList = data.users || [];
                        self.total = data.total || 0;
                        self.loading = false;
                    })
                    .catch(function(err) {
                        self.loadError = err.message || self.$t('node.wallet_users.load_error');
                        self.loading = false;
                    });
            },
            shortAddress: function(addr) {
                if (!addr || addr.length < 14) return addr;
                return addr.substring(0, 8) + '...' + addr.substring(addr.length - 6);
            },
            initial: function(u) {
                return (u.nickname && u.nickname[0]) ? u.nickname[0].toUpperCase() : '?';
            },
            resetFilters: function() {
                this.searchQuery = '';
                this.blockchainFilter = 'all';
                this.currentPage = 1;
                this.loadUsers();
            },
            openAdd: function() {
                this.addForm = { wallet_address: '', blockchain: 'tron', nickname: '', is_verified: false, access_to_admin_panel: false };
                this.submitError = '';
                this.showAddModal = true;
            },
            closeAddModal: function() { this.showAddModal = false; },
            submitAdd: function() {
                var self = this;
                self.submitError = '';
                var addr = (this.addForm.wallet_address || '').trim();
                var nick = (this.addForm.nickname || '').trim();
                if (!addr) { self.submitError = self.$t('node.wallets.manager_add_error_address'); return; }
                if (!nick) { self.submitError = self.$t('node.wallets.manager_add_error_nickname'); return; }
                self.submitting = true;
                fetch(USERS_API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        wallet_address: addr,
                        blockchain: (this.addForm.blockchain || 'tron').toLowerCase(),
                        nickname: nick,
                        is_verified: !!this.addForm.is_verified,
                        access_to_admin_panel: !!this.addForm.access_to_admin_panel
                    })
                })
                    .then(function(r) {
                        return r.json().then(function(d) { return { ok: r.ok, data: d }; }).catch(function() { return { ok: false, data: {} }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data.id != null) {
                            self.userList.unshift(result.data);
                            self.total = (self.total || 0) + 1;
                            self.closeAddModal();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.wallet_users.error_create');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallet_users.error_create');
                    });
            },
            openEdit: function(u) {
                this.editUser = u;
                this.editForm = { nickname: u.nickname || '', is_verified: !!u.is_verified, access_to_admin_panel: !!u.access_to_admin_panel };
                this.submitError = '';
                this.showEditModal = true;
            },
            closeEditModal: function() { this.showEditModal = false; this.editUser = null; },
            submitEdit: function() {
                var self = this;
                if (!this.editUser) return;
                self.submitError = '';
                var nick = (this.editForm.nickname || '').trim();
                if (!nick) { self.submitError = self.$t('node.wallets.manager_add_error_nickname'); return; }
                self.submitting = true;
                fetch(USERS_API + '/' + this.editUser.id, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        nickname: nick,
                        is_verified: !!this.editForm.is_verified,
                        access_to_admin_panel: !!this.editForm.access_to_admin_panel
                    })
                })
                    .then(function(r) {
                        return r.json().then(function(d) { return { ok: r.ok, data: d }; }).catch(function() { return { ok: false, data: {} }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data) {
                            var idx = self.userList.findIndex(function(x) { return x.id === self.editUser.id; });
                            if (idx !== -1) self.userList.splice(idx, 1, result.data);
                            self.closeEditModal();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.wallet_users.error_update');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallet_users.error_update');
                    });
            },
            openBalance: function(u) {
                this.balanceUser = u;
                this.balanceForm = { operation_type: 'replenish', amount: '' };
                this.submitError = '';
                this.showBalanceModal = true;
            },
            closeBalanceModal: function() { this.showBalanceModal = false; this.balanceUser = null; },
            submitBalance: function() {
                var self = this;
                if (!this.balanceUser) return;
                var amount = parseFloat(String(this.balanceForm.amount).replace(',', '.'), 10);
                if (isNaN(amount) || amount <= 0) { self.submitError = self.$t('node.wallet_users.amount_placeholder'); return; }
                self.submitError = '';
                self.submitting = true;
                fetch(USERS_API + '/' + this.balanceUser.id + '/balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        operation_type: this.balanceForm.operation_type,
                        amount: amount
                    })
                })
                    .then(function(r) {
                        return r.json().then(function(d) { return { ok: r.ok, data: d }; }).catch(function() { return { ok: false, data: {} }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data) {
                            var idx = self.userList.findIndex(function(x) { return x.id === self.balanceUser.id; });
                            if (idx !== -1) self.userList.splice(idx, 1, result.data);
                            self.closeBalanceModal();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.wallet_users.error_balance');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallet_users.error_balance');
                    });
            },
            openHistory: function(u) {
                this.historyUser = u;
                this.historyList = [];
                this.historyLoading = true;
                this.showHistoryModal = true;
                var self = this;
                fetch(USERS_API + '/' + u.id + '/billing?page=1&page_size=50', { credentials: 'same-origin' })
                    .then(function(r) { return r.ok ? r.json() : []; })
                    .then(function(data) {
                        self.historyList = data.transactions || [];
                        self.historyLoading = false;
                    })
                    .catch(function() { self.historyLoading = false; self.historyList = []; });
            },
            closeHistoryModal: function() { this.showHistoryModal = false; this.historyUser = null; },
            openDelete: function(u) {
                this.deleteUser = u;
                this.submitError = '';
                this.showDeleteModal = true;
            },
            closeDeleteModal: function() { this.showDeleteModal = false; this.deleteUser = null; },
            confirmDelete: function() {
                var self = this;
                if (!this.deleteUser) return;
                var id = this.deleteUser.id;
                self.submitting = true;
                fetch(USERS_API + '/' + id, { method: 'DELETE', credentials: 'same-origin' })
                    .then(function(r) {
                        self.submitting = false;
                        if (r.ok) {
                            self.userList = self.userList.filter(function(x) { return x.id !== id; });
                            self.total = Math.max(0, self.total - 1);
                            self.closeDeleteModal();
                        } else {
                            return r.json().then(function(d) { self.submitError = self._errorDetail(d) || self.$t('node.wallet_users.error_delete'); });
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.wallet_users.error_delete');
                    });
            },
            openDidDoc: function(u) {
                this.didDocUser = u;
                this.showDidDocModal = true;
            },
            closeDidDoc: function() {
                this.showDidDocModal = false;
                this.didDocUser = null;
            }
        },
        template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">[[ $t('node.sidebar.wallet-users') ]]</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.wallet_users.title') ]]</span>
          </div>
          <div class="p-6">
            <h2 class="text-xl font-bold text-zinc-900 mb-1 tracking-tight">[[ $t('node.wallet_users.title') ]]</h2>
            <p class="text-[13px] text-zinc-500 mb-6">[[ $t('node.wallet_users.subtitle') ]]</p>
            <p v-if="submitError" class="text-red-600 text-[13px] mb-3">[[ submitError ]]</p>
            <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div class="flex flex-wrap items-center gap-2">
                <div class="flex-1 min-w-[200px] max-w-md">
                  <input type="text" v-model="searchQuery" :placeholder="$t('node.wallet_users.search_placeholder')" class="w-full px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
                </div>
                <select v-model="blockchainFilter" class="px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] text-zinc-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                  <option value="all">[[ $t('node.wallet_users.all_blockchains') ]]</option>
                  <option value="tron">TRON</option>
                  <option value="ethereum">Ethereum</option>
                </select>
                <button type="button" @click="resetFilters" class="px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] font-medium text-zinc-600 hover:bg-zinc-50">[[ $t('node.wallet_users.reset') ]]</button>
                <button type="button" @click="openAdd" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  [[ $t('node.wallet_users.add_user') ]]
                </button>
              </div>
            </div>
            <p v-if="loadError" class="text-red-600 text-[13px]">[[ loadError ]]</p>
            <p v-if="loading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
            <div v-else-if="userList.length === 0" class="py-8 text-center text-zinc-500 text-[13px]">[[ $t('node.wallet_users.empty') ]]</div>
            <div v-else class="overflow-x-auto rounded-xl border border-zinc-200">
              <table class="w-full text-left text-[13px]">
                <thead class="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_id') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_wallet_address') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_blockchain') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_name') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_verified') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_panel_access') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_balance') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_created') ]]</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.wallet_users.col_actions') ]]</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="u in userList" :key="u.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                    <td class="px-4 py-3 font-mono text-zinc-600">[[ u.id ]]</td>
                    <td class="px-4 py-3 font-mono text-zinc-700">[[ shortAddress(u.wallet_address) ]]</td>
                    <td class="px-4 py-3"><span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">[[ (u.blockchain || '').toUpperCase() ]]</span></td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="w-7 h-7 rounded-full bg-zinc-200 flex items-center justify-center text-[11px] font-bold text-zinc-600 shrink-0">[[ initial(u) ]]</span>
                      <span class="text-zinc-800">[[ u.nickname ]]</span>
                    </td>
                    <td class="px-4 py-3">
                      <span v-if="u.is_verified" class="inline-flex items-center gap-1.5 text-emerald-600"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>[[ $t('node.wallet_users.verified_yes') ]]</span>
                      <span v-else class="inline-flex items-center gap-1.5 text-zinc-500"><span class="w-1.5 h-1.5 rounded-full bg-zinc-400"></span>[[ $t('node.wallet_users.verified_no') ]]</span>
                    </td>
                    <td class="px-4 py-3"><span class="w-2 h-2 rounded-full inline-block" :class="u.access_to_admin_panel ? 'bg-blue-500' : 'bg-zinc-300 opacity-50'"></span></td>
                    <td class="px-4 py-3">
                      <button type="button" @click="openBalance(u)" class="text-zinc-800 hover:text-blue-600 text-left">[[ formatBalance(u.balance_usdt) ]] USDT</button>
                    </td>
                    <td class="px-4 py-3 text-zinc-600">[[ formatDate(u.created_at) ]]</td>
                    <td class="px-4 py-3 flex items-center gap-1">
                      <button type="button" @click="openEdit(u)" class="p-1.5 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallet_users.edit')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg></button>
                      <button type="button" @click="openDidDoc(u)" class="p-1.5 text-zinc-400 hover:text-emerald-600 rounded" :title="$t('node.wallet_users.view_diddoc')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg></button>
                      <button type="button" @click="openHistory(u)" class="p-1.5 text-zinc-400 hover:text-zinc-600 rounded" :title="$t('node.wallet_users.history')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg></button>
                      <button type="button" @click="openDelete(u)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" :title="$t('node.wallet_users.delete')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="!loading && userList.length > 0" class="mt-4 flex flex-wrap items-center justify-between gap-4">
              <p class="text-[13px] text-zinc-500">[[ fromCount ]]-[[ toCount ]] / [[ total ]]</p>
              <div class="flex items-center gap-1">
                <button type="button" @click="currentPage = currentPage - 1" :disabled="currentPage <= 1" class="px-3 py-1.5 rounded-lg text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50">[[ $t('node.wallet_users.prev') ]]</button>
                <span class="px-2 text-[13px] text-zinc-500">[[ currentPage ]] / [[ totalPages ]]</span>
                <button type="button" @click="currentPage = currentPage + 1" :disabled="currentPage >= totalPages" class="px-3 py-1.5 rounded-lg text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50">[[ $t('node.wallet_users.next') ]]</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <modal :show="showAddModal" :title="$t('node.wallet_users.modal_add_title')" @close="closeAddModal">
        <div class="space-y-4">
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_wallet_address') ]]</label><input type="text" v-model="addForm.wallet_address" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px]"></div>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_blockchain') ]]</label><select v-model="addForm.blockchain" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px]"><option value="tron">TRON</option><option value="ethereum">Ethereum</option></select></div>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_name') ]]</label><input type="text" v-model="addForm.nickname" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px]"></div>
          <div class="flex items-center gap-4"><label class="flex items-center gap-2"><input type="checkbox" v-model="addForm.is_verified"> [[ $t('node.wallet_users.col_verified') ]]</label><label class="flex items-center gap-2"><input type="checkbox" v-model="addForm.access_to_admin_panel"> [[ $t('node.wallet_users.col_panel_access') ]]</label></div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeAddModal" class="px-4 py-2 text-zinc-600 hover:bg-zinc-100 rounded-lg text-[13px]">[[ $t('node.wallet_users.cancel') ]]</button>
          <button type="button" @click="submitAdd" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.wallet_users.create') ]]</button>
        </template>
      </modal>

      <modal :show="showEditModal" :title="$t('node.wallet_users.modal_edit_title')" @close="closeEditModal">
        <div v-if="editUser" class="space-y-4">
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_wallet_address') ]]</label><input type="text" :value="editUser.wallet_address" disabled class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] bg-zinc-50"><p class="text-[12px] text-zinc-500 mt-0.5">[[ $t('node.wallet_users.address_readonly') ]]</p></div>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_blockchain') ]]</label><input type="text" :value="editUser.blockchain" disabled class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] bg-zinc-50"></div>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.col_name') ]]</label><input type="text" v-model="editForm.nickname" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px]"></div>
          <div class="flex items-center gap-4"><label class="flex items-center gap-2"><input type="checkbox" v-model="editForm.is_verified"> [[ $t('node.wallet_users.col_verified') ]]</label><label class="flex items-center gap-2"><input type="checkbox" v-model="editForm.access_to_admin_panel"> [[ $t('node.wallet_users.col_panel_access') ]]</label></div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeEditModal" class="px-4 py-2 text-zinc-600 hover:bg-zinc-100 rounded-lg text-[13px]">[[ $t('node.wallet_users.cancel') ]]</button>
          <button type="button" @click="submitEdit" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.wallet_users.save') ]]</button>
        </template>
      </modal>

      <modal :show="showBalanceModal" :title="$t('node.wallet_users.modal_balance_title')" @close="closeBalanceModal">
        <div v-if="balanceUser" class="space-y-4">
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
          <p class="text-[13px]">[[ $t('node.wallet_users.user_label') ]]: <strong>[[ balanceUser.nickname ]]</strong></p>
          <p class="text-[13px]">[[ $t('node.wallet_users.current_balance') ]]: <strong class="text-blue-600">[[ formatBalance(balanceUser.balance_usdt) ]] USDT</strong></p>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.operation_type') ]]</label><div class="flex gap-2"><button type="button" @click="balanceForm.operation_type = 'replenish'" :class="balanceForm.operation_type === 'replenish' ? 'bg-emerald-600 text-white' : 'bg-zinc-200 text-zinc-700'" class="px-4 py-2 rounded-lg text-[13px] font-medium">+ [[ $t('node.wallet_users.replenish') ]]</button><button type="button" @click="balanceForm.operation_type = 'withdraw'" :class="balanceForm.operation_type === 'withdraw' ? 'bg-red-600 text-white' : 'bg-zinc-200 text-zinc-700'" class="px-4 py-2 rounded-lg text-[13px] font-medium">- [[ $t('node.wallet_users.withdraw') ]]</button></div></div>
          <div><label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.wallet_users.amount_usdt') ]]</label><input type="text" v-model="balanceForm.amount" :placeholder="$t('node.wallet_users.amount_placeholder')" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px]"></div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeBalanceModal" class="px-4 py-2 text-zinc-600 hover:bg-zinc-100 rounded-lg text-[13px]">[[ $t('node.wallet_users.cancel') ]]</button>
          <button type="button" @click="submitBalance" :disabled="submitting" class="px-4 py-2 bg-emerald-600 text-white rounded-lg text-[13px] font-semibold hover:bg-emerald-700 disabled:opacity-50">[[ balanceForm.operation_type === 'replenish' ? $t('node.wallet_users.replenish') : $t('node.wallet_users.withdraw') ]]</button>
        </template>
      </modal>

      <modal :show="showHistoryModal" :title="$t('node.wallet_users.modal_history_title')" size="large" @close="closeHistoryModal">
        <div v-if="historyUser" class="space-y-4">
          <p class="text-[13px]">[[ $t('node.wallet_users.user_label') ]]: <strong>[[ historyUser.nickname ]]</strong></p>
          <p class="text-[13px]">[[ $t('node.wallet_users.current_balance') ]]: <strong>[[ formatBalance(historyUser.balance_usdt) ]] USDT</strong></p>
          <p v-if="historyLoading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
          <div v-else-if="historyList.length === 0" class="py-8 text-center text-zinc-500 text-[13px]">[[ $t('node.wallet_users.history_empty') ]]</div>
          <div v-else class="overflow-x-auto"><table class="w-full text-[13px]"><thead class="bg-zinc-50 border-b"><tr><th class="px-3 py-2 text-left">ID</th><th class="px-3 py-2 text-left">[[ $t('node.wallet_users.amount_usdt') ]]</th><th class="px-3 py-2 text-left">[[ $t('node.wallet_users.col_created') ]]</th></tr></thead><tbody><tr v-for="t in historyList" :key="t.id" class="border-b"><td class="px-3 py-2">[[ t.id ]]</td><td class="px-3 py-2" :class="t.usdt_amount >= 0 ? 'text-emerald-600' : 'text-red-600'">[[ t.usdt_amount >= 0 ? '+' : '' ]][[ t.usdt_amount ]]</td><td class="px-3 py-2">[[ formatDate(t.created_at) ]]</td></tr></tbody></table></div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeHistoryModal" class="px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-[13px] font-medium">[[ $t('node.wallet_users.close') ]]</button>
        </template>
      </modal>

      <modal-dialog :show="showDeleteModal" :title="$t('node.wallet_users.modal_delete_title')" :message="deleteUser ? ($t('node.wallet_users.delete_confirm_message') + ' ' + (deleteUser.nickname || '') + ' — ' + (deleteUser.wallet_address || '') + '. ' + $t('node.wallet_users.delete_irreversible')) : ''" :confirm-label="$t('node.wallet_users.delete')" :cancel-label="$t('node.wallet_users.cancel')" confirm-class="bg-red-600 hover:bg-red-700 text-white" @confirm="confirmDelete" @cancel="closeDeleteModal"></modal-dialog>

      <diddoc-modal :show="showDidDocModal" :title="$t('node.wallet_users.diddoc_title')" :subtitle="didDocUser ? ($t('node.wallet_users.col_name') + ': ' + didDocUser.nickname) : ''" :fetch-url="didDocUser ? (USERS_API + '/' + didDocUser.id + '/did-document') : ''" @close="closeDidDoc"></diddoc-modal>
    </div>
    `
    });
})();
