/**
 * Vue 2 компонент: Кошельки
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('wallets', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Кошельки</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Кошельки</span>
          </div>
          <div class="p-10 text-center">
            <p class="text-zinc-500 text-[15px] font-medium">Страница в разработке</p>
          </div>
        </div>
      </div>
    </div>
    `
});
