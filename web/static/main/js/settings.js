/**
 * Vue 2 компонент: Настройки (main) — заглушка
 */
Vue.component('settings', {
    delimiters: ['[[', ']]'],
    methods: {
        goDashboard: function() {
            if (window.__mainApp) window.__mainApp.currentPage = 'dashboard';
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('dashboard');
        }
    },
    template: `
    <div class="max-w-4xl mx-auto px-4 py-16 flex flex-col items-center justify-center min-h-[60vh] text-cmc-muted">
      <div class="w-16 h-16 rounded-3xl bg-[#eff2f5] flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-[#58667e]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
      </div>
      <h2 class="text-xl font-bold text-[#191d23] mb-2">[[ $t('main.settings.placeholder_title') ]]</h2>
      <p class="text-sm mb-6">[[ $t('main.settings.placeholder_desc') ]]</p>
      <button @click="goDashboard" class="cmc-btn-primary">[[ $t('main.settings.back_btn') ]]</button>
    </div>
    `
});
