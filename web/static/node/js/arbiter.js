/**
 * Vue 2 компонент: Арбитр.
 * Загрузка списка с API GET /v1/arbiter/addresses, CRUD через API.
 */
(function() {
    var API_BASE = '/v1';
    var ARBITER_API = API_BASE + '/arbiter';

    function formatDate(isoStr) {
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
    }

    function mapApiToDisplay(item) {
        return {
            id: item.id,
            name: item.name,
            tronAddress: item.tron_address || '',
            ethereumAddress: item.ethereum_address || '',
            is_active: item.is_active,
            role: item.is_active ? 'active' : 'backup',
            createdAt: formatDate(item.created_at),
            created_at: item.created_at,
            updated_at: item.updated_at
        };
    }

    Vue.component('arbiter', {
        delimiters: ['[[', ']]'],
        props: { isNodeInitialized: { type: Boolean, default: false } },
        data: function() {
            return {
                addresses: [],
                loading: false,
                loadError: '',
                showAddModal: false,
                showEditModal: false,
                showDeleteModal: false,
                addForm: { name: '', mnemonic: '' },
                editForm: { name: '' },
                editAddress: null,
                deleteAddress: null,
                submitting: false,
                submitError: ''
            };
        },
        mounted: function() {
            this.loadAddresses();
        },
        methods: {
            _errorDetail: function(data) {
                if (!data) return '';
                var d = data.detail;
                if (typeof d === 'string') return d;
                if (Array.isArray(d) && d.length > 0) {
                    return d.map(function(x) { return x.msg || (x.loc ? (x.loc.join('.') + ': ' + (x.msg || '')) : JSON.stringify(x)); }).join('; ');
                }
                return '';
            },
            loadAddresses: function() {
                var self = this;
                self.loading = true;
                self.loadError = '';
                fetch(ARBITER_API + '/addresses', { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(self._errorDetail(d) || self.$t('node.arbiter.load_error')); });
                        return r.json();
                    })
                    .then(function(data) {
                        self.addresses = (data.addresses || []).map(mapApiToDisplay);
                        self.loading = false;
                    })
                    .catch(function(err) {
                        self.loadError = err.message || self.$t('node.arbiter.load_error');
                        self.loading = false;
                    });
            },
            shortAddress: function(addr, head, tail) {
                if (!addr || addr.length < (head + tail + 3)) return addr;
                head = head || 10;
                tail = tail || 8;
                return addr.substring(0, head) + '...' + addr.substring(addr.length - tail);
            },
            copyToClipboard: function(text) {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text);
                }
            },
            openAdd: function() {
                this.addForm = { name: '', mnemonic: '' };
                this.submitError = '';
                this.showAddModal = true;
            },
            closeAddModal: function() {
                this.showAddModal = false;
            },
            submitAdd: function() {
                var self = this;
                self.submitError = '';
                var name = (this.addForm.name || '').trim();
                var mnemonic = (this.addForm.mnemonic || '').trim();
                if (!name) {
                    self.submitError = self.$t('node.wallets.error_name_required');
                    return;
                }
                if (!mnemonic) {
                    self.submitError = self.$t('node.wallets.error_mnemonic_required');
                    return;
                }
                self.submitting = true;
                fetch(ARBITER_API + '/addresses', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: name, mnemonic: mnemonic })
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, status: r.status, data: d };
                        }).catch(function() { return { ok: false, status: r.status, data: { detail: r.statusText } }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data) {
                            self.addresses.unshift(mapApiToDisplay(result.data));
                            self.closeAddModal();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.arbiter.error_add');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.arbiter.error_add');
                    });
            },
            openEdit: function(a) {
                this.editAddress = a;
                this.editForm = { name: (a && a.name) || '' };
                this.submitError = '';
                this.showEditModal = true;
            },
            closeEditModal: function() {
                this.showEditModal = false;
                this.editAddress = null;
            },
            submitEdit: function() {
                var self = this;
                if (!this.editAddress) { self.closeEditModal(); return; }
                self.submitError = '';
                var name = (this.editForm.name || '').trim();
                if (!name) {
                    self.submitError = self.$t('node.wallets.error_name_required');
                    return;
                }
                var id = this.editAddress.id;
                self.submitting = true;
                fetch(ARBITER_API + '/addresses/' + id + '/name', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: name })
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, data: d };
                        }).catch(function() { return { ok: false, data: { detail: r.statusText } }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data) {
                            var idx = self.addresses.findIndex(function(x) { return x.id === id; });
                            if (idx !== -1) self.addresses.splice(idx, 1, mapApiToDisplay(result.data));
                            self.closeEditModal();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.arbiter.error_edit');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.arbiter.error_edit');
                    });
            },
            openActivate: function(a) {
                var self = this;
                if (!a || a.is_active) return;
                var id = a.id;
                self.submitting = true;
                self.submitError = '';
                fetch(ARBITER_API + '/addresses/' + id + '/activate', {
                    method: 'POST',
                    credentials: 'same-origin'
                })
                    .then(function(r) {
                        return r.json().then(function(d) {
                            return { ok: r.ok, data: d };
                        }).catch(function() { return { ok: false, data: { detail: r.statusText } }; });
                    })
                    .then(function(result) {
                        self.submitting = false;
                        if (result.ok && result.data) {
                            self.loadAddresses();
                        } else {
                            self.submitError = self._errorDetail(result.data) || self.$t('node.arbiter.error_activate');
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.arbiter.error_activate');
                    });
            },
            openDelete: function(a) {
                this.deleteAddress = a;
                this.showDeleteModal = true;
            },
            closeDeleteModal: function() {
                this.showDeleteModal = false;
                this.deleteAddress = null;
            },
            confirmDelete: function() {
                var self = this;
                if (!this.deleteAddress) { self.closeDeleteModal(); return; }
                if (this.deleteAddress.is_active) {
                    self.submitError = self.$t('node.arbiter.error_delete');
                    return;
                }
                var id = this.deleteAddress.id;
                self.submitting = true;
                fetch(ARBITER_API + '/addresses/' + id, {
                    method: 'DELETE',
                    credentials: 'same-origin'
                })
                    .then(function(r) {
                        self.submitting = false;
                        if (r.ok) {
                            self.addresses = self.addresses.filter(function(x) { return x.id !== id; });
                            self.closeDeleteModal();
                        } else {
                            return r.json().then(function(d) {
                                self.submitError = self._errorDetail(d) || self.$t('node.arbiter.error_delete');
                            });
                        }
                    })
                    .catch(function(err) {
                        self.submitting = false;
                        self.submitError = err.message || self.$t('node.arbiter.error_delete');
                    });
            }
        },
        template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">[[ $t('node.sidebar.arbiter') ]]</nav>
        <div class="mb-6 rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3">
          <svg class="w-5 h-5 text-sky-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <p class="text-[13px] font-medium text-sky-900">Кошельки Арбитража участвуют в защищенных сделках</p>
        </div>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.sidebar.arbiter') ]]</span>
          </div>
          <div class="p-6">
            <p v-if="submitError" class="text-red-600 text-[13px] mb-3">[[ submitError ]]</p>
            <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
              <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Адреса арбитра</h3>
              <button type="button" @click="openAdd" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                [[ $t('node.arbiter.add_btn') ]]
              </button>
            </div>
            <p v-if="loadError" class="text-red-600 text-[13px]">[[ loadError ]]</p>
            <p v-if="loading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
            <div v-else-if="addresses.length === 0" class="py-8 text-center text-zinc-500 text-[13px]">[[ $t('node.arbiter.empty') ]]</div>
            <div v-else class="overflow-x-auto rounded-xl border border-zinc-200 fade-in-content">
              <table class="w-full text-left text-[13px]">
                <thead class="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Имя</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Роль</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">TRON адрес</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Ethereum адрес</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Создан</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in addresses" :key="a.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                    <td class="px-4 py-3 font-mono text-zinc-600">[[ a.id ]]</td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="text-zinc-800">[[ a.name ]]</span>
                      <button type="button" @click="openEdit(a)" class="p-1 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallets.edit')">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3">
                      <span v-if="a.role === 'active'" class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">[[ $t('node.arbiter.role_active') ]]</span>
                      <span v-else class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-700">[[ $t('node.arbiter.role_backup') ]]</span>
                    </td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="font-mono text-zinc-700">[[ shortAddress(a.tronAddress, 12, 8) ]]</span>
                      <button type="button" @click="copyToClipboard(a.tronAddress)" class="p-1 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallets.copy_address')">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="font-mono text-zinc-700">[[ shortAddress(a.ethereumAddress, 10, 8) ]]</span>
                      <button type="button" @click="copyToClipboard(a.ethereumAddress)" class="p-1 text-zinc-400 hover:text-blue-600 rounded" :title="$t('node.wallets.copy_address')">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3 text-zinc-600">[[ a.createdAt ]]</td>
                    <td class="px-4 py-3 flex items-center gap-1">
                      <button v-if="!a.is_active" type="button" @click="openActivate(a)" :disabled="submitting" class="px-2 py-1 text-[12px] font-medium text-blue-600 hover:bg-blue-50 rounded">[[ $t('node.arbiter.activate_btn') ]]</button>
                      <button type="button" @click="openDelete(a)" :disabled="submitting" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" :title="$t('node.arbiter.delete_btn')">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <modal :show="showAddModal" :title="$t('node.arbiter.modal_add_title')" @close="closeAddModal">
        <div class="space-y-4">
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
          <div>
            <label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.arbiter.modal_add_name_label') ]]</label>
            <input type="text" v-model="addForm.name" :placeholder="$t('node.arbiter.modal_add_name_placeholder')" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <div>
            <label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.arbiter.modal_add_mnemonic_label') ]]</label>
            <input type="text" v-model="addForm.mnemonic" :placeholder="$t('node.arbiter.modal_add_mnemonic_placeholder')" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeAddModal" class="px-4 py-2 text-zinc-600 hover:bg-zinc-100 rounded-lg text-[13px] font-medium">[[ $t('node.arbiter.cancel') ]]</button>
          <button type="button" @click="submitAdd" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.arbiter.create') ]]</button>
        </template>
      </modal>

      <modal :show="showEditModal" :title="$t('node.arbiter.modal_edit_title')" @close="closeEditModal">
        <div class="space-y-4">
          <p v-if="submitError" class="text-red-600 text-[13px]">[[ submitError ]]</p>
          <div>
            <label class="block text-[13px] font-medium text-zinc-700 mb-1">[[ $t('node.arbiter.modal_add_name_label') ]]</label>
            <input type="text" v-model="editForm.name" :placeholder="$t('node.arbiter.modal_add_name_placeholder')" class="w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeEditModal" class="px-4 py-2 text-zinc-600 hover:bg-zinc-100 rounded-lg text-[13px] font-medium">[[ $t('node.arbiter.cancel') ]]</button>
          <button type="button" @click="submitEdit" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.arbiter.save') ]]</button>
        </template>
      </modal>

      <modal-dialog :show="showDeleteModal" :title="$t('node.arbiter.delete_confirm_title')" :message="deleteAddress ? $t('node.arbiter.delete_confirm_message', { name: deleteAddress.name }) : ''" :confirm-label="$t('node.arbiter.delete_btn')" :cancel-label="$t('node.arbiter.cancel')" confirm-class="bg-red-600 hover:bg-red-700 text-white" @confirm="confirmDelete" @cancel="closeDeleteModal">
      </modal-dialog>
    </div>
    `
    });
})();
