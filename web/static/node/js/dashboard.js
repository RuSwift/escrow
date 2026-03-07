/**
 * Vue 2 компонент: Дашборд
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('dashboard', {
    delimiters: ['[[', ']]'],
    props: {
        isNodeInitialized: { type: Boolean, default: false }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Дашборд</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Dashboard</span>
          </div>
          <div class="p-10">
            <h2 class="text-2xl font-bold text-zinc-900 mb-8 tracking-tight">Добро пожаловать в админ-панель!</h2>
            <div v-if="isNodeInitialized" class="mb-6 rounded-xl bg-emerald-50 border border-emerald-100 p-4 text-[13px] font-medium text-emerald-900">
              Нода инициализирована: ключ и service endpoint настроены.
            </div>
            <div v-else class="mb-6 rounded-xl bg-amber-50 border border-amber-100 p-4 text-[13px] font-medium text-amber-900">
              Нода не инициализирована. Настройте ключ и service endpoint через API.
            </div>
            <div class="mb-6">
              <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-[0.1em] mb-6">Статистика</h3>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="flex-1 bg-white border border-blue-100 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
                  <div class="mb-4 text-blue-600"><svg class="w-10 h-10 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg></div>
                  <div class="text-3xl font-bold text-zinc-900 mb-1">[[ stats.users ]]</div>
                  <div class="text-[13px] font-medium text-zinc-500 uppercase tracking-wide">Пользователи</div>
                </div>
                <div class="flex-1 bg-white border border-sky-100 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
                  <div class="mb-4 text-sky-400"><svg class="w-10 h-10 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg></div>
                  <div class="text-3xl font-bold text-zinc-900 mb-1">[[ stats.managers ]]</div>
                  <div class="text-[13px] font-medium text-zinc-500 uppercase tracking-wide">Менеджеры</div>
                </div>
                <div class="flex-1 bg-white border border-emerald-100 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
                  <div class="mb-4 text-emerald-500"><svg class="w-10 h-10 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg></div>
                  <div class="text-3xl font-bold text-zinc-900 mb-1">[[ stats.wallets ]]</div>
                  <div class="text-[13px] font-medium text-zinc-500 uppercase tracking-wide">Кошельки</div>
                </div>
                <div class="flex-1 bg-white border border-amber-100 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
                  <div class="mb-4 text-amber-400"><svg class="w-10 h-10 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg></div>
                  <div class="text-3xl font-bold text-zinc-900 mb-1">[[ stats.arbiterWallets ]]</div>
                  <div class="text-[13px] font-medium text-zinc-500 uppercase tracking-wide">Кошельки арбитража</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <footer class="mt-auto pt-12 text-center text-[11px] text-zinc-400 font-medium tracking-wide uppercase">&copy; Escrow Node &bull; v0.1.0</footer>
    </div>
    `,
    data: function() {
        return {
            stats: { users: '—', managers: '—', wallets: '—', arbiterWallets: '—' }
        };
    }
});
