/**
 * Vue 2 компонент: Как это работает (main)
 */
Vue.component('how-it-works', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            steps: [
                { titleKey: 'main.how_it_works.step1_title', descKey: 'main.how_it_works.step1_desc', icon: 'shield', color: 'text-main-blue', bg: 'bg-main-blue/10' },
                { titleKey: 'main.how_it_works.step2_title', descKey: 'main.how_it_works.step2_desc', icon: 'search', color: 'text-purple-500', bg: 'bg-purple-50' },
                { titleKey: 'main.how_it_works.step3_title', descKey: 'main.how_it_works.step3_desc', icon: 'lock', color: 'text-amber-500', bg: 'bg-amber-50' },
                { titleKey: 'main.how_it_works.step4_title', descKey: 'main.how_it_works.step4_desc', icon: 'check', color: 'text-main-green', bg: 'bg-main-green/10' }
            ]
        };
    },
    methods: {
        goDashboard: function() {
            if (window.__mainApp) window.__mainApp.currentPage = 'dashboard';
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('dashboard');
        }
    },
    template: `
    <div class="max-w-4xl mx-auto px-4 py-16">
      <div class="text-center mb-16">
        <h1 class="text-4xl font-bold mb-4 tracking-tight">[[ $t('main.how_it_works.title') ]]</h1>
        <p class="text-lg text-cmc-muted max-w-2xl mx-auto">[[ $t('main.how_it_works.subtitle') ]]</p>
      </div>
      <div class="space-y-12">
        <div v-for="(step, i) in steps" :key="i" class="flex flex-col md:flex-row gap-8 items-center">
          <div :class="['w-20 h-20 rounded-3xl flex items-center justify-center shrink-0 shadow-lg', step.bg, step.color]">
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
          </div>
          <div class="flex-1 text-center md:text-left">
            <div class="text-xs font-bold uppercase tracking-widest text-main-blue mb-2">[[ $t('main.how_it_works.step') ]] 0[[ i + 1 ]]</div>
            <h3 class="text-2xl font-bold mb-3">[[ $t(step.titleKey) ]]</h3>
            <p class="text-cmc-muted leading-relaxed">[[ $t(step.descKey) ]]</p>
          </div>
        </div>
      </div>
      <div class="mt-24 p-8 bg-[#f8fafd] rounded-3xl border border-[#eff2f5] text-center">
        <h2 class="text-2xl font-bold mb-4">[[ $t('main.how_it_works.cta_title') ]]</h2>
        <p class="text-cmc-muted mb-8">[[ $t('main.how_it_works.cta_subtitle') ]]</p>
        <button @click="goDashboard" class="cmc-btn-primary px-8 py-3 text-lg">[[ $t('main.how_it_works.cta_btn') ]]</button>
      </div>
    </div>
    `
});
