/**
 * Vue 2 компонент: Профиль спейса (main). Только для владельца.
 * GET/PATCH /v1/spaces/{space}/profile. Поля: description, icon (base64).
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
                            self.icon = '';
                            return;
                        }
                        self.description = data.description || '';
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
            '<div class="max-w-2xl mx-auto px-4 py-8">',
            '  <h1 class="text-2xl font-bold mb-6">[[ $t(\'main.space_profile.title\', { space: currentSpace }) ]]</h1>',
            '  <div v-if="loading" class="text-cmc-muted text-sm">[[ $t(\'main.loading\') ]]</div>',
            '  <template v-else>',
            '    <div v-if="successMessage" class="rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 mb-4 text-emerald-800 text-sm">[[ successMessage ]]</div>',
            '    <div v-if="error" class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-4 text-amber-800 text-sm">[[ error ]]</div>',
            '    <div class="space-y-4 mb-6">',
            '      <div>',
            '        <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t(\'main.space_profile.form_description\') ]]</label>',
            '        <textarea v-model="description" rows="4" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-main-blue/20" :placeholder="$t(\'main.space_profile.form_description_placeholder\')"></textarea>',
            '      </div>',
            '      <div>',
            '        <label class="block text-sm font-medium text-gray-700 mb-1">[[ $t(\'main.space_profile.form_icon\') ]]</label>',
            '        <div class="flex flex-wrap items-center gap-3">',
            '          <input type="file" accept="image/*" @change="onIconFile" class="text-sm text-gray-600 file:mr-2 file:py-2 file:px-4 file:rounded file:border file:border-gray-300 file:bg-white file:text-sm file:font-medium file:cursor-pointer hover:file:bg-gray-50">',
            '          <button type="button" class="px-4 py-2 border border-[#eff2f5] rounded-lg text-sm font-medium hover:bg-gray-50" @click="generateAvatar">[[ $t(\'main.space_profile.generate_avatar\') ]]</button>',
            '        </div>',
            '        <p v-if="icon" class="mt-2"><img :src="icon" alt="icon" class="w-16 h-16 object-cover rounded-lg border border-[#eff2f5]"></p>',
            '      </div>',
            '    </div>',
            '    <button type="button" class="cmc-btn-primary px-4 py-2" :disabled="submitLoading" @click="saveProfile">[[ submitLoading ? $t(\'main.loading\') : $t(\'main.space_profile.save\') ]]</button>',
            '  </template>',
            '</div>'
        ].join('')
    });
})();
