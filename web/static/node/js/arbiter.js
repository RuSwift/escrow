/**
 * Vue 2 компонент: Арбитр
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('arbiter', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            addresses: [
                { id: 1, name: 'Root', role: 'active', tronAddress: 'TSZqbQBu9EQTAY1cD3fG6hJ0kLmN4vX8wY', ethereumAddress: '0x2bA8D0Bf5879a25b3c4e5f6a7b8c9d0e1f2a3b4c5d', createdAt: '21.02.2026, 01:40:30' },
                { id: 2, name: 'Backup', role: 'backup', tronAddress: 'TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt', ethereumAddress: '0x7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f', createdAt: '22.02.2026, 14:22:15' },
                { id: 3, name: 'Reserve', role: 'backup', tronAddress: 'TF4BB2BN8oYVyxL1aK3mP5qW9eRtU2vX', ethereumAddress: '0x9f0e1d2c3b4a5968e7f0a1b2c3d4e5f6a7b8c9d', createdAt: '23.02.2026, 09:15:00' }
            ]
        };
    },
    methods: {
        shortAddress: function(addr, head, tail) {
            if (!addr || addr.length < (head + tail + 3)) return addr;
            head = head || 10;
            tail = tail || 8;
            return addr.substring(0, head) + '...' + addr.substring(addr.length - tail);
        },
        copyToClipboard: function(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text);
            }
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Арбитр</nav>
        <div class="mb-6 rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3">
          <svg class="w-5 h-5 text-sky-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <p class="text-[13px] font-medium text-sky-900">Кошельки Арбитража участвуют в защищенных сделках</p>
        </div>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Арбитр</span>
          </div>
          <div class="p-6">
            <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
              <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Адреса арбитра</h3>
              <button type="button" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                Добавить кошелек арбитра
              </button>
            </div>
            <div class="overflow-x-auto rounded-xl border border-zinc-200">
              <table class="w-full text-left text-[13px]">
                <thead class="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Имя</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Роль</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">TRON адрес</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Ethereum адрес</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Создан</th>
                    <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in addresses" :key="a.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                    <td class="px-4 py-3 font-mono text-zinc-600">[[ a.id ]]</td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="text-zinc-800">[[ a.name ]]</span>
                      <button type="button" class="p-1 text-zinc-400 hover:text-blue-600 rounded" title="Редактировать">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3">
                      <span v-if="a.role === 'active'" class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">Активный</span>
                      <span v-else class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-700">Резервный</span>
                    </td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="font-mono text-zinc-700">[[ shortAddress(a.tronAddress, 12, 8) ]]</span>
                      <button type="button" @click="copyToClipboard(a.tronAddress)" class="p-1 text-zinc-400 hover:text-blue-600 rounded" title="Копировать">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3 flex items-center gap-2">
                      <span class="font-mono text-zinc-700">[[ shortAddress(a.ethereumAddress, 10, 8) ]]</span>
                      <button type="button" @click="copyToClipboard(a.ethereumAddress)" class="p-1 text-zinc-400 hover:text-blue-600 rounded" title="Копировать">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                      </button>
                    </td>
                    <td class="px-4 py-3 text-zinc-600">[[ a.createdAt ]]</td>
                    <td class="px-4 py-3">
                      <button type="button" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" title="Удалить">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
    `
});
