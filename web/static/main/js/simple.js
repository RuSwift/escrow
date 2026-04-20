/**
 * Публичная страница /arbiter/{arbiter_space_did}: Vue 2 (UDM).
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

    var ORDERS_SEARCH_DEBOUNCE_MS = 300;

    function stablecoinsList() {
        var raw = typeof window !== 'undefined' ? window.__SIMPLE_STABLECOINS__ : null;
        return Array.isArray(raw) ? raw : [];
    }

    function fiatCodesList() {
        var raw = typeof window !== 'undefined' ? window.__SIMPLE_FIAT_CODES__ : null;
        return Array.isArray(raw) ? raw : [];
    }

    function buildUnifiedAssetOptions() {
        var seen = {};
        var out = [];
        stablecoinsList().forEach(function(x) {
            var sym = (x && x.symbol) ? String(x.symbol).trim().toUpperCase() : '';
            if (!sym || seen[sym]) return;
            seen[sym] = true;
            out.push({ code: sym, kind: 'stable' });
        });
        fiatCodesList().forEach(function(code) {
            var c = String(code || '').trim().toUpperCase();
            if (!c || seen[c]) return;
            seen[c] = true;
            out.push({ code: c, kind: 'fiat' });
        });
        return out;
    }

    function amountLocaleTag() {
        try {
            var L = (typeof window !== 'undefined' && window.__LOCALE__) ? String(window.__LOCALE__).trim() : '';
            if (!L) return 'ru';
            return L.replace(/_/g, '-');
        } catch (e) {
            return 'ru';
        }
    }

    function localePrefersCommaDecimal() {
        var low = amountLocaleTag().toLowerCase();
        return low.indexOf('en') !== 0;
    }

    /**
     * Ввод суммы: цифры, один десятичный разделитель; пробелы как в форматировании убираются.
     * При вставке "1,234.56" / "1.234,56" десятичным считается последний разделитель.
     */
    function sanitizeDecimalAmountInput(raw) {
        var s = raw === undefined || raw === null ? '' : String(raw);
        s = s.replace(/[\s\u00A0\u202F]/g, '');
        var lastComma = s.lastIndexOf(',');
        var lastDot = s.lastIndexOf('.');
        if (lastComma >= 0 && lastDot >= 0) {
            if (lastDot > lastComma) {
                s = s.split(',').join('');
            } else {
                s = s.split('.').join('');
            }
        } else if (lastComma >= 0 && lastDot < 0 && !localePrefersCommaDecimal()) {
            if (/^\d{1,3}(,\d{3})+$/.test(s)) {
                s = s.replace(/,/g, '');
            }
        } else if (lastDot >= 0 && lastComma < 0 && localePrefersCommaDecimal()) {
            if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
                s = s.split('.').join('');
            }
        }
        var out = '';
        var sep = false;
        for (var i = 0; i < s.length; i++) {
            var c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                out += c;
                continue;
            }
            if ((c === '.' || c === ',') && !sep) {
                sep = true;
                out += '.';
            }
        }
        return out;
    }

    /** Нормализация к двум знакам после точки (хранение и отправка). */
    function normalizeAmountTwoDecimals(raw) {
        var s = sanitizeDecimalAmountInput(raw);
        if (!s) return '';
        var n = parseFloat(s);
        if (!isFinite(n)) return '';
        var r = Math.round(n * 1e2) / 1e2;
        return r.toFixed(2);
    }

    /** Отображение с группировкой тысяч и ровно 2 дробными знаками (Intl + __LOCALE__). */
    function formatAmountForLocale(rawDot) {
        var s = String(rawDot || '').trim();
        if (!s) return '';
        var n = parseFloat(sanitizeDecimalAmountInput(s));
        if (!isFinite(n)) return '';
        var loc = amountLocaleTag();
        try {
            return new Intl.NumberFormat(loc, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(n);
        } catch (e) {
            try {
                return new Intl.NumberFormat('ru', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }).format(n);
            } catch (e2) {
                return n.toFixed(2);
            }
        }
    }

    /** Нога заявки: fiat | stable по direction (fiat_to_stable / stable_to_fiat). */
    function prLegForAsset(pr, wantFiat) {
        if (!pr) return null;
        var d = String(pr.direction || '');
        if (d === 'fiat_to_stable') {
            return wantFiat ? pr.primary_leg : pr.counter_leg;
        }
        if (d === 'stable_to_fiat') {
            return wantFiat ? pr.counter_leg : pr.primary_leg;
        }
        return null;
    }

    /**
     * Курс из заявки: raw = counter_amt / primary_amt.
     * Если raw < 1 — показываем обратный 1/raw и меняем ось подписи (см. dealViewStatRateLabel).
     */
    function paymentRequestDisplayRateMeta(pr) {
        if (!pr) return null;
        var pl = pr.primary_leg || {};
        var cl = pr.counter_leg || {};
        var pa = pl.amount != null ? parseFloat(sanitizeDecimalAmountInput(String(pl.amount))) : NaN;
        var ca = cl.amount != null ? parseFloat(sanitizeDecimalAmountInput(String(cl.amount))) : NaN;
        if (!isFinite(pa) || !isFinite(ca) || pa <= 0) return null;
        var raw = ca / pa;
        if (!isFinite(raw) || raw <= 0) return null;
        var inverted = raw < 1;
        var display = inverted ? 1 / raw : raw;
        var fiatLeg = prLegForAsset(pr, true);
        var stableLeg = prLegForAsset(pr, false);
        var fiat = fiatLeg && fiatLeg.code ? String(fiatLeg.code).trim().toUpperCase() : '';
        var st = stableLeg && stableLeg.code ? String(stableLeg.code).trim().toUpperCase() : '';
        var d = String(pr.direction || '');
        return { raw: raw, display: display, inverted: inverted, fiat: fiat, st: st, d: d };
    }

    function formatPaymentRequestLegLine(leg, allowDiscussed) {
        if (!leg) return '—';
        var amt = leg.amount != null ? String(leg.amount).trim() : '';
        var code = leg.code ? String(leg.code).trim().toUpperCase() : '';
        if (allowDiscussed && !amt && leg.amount_discussed) {
            return code ? code + ' (' + t('main.simple.counter_discussed_short') + ')' : '—';
        }
        var fmt = amt ? formatAmountForLocale(amt) : '';
        return fmt ? fmt + ' ' + code : (code || '—');
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
                navSteps: (function initialNavSteps() {
                    var du = (el.getAttribute('data-simple-deal-uid') || '').trim();
                    /* /arbiter/.../deal/{uid}: до resolve показываем активным этап «Условия», не Lockbox */
                    var s1 = du ? 'active' : 'done';
                    var s2 = du ? 'pending' : 'active';
                    return [
                        { num: '01', titleKey: 'main.simple.nav_step1_title', subKey: 'main.simple.nav_step1_sub', status: s1 },
                        { num: '02', titleKey: 'main.simple.nav_step2_title', subKey: 'main.simple.nav_step2_sub', status: s2 },
                        { num: '03', titleKey: 'main.simple.nav_step3_title', subKey: 'main.simple.nav_step3_sub', status: 'pending' },
                        { num: '04', titleKey: 'main.simple.nav_step4_title', subKey: 'main.simple.nav_step4_sub', status: 'pending' }
                    ];
                })(),
                orderId: (el.getAttribute('data-simple-order-id') || '').trim(),
                dealUid: (el.getAttribute('data-simple-deal-uid') || '').trim(),
                arbiterSpaceDid: (el.getAttribute('data-simple-arbiter-space-did') || '').trim(),
                resolveLoading: false,
                resolveError: false,
                resolveErrorMsg: '',
                resolveKind: null,
                resolvePaymentRequest: null,
                resolveDeal: null,
                /* Без префикса _: Vue 2 не проксирует data._* на this — иначе ++ даёт NaN. */
                resolveFetchSeq: 0,
                ordersItems: [],
                ordersTotal: 0,
                ordersLoading: false,
                ordersError: false,
                ordersPage: 1,
                ordersPageSize: 10,
                ordersSearch: '',
                ordersFetchSeq: 0,
                _ordersSearchDebounce: null,
                showCreateModal: false,
                showDeactivateModal: false,
                deactivateTargetPk: null,
                deactivateConfirm: '',
                deactivateError: '',
                deactivateSubmitting: false,
                createSubmitting: false,
                createError: '',
                giveCode: '',
                giveAmount: '',
                giveAmountFocus: false,
                receiveCode: '',
                receiveAmount: '',
                receiveAmountFocus: false,
                receiveAmountMode: 'negotiable',
                createHeading: '',
                createLifetime: '72h',
                /** Тик для перерисовки countdown по expires_at заявок. */
                countdownTick: 0,
                /** Кэш payload GET /ui-prefs для мгновенного применения при повторном открытии модалки. */
                _uiPrefsPayloadCache: null,
                _countdownInterval: null
            };
        },
        watch: {
            giveCode: function(newVal) {
                var self = this;
                /* Срабатывает только при реальном изменении giveCode; не полагаемся на oldVal —
                   в одном тике Vue иногда отдаёт oldVal === newVal. */
                self.giveAmountFocus = false;
                self.giveAmount = '';
                if (!newVal) {
                    self.receiveCode = '';
                    self.receiveAmount = '';
                    return;
                }
                var gv = String(newVal).trim().toUpperCase();
                if (self.receiveCode === gv) {
                    self.receiveCode = '';
                    self.receiveAmount = '';
                }
                self.$nextTick(function() {
                    var ro = self.receiveOptions;
                    var rc = (self.receiveCode || '').trim().toUpperCase();
                    if (!rc) return;
                    var ok = false;
                    for (var j = 0; j < ro.length; j++) {
                        if (ro[j].code === rc) {
                            ok = true;
                            break;
                        }
                    }
                    if (!ok) {
                        self.receiveCode = '';
                        self.receiveAmount = '';
                    }
                });
            },
            theme: function(v) {
                try {
                    localStorage.setItem(STORAGE_KEY, v);
                } catch (e) {}
            },
            showAuthModal: function() {
                this.maybeFetchOrders();
                this.maybeFetchResolve();
            },
            activeSpace: function() {
                this.maybeFetchOrders();
            }
        },
        beforeDestroy: function() {
            if (this._ordersSearchDebounce != null) {
                clearTimeout(this._ordersSearchDebounce);
                this._ordersSearchDebounce = null;
            }
            if (this._countdownInterval != null) {
                clearInterval(this._countdownInterval);
                this._countdownInterval = null;
            }
        },
        created: function() {
            var self = this;
            if (self.dealUid) {
                self.resolveLoading = true;
            }
            this.countdownTick = Date.now();
            this._countdownInterval = setInterval(function() {
                self.countdownTick = Date.now();
            }, 1000);

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
                self.maybeFetchOrders();
                self.maybeFetchResolve();
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
                self.maybeFetchOrders();
                self.maybeFetchResolve();
            });
        },
        computed: {
            rootClass: function() {
                return {
                    'simple-page': true,
                    'simple-page--dark': this.theme === 'dark'
                };
            },
            isDealView: function() {
                return !!(this.dealUid || this.orderId);
            },
            chromeTitle: function() {
                if (this.dealUid) {
                    if (!this.resolveLoading && !this.resolveError && this.resolveKind === 'payment_request_only' && this.resolvePaymentRequest) {
                        return this.appName + ' — ' + this.orderListTitle(this.resolvePaymentRequest);
                    }
                    if (!this.resolveLoading && !this.resolveError && this.resolveKind === 'deal_only' && this.resolveDeal) {
                        var dd = this.resolveDeal;
                        var lb = (dd.label || '').trim();
                        if (lb) return this.appName + ' — ' + lb;
                        var du = String(dd.uid || '').trim();
                        return du ? (this.appName + ' — ' + du.slice(0, 20)) : (this.appName + ' — ' + String(this.dealUid).slice(0, 20));
                    }
                    return t('main.simple.chrome_title_deal_uid', { app_name: this.appName, deal_uid: this.dealUid });
                }
                if (this.orderId) {
                    return t('main.simple.chrome_title_deal', { app_name: this.appName, order_id: this.orderId });
                }
                return t('main.simple.chrome_title_list', { app_name: this.appName });
            },
            /** Страница /arbiter/.../deal/{uid}: данные resolve загружены и можно рисовать блоки. */
            dealViewShowResolved: function() {
                return !!(this.dealUid && !this.resolveLoading && !this.resolveError && this.resolveKind);
            },
            /** Заявка снята с публикации (деактивирована владельцем). */
            dealPrDeactivated: function() {
                return !!(
                    this.resolveKind === 'payment_request_only' &&
                    this.resolvePaymentRequest &&
                    this.resolvePaymentRequest.deactivated_at
                );
            },
            unifiedAssetOptions: function() {
                return buildUnifiedAssetOptions();
            },
            /** Пока нет актива «Отдаю» — нельзя вводить сумму отдачи. */
            giveAssetEmpty: function() {
                return !(this.giveCode || '').trim();
            },
            /** «Получаю» недоступно, пока не выбран актив и не введена сумма «Отдаю». */
            receiveLocked: function() {
                if (this.giveAssetEmpty) return true;
                return !(this.giveAmount || '').trim();
            },
            giveAmountInputDisplay: function() {
                if (this.giveAmountFocus) return this.giveAmount;
                return formatAmountForLocale(this.giveAmount);
            },
            receiveAmountInputDisplay: function() {
                if (this.receiveAmountFocus) return this.receiveAmount;
                return formatAmountForLocale(this.receiveAmount);
            },
            receiveOptions: function() {
                var g = (this.giveCode || '').trim().toUpperCase();
                if (!g) return [];
                var opts = this.unifiedAssetOptions;
                var giveMeta = null;
                for (var i = 0; i < opts.length; i++) {
                    if (opts[i].code === g) {
                        giveMeta = opts[i];
                        break;
                    }
                }
                if (!giveMeta) return [];
                var wantKind = giveMeta.kind === 'fiat' ? 'stable' : 'fiat';
                return opts.filter(function(o) {
                    return o.code !== g && o.kind === wantKind;
                });
            },
            createSubmitDisabled: function() {
                if (this.createSubmitting) return true;
                if (this.receiveLocked) return true;
                if (!(this.giveAmount || '').trim()) return true;
                if (!(this.receiveCode || '').trim()) return true;
                if (this.receiveAmountMode === 'fixed' && !(this.receiveAmount || '').trim()) return true;
                return false;
            },
            escrowLine: function() {
                if (this.resolveKind === 'deal_only' && this.resolveDeal && this.resolveDeal.uid) {
                    var u = String(this.resolveDeal.uid).trim();
                    var short = u.length > 18 ? u.slice(0, 10) + '…' + u.slice(-6) : u;
                    return t('main.simple.deal_uid_footer', { uid: short });
                }
                if (
                    this.resolveKind === 'payment_request_only' &&
                    this.resolvePaymentRequest &&
                    this.resolvePaymentRequest.deactivated_at
                ) {
                    return t('main.simple.deal_escrow_deactivated_footer');
                }
                if (this.resolveKind === 'payment_request_only') {
                    return t('main.simple.deal_escrow_pending_footer');
                }
                return t('main.simple.escrow_line', { addr: '…' });
            },
            themeBtnLabel: function() {
                return this.theme === 'light' ? t('main.simple.theme_dark') : t('main.simple.theme_light');
            },
            ordersListHref: function() {
                if (!this.isDealView) return '';
                var a = (this.arbiterSpaceDid || '').trim();
                if (!a) return '/arbiter';
                return '/arbiter/' + encodeURIComponent(a);
            },
            activeNavStep: function() {
                var steps = this.navSteps;
                for (var i = 0; i < steps.length; i++) {
                    if (steps[i].status === 'active') return steps[i];
                }
                return steps.length ? steps[0] : null;
            },
            ordersTotalPages: function() {
                var sz = this.ordersPageSize || 10;
                var tot = typeof this.ordersTotal === 'number' ? this.ordersTotal : 0;
                if (tot <= 0) return 0;
                return Math.ceil(tot / sz);
            },
            ordersPaginationLabel: function() {
                var m = this.ordersTotalPages;
                if (m <= 1) return '';
                return t('main.simple.orders_pagination_page', {
                    current: String(this.ordersPage),
                    total: String(m)
                });
            },
            ordersPrevDisabled: function() {
                return this.ordersLoading || this.ordersPage <= 1;
            },
            ordersNextDisabled: function() {
                return this.ordersLoading || this.ordersPage >= this.ordersTotalPages;
            },
            deactivateSubmitDisabled: function() {
                if (this.deactivateSubmitting) return true;
                if (this.deactivateTargetPk == null) return true;
                return !(String(this.deactivateConfirm || '').trim());
            }
        },
        methods: {
            t: t,
            /** База HTML-путей: /arbiter/{encodeURIComponent(arbiter_space_did)} */
            simpleHtmlBase: function() {
                var a = (this.arbiterSpaceDid || '').trim();
                if (!a) return '/arbiter';
                return '/arbiter/' + encodeURIComponent(a);
            },
            /** Префикс JSON API: /v1/arbiter/{encodeURIComponent(arbiter_space_did)}/ */
            simpleV1Prefix: function() {
                var a = (this.arbiterSpaceDid || '').trim();
                if (!a) return '/v1/arbiter/';
                return '/v1/arbiter/' + encodeURIComponent(a) + '/';
            },
            maybeFetchOrders: function() {
                if (this.isDealView || !this.authReady || this.showAuthModal) return;
                this.ordersPage = 1;
                this.fetchOrders();
            },
            maybeFetchResolve: function() {
                if (!this.dealUid) return;
                if (!this.authReady || this.showAuthModal) {
                    this.resolveLoading = false;
                    return;
                }
                this.fetchResolve();
            },
            /** Этапы сайдбара: заявка — «Условия»; созданная сделка — Lockbox. */
            applyNavStepsForResolveKind: function(kind) {
                var steps = this.navSteps;
                if (!steps || !steps.length) return;
                if (kind === 'deal_only') {
                    if (steps[0]) steps[0].status = 'done';
                    if (steps[1]) steps[1].status = 'active';
                    if (steps[2]) steps[2].status = 'pending';
                    if (steps[3]) steps[3].status = 'pending';
                    return;
                }
                if (kind === 'payment_request_only') {
                    if (steps[0]) steps[0].status = 'active';
                    if (steps[1]) steps[1].status = 'pending';
                    if (steps[2]) steps[2].status = 'pending';
                    if (steps[3]) steps[3].status = 'pending';
                }
            },
            fetchResolve: function() {
                var self = this;
                if (!self.dealUid) return;
                var mySeq = ++self.resolveFetchSeq;
                self.resolveLoading = true;
                self.resolveError = false;
                self.resolveErrorMsg = '';
                var tok = getToken();
                var headers = { Accept: 'application/json' };
                if (tok) headers.Authorization = 'Bearer ' + tok;
                fetch(self.simpleV1Prefix() + 'resolve/' + encodeURIComponent(self.dealUid), {
                    method: 'GET',
                    headers: headers,
                    credentials: 'same-origin'
                })
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (mySeq !== self.resolveFetchSeq) return;
                        if (!res.ok) {
                            self.resolveError = true;
                            var d = res.data && res.data.detail;
                            self.resolveErrorMsg = typeof d === 'string' ? d : '';
                            self.resolveKind = null;
                            self.resolvePaymentRequest = null;
                            self.resolveDeal = null;
                            return;
                        }
                        var data = res.data || {};
                        self.resolveKind = data.kind || null;
                        self.resolvePaymentRequest = data.payment_request || null;
                        self.resolveDeal = data.deal || null;
                        self.applyNavStepsForResolveKind(self.resolveKind);
                    })
                    .catch(function() {
                        if (mySeq !== self.resolveFetchSeq) return;
                        self.resolveError = true;
                        self.resolveErrorMsg = t('main.simple.resolve_error');
                        self.resolveKind = null;
                        self.resolvePaymentRequest = null;
                        self.resolveDeal = null;
                    })
                    .finally(function() {
                        /* Снимаем спиннер только для актуального запроса (без гонки двух fetchResolve). */
                        if (mySeq !== self.resolveFetchSeq) return;
                        self.resolveLoading = false;
                    });
            },
            /** Подзаголовок шага 02 в сайдбаре (динамика из resolve). */
            navStepActiveSub: function(step) {
                if (step.status !== 'active') return '';
                if (step.num !== '02') return t(step.subKey);
                if (this.resolveLoading) return '…';
                if (this.resolveKind === 'payment_request_only' && this.resolvePaymentRequest) {
                    var line = this.dealLockboxHintFromPr(this.resolvePaymentRequest);
                    return line || t('main.simple.nav_step2_sub');
                }
                if (this.resolveKind === 'deal_only' && this.resolveDeal) {
                    return String(this.resolveDeal.status || '') || t('main.simple.nav_step2_sub');
                }
                return t('main.simple.nav_step2_sub');
            },
            /** Строка для блока lockbox inner при заявке (сумма стейбла / контекст). */
            dealLockboxHintFromPr: function(req) {
                if (!req) return '';
                var dir = String(req.direction || '');
                var pl = req.primary_leg || {};
                var cl = req.counter_leg || {};
                var stableLeg = dir === 'stable_to_fiat' ? pl : cl;
                var at = String(stableLeg.asset_type || '').toLowerCase();
                if (at !== 'stable') return '';
                var amt = stableLeg.amount != null ? String(stableLeg.amount).trim() : '';
                var code = stableLeg.code ? String(stableLeg.code).trim().toUpperCase() : '';
                var fmt = amt ? formatAmountForLocale(amt) : '';
                if (fmt && code) return fmt + ' ' + code;
                return code || '';
            },
            /** Текст под заголовком мобильного summary для активного шага. */
            mobileSummarySub: function() {
                if (!this.activeNavStep) return '';
                return this.navStepActiveSub(this.activeNavStep);
            },
            dealViewStatGive: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return '—';
                var pr = this.resolvePaymentRequest;
                var pl = pr.primary_leg || {};
                var amt = pl.amount != null ? String(pl.amount).trim() : '';
                var code = pl.code ? String(pl.code).trim().toUpperCase() : '';
                var fmt = amt ? formatAmountForLocale(amt) : '';
                return fmt ? fmt + ' ' + code : (code || '—');
            },
            dealViewStatReceive: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return '—';
                var pr = this.resolvePaymentRequest;
                var cl = pr.counter_leg || {};
                var amt = cl.amount != null ? String(cl.amount).trim() : '';
                var code = cl.code ? String(cl.code).trim().toUpperCase() : '';
                if (!amt && cl.amount_discussed) {
                    return code ? code + ' (' + t('main.simple.counter_discussed_short') + ')' : '—';
                }
                var fmt = amt ? formatAmountForLocale(amt) : '';
                return fmt ? fmt + ' ' + code : (code || '—');
            },
            /** Карточка «Сумма»: только фиат-нога. */
            dealViewStatFiatAmount: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return '—';
                return formatPaymentRequestLegLine(prLegForAsset(this.resolvePaymentRequest, true), false);
            },
            /** Карточка «Залог»: только стейбл-нога. */
            dealViewStatStableAmount: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return '—';
                return formatPaymentRequestLegLine(prLegForAsset(this.resolvePaymentRequest, false), true);
            },
            dealViewStatRate: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return '—';
                var m = paymentRequestDisplayRateMeta(this.resolvePaymentRequest);
                if (!m) return '—';
                return m.display.toFixed(4);
            },
            /**
             * Подпись к числу курса: ось совпадает с отображаемым значением
             * (при raw < 1 — обратный курс и переставленная ось через те же ключи i18n).
             */
            dealViewStatRateLabel: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) {
                    return t('main.simple.stat_rate');
                }
                var m = paymentRequestDisplayRateMeta(this.resolvePaymentRequest);
                if (!m) return t('main.simple.stat_rate');
                var fiat = m.fiat;
                var st = m.st;
                var d = m.d;
                var inv = m.inverted;
                if (d === 'fiat_to_stable' && fiat && st) {
                    return inv
                        ? t('main.simple.stat_rate_label_stable_to_fiat', { stable: st, fiat: fiat })
                        : t('main.simple.stat_rate_label_fiat_to_stable', { stable: st, fiat: fiat });
                }
                if (d === 'stable_to_fiat' && fiat && st) {
                    return inv
                        ? t('main.simple.stat_rate_label_fiat_to_stable', { stable: st, fiat: fiat })
                        : t('main.simple.stat_rate_label_stable_to_fiat', { stable: st, fiat: fiat });
                }
                return t('main.simple.stat_rate');
            },
            dealViewDealAmountLine: function() {
                if (this.resolveKind !== 'deal_only' || !this.resolveDeal) return '—';
                var d = this.resolveDeal;
                if (d.amount != null && String(d.amount).trim() !== '') {
                    return formatAmountForLocale(String(d.amount).trim());
                }
                return '—';
            },
            dealDealLabelPreview: function() {
                var d = this.resolveDeal;
                if (!d) return '';
                var s = String(d.label || '').trim();
                if (!s) return String(d.uid || '').slice(0, 24);
                return s.length > 52 ? s.slice(0, 49) + '…' : s;
            },
            onOrdersSearchInput: function() {
                var self = this;
                if (self._ordersSearchDebounce != null) {
                    clearTimeout(self._ordersSearchDebounce);
                    self._ordersSearchDebounce = null;
                }
                self._ordersSearchDebounce = setTimeout(function() {
                    self._ordersSearchDebounce = null;
                    self.ordersPage = 1;
                    self.fetchOrders();
                }, ORDERS_SEARCH_DEBOUNCE_MS);
            },
            ordersGoPrev: function() {
                if (this.ordersPrevDisabled) return;
                this.ordersPage = Math.max(1, this.ordersPage - 1);
                this.fetchOrders();
            },
            ordersGoNext: function() {
                if (this.ordersNextDisabled) return;
                var m = this.ordersTotalPages;
                if (m <= 0) return;
                this.ordersPage = Math.min(m, this.ordersPage + 1);
                this.fetchOrders();
            },
            fetchOrders: function() {
                var self = this;
                if (self.isDealView) return;
                var mySeq = ++self.ordersFetchSeq;
                self.ordersLoading = true;
                self.ordersError = false;
                var params = new URLSearchParams();
                params.set('page', String(self.ordersPage));
                params.set('page_size', String(self.ordersPageSize));
                var q = (self.ordersSearch || '').trim();
                if (q) params.set('q', q);
                var url = self.simpleV1Prefix() + 'payment-requests?' + params.toString();
                var headers = { Accept: 'application/json' };
                var tok = getToken();
                if (tok) headers.Authorization = 'Bearer ' + tok;
                fetch(url, { method: 'GET', headers: headers, credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) throw new Error('deals');
                        return r.json();
                    })
                    .then(function(data) {
                        if (mySeq !== self.ordersFetchSeq) return;
                        self.ordersItems = data && data.items ? data.items : [];
                        self.ordersTotal = data && typeof data.total === 'number' ? data.total : 0;
                        var sz = self.ordersPageSize || 10;
                        var tot = self.ordersTotal;
                        var tp = tot <= 0 ? 0 : Math.ceil(tot / sz);
                        if (tp > 0 && self.ordersPage > tp) {
                            self.ordersPage = tp;
                            return self.fetchOrders();
                        }
                    })
                    .catch(function() {
                        if (mySeq !== self.ordersFetchSeq) return;
                        self.ordersError = true;
                        self.ordersItems = [];
                        self.ordersTotal = 0;
                    })
                    .finally(function() {
                        if (mySeq === self.ordersFetchSeq) {
                            self.ordersLoading = false;
                        }
                    });
            },
            /** Есть сумма в ноге «Получаю» (counter_leg) — режим «Выставлен счет». */
            orderHasReceiveAmount: function(req) {
                var cl = req && req.counter_leg;
                var recvAmt = '';
                if (cl && cl.amount != null && cl.amount !== undefined) {
                    recvAmt = String(cl.amount).trim();
                }
                return recvAmt.length > 0;
            },
            /**
             * Выставлен счет: суммы обеих ног + коды.
             * Запрос условий: сумма отдачи + направление (получение без суммы).
             */
            orderAmountsLine: function(req) {
                if (!req) return '';
                var pl = req.primary_leg;
                var cl = req.counter_leg;
                var gc = pl && pl.code ? String(pl.code).trim().toUpperCase() : '';
                var rc = cl && cl.code ? String(cl.code).trim().toUpperCase() : '';
                var gaRaw = pl && pl.amount != null ? String(pl.amount).trim() : '';
                var raRaw = cl && cl.amount != null ? String(cl.amount).trim() : '';
                var ga = gaRaw ? formatAmountForLocale(gaRaw) : '';
                var ra = raRaw ? formatAmountForLocale(raRaw) : '';
                var arrow = ' → ';
                if (this.orderHasReceiveAmount(req)) {
                    var leftInv = ga ? ga + ' ' + gc : (gc || '—');
                    var rightInv = ra ? ra + ' ' + rc : (rc || '—');
                    return leftInv + arrow + rightInv;
                }
                var leftTerms = ga ? ga + ' ' + gc : (gc || '—');
                var rightTerms = rc || '—';
                return leftTerms + arrow + rightTerms;
            },
            /** Оставшееся время до expires_at; тикает раз в секунду через countdownTick. */
            formatExpiryCountdown: function(order) {
                var _tick = this.countdownTick;
                void _tick;
                if (!order) return '';
                if (!order.expires_at) return t('main.simple.request_expires_never');
                var end = new Date(order.expires_at).getTime();
                if (isNaN(end)) return '';
                var now = Date.now();
                var ms = end - now;
                if (ms <= 0) return t('main.simple.request_expired');
                var sec = Math.floor(ms / 1000);
                var days = Math.floor(sec / 86400);
                var h = Math.floor((sec % 86400) / 3600);
                var m = Math.floor((sec % 3600) / 60);
                var s = sec % 60;
                var hh = h < 10 ? '0' + h : String(h);
                var mm = m < 10 ? '0' + m : String(m);
                var ss = s < 10 ? '0' + s : String(s);
                if (days >= 1) {
                    return t('main.simple.countdown_days', {
                        days: String(days),
                        hh: hh,
                        mm: mm,
                        ss: ss
                    });
                }
                return hh + ':' + mm + ':' + ss;
            },
            orderListTitle: function(req) {
                var pk = req && req.pk != null ? String(req.pk) : '';
                var h = req && req.heading ? String(req.heading).trim() : '';
                var hasReceiveAmount = this.orderHasReceiveAmount(req);
                if (h) {
                    if (hasReceiveAmount) {
                        return t('main.simple.request_title_invoice_with_heading', {
                            pk: pk,
                            heading: h
                        });
                    }
                    return t('main.simple.request_title_terms_with_heading', {
                        pk: pk,
                        heading: h
                    });
                }
                if (hasReceiveAmount) {
                    return t('main.simple.request_title_invoice', { pk: pk });
                }
                return t('main.simple.request_title_terms', { pk: pk });
            },
            onGiveCodeSelectChange: function() {
                this.giveAmountFocus = false;
                this.giveAmount = '';
            },
            /** Снимает нецифровой ввод и принудительно чистит DOM (иначе при giveAmount === '' Vue не обновляет поле). */
            syncAmountInputDom: function(e, field) {
                var el = e.target;
                var v = sanitizeDecimalAmountInput(el.value);
                this[field] = v;
                if (el.value !== v) el.value = v;
            },
            onAmountFieldKeydown: function(e) {
                if (e.isComposing) return;
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                var k = e.key;
                if (k === 'Backspace' || k === 'Delete' || k === 'Tab' || k === 'Escape') return;
                if (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === 'ArrowDown' || k === 'Home' || k === 'End') return;
                if (k === 'Enter') return;
                if (k.length === 1) {
                    if (k >= '0' && k <= '9') return;
                    if (k === '.' || k === ',') return;
                    e.preventDefault();
                }
            },
            onGiveAmountInput: function(e) {
                this.syncAmountInputDom(e, 'giveAmount');
            },
            onGiveAmountFocus: function() {
                this.giveAmountFocus = true;
            },
            onGiveAmountBlur: function() {
                this.giveAmountFocus = false;
                this.giveAmount = normalizeAmountTwoDecimals(this.giveAmount);
            },
            onReceiveAmountInput: function(e) {
                this.syncAmountInputDom(e, 'receiveAmount');
            },
            onReceiveAmountFocus: function() {
                this.receiveAmountFocus = true;
            },
            onReceiveAmountBlur: function() {
                this.receiveAmountFocus = false;
                this.receiveAmount = normalizeAmountTwoDecimals(this.receiveAmount);
            },
            openCreateModal: function() {
                var self = this;
                self.createError = '';
                self.giveCode = '';
                self.giveAmount = '';
                self.giveAmountFocus = false;
                self.receiveCode = '';
                self.receiveAmount = '';
                self.receiveAmountFocus = false;
                self.receiveAmountMode = 'negotiable';
                self.createHeading = '';
                self.createLifetime = '72h';
                self.showCreateModal = true;
                if (self._uiPrefsPayloadCache) {
                    self.applySimpleCreatePrefsFromPayload(self._uiPrefsPayloadCache);
                }
                self.fetchSimpleCreateUiPrefs().then(function(payload) {
                    if (!self.showCreateModal) return;
                    if (payload && typeof payload === 'object') {
                        self._uiPrefsPayloadCache = Object.assign({}, self._uiPrefsPayloadCache || {}, payload);
                    }
                    self.applySimpleCreatePrefsFromPayload(self._uiPrefsPayloadCache || {});
                });
            },
            closeCreateModal: function() {
                if (this.createSubmitting) return;
                this.giveAmountFocus = false;
                this.receiveAmountFocus = false;
                this.showCreateModal = false;
            },
            openDeactivateModal: function(req) {
                if (!req || req.deactivated_at) return;
                this.deactivateTargetPk = req.pk;
                this.deactivateConfirm = '';
                this.deactivateError = '';
                this.showDeactivateModal = true;
            },
            closeDeactivateModal: function() {
                if (this.deactivateSubmitting) return;
                this.showDeactivateModal = false;
                this.deactivateTargetPk = null;
                this.deactivateConfirm = '';
                this.deactivateError = '';
            },
            submitDeactivate: function() {
                var self = this;
                if (self.deactivateSubmitDisabled) return;
                var pk = self.deactivateTargetPk;
                var confirm = String(self.deactivateConfirm || '').trim();
                self.deactivateSubmitting = true;
                self.deactivateError = '';
                var tok = getToken();
                var headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
                if (tok) headers.Authorization = 'Bearer ' + tok;
                fetch(
                    self.simpleV1Prefix() + 'payment-requests/' + encodeURIComponent(String(pk)) + '/deactivate',
                    {
                        method: 'POST',
                        headers: headers,
                        credentials: 'same-origin',
                        body: JSON.stringify({ confirm_pk: confirm })
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { status: r.status, data: data };
                        });
                    })
                    .then(function(res) {
                        if (res.status === 200 && res.data && res.data.payment_request) {
                            var updated = res.data.payment_request;
                            var items = self.ordersItems.slice();
                            for (var i = 0; i < items.length; i++) {
                                if (items[i].pk === updated.pk) {
                                    items[i] = updated;
                                    break;
                                }
                            }
                            self.ordersItems = items;
                            self.showDeactivateModal = false;
                            self.deactivateTargetPk = null;
                            self.deactivateConfirm = '';
                            return;
                        }
                        var detail = res.data && res.data.detail;
                        var msg = '';
                        if (typeof detail === 'string') {
                            msg = detail;
                        } else if (Array.isArray(detail) && detail.length && detail[0].msg) {
                            msg = detail[0].msg;
                        }
                        self.deactivateError = msg || t('main.simple.deactivate_error_generic');
                    })
                    .catch(function() {
                        self.deactivateError = t('main.simple.deactivate_error_generic');
                    })
                    .finally(function() {
                        self.deactivateSubmitting = false;
                    });
            },
            simpleUiPrefsUrl: function() {
                var space = (this.activeSpace || '').trim();
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/ui-prefs';
            },
            fetchSimpleCreateUiPrefs: function() {
                var url = this.simpleUiPrefsUrl();
                if (!url) return Promise.resolve(null);
                var tok = getToken();
                var headers = { Accept: 'application/json' };
                if (tok) headers.Authorization = 'Bearer ' + tok;
                return fetch(url, { method: 'GET', headers: headers, credentials: 'same-origin' })
                    .then(function(r) {
                        if (!r.ok) return null;
                        return r.json();
                    })
                    .then(function(data) {
                        if (!data || typeof data !== 'object') return null;
                        return data.payload && typeof data.payload === 'object' ? data.payload : {};
                    })
                    .catch(function() {
                        return null;
                    });
            },
            _assetCodeInUnified: function(code) {
                var c = (code || '').trim().toUpperCase();
                if (!c) return false;
                var opts = this.unifiedAssetOptions;
                for (var i = 0; i < opts.length; i++) {
                    if (opts[i].code === c) return true;
                }
                return false;
            },
            _receiveCodeAllowedForGive: function(recvCode) {
                var rc = (recvCode || '').trim().toUpperCase();
                if (!rc) return false;
                var ro = this.receiveOptions;
                for (var j = 0; j < ro.length; j++) {
                    if (ro[j].code === rc) return true;
                }
                return false;
            },
            applySimpleCreatePrefsFromPayload: function(payload) {
                var p = payload && typeof payload === 'object' ? payload : {};
                var sc = p.simple_create;
                if (!sc || typeof sc !== 'object') return;
                var lt = (sc.lifetime != null ? String(sc.lifetime) : '').trim();
                if (lt === '24h' || lt === '48h' || lt === '72h' || lt === 'forever') {
                    this.createLifetime = lt;
                }
                var give = (sc.give_code || '').trim().toUpperCase();
                var recv = (sc.receive_code || '').trim().toUpperCase();
                var mode = sc.receive_amount_mode === 'fixed' ? 'fixed' : 'negotiable';
                if (!this._assetCodeInUnified(give)) return;
                this.giveCode = give;
                if (mode === 'fixed') {
                    this.setReceiveMode('fixed');
                } else {
                    this.setReceiveMode('negotiable');
                }
                var self = this;
                this.$nextTick(function() {
                    if (self._receiveCodeAllowedForGive(recv)) {
                        self.receiveCode = recv;
                    }
                });
            },
            persistSimpleCreateUiPrefs: function() {
                var url = this.simpleUiPrefsUrl();
                if (!url) return;
                var tok = getToken();
                if (!tok) return;
                var gc = (this.giveCode || '').trim().toUpperCase();
                var rc = (this.receiveCode || '').trim().toUpperCase();
                var mode = this.receiveAmountMode === 'fixed' ? 'fixed' : 'negotiable';
                var body = {
                    simple_create: {
                        give_code: gc || null,
                        receive_code: rc || null,
                        receive_amount_mode: mode,
                        lifetime: this.createLifetime || '72h'
                    }
                };
                var self = this;
                fetch(url, {
                    method: 'PATCH',
                    headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                        Authorization: 'Bearer ' + tok
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        return r.ok ? r.json() : null;
                    })
                    .then(function(data) {
                        if (data && data.payload && typeof data.payload === 'object') {
                            self._uiPrefsPayloadCache = Object.assign({}, self._uiPrefsPayloadCache || {}, data.payload);
                        }
                    })
                    .catch(function() { /* ignore */ });
            },
            assetMeta: function(code) {
                var c = (code || '').trim().toUpperCase();
                if (!c) return null;
                var opts = this.unifiedAssetOptions;
                for (var i = 0; i < opts.length; i++) {
                    if (opts[i].code === c) return opts[i];
                }
                return null;
            },
            setReceiveMode: function(mode) {
                this.receiveAmountMode = mode;
                if (mode === 'negotiable') {
                    this.receiveAmountFocus = false;
                    this.receiveAmount = '';
                }
            },
            onReceiveFixedChange: function(ev) {
                if (ev.target.checked) {
                    this.setReceiveMode('fixed');
                } else {
                    this.setReceiveMode('negotiable');
                }
            },
            onReceiveNegotiableChange: function(ev) {
                if (ev.target.checked) {
                    this.setReceiveMode('negotiable');
                } else {
                    this.setReceiveMode('fixed');
                }
            },
            submitCreateApplication: function() {
                var self = this;
                if (self.createSubmitting || self.createSubmitDisabled) return;
                self.createError = '';
                self.giveAmount = normalizeAmountTwoDecimals(self.giveAmount);
                self.receiveAmount = normalizeAmountTwoDecimals(self.receiveAmount);
                var giveMeta = self.assetMeta(self.giveCode);
                var recvMeta = self.assetMeta(self.receiveCode);
                if (!giveMeta || !recvMeta) {
                    self.createError = t('main.simple.create_invalid_assets');
                    return;
                }
                if (giveMeta.kind === recvMeta.kind) {
                    self.createError = t('main.simple.create_invalid_same_kind');
                    return;
                }
                var direction = (giveMeta.kind === 'fiat' && recvMeta.kind === 'stable')
                    ? 'fiat_to_stable'
                    : 'stable_to_fiat';
                var leg1 = {
                    asset_type: giveMeta.kind === 'stable' ? 'stable' : 'fiat',
                    code: giveMeta.code,
                    amount: (self.giveAmount || '').trim(),
                    side: 'give'
                };
                var cAmt = (self.receiveAmount || '').trim();
                var leg2 = {
                    asset_type: recvMeta.kind === 'stable' ? 'stable' : 'fiat',
                    code: recvMeta.code,
                    amount: self.receiveAmountMode === 'fixed' ? (cAmt || null) : null,
                    side: 'receive',
                    amount_discussed: self.receiveAmountMode === 'negotiable'
                };
                var body = {
                    direction: direction,
                    primary_leg: leg1,
                    counter_leg: leg2,
                    lifetime: self.createLifetime || '72h'
                };
                var gh = (self.createHeading || '').trim();
                if (gh) body.heading = gh;
                self.createSubmitting = true;
                var tok = getToken();
                var headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
                if (tok) headers.Authorization = 'Bearer ' + tok;
                fetch(self.simpleV1Prefix() + 'payment-requests', {
                    method: 'POST',
                    headers: headers,
                    credentials: 'same-origin',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        return r.json().then(function(j) { return { ok: r.ok, status: r.status, j: j }; });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var det = res.j && res.j.detail;
                            if (Array.isArray(det)) {
                                det = det.map(function(x) { return x && x.msg ? x.msg : JSON.stringify(x); }).join('; ');
                            }
                            if (det == null && res.j && res.j.message) det = res.j.message;
                            self.createError = det ? String(det) : t('main.simple.create_error');
                            return;
                        }
                        self.persistSimpleCreateUiPrefs();
                        self.showCreateModal = false;
                        self.ordersPage = 1;
                        self.fetchOrders();
                    })
                    .catch(function() {
                        self.createError = t('main.simple.create_error');
                    })
                    .finally(function() {
                        self.createSubmitting = false;
                    });
            },
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
                    self.maybeFetchOrders();
                    self.maybeFetchResolve();
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
  <div v-if="showCreateModal" class="simple-create__overlay" @click.self="closeCreateModal">\
    <div class="simple-create__modal" role="dialog" aria-modal="true" @click.stop>\
      <h2 class="simple-create__title">{{ t(\'main.simple.create_modal_title\') }}</h2>\
      <div class="simple-create__grid">\
        <div class="simple-create__col">\
          <div class="simple-create__col-title">{{ t(\'main.simple.give_label\') }}</div>\
          <label class="simple-create__label">{{ t(\'main.simple.asset_label\') }}</label>\
          <select v-model="giveCode" class="simple-create__select" @change="onGiveCodeSelectChange">\
            <option value="">{{ t(\'main.simple.give_select_placeholder\') }}</option>\
            <option v-for="o in unifiedAssetOptions" :key="\'g-\' + o.code" :value="o.code">\
              {{ o.code }} — {{ o.kind === \'stable\' ? t(\'main.simple.asset_kind_crypto\') : t(\'main.simple.asset_kind_fiat\') }}\
            </option>\
          </select>\
          <label class="simple-create__label">{{ t(\'main.simple.amount_label\') }}</label>\
          <input type="text" class="simple-create__input" :value="giveAmountInputDisplay" inputmode="decimal" autocomplete="off" :disabled="giveAssetEmpty" :placeholder="t(\'main.simple.amount_ph\')" @focus="onGiveAmountFocus" @blur="onGiveAmountBlur" @keydown="onAmountFieldKeydown" @input="onGiveAmountInput" @compositionend="onGiveAmountInput" />\
        </div>\
        <div class="simple-create__col" :class="{ \'simple-create__col--muted\': receiveLocked }" :aria-disabled="receiveLocked ? \'true\' : \'false\'">\
          <div class="simple-create__col-title">{{ t(\'main.simple.receive_label\') }}</div>\
          <label class="simple-create__label">{{ t(\'main.simple.asset_label\') }}</label>\
          <select v-model="receiveCode" class="simple-create__select" :disabled="receiveLocked">\
            <option value="">{{ t(\'main.simple.receive_select_placeholder\') }}</option>\
            <option v-for="o in receiveOptions" :key="\'r-\' + o.code" :value="o.code">\
              {{ o.code }} — {{ o.kind === \'stable\' ? t(\'main.simple.asset_kind_crypto\') : t(\'main.simple.asset_kind_fiat\') }}\
            </option>\
          </select>\
          <div class="simple-create__row simple-create__row--checks">\
            <label class="simple-create__check">\
              <input type="checkbox" :checked="receiveAmountMode === \'negotiable\'" @change="onReceiveNegotiableChange" :disabled="receiveLocked" />\
              {{ t(\'main.simple.receive_negotiable_rate\') }}\
            </label>\
            <label class="simple-create__check">\
              <input type="checkbox" :checked="receiveAmountMode === \'fixed\'" @change="onReceiveFixedChange" :disabled="receiveLocked" />\
              {{ t(\'main.simple.receive_fixed_rate\') }}\
            </label>\
          </div>\
          <template v-if="receiveAmountMode === \'fixed\'">\
            <label class="simple-create__label">{{ t(\'main.simple.amount_label\') }}</label>\
            <input type="text" class="simple-create__input" :value="receiveAmountInputDisplay" inputmode="decimal" autocomplete="off" :disabled="receiveLocked" :placeholder="t(\'main.simple.amount_optional_ph\')" @focus="onReceiveAmountFocus" @blur="onReceiveAmountBlur" @keydown="onAmountFieldKeydown" @input="onReceiveAmountInput" @compositionend="onReceiveAmountInput" />\
          </template>\
        </div>\
      </div>\
      <div class="simple-create__extra">\
        <label class="simple-create__label">{{ t(\'main.simple.heading_label\') }}</label>\
        <input type="text" class="simple-create__input" v-model.trim="createHeading" maxlength="256" :placeholder="t(\'main.simple.heading_placeholder\')" autocomplete="off" />\
        <label class="simple-create__label" for="simple-create-lifetime">{{ t(\'main.simple.lifetime_label\') }}</label>\
        <select id="simple-create-lifetime" v-model="createLifetime" class="simple-create__select simple-create__select--lifetime" @change="persistSimpleCreateUiPrefs">\
          <option value="24h">{{ t(\'main.simple.lifetime_24h\') }}</option>\
          <option value="48h">{{ t(\'main.simple.lifetime_48h\') }}</option>\
          <option value="72h">{{ t(\'main.simple.lifetime_72h\') }}</option>\
          <option value="forever">{{ t(\'main.simple.lifetime_forever\') }}</option>\
        </select>\
      </div>\
      <div v-if="createError" class="simple-create__err">{{ createError }}</div>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeCreateModal" :disabled="createSubmitting">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="submitCreateApplication" :disabled="createSubmitDisabled">\
          <span v-if="createSubmitting" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.submit_create\') }}\
        </button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showDeactivateModal" class="simple-deactivate__overlay" @click.self="closeDeactivateModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" @click.stop>\
      <h2 class="simple-create__title">{{ t(\'main.simple.deactivate_modal_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.deactivate_modal_hint\', { pk: deactivateTargetPk }) }}</p>\
      <label class="simple-create__label" for="simple-deactivate-confirm">{{ t(\'main.simple.deactivate_modal_label\') }}</label>\
      <input id="simple-deactivate-confirm" type="text" class="simple-create__input" v-model.trim="deactivateConfirm" autocomplete="off" inputmode="numeric" :placeholder="t(\'main.simple.deactivate_modal_placeholder\')" />\
      <div v-if="deactivateError" class="simple-create__err">{{ deactivateError }}</div>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeDeactivateModal" :disabled="deactivateSubmitting">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="submitDeactivate" :disabled="deactivateSubmitDisabled">\
          <span v-if="deactivateSubmitting" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.deactivate_confirm\') }}\
        </button>\
      </div>\
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
    <div v-if="!isDealView" class="simple-page__list-root">\
      <div class="simple-page__main-scroll simple-page__main-scroll--list">\
        <div v-if="authReady && !showAuthModal" class="simple-page__list-inner">\
        <p class="simple-page__list-intro">{{ t(\'main.simple.deals_list_intro\') }}</p>\
        <div class="simple-page__orders-toolbar">\
          <button type="button" class="simple-page__create-deal-btn" @click="openCreateModal">{{ t(\'main.simple.create_deal_btn\') }}</button>\
          <input type="search" class="simple-page__orders-search" v-model="ordersSearch" @input="onOrdersSearchInput" :placeholder="t(\'main.simple.deals_search_placeholder\')" autocomplete="off" />\
        </div>\
        <div v-if="ordersError" class="simple-page__list-msg simple-page__list-msg--err">{{ t(\'main.simple.deals_error\') }}</div>\
        <div v-else class="simple-page__orders-stage" :aria-busy="ordersLoading ? \'true\' : \'false\'">\
          <div v-if="ordersLoading" class="simple-page__orders-overlay" role="status">\
            <div class="simple-page__orders-spinner-el" aria-hidden="true"></div>\
            <span class="simple-page__sr-only">{{ t(\'main.simple.deals_loading_aria\') }}</span>\
          </div>\
          <div v-if="!ordersLoading && !ordersItems.length" class="simple-page__list-msg">{{ t(\'main.simple.deals_empty\') }}</div>\
          <div v-if="!ordersLoading && ordersItems.length" class="simple-page__order-list" role="list">\
            <div v-for="req in ordersItems" :key="req.uid" class="simple-page__order-card" :class="{ \'simple-page__order-card--deactivated\': req.deactivated_at }" role="listitem">\
              <a class="simple-page__order-card-hit" :href="simpleHtmlBase() + \'/deal/\' + encodeURIComponent(String(req.public_ref || req.uid))">\
                <div class="simple-page__order-card-main">\
                  <div class="simple-page__order-titles">\
                    <span class="simple-page__order-list-title">{{ orderListTitle(req) }}</span>\
                  </div>\
                </div>\
                <div class="simple-page__order-card-sub">\
                  <span class="simple-page__order-amounts">{{ orderAmountsLine(req) }}</span>\
                  <div class="simple-page__order-sub-right">\
                    <div class="simple-page__order-countdown-row" :class="{ \'simple-page__order-countdown-row--muted\': !req.expires_at }">\
                      <svg class="simple-page__ico-clock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                        <circle cx="12" cy="12" r="10" stroke-linecap="round"/>\
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l4 2"/>\
                      </svg>\
                      <span class="simple-page__order-countdown">{{ formatExpiryCountdown(req) }}</span>\
                    </div>\
                    <span class="simple-page__order-cta">{{ t(\'main.simple.deals_open\') }}</span>\
                  </div>\
                </div>\
              </a>\
              <div class="simple-page__order-card-actions">\
                <button v-if="!req.deactivated_at" type="button" class="simple-page__order-deactivate-btn" @click.stop="openDeactivateModal(req)">{{ t(\'main.simple.deactivate_btn\') }}</button>\
                <span v-else class="simple-page__order-deactivated-badge">{{ t(\'main.simple.deactivated_badge\') }}</span>\
              </div>\
            </div>\
          </div>\
        </div>\
        <div v-if="!ordersError && ordersTotalPages > 1" class="simple-page__orders-pagination">\
          <button type="button" class="simple-page__orders-page-btn" :disabled="ordersPrevDisabled" @click="ordersGoPrev" :aria-label="t(\'main.simple.orders_pagination_prev\')">{{ t(\'main.simple.orders_pagination_prev\') }}</button>\
          <span class="simple-page__orders-page-label">{{ ordersPaginationLabel }}</span>\
          <button type="button" class="simple-page__orders-page-btn" :disabled="ordersNextDisabled" @click="ordersGoNext" :aria-label="t(\'main.simple.orders_pagination_next\')">{{ t(\'main.simple.orders_pagination_next\') }}</button>\
        </div>\
        </div>\
        <div v-else-if="!authReady" class="simple-page__list-msg">{{ t(\'main.simple.orders_loading\') }}</div>\
      </div>\
    </div>\
    <div v-else class="simple-page__body">\
      <aside class="simple-page__aside">\
        <div class="simple-page__aside-scroll">\
          <div class="simple-page__aside-label">{{ t(\'main.simple.sidebar_title\') }}</div>\
          <div class="simple-page__orders-block">\
            <a v-if="isDealView && ordersListHref" :href="ordersListHref" class="simple-page__orders-cta">\
              <svg class="simple-page__svg--sm" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>\
              {{ t(\'main.simple.orders_list_cta\') }}\
            </a>\
            <span v-else class="simple-page__orders-cta simple-page__orders-cta--muted" role="note">{{ t(\'main.simple.orders_list_hint\') }}</span>\
          </div>\
          <details class="simple-page__stages-mobile">\
            <summary class="simple-page__stages-mobile-summary" :aria-label="t(\'main.simple.stages_expand_aria\')">\
              <span class="simple-page__stages-mobile-summary-inner">\
                <span v-if="activeNavStep" class="simple-page__stages-mobile-summary-title">{{ t(activeNavStep.titleKey) }}</span>\
                <span v-if="activeNavStep" class="simple-page__stages-mobile-summary-sub">{{ mobileSummarySub() }}</span>\
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
                  <div v-if="step.status === \'active\'" class="simple-page__stages-mobile-row-sub">{{ navStepActiveSub(step) }}</div>\
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
                <div v-if="step.status === \'active\'" class="simple-page__nav-sub">{{ navStepActiveSub(step) }}</div>\
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
          <div v-if="dealUid && resolveLoading" class="simple-page__orders-overlay simple-page__resolve-loading" role="status">\
            <div class="simple-page__orders-spinner-el" aria-hidden="true"></div>\
            <span>{{ t(\'main.simple.resolve_loading\') }}</span>\
          </div>\
          <div v-else-if="dealUid && resolveError" class="simple-page__list-msg simple-page__list-msg--err">{{ resolveErrorMsg || t(\'main.simple.resolve_error\') }}</div>\
          <template v-else-if="dealViewShowResolved && resolveKind === \'payment_request_only\'">\
            <div class="simple-page__pr-view" :class="{ \'simple-page__pr-view--deactivated\': dealPrDeactivated }">\
            <div v-if="dealPrDeactivated" class="simple-page__pr-deactivated-banner" role="status">{{ t(\'main.simple.pr_deactivated_banner\') }}</div>\
            <div class="simple-page__stat-rail" role="region" :aria-label="t(\'main.simple.stat_carousel_aria\')">\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_amount_short\') }}</div>\
              <div class="simple-page__stat-value">{{ dealViewStatFiatAmount() }}</div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_pledge_short\') }}</div>\
              <div class="simple-page__stat-value">{{ dealViewStatStableAmount() }}</div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail simple-page__stat-card--rate-axis">\
              <div class="simple-page__stat-label">{{ dealViewStatRateLabel() }}</div>\
              <div class="simple-page__stat-value">{{ dealViewStatRate() }}</div>\
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
              <div class="simple-page__stat-value">{{ dealViewStatFiatAmount() }}</div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_pledge\') }}</div>\
              <div class="simple-page__stat-value">{{ dealViewStatStableAmount() }}</div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rate-axis">\
              <div class="simple-page__stat-label">{{ dealViewStatRateLabel() }}</div>\
              <div class="simple-page__stat-value">{{ dealViewStatRate() }}</div>\
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
                <div class="simple-page__flow-title-row">\
                  <span class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_offer_title\') }}</span>\
                  <span v-if="resolvePaymentRequest && resolvePaymentRequest.expires_at && !resolvePaymentRequest.deactivated_at" class="simple-page__flow-deadline" role="status" :aria-label="t(\'main.simple.deal_flow_deadline_aria\')">\
                    <svg class="simple-page__ico-clock simple-page__ico-clock--flow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                      <circle cx="12" cy="12" r="10" stroke-linecap="round"/>\
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l4 2"/>\
                    </svg>\
                    <span class="simple-page__flow-deadline-text">{{ formatExpiryCountdown(resolvePaymentRequest) }}</span>\
                  </span>\
                </div>\
                <div class="simple-page__flow-mono">{{ orderAmountsLine(resolvePaymentRequest) }}</div>\
              </div>\
              <div class="simple-page__flow-status" :class="{ \'simple-page__flow-status--deactivated\': dealPrDeactivated }">{{ dealPrDeactivated ? t(\'main.simple.request_status_deactivated\') : t(\'main.simple.request_status_terms\') }}</div>\
            </div>\
            <div class="simple-page__lockbox" :class="{ \'simple-page__lockbox--deactivated\': dealPrDeactivated }">\
              <div class="simple-page__lockbox-tag">{{ t(\'main.simple.lockbox_title\') }}</div>\
              <div class="simple-page__lockbox-head">\
                <svg class="simple-page__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                <span class="simple-page__lockbox-brand">{{ t(\'main.simple.lockbox_subtitle\') }}</span>\
              </div>\
              <div class="simple-page__flow-mono" style="margin-bottom:1rem">{{ dealPrDeactivated ? t(\'main.simple.lockbox_pending_help_deactivated\') : t(\'main.simple.lockbox_pending_help\') }}</div>\
              <div class="simple-page__lockbox-inner">\
                <svg class="simple-page__svg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>\
                {{ dealLockboxHintFromPr(resolvePaymentRequest) || t(\'main.simple.lockbox_inner_placeholder\') }}\
              </div>\
              <div v-if="!dealPrDeactivated" class="simple-page__lockbox-pending-foot" role="status">\
                <div class="simple-page__lockbox-spinner" aria-hidden="true"></div>\
                <p class="simple-page__lockbox-pending-text">{{ t(\'main.simple.lockbox_terms_pending_detail\') }}</p>\
              </div>\
              <div v-else class="simple-page__lockbox-deactivated-foot" role="status">\
                <p class="simple-page__lockbox-deactivated-text">{{ t(\'main.simple.pr_deactivated_lockbox_note\') }}</p>\
              </div>\
            </div>\
            <div class="simple-page__recipient-wrap">\
              <div class="simple-page__flow-row">\
                <div class="simple-page__flow-icon simple-page__flow-icon--muted">\
                  <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
                </div>\
                <div class="simple-page__flow-body">\
                  <div class="simple-page__flow-title">{{ t(\'main.simple.counter_leg\') }}</div>\
                  <div class="simple-page__flow-mono">{{ dealViewStatReceive() }}</div>\
                </div>\
              </div>\
            </div>\
          </div>\
            </div>\
          </template>\
          <template v-else-if="dealViewShowResolved && resolveKind === \'deal_only\'">\
          <div class="simple-page__stat-rail" role="region" :aria-label="t(\'main.simple.stat_carousel_aria\')">\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.stat_amount_short\') }}</div>\
              <div class="simple-page__stat-value">{{ dealViewDealAmountLine() }}</div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.deal_stat_status\') }}</div>\
              <div class="simple-page__stat-value">{{ resolveDeal.status }}</div>\
            </div>\
            <div class="simple-page__stat-card simple-page__stat-card--rail">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.heading_label\') }}</div>\
              <div class="simple-page__stat-value simple-page__stat-value--clamp">{{ dealDealLabelPreview() }}</div>\
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
              <div class="simple-page__stat-value">{{ dealViewDealAmountLine() }}</div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.deal_stat_status\') }}</div>\
              <div class="simple-page__stat-value">{{ resolveDeal.status }}</div>\
            </div>\
            <div class="simple-page__stat-card">\
              <div class="simple-page__stat-label">{{ t(\'main.simple.heading_label\') }}</div>\
              <div class="simple-page__stat-value">{{ dealDealLabelPreview() }}</div>\
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
                <div class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_deal_title\') }}</div>\
                <div class="simple-page__flow-mono">{{ dealDealLabelPreview() }} · {{ resolveDeal.uid }}</div>\
              </div>\
            </div>\
          </div>\
          </template>\
          <template v-else-if="orderId && !dealUid">\
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
          </template>\
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
  <div v-if="isDealView" class="simple-page__fab" role="status">\
    <svg class="simple-page__svg" style="color:var(--simple-primary);flex-shrink:0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>\
    <span>{{ t(\'main.simple.protected_badge\') }}</span>\
  </div>\
</div>'
    });
})();
