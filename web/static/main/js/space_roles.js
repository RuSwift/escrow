/**
 * Vue 2 компонент: Роли спейса (main). Только для владельца спейса.
 * Таблица участников, добавление/редактирование через API /v1/spaces/{space}/participants.
 */
Vue.component('space-roles', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            participants: [],
            loading: false,
            error: null,
            modalMode: null,
            editingParticipant: null,
            form: {
                nickname: '',
                wallet_address: '',
                blockchain: 'tron',
                roles: ['reader'],
                is_blocked: false
            },
            submitLoading: false,
            roleOptions: [
                { value: 'owner', labelKey: 'main.space.role_owner', hintKey: 'main.space_roles.role_owner_hint' },
                { value: 'operator', labelKey: 'main.space.role_operator', hintKey: 'main.space_roles.role_operator_hint' },
                { value: 'reader', labelKey: 'main.space.role_reader', hintKey: 'main.space_roles.role_reader_hint' }
            ],
            inviteLinkModal: false,
            inviteLinkUrl: '',
            inviteLinkCopied: false,
            inviteLinkLoading: false
        };
    },
    mounted: function() {
        this.fetchParticipants();
    },
    methods: {
        apiBase: function() {
            var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? window.__CURRENT_SPACE__ : '';
            if (!space) return '';
            return '/v1/spaces/' + encodeURIComponent(space) + '/participants';
        },
        authHeaders: function() {
            var token = null;
            try {
                var key = (typeof window !== 'undefined' && window.main_auth_token_key) ? window.main_auth_token_key : 'main_auth_token';
                token = localStorage.getItem(key);
            } catch (e) {}
            var h = { 'Content-Type': 'application/json' };
            if (token) h['Authorization'] = 'Bearer ' + token;
            return h;
        },
        /** Сообщение об ошибке из ответа API: по коду (мультияз) или detail. */
        participantErrorMessage: function(status, data) {
            var self = this;
            if (status === 403) return self.$t('main.space_roles.error_403');
            if (status === 400 && data && data.detail) {
                var d = data.detail;
                if (typeof d === 'object' && d.code) {
                    var key = 'main.space_roles.error_' + d.code;
                    return self.$t(key) !== key ? self.$t(key) : (d.message || self.$t('main.space_roles.error_invalid_address'));
                }
                if (typeof d === 'object' && d.message) return d.message;
                if (typeof d === 'string') return d;
            }
            if (status === 400) return self.$t('main.space_roles.error_invalid_address');
            return self.$t('main.space_roles.error_network');
        },
        fetchParticipants: function() {
            var self = this;
            var base = this.apiBase();
            if (!base) { this.error = 'Space not set'; return; }
            this.loading = true;
            this.error = null;
            fetch(base, { method: 'GET', headers: this.authHeaders(), credentials: 'include' })
                .then(function(r) {
                    if (!r.ok) {
                        if (r.status === 403) throw new Error(self.$t('main.space_roles.error_403'));
                        throw new Error(self.$t('main.space_roles.error_load'));
                    }
                    return r.json();
                })
                .then(function(data) {
                    self.participants = Array.isArray(data) ? data : [];
                })
                .catch(function(e) {
                    self.error = e.message || self.$t('main.space_roles.error_network');
                    self.participants = [];
                })
                .finally(function() {
                    self.loading = false;
                });
        },
        openAdd: function() {
            this.editingParticipant = null;
            this.modalMode = 'add';
            this.form = { nickname: '', wallet_address: '', blockchain: 'tron', roles: ['reader'], is_blocked: false };
            this.error = null;
        },
        openEdit: function(p) {
            this.editingParticipant = p;
            this.modalMode = 'edit';
            var roles = (p && p.roles) ? (Array.isArray(p.roles) ? p.roles.slice() : [p.roles]) : ['reader'];
            this.form = { nickname: (p && p.nickname) ? p.nickname : '', wallet_address: (p && p.wallet_address) ? p.wallet_address : '', blockchain: (p && p.blockchain) ? p.blockchain : 'tron', roles: roles, is_blocked: !!(p && p.is_blocked) };
            this.error = null;
        },
        closeModal: function() {
            this.modalMode = null;
            this.editingParticipant = null;
            this.submitLoading = false;
        },
        toggleRole: function(role) {
            var idx = this.form.roles.indexOf(role);
            if (idx === -1) this.form.roles.push(role);
            else this.form.roles.splice(idx, 1);
            if (this.form.roles.length === 0) this.form.roles = ['reader'];
        },
        submitAdd: function() {
            var self = this;
            var base = this.apiBase();
            if (!base) return;
            this.submitLoading = true;
            this.error = null;
            var body = {
                wallet_address: this.form.wallet_address.trim(),
                blockchain: this.form.blockchain.trim(),
                nickname: this.form.nickname.trim() || null,
                roles: this.form.roles.length ? this.form.roles : ['reader'],
                is_blocked: !!this.form.is_blocked
            };
            fetch(base, { method: 'POST', headers: this.authHeaders(), credentials: 'include', body: JSON.stringify(body) })
                .then(function(r) {
                    return r.json().catch(function() { return {}; }).then(function(data) {
                        if (!r.ok) {
                            throw new Error(self.participantErrorMessage(r.status, data));
                        }
                        return data;
                    });
                })
                .then(function() {
                    self.closeModal();
                    self.fetchParticipants();
                })
                .catch(function(e) {
                    self.error = e.message || self.$t('main.space_roles.error_network');
                })
                .finally(function() {
                    self.submitLoading = false;
                });
        },
        submitEdit: function() {
            var self = this;
            if (!this.editingParticipant || this.editingParticipant.id == null) return;
            var base = this.apiBase();
            if (!base) return;
            var url = base + '/' + encodeURIComponent(this.editingParticipant.id);
            this.submitLoading = true;
            this.error = null;
            var body = {
                nickname: this.form.nickname.trim() || null,
                roles: this.form.roles.length ? this.form.roles : ['reader'],
                is_blocked: !!this.form.is_blocked
            };
            fetch(url, { method: 'PATCH', headers: this.authHeaders(), credentials: 'include', body: JSON.stringify(body) })
                .then(function(r) {
                    return r.json().catch(function() { return {}; }).then(function(data) {
                        if (!r.ok) throw new Error(self.participantErrorMessage(r.status, data));
                        return data;
                    });
                })
                .then(function() {
                    self.closeModal();
                    self.fetchParticipants();
                })
                .catch(function(e) {
                    self.error = e.message || self.$t('main.space_roles.error_network');
                })
                .finally(function() {
                    self.submitLoading = false;
                });
        },
        deleteParticipant: function(p) {
            var self = this;
            if (!p || p.id == null) return;
            var base = this.apiBase();
            if (!base) return;
            if (typeof window.showConfirm !== 'function') {
                self.doDeleteParticipant(p);
                return;
            }
            var nickname = (p.nickname && p.nickname.trim()) ? p.nickname.trim() : (p.wallet_address || '—');
            var walletMask = (p.wallet_address && p.wallet_address.length > 8)
                ? (p.wallet_address.slice(0, 6) + '…' + p.wallet_address.slice(-4))
                : (p.wallet_address || '—');
            window.showConfirm({
                title: self.$t('main.space_roles.delete_confirm_title'),
                message: self.$t('main.space_roles.delete_confirm_message', { nickname: nickname, wallet_mask: walletMask }),
                danger: true,
                onConfirm: function() {
                    self.doDeleteParticipant(p);
                }
            });
        },
        doDeleteParticipant: function(p) {
            var self = this;
            if (!p || p.id == null) return;
            var base = this.apiBase();
            if (!base) return;
            var url = base + '/' + encodeURIComponent(p.id);
            fetch(url, { method: 'DELETE', headers: this.authHeaders(), credentials: 'include' })
                .then(function(r) {
                    if (!r.ok) throw new Error(r.status === 403 ? self.$t('main.space_roles.error_403') : self.$t('main.space_roles.error_network'));
                })
                .then(function() {
                    if (self.modalMode === 'edit' && self.editingParticipant && self.editingParticipant.id === p.id) self.closeModal();
                    self.fetchParticipants();
                })
                .catch(function(e) {
                    self.error = e.message || self.$t('main.space_roles.error_network');
                });
        },
        roleLabel: function(role) {
            if (role === 'owner') return this.$t('main.space.role_owner');
            if (role === 'operator') return this.$t('main.space.role_operator');
            if (role === 'reader') return this.$t('main.space.role_reader');
            return role;
        },
        rolesDisplay: function(participant) {
            var roles = (participant && participant.roles) ? (Array.isArray(participant.roles) ? participant.roles : [participant.roles]) : [];
            return roles.map(this.roleLabel).join(', ') || '—';
        },
        verifiedBadgeClass: function(isVerified) {
            return isVerified
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-amber-50 text-amber-900 border border-amber-300';
        },
        verifiedDotClass: function(isVerified) {
            return isVerified ? 'bg-emerald-500' : 'bg-amber-500';
        },
        blockedBadgeClass: function(isBlocked) {
            return isBlocked ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700';
        },
        blockedDotClass: function(isBlocked) {
            return isBlocked ? 'bg-rose-500' : 'bg-emerald-500';
        },
        openInviteLink: function(p) {
            var self = this;
            if (!p || p.id == null) return;
            var base = this.apiBase();
            if (!base) return;
            var url = base + '/' + encodeURIComponent(p.id) + '/invite-link';
            this.inviteLinkLoading = true;
            this.inviteLinkUrl = '';
            this.inviteLinkCopied = false;
            fetch(url, { method: 'POST', headers: this.authHeaders(), credentials: 'include' })
                .then(function(r) {
                    return r.json().then(function(data) {
                        if (!r.ok) throw new Error((data && data.detail) ? data.detail : self.$t('main.space_roles.error_network'));
                        return data;
                    });
                })
                .then(function(data) {
                    self.inviteLinkUrl = (data && data.invite_link) ? data.invite_link : '';
                    self.inviteLinkModal = true;
                })
                .catch(function(e) {
                    self.error = e.message || self.$t('main.space_roles.error_network');
                })
                .finally(function() {
                    self.inviteLinkLoading = false;
                });
        },
        closeInviteLinkModal: function() {
            this.inviteLinkModal = false;
            this.inviteLinkUrl = '';
            this.inviteLinkCopied = false;
        },
        copyInviteLink: function() {
            var self = this;
            if (!this.inviteLinkUrl) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(this.inviteLinkUrl).then(function() {
                    self.inviteLinkCopied = true;
                }).catch(function() {
                    self.selectAndCopyInviteLink();
                });
            } else {
                self.selectAndCopyInviteLink();
            }
        },
        selectAndCopyInviteLink: function() {
            var el = document.getElementById('invite-link-input');
            if (el) {
                el.select();
                try {
                    document.execCommand('copy');
                    this.inviteLinkCopied = true;
                } catch (e) {}
            }
        }
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="rounded-lg bg-main-blue/10 border border-main-blue/20 px-4 py-3 mb-6 text-main-blue font-medium">
        [[ $t('main.space_roles.alert_manage_roles') ]]
      </div>
      <div v-if="error" class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 mb-6 text-red-700 text-sm">
        [[ error ]]
      </div>
      <div class="flex justify-end mb-4">
        <button type="button" class="cmc-btn-primary py-2 px-4" @click="openAdd">
          [[ $t('main.space_roles.add_participant') ]]
        </button>
      </div>
      <div class="cmc-card overflow-hidden">
        <div v-if="loading" class="p-8 flex items-center justify-center gap-2 text-cmc-muted">
          [[ $t('main.loading') ]]
          <span class="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" aria-hidden="true"></span>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="cmc-table-header">[[ $t('main.space_roles.table_nickname') ]]</th>
                <th class="cmc-table-header">[[ $t('main.space_roles.table_blockchain') ]]</th>
                <th class="cmc-table-header">[[ $t('main.space_roles.table_address') ]]</th>
                <th class="cmc-table-header">[[ $t('main.space_roles.table_roles') ]]</th>
                <th class="cmc-table-header">[[ $t('main.space_roles.table_verified') ]]</th>
                <th class="cmc-table-header">[[ $t('main.space_roles.table_blocked') ]]</th>
                <th class="cmc-table-header text-right">[[ $t('main.space_roles.table_actions') ]]</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!loading && participants.length === 0">
                <td colspan="7" class="cmc-table-cell text-center py-8 text-cmc-muted">[[ $t('main.space_roles.placeholder') ]]</td>
              </tr>
              <tr v-for="p in participants" :key="p.id" class="border-b border-[#eff2f5] last:border-0 hover:bg-[#f8fafd]">
                <td class="cmc-table-cell">[[ p.nickname || '—' ]]</td>
                <td class="cmc-table-cell">[[ p.blockchain || '—' ]]</td>
                <td class="cmc-table-cell font-mono text-xs">[[ p.wallet_address || '—' ]]</td>
                <td class="cmc-table-cell">[[ rolesDisplay(p) ]]</td>
                <td class="cmc-table-cell">
                  <div :class="['inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider', verifiedBadgeClass(p.is_verified)]">
                    <span :class="['w-1.5 h-1.5 rounded-full shrink-0', verifiedDotClass(p.is_verified)]"></span>
                    [[ p.is_verified ? $t('main.space_roles.verified_yes') : $t('main.space_roles.verified_no') ]]
                  </div>
                </td>
                <td class="cmc-table-cell">
                  <div :class="['inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider', blockedBadgeClass(p.is_blocked)]">
                    <span :class="['w-1.5 h-1.5 rounded-full shrink-0', blockedDotClass(p.is_blocked)]"></span>
                    [[ p.is_blocked ? $t('main.space_roles.blocked_yes') : $t('main.space_roles.blocked_no') ]]
                  </div>
                </td>
                <td class="cmc-table-cell text-right">
                  <template v-if="!p.is_verified && !p.is_blocked">
                    <button type="button" class="text-main-blue hover:underline text-sm font-medium mr-2" @click="openInviteLink(p)" :disabled="inviteLinkLoading">[[ $t('main.space_roles.invite_link') ]]</button>
                  </template>
                  <button type="button" class="text-main-blue hover:underline text-sm font-medium mr-2" @click="openEdit(p)">[[ $t('main.space_roles.edit') ]]</button>
                  <button type="button" class="text-red-600 hover:underline text-sm font-medium" @click="deleteParticipant(p)">[[ $t('main.space_roles.delete') ]]</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="modalMode" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeModal">
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full p-6" @click.stop>
          <h3 class="text-lg font-bold mb-4">[[ modalMode === 'add' ? $t('main.space_roles.modal_add_title') : $t('main.space_roles.modal_edit_title') ]]</h3>
          <div v-if="modalMode === 'add'" class="space-y-3 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_nickname') ]]</label>
              <input v-model="form.nickname" type="text" class="w-full border border-[#eff2f5] rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_blockchain') ]]</label>
              <select v-model="form.blockchain" class="w-full border border-[#eff2f5] rounded-lg px-3 py-2 text-sm">
                <option value="tron">TRON</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_address') ]]</label>
              <input v-model="form.wallet_address" type="text" class="w-full border border-[#eff2f5] rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_roles') ]]</label>
              <div class="flex flex-wrap gap-3">
                <label v-for="ro in roleOptions" :key="ro.value" class="inline-flex items-center gap-2 cursor-pointer" :title="$t(ro.hintKey)">
                  <input type="checkbox" :checked="form.roles.indexOf(ro.value) !== -1" @change="toggleRole(ro.value)" />
                  <span>[[ $t(ro.labelKey) ]]</span>
                </label>
              </div>
            </div>
            <div>
              <label class="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" v-model="form.is_blocked" />
                <span>[[ $t('main.space_roles.form_blocked') ]]</span>
              </label>
            </div>
          </div>
          <div v-if="modalMode === 'edit'" class="space-y-3 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_nickname') ]]</label>
              <input v-model="form.nickname" type="text" class="w-full border border-[#eff2f5] rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t('main.space_roles.form_roles') ]]</label>
              <div class="flex flex-wrap gap-3">
                <label v-for="ro in roleOptions" :key="ro.value" class="inline-flex items-center gap-2 cursor-pointer" :title="$t(ro.hintKey)">
                  <input type="checkbox" :checked="form.roles.indexOf(ro.value) !== -1" @change="toggleRole(ro.value)" />
                  <span>[[ $t(ro.labelKey) ]]</span>
                </label>
              </div>
            </div>
            <div>
              <label class="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" v-model="form.is_blocked" />
                <span>[[ $t('main.space_roles.form_blocked') ]]</span>
              </label>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <button type="button" class="px-4 py-2 border border-[#eff2f5] rounded-lg text-sm font-medium hover:bg-gray-50" @click="closeModal">[[ $t('main.space_roles.cancel') ]]</button>
            <button v-if="modalMode === 'add'" type="button" class="cmc-btn-primary px-4 py-2" :disabled="submitLoading" @click="submitAdd">[[ submitLoading ? $t('main.loading') : $t('main.space_roles.save') ]]</button>
            <template v-if="modalMode === 'edit'">
              <button type="button" class="px-4 py-2 text-red-600 border border-red-200 rounded-lg text-sm font-medium hover:bg-red-50" :disabled="submitLoading" @click="deleteParticipant(editingParticipant)">[[ $t('main.space_roles.delete') ]]</button>
              <button type="button" class="cmc-btn-primary px-4 py-2" :disabled="submitLoading" @click="submitEdit">[[ submitLoading ? $t('main.loading') : $t('main.space_roles.save') ]]</button>
            </template>
          </div>
        </div>
      </div>

      <div v-if="inviteLinkModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeInviteLinkModal">
        <div class="bg-white rounded-xl shadow-xl max-w-lg w-full p-6" @click.stop>
          <h3 class="text-lg font-bold mb-4">[[ $t('main.space_roles.invite_link_modal_title') ]]</h3>
          <p class="text-sm text-cmc-muted mb-3">[[ $t('main.space_roles.invite_link_expires') ]]</p>
          <div class="flex gap-2 mb-4">
            <input id="invite-link-input" type="text" :value="inviteLinkUrl" readonly class="flex-1 border border-[#eff2f5] rounded-lg px-3 py-2 text-sm font-mono bg-gray-50" />
            <button type="button" class="cmc-btn-primary px-4 py-2 whitespace-nowrap" @click="copyInviteLink">[[ inviteLinkCopied ? $t('main.space_roles.invite_link_copied') : $t('main.space_roles.invite_copy_btn') ]]</button>
          </div>
          <div class="flex justify-end">
            <button type="button" class="px-4 py-2 border border-[#eff2f5] rounded-lg text-sm font-medium hover:bg-gray-50" @click="closeInviteLinkModal">[[ $t('main.space_roles.cancel') ]]</button>
          </div>
        </div>
      </div>
    </div>
    `
});
