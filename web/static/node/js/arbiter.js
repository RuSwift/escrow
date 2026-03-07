/**
 * Vue 2 компонент: Арбитр
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('arbiter', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Арбитр</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Арбитр</span>
          </div>
          <div class="p-10 text-center">
            <p class="text-zinc-500 text-[15px] font-medium">Страница в разработке</p>
          </div>
        </div>
      </div>
    </div>
    `
});
