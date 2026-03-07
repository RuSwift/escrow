/**
 * Vue 2 компонент: Кошельки
 * Подключение: после vue.min.js и modal.js, перед app.js
 */
Vue.component('wallets', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            activeTab: 'wallets',
            searchQuery: '',
            showAddWalletModal: false,
            addForm: {
                name: '',
                mnemonic: ''
            },
            walletList: [
                { id: 1, name: 'Main Trading', address: '0x71C7a3b9e2f1d4c5a6b7e8f9a0b1c2d3e276F', blockchain: 'ethereum', balance: '12.45', currency: 'ETH' },
                { id: 2, name: 'Liquidity Pool', address: 'TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt', blockchain: 'tron', balance: '45,000', currency: 'USDT' },
                { id: 3, name: 'Operational', address: '0xRx1234abcd5678efgh9012ijkl3456', blockchain: 'ethereum', balance: '1.20', currency: 'ETH' }
            ]
        };
    },
    methods: {
        shortAddress: function(addr) {
            if (!addr || addr.length < 14) return addr;
            return addr.substring(0, 6) + '...' + addr.substring(addr.length - 4);
        },
        openAddWallet: function() {
            this.addForm = { name: '', mnemonic: '' };
            this.showAddWalletModal = true;
        },
        closeAddWallet: function() {
            this.showAddWalletModal = false;
        },
        submitAddWallet: function() {
            if (!this.addForm.name.trim()) return;
            this.walletList.push({
                id: this.walletList.length + 1,
                name: this.addForm.name.trim(),
                address: '0x' + Math.random().toString(16).slice(2, 10) + '...' + Math.random().toString(16).slice(2, 6),
                blockchain: 'ethereum',
                balance: '0',
                currency: 'ETH'
            });
            this.closeAddWallet();
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Кошельки</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Управление кошельками и менеджерами</span>
          </div>
          <div class="p-6">
            <div class="flex flex-wrap items-center gap-4 border-b border-zinc-200 mb-6">
              <button type="button" @click="activeTab = 'wallets'" :class="activeTab === 'wallets' ? 'text-blue-600 border-b-2 border-blue-600 pb-2 -mb-px font-semibold' : 'text-zinc-500 hover:text-zinc-700'" class="text-[13px] uppercase tracking-tight">
                Кошельки для операций
              </button>
              <button type="button" @click="activeTab = 'managers'" :class="activeTab === 'managers' ? 'text-blue-600 border-b-2 border-blue-600 pb-2 -mb-px font-semibold' : 'text-zinc-500 hover:text-zinc-700'" class="text-[13px] uppercase tracking-tight">
                Менеджеры
              </button>
            </div>
            <div v-show="activeTab === 'wallets'" class="space-y-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <div class="flex flex-wrap items-center gap-3">
                  <input type="text" v-model="searchQuery" placeholder="Поиск по имени или адресу..." class="px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] w-64 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
                  <button type="button" class="px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] font-medium text-zinc-600 hover:bg-zinc-50">Все кошельки</button>
                </div>
                <button type="button" @click="openAddWallet" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  Добавить кошелек
                </button>
              </div>
              <div class="overflow-x-auto rounded-xl border border-zinc-200 fade-in-content">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Имя кошелька</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Адрес</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Блокчейн</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Баланс</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="w in walletList" :key="w.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ w.name ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">[[ shortAddress(w.address) ]]</td>
                      <td class="px-4 py-3">
                        <span v-if="w.blockchain === 'ethereum'" class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">Ethereum</span>
                        <span v-else class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">TRON</span>
                      </td>
                      <td class="px-4 py-3 text-zinc-800">[[ w.balance ]] [[ w.currency ]]</td>
                      <td class="px-4 py-3">
                        <button type="button" class="p-1.5 text-zinc-400 hover:text-blue-600 rounded" title="Редактировать">
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div v-show="activeTab === 'managers'" class="py-8 text-center text-zinc-500 text-[13px]">
              Раздел «Менеджеры» в разработке
            </div>
          </div>
        </div>
      </div>

      <modal :show="showAddWalletModal" title="Добавить кошелек" @close="closeAddWallet">
        <div class="space-y-4">
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Имя кошелька</label>
            <input type="text" v-model="addForm.name" placeholder="Введите имя кошелька" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Мнемоническая фраза</label>
            <textarea v-model="addForm.mnemonic" rows="4" placeholder="Введите мнемоническую фразу (12-24 слова)" class="w-full px-4 py-2.5 border border-zinc-200 rounded-lg text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"></textarea>
            <p class="mt-1.5 text-[12px] text-zinc-400">Мнемоническая фраза будет зашифрована и сохранена в базе данных.</p>
          </div>
        </div>
        <template slot="footer">
          <button type="button" @click="closeAddWallet" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-100">Отмена</button>
          <button type="button" @click="submitAddWallet" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700">Создать</button>
        </template>
      </modal>
    </div>
    `
});
