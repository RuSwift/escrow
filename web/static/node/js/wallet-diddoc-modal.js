/**
 * Vue 2 компонент: модалка просмотра DID Document кошелька.
 * Один DID и один DID Document со всеми адресами (TRON и Ethereum). API: GET /v1/wallets/{id}/did-documents.
 */
(function() {
    var API_BASE = '/v1';
    var WALLETS_API = API_BASE + '/wallets';

    Vue.component('wallet-diddoc-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false },
            wallet: { type: Object, default: null }
        },
        data: function() {
            return {
                loading: false,
                loadError: '',
                data: null
            };
        },
        watch: {
            show: function(visible) {
                if (visible && this.wallet && this.wallet.id) this.load();
                else this.data = null;
            }
        },
        methods: {
            load: function() {
                var self = this;
                if (!this.wallet || !this.wallet.id) return;
                self.loading = true;
                self.loadError = '';
                fetch(WALLETS_API + '/' + this.wallet.id + '/did-documents', { credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || self.$t('node.wallets.diddoc_load_error')); });
                        return r.json();
                    })
                    .then(function(d) {
                        self.data = d;
                        self.loading = false;
                    })
                    .catch(function(err) {
                        self.loadError = err.message || self.$t('node.wallets.diddoc_load_error');
                        self.loading = false;
                    });
            },
            close: function() {
                this.$emit('close');
            },
            jsonString: function(obj) {
                try {
                    return typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
                } catch (e) {
                    return String(obj);
                }
            }
        },
        template: `
    <modal :show="show" :title="$t('node.wallets.diddoc_modal_title')" size="large" @close="close">
      <div v-if="wallet" class="space-y-4">
        <p class="text-[13px] text-zinc-600">[[ $t('node.wallets.diddoc_modal_wallet') ]]: <strong>[[ wallet.name ]]</strong></p>
        <p v-if="loading" class="text-zinc-500 text-[13px]">[[ $t('node.loading') ]]</p>
        <p v-else-if="loadError" class="text-red-600 text-[13px]">[[ loadError ]]</p>
        <template v-else-if="data">
          <div class="rounded-xl border border-zinc-200 overflow-hidden">
            <div class="p-4 space-y-3">
              <div>
                <p class="text-[12px] text-zinc-500">DID:</p>
                <p class="font-mono text-[13px] text-zinc-800 break-all">[[ data.did ]]</p>
              </div>
              <div>
                <p class="text-[12px] text-zinc-500">DID Document:</p>
                <pre class="p-3 bg-zinc-50 rounded-lg text-[12px] overflow-x-auto max-h-64 overflow-y-auto border border-zinc-100">[[ jsonString(data.did_document) ]]</pre>
              </div>
            </div>
          </div>
        </template>
      </div>
      <template slot="footer">
        <button type="button" @click="close" class="px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-[13px] font-medium hover:bg-zinc-300">[[ $t('node.wallets.diddoc_close') ]]</button>
      </template>
    </modal>
    `
    });
})();
