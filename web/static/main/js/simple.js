/**
 * Публичная страница /simple: Vue 2 (UDM), перенос UI trustflow-p2p-cmc.
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
                    'p2p-deal': true,
                    'p2p-deal--dark': this.theme === 'dark'
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
                    'p2p-deal__nav-item': true,
                    'p2p-deal__nav-item--done': step.status === 'done',
                    'p2p-deal__nav-item--active': step.status === 'active',
                    'p2p-deal__nav-item--pending': step.status === 'pending'
                };
            },
            toggleTheme: function() {
                this.theme = this.theme === 'light' ? 'dark' : 'light';
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
  <div class="p2p-deal__window">\
    <div class="p2p-deal__titlebar">\
      <div class="p2p-deal__traffic" aria-hidden="true"><span></span><span></span><span></span></div>\
      <div class="p2p-deal__titlebar-text">{{ chromeTitle }}</div>\
      <div class="p2p-deal__titlebar-actions">\
        <a class="p2p-deal__link-home" href="/">{{ t(\'main.simple.back_home\') }}</a>\
      </div>\
    </div>\
    <div class="p2p-deal__body">\
      <aside class="p2p-deal__aside">\
        <div class="p2p-deal__aside-scroll">\
          <div class="p2p-deal__aside-label">{{ t(\'main.simple.sidebar_title\') }}</div>\
          <div class="p2p-deal__nav" role="list">\
            <div v-for="step in navSteps" :key="step.num" :class="navItemClass(step)" role="listitem">\
              <div class="p2p-deal__nav-badge">\
                <svg v-if="step.status === \'done\'" class="p2p-deal__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
                <template v-else>{{ step.num }}</template>\
              </div>\
              <div class="p2p-deal__nav-text">\
                <div class="p2p-deal__nav-title">{{ t(step.titleKey) }}</div>\
                <div v-if="step.status === \'active\'" class="p2p-deal__nav-sub">{{ t(step.subKey) }}</div>\
              </div>\
              <svg v-if="step.status === \'done\'" class="p2p-deal__nav-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
              <span v-if="step.status === \'active\'" class="p2p-deal__nav-pulse" aria-hidden="true"></span>\
            </div>\
          </div>\
        </div>\
        <div class="p2p-deal__aside-footer">\
          <svg class="p2p-deal__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>\
          {{ t(\'main.simple.arbitration\') }}\
        </div>\
      </aside>\
      <main class="p2p-deal__main">\
        <div class="p2p-deal__main-scroll">\
          <div class="p2p-deal__stat-grid">\
            <div class="p2p-deal__stat-card">\
              <div class="p2p-deal__stat-label">{{ t(\'main.simple.stat_amount\') }}</div>\
              <div class="p2p-deal__stat-value">125K <span style="color:var(--p2p-primary)">USDT</span></div>\
            </div>\
            <div class="p2p-deal__stat-card">\
              <div class="p2p-deal__stat-label">{{ t(\'main.simple.stat_receives\') }}</div>\
              <div class="p2p-deal__stat-value">862.5K <span style="color:var(--p2p-success)">CNY</span></div>\
            </div>\
            <div class="p2p-deal__stat-card">\
              <div class="p2p-deal__stat-label">{{ t(\'main.simple.stat_rate\') }}</div>\
              <div class="p2p-deal__stat-value">6.90 <span style="color:var(--p2p-muted);font-weight:600">¥/$</span></div>\
            </div>\
            <div class="p2p-deal__stat-card">\
              <div class="p2p-deal__stat-label">{{ t(\'main.simple.stat_network\') }}</div>\
              <div class="p2p-deal__stat-value" style="display:flex;align-items:center;gap:0.5rem;justify-content:center">\
                <span style="display:inline-flex;width:2rem;height:2rem;border-radius:0.5rem;background:#ef4444;color:#fff;font-size:10px;font-weight:800;align-items:center;justify-content:center">T</span>\
                TRON\
              </div>\
              <div class="p2p-deal__stat-sub">TRON</div>\
            </div>\
          </div>\
          <div class="p2p-deal__flow-shell">\
            <div class="p2p-deal__flow-row">\
              <div class="p2p-deal__flow-icon">\
                <svg class="p2p-deal__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
              </div>\
              <div class="p2p-deal__flow-body">\
                <div class="p2p-deal__flow-title">{{ t(\'main.simple.sender\') }}</div>\
                <div class="p2p-deal__flow-mono">{{ t(\'main.simple.sender_line\') }}</div>\
              </div>\
              <div class="p2p-deal__flow-status">\
                {{ t(\'main.simple.sender_sent\') }}\
                <svg class="p2p-deal__svg--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>\
              </div>\
            </div>\
            <div class="p2p-deal__lockbox">\
              <div class="p2p-deal__lockbox-tag">{{ t(\'main.simple.lockbox_locked\') }}</div>\
              <div class="p2p-deal__lockbox-head">\
                <svg class="p2p-deal__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                <span class="p2p-deal__lockbox-brand">{{ t(\'main.simple.lockbox_title\') }}</span>\
              </div>\
              <div class="p2p-deal__flow-mono" style="margin-bottom:1rem">{{ t(\'main.simple.lockbox_contract_line\') }}</div>\
              <div class="p2p-deal__lockbox-inner">\
                <svg class="p2p-deal__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                {{ t(\'main.simple.lockbox_frozen_line\') }}\
              </div>\
            </div>\
            <div class="p2p-deal__recipient-wrap">\
              <div class="p2p-deal__flow-row">\
                <div class="p2p-deal__flow-icon p2p-deal__flow-icon--muted">\
                  <svg class="p2p-deal__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
                </div>\
                <div class="p2p-deal__flow-body">\
                  <div class="p2p-deal__flow-title">{{ t(\'main.simple.recipient\') }}</div>\
                  <div class="p2p-deal__flow-mono">{{ t(\'main.simple.recipient_line\') }}</div>\
                </div>\
              </div>\
            </div>\
          </div>\
        </div>\
        <div class="p2p-deal__footer">\
          <div class="p2p-deal__footer-row">\
            <svg class="p2p-deal__svg--sm" style="color:var(--p2p-primary)" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>\
            {{ escrowLine }}\
          </div>\
          <div class="p2p-deal__footer-row">\
            {{ t(\'main.simple.network_ok\') }}\
            <span class="p2p-deal__dot-online" aria-hidden="true"></span>\
          </div>\
        </div>\
      </main>\
    </div>\
  </div>\
  <div class="p2p-deal__fab" role="status">\
    <svg class="p2p-deal__svg" style="color:var(--p2p-primary);flex-shrink:0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>\
    <span>{{ t(\'main.simple.protected_badge\') }}</span>\
  </div>\
  <button type="button" class="p2p-deal__theme-btn" :aria-label="themeBtnLabel" :title="themeBtnLabel" @click="toggleTheme">\
    <svg v-if="theme === \'light\'" class="p2p-deal__svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>\
    <svg v-else class="p2p-deal__svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path stroke-linecap="round" d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>\
  </button>\
</div>'
    });
})();
