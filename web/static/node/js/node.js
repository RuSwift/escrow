/**
 * Vue 2 компонент: Нода (профиль ноды)
 * Подключение: после vue.min.js, перед app.js
 * Логика как в garantex node.py: key-info, set-service-endpoint, test-service-endpoint.
 */
(function() {
    var API_BASE = '/v1';
    var NODE_API = API_BASE + '/node';

    Vue.component('node', {
        delimiters: ['[[', ']]'],
        props: { isNodeInitialized: { type: Boolean, default: false } },
        data: function() {
            return {
                loading: true,
                loadError: '',
                pemKey: '',
                did: '',
                serviceEndpoint: '',
                endpointEditing: false,
                endpointEditValue: '',
                endpointSaving: false,
                endpointTesting: false,
                endpointMessage: '',
                endpointMessageType: ''
            };
        },
        mounted: function() {
            this.loadKeyInfo();
        },
        methods: {
            loadKeyInfo: function() {
                var self = this;
                self.loading = true;
                self.loadError = '';
                fetch(NODE_API + '/key-info', { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) {
                            if (r.status === 401 || r.status === 404) {
                                self.loadError = self.$t('node.profile.load_error');
                            }
                            return r.json().then(function(data) { throw new Error(data.detail || 'Failed to load'); });
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.pemKey = data.public_key_pem || '';
                        self.did = data.did || '';
                        self.serviceEndpoint = data.service_endpoint || '';
                        self.loading = false;
                    })
                    .catch(function(err) {
                        if (!self.loadError) self.loadError = err.message || self.$t('node.profile.load_error');
                        self.loading = false;
                    });
            },
            copyToClipboard: function(text) {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text);
                }
            },
            startEditEndpoint: function() {
                this.endpointEditValue = this.serviceEndpoint || '';
                this.endpointEditing = true;
                this.endpointMessage = '';
            },
            cancelEditEndpoint: function() {
                this.endpointEditing = false;
                this.endpointMessage = '';
            },
            saveEndpoint: function() {
                var self = this;
                var url = (self.endpointEditValue || '').trim();
                if (!url) {
                    self.endpointMessage = self.$t('node.profile.enter_url');
                    self.endpointMessageType = 'error';
                    return;
                }
                self.endpointSaving = true;
                self.endpointMessage = '';
                fetch(NODE_API + '/set-service-endpoint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ service_endpoint: url })
                })
                    .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
                    .then(function(result) {
                        if (result.ok && result.data.success) {
                            self.serviceEndpoint = url;
                            self.endpointEditing = false;
                            self.endpointMessage = self.$t('node.profile.endpoint_saved');
                            self.endpointMessageType = 'success';
                        } else {
                            self.endpointMessage = (result.data.detail || self.$t('node.init.error_saving'));
                            self.endpointMessageType = 'error';
                        }
                    })
                    .catch(function(err) {
                        self.endpointMessage = (err.message || self.$t('node.profile.load_error'));
                        self.endpointMessageType = 'error';
                    })
                    .finally(function() { self.endpointSaving = false; });
            },
            checkEndpoint: function() {
                var self = this;
                var url = self.endpointEditing ? (self.endpointEditValue || '').trim() : (self.serviceEndpoint || '').trim();
                if (!url) {
                    self.endpointMessage = self.$t('node.profile.enter_url');
                    self.endpointMessageType = 'error';
                    return;
                }
                self.endpointTesting = true;
                self.endpointMessage = '';
                fetch(NODE_API + '/test-service-endpoint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service_endpoint: url })
                })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.success) {
                            self.endpointMessage = self.$t('node.profile.endpoint_test_ok', { ms: result.response_time_ms != null ? result.response_time_ms : '' });
                            self.endpointMessageType = 'success';
                        } else {
                            self.endpointMessage = result.message || self.$t('node.profile.endpoint_test_fail');
                            self.endpointMessageType = 'error';
                        }
                    })
                    .catch(function(err) {
                        self.endpointMessage = err.message || self.$t('node.profile.endpoint_test_fail');
                        self.endpointMessageType = 'error';
                    })
                    .finally(function() { self.endpointTesting = false; });
            }
        },
        template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">[[ $t('node.page.node') ]]</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Профиль ноды</span>
          </div>
          <div class="p-8">
            <p v-if="loading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
            <p v-if="loadError" class="text-red-600 text-[13px] mb-4">[[ loadError ]]</p>
            <template v-if="!loading && !loadError">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 shrink-0">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg>
              </div>
              <h2 class="text-xl font-bold text-zinc-900 tracking-tight">Публичная информация о ключе</h2>
            </div>
            <div class="rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3 mb-8">
              <svg class="w-5 h-5 text-sky-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <p class="text-[13px] font-medium text-sky-900 leading-relaxed"><span class="font-bold">Информация:</span> Публичный ключ, PEM, DID и DID Document можно безопасно делиться с другими. Они используются для проверки подписей, шифрования сообщений и идентификации в P2P сети.</p>
            </div>

            <div class="mb-8">
              <div class="flex items-center gap-2 mb-3">
                <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-7 0V6a2 2 0 012-2h2a2 2 0 012 2v4h-4z" /></svg>
                <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Публичный ключ (PEM):</h3>
              </div>
              <div class="relative group">
                <textarea readonly rows="5" class="w-full px-4 py-4 bg-zinc-50 border border-zinc-200 rounded-xl text-[12px] font-mono text-zinc-600 focus:outline-none resize-none leading-relaxed" :value="pemKey"></textarea>
                <button type="button" @click="copyToClipboard(pemKey)" class="absolute right-3 top-3 p-2 bg-white border border-zinc-200 rounded-lg text-zinc-400 hover:text-blue-600 hover:border-blue-200 transition-all shadow-sm opacity-0 group-hover:opacity-100" :title="$t('node.init.copy')">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                </button>
              </div>
              <p class="mt-2 text-[11px] text-zinc-400 font-medium italic">Этот PEM ключ можно безопасно делиться — он содержит только публичную информацию</p>
            </div>

            <div class="mb-12">
              <div class="flex items-center gap-2 mb-3">
                <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-7 0V6a2 2 0 012-2h2a2 2 0 012 2v4h-4z" /></svg>
                <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">DID (Decentralized Identifier):</h3>
              </div>
              <div class="relative group">
                <input readonly type="text" :value="did" class="w-full px-4 py-3 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] font-mono text-zinc-600 focus:outline-none">
                <button type="button" @click="copyToClipboard(did)" class="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-white border border-zinc-200 rounded-lg text-zinc-400 hover:text-blue-600 hover:border-blue-200 transition-all shadow-sm opacity-0 group-hover:opacity-100" :title="$t('node.init.copy')">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                </button>
              </div>
              <p class="mt-2 text-[11px] text-zinc-400 font-medium">Децентрализованный идентификатор для P2P сети</p>
            </div>

            <div class="h-px bg-zinc-100 mb-12"></div>

            <div class="mb-8">
              <div class="flex items-center gap-3 mb-6">
                <div class="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 shrink-0">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                </div>
                <h2 class="text-xl font-bold text-zinc-900 tracking-tight">Service Endpoint</h2>
              </div>
              <div class="mb-4">
                <div class="flex items-center gap-2 mb-3">
                  <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Service Endpoint URL:</h3>
                </div>
                <div class="flex gap-3 flex-wrap items-center">
                  <input v-if="endpointEditing" type="text" v-model="endpointEditValue" class="flex-1 min-w-0 px-4 py-3 bg-white border border-zinc-300 rounded-xl text-[13px] font-mono text-zinc-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400" :placeholder="$t('node.profile.enter_url')">
                  <input v-else type="text" readonly :value="serviceEndpoint" class="flex-1 min-w-0 px-4 py-3 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] font-mono text-zinc-600 focus:outline-none">
                  <template v-if="endpointEditing">
                    <button type="button" @click="saveEndpoint" :disabled="endpointSaving" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold flex items-center gap-2 hover:bg-blue-700 transition-all shrink-0 disabled:opacity-60">
                      <span v-if="endpointSaving">[[ $t('node.init.saving') ]]</span>
                      <span v-else>[[ $t('node.profile.save_endpoint') ]]</span>
                    </button>
                    <button type="button" @click="cancelEditEndpoint" :disabled="endpointSaving" class="px-4 py-2 bg-white border border-zinc-300 text-zinc-700 rounded-lg text-[13px] font-semibold hover:bg-zinc-50 transition-all shrink-0">[[ $t('node.profile.cancel') ]]</button>
                  </template>
                  <button v-else type="button" @click="startEditEndpoint" class="px-4 py-2 bg-white border border-blue-600 text-blue-600 rounded-lg text-[13px] font-semibold flex items-center gap-2 hover:bg-blue-50 transition-all shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                    [[ $t('node.profile.edit_endpoint') ]]
                  </button>
                </div>
                <p class="mt-2 text-[11px] text-zinc-400 font-medium">[[ $t('node.profile.endpoint_hint') ]]</p>
                <p v-if="endpointMessage" :class="endpointMessageType === 'success' ? 'mt-2 text-[13px] text-green-600 font-medium' : 'mt-2 text-[13px] text-red-600 font-medium'">[[ endpointMessage ]]</p>
              </div>
              <button type="button" @click="checkEndpoint" :disabled="endpointTesting" class="px-4 py-2.5 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-[13px] font-bold flex items-center gap-2 transition-all shadow-md shadow-sky-400/20 disabled:opacity-60">
                <span v-if="endpointTesting">[[ $t('node.init.checking_availability') ]]</span>
                <template v-else>
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                  [[ $t('node.profile.test_get') ]]
                </template>
              </button>
            </div>
            </template>
          </div>
        </div>
      </div>
      <footer class="mt-auto pt-12 text-center text-[11px] text-zinc-400 font-medium tracking-wide uppercase">&copy; Escrow Node &bull; v0.1.0</footer>
    </div>
    `
    });
})();
