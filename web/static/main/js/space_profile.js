/**
 * Vue 2 компонент: Профиль спейса (main). Только для владельца.
 * GET/PATCH /v1/spaces/{space}/profile. Поля: description, company_name, icon (base64).
 */
(function() {
    var PROFILE_ICON_MAX_LEN = 524288; // 512 KB (base64 length)
    // Макс. размер файла в байтах (base64 ~4/3 от бинарного: 512KB base64 ≈ 384KB file)
    var PROFILE_ICON_MAX_FILE_BYTES = 393216; // ~384 KB

    Vue.component('space-profile', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                description: '',
                company_name: '',
                icon: '',
                loading: false,
                error: null,
                successMessage: null,
                submitLoading: false
            };
        },
        computed: {
            currentSpace: function() {
                return (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? window.__CURRENT_SPACE__ : '';
            }
        },
        mounted: function() {
            this.fetchProfile();
        },
        methods: {
            apiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? window.__CURRENT_SPACE__ : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/profile';
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
            fetchProfile: function() {
                var self = this;
                var base = this.apiBase();
                if (!base) { this.error = 'Space not set'; return; }
                this.loading = true;
                this.error = null;
                fetch(base, { method: 'GET', headers: this.authHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) {
                            if (r.status === 403) throw new Error(self.$t('main.space_profile.error_403'));
                            throw new Error(self.$t('main.space_profile.error_load'));
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        if (!data || typeof data !== 'object') {
                            self.description = '';
                            self.company_name = '';
                            self.icon = '';
                            return;
                        }
                        self.description = data.description || '';
                        self.company_name = data.company_name || '';
                        self.icon = data.icon || '';
                    })
                    .catch(function(e) {
                        self.error = e.message || self.$t('main.space_profile.error_network');
                    })
                    .finally(function() {
                        self.loading = false;
                    });
            },
            onIconFile: function(ev) {
                var self = this;
                var file = ev.target && ev.target.files && ev.target.files[0];
                if (!file) return;
                if (file.size > PROFILE_ICON_MAX_FILE_BYTES) {
                    self.error = self.$t('main.space_profile.error_icon_too_large');
                    ev.target.value = '';
                    return;
                }
                var reader = new FileReader();
                reader.onload = function() {
                    var dataUrl = reader.result;
                    if (dataUrl && dataUrl.length > PROFILE_ICON_MAX_LEN) {
                        self.error = self.$t('main.space_profile.error_icon_too_large');
                        return;
                    }
                    self.icon = dataUrl || '';
                    self.error = null;
                };
                reader.onerror = function() {
                    self.error = self.$t('main.space_profile.error_icon_too_large');
                };
                reader.readAsDataURL(file);
                ev.target.value = '';
            },
            generateAvatar: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? window.__CURRENT_SPACE__ : '';
                var initials = (space || 'S').trim().slice(0, 2).toUpperCase();
                if (!initials) initials = 'S';
                var canvas = document.createElement('canvas');
                canvas.width = 128;
                canvas.height = 128;
                var ctx = canvas.getContext('2d');
                if (!ctx) return;
                var hue = (space ? (space.split('').reduce(function(a, c) { return a + c.charCodeAt(0); }, 0) % 360) : 220);
                ctx.fillStyle = 'hsl(' + hue + ', 55%, 45%)';
                ctx.fillRect(0, 0, 128, 128);
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 48px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(initials, 64, 64);
                this.icon = canvas.toDataURL('image/png');
                this.error = null;
            },
            saveProfile: function() {
                var self = this;
                if (this.icon && this.icon.length > PROFILE_ICON_MAX_LEN) {
                    this.error = this.$t('main.space_profile.error_icon_too_large');
                    return;
                }
                var base = this.apiBase();
                if (!base) { this.error = 'Space not set'; return; }
                this.submitLoading = true;
                this.error = null;
                this.successMessage = null;
                var body = JSON.stringify({
                    description: this.description || null,
                    company_name: this.company_name || null,
                    icon: this.icon || null
                });
                fetch(base, {
                    method: 'PATCH',
                    headers: this.authHeaders(),
                    credentials: 'include',
                    body: body
                })
                    .then(function(r) {
                        if (!r.ok) {
                            return r.json().then(function(data) {
                                var msg = (data && data.detail) ? (typeof data.detail === 'string' ? data.detail : (data.detail.message || (data.detail.detail && typeof data.detail.detail === 'string' ? data.detail.detail : null) || JSON.stringify(data.detail))) : self.$t('main.space_profile.error_network');
                                if (r.status === 403) msg = self.$t('main.space_profile.error_403');
                                if (r.status === 400 && msg.indexOf('512') !== -1) msg = self.$t('main.space_profile.error_icon_too_large');
                                throw new Error(msg);
                            }).catch(function(e) {
                                if (e && e.message) throw e;
                                throw new Error(self.$t('main.space_profile.error_network'));
                            });
                        }
                        return r.json();
                    })
                    .then(function() {
                        if (typeof window.__SPACE_PROFILE_FILLED__ !== 'undefined') window.__SPACE_PROFILE_FILLED__ = true;
                        self.successMessage = self.$t('main.space_profile.success');
                        self.error = null;
                        if (self._successTimeout) clearTimeout(self._successTimeout);
                        self._successTimeout = setTimeout(function() {
                            self.successMessage = null;
                            self._successTimeout = null;
                        }, 5000);
                    })
                    .catch(function(e) {
                        self.error = (e && e.message) ? e.message : self.$t('main.space_profile.error_network');
                        self.successMessage = null;
                    })
                    .finally(function() {
                        self.submitLoading = false;
                    });
            }
        },
        template: [
            '<div class="max-w-4xl mx-auto px-4 py-8">',
            '  <h1 class="text-2xl font-bold text-[#191d23] mb-2">[[ $t(\'main.space_profile.title\', { space: currentSpace }) ]]</h1>',
            '  <p class="text-sm text-[#58667e] mb-6">[[ $t(\'main.space_profile.form_description_placeholder\') ]]</p>',
            '  <div v-if="loading" class="flex items-center justify-center py-12"><span class="text-[#58667e] text-sm">[[ $t(\'main.loading\') ]]</span></div>',
            '  <template v-else>',
            '    <div v-if="successMessage" class="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 mb-6 text-emerald-800 text-sm">[[ successMessage ]]</div>',
            '    <div v-if="error" class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-amber-800 text-sm">[[ error ]]</div>',
            '    <div class="bg-white rounded-2xl border border-[#eff2f5] shadow-sm overflow-hidden">',
            '      <div class="p-6 md:p-8 flex flex-col md:flex-row gap-8">',
            '        <div class="md:w-48 shrink-0 flex flex-col items-center md:items-start">',
            '          <label class="block text-xs font-bold text-[#58667e] uppercase tracking-wider mb-3">[[ $t(\'main.space_profile.form_icon\') ]]</label>',
            '          <div class="w-32 h-32 rounded-2xl border-2 border-[#eff2f5] overflow-hidden bg-gray-50 flex items-center justify-center shrink-0">',
            '            <img v-if="icon" :src="icon" alt="" class="w-full h-full object-cover" />',
            '            <span v-else class="text-3xl font-bold text-[#58667e]">[[ (currentSpace || \'?\').charAt(0).toUpperCase() ]]</span>',
            '          </div>',
            '          <div class="flex flex-col sm:flex-row md:flex-col gap-2 mt-4 w-full md:w-auto">',
            '            <label class="cursor-pointer"><span class="inline-flex items-center justify-center w-full md:w-auto px-4 py-2.5 rounded-xl border border-[#eff2f5] text-sm font-medium text-[#191d23] hover:bg-gray-50 transition-colors">[[ $t(\'main.space_profile.upload\') ]]</span><input type="file" accept="image/*" @change="onIconFile" class="hidden" /></label>',
            '            <button type="button" class="px-4 py-2.5 rounded-xl border border-[#eff2f5] text-sm font-medium text-[#191d23] hover:bg-gray-50 transition-colors" @click="generateAvatar">[[ $t(\'main.space_profile.generate_avatar\') ]]</button>',
            '          </div>',
            '        </div>',
            '        <div class="flex-1 min-w-0 space-y-5">',
            '          <div>',
            '            <label class="block text-xs font-bold text-[#58667e] uppercase tracking-wider mb-2">[[ $t(\'main.space_profile.form_company_name\') ]]</label>',
            '            <input v-model="company_name" type="text" maxlength="255" class="w-full px-4 py-3 border border-[#eff2f5] rounded-xl text-sm text-[#191d23] placeholder-[#58667e] focus:outline-none focus:border-[#3861fb] focus:ring-2 focus:ring-[#3861fb]/20 transition-all" :placeholder="$t(\'main.space_profile.form_company_name_placeholder\')" />',
            '          </div>',
            '          <div>',
            '          <label class="block text-xs font-bold text-[#58667e] uppercase tracking-wider mb-2">[[ $t(\'main.space_profile.form_description\') ]]</label>',
            '          <textarea v-model="description" rows="5" class="w-full px-4 py-3 border border-[#eff2f5] rounded-xl text-sm text-[#191d23] placeholder-[#58667e] focus:outline-none focus:border-[#3861fb] focus:ring-2 focus:ring-[#3861fb]/20 transition-all resize-none" :placeholder="$t(\'main.space_profile.form_description_placeholder\')"></textarea>',
            '          </div>',
            '        </div>',
            '      </div>',
            '      <div class="px-6 md:px-8 py-4 bg-gray-50/80 border-t border-[#eff2f5] flex justify-end">',
            '        <button type="button" class="cmc-btn-primary px-6 py-2.5 rounded-xl font-medium" :disabled="submitLoading" @click="saveProfile">[[ submitLoading ? $t(\'main.loading\') : $t(\'main.space_profile.save\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </template>',
            '</div>'
        ].join('')
    });
})();
