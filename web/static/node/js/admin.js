/**
 * Vue 2 компонент: Админ
 * Подключение: после vue.min.js, перед app.js
 */
(function() {
    var API_BASE = '/v1';
    var ADMIN_API = API_BASE + '/admin';

    function formatDate(isoStr) {
        if (!isoStr) return '';
        try {
            var d = new Date(isoStr);
            return isNaN(d.getTime()) ? isoStr : d.toLocaleString();
        } catch (e) { return isoStr; }
    }

    function setAdminCookie(token) {
        var d = new Date();
        d.setTime(d.getTime() + 24 * 60 * 60 * 1000);
        document.cookie = 'admin_token=' + token + '; expires=' + d.toUTCString() + '; path=/; SameSite=Lax';
    }

Vue.component('admin', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            loading: true,
            authError: false,
            saveError: '',
            loginError: '',
            loginForm: { username: '', password: '' },
            loginSubmitting: false,
            account: {
                username: '',
                createdAt: '',
                updatedAt: '',
                hasPassword: false,
                tronAddressesCount: 0
            },
            passwordForm: {
                oldPassword: '',
                newPassword: '',
                confirmPassword: ''
            },
            passwordSubmitting: false,
            passwordSuccess: '',
            tronForm: {
                label: '',
                address: ''
            },
            tronAddresses: [],
            tronSubmitting: false,
            tronError: '',
            tronSuccess: '',
            deleteModalShow: false,
            deleteTronItem: null,
            copyFeedbackId: null,
            adminSearchQuery: ''
        };
    },
    mounted: function() {
        this.loadData();
        var self = this;
        var searchEl = document.getElementById('header-search');
        if (searchEl) {
            searchEl.value = '';
            searchEl.dispatchEvent(new Event('input', { bubbles: true }));
            self.adminSearchQuery = '';
        }
        self._onHeaderSearch = function(e) {
            self.adminSearchQuery = (e.detail && e.detail.query !== undefined) ? e.detail.query : '';
        };
        window.addEventListener('header-search', self._onHeaderSearch);
    },
    beforeDestroy: function() {
        if (this._onHeaderSearch) window.removeEventListener('header-search', this._onHeaderSearch);
    },
    computed: {
        deleteModalTitle: function() {
            return this.$t('node.admin.delete_confirm_title');
        },
        deleteModalMessage: function() {
            if (!this.deleteTronItem) return '';
            var label = this.deleteTronItem.label || '';
            var addr = this.shortAddress(this.deleteTronItem.address || '');
            return this.$t('node.admin.delete_confirm_message', { label: label, address: addr });
        },
        filteredTronAddresses: function() {
            var q = (this.adminSearchQuery || '').trim().toLowerCase();
            if (!q) return this.tronAddresses;
            return this.tronAddresses.filter(function(a) {
                var label = (a.label || '').toLowerCase();
                var addr = (a.address || '').toLowerCase();
                return label.indexOf(q) !== -1 || addr.indexOf(q) !== -1;
            });
        }
    },
    methods: {
        loadData: function() {
            var self = this;
            self.loading = true;
            self.authError = false;
            self.loginError = '';
            self.saveError = '';
            Promise.all([
                fetch(ADMIN_API + '/info', { credentials: 'same-origin' }),
                fetch(ADMIN_API + '/tron-addresses', { credentials: 'same-origin' })
            ]).then(function(responses) {
                if (responses[0].status === 401 || responses[1].status === 401) {
                    self.authError = true;
                    self.loading = false;
                    return;
                }
                return Promise.all([responses[0].json(), responses[1].json()]).then(function(results) {
                    var info = results[0];
                    var list = results[1];
                    self.account = {
                        username: info.username || '',
                        createdAt: formatDate(info.created_at),
                        updatedAt: formatDate(info.updated_at),
                        hasPassword: info.has_password,
                        tronAddressesCount: info.tron_addresses_count || 0
                    };
                    self.tronAddresses = (list.addresses || []).map(function(a) {
                        return { id: a.id, label: a.label || '', address: a.tron_address || '', is_active: a.is_active };
                    });
                    self.loading = false;
                });
            }).catch(function() {
                self.loading = false;
                self.authError = true;
            });
        },
        doLogin: function() {
            var self = this;
            if (!this.loginForm.username.trim() || !this.loginForm.password) return;
            self.loginError = '';
            self.loginSubmitting = true;
            fetch(ADMIN_API + '/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ username: self.loginForm.username, password: self.loginForm.password })
            }).then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); }).then(function(result) {
                self.loginSubmitting = false;
                if (result.ok && result.data.token) {
                    setAdminCookie(result.data.token);
                    self.authError = false;
                    self.loginForm = { username: '', password: '' };
                    self.loadData();
                } else {
                    self.loginError = result.data.detail || self.$t('node.admin.invalid_credentials');
                }
            }).catch(function() {
                self.loginSubmitting = false;
                self.loginError = self.$t('node.admin.invalid_credentials');
            });
        },
        shortAddress: function(addr) {
            if (!addr || addr.length < 14) return addr;
            return addr.substring(0, 8) + '...' + addr.substring(addr.length - 6);
        },
        openDeleteModal: function(item) {
            this.deleteTronItem = item;
            this.deleteModalShow = true;
        },
        confirmDeleteTron: function() {
            if (this.deleteTronItem) {
                this.removeTronAddress(this.deleteTronItem.id);
                this.deleteTronItem = null;
            }
            this.deleteModalShow = false;
        },
        closeDeleteModal: function() {
            this.deleteModalShow = false;
            this.deleteTronItem = null;
        },
        copyTronAddress: function(address) {
            var self = this;
            if (!address) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(address).then(function() {
                    self.copyFeedbackId = address;
                    setTimeout(function() { self.copyFeedbackId = null; }, 2000);
                }).catch(function() { self.fallbackCopyAddress(address); });
            } else {
                self.fallbackCopyAddress(address);
            }
        },
        fallbackCopyAddress: function(address) {
            var self = this;
            var input = document.createElement('input');
            input.value = address;
            input.setAttribute('readonly', '');
            input.style.position = 'absolute';
            input.style.left = '-9999px';
            document.body.appendChild(input);
            input.select();
            try {
                document.execCommand('copy');
                self.copyFeedbackId = address;
                setTimeout(function() { self.copyFeedbackId = null; }, 2000);
            } catch (e) {}
            document.body.removeChild(input);
        },
        detailMessage: function(detail) {
            if (detail == null) return this.$t('node.admin.error_save');
            if (typeof detail === 'string') return detail;
            if (Array.isArray(detail) && detail.length > 0) return detail[0].msg || detail[0].message || JSON.stringify(detail[0]);
            return this.$t('node.admin.error_save');
        },
        changePassword: function() {
            var self = this;
            var oldP = (this.passwordForm.oldPassword || '').trim();
            var newP = (this.passwordForm.newPassword || '').trim();
            var confirmP = (this.passwordForm.confirmPassword || '').trim();
            if (!oldP || !newP || !confirmP) {
                self.saveError = self.$t('node.admin.error_fill_password');
                return;
            }
            if (newP.length < 8) {
                self.saveError = self.$t('node.admin.error_min_8');
                return;
            }
            if (newP !== confirmP) {
                self.saveError = self.$t('node.init.passwords_mismatch');
                return;
            }
            self.saveError = '';
            self.passwordSuccess = '';
            self.passwordSubmitting = true;
            fetch(ADMIN_API + '/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ old_password: oldP, new_password: newP })
            }).then(function(r) {
                if (r.status === 401) {
                    self.authError = true;
                    self.passwordSubmitting = false;
                    return null;
                }
                return r.json().then(function(data) { return { ok: r.ok, status: r.status, data: data }; });
            }).then(function(result) {
                if (result == null) return;
                self.passwordSubmitting = false;
                if (result.ok) {
                    self.passwordForm = { oldPassword: '', newPassword: '', confirmPassword: '' };
                    self.saveError = '';
                    self.passwordSuccess = self.$t('node.admin.password_changed');
                    setTimeout(function() { self.passwordSuccess = ''; }, 5000);
                } else {
                    self.saveError = self.detailMessage(result.data && result.data.detail);
                }
            }).catch(function() {
                self.passwordSubmitting = false;
                self.saveError = self.$t('node.admin.error_save');
            });
        },
        addTronAddress: function() {
            var self = this;
            var label = (this.tronForm.label || '').trim();
            var address = (this.tronForm.address || '').trim();
            if (!label || !address) {
                self.tronError = self.$t('node.admin.error_fill_tron');
                return;
            }
            self.tronError = '';
            self.tronSuccess = '';
            self.tronSubmitting = true;
            fetch(ADMIN_API + '/tron-addresses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ tron_address: address, label: label })
            }).then(function(r) {
                if (r.status === 401) {
                    self.authError = true;
                    self.tronSubmitting = false;
                    return null;
                }
                return r.json().then(function(data) { return { ok: r.ok, status: r.status, data: data }; });
            }).then(function(result) {
                if (result == null) return;
                self.tronSubmitting = false;
                if (result.ok) {
                    self.tronForm = { label: '', address: '' };
                    self.tronError = '';
                    self.tronSuccess = self.$t('node.admin.tron_added');
                    setTimeout(function() { self.tronSuccess = ''; }, 5000);
                    self.loadData();
                } else {
                    self.tronError = self.detailMessage(result.data && result.data.detail);
                }
            }).catch(function() {
                self.tronSubmitting = false;
                self.tronError = self.$t('node.admin.error_save');
            });
        },
        removeTronAddress: function(id) {
            var self = this;
            self.tronError = '';
            fetch(ADMIN_API + '/tron-addresses/' + id, {
                method: 'DELETE',
                credentials: 'same-origin'
            }).then(function(r) {
                if (r.status === 401) {
                    self.authError = true;
                    return;
                }
                if (r.ok) {
                    self.tronAddresses = self.tronAddresses.filter(function(a) { return a.id !== id; });
                    return;
                }
                return r.json().then(function(data) {
                    self.tronError = self.detailMessage(data && data.detail);
                }).catch(function() {
                    self.tronError = self.$t('node.admin.error_save');
                });
            }).catch(function() {
                self.tronError = self.$t('node.admin.error_save');
            });
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">[[ $t('node.page.admin') ]]</nav>
        <h2 class="text-xl font-bold text-zinc-900 mb-6 tracking-tight">[[ $t('node.admin.page_title') ]]</h2>

        <div v-if="loading" class="py-12 text-center text-zinc-500">[[ $t('node.loading') ]]</div>

        <div v-if="authError && !loading" class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 p-6 max-w-md">
          <p class="text-zinc-700 mb-4">[[ $t('node.admin.login_required') ]]</p>
          <div v-if="loginError" class="mb-3 p-3 rounded-lg bg-red-50 text-red-800 text-sm">[[ loginError ]]</div>
          <input type="text" v-model="loginForm.username" :placeholder="$t('node.init.login_placeholder')" class="block w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] mb-2">
          <input type="password" v-model="loginForm.password" :placeholder="$t('node.admin.password_placeholder')" class="block w-full px-3 py-2 border border-zinc-200 rounded-lg text-[13px] mb-3">
          <button type="button" :disabled="loginSubmitting" @click="doLogin" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.admin.login_btn') ]]</button>
        </div>

        <template v-if="!authError && !loading">
        <div class="rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3 mb-6">
          <svg class="w-5 h-5 text-sky-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
          <p class="text-[13px] font-medium text-sky-900 leading-relaxed">[[ $t('node.admin.security_message') ]]</p>
        </div>

        <div class="space-y-6">
          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="px-4 py-3 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <div class="w-7 h-7 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 shrink-0">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <span class="text-[12px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.admin.account_info') ]]</span>
            </div>
            <div class="p-4">
              <table class="w-full text-[13px] border-collapse">
                <tbody>
                  <tr class="border-b border-zinc-100 last:border-0">
                    <td class="py-2 pr-4 align-top w-48 text-[11px] font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.auth_methods') ]]</td>
                    <td class="py-2"><button type="button" class="px-3 py-1 bg-blue-100 text-blue-800 rounded-lg text-[12px] font-semibold hover:bg-blue-200">[[ $t('node.admin.password_method') ]]</button></td>
                  </tr>
                  <tr class="border-b border-zinc-100 last:border-0">
                    <td class="py-2 pr-4 align-top text-[11px] font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.username') ]]</td>
                    <td class="py-2 font-medium text-zinc-800">[[ account.username ]]</td>
                  </tr>
                  <tr class="border-b border-zinc-100 last:border-0">
                    <td class="py-2 pr-4 align-top text-[11px] font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.created') ]]</td>
                    <td class="py-2 text-zinc-600">[[ account.createdAt ]]</td>
                  </tr>
                  <tr class="border-b border-zinc-100 last:border-0">
                    <td class="py-2 pr-4 align-top text-[11px] font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.updated') ]]</td>
                    <td class="py-2 text-zinc-600">[[ account.updatedAt ]]</td>
                  </tr>
                    <tr>
                    <td class="py-2 pr-4 align-top text-[11px] font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.status') ]]</td>
                    <td class="py-2"><span class="inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">[[ (account.hasPassword || account.tronAddressesCount > 0) ? $t('node.admin.status_active') : '' ]]</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="px-4 py-3 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <div class="w-7 h-7 bg-amber-50 rounded-lg flex items-center justify-center text-amber-600 shrink-0">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
              </div>
              <span class="text-[12px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.admin.change_password_section') ]]</span>
            </div>
            <div class="p-4">
              <table class="w-full text-[13px] border-collapse">
                <tbody>
                  <tr class="border-b border-zinc-100">
                    <td class="py-2 pr-4 align-middle w-48 text-[11px] font-bold text-zinc-600 uppercase tracking-wider">[[ $t('node.admin.old_password') ]]</td>
                    <td class="py-2"><input type="password" v-model="passwordForm.oldPassword" :placeholder="$t('node.admin.placeholder_current_password')" class="w-full max-w-xs px-3 py-2 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"></td>
                  </tr>
                  <tr class="border-b border-zinc-100">
                    <td class="py-2 pr-4 align-middle text-[11px] font-bold text-zinc-600 uppercase tracking-wider">[[ $t('node.admin.new_password') ]]</td>
                    <td class="py-2"><input type="password" v-model="passwordForm.newPassword" :placeholder="$t('node.admin.placeholder_min_8')" class="w-full max-w-xs px-3 py-2 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"></td>
                  </tr>
                  <tr>
                    <td class="py-2 pr-4 align-middle text-[11px] font-bold text-zinc-600 uppercase tracking-wider">[[ $t('node.admin.confirm_password') ]]</td>
                    <td class="py-2"><input type="password" v-model="passwordForm.confirmPassword" :placeholder="$t('node.init.password_confirm_placeholder')" class="w-full max-w-xs px-3 py-2 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"></td>
                  </tr>
                </tbody>
              </table>
              <div class="pt-3">
                <div v-if="saveError" class="mb-2 text-sm text-red-600">[[ saveError ]]</div>
                <div v-if="passwordSuccess" class="mb-2 text-sm text-emerald-600 font-medium">[[ passwordSuccess ]]</div>
                <button type="button" :disabled="passwordSubmitting" @click="changePassword" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 disabled:opacity-50">[[ $t('node.admin.change_password_btn') ]]</button>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">[[ $t('node.admin.tron_addresses_title') ]]</span>
            </div>
            <div class="p-6 space-y-4">
              <div class="flex flex-wrap items-end gap-3">
                <div>
                  <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.admin.label') ]]</label>
                  <input type="text" v-model="tronForm.label" :placeholder="$t('node.admin.placeholder_label_example')" class="w-48 px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                </div>
                <div class="flex-1 min-w-[200px]">
                  <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">[[ $t('node.admin.tron_address') ]]</label>
                  <input type="text" v-model="tronForm.address" :placeholder="$t('node.admin.placeholder_tron')" class="w-full px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] font-mono placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                </div>
                <button type="button" :disabled="tronSubmitting" @click="addTronAddress" class="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2 disabled:opacity-50">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  [[ $t('node.admin.add_btn') ]]
                </button>
              </div>
              <div v-if="tronError" class="mb-2 text-sm text-red-600">[[ tronError ]]</div>
              <div v-if="tronSuccess" class="mb-2 text-sm text-emerald-600 font-medium">[[ tronSuccess ]]</div>
              <div class="overflow-x-auto rounded-xl border border-zinc-200 fade-in-content">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.label') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">[[ $t('node.admin.table_address') ]]</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider w-24">[[ $t('node.admin.table_actions') ]]</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="filteredTronAddresses.length === 0" class="border-b border-zinc-100">
                      <td colspan="3" class="px-4 py-6 text-center text-zinc-500 text-[13px]">[[ adminSearchQuery ? $t('node.admin.search_no_results') : $t('node.admin.no_tron_addresses') ]]</td>
                    </tr>
                    <tr v-for="a in filteredTronAddresses" :key="a.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ a.label ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">
                        <span class="align-middle">[[ shortAddress(a.address) ]]</span>
                        <button type="button" @click="copyTronAddress(a.address)" class="ml-2 p-1.5 inline-flex align-middle text-zinc-400 hover:text-blue-600 rounded" :title="copyFeedbackId === a.address ? $t('node.admin.copied') : $t('node.admin.copy_address')">
                          <svg v-if="copyFeedbackId !== a.address" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h2m8 0h2a2 2 0 012 2v2m2 4a2 2 0 01-2 2h-2m-4 0H6m8 0h8" /></svg>
                          <svg v-else class="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                        </button>
                      </td>
                      <td class="px-4 py-3">
                        <button type="button" @click="openDeleteModal(a)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" :title="$t('node.admin.delete_title')">
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

        <modal-dialog :show="deleteModalShow" :title="deleteModalTitle" :message="deleteModalMessage"
          :confirm-label="$t('node.admin.delete_btn')" :cancel-label="$t('node.admin.cancel_btn')"
          confirm-class="bg-red-600 hover:bg-red-700 text-white"
          @confirm="confirmDeleteTron" @cancel="closeDeleteModal">
        </modal-dialog>
        </template>
      </div>
    </div>
    `
});
})();
