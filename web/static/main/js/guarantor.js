/**
 * Vue 2: панель гаранта — направления (валюта + платёжный метод из BestChange), комиссии.
 */
(function() {
    var DEBOUNCE_MS = 280;

    function emptyBlock(id) {
        return {
            id: id,
            currencyCode: '',
            paymentCode: '',
            paymentName: '',
            currencyInput: '',
            paymentInput: '',
            currencyOpen: false,
            paymentOpen: false,
            currencySuggestions: [],
            paymentSuggestions: [],
            currencyNoHits: false,
            paymentNoHits: false,
            _currencyTimer: null,
            _paymentTimer: null
        };
    }

    function appLocale() {
        if (typeof window !== 'undefined' && window.__LOCALE__) {
            return String(window.__LOCALE__).trim() || 'en';
        }
        return 'en';
    }

    Vue.component('guarantor', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                commissionPercent: 2.5,
                blocks: [emptyBlock('b1')]
            };
        },
        mounted: function() {
            this._docClick = this.onDocumentClick.bind(this);
            document.addEventListener('click', this._docClick);
        },
        beforeDestroy: function() {
            document.removeEventListener('click', this._docClick);
        },
        methods: {
            addBlock: function() {
                this.blocks.push(emptyBlock('b' + Date.now()));
            },
            onDocumentClick: function(e) {
                if (!this.$el || !this.$el.contains(e.target)) {
                    return;
                }
                if (e.target.closest('[data-guarantor-ac]')) {
                    return;
                }
                this.blocks.forEach(function(b) {
                    b.currencyOpen = false;
                    b.paymentOpen = false;
                });
            },
            onCurrencyFocus: function(b) {
                this.blocks.forEach(function(x) {
                    if (x !== b) {
                        x.currencyOpen = false;
                        x.paymentOpen = false;
                    }
                });
                b.currencyOpen = true;
            },
            onPaymentFocus: function(b) {
                if (!b.currencyCode) {
                    return;
                }
                this.blocks.forEach(function(x) {
                    if (x !== b) {
                        x.currencyOpen = false;
                        x.paymentOpen = false;
                    }
                });
                b.paymentOpen = true;
            },
            onCurrencyInput: function(b) {
                var self = this;
                var v = (b.currencyInput || '').trim();
                b.currencyNoHits = false;
                if (b.currencyCode && v !== b.currencyCode) {
                    b.currencyCode = '';
                    b.paymentCode = '';
                    b.paymentName = '';
                    b.paymentInput = '';
                    b.paymentSuggestions = [];
                    b.paymentNoHits = false;
                }
                if (!b.currencyCode) {
                    b.paymentCode = '';
                    b.paymentName = '';
                    b.paymentInput = '';
                    b.paymentSuggestions = [];
                    b.paymentNoHits = false;
                }
                clearTimeout(b._currencyTimer);
                b._currencyTimer = setTimeout(function() {
                    self.fetchCurrencies(b);
                }, DEBOUNCE_MS);
            },
            onPaymentInput: function(b) {
                var self = this;
                var v = (b.paymentInput || '').trim();
                b.paymentNoHits = false;
                if (b.paymentCode && v !== (b.paymentName || '').trim()) {
                    b.paymentCode = '';
                    b.paymentName = '';
                }
                clearTimeout(b._paymentTimer);
                b._paymentTimer = setTimeout(function() {
                    self.fetchPayments(b);
                }, DEBOUNCE_MS);
            },
            fetchCurrencies: function(b) {
                var q = (b.currencyInput || '').trim();
                if (q.length < 1) {
                    b.currencySuggestions = [];
                    b.currencyNoHits = false;
                    return;
                }
                var self = this;
                fetch(
                    '/v1/autocomplete/currencies?q=' + encodeURIComponent(q) + '&limit=40',
                    { credentials: 'same-origin' }
                )
                    .then(function(r) {
                        return r.json();
                    })
                    .then(function(data) {
                        b.currencySuggestions = data.items || [];
                        b.currencyNoHits = (b.currencySuggestions.length === 0);
                        b.currencyOpen = true;
                        self.$forceUpdate();
                    })
                    .catch(function() {
                        b.currencySuggestions = [];
                        b.currencyNoHits = false;
                        self.$forceUpdate();
                    });
            },
            fetchPayments: function(b) {
                if (!b.currencyCode) {
                    b.paymentSuggestions = [];
                    return;
                }
                var q = (b.paymentInput || '').trim();
                if (q.length < 1) {
                    b.paymentSuggestions = [];
                    b.paymentNoHits = false;
                    return;
                }
                var self = this;
                var loc = appLocale();
                var url =
                    '/v1/autocomplete/directions?locale=' +
                    encodeURIComponent(loc) +
                    '&q=' +
                    encodeURIComponent(q) +
                    '&limit=40&cur=' +
                    encodeURIComponent(b.currencyCode);
                fetch(url, { credentials: 'same-origin' })
                    .then(function(r) {
                        return r.json();
                    })
                    .then(function(data) {
                        b.paymentSuggestions = data.items || [];
                        b.paymentNoHits = (b.paymentSuggestions.length === 0);
                        b.paymentOpen = true;
                        self.$forceUpdate();
                    })
                    .catch(function() {
                        b.paymentSuggestions = [];
                        b.paymentNoHits = false;
                        self.$forceUpdate();
                    });
            },
            selectCurrency: function(b, item) {
                b.currencyCode = item.code;
                b.currencyInput = item.code;
                b.currencyOpen = false;
                b.currencyNoHits = false;
                b.paymentCode = '';
                b.paymentName = '';
                b.paymentInput = '';
                b.paymentSuggestions = [];
                b.paymentNoHits = false;
            },
            selectPayment: function(b, item) {
                b.paymentCode = item.payment_code;
                b.paymentName = item.name;
                b.paymentInput = item.name;
                b.paymentOpen = false;
                b.paymentNoHits = false;
            },
            currencyChipLabel: function(b) {
                return b.currencyCode || '—';
            },
            paymentChipLabel: function(b) {
                return b.paymentName || '—';
            }
        },
        template: [
            '<div class="max-w-7xl mx-auto px-4 py-6 md:py-8">',
            '  <div class="flex flex-col lg:flex-row gap-6 lg:gap-8 lg:items-start">',
            '    <div class="flex-1 min-w-0 space-y-6">',
            '      <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">',
            '        <div class="min-w-0">',
            '          <h1 class="text-xl md:text-2xl font-bold text-[#191d23] flex items-center gap-3">',
            '            <span class="inline-flex w-9 h-9 md:w-10 md:h-10 rounded-xl bg-main-blue/10 text-main-blue items-center justify-center shrink-0">',
            '              <svg class="w-5 h-5 md:w-6 md:h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>',
            '            </span>',
            '            <span>[[ $t(\'main.guarantor.title\') ]]</span>',
            '          </h1>',
            '          <p class="text-sm text-[#58667e] mt-1 max-w-2xl">[[ $t(\'main.guarantor.subtitle\') ]]</p>',
            '        </div>',
            '      </div>',
            '      <div class="flex flex-col sm:flex-row gap-4 sm:items-stretch">',
            '        <div class="rounded-xl border border-[#eff2f5] bg-white shadow-sm p-4 md:p-5 sm:flex-1 min-w-0">',
            '          <div class="text-xs font-medium text-[#58667e] mb-2">[[ $t(\'main.guarantor.commission_card_label\') ]]</div>',
            '          <div class="flex items-center gap-2 flex-wrap">',
            '            <input v-model.number="commissionPercent" type="number" min="0" max="100" step="0.1" class="w-20 px-2 py-1.5 rounded-lg border border-[#eff2f5] text-sm font-bold text-main-blue text-center focus:outline-none focus:ring-2 focus:ring-main-blue/20" />',
            '            <span class="text-sm text-[#58667e]">%</span>',
            '          </div>',
            '        </div>',
            '        <div class="rounded-xl border border-main-blue/20 bg-main-blue/[0.06] p-4 md:p-5 sm:flex-1 min-w-0">',
            '          <h3 class="text-sm font-bold text-[#191d23] mb-2">[[ $t(\'main.guarantor.verification_title\') ]]</h3>',
            '          <p class="text-xs text-[#58667e] leading-relaxed mb-4">[[ $t(\'main.guarantor.verification_text\') ]]</p>',
            '          <div class="inline-flex items-center gap-2 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 px-3 py-1.5 text-xs font-semibold">',
            '            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>',
            '            [[ $t(\'main.guarantor.status_active\') ]]',
            '          </div>',
            '        </div>',
            '      </div>',
            '      <section>',
            '        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">',
            '          <h2 class="text-sm font-bold text-[#191d23] tracking-tight">[[ $t(\'main.guarantor.section_directions\') ]]</h2>',
            '          <button type="button" @click="addBlock" class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-main-blue text-white hover:opacity-90 transition-opacity shrink-0">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '            [[ $t(\'main.guarantor.add_block\') ]]',
            '          </button>',
            '        </div>',
            '        <div class="space-y-4">',
            '          <article v-for="(b, idx) in blocks" :key="b.id" class="rounded-xl border border-[#eff2f5] bg-white shadow-sm p-4 md:p-5">',
            '            <div class="flex flex-wrap items-center gap-2 mb-3">',
            '              <span class="inline-flex items-center gap-1.5 rounded-full bg-[#f8fafd] border border-[#eff2f5] px-3 py-1 text-xs font-semibold text-[#191d23]">',
            '                <svg class="w-3.5 h-3.5 text-main-blue shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '                [[ currencyChipLabel(b) ]]',
            '              </span>',
            '              <span class="inline-flex items-center gap-1.5 rounded-full bg-[#f8fafd] border border-[#eff2f5] px-3 py-1 text-xs font-semibold text-[#191d23]">',
            '                <svg class="w-3.5 h-3.5 text-main-blue shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>',
            '                [[ paymentChipLabel(b) ]]',
            '              </span>',
            '            </div>',
            '            <div data-guarantor-ac class="flex flex-col sm:flex-row gap-3 mb-4">',
            '              <div class="flex-1 min-w-0 relative">',
            '                <input',
            '                  v-model="b.currencyInput"',
            '                  type="text"',
            '                  :placeholder="$t(\'main.guarantor.currency_placeholder\')"',
            '                  autocomplete="off"',
            '                  autocapitalize="off"',
            '                  spellcheck="false"',
            '                  @focus="onCurrencyFocus(b)"',
            '                  @input="onCurrencyInput(b)"',
            '                  class="w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm text-[#191d23] placeholder:text-[#58667e] focus:outline-none focus:ring-2 focus:ring-main-blue/20"',
            '                />',
            '                <ul v-show="b.currencyOpen && (b.currencySuggestions.length > 0 || b.currencyNoHits) && (b.currencyInput || \'\').trim().length >= 1" class="absolute left-0 right-0 top-full mt-1 z-30 max-h-48 overflow-y-auto rounded-lg border border-[#eff2f5] bg-white shadow-lg py-1 text-sm">',
            '                  <li v-for="c in b.currencySuggestions" :key="c.code">',
            '                    <button type="button" class="w-full text-left px-3 py-2 hover:bg-[#f8fafd] text-[#191d23]" @mousedown.prevent @click.stop="selectCurrency(b, c)">[[ c.code ]]</button>',
            '                  </li>',
            '                  <li v-if="b.currencyNoHits && b.currencySuggestions.length === 0" class="px-3 py-2 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</li>',
            '                </ul>',
            '              </div>',
            '              <div class="flex-1 min-w-0 relative">',
            '                <input',
            '                  v-model="b.paymentInput"',
            '                  type="text"',
            '                  :disabled="!b.currencyCode"',
            '                  :placeholder="b.currencyCode ? $t(\'main.guarantor.payment_placeholder\') : $t(\'main.guarantor.select_currency_first\')"',
            '                  autocomplete="off"',
            '                  autocapitalize="off"',
            '                  spellcheck="false"',
            '                  @focus="onPaymentFocus(b)"',
            '                  @input="onPaymentInput(b)"',
            '                  :class="!b.currencyCode ? \'w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm bg-[#f8fafd] text-[#58667e] cursor-not-allowed\' : \'w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm text-[#191d23] placeholder:text-[#58667e] focus:outline-none focus:ring-2 focus:ring-main-blue/20\'"',
            '                />',
            '                <ul v-show="b.paymentOpen && (b.paymentSuggestions.length > 0 || b.paymentNoHits) && b.currencyCode && (b.paymentInput || \'\').trim().length >= 1" class="absolute left-0 right-0 top-full mt-1 z-30 max-h-48 overflow-y-auto rounded-lg border border-[#eff2f5] bg-white shadow-lg py-1 text-sm">',
            '                  <li v-for="p in b.paymentSuggestions" :key="p.payment_code">',
            '                    <button type="button" class="w-full text-left px-3 py-2 hover:bg-[#f8fafd] text-[#191d23]" @mousedown.prevent @click.stop="selectPayment(b, p)">',
            '                      <span class="font-medium">[[ p.name ]]</span>',
            '                      <span class="text-[#58667e] text-xs ml-1">[[ p.cur ]] · [[ p.payment_code ]]</span>',
            '                    </button>',
            '                  </li>',
            '                  <li v-if="b.paymentNoHits && b.paymentSuggestions.length === 0" class="px-3 py-2 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</li>',
            '                </ul>',
            '              </div>',
            '            </div>',
            '            <div class="rounded-lg bg-[#f8fafd] border border-[#eff2f5] p-3 md:p-4">',
            '              <div class="text-[10px] font-bold text-[#58667e] uppercase tracking-wider mb-2">[[ $t(\'main.guarantor.conditions_label\') ]]</div>',
            '              <p class="text-sm text-[#191d23] leading-relaxed whitespace-pre-wrap">[[ idx === 0 ? $t(\'main.guarantor.sample_block_desc\') : $t(\'main.guarantor.placeholder_conditions\') ]]</p>',
            '            </div>',
            '          </article>',
            '        </div>',
            '      </section>',
            '    </div>',
            '    <aside class="w-full lg:w-80 shrink-0 space-y-4">',
            '      <div class="rounded-xl border border-[#0a0b0d]/10 bg-[#0a0b0d] text-white p-4 md:p-5 shadow-sm">',
            '        <div class="flex items-start gap-3">',
            '          <span class="inline-flex w-8 h-8 rounded-lg bg-main-blue/20 text-main-blue items-center justify-center shrink-0">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '          </span>',
            '          <div class="min-w-0">',
            '            <h3 class="text-sm font-bold mb-2">[[ $t(\'main.guarantor.rules_title\') ]]</h3>',
            '            <ul class="text-xs text-white/80 space-y-2 list-disc list-inside leading-relaxed">',
            '              <li>[[ $t(\'main.guarantor.rules_item_1\') ]]</li>',
            '              <li>[[ $t(\'main.guarantor.rules_item_2\') ]]</li>',
            '              <li>[[ $t(\'main.guarantor.rules_item_3\') ]]</li>',
            '            </ul>',
            '          </div>',
            '        </div>',
            '      </div>',
            '    </aside>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
