/**
 * Vue 2 компонент: Дашборд (main)
 */
(function() {
    function authHeadersMain() {
        var h = { Accept: 'application/json' };
        var key = (typeof window !== 'undefined' && window.main_auth_token_key) ? window.main_auth_token_key : 'main_auth_token';
        var token = null;
        try {
            token = localStorage.getItem(key);
        } catch (e) {}
        if (token) h['Authorization'] = 'Bearer ' + token;
        return h;
    }

    function buildRatiosPivot(apiData) {
        if (!apiData || typeof apiData !== 'object') return { engines: [], rows: [] };
        var engines = Object.keys(apiData).filter(function(k) {
            return Array.isArray(apiData[k]);
        }).sort();
        var pairMap = {};
        engines.forEach(function(eng) {
            apiData[eng].forEach(function(row) {
                var key = row.base + '/' + row.quote;
                if (!pairMap[key]) {
                    pairMap[key] = { base: row.base, quote: row.quote, ratios: {}, utcMax: null };
                }
                var r = row.pair && typeof row.pair.ratio === 'number' ? row.pair.ratio : null;
                pairMap[key].ratios[eng] = r;
                var u = row.pair && typeof row.pair.utc === 'number' ? row.pair.utc : null;
                if (r != null && u != null && isFinite(u)) {
                    if (pairMap[key].utcMax == null || u > pairMap[key].utcMax) {
                        pairMap[key].utcMax = u;
                    }
                }
            });
        });
        var rows = Object.keys(pairMap).sort().map(function(k) {
            return pairMap[k];
        }).filter(function(row) {
            return engines.some(function(eng) {
                var v = row.ratios[eng];
                return v != null && typeof v === 'number';
            });
        });
        return { engines: engines, rows: rows };
    }

Vue.component('dashboard', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
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
            mockLoading: false,
            ratiosRaw: null,
            ratiosLoading: false,
            ratiosError: null,
            ratiosModalOpen: false,
            spaceRole: '',
            showWithdrawalModal: false
        };
    },
    computed: {
        currentSpace: function() {
            return (typeof window !== 'undefined' && window.__CURRENT_SPACE__) ? String(window.__CURRENT_SPACE__).trim() : '';
        },
        canCreateWithdrawal: function() {
            var r = (this.spaceRole || '').trim();
            return r === 'owner' || r === 'operator';
        },
        ratiosPivot: function() {
            return buildRatiosPivot(this.ratiosRaw);
        },
        marqueeSegments: function() {
            var pivot = this.ratiosPivot;
            var rows = pivot.rows || [];
            if (!rows.length) return [];
            return rows.map(function(r) {
                var vals = [];
                (pivot.engines || []).forEach(function(e) {
                    var x = r.ratios[e];
                    if (x != null && typeof x === 'number') vals.push(x);
                });
                var maxVal = vals.length ? Math.max.apply(null, vals) : null;
                var ratioText = maxVal != null ? String(Number(maxVal).toFixed(2)).replace(/\.?0+$/, '') : '—';
                return { pair: r.base + '/' + r.quote, ratioText: ratioText };
            });
        },
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
    mounted: function() {
        if (typeof window !== 'undefined' && window.__SPACE_ROLE__) {
            this.spaceRole = String(window.__SPACE_ROLE__).trim();
        }
        this.fetchRatios();
    },
    methods: {
        refreshOrdersTable: function(opts) {
            if (this.$refs.ordersTable && typeof this.$refs.ordersTable.refresh === 'function') {
                this.$refs.ordersTable.refresh(opts || {});
            }
        },
        fetchRatios: function() {
            var self = this;
            self.ratiosLoading = true;
            self.ratiosError = null;
            fetch('/v1/dashboard/ratios', {
                method: 'GET',
                headers: authHeadersMain(),
                credentials: 'include'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    if (data && data.root && typeof data.root === 'object') {
                        data = data.root;
                    }
                    self.ratiosRaw = data;
                })
                .catch(function() {
                    self.ratiosError = true;
                    self.ratiosRaw = null;
                })
                .finally(function() {
                    self.ratiosLoading = false;
                });
        },
        onNewRequestSelect: function(e) {
            var el = e && e.target;
            var v = el ? el.value : '';
            if (v === 'withdrawal') {
                this.showWithdrawalModal = true;
            }
            if (el) el.value = '';
        },
        closeWithdrawalModal: function() {
            this.showWithdrawalModal = false;
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
        formatDate: function(created_at) {
            if (!created_at) return '—';
            var d = new Date(created_at);
            if (isNaN(d.getTime())) return '—';
            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return months[d.getMonth()] + ' ' + d.getDate() + ', ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        },
        formatRatioCell: function(val) {
            if (val == null || typeof val !== 'number') return '—';
            return String(Number(val).toFixed(2)).replace(/\.?0+$/, '');
        },
        formatUtcCell: function(tsSeconds) {
            if (tsSeconds == null || typeof tsSeconds !== 'number' || !isFinite(tsSeconds)) return '—';
            var d = new Date(tsSeconds * 1000);
            if (isNaN(d.getTime())) return '—';
            return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
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
      <div v-if="ratiosLoading" class="mb-6 h-10 rounded-lg bg-[#eff2f5] animate-pulse border border-[#eff2f5]" aria-hidden="true"></div>
      <div v-else-if="ratiosError" class="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-800">[[ $t('main.dashboard.ratios_load_error') ]]</div>
      <div v-else-if="ratiosPivot.rows.length" class="mb-6 flex rounded-lg border border-[#eff2f5] bg-white overflow-hidden shadow-sm cursor-pointer group" @click="ratiosModalOpen = true" role="button" :aria-label="$t('main.dashboard.ratios_modal_title')">
        <div class="flex-1 min-w-0 overflow-hidden py-2">
          <div class="dashboard-ratios-marquee-track">
            <div class="flex items-center shrink-0">
              <span v-for="(seg, i) in marqueeSegments" :key="'m1-' + i" class="inline-flex items-center px-4 text-sm whitespace-nowrap border-r border-[#eff2f5]">
                <span class="font-bold text-[#191d23]">[[ seg.pair ]]</span>
                <span class="mx-2 text-cmc-muted">[[ seg.ratioText ]]</span>
              </span>
            </div>
            <div class="flex items-center shrink-0">
              <span v-for="(seg, i) in marqueeSegments" :key="'m2-' + i" class="inline-flex items-center px-4 text-sm whitespace-nowrap border-r border-[#eff2f5]">
                <span class="font-bold text-[#191d23]">[[ seg.pair ]]</span>
                <span class="mx-2 text-cmc-muted">[[ seg.ratioText ]]</span>
              </span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-1.5 px-3 sm:px-4 shrink-0 border-l border-[#eff2f5] bg-[#fafbfd] text-xs font-bold text-main-blue group-hover:bg-main-blue/5 transition-colors">
          <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
          <span class="hidden sm:inline">[[ $t('main.dashboard.ratios_expand') ]]</span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2 min-w-0 mb-6">
        <h1 class="text-2xl font-bold">[[ $t('main.dashboard.title') ]]</h1>
        <button
          type="button"
          @click="refreshOrdersTable"
          class="inline-flex items-center gap-1.5 rounded-lg border border-[#eff2f5] bg-white px-3 py-1.5 text-xs font-bold text-[#3861fb] hover:bg-[#f8fafd] transition-colors shrink-0"
          :aria-label="$t('main.dashboard.orders_refresh')"
        >
          <svg class="w-4 h-4 shrink-0 text-[#3861fb]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>[[ $t('main.dashboard.orders_refresh') ]]</span>
        </button>
      </div>
      <div v-if="canCreateWithdrawal" class="flex flex-wrap items-center gap-2 mb-4">
        <label class="text-xs font-semibold text-[#58667e] shrink-0" for="dash-new-request-select">[[ $t('main.dashboard.new_request_label') ]]</label>
        <select
          id="dash-new-request-select"
          @change="onNewRequestSelect"
          class="max-w-xs rounded-lg border border-[#eff2f5] bg-white px-3 py-2 text-sm text-[#191d23] focus:outline-none focus:ring-2 focus:ring-main-blue/20"
        >
          <option value="">[[ $t('main.dashboard.new_request_placeholder') ]]</option>
          <option value="withdrawal">[[ $t('main.dashboard.new_request_withdrawal') ]]</option>
          <option value="invoice" disabled>[[ $t('main.dashboard.new_request_invoice') ]]</option>
        </select>
      </div>
      <orders-table
        ref="ordersTable"
        :space="currentSpace"
        :can-manage="canCreateWithdrawal"
      ></orders-table>

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
      <div class="mt-14">
        <h2 class="text-lg font-bold text-[#191d23] mb-2">[[ $t('main.dashboard.mocker_orders_title') ]]</h2>
        <p class="text-xs text-cmc-muted mb-4">[[ $t('main.dashboard.mocker_orders_subtitle') ]]</p>
        <div class="flex flex-wrap items-center gap-4 mb-6">
          <div class="flex items-center gap-2 bg-white border border-[#eff2f5] rounded-lg p-1">
            <button v-for="s in ['all','pending','funded','released','disputed']" :key="'mock-' + s" type="button" @click="statusFilter = s" :class="['px-3 py-1 rounded-md text-xs font-bold capitalize transition-all', statusFilter === s ? 'bg-main-blue text-white shadow-sm' : 'text-cmc-muted hover:bg-[#f8fafd]']">[[ $t('main.dashboard.filter_' + s) ]]</button>
          </div>
          <div class="relative flex-1 max-w-xs">
            <input v-model="searchQuery" type="text" :placeholder="$t('main.dashboard.search_placeholder')" class="w-full pl-9 pr-4 py-1.5 bg-white border border-[#eff2f5] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-main-blue/20" />
          </div>
          <div class="relative flex-1 max-w-xs min-w-[140px]">
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
                <template v-if="mockLoading">
                  <tr v-for="i in 5" :key="'mock-skeleton-' + i" class="animate-pulse">
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
      </div>
      <transition name="fade">
        <div v-if="ratiosModalOpen" class="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="ratiosModalOpen = false">
          <div class="bg-white rounded-xl shadow-xl border border-[#eff2f5] w-full max-w-5xl max-h-[85vh] flex flex-col" role="dialog" aria-modal="true" @click.stop>
            <div class="flex items-center justify-between gap-4 px-4 py-3 border-b border-[#eff2f5] shrink-0">
              <h2 class="text-lg font-bold text-[#191d23]">[[ $t('main.dashboard.ratios_modal_title') ]]</h2>
              <button type="button" class="p-2 rounded-lg text-[#58667e] hover:bg-[#eff2f5] transition-colors" @click="ratiosModalOpen = false" :aria-label="$t('main.dashboard.ratios_close')">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div class="dashboard-ratios-modal-scroll overflow-auto p-4 flex-1 min-h-0">
              <div v-if="!ratiosPivot.rows.length" class="text-sm text-cmc-muted py-8 text-center">[[ $t('main.dashboard.ratios_empty') ]]</div>
              <table v-else class="dashboard-ratios-modal-table w-full text-left text-sm">
                <thead>
                  <tr class="bg-gray-50">
                    <th class="cmc-table-header dashboard-ratios-sticky-col min-w-[100px]">[[ $t('main.dashboard.ratios_col_pair') ]]</th>
                    <th v-for="eng in ratiosPivot.engines" :key="eng" class="cmc-table-header whitespace-nowrap">[[ eng ]]</th>
                    <th class="cmc-table-header whitespace-nowrap">[[ $t('main.dashboard.ratios_col_utc') ]]</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in ratiosPivot.rows" :key="ri" class="hover:bg-[#f8fafd]">
                    <td class="cmc-table-cell dashboard-ratios-sticky-col text-[#191d23] font-semibold">[[ row.base ]]/[[ row.quote ]]</td>
                    <td v-for="eng in ratiosPivot.engines" :key="eng" class="cmc-table-cell text-cmc-muted font-mono text-xs tabular-nums">[[ formatRatioCell(row.ratios[eng]) ]]</td>
                    <td class="cmc-table-cell text-cmc-muted text-xs tabular-nums whitespace-nowrap">[[ formatUtcCell(row.utcMax) ]]</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="px-4 py-3 border-t border-[#eff2f5] flex justify-end shrink-0">
              <button type="button" class="px-4 py-2 text-sm font-semibold rounded-lg bg-main-blue text-white hover:opacity-90 transition-opacity" @click="ratiosModalOpen = false">[[ $t('main.dashboard.ratios_close') ]]</button>
            </div>
          </div>
        </div>
      </transition>
      <withdrawal-order-modal
        :show="showWithdrawalModal"
        @close="closeWithdrawalModal"
      ></withdrawal-order-modal>
    </div>
    `
});
})();
