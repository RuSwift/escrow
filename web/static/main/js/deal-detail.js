/**
 * Vue 2 компонент: детальный просмотр сделки (main), UX как в _temp EscrowDetail
 */
Vue.component('detail', {
    delimiters: ['[[', ']]'],
    props: {
        escrowId: { type: String, default: null }
    },
    data: function() {
        var mockEscrows = [
            { id: 'esc-001', title: 'Premium Domain Purchase: crypto-vault.com', description: 'Transfer of ownership for the domain crypto-vault.com. Funds to be released upon successful DNS verification.', amount: 2.5, currency: 'BTC', status: 'pending', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-11T20:52:00' },
            { id: 'esc-002', title: 'OTC 50K USDT', description: 'High-value OTC trade', amount: 50000, currency: 'USDT', status: 'pending', buyer_id: '0x33C...7788F', seller_id: '0x55D...9900A', created_at: '2026-03-11T09:15:00' },
            { id: 'esc-003', title: 'NFT #4421', description: 'Art piece transfer', amount: 0.8, currency: 'ETH', status: 'released', buyer_id: '0x99B...3344D', seller_id: '0x11A...5566E', created_at: '2026-03-08T16:00:00' },
            { id: 'esc-004', title: 'Software license', description: 'Annual enterprise license', amount: 12000, currency: 'USDT', status: 'disputed', buyer_id: '0x22B...4455C', seller_id: '0x77E...6677F', created_at: '2026-03-09T11:20:00' },
            { id: 'esc-005', title: 'Hardware batch', description: 'Miners delivery', amount: 150000, currency: 'USDT', status: 'funded', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-12T08:45:00' }
        ];
        return {
            mockEscrows: mockEscrows,
            newMessage: '',
            messages: [
                { id: 1, sender_id: 'user_1', content: "Hello! I've initiated the escrow. Please confirm the domain transfer details.", created_at: '2026-03-11T20:52:00' }
            ]
        };
    },
    computed: {
        escrow: function() {
            if (!this.escrowId) return null;
            return this.mockEscrows.filter(function(e) { return e.id === this.escrowId; }.bind(this))[0] || this.mockEscrows[0];
        },
        statusClass: function() {
            if (!this.escrow) return '';
            var s = this.escrow.status;
            return s === 'pending' ? 'bg-amber-100 text-amber-700' : s === 'funded' ? 'bg-blue-100 text-blue-700' : s === 'released' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700';
        },
        statusDotClass: function() {
            if (!this.escrow) return '';
            var s = this.escrow.status;
            return s === 'pending' ? 'bg-amber-500' : s === 'funded' ? 'bg-blue-500' : s === 'released' ? 'bg-emerald-500' : 'bg-rose-500';
        },
        trustLayerFee: function() {
            if (!this.escrow) return '—';
            return (this.escrow.amount * 0.01).toFixed(4) + ' ' + this.escrow.currency;
        }
    },
    methods: {
        goBack: function() {
            if (window.__mainApp) {
                window.__mainApp.currentPage = 'dashboard';
                window.__mainApp.selectedEscrowId = null;
            }
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('dashboard');
        },
        formatDate: function(created_at) {
            if (!created_at) return '—';
            var d = new Date(created_at);
            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
        },
        formatTime: function(created_at) {
            if (!created_at) return '';
            var d = new Date(created_at);
            return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        },
        sendMessage: function(e) {
            e.preventDefault();
            if (!this.newMessage.trim()) return;
            this.messages.push({ id: this.messages.length + 1, sender_id: 'user_1', content: this.newMessage.trim(), created_at: new Date().toISOString() });
            this.newMessage = '';
        }
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-4 md:py-8">
      <button type="button" @click="goBack" class="flex items-center gap-2 text-cmc-muted hover:text-[#191d23] mb-4 md:mb-6 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
        [[ $t('main.detail.back_to_dashboard') ]]
      </button>

      <div v-if="!escrow" class="p-8 text-center text-cmc-muted">[[ $t('main.detail.loading') ]]</div>
      <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
        <div class="lg:col-span-2 space-y-6">
          <div class="cmc-card p-4 md:p-6">
            <div class="flex flex-col sm:flex-row justify-between items-start gap-4 mb-6">
              <div>
                <div class="flex flex-wrap items-center gap-2 mb-2">
                  <div :class="['inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider', statusClass]">
                    <span :class="['w-1.5 h-1.5 rounded-full shrink-0', statusDotClass]"></span>
                    [[ escrow.status ]]
                  </div>
                  <span class="text-[10px] text-cmc-muted">ID: [[ escrow.id ]]</span>
                  <span class="hidden sm:inline text-xs text-cmc-muted">•</span>
                  <span class="text-[10px] text-cmc-muted">[[ formatDate(escrow.created_at) ]]</span>
                </div>
                <h1 class="text-xl md:text-2xl font-bold">[[ escrow.title ]]</h1>
              </div>
              <div class="sm:text-right w-full sm:w-auto p-3 sm:p-0 bg-[#f8fafd] sm:bg-transparent rounded-lg sm:rounded-none">
                <div class="text-xl md:text-2xl font-bold text-main-blue">[[ escrow.amount ]] [[ escrow.currency ]]</div>
                <div class="text-[10px] md:text-xs text-cmc-muted">[[ $t('main.detail.locked_in_escrow') ]]</div>
              </div>
            </div>
            <p class="text-cmc-muted mb-8">[[ escrow.description ]]</p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="p-4 bg-[#f8fafd] rounded-xl border border-[#eff2f5]">
                <div class="text-xs text-cmc-muted mb-1">[[ $t('main.detail.buyer_address') ]]</div>
                <div class="font-mono text-xs truncate">[[ escrow.buyer_id ]]</div>
              </div>
              <div class="p-4 bg-[#f8fafd] rounded-xl border border-[#eff2f5]">
                <div class="text-xs text-cmc-muted mb-1">[[ $t('main.detail.seller_address') ]]</div>
                <div class="font-mono text-xs truncate">[[ escrow.seller_id ]]</div>
              </div>
            </div>
          </div>

          <div class="cmc-card flex flex-col h-[400px]">
            <div class="p-4 border-b border-[#eff2f5] flex items-center justify-between">
              <div class="flex items-center gap-2 font-bold">
                <svg class="w-5 h-5 text-main-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                [[ $t('main.detail.communication_title') ]]
              </div>
              <div class="text-xs text-cmc-muted flex items-center gap-1">
                <span class="w-2 h-2 rounded-full bg-main-green animate-pulse"></span>
                [[ $t('main.detail.live_chat_active') ]]
              </div>
            </div>
            <div class="flex-1 overflow-y-auto p-4 space-y-4">
              <div v-for="msg in messages" :key="msg.id" :class="['flex', msg.sender_id === 'user_1' ? 'justify-end' : 'justify-start']">
                <div :class="['max-w-[80%] p-3 rounded-2xl text-sm', msg.sender_id === 'user_1' ? 'bg-main-blue text-white rounded-tr-none' : 'bg-[#f8fafd] border border-[#eff2f5] rounded-tl-none']">
                  <div class="mb-1">[[ msg.content ]]</div>
                  <div :class="['text-[10px] opacity-70', msg.sender_id === 'user_1' ? 'text-right' : '']">[[ formatTime(msg.created_at) ]]</div>
                </div>
              </div>
            </div>
            <form @submit="sendMessage" class="p-4 border-t border-[#eff2f5] flex gap-2">
              <input v-model="newMessage" type="text" :placeholder="$t('main.detail.type_message')" class="flex-1 px-4 py-2 bg-[#f8fafd] border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
              <button type="submit" class="p-2 bg-main-blue text-white rounded-xl hover:opacity-90 transition-opacity">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
              </button>
            </form>
          </div>
        </div>

        <div class="space-y-6">
          <div class="cmc-card p-6">
            <h3 class="font-bold mb-4 flex items-center gap-2">
              <svg class="w-5 h-5 text-main-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
              [[ $t('main.detail.escrow_controls_title') ]]
            </h3>
            <div class="space-y-3">
              <button v-if="escrow.status === 'pending'" type="button" class="w-full cmc-btn-primary flex items-center justify-center gap-2 py-3">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                [[ $t('main.detail.fund_escrow') ]]
              </button>
              <div v-if="escrow.status === 'funded'" class="space-y-2">
                <button type="button" class="w-full bg-main-green text-white py-3 rounded-lg font-bold hover:opacity-90 flex items-center justify-center gap-2">[[ $t('main.detail.release_funds') ]]</button>
                <button type="button" class="w-full bg-main-red text-white py-3 rounded-lg font-bold hover:opacity-90 flex items-center justify-center gap-2">[[ $t('main.detail.raise_dispute') ]]</button>
              </div>
              <div v-if="escrow.status === 'released'" class="p-4 rounded-xl bg-main-green/10 border border-main-green/30 flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-main-green flex items-center justify-center shrink-0">
                  <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                </div>
                <p class="text-sm font-medium text-main-green">[[ $t('main.detail.funds_released') ]]</p>
              </div>
              <div v-if="escrow.status === 'disputed'" class="p-4 rounded-xl bg-main-red/10 border border-main-red/30 flex items-start gap-3">
                <div class="w-10 h-10 rounded-full bg-main-red flex items-center justify-center shrink-0">
                  <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                </div>
                <div>
                  <p class="text-sm font-bold text-main-red">[[ $t('main.detail.under_dispute') ]]</p>
                  <p class="text-xs text-main-red/90 mt-0.5">[[ $t('main.detail.arbiter_reviewing') ]]</p>
                </div>
              </div>
            </div>
            <div class="mt-6 pt-6 border-t border-[#eff2f5]">
              <div class="flex justify-between text-xs mb-2">
                <span class="text-cmc-muted">[[ $t('main.detail.network_fee') ]]</span>
                <span class="font-bold">0.0001 [[ escrow.currency ]]</span>
              </div>
              <div class="flex justify-between text-xs">
                <span class="text-cmc-muted">[[ $t('main.detail.trustlayer_fee') ]]</span>
                <span class="font-bold">[[ trustLayerFee ]]</span>
              </div>
            </div>
          </div>

          <div class="cmc-card p-6 border-2 border-dashed border-[#eff2f5] rounded-xl">
            <div class="flex items-center gap-2 font-bold mb-2">
              <svg class="w-5 h-5 text-main-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
              [[ $t('main.detail.ai_audit_title') ]]
            </div>
            <button type="button" class="text-[10px] font-bold text-main-blue hover:underline">[[ $t('main.detail.run_audit') ]]</button>
            <p class="text-xs text-cmc-muted mt-4">[[ $t('main.detail.ai_audit_hint') ]]</p>
          </div>
        </div>
      </div>
    </div>
    `
});
