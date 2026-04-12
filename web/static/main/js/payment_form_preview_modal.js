/**
 * Модалка предпросмотра формы реквизитов по payment_code (effective: forms.yaml / override спейса).
 * Подключать после vue.min.js, до my_business.js.
 */
(function() {
    if (typeof Vue === 'undefined') return;

    function unwrapApiRoot(data) {
        if (data && data.root && typeof data.root === 'object') return data.root;
        return data;
    }

    function authHeaders() {
        var token = null;
        try {
            var key = (typeof window !== 'undefined' && window.main_auth_token_key)
                ? window.main_auth_token_key
                : 'main_auth_token';
            token = localStorage.getItem(key);
        } catch (e) {}
        var h = { 'Content-Type': 'application/json', Accept: 'application/json' };
        if (token) h.Authorization = 'Bearer ' + token;
        return h;
    }

    Vue.component('payment-form-preview-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false },
            paymentCode: { type: String, default: '' }
        },
        data: function() {
            return {
                loading: false,
                error: null,
                payload: null
            };
        },
        mounted: function() {
            var self = this;
            this.$watch(
                function() {
                    return String(self.show) + '\0' + (self.paymentCode || '').trim();
                },
                function() {
                    if (!self.show) {
                        self.error = null;
                        self.payload = null;
                        self.loading = false;
                        return;
                    }
                    if ((self.paymentCode || '').trim()) {
                        self.load();
                    }
                }
            );
        },
        methods: {
            close: function() {
                this.$emit('close');
            },
            load: function() {
                var code = (this.paymentCode || '').trim();
                if (!code) return;
                var self = this;
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                self.loading = true;
                self.error = null;
                self.payload = null;
                if (!space) {
                    self.loading = false;
                    self.error = 'nospace';
                    return;
                }
                var url = '/v1/spaces/' + encodeURIComponent(space) + '/payment-forms/' + encodeURIComponent(code);
                fetch(url, { method: 'GET', headers: authHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.payload = unwrapApiRoot(data);
                    })
                    .catch(function() {
                        self.error = 'load';
                    })
                    .then(function() {
                        self.loading = false;
                    });
            }
        },
        template: [
            '<div v-if="show" class="fixed inset-0 z-[110] overflow-y-auto overscroll-contain">',
            '  <div class="min-h-[100dvh] min-h-[100svh] flex items-end justify-center sm:items-center p-0 sm:p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="close"></div>',
            '    <div class="relative z-10 bg-white w-full max-w-full sm:max-w-lg rounded-t-3xl sm:rounded-3xl shadow-2xl grid grid-rows-[auto_minmax(0,1fr)] h-[90dvh] max-h-[90dvh] overflow-hidden my-0 sm:my-4" role="dialog" aria-modal="true">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between shrink-0">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ $t(\'main.my_business.form_preview_title\') ]] <span class="font-mono text-base text-[#58667e]">[[ (paymentCode || \'\').trim() ]]</span></h3>',
            '        <button type="button" @click="close" class="p-2 hover:bg-gray-100 rounded-full" :aria-label="$t(\'main.my_business.multisig_wizard_close\')">',
            '          <svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '        </button>',
            '      </div>',
            '      <div class="min-h-0 overflow-y-auto touch-pan-y p-6 space-y-3 text-sm">',
            '        <p v-if="loading" class="text-[#58667e]">[[ $t(\'main.loading\') ]]</p>',
            '        <p v-else-if="error" class="text-red-600">[[ $t(\'main.my_business.form_preview_error\') ]]</p>',
            '        <template v-else-if="payload">',
            '          <p class="text-xs text-[#58667e]">[[ $t(\'main.my_business.form_source_label\') ]]: <strong>[[ payload.source ]]</strong></p>',
            '          <ul v-if="payload.form && payload.form.fields && payload.form.fields.length" class="list-disc pl-5 space-y-1">',
            '            <li v-for="(f, idx) in payload.form.fields" :key="idx" class="text-[#191d23]"><span class="font-mono text-xs">[[ f.id ]]</span> — [[ f.type ]] <span v-if="f.required" class="text-amber-600 text-xs">([[ $t(\'main.my_business.field_required\') ]])</span></li>',
            '          </ul>',
            '          <p v-else class="text-[#58667e]">[[ $t(\'main.my_business.form_preview_empty\') ]]</p>',
            '        </template>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
