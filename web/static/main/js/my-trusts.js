/**
 * Vue 2 компонент: Мои трасты (main)
 */
Vue.component('my-trusts', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            searchQuery: '',
            trustBoxes: [
                { id: '1', name: 'High-Value OTC Group', payer: '0x71C...8976F', payee: '0x42A...1122C', arbiter: 'TrustLayer_Official', status: 'active', created_at: '2026-03-01' },
                { id: '2', name: 'Domain Escrow #442', payer: '0x33C...7788F', payee: '0x55D...9900A', arbiter: 'Legal_Arbiter_Pro', status: 'pending', created_at: '2026-03-05' }
            ]
        };
    },
    computed: {
        filteredBoxes: function() {
            var q = this.searchQuery.toLowerCase();
            if (!q) return this.trustBoxes;
            return this.trustBoxes.filter(function(b) {
                return b.name.toLowerCase().indexOf(q) !== -1 || b.payer.toLowerCase().indexOf(q) !== -1 || b.payee.toLowerCase().indexOf(q) !== -1 || b.arbiter.toLowerCase().indexOf(q) !== -1;
            });
        }
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
          <h1 class="text-2xl font-bold mb-1">[[ $t('main.my_trusts.title') ]]</h1>
          <p class="text-sm text-cmc-muted">[[ $t('main.my_trusts.subtitle') ]]</p>
        </div>
        <div class="relative flex-1 md:w-64">
          <input v-model="searchQuery" type="text" :placeholder="$t('main.my_trusts.search_placeholder')" class="w-full pl-10 pr-4 py-2 bg-white border border-[#eff2f5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="cmc-card p-6 bg-main-blue/5 border-main-blue/20">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-main-blue flex items-center justify-center text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
            </div>
            <div>
              <div class="text-xs text-cmc-muted font-bold uppercase tracking-wider">[[ $t('main.my_trusts.stat_trust') ]]</div>
              <div class="text-xl font-bold">94.2%</div>
            </div>
          </div>
          <p class="text-xs text-cmc-muted">[[ $t('main.my_trusts.stat_trust_desc') ]]</p>
        </div>
        <div class="cmc-card p-6 bg-main-green/5 border-main-green/20">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-main-green flex items-center justify-center text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2V9a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2z" /></svg>
            </div>
            <div>
              <div class="text-xs text-cmc-muted font-bold uppercase tracking-wider">[[ $t('main.my_trusts.stat_partners') ]]</div>
              <div class="text-xl font-bold">12</div>
            </div>
          </div>
          <p class="text-xs text-cmc-muted">[[ $t('main.my_trusts.stat_partners_desc') ]]</p>
        </div>
        <div class="cmc-card p-6 bg-purple-50 border-purple-100">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-purple-500 flex items-center justify-center text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
            </div>
            <div>
              <div class="text-xs text-cmc-muted font-bold uppercase tracking-wider">[[ $t('main.my_trusts.stat_rank') ]]</div>
              <div class="text-xl font-bold">Top 5%</div>
            </div>
          </div>
          <p class="text-xs text-cmc-muted">[[ $t('main.my_trusts.stat_rank_desc') ]]</p>
        </div>
      </div>
      <div class="cmc-card overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-gray-50">
              <th class="cmc-table-header">[[ $t('main.my_trusts.col_name') ]]</th>
              <th class="cmc-table-header">[[ $t('main.my_trusts.col_payer') ]]</th>
              <th class="cmc-table-header">[[ $t('main.my_trusts.col_payee') ]]</th>
              <th class="cmc-table-header">[[ $t('main.my_trusts.col_arbiter') ]]</th>
              <th class="cmc-table-header">[[ $t('main.my_trusts.col_status') ]]</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="box in filteredBoxes" :key="box.id" class="hover:bg-[#f8fafd] transition-all border-b border-[#eff2f5] last:border-0">
              <td class="cmc-table-cell">
                <div class="font-bold">[[ box.name ]]</div>
                <div class="text-[10px] text-cmc-muted">[[ box.created_at ]]</div>
              </td>
              <td class="cmc-table-cell font-mono text-xs">[[ box.payer ]]</td>
              <td class="cmc-table-cell font-mono text-xs">[[ box.payee ]]</td>
              <td class="cmc-table-cell font-bold text-main-blue text-sm">[[ box.arbiter ]]</td>
              <td class="cmc-table-cell">
                <span :class="['inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase', box.status === 'active' ? 'bg-main-green/10 text-main-green' : 'bg-amber-100 text-amber-700']">[[ box.status ]]</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    `
});
