/**
 * Vue 2 компонент: Поддержка
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('support', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Поддержка</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Поддержка</span>
          </div>
          <div class="p-10 text-center">
            <p class="text-zinc-500 text-[15px] font-medium">Страница в разработке</p>
          </div>
        </div>
      </div>
    </div>
    `
});
