/**
 * Vue 2 компонент: Таблица ордеров (заявок)
 */
(function() {
Vue.component('orders-table', {
    delimiters: ['[[', ']]'],
    props: {
        orders: { type: Array, default: () => [] },
        loading: { type: Boolean, default: false },
        copiedId: { type: [String, Number], default: null },
        canManage: { type: Boolean, default: false }
    },
    methods: {
        isWithdrawalOrder: function(order) {
            return order && order.payload && order.payload.kind === 'withdrawal_request';
        },
        isMultisigEphemeralOrder: function(order) {
            var k = order && order.payload && order.payload.kind;
            return k === 'multisig_pipeline' || k === 'multisig_space_drift';
        },
        withdrawalSignTokenFromOrder: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var dk = String((order && order.dedupe_key) || '').trim();
            var prefix = 'withdrawal:';
            if (dk.indexOf(prefix) !== 0) return '';
            var t = dk.slice(prefix.length).trim();
            return t || '';
        },
        withdrawalSignHref: function(order) {
            var t = this.withdrawalSignTokenFromOrder(order);
            if (!t) return '#';
            return '/o/' + encodeURIComponent(t);
        },
        withdrawalSignAbsoluteUrl: function(order) {
            var path = this.withdrawalSignHref(order);
            if (!path || path === '#') return '';
            if (typeof window !== 'undefined' && window.location && window.location.origin) {
                return window.location.origin + path;
            }
            return path;
        },
        withdrawalTxExplorerVisible: function(order) {
            var p = (order && order.payload) || {};
            var tx = String((p.broadcast_tx_id || '')).trim();
            if (!tx) return false;
            var st = String((p.status || '')).trim();
            return st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed';
        },
        withdrawalTxExplorerUrl: function(order) {
            var p = (order && order.payload) || {};
            var tx = String((p.broadcast_tx_id || '')).trim();
            if (!tx || !window.EscrowWithdrawalSign || typeof window.EscrowWithdrawalSign.tronTxExplorerUrl !== 'function') {
                return '';
            }
            return window.EscrowWithdrawalSign.tronTxExplorerUrl(tx);
        },
        withdrawalAmountDisplay: function(order) {
            var p = (order && order.payload) || {};
            var raw = p.amount_raw;
            if (raw == null) return '—';
            var tok = p.token || {};
            var ttype = (tok.type || '').toLowerCase();
            var dec = typeof tok.decimals === 'number' && tok.decimals >= 0 ? tok.decimals : 6;
            var sym = (tok.symbol || '').toUpperCase() || (ttype === 'native' ? 'TRX' : 'TOKEN');
            var human = Number(raw) / Math.pow(10, dec);
            var formatted = human.toLocaleString(undefined, {
                maximumFractionDigits: dec,
                minimumFractionDigits: 0
            });
            return formatted + ' ' + sym;
        },
        withdrawalStatusLabel: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.status || '').trim();
            if (!st) return '—';
            var key = 'main.dashboard.withdrawal_status_' + st;
            var t = this.$t(key);
            return (t && t !== key) ? t : st;
        },
        withdrawalBadgeClass: function(order) {
            if (!this.isWithdrawalOrder(order)) {
                return 'bg-sky-50 text-sky-900 border border-sky-100';
            }
            var p = (order && order.payload) || {};
            var st = String((p.status || '')).trim();
            if (st === 'confirmed') return 'bg-main-green/12 text-main-green border border-main-green/25';
            if (st === 'failed') return 'bg-main-red/10 text-main-red border border-main-red/25';
            if (st === 'broadcast_submitted' || st === 'awaiting_signatures' || st === 'ready_to_broadcast') return 'bg-main-blue/12 text-main-blue border border-main-blue/25';
            return 'bg-main-blue/10 text-main-blue border border-main-blue/20';
        },
        withdrawalSpinnerVisible: function(order) {
            if (!this.isWithdrawalOrder(order)) return false;
            var p = (order && order.payload) || {};
            var st = (p.status || '').trim();
            if (st === 'confirmed' || st === 'failed') return false;
            return true;
        },
        ephemeralMultisigStatusLabel: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.multisig_setup_status != null) ? String(p.multisig_setup_status) : '';
            if (!st) return '—';
            var key = 'main.my_business.multisig_status_' + st;
            var t = this.$t(key);
            return (t && t !== key) ? t : st;
        },
        ephemeralMultisigBadgeClass: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'multisig_space_drift') return 'bg-violet-50 text-violet-900 border border-violet-100';
            return 'bg-amber-50 text-amber-900 border border-amber-100';
        },
        ephemeralMultisigSpinnerVisible: function(order) {
            var p = (order && order.payload) || {};
            var st = (p.multisig_setup_status != null) ? String(p.multisig_setup_status) : '';
            if (!st || st === 'failed' || st === 'reconfigure' || st === 'active') return false;
            return true;
        },
        withdrawalDeleteAllowed: function(order) {
            if (!this.isWithdrawalOrder(order)) return false;
            var st = String((((order || {}).payload || {}).status || '')).trim();
            if (st === 'broadcast_submitted' || st === 'confirmed' || st === 'failed') return false;
            return true;
        },
        formatDate: function(created_at) {
            if (!created_at) return '—';
            var d = new Date(created_at);
            if (isNaN(d.getTime())) return '—';
            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return months[d.getMonth()] + ' ' + d.getDate() + ', ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        },
        shortenAddress: function(addr) {
            var s = String(addr || '').trim();
            if (!s) return '—';
            if (s.length <= 12) return s;
            return s.slice(0, 4) + '…' + s.slice(-4);
        },
        ellipsisMiddle: function(str, maxLen) {
            var n = maxLen == null ? 56 : maxLen;
            var s = String(str == null ? '' : str);
            if (s.length <= n) return s;
            var take = Math.floor((n - 1) / 2);
            if (take < 4) take = 4;
            return s.slice(0, take) + '…' + s.slice(s.length - take);
        },
        orderRowTitle: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'withdrawal_request') return this.$t('main.dashboard.order_kind_withdrawal');
            var wid = order.space_wallet_id != null ? order.space_wallet_id : (p.wallet_id != null ? p.wallet_id : null);
            return (p.wallet_name || '').trim() || ('#' + (wid != null ? wid : (order.id || '')));
        },
        orderRowDesc: function(order) {
            var p = (order && order.payload) || {};
            if (p.kind === 'withdrawal_request') {
                var dest = (p.destination_address || '').trim();
                var tok = (p.token && p.token.symbol) ? String(p.token.symbol) : '';
                var destDisp = dest ? this.shortenAddress(dest) : '';
                var tail = tok + (destDisp ? ' → ' + destDisp : '');
                var srcRaw = (p.tron_address || '').trim();
                var srcDisp = srcRaw ? this.shortenAddress(srcRaw) : '';
                var line = (srcDisp && srcDisp !== '—') ? (srcDisp + ' → ' + tail) : tail;
                var pur = (p.purpose || '').trim();
                if (pur) return pur + ' — ' + line;
                return line;
            }
            if (p.kind === 'multisig_space_drift') {
                if (p.owners_drift == null && p.actors_drift == null) {
                    var om0 = (p.only_in_meta && p.only_in_meta.length) ? p.only_in_meta.join(', ') : '';
                    var os0 = (p.only_in_space && p.only_in_space.length) ? p.only_in_space.join(', ') : '';
                    return this.$t('main.dashboard.order_drift_summary', { only_in_meta: om0 || '—', only_in_space: os0 || '—' });
                }
                var parts = [];
                if (p.owners_drift) {
                    var oim = (p.owners_only_in_meta && p.owners_only_in_meta.length) ? p.owners_only_in_meta.join(', ') : '';
                    var ois = (p.owners_only_in_space && p.owners_only_in_space.length) ? p.owners_only_in_space.join(', ') : '';
                    parts.push(this.$t('main.dashboard.order_drift_owners_line', { only_in_meta: oim || '—', only_in_space: ois || '—' }));
                }
                if (p.actors_drift) {
                    var aim = (p.actors_only_in_meta && p.actors_only_in_meta.length) ? p.actors_only_in_meta.join(', ') : '';
                    var ais = (p.actors_only_in_space && p.actors_only_in_space.length) ? p.actors_only_in_space.join(', ') : '';
                    parts.push(this.$t('main.dashboard.order_drift_actors_line', { only_in_meta: aim || '—', only_in_space: ais || '—' }));
                }
                if (parts.length) return parts.join(' · ');
                var om = (p.only_in_meta && p.only_in_meta.length) ? p.only_in_meta.join(', ') : '';
                var os = (p.only_in_space && p.only_in_space.length) ? p.only_in_space.join(', ') : '';
                return this.$t('main.dashboard.order_drift_summary', { only_in_meta: om || '—', only_in_space: os || '—' });
            }
            return (p.tron_address || '').trim() || '';
        },
        orderRowDescDisplay: function(order) {
            return this.ellipsisMiddle(this.orderRowDesc(order), 56);
        },
        withdrawalRowDescTitle: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var p = order.payload || {};
            var src = (p.tron_address || '').trim();
            var dest = (p.destination_address || '').trim();
            var tok = (p.token && p.token.symbol) ? String(p.token.symbol) : '';
            var parts = [];
            var pur = (p.purpose || '').trim();
            if (pur) parts.push(pur);
            if (src) parts.push(src);
            if (tok) parts.push(tok);
            if (dest) parts.push(dest);
            return parts.join(' → ');
        },
        orderRowDescTooltip: function(order) {
            if (this.isWithdrawalOrder(order)) return this.withdrawalRowDescTitle(order);
            return this.orderRowDesc(order);
        },
        withdrawalSignatoriesDisplay: function(order) {
            if (!this.isWithdrawalOrder(order)) return '—';
            this.$emit('request-signatories-display', order);
            return order._signatoriesDisplay || '—';
        },
        withdrawalSignatoriesTitle: function(order) {
            if (!this.isWithdrawalOrder(order)) return '';
            var p = order.payload || {};
            var role = (p.wallet_role || '').trim();
            if (role === 'external') return (p.tron_address || '').trim() || '';
            if (role === 'multisig') {
                var actors = Array.isArray(p.actors_snapshot) ? p.actors_snapshot : [];
                return actors.map(function(a) { return String(a || '').trim(); }).filter(Boolean).join(', ');
            }
            return '';
        },
        shareWithdrawalSignLink: function(order, ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            var url = this.withdrawalSignAbsoluteUrl(order);
            if (!url) return;
            if (navigator.share) {
                navigator.share({
                    title: this.$t('main.dashboard.order_kind_withdrawal'),
                    text: this.orderRowDesc(order),
                    url: url
                }).catch(function(err) {
                    console.error('Error sharing:', err);
                });
            }
        }
    },
    computed: {
        canShare: function() {
            return typeof navigator !== 'undefined' && !!navigator.share;
        }
    },
    template: `
      <div class="cmc-card overflow-hidden mb-10">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="cmc-table-header w-12">#</th>
                <th class="cmc-table-header whitespace-nowrap min-w-[11rem] sm:min-w-[13rem]">[[ $t('main.dashboard.table_col_link') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_title') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_amount') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_status') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_created') ]]</th>
                <th class="cmc-table-header">[[ $t('main.dashboard.table_col_signatories') ]]</th>
                <th class="cmc-table-header text-right">[[ $t('main.dashboard.table_col_action') ]]</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="loading">
                <tr v-for="i in 5" :key="'ord-sk-' + i" class="animate-pulse">
                  <td colspan="8" class="cmc-table-cell h-16 bg-gray-50/50"></td>
                </tr>
              </template>
              <tr v-else-if="orders.length === 0">
                <td colspan="8" class="cmc-table-cell text-center py-12 text-cmc-muted">[[ $t('main.dashboard.ephemeral_no_orders') ]]</td>
              </tr>
              <tr v-else v-for="(order, i) in orders" :key="'api-ord-' + order.id"
                class="border-b border-[#eff2f5] last:border-0 transition-all duration-200"
                :class="(isMultisigEphemeralOrder(order) || isWithdrawalOrder(order)) ? 'hover:bg-[#f0f6ff] cursor-pointer' : 'hover:bg-[#f8fafd]'"
                :tabindex="(isMultisigEphemeralOrder(order) || isWithdrawalOrder(order)) ? 0 : -1"
                @click="$emit('row-click', order)"
                @keydown.enter.prevent="$emit('row-click', order)"
              >
                <td class="cmc-table-cell text-cmc-muted font-medium">[[ i + 1 ]]</td>
                <td class="cmc-table-cell align-middle" @click.stop>
                  <div v-if="isWithdrawalOrder(order) && withdrawalSignTokenFromOrder(order)" class="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    <a
                      :href="withdrawalSignHref(order)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1.5 text-xs font-semibold text-main-blue hover:opacity-90 shrink-0"
                      :aria-label="$t('main.dashboard.orders_sign_link') + ' — ' + withdrawalSignHref(order)"
                      @click.stop
                    >
                      <svg class="w-4 h-4 shrink-0 text-main-blue" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                      <span>[[ $t('main.dashboard.orders_link_label') ]]</span>
                    </a>
                    <button
                      type="button"
                      class="shrink-0 rounded-md border border-[#eff2f5] bg-white px-2 py-1 text-[10px] sm:text-xs font-semibold text-[#58667e] hover:bg-[#f8fafd] hover:border-[#cfd6e4] focus:outline-none focus:ring-2 focus:ring-main-blue/25"
                      :aria-label="$t('main.dashboard.orders_copy_sign_link')"
                      @click="$emit('copy-link', order, $event)"
                    >
                      [[ copiedId === order.id ? $t('main.copied') : $t('main.dashboard.orders_copy_sign_link') ]]
                    </button>
                    <button
                      v-if="canShare"
                      type="button"
                      class="shrink-0 rounded-md border border-[#eff2f5] bg-white px-2 py-1 text-[10px] sm:text-xs font-semibold text-main-blue hover:bg-[#f8fafd] hover:border-[#cfd6e4] focus:outline-none focus:ring-2 focus:ring-main-blue/25"
                      :aria-label="$t('main.dashboard.orders_share_link')"
                      @click="shareWithdrawalSignLink(order, $event)"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                      </svg>
                    </button>
                    <a
                      v-if="withdrawalTxExplorerVisible(order)"
                      :href="withdrawalTxExplorerUrl(order)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-[10px] sm:text-xs font-semibold text-main-green hover:text-emerald-700 shrink-0 rounded-md px-1.5 py-0.5 bg-main-green/12 hover:bg-main-green/20 transition-colors"
                      :aria-label="$t('main.dashboard.withdrawal_tx_explorer')"
                      @click.stop
                    >
                      <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0 text-main-green" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3z"/>
                        <path d="M12 12 4 7.5M12 12l8-4.5M12 12v9"/>
                      </svg>
                      <span>[[ $t('main.dashboard.withdrawal_tx_explorer_short') ]]</span>
                    </a>
                  </div>
                  <span v-else class="text-cmc-muted text-xs">—</span>
                </td>
                <td class="cmc-table-cell">
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-main-blue/10 flex items-center justify-center text-main-blue shrink-0">
                      <svg class="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div class="min-w-0">
                      <div class="font-bold truncate">[[ orderRowTitle(order) ]]</div>
                      <div class="text-xs text-cmc-muted max-w-[240px] sm:max-w-md min-w-0 whitespace-nowrap overflow-hidden" :title="orderRowDescTooltip(order)">[[ orderRowDescDisplay(order) ]]</div>
                    </div>
                  </div>
                </td>
                <td class="cmc-table-cell text-cmc-muted">
                  <span v-if="isWithdrawalOrder(order)">[[ withdrawalAmountDisplay(order) ]]</span>
                  <span v-else>—</span>
                </td>
                <td class="cmc-table-cell">
                  <div v-if="isWithdrawalOrder(order)" class="flex items-center gap-1 min-w-0">
                    <div :class="['inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md pl-2 pr-1.5 py-0.5', withdrawalBadgeClass(order)]">
                      <span class="text-[10px] font-bold uppercase truncate">[[ withdrawalStatusLabel(order) ]]</span>
                      <svg v-if="withdrawalSpinnerVisible(order)" class="w-3.5 h-3.5 shrink-0 animate-spin opacity-90 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </div>
                  </div>
                  <div v-else class="flex items-center gap-1 min-w-0">
                    <div :class="['inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md pl-2 pr-1.5 py-0.5', ephemeralMultisigBadgeClass(order)]">
                      <span class="text-[10px] font-bold uppercase truncate">[[ ephemeralMultisigStatusLabel(order) ]]</span>
                      <svg v-if="ephemeralMultisigSpinnerVisible(order)" class="w-3.5 h-3.5 shrink-0 animate-spin opacity-90" :class="(order.payload && order.payload.kind) === 'multisig_space_drift' ? 'text-violet-800' : 'text-amber-800'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </div>
                  </div>
                </td>
                <td class="cmc-table-cell text-cmc-muted">[[ formatDate(order.updated_at) ]]</td>
                <td class="cmc-table-cell text-cmc-muted text-xs min-w-0 max-w-[220px]">
                  <span v-if="isWithdrawalOrder(order)" class="block truncate" :title="withdrawalSignatoriesTitle(order)">[[ withdrawalSignatoriesDisplay(order) ]]</span>
                  <span v-else>—</span>
                </td>
                <td class="cmc-table-cell text-right align-middle" @click.stop>
                  <button
                    v-if="isWithdrawalOrder(order) && canManage"
                    type="button"
                    class="px-2 py-1 text-xs font-semibold rounded-md border border-rose-200 text-rose-800 bg-white hover:bg-rose-50 disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-white"
                    :disabled="!withdrawalDeleteAllowed(order)"
                    :title="withdrawalDeleteAllowed(order) ? '' : $t('main.withdrawal_detail.delete_order_forbidden_hint')"
                    @click="$emit('delete-order', order, $event)"
                  >[[ $t('main.dashboard.orders_delete') ]]</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-2 border-t border-[#eff2f5] text-xs text-cmc-muted">[[ $t('main.dashboard.showing_api_orders', { count: orders.length, total: orders.length }) ]]</div>
      </div>
    `
});
})();
