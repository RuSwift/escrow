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
            searchQuery: '',
            statusFilter: 'all',
            participantFilter: '',
            escrows: [
                { id: 'esc-001', title: 'Domain crypto-vault.com', description: 'Domain purchase agreement', amount: 2.5, currency: 'USDT', status: 'funded', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-10T14:30:00' },
                { id: 'esc-002', title: 'OTC 50K USDT', description: 'High-value OTC trade', amount: 50000, currency: 'USDT', status: 'pending', buyer_id: '0x33C...7788F', seller_id: '0x55D...9900A', created_at: '2026-03-11T09:15:00' },
                { id: 'esc-003', title: 'NFT #4421', description: 'Art piece transfer', amount: 0.8, currency: 'ETH', status: 'released', buyer_id: '0x99B...3344D', seller_id: '0x11A...5566E', created_at: '2026-03-08T16:00:00' },
                { id: 'esc-004', title: 'Software license', description: 'Annual enterprise license', amount: 12000, currency: 'USDT', status: 'disputed', buyer_id: '0x22B...4455C', seller_id: '0x77E...6677F', created_at: '2026-03-09T11:20:00' },
                { id: 'esc-005', title: 'Hardware batch', description: 'Miners delivery', amount: 150000, currency: 'USDT', status: 'funded', buyer_id: '0x71C...8976F', seller_id: '0x42A...1122C', created_at: '2026-03-12T08:45:00' }
            ],
            loading: false
        };
    },
    computed: {
        filteredEscrows: function() {
            var self = this;
            var query = (this.searchQuery || '').toLowerCase();
            var statusFilter = this.statusFilter;
            var participantFilter = (this.participantFilter || '').toLowerCase();
            return this.escrows.filter(function(escrow) {
                var matchesSearch = !query ||
                    (escrow.title || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.description || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.id || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.status || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.buyer_id || '').toLowerCase().indexOf(query) !== -1 ||
                    (escrow.seller_id || '').toLowerCase().indexOf(query) !== -1;
                var matchesStatus = statusFilter === 'all' || escrow.status === statusFilter;
                var matchesParticipant = !participantFilter ||
                    (escrow.buyer_id || '').toLowerCase().indexOf(participantFilter) !== -1 ||
                    (escrow.seller_id || '').toLowerCase().indexOf(participantFilter) !== -1;
                return matchesSearch && matchesStatus && matchesParticipant;
            });
        }
    },
    methods: {
        formatDate: function(created_at) {
            if (!created_at) return '—';
            var d = new Date(created_at);
            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return months[d.getMonth()] + ' ' + d.getDate() + ', ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        },
        formatUsd: function(amount, currency) {
            if (currency === 'USDT' && amount) return '≈ $' + (amount).toLocaleString();
            if (currency === 'ETH' && amount) return '≈ $' + (Math.round(amount * 3500)).toLocaleString();
            return '—';
        },
        statusClass: function(status) {
            return status === 'pending' ? 'bg-amber-100 text-amber-700' : status === 'funded' ? 'bg-blue-100 text-blue-700' : status === 'released' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700';
        },
        statusDotClass: function(status) {
            return status === 'pending' ? 'bg-amber-500' : status === 'funded' ? 'bg-blue-500' : status === 'released' ? 'bg-emerald-500' : 'bg-rose-500';
        },
        goToDetail: function(escrowId) {
            if (!escrowId || !window.__mainApp) return;
            window.__mainApp.selectedEscrowId = escrowId;
            window.__mainApp.currentPage = 'detail';
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) {
                sidebar.__vue__.currentPage = 'dashboard';
            }
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            var url = base + '?initial_page=detail&escrow_id=' + encodeURIComponent(escrowId);
            history.pushState({ page: 'detail', escrowId: escrowId }, '', url);
        },
        rolesPageHref: function() {
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            return base + '?initial_page=space-roles';
        },
        goToRoles: function() {
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('space-roles');
            if (window.__mainApp) window.__mainApp.currentPage = 'space-roles';
        },
        profilePageHref: function() {
            var space = window.__CURRENT_SPACE__ || '';
            var base = space ? '/' + encodeURIComponent(space) : '/app';
            return base + '?initial_page=space-profile';
        },
        goToProfile: function() {
            var sidebar = document.querySelector('#sidebar-main');
            if (sidebar && sidebar.__vue__) sidebar.__vue__.go('space-profile');
            if (window.__mainApp) window.__mainApp.currentPage = 'space-profile';
        }
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div v-if="typeof window !== \'undefined\' && window.__SPACE_ROLE__ === \'owner\' && window.__SPACE_SUBS_COUNT__ === 0" class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-amber-800 text-sm font-medium flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>[[ $t(\'main.dashboard.no_roles_warning\') ]]</span>
        <a :href="rolesPageHref()" @click.prevent="goToRoles()" class="font-semibold text-main-blue hover:underline">[[ $t(\'main.dashboard.go_to_roles\') ]]</a>
      </div>
      <div v-if="typeof window !== \'undefined\' && window.__SPACE_ROLE__ === \'owner\' && window.__SPACE_PROFILE_FILLED__ === false" class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-amber-800 text-sm font-medium flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>[[ $t(\'main.dashboard.no_profile_warning\') ]]</span>
        <a :href="profilePageHref()" @click.prevent="goToProfile()" class="font-semibold text-main-blue hover:underline">[[ $t(\'main.dashboard.go_to_profile\') ]]</a>
      </div>
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
      <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h1 class="text-2xl font-bold mb-1">[[ $t('main.dashboard.title') ]]</h1>
          <p class="text-sm text-cmc-muted">[[ $t('main.dashboard.subtitle') ]]</p>
        </div>
        <div class="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
          <div class="relative flex-1 md:w-80">
            <input v-model="searchQuery" type="text" :placeholder="$t('main.dashboard.search_placeholder')" class="w-full pl-10 pr-4 py-2 bg-white border border-[#eff2f5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
          </div>
          <button type="button" class="cmc-btn-primary flex items-center justify-center gap-2 whitespace-nowrap py-2 px-4">
            [[ $t('main.dashboard.create_escrow') ]]
          </button>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-4 mb-6">
        <div class="flex items-center gap-2 bg-white border border-[#eff2f5] rounded-lg p-1">
          <button v-for="s in ['all','pending','funded','released','disputed']" :key="s" type="button" @click="statusFilter = s" :class="['px-3 py-1 rounded-md text-xs font-bold capitalize transition-all', statusFilter === s ? 'bg-main-blue text-white shadow-sm' : 'text-cmc-muted hover:bg-[#f8fafd]']">[[ $t('main.dashboard.filter_' + s) ]]</button>
        </div>
        <div class="relative flex-1 max-w-xs">
          <input v-model="participantFilter" type="text" :placeholder="$t('main.dashboard.filter_participant')" class="w-full pl-9 pr-4 py-1.5 bg-white border border-[#eff2f5] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
        </div>
        <div class="ml-auto text-xs text-cmc-muted font-medium">[[ $t('main.dashboard.showing_orders', { count: filteredEscrows.length, total: escrows.length }) ]]</div>
      </div>
      <div class="cmc-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="cmc-table-header w-12">#</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_title') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_amount') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_status') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_created') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_participants') ]]</th>
                <th class="cmc-table-header text-right">[[ $t('main.dashboard.table_col_action') ]]</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="loading">
                <tr v-for="i in 5" :key="'skeleton-' + i" class="animate-pulse">
                  <td colspan="7" class="cmc-table-cell h-16 bg-gray-50/50"></td>
                </tr>
              </template>
              <tr v-else-if="filteredEscrows.length === 0">
                <td colspan="7" class="cmc-table-cell text-center py-12 text-cmc-muted">[[ $t('main.dashboard.no_orders_match') ]]</td>
              </tr>
              <tr v-else v-for="(escrow, i) in filteredEscrows" :key="escrow.id" class="hover:bg-[#f8fafd] cursor-pointer transition-all duration-200 group border-b border-[#eff2f5] last:border-0" @click="goToDetail(escrow.id)">
                <td class="cmc-table-cell text-cmc-muted font-medium">[[ i + 1 ]]</td>
                <td class="cmc-table-cell">
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
                      <svg class="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                    </div>
                    <div>
                      <div class="font-bold">[[ escrow.title ]]</div>
                      <div class="text-xs text-cmc-muted truncate max-w-[200px]">[[ escrow.description ]]</div>
                    </div>
                  </div>
                </td>
                <td class="cmc-table-cell">
                  <div class="font-bold">[[ escrow.amount ]] [[ escrow.currency ]]</div>
                  <div class="text-xs text-cmc-muted">[[ formatUsd(escrow.amount, escrow.currency) ]]</div>
                </td>
                <td class="cmc-table-cell">
                  <div :class="['inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider', statusClass(escrow.status)]">
                    <span :class="['w-1.5 h-1.5 rounded-full shrink-0', statusDotClass(escrow.status)]"></span>
                    [[ escrow.status ]]
                  </div>
                </td>
                <td class="cmc-table-cell text-cmc-muted">[[ formatDate(escrow.created_at) ]]</td>
                <td class="cmc-table-cell">
                  <div class="flex -space-x-2">
                    <div class="w-6 h-6 rounded-full bg-indigo-500 border-2 border-white flex items-center justify-center text-[10px] text-white font-bold" title="Buyer">B</div>
                    <div class="w-6 h-6 rounded-full bg-emerald-500 border-2 border-white flex items-center justify-center text-[10px] text-white font-bold" title="Seller">S</div>
                  </div>
                </td>
                <td class="cmc-table-cell text-right">
                  <span class="text-[10px] font-bold text-main-blue">[[ $t('main.dashboard.view_details') ]]</span>
                </td>
              </tr>
            </tbody>
          </table>
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
