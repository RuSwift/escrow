/**
 * Модалка: заявка на вывод (ramp-кошелёк, токен TRX/TRC-20, сумма, адрес).
 */
(function() {
    Vue.component('withdrawal-order-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false }
        },
        data: function() {
            return {
                loading: false,
                submitError: null,
                successUrl: null,
                rampWallets: [],
                walletId: '',
                tokenMode: 'native',
                selectedTokenContract: '',
                amount: '',
                destination: ''
            };
        },
        computed: {
            collateralTokens: function() {
                var raw = typeof window !== 'undefined' ? window.__COLLATERAL_STABLECOIN_TOKENS__ : null;
                if (!raw || !Array.isArray(raw)) return [];
                return raw.filter(function(t) {
                    return (t.network || '').toUpperCase() === 'TRON';
                });
            }
        },
        watch: {
            show: function(v) {
                if (v) {
                    this.submitError = null;
                    this.successUrl = null;
                    this.fetchWallets();
                }
            },
            tokenMode: function() {
                this.submitError = null;
            }
        },
        methods: {
            rampApiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets';
            },
            rampAuthHeaders: function() {
                var h = { 'Content-Type': 'application/json', Accept: 'application/json' };
                var token = null;
                try {
                    var key = (typeof window !== 'undefined' && window.main_auth_token_key)
                        ? window.main_auth_token_key
                        : 'main_auth_token';
                    token = localStorage.getItem(key);
                } catch (e) {}
                if (token) h.Authorization = 'Bearer ' + token;
                return h;
            },
            fetchWallets: function() {
                var self = this;
                var base = this.rampApiBase();
                if (!base) {
                    self.rampWallets = [];
                    return;
                }
                self.loading = true;
                fetch(base, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.rampWallets = (data && data.items) ? data.items : [];
                    })
                    .catch(function() {
                        self.rampWallets = [];
                    })
                    .finally(function() {
                        self.loading = false;
                    });
            },
            close: function() {
                this.$emit('close');
            },
            submit: function() {
                var self = this;
                self.submitError = null;
                self.successUrl = null;
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) {
                    self.submitError = self.$t('main.withdrawal_modal.error_no_space');
                    return;
                }
                var wid = parseInt(String(self.walletId), 10);
                if (!isFinite(wid) || wid < 1) {
                    self.submitError = self.$t('main.withdrawal_modal.error_wallet');
                    return;
                }
                var dest = (self.destination || '').trim();
                if (!dest || dest.length < 26) {
                    self.submitError = self.$t('main.withdrawal_modal.error_dest');
                    return;
                }
                var amtStr = String(self.amount || '').replace(',', '.').trim();
                var amt = parseFloat(amtStr);
                if (!isFinite(amt) || amt <= 0) {
                    self.submitError = self.$t('main.withdrawal_modal.error_amount');
                    return;
                }
                var tokenType = self.tokenMode === 'native' ? 'native' : 'trc20';
                var symbol = tokenType === 'native' ? 'TRX' : '';
                var contract = null;
                if (tokenType === 'trc20') {
                    var ct = self.collateralTokens.find(function(x) {
                        return (x.contract_address || '') === self.selectedTokenContract;
                    });
                    if (!ct) {
                        self.submitError = self.$t('main.withdrawal_modal.error_token');
                        return;
                    }
                    symbol = (ct.symbol || '').toUpperCase();
                    contract = (ct.contract_address || '').trim();
                }
                var amountRaw;
                if (tokenType === 'native') {
                    amountRaw = Math.round(amt * 1e6);
                } else {
                    var dec = typeof ct.decimals === 'number' ? ct.decimals : 6;
                    amountRaw = Math.round(amt * Math.pow(10, dec));
                }
                var body = {
                    wallet_id: wid,
                    token_type: tokenType,
                    symbol: symbol,
                    contract_address: contract,
                    amount_raw: amountRaw,
                    destination_address: dest
                };
                self.loading = true;
                fetch('/v1/spaces/' + encodeURIComponent(space) + '/orders/withdrawal', {
                    method: 'POST',
                    headers: self.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        if (!r.ok) {
                            return r.json().then(function(d) {
                                throw new Error(typeof d.detail === 'string' ? d.detail : 'HTTP ' + r.status);
                            });
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.successUrl = (data && data.sign_url) ? data.sign_url : '';
                        self.$emit('created', data);
                        self.fetchOrdersParent();
                    })
                    .catch(function(e) {
                        self.submitError = String(e && e.message ? e.message : e);
                    })
                    .finally(function() {
                        self.loading = false;
                    });
            },
            fetchOrdersParent: function() {
                if (this.$parent && typeof this.$parent.fetchOrders === 'function') {
                    this.$parent.fetchOrders();
                }
            }
        },
        template: '<transition name="fade">' +
            '<div v-if="show" class="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="close">' +
            '<div class="bg-white rounded-xl shadow-xl border border-[#eff2f5] w-full max-w-lg max-h-[90vh] flex flex-col" role="dialog" aria-modal="true" @click.stop>' +
            '<div class="flex items-center justify-between gap-4 px-4 py-3 border-b border-[#eff2f5] shrink-0">' +
            '<h2 class="text-lg font-bold text-[#191d23]">[[ $t(\'main.withdrawal_modal.title\') ]]</h2>' +
            '<button type="button" class="p-2 rounded-lg text-[#58667e] hover:bg-[#eff2f5]" @click="close" :aria-label="$t(\'main.withdrawal_modal.close\')">' +
            '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>' +
            '</button></div>' +
            '<div class="overflow-auto p-4 flex-1 min-h-0 space-y-4 text-sm">' +
            '<p v-if="submitError" class="text-main-red text-xs">[[ submitError ]]</p>' +
            '<p v-if="successUrl" class="text-xs text-emerald-800 break-all">' +
            '<span class="font-semibold">[[ $t(\'main.withdrawal_modal.sign_link\') ]]</span><br>' +
            '<a :href="successUrl" class="text-main-blue underline" target="_blank" rel="noopener">[[ successUrl ]]</a></p>' +
            '<div v-if="loading && !rampWallets.length" class="text-cmc-muted text-xs">[[ $t(\'main.loading\') ]]</div>' +
            '<div><label class="block text-xs font-semibold text-[#58667e] mb-1">[[ $t(\'main.withdrawal_modal.wallet\') ]]</label>' +
            '<select v-model="walletId" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm">' +
            '<option value="" disabled>[[ $t(\'main.withdrawal_modal.wallet_placeholder\') ]]</option>' +
            '<option v-for="w in rampWallets" :key="\'rw-\' + w.id" :value="w.id">[[ w.name ]] ([[ w.role ]])</option>' +
            '</select></div>' +
            '<div><label class="block text-xs font-semibold text-[#58667e] mb-1">[[ $t(\'main.withdrawal_modal.token\') ]]</label>' +
            '<select v-model="tokenMode" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm mb-2">' +
            '<option value="native">TRX</option>' +
            '<option value="trc20">[[ $t(\'main.withdrawal_modal.token_trc20\') ]]</option>' +
            '</select>' +
            '<select v-if="tokenMode === \'trc20\'" v-model="selectedTokenContract" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm">' +
            '<option value="" disabled>[[ $t(\'main.withdrawal_modal.token_pick\') ]]</option>' +
            '<option v-for="tok in collateralTokens" :key="tok.contract_address" :value="tok.contract_address">[[ tok.symbol ]]</option>' +
            '</select></div>' +
            '<div><label class="block text-xs font-semibold text-[#58667e] mb-1">[[ $t(\'main.withdrawal_modal.amount\') ]]</label>' +
            '<input v-model="amount" type="text" inputmode="decimal" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm" :placeholder="$t(\'main.withdrawal_modal.amount_ph\')" /></div>' +
            '<div><label class="block text-xs font-semibold text-[#58667e] mb-1">[[ $t(\'main.withdrawal_modal.destination\') ]]</label>' +
            '<input v-model="destination" type="text" class="w-full px-3 py-2 border border-[#eff2f5] rounded-lg text-sm font-mono" :placeholder="$t(\'main.withdrawal_modal.destination_ph\')" /></div>' +
            '</div>' +
            '<div class="px-4 py-3 border-t border-[#eff2f5] flex justify-end gap-2 shrink-0">' +
            '<button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg border border-[#eff2f5] bg-white text-[#191d23] hover:bg-[#f8fafd]" @click="close">[[ $t(\'main.withdrawal_modal.cancel\') ]]</button>' +
            '<button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg bg-main-blue text-white hover:opacity-90 disabled:opacity-50" :disabled="loading" @click="submit">[[ $t(\'main.withdrawal_modal.submit\') ]]</button>' +
            '</div></div></div>' +
            '</transition>'
    });
})();
