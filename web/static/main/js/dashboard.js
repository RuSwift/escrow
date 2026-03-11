/**
 * Vue 2 компонент: Дашборд (main)
 */
Vue.component('dashboard', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            stats: [
                { labelKey: 'main.dashboard.stat_tvl', value: '$1.2M', change: '+12.5%', isPositive: true },
                { labelKey: 'main.dashboard.stat_active', value: '1,284', change: '+3.2%', isPositive: true },
                { labelKey: 'main.dashboard.stat_success', value: '99.8%', change: '+0.1%', isPositive: true },
                { labelKey: 'main.dashboard.stat_release', value: '4.2h', change: '-15.4%', isPositive: false }
            ],
            loading: false
        };
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div v-for="(stat, i) in stats" :key="i" class="cmc-card p-4 flex flex-col">
          <span class="text-xs text-cmc-muted font-medium mb-1">[[ $t(stat.labelKey) ]]</span>
          <div class="flex items-end gap-2">
            <span class="text-xl font-bold">[[ stat.value ]]</span>
            <span :class="['text-xs font-bold flex items-center mb-1', stat.isPositive ? 'text-main-green' : 'text-main-red']">
              [[ stat.change ]]
            </span>
          </div>
        </div>
      </div>
      <div class="mb-6">
        <h1 class="text-2xl font-bold mb-1">[[ $t('main.dashboard.title') ]]</h1>
        <p class="text-sm text-cmc-muted">[[ $t('main.dashboard.subtitle') ]]</p>
      </div>
      <div class="cmc-card overflow-hidden">
        <div class="p-6 text-center text-cmc-muted">
          <p class="text-sm">[[ $t('main.dashboard.placeholder') ]]</p>
        </div>
      </div>
      <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_multisig_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_multisig') ]]</p>
          </div>
        </div>
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-green/10 flex items-center justify-center text-main-green shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_ai_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_ai') ]]</p>
          </div>
        </div>
        <div class="flex gap-4">
          <div class="w-12 h-12 rounded-2xl bg-main-red/10 flex items-center justify-center text-main-red shrink-0">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          </div>
          <div>
            <h3 class="font-bold mb-1">[[ $t('main.dashboard.info_arbitration_title') ]]</h3>
            <p class="text-sm text-cmc-muted leading-relaxed">[[ $t('main.dashboard.info_arbitration') ]]</p>
          </div>
        </div>
      </div>
    </div>
    `
});
