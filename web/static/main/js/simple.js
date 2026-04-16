/**
 * Публичная страница /simple: Vue 2 (UDM).
 */
(function() {
    var el = document.getElementById('simple-root');
    if (!el || typeof Vue === 'undefined') return;

    var T = window.__TRANSLATIONS__ || {};

    function t(key, params) {
        var s = T[key] !== undefined ? T[key] : key;
        if (params && typeof s === 'string') {
            Object.keys(params).forEach(function(k) {
                s = s.split('{' + k + '}').join(params[k]);
            });
        }
        return s;
    }

    Vue.prototype.$t = t;

    var STORAGE_KEY = 'simple_theme';
    var SPACE_KEY = 'simple_space';
    var TOKEN_KEY = (typeof window !== 'undefined' && window.main_auth_token_key) ? window.main_auth_token_key : 'main_auth_token';

    function getToken() {
        try { return (localStorage.getItem(TOKEN_KEY) || '').trim(); } catch (e) { return ''; }
    }

    function setSpace(space) {
        try { localStorage.setItem(SPACE_KEY, space || ''); } catch (e) {}
    }

    function getSpace() {
        try { return (localStorage.getItem(SPACE_KEY) || '').trim(); } catch (e) { return ''; }
    }

    function clearAuthAndSpace() {
        try { localStorage.removeItem(TOKEN_KEY); } catch (e) {}
        try { localStorage.removeItem(SPACE_KEY); } catch (e) {}
    }

    /** Сессия: не трогает simple_theme (тема остаётся). */
    function clearSessionClientStorage() {
        clearAuthAndSpace();
        try { localStorage.removeItem('main_current_space'); } catch (e) {}
        try { localStorage.removeItem('main_invite_tron_snapshot'); } catch (e) {}
        try { sessionStorage.removeItem('main_invite_wallet_reminder'); } catch (e) {}
    }

    function themeFromQuery() {
        try {
            var raw = new URLSearchParams(window.location.search).get('theme');
            if (!raw) return null;
            var q = String(raw).toLowerCase().trim();
            if (q === 'dark' || q === 'light') return q;
        } catch (e) {}
        return null;
    }

    function ensureSpace(token) {
        return fetch('/v1/auth/tron/ensure-space', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? ('Bearer ' + token) : ''
            },
            credentials: 'same-origin'
        }).then(function(r) {
            return r.json().then(function(data) { return { status: r.status, data: data }; });
        });
    }

    new Vue({
        el: el,
        data: function() {
            return {
                appName: (el.getAttribute('data-app-name') || '').trim() || 'Escrow',
                theme: 'light',
                authReady: false,
                showAuthModal: false,
                authError: '',
                activeSpace: '',
                navSteps: [
                    { num: '01', titleKey: 'main.simple.nav_step1_title', subKey: 'main.simple.nav_step1_sub', status: 'done' },
                    { num: '02', titleKey: 'main.simple.nav_step2_title', subKey: 'main.simple.nav_step2_sub', status: 'active' },
                    { num: '03', titleKey: 'main.simple.nav_step3_title', subKey: 'main.simple.nav_step3_sub', status: 'pending' },
                    { num: '04', titleKey: 'main.simple.nav_step4_title', subKey: 'main.simple.nav_step4_sub', status: 'pending' }
                ]
            };
        },
        created: function() {
            var self = this;
            var fromUrl = themeFromQuery();
            if (fromUrl) {
                this.theme = fromUrl;
            } else {
                var saved = null;
                try {
                    saved = localStorage.getItem(STORAGE_KEY);
                } catch (e) {}
                if (saved === 'dark' || saved === 'light') {
                    this.theme = saved;
                }
            }

            // Auth bootstrap: if no JWT -> require TronLink login; if JWT exists -> ensure correct (primary) space
            var token = getToken();
            var getCurrent = window.get_current_user;
            if (!getCurrent) {
                // If auth.js wasn't loaded for some reason, still show modal
                self.showAuthModal = true;
                self.authReady = true;
                return;
            }

            getCurrent().then(function(u) {
                if (!u) {
                    self.showAuthModal = true;
                    return;
                }
                token = getToken();
                if (!token) {
                    self.showAuthModal = true;
                    return;
                }
                return ensureSpace(token).then(function(res) {
                    if (!res || res.status !== 200 || !res.data || !res.data.space) {
                        self.showAuthModal = true;
                        return;
                    }
                    var target = String(res.data.space || '').trim();
                    var current = getSpace();
                    // If user is "in чужом спейсе" (saved space differs from primary/fallback target) -> force relogin
                    if (current && target && current !== target) {
                        return fetch('/v1/auth/logout', { method: 'POST', credentials: 'same-origin' })
                            .catch(function() {})
                            .then(function() {
                                clearAuthAndSpace();
                                self.activeSpace = '';
                                self.showAuthModal = true;
                            });
                    }
                    self.activeSpace = target;
                    setSpace(target);
                });
            }).catch(function() {
                self.showAuthModal = true;
            }).finally(function() {
                self.authReady = true;
            });
        },
        watch: {
            theme: function(v) {
                try {
                    localStorage.setItem(STORAGE_KEY, v);
                } catch (e) {}
            }
        },
        computed: {
            rootClass: function() {
                return {
                    'simple-page': true,
                    'simple-page--dark': this.theme === 'dark'
                };
            },
            chromeTitle: function() {
                return t('main.simple.chrome_title', { app_name: this.appName });
            },
            escrowLine: function() {
                return t('main.simple.escrow_line', { addr: 'TCEu5M…jGesqi' });
            },
            themeBtnLabel: function() {
                return this.theme === 'light' ? t('main.simple.theme_dark') : t('main.simple.theme_light');
            },
            ordersListHref: function() {
                var s = (this.activeSpace || '').trim();
                if (!s) return '';
                return '/' + encodeURIComponent(s);
            },
            activeNavStep: function() {
                var steps = this.navSteps;
                for (var i = 0; i < steps.length; i++) {
                    if (steps[i].status === 'active') return steps[i];
                }
                return steps.length ? steps[0] : null;
            }
        },
        methods: {
            t: t,
            onTronSuccess: function(payload) {
                var self = this;
                self.authError = '';
                var key = TOKEN_KEY;
                try { localStorage.setItem(key, payload.token); } catch (e) {}
                var token = getToken();
                if (!token) {
                    self.authError = t('main.simple.auth_error');
                    return;
                }
                ensureSpace(token).then(function(res) {
                    if (!res || res.status !== 200 || !res.data || !res.data.space) {
                        self.authError = (res && res.data && res.data.detail) ? String(res.data.detail) : t('main.simple.auth_error');
                        return;
                    }
                    var target = String(res.data.space || '').trim();
                    self.activeSpace = target;
                    setSpace(target);
                    self.showAuthModal = false;
                }).catch(function() {
                    self.authError = t('main.simple.auth_error');
                });
            },
            navItemClass: function(step) {
                return {
                    'simple-page__nav-item': true,
                    'simple-page__nav-item--done': step.status === 'done',
                    'simple-page__nav-item--active': step.status === 'active',
                    'simple-page__nav-item--pending': step.status === 'pending'
                };
            },
            toggleTheme: function() {
                this.theme = this.theme === 'light' ? 'dark' : 'light';
            },
            onLogout: function() {
                fetch('/v1/auth/logout', { method: 'POST', credentials: 'same-origin' })
                    .catch(function() {})
                    .finally(function() {
                        clearSessionClientStorage();
                        window.location.reload();
                    });
            }
        },
        template: '\
<div :class="rootClass">\
  <div v-if="authReady && showAuthModal" class="simple-auth__overlay" role="dialog" aria-modal="true">\
    <div class="simple-auth__modal">\
      <h2 class="simple-auth__title">{{ t(\'main.simple.auth_modal_title\') }}</h2>\
      <p class="simple-auth__text">{{ t(\'main.simple.auth_modal_text\') }}</p>\
      <div class="simple-auth__tron">\
        <tron-login @success="onTronSuccess"></tron-login>\
      </div>\
      <div v-if="authError" class="simple-auth__error">{{ authError }}</div>\
    </div>\
  </div>\
  <div class="simple-page__window">\
    <div class="simple-page__titlebar">\
      <div class="simple-page__titlebar-text">{{ chromeTitle }}</div>\
      <div class="simple-page__titlebar-actions">\
        <button type="button" class="simple-page__link-home simple-page__link-home--btn" @click="onLogout">{{ t(\'main.simple.logout\') }}</button>\
        <button type="button" class="simple-page__theme-btn" :aria-label="themeBtnLabel" :title="themeBtnLabel" @click="toggleTheme">\
          <svg v-if="theme === \'light\'" class="simple-page__svg simple-page__svg--theme" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>\
          <svg v-else class="simple-page__svg simple-page__svg--theme" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path stroke-linecap="round" d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>\
        </button>\
      </div>\
    </div>\
    <div class="simple-page__body">\
      <aside class="simple-page__aside">\
        <div class="simple-page__aside-scroll">\
          <div class="simple-page__aside-label">{{ t(\'main.simple.sidebar_title\') }}</div>\
          <div class="simple-page__orders-block">\
            <a v-if="ordersListHref" :href="ordersListHref" class="simple-page__orders-cta">\
              <svg class="simple-page__svg--sm" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>\
              {{ t(\'main.simple.orders_list_cta\') }}\
            </a>\
            <span v-else class="simple-page__orders-cta simple-page__orders-cta--muted" role="note">{{ t(\'main.simple.orders_list_hint\') }}</span>\
          </div>\
          <details class="simple-page__stages-mobile">\
            <summary class="simple-page__stages-mobile-summary" :aria-label="t(\'main.simple.stages_expand_aria\')">\
              <span class="simple-page__stages-mobile-summary-inner">\
                <span v-if="activeNavStep" class="simple-page__stages-mobile-summary-title">{{ t(activeNavStep.titleKey) }}</span>\
                <span v-if="activeNavStep" class="simple-page__stages-mobile-summary-sub">{{ t(activeNavStep.subKey) }}</span>\
              </span>\
              <svg class="simple-page__stages-mobile-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>\
            </summary>\
            <div class="simple-page__stages-mobile-panel" role="list">\
              <div v-for="step in navSteps" :key="\'m-\' + step.num" class="simple-page__stages-mobile-row" :class="{\'simple-page__stages-mobile-row--active\': step.status === \'active\', \'simple-page__stages-mobile-row--done\': step.status === \'done\'}" role="listitem">\
                <span class="simple-page__stages-mobile-mark">\
                  <svg v-if="step.status === \'done\'" class="simple-page__svg--sm simple-page__stages-mobile-checkico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
                  <input v-else-if="step.status === \'active\'" type="checkbox" class="simple-page__stages-mobile-cb" checked="checked" disabled="disabled" :aria-label="t(\'main.simple.stages_current_aria\')" />\
                  <span v-else class="simple-page__stages-mobile-num">{{ step.num }}</span>\
                </span>\
                <div class="simple-page__stages-mobile-row-text">\
                  <div class="simple-page__stages-mobile-row-title">{{ t(step.titleKey) }}</div>\
                  <div v-if="step.status === \'active\'" class="simple-page__stages-mobile-row-sub">{{ t(step.subKey) }}</div>\
                </div>\
              </div>\
            </div>\
          </details>\
          <div class="simple-page__nav simple-page__nav--desktop" role="list">\
            <div v-for="step in navSteps" :key="step.num" :class="navItemClass(step)" role="listitem">\
              <div class="simple-page__nav-badge">\
                <svg v-if="step.status === \'done\'" class="simple-page__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
                <template v-else>{{ step.num }}</template>\
              </div>\
              <div class="simple-page__nav-text">\
                <div class="simple-page__nav-title">{{ t(step.titleKey) }}</div>\
                <div v-if="step.status === \'active\'" class="simple-page__nav-sub">{{ t(step.subKey) }}</div>\
              </div>\
              <svg v-if="step.status === \'done\'" class="simple-page__nav-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
              <span v-if="step.status === \'active\'" class="simple-page__nav-pulse" aria-hidden="true"></span>\
            </div>\
          </div>\
        </div>\
        <div class="simple-page__aside-footer">\
          <svg class="simple-page__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>\
          {{ t(\'main.simple.arbitration\') }}\
        </div>\
      </aside>\
      <main class="simple-page__main">\
        <div class="simple-page__main-scroll">\
          <div class="simple-page__stat-rail" role="region" :aria-label="t(\'main.simple.stat_carousel_aria\')">\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_amount_short\') }}</div>\
              <div class="simple-page__stat-value">125K <span style="color:var(--simple-primary)">USDT</span></div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_receives_short\') }}</div>\
              <div class="simple-page__stat-value">862.5K <span style="color:var(--simple-success)">CNY</span></div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_rate_short\') }}</div>\
              <div class="simple-page__stat-value">6.90 <span style="color:var(--simple-muted);font-weight:600">¥/$</span></div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_network_short\') }}</div>\
              <div class="simple-page__stat-value simple-page__stat-value--rail-net">\
                <span class="simple-page__stat-tron-badge">T</span>\
                TRON\
              </div>\
              <div class="simple-page__stat-sub">TRON</div>\
            </div>\
          </div>\
          <div class="simple-page__stat-grid simple-page__stat-grid--desktop">\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_amount\') }}</div>\
              <div class="simple-page__stat-value">125K <span style="color:var(--simple-primary)">USDT</span></div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_receives\') }}</div>\
              <div class="simple-page__stat-value">862.5K <span style="color:var(--simple-success)">CNY</span></div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_rate\') }}</div>\
              <div class="simple-page__stat-value">6.90 <span style="color:var(--simple-muted);font-weight:600">¥/$</span></div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_network\') }}</div>\
              <div class="simple-page__stat-value" style="display:flex;align-items:center;gap:0.5rem;justify-content:center">\
                <span style="display:inline-flex;width:2rem;height:2rem;border-radius:0.5rem;background:#ef4444;color:#fff;font-size:10px;font-weight:800;align-items:center;justify-content:center">T</span>\
                TRON\
              </div>\
              <div class="simple-page__stat-sub">TRON</div>\
            </div>\
          </div>\
          <div class="simple-page__flow-shell">\
            <div class="simple-page__flow-row">\
              <div class="simple-page__flow-icon">\
                <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
              </div>\
              <div class="simple-page__flow-body">\
                <div class="simple-page__flow-title">{{ t(\'main.simple.sender\') }}</div>\
                <div class="simple-page__flow-mono">{{ t(\'main.simple.sender_line\') }}</div>\
              </div>\
              <div class="simple-page__flow-status">\
                {{ t(\'main.simple.sender_sent\') }}\
                <svg class="simple-page__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
              </div>\
            </div>\
            <div class="simple-page__lockbox">\
              <div class="simple-page__lockbox-tag">{{ t(\'main.simple.lockbox_locked\') }}</div>\
              <div class="simple-page__lockbox-head">\
                <svg class="simple-page__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                <span class="simple-page__lockbox-brand">{{ t(\'main.simple.lockbox_title\') }}</span>\
              </div>\
              <div class="simple-page__flow-mono" style="margin-bottom:1rem">{{ t(\'main.simple.lockbox_contract_line\') }}</div>\
              <div class="simple-page__lockbox-inner">\
                <svg class="simple-page__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                {{ t(\'main.simple.lockbox_frozen_line\') }}\
              </div>\
            </div>\
            <div class="simple-page__recipient-wrap">\
              <div class="simple-page__flow-row">\
                <div class="simple-page__flow-icon simple-page__flow-icon--muted">\
                  <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
                </div>\
                <div class="simple-page__flow-body">\
                  <div class="simple-page__flow-title">{{ t(\'main.simple.recipient\') }}</div>\
                  <div class="simple-page__flow-mono">{{ t(\'main.simple.recipient_line\') }}</div>\
                </div>\
              </div>\
            </div>\
          </div>\
        <div class="simple-page__footer">\
          <div class="simple-page__footer-row">\
            <svg class="simple-page__svg--sm" style="color:var(--simple-primary)" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>\
            {{ escrowLine }}\
          </div>\
          <div class="simple-page__footer-row">\
            {{ t(\'main.simple.network_ok\') }}\
            <span class="simple-page__dot-online" aria-hidden="true"></span>\
          </div>\
        </div>\
        </div>\
      </main>\
    </div>\
  </div>\
  <div class="simple-page__fab" role="status">\
    <svg class="simple-page__svg" style="color:var(--simple-primary);flex-shrink:0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>\
    <span>{{ t(\'main.simple.protected_badge\') }}</span>\
  </div>\
</div>'
    });
})();
