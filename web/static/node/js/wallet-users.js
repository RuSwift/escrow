/**
 * Vue 2 компонент: Пользователи (маркетплейс)
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('wallet-users', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            searchQuery: '',
            networkFilter: 'all',
            currentPage: 1,
            perPage: 5,
            totalMock: 124,
            users: [
                { id: 5, walletAddress: 'TFMwBmCj7xQ8LpJk2nV4bR9sT1JgT5S', network: 'TRON', initial: 'U', username: 'User_TFMwBm', status: 'pending', hasPanel: true, balance: '0,00', currency: 'USDT', subCurrency: 'TETHER USD', createdAt: '24.02.2026' },
                { id: 4, walletAddress: 'TXCf4Beo3kL9mNpQ2wY6vX8hR7YR788j', network: 'TRON', initial: 'U', username: 'User_TXCf4B', status: 'pending', hasPanel: true, balance: '0,00', currency: 'USDT', subCurrency: 'TETHER USD', createdAt: '24.02.2026' },
                { id: 3, walletAddress: 'TF4BB2BN8oYVyxL1aK3mP5qW9eRtU', network: 'TRON', initial: 'S', username: 'Sender', status: 'verified', hasPanel: true, balance: '0,00', currency: 'USDT', subCurrency: 'TETHER USD', createdAt: '21.02.2026' },
                { id: 2, walletAddress: 'TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ', network: 'TRON', initial: 'R', username: 'Reciever', status: 'verified', hasPanel: true, balance: '0,00', currency: 'USDT', subCurrency: 'TETHER USD', createdAt: '21.02.2026' },
                { id: 1, walletAddress: 'TSZqbQBu9EQTAY1cD3fG6hJ0kLmN', network: 'TRON', initial: 'A', username: 'Arbiter as user', status: 'pending', hasPanel: false, balance: '0,00', currency: 'USDT', subCurrency: 'TETHER USD', createdAt: '19.02.2026' }
            ]
        };
    },
    computed: {
        displayedUsers: function() {
            var q = (this.searchQuery || '').toLowerCase();
            var list = this.users;
            if (q) {
                list = list.filter(function(u) {
                    return (u.walletAddress && u.walletAddress.toLowerCase().indexOf(q) !== -1) ||
                           (u.username && u.username.toLowerCase().indexOf(q) !== -1) ||
                           (String(u.id)).indexOf(q) !== -1;
                });
            }
            var start = (this.currentPage - 1) * this.perPage;
            return list.slice(start, start + this.perPage);
        },
        totalFiltered: function() {
            var q = (this.searchQuery || '').toLowerCase();
            if (!q) return this.totalMock;
            return this.users.filter(function(u) {
                return (u.walletAddress && u.walletAddress.toLowerCase().indexOf(q) !== -1) ||
                       (u.username && u.username.toLowerCase().indexOf(q) !== -1) ||
                       (String(u.id)).indexOf(q) !== -1;
            }).length;
        },
        totalPages: function() {
            return Math.max(1, Math.ceil(this.totalFiltered / this.perPage));
        },
        pageNumbers: function() {
            var n = this.totalPages;
            var out = [];
            for (var i = 1; i <= n; i++) out.push(i);
            return out;
        },
        fromCount: function() {
            return (this.currentPage - 1) * this.perPage + 1;
        },
        toCount: function() {
            return Math.min(this.currentPage * this.perPage, this.totalFiltered);
        }
    },
    methods: {
        shortAddress: function(addr) {
            if (!addr || addr.length < 12) return addr;
            return addr.substring(0, 8) + '...' + addr.substring(addr.length - 6);
        },
        goPage: function(p) {
            if (p >= 1 && p <= this.totalPages) this.currentPage = p;
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Пользователи</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Пользователи</span>
          </div>
          <div class="p-6">
            <h2 class="text-xl font-bold text-zinc-900 mb-1 tracking-tight">Пользователи</h2>
            <p class="text-[13px] text-zinc-500 mb-6">Управление учетными записями и правами доступа в системе.</p>
            <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div class="flex items-center gap-2">
                <button type="button" class="px-4 py-2 border border-zinc-200 rounded-lg text-[13px] font-medium text-zinc-700 hover:bg-zinc-50 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                  Экспорт
                </button>
                <button type="button" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  Новый пользователь
                </button>
              </div>
            </div>
            <div class="flex flex-wrap items-center gap-3 mb-4">
              <div class="flex-1 min-w-[200px] max-w-md">
                <input type="text" v-model="searchQuery" placeholder="Поиск по адресу, имени или ID..." class="w-full px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              </div>
              <button type="button" class="px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] font-medium text-zinc-600 hover:bg-zinc-50">Все сети</button>
              <button type="button" class="p-2.5 border border-zinc-200 rounded-xl text-zinc-500 hover:bg-zinc-50">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
              </button>
              <button type="button" class="p-2.5 border border-zinc-200 rounded-xl text-zinc-500 hover:bg-zinc-50">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
              </button>
            </div>
            <div class="overflow-x-auto rounded-xl border border-zinc-200 fade-in-content">
              <table class="w-full text-left text-[13px]">
                <thead class="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Адрес кошелька</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Сеть</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Имя пользователя</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Статус</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Панель</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Баланс</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Дата создания</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="u in displayedUsers" :key="u.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                    <td class="px-4 py-3 font-mono text-zinc-600">#[[ u.id.toString().padStart(3, '0') ]]</td>
                    <td class="px-4 py-3 font-mono text-zinc-700">[[ shortAddress(u.walletAddress) ]]</td>
                    <td class="px-4 py-3"><span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">[[ u.network ]]</span></td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="w-7 h-7 rounded-full bg-zinc-200 flex items-center justify-center text-[11px] font-bold text-zinc-600 shrink-0">[[ u.initial ]]</span>
                      <span class="text-zinc-800">[[ u.username ]]</span>
                    </td>
                    <td class="px-4 py-3">
                      <span v-if="u.status === 'verified'" class="inline-flex items-center gap-1.5 text-emerald-600">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Верифицирован
                      </span>
                      <span v-else class="inline-flex items-center gap-1.5 text-zinc-500">
                        <span class="w-1.5 h-1.5 rounded-full bg-zinc-400"></span>
                        Ожидает
                      </span>
                    </td>
                    <td class="px-4 py-3"><span class="w-2 h-2 rounded-full bg-zinc-300 inline-block" :class="{ 'opacity-50': !u.hasPanel }"></span></td>
                    <td class="px-4 py-3">
                      <div class="text-zinc-800">[[ u.balance ]] [[ u.currency ]]</div>
                      <div class="text-[11px] text-zinc-400">[[ u.subCurrency ]]</div>
                    </td>
                    <td class="px-4 py-3 text-zinc-600">[[ u.createdAt ]]</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="mt-4 flex flex-wrap items-center justify-between gap-4">
              <p class="text-[13px] text-zinc-500">Показано [[ fromCount ]]-[[ toCount ]] из [[ totalFiltered ]] пользователей</p>
              <div class="flex items-center gap-1">
                <button type="button" @click="goPage(currentPage - 1)" :disabled="currentPage <= 1" class="px-3 py-1.5 rounded-lg text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed">Назад</button>
                <button type="button" v-for="p in pageNumbers" :key="p" @click="goPage(p)" :class="p === currentPage ? 'bg-blue-600 text-white' : 'text-zinc-600 hover:bg-zinc-100'" class="min-w-[2rem] px-3 py-1.5 rounded-lg text-[13px] font-medium">[[ p ]]</button>
                <button type="button" @click="goPage(currentPage + 1)" :disabled="currentPage >= totalPages" class="px-3 py-1.5 rounded-lg text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed">Вперед</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    `
});
