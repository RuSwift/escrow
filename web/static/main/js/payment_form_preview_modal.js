/**
 * Модалка предпросмотра / редактирования формы реквизитов по payment_code.
 * Effective: forms.yaml + override спейса (preview). Редактор сравнивает с system_only.
 * Подключать после vue.min.js, до my_business.js.
 */
(function() {
    if (typeof Vue === 'undefined') return;

    var FIELD_TYPES = [
        'string', 'text', 'integer', 'decimal', 'money', 'phone', 'email',
        'bic', 'iban', 'account_number', 'pan_last_digits', 'date'
    ];

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

    function cloneFieldRow(f) {
        var raw = f || {};
        var d = raw.default;
        var labs = raw.labels && typeof raw.labels === 'object' ? raw.labels : {};
        return {
            id: raw.id != null ? String(raw.id) : '',
            type: raw.type || 'string',
            required: !!raw.required,
            label_key: raw.label_key != null ? String(raw.label_key) : '',
            label: raw.label != null ? String(raw.label) : '',
            labels: {
                ru: labs.ru != null ? String(labs.ru) : '',
                en: labs.en != null ? String(labs.en) : ''
            },
            default: d != null && d !== '' ? String(d) : '',
            readonly: !!raw.readonly
        };
    }

    function normalizeLabelsForStore(labels) {
        if (!labels || typeof labels !== 'object') return null;
        var out = {};
        var k;
        for (k in labels) {
            if (!Object.prototype.hasOwnProperty.call(labels, k)) continue;
            var v = labels[k];
            if (v != null && String(v).trim() !== '') out[k] = String(v).trim();
        }
        return Object.keys(out).length ? out : null;
    }

    function normalizeFieldForCompare(f) {
        var def = (f.default != null && String(f.default).trim() !== '')
            ? String(f.default).trim()
            : null;
        var out = {
            id: String(f.id || '').trim(),
            type: f.type || 'string',
            required: !!f.required,
            default: def,
            readonly: !!f.readonly
        };
        var lk = String(f.label_key || '').trim();
        var lbl = (f.label != null && String(f.label).trim() !== '') ? String(f.label).trim() : null;
        var labs = normalizeLabelsForStore(f.labels);
        if (lk) out.label_key = lk;
        if (lbl) out.label = lbl;
        if (labs) out.labels = labs;
        return out;
    }

    function normalizeFieldsList(fields) {
        if (!fields || !fields.length) return [];
        return fields.map(normalizeFieldForCompare);
    }

    function fieldsEqual(a, b) {
        if (a.length !== b.length) return false;
        for (var i = 0; i < a.length; i++) {
            if (JSON.stringify(a[i]) !== JSON.stringify(b[i])) return false;
        }
        return true;
    }

    function hasFieldCaption(row) {
        if ((row.label || '').trim()) return true;
        if ((row.label_key || '').trim()) return true;
        var L = row.labels || {};
        if ((L.ru || '').trim() || (L.en || '').trim()) return true;
        return false;
    }

    Vue.component('payment-form-preview-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false },
            paymentCode: { type: String, default: '' },
            variant: { type: String, default: 'preview' },
            initialRequisitesSchema: {
                type: Object,
                default: function() {
                    return {};
                }
            }
        },
        data: function() {
            return {
                loading: false,
                error: null,
                payload: null,
                systemFieldsNormalized: [],
                editFields: [],
                saveError: null,
                saveLoading: false,
                fieldTypes: FIELD_TYPES
            };
        },
        computed: {
            isEdit: function() {
                return this.variant === 'edit';
            }
        },
        mounted: function() {
            var self = this;
            this.$watch(
                function() {
                    return [
                        String(self.show),
                        (self.paymentCode || '').trim(),
                        self.variant,
                        JSON.stringify(self.initialRequisitesSchema || {})
                    ].join('\0');
                },
                function() {
                    if (!self.show) {
                        self.resetLocal();
                        return;
                    }
                    if (!(self.paymentCode || '').trim()) return;
                    if (self.isEdit) {
                        self.loadEdit();
                    } else {
                        self.loadPreview();
                    }
                }
            );
        },
        methods: {
            resetLocal: function() {
                this.error = null;
                this.payload = null;
                this.loading = false;
                this.systemFieldsNormalized = [];
                this.editFields = [];
                this.saveError = null;
                this.saveLoading = false;
            },
            close: function() {
                this.$emit('close');
            },
            /** Подпись для предпросмотра: label → labels[locale] → $t(label_key) */
            fieldCaption: function(f) {
                if (!f) return '';
                if (f.label != null && String(f.label).trim()) return String(f.label).trim();
                var loc = '';
                try {
                    if (this.$i18n && this.$i18n.locale) {
                        loc = String(this.$i18n.locale).split('-')[0].toLowerCase();
                    }
                } catch (e) {}
                if (f.labels && loc && f.labels[loc] != null && String(f.labels[loc]).trim()) {
                    return String(f.labels[loc]).trim();
                }
                if (f.labels && f.labels.ru != null && String(f.labels.ru).trim()) return String(f.labels.ru).trim();
                if (f.labels && f.labels.en != null && String(f.labels.en).trim()) return String(f.labels.en).trim();
                if (f.label_key) {
                    try {
                        return String(this.$t(f.label_key));
                    } catch (e2) {
                        return f.label_key;
                    }
                }
                return '';
            },
            loadPreview: function() {
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
            },
            loadEdit: function() {
                var code = (this.paymentCode || '').trim();
                if (!code) return;
                var self = this;
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                self.loading = true;
                self.error = null;
                self.saveError = null;
                self.systemFieldsNormalized = [];
                self.editFields = [];
                if (!space) {
                    self.loading = false;
                    self.error = 'nospace';
                    return;
                }
                var url = '/v1/spaces/' + encodeURIComponent(space) + '/payment-forms/' + encodeURIComponent(code)
                    + '?system_only=true';
                fetch(url, { method: 'GET', headers: authHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        var root = unwrapApiRoot(data);
                        var sysFields = (root && root.form && root.form.fields) ? root.form.fields : [];
                        self.systemFieldsNormalized = normalizeFieldsList(sysFields);
                        var init = self.initialRequisitesSchema || {};
                        var saved = (init.fields && init.fields.length) ? init.fields : null;
                        if (saved && saved.length) {
                            self.editFields = saved.map(cloneFieldRow);
                        } else {
                            self.editFields = sysFields.map(function(sf) {
                                return cloneFieldRow(sf);
                            });
                        }
                    })
                    .catch(function() {
                        self.error = 'load';
                    })
                    .then(function() {
                        self.loading = false;
                    });
            },
            addField: function() {
                this.editFields.push(cloneFieldRow({
                    id: '',
                    type: 'string',
                    required: false,
                    label_key: '',
                    label: '',
                    labels: { ru: '', en: '' },
                    default: '',
                    readonly: false
                }));
            },
            removeField: function(idx) {
                var list = this.editFields.slice();
                if (idx >= 0 && idx < list.length) list.splice(idx, 1);
                this.editFields = list;
            },
            saveEdit: function() {
                this.saveError = null;
                var rows = this.editFields || [];
                var normalized = [];
                var i;
                for (i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    if (!String(row.id || '').trim()) {
                        this.saveError = 'invalid_field';
                        return;
                    }
                    if (!hasFieldCaption(row)) {
                        this.saveError = 'invalid_field';
                        return;
                    }
                    normalized.push(normalizeFieldForCompare(row));
                }
                var schema;
                if (this.systemFieldsNormalized.length === 0 && normalized.length === 0) {
                    schema = {};
                } else if (this.systemFieldsNormalized.length === 0 && normalized.length > 0) {
                    schema = { fields: normalized };
                } else if (fieldsEqual(this.systemFieldsNormalized, normalized)) {
                    schema = {};
                } else {
                    schema = { fields: normalized };
                }
                this.$emit('requisites-saved', { schema: schema });
            }
        },
        template: [
            '<div v-if="show" class="fixed inset-0 z-[110] overflow-y-auto overscroll-contain">',
            '  <div class="min-h-[100dvh] min-h-[100svh] flex items-end justify-center sm:items-center p-0 sm:p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="close"></div>',
            '    <div class="relative z-10 bg-white w-full max-w-full sm:max-w-2xl rounded-t-3xl sm:rounded-3xl shadow-2xl grid grid-rows-[auto_minmax(0,1fr)_auto] h-[90dvh] max-h-[90dvh] overflow-hidden my-0 sm:my-4" role="dialog" aria-modal="true">',
            '      <div class="p-5 sm:p-6 border-b border-[#eff2f5] flex items-center justify-between shrink-0">',
            '        <h3 class="text-lg sm:text-xl font-bold text-[#191d23] pr-2">',
            '          <template v-if="isEdit">[[ $t(\'main.my_business.form_edit_title\') ]]</template>',
            '          <template v-else>[[ $t(\'main.my_business.form_preview_title\') ]]</template>',
            '          <span class="font-mono text-sm sm:text-base text-[#58667e] block sm:inline sm:ml-1">[[ (paymentCode || \'\').trim() ]]</span>',
            '        </h3>',
            '        <button type="button" @click="close" class="p-2 hover:bg-gray-100 rounded-full shrink-0" :aria-label="$t(\'main.my_business.multisig_wizard_close\')">',
            '          <svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '        </button>',
            '      </div>',
            '      <div class="min-h-0 overflow-y-auto touch-pan-y p-5 sm:p-6 space-y-3 text-sm">',
            '        <template v-if="!isEdit">',
            '        <p v-if="loading" class="text-[#58667e]">[[ $t(\'main.loading\') ]]</p>',
            '        <p v-else-if="error" class="text-red-600">[[ $t(\'main.my_business.form_preview_error\') ]]</p>',
            '        <template v-else-if="payload">',
            '          <p class="text-xs text-[#58667e]">[[ $t(\'main.my_business.form_source_label\') ]]: <strong>[[ payload.source ]]</strong></p>',
            '          <ul v-if="payload.form && payload.form.fields && payload.form.fields.length" class="list-disc pl-5 space-y-1">',
            '            <li v-for="(f, idx) in payload.form.fields" :key="idx" class="text-[#191d23]"><span class="font-mono text-xs">[[ f.id ]]</span> — <span class="text-[#58667e]">[[ fieldCaption(f) ]]</span> — [[ f.type ]] <span v-if="f.required" class="text-amber-600 text-xs">([[ $t(\'main.my_business.field_required\') ]])</span></li>',
            '          </ul>',
            '          <p v-else class="text-[#58667e]">[[ $t(\'main.my_business.form_preview_empty\') ]]</p>',
            '        </template>',
            '        </template>',
            '        <template v-else>',
            '        <p v-if="loading" class="text-[#58667e]">[[ $t(\'main.loading\') ]]</p>',
            '        <p v-else-if="error" class="text-red-600">[[ $t(\'main.my_business.form_preview_error\') ]]</p>',
            '        <template v-else>',
            '          <p class="text-xs text-[#58667e] mb-3">[[ $t(\'main.my_business.form_edit_intro\') ]]</p>',
            '          <p v-if="saveError === \'invalid_field\'" class="text-red-600 text-sm mb-2">[[ $t(\'main.my_business.form_edit_validation\') ]]</p>',
            '          <div class="space-y-3">',
            '            <div v-for="(row, ridx) in editFields" :key="\'r-\' + ridx" class="rounded-xl border border-[#eff2f5] p-3 sm:p-4 space-y-2 bg-[#fafbfc]">',
            '              <div class="flex justify-between items-center gap-2">',
            '                <span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_block\', { n: ridx + 1 }) ]]</span>',
            '                <button type="button" @click="removeField(ridx)" class="text-xs font-bold text-red-600 hover:underline">[[ $t(\'main.my_business.form_field_remove\') ]]</button>',
            '              </div>',
            '              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">',
            '                <label class="block min-w-0"><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_id\') ]]</span>',
            '                  <input type="text" v-model="row.id" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm font-mono" autocomplete="off" /></label>',
            '                <label class="block min-w-0"><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_type\') ]]</span>',
            '                  <select v-model="row.type" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm">',
            '                    <option v-for="t in fieldTypes" :key="t" :value="t">[[ t ]]</option>',
            '                  </select></label>',
            '              </div>',
            '              <label class="block min-w-0"><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_label\') ]]</span>',
            '                <input type="text" v-model="row.label" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm" autocomplete="off" :placeholder="$t(\'main.my_business.form_field_label_placeholder\')" /></label>',
            '              <div class="rounded-lg border border-dashed border-[#eff2f5] p-3 space-y-2 bg-white/80">',
            '                <p class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_translations\') ]]</p>',
            '                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">',
            '                  <label class="block min-w-0"><span class="text-[10px] text-[#58667e]">[[ $t(\'main.my_business.form_field_lang_ru\') ]]</span>',
            '                    <input type="text" v-model="row.labels.ru" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm" autocomplete="off" /></label>',
            '                  <label class="block min-w-0"><span class="text-[10px] text-[#58667e]">[[ $t(\'main.my_business.form_field_lang_en\') ]]</span>',
            '                    <input type="text" v-model="row.labels.en" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm" autocomplete="off" /></label>',
            '                </div>',
            '              </div>',
            '              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 items-end">',
            '                <label class="flex items-center gap-2 cursor-pointer select-none">',
            '                  <input type="checkbox" v-model="row.required" class="rounded border-[#eff2f5] text-[#3861fb]" />',
            '                  <span class="text-xs font-bold text-[#58667e]">[[ $t(\'main.my_business.form_field_required\') ]]</span>',
            '                </label>',
            '                <label class="flex items-center gap-2 cursor-pointer select-none">',
            '                  <input type="checkbox" v-model="row.readonly" class="rounded border-[#eff2f5] text-[#3861fb]" />',
            '                  <span class="text-xs font-bold text-[#58667e]">[[ $t(\'main.my_business.form_field_readonly\') ]]</span>',
            '                </label>',
            '              </div>',
            '              <label class="block min-w-0"><span class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.form_field_default\') ]]</span>',
            '                <input type="text" v-model="row.default" class="mt-0.5 w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm" autocomplete="off" :placeholder="$t(\'main.my_business.form_field_default_placeholder\')" /></label>',
            '            </div>',
            '          </div>',
            '          <button type="button" @click="addField" class="mt-3 w-full sm:w-auto px-4 py-2.5 rounded-xl border-2 border-dashed border-[#3861fb]/40 text-sm font-bold text-[#3861fb] hover:bg-blue-50">[[ $t(\'main.my_business.form_field_add\') ]]</button>',
            '        </template>',
            '        </template>',
            '      </div>',
            '      <div v-if="isEdit" class="p-4 sm:p-5 border-t border-[#eff2f5] bg-gray-50 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end shrink-0 pb-[max(1rem,env(safe-area-inset-bottom))]">',
            '        <button type="button" @click="close" class="w-full sm:w-auto px-5 py-3 rounded-xl border border-[#eff2f5] text-sm font-bold text-[#58667e] hover:bg-white">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="saveEdit" :disabled="loading" class="w-full sm:w-auto px-5 py-3 rounded-xl bg-[#3861fb] text-white text-sm font-bold hover:opacity-90 disabled:opacity-50">[[ $t(\'main.my_business.form_edit_save\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
