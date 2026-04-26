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

    /** Процент посредника перепродажи: 0.1–100 для API (строка с точкой). */
    function parseIntermediaryPercentForResell(raw) {
        var s = sanitizeDecimalAmountInput(raw);
        if (!s) return { ok: false, code: 'empty' };
        var n = parseFloat(s);
        if (!isFinite(n)) return { ok: false, code: 'invalid' };
        if (n < 0.1 || n > 100) return { ok: false, code: 'range' };
        return { ok: true, apiValue: s };
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

    /**
     * Слот посредника для viewerDid (не system/counterparty).
     * Несколько посредников — у каждого свой ключ в commissioners; на один did один слот.
     */
    function viewerIntermediarySlot(pr, viewerDid) {
        if (!pr || !pr.commissioners || typeof pr.commissioners !== 'object') return null;
        var v = (viewerDid || '').trim();
        if (!v) return null;
        var keys = Object.keys(pr.commissioners);
        for (var i = 0; i < keys.length; i++) {
            var slot = pr.commissioners[keys[i]];
            if (!slot || typeof slot !== 'object') continue;
            var role = String(slot.role || '').trim().toLowerCase();
            if (role !== 'intermediary') continue;
            if ((slot.did || '').trim() !== v) continue;
            return slot;
        }
        return null;
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
     * Сумма комиссий по залогу (stable), которые должны входить в escrow lock.
     * Возвращает total borrow_amount по слотам commissioners без раскрытия структуры.
     */
    function prStableEscrowFeesTotal(pr) {
        if (!pr || !pr.commissioners || typeof pr.commissioners !== 'object') return 0;
        var total = 0;
        var keys = Object.keys(pr.commissioners || {});
        for (var i = 0; i < keys.length; i++) {
            var slot = pr.commissioners[keys[i]];
            if (!slot || typeof slot !== 'object') continue;
            var role = String(slot.role || '').trim().toLowerCase();
            if (role !== 'system' && role !== 'intermediary') continue;
            var feeRaw = slot.borrow_amount != null ? String(slot.borrow_amount).trim() : '';
            if (!feeRaw) continue;
            var fa = parseFloat(sanitizeDecimalAmountInput(feeRaw));
            if (!isFinite(fa)) continue;
            total += fa;
        }
        return total;
    }

    /**
     * Комиссии предыдущей цепочки по залогу (stable) для посредника viewerDid:
     * сумма borrow_amount всех слотов, кроме borrow_amount слота данного посредника.
     */
    function prStableEscrowFeesBeforeViewer(pr, viewerDid) {
        if (!pr) return 0;
        var total = prStableEscrowFeesTotal(pr);
        if (!total || !isFinite(total)) return 0;
        var slot = viewerIntermediarySlot(pr, viewerDid);
        if (!slot) return total;
        var feeRaw = slot.borrow_amount != null ? String(slot.borrow_amount).trim() : '';
        if (!feeRaw) return total;
        var fa = parseFloat(sanitizeDecimalAmountInput(feeRaw));
        if (!isFinite(fa)) return total;
        var before = total - fa;
        return before > 0 ? before : 0;
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
                theme: 'dark',
                authReady: false,
                showAuthModal: false,
                authError: '',
                activeSpace: '',
                /** Свой nickname (WalletUser владельца кошелька); из GET /v1/auth/tron/me — для скрытия смены ника в чужом space */
                authOwnSpace: '',
                /** Фирменное название (Label) из профиля; GET /v1/profile/tron/me */
                spaceProfileLabel: '',
                spaceLabelEdit: '',
                /** Никнейм спейса (WalletUser), как в профиле; GET/PUT /v1/profile/tron/me */
                spaceProfileNickname: '',
                spaceNicknameEdit: '',
                showSpaceNicknameModal: false,
                spaceLabelSaving: false,
                spaceLabelError: '',
                /** Адрес сессии (auth) и primary спейса — из GET /v1/profile/tron/me для предупреждения перед accept/confirm */
                profileWalletAddress: '',
                profilePrimaryWalletAddress: '',
                profilePrimaryWalletBlockchain: '',
                showWalletMismatchModal: false,
                _walletMismatchPending: null,
                /** Роль viewer на стадии согласования условий: '' (не выбрано) | counterparty | intermediary */
                viewerRoleChoice: '',
                roleSubmitting: false,
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
                arbiterDisplayName: (el.getAttribute('data-simple-arbiter-display-name') || '').trim(),
                resolveLoading: false,
                resolveError: false,
                resolveErrorMsg: '',
                resolveKind: null,
                resolvePaymentRequest: null,
                resolveDeal: null,
                resolveDealPaymentRequestPk: null,
                resolveDealPaymentRequestPublicRef: '',
                resolveDealPaymentRequestHeading: '',
                viewerDid: '',
                showResellCommissionModal: false,
                resellCommissionPercent: '0.5',
                resellModalError: '',
                resellSubmitting: false,
                resellBanner: null,
                handshakeBanner: null,
                copyLinkBanner: '',
                acceptSubmitting: false,
                withdrawAcceptSubmitting: false,
                ownerConfirmSubmitting: false,
                showAcceptAmountModal: false,
                acceptAmountInput: '',
                acceptModalError: '',
                showExpiredTermsModal: false,
                extendSubmitting: false,
                showExtendLifetimeModal: false,
                showPrLockedByOtherModal: false,
                extendTargetPk: null,
                extendApplyToResolve: false,
                extendLifetime: '72h',
                _termsFeedbackTimer: null,
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
            if (this._termsFeedbackTimer) {
                clearTimeout(this._termsFeedbackTimer);
                this._termsFeedbackTimer = null;
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
                                self.authOwnSpace = '';
                                self.showAuthModal = true;
                            });
                    }
                    self.activeSpace = target;
                    setSpace(target);
                    return self.fetchAuthOwnSpace();
                });
            }).catch(function() {
                self.showAuthModal = true;
            }).finally(function() {
                self.authReady = true;
                self.maybeFetchOrders();
                self.maybeFetchResolve();
                self.fetchSpaceProfileNickname();
            });
        },
        computed: {
            rootClass: function() {
                return {
                    'simple-page': true,
                    'simple-page--dark': this.theme === 'dark'
                };
            },
            /** Подпись в шапке до загрузки профиля берётся из activeSpace (ensure-space). */
            titlebarSpaceLabel: function() {
                var label = (this.spaceProfileLabel || '').trim();
                if (label) return label;
                var a = (this.spaceProfileNickname || '').trim();
                if (a) return a;
                return (this.activeSpace || '').trim();
            },
            /** Текущий space — свой (владелец WalletUser с этим nickname), иначе участие как суб и т.п. */
            simpleSpaceIsOwner: function() {
                var s = (this.activeSpace || '').trim();
                var o = (this.authOwnSpace || '').trim();
                return !!(s && o && s === o);
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
            },
            dealPrTermsPhase: function() {
                var pr = this.resolvePaymentRequest;
                return !!(
                    this.resolveKind === 'payment_request_only' &&
                    pr &&
                    !pr.deal_id &&
                    !pr.deactivated_at
                );
            },
            isPaymentRequestOwner: function() {
                var v = (this.viewerDid || '').trim();
                var pr = this.resolvePaymentRequest;
                var o = pr && (pr.owner_did || '').trim();
                return !!(v && o && v === o);
            },
            /** Текущий зритель — один из слотов-посредников (любой ключ кроме system/counterparty). */
            isCommissionerIntermediary: function() {
                var v = (this.viewerDid || '').trim();
                if (!v || this.isPaymentRequestOwner) return false;
                return !!viewerIntermediarySlot(this.resolvePaymentRequest, v);
            },
            /** Процент комиссии справа от подписи «Перепродать» для посредника (пусто — если не показываем). */
            commissionerResellButtonPctLabel: function() {
                var s = this.commissionerCommissionPercentLine();
                return s === '—' ? '' : s;
            },
            /** Текст FAB-бейджа «гарант сделки» с именем арбитра из сервера. */
            fabProtectedBadgeLabel: function() {
                var nick = (this.arbiterDisplayName || '').trim();
                if (!nick) return t('main.simple.protected_badge');
                return t('main.simple.protected_badge_arbiter', { nickname: nick });
            },
            resellModalSubmitDisabled: function() {
                return (
                    this.resellSubmitting ||
                    !(String(this.resellCommissionPercent || '').trim())
                );
            },
            /** Ползунок только 0.1–10 %; при большем числе в поле — позиция «10» без подмены текста. */
            resellSliderValue: function() {
                var clampS = function(n) {
                    return Math.min(10, Math.max(0.1, Math.round(n * 100) / 100));
                };
                var p = parseIntermediaryPercentForResell(this.resellCommissionPercent);
                if (p.ok) {
                    var n = parseFloat(p.apiValue);
                    return clampS(n > 10 ? 10 : n);
                }
                var s = sanitizeDecimalAmountInput(this.resellCommissionPercent);
                var n2 = parseFloat(s);
                if (!isFinite(n2) || !String(s).trim()) return 0.5;
                if (n2 < 0.1) return 0.1;
                if (n2 > 10) return 10;
                return clampS(n2);
            },
            counterLegDiscussed: function() {
                var pr = this.resolvePaymentRequest;
                if (!pr || !pr.counter_leg) return false;
                return !!pr.counter_leg.amount_discussed;
            },
            handshakeLockedByOther: function() {
                var pr = this.resolvePaymentRequest;
                return !!(pr && pr.handshake_locked_by_other);
            },
            showWithdrawAcceptButton: function() {
                var pr = this.resolvePaymentRequest;
                if (!this.dealPrTermsPhase || this.isPaymentRequestOwner || !pr) return false;
                var v = (this.viewerDid || '').trim();
                var acc = (pr.counterparty_accept_did || '').trim();
                return !!(pr.owner_confirm_pending && acc && v === acc);
            },
            /** True если viewer уже принял как контрагент и ждёт владельца (пока нельзя менять роль). */
            viewerAcceptancePending: function() {
                var pr = this.resolvePaymentRequest;
                if (!this.dealPrTermsPhase || !pr || this.isPaymentRequestOwner) return false;
                var v = (this.viewerDid || '').trim();
                var acc = (pr.counterparty_accept_did || '').trim();
                return !!(pr.owner_confirm_pending && acc && v && v === acc);
            },
            showAcceptTermsButton: function() {
                if (!this.dealPrTermsPhase || this.isPaymentRequestOwner || this.handshakeLockedByOther) return false;
                var pr = this.resolvePaymentRequest;
                if (!pr) return false;
                var v = (this.viewerDid || '').trim();
                var acc = (pr.counterparty_accept_did || '').trim();
                if (pr.owner_confirm_pending && acc && v === acc) return false;
                return true;
            },
            showOwnerConfirmBanner: function() {
                var pr = this.resolvePaymentRequest;
                return !!(
                    this.dealPrTermsPhase &&
                    this.isPaymentRequestOwner &&
                    pr &&
                    pr.owner_confirm_pending &&
                    !pr.deal_id
                );
            },
            /** Строка статуса справа в блоке «Условия по заявке» (рукопожатие / сделка). */
            dealPrFlowStatusLabel: function() {
                if (this.dealPrDeactivated) return t('main.simple.request_status_deactivated');
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) {
                    return t('main.simple.request_status_terms');
                }
                var pr = this.resolvePaymentRequest;
                if (pr.deal_id) return t('main.simple.request_status_deal_linked');
                if (pr.owner_confirm_pending) {
                    var v = (this.viewerDid || '').trim();
                    var owner = (pr.owner_did || '').trim();
                    var acc = (pr.counterparty_accept_did || '').trim();
                    if (v === owner) return t('main.simple.request_status_owner_confirm');
                    if (acc && v === acc) return t('main.simple.request_status_you_waiting_owner');
                    if (this.handshakeLockedByOther) return t('main.simple.request_status_locked_other');
                    return t('main.simple.request_status_negotiating');
                }
                return t('main.simple.request_status_terms');
            },
            /** True если заявка истекла по expires_at. */
            dealPrExpired: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) return false;
                var pr = this.resolvePaymentRequest;
                if (!pr || !pr.expires_at) return false;
                var ts = Date.parse(String(pr.expires_at));
                if (!isFinite(ts)) return false;
                return Date.now() > ts;
            },
            /** Только на стадии согласования условий: истекла и сделка ещё не создана. */
            dealPrExpiredDuringTerms: function() {
                return !!(this.dealPrTermsPhase && !this.dealPrDeactivated && this.dealPrExpired);
            },
            acceptModalSubmitDisabled: function() {
                return (
                    this.acceptSubmitting ||
                    !(String(this.acceptAmountInput || '').trim())
                );
            }
        },
        methods: {
            t: t,
            warnExpiredTerms: function() {
                this.showExpiredTermsModal = true;
            },
            /** Блокирует действия по истекшей заявке на стадии согласования условий. */
            guardTermsNotExpired: function() {
                if (this.dealPrExpiredDuringTerms) {
                    this.warnExpiredTerms();
                    return false;
                }
                return true;
            },
            closeExpiredTermsModal: function() {
                this.showExpiredTermsModal = false;
            },
            setViewerRoleChoice: function(role) {
                var self = this;
                if (!self.resolvePaymentRequest || self.roleSubmitting) return;
                if (self.viewerAcceptancePending) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                var r = String(role || '').trim();
                if (r !== 'counterparty' && r !== 'intermediary') {
                    self.viewerRoleChoice = '';
                    return;
                }
                self.roleSubmitting = true;
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(pk)) +
                        '/viewer-role',
                    {
                        method: 'POST',
                        headers: {
                            Accept: 'application/json',
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({
                            role: r,
                            parent_ref: self.dealUid ? String(self.dealUid).trim() : null
                        })
                    }
                )
                    .then(function(resp) {
                        return resp.json().then(function(data) {
                            return { ok: resp.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) return;
                        var pr = res.data && res.data.payment_request;
                        if (pr) self.resolvePaymentRequest = pr;
                        self.viewerRoleChoice = r;
                    })
                    .catch(function() {})
                    .finally(function() {
                        self.roleSubmitting = false;
                    });
            },
            needsWalletPrimaryMismatch: function() {
                var auth = (this.profileWalletAddress || '').trim();
                var primary = (this.profilePrimaryWalletAddress || '').trim();
                if (!auth || !primary) return false;
                return auth !== primary;
            },
            closeWalletMismatchModal: function() {
                this.showWalletMismatchModal = false;
                this._walletMismatchPending = null;
            },
            closePrLockedByOtherModal: function() {
                this.showPrLockedByOtherModal = false;
            },
            confirmWalletMismatchProceed: function() {
                var p = this._walletMismatchPending;
                this.closeWalletMismatchModal();
                if (!p) return;
                if (p.mode === 'accept') {
                    this._performHandshakeAccept(p.counterStableAmount);
                } else if (p.mode === 'confirm') {
                    this._performOwnerConfirm();
                }
            },
            openExtendLifetimeModal: function(pk, applyToResolve) {
                if (pk === undefined || pk === null) return;
                this.extendTargetPk = pk;
                this.extendApplyToResolve = !!applyToResolve;
                this.extendLifetime = '72h';
                this.showExtendLifetimeModal = true;
            },
            closeExtendLifetimeModal: function() {
                if (this.extendSubmitting) return;
                this.showExtendLifetimeModal = false;
                this.extendTargetPk = null;
                this.extendApplyToResolve = false;
            },
            /** Текст ошибки из тела ответа FastAPI (detail: str | array). */
            simpleApiErrorMessage: function(data) {
                if (!data) return '';
                var d = data.detail;
                if (typeof d === 'string') return d;
                if (Array.isArray(d) && d.length) {
                    return d
                        .map(function(x) {
                            return x && x.msg ? String(x.msg) : JSON.stringify(x);
                        })
                        .join('; ');
                }
                if (data.message) return String(data.message);
                return '';
            },
            fetchAuthOwnSpace: function() {
                var self = this;
                var tok = getToken();
                if (!tok || self.showAuthModal) {
                    self.authOwnSpace = '';
                    self.viewerDid = '';
                    return Promise.resolve();
                }
                var headers = { Accept: 'application/json', Authorization: 'Bearer ' + tok };
                var xs = (self.activeSpace || '').trim();
                if (xs) headers['X-Space'] = xs;
                return fetch('/v1/auth/tron/me', {
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
                        if (!res.ok || !res.data) {
                            self.authOwnSpace = '';
                            self.viewerDid = '';
                            return;
                        }
                        var o = res.data.own_space;
                        self.authOwnSpace = o != null && o !== undefined ? String(o).trim() : '';
                        var didRaw = res.data.did;
                        self.viewerDid =
                            didRaw != null && didRaw !== undefined ? String(didRaw).trim() : '';
                    })
                    .catch(function() {
                        self.authOwnSpace = '';
                    });
            },
            fetchSpaceProfileNickname: function() {
                var self = this;
                if (!getToken() || self.showAuthModal) return Promise.resolve();
                var tok = getToken();
                var headers = { Accept: 'application/json', Authorization: 'Bearer ' + tok };
                var xs = (self.activeSpace || '').trim();
                if (xs) headers['X-Space'] = xs;
                return fetch('/v1/profile/tron/me', {
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
                        if (!res.ok || !res.data) return;
                        var d = res.data;
                        self.profileWalletAddress =
                            d.wallet_address != null && d.wallet_address !== undefined
                                ? String(d.wallet_address).trim()
                                : '';
                        self.profilePrimaryWalletAddress =
                            d.primary_wallet_address != null &&
                            d.primary_wallet_address !== undefined
                                ? String(d.primary_wallet_address).trim()
                                : '';
                        self.profilePrimaryWalletBlockchain =
                            d.primary_wallet_blockchain != null &&
                            d.primary_wallet_blockchain !== undefined
                                ? String(d.primary_wallet_blockchain).trim().toLowerCase()
                                : '';
                        var label = String(res.data.company_name || '').trim();
                        self.spaceProfileLabel = label;
                        var nick = String(res.data.nickname || '').trim();
                        if (!nick) return;
                        self.spaceProfileNickname = nick;
                        if ((self.activeSpace || '').trim() !== nick) {
                            self.activeSpace = nick;
                            setSpace(nick);
                        }
                    })
                    .catch(function() {});
            },
            openSpaceNicknameModal: function() {
                if (!this.simpleSpaceIsOwner) return;
                if (!getToken() || this.showAuthModal) return;
                this.spaceLabelError = '';
                this.spaceLabelEdit = (this.spaceProfileLabel || '').trim();
                this.showSpaceNicknameModal = true;
            },
            closeSpaceNicknameModal: function() {
                if (this.spaceLabelSaving) return;
                this.showSpaceNicknameModal = false;
                this.spaceLabelError = '';
            },
            submitSpaceNickname: function() {
                var self = this;
                if (!self.simpleSpaceIsOwner) return;
                if (self.spaceLabelSaving) return;
                var raw = String(self.spaceLabelEdit || '').trim();
                if (!raw) {
                    self.spaceLabelError = t('main.simple.space_nickname_error_empty');
                    return;
                }
                if (raw.length > 100) {
                    self.spaceLabelError = t('main.simple.space_nickname_error_length');
                    return;
                }
                if (raw === (self.spaceProfileLabel || '').trim()) {
                    self.showSpaceNicknameModal = false;
                    self.spaceLabelError = '';
                    return;
                }
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                self.spaceLabelSaving = true;
                self.spaceLabelError = '';
                fetch('/v1/profile/tron/me', {
                    method: 'PUT',
                    headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                        Authorization: 'Bearer ' + tok
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ company_name: raw })
                })
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var msg = self.simpleApiErrorMessage(res.data);
                            self.spaceLabelError =
                                msg || t('main.simple.space_nickname_error_generic');
                            return;
                        }
                        var label = res.data && res.data.company_name ? String(res.data.company_name).trim() : raw;
                        self.spaceProfileLabel = label;
                        self.showSpaceNicknameModal = false;
                    })
                    .catch(function() {
                        self.spaceLabelError = t('main.simple.space_nickname_error_generic');
                    })
                    .finally(function() {
                        self.spaceLabelSaving = false;
                    });
            },
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
                            self.showResellCommissionModal = false;
                            self.resellModalError = '';
                            return;
                        }
                        var data = res.data || {};
                        self.resolveKind = data.kind || null;
                        self.resolvePaymentRequest = data.payment_request || null;
                        self.resolveDeal = data.deal || null;
                        self.resolveDealPaymentRequestPk =
                            data.payment_request_pk !== undefined && data.payment_request_pk !== null
                                ? parseInt(String(data.payment_request_pk), 10)
                                : null;
                        self.resolveDealPaymentRequestPublicRef =
                            data.payment_request_public_ref !== undefined &&
                            data.payment_request_public_ref !== null
                                ? String(data.payment_request_public_ref).trim()
                                : '';
                        self.resolveDealPaymentRequestHeading =
                            data.payment_request_heading !== undefined && data.payment_request_heading !== null
                                ? String(data.payment_request_heading).trim()
                                : '';
                        self.viewerDid =
                            data.viewer_did !== undefined && data.viewer_did !== null
                                ? String(data.viewer_did).trim()
                                : '';
                        /* После auto-resell API отдаёт commissioner public_ref; синхронизируем URL без перезагрузки.
                           Важно: для acceptor по commissioner_alias сервер сохраняет segment как public_ref, чтобы не переписывать URL на owner ref. */
                        var prAuto = data.payment_request;
                        var ownerDidAuto =
                            prAuto &&
                            prAuto.owner_did !== undefined &&
                            prAuto.owner_did !== null
                                ? String(prAuto.owner_did).trim()
                                : '';
                        var viewDidAuto = self.viewerDid || '';
                        if (
                            prAuto &&
                            data.kind === 'payment_request_only' &&
                            ownerDidAuto &&
                            viewDidAuto &&
                            ownerDidAuto !== viewDidAuto
                        ) {
                            var segAuto = String(self.dealUid || '').trim();
                            var prefAuto = String(prAuto.public_ref || '').trim();
                            if (
                                prefAuto &&
                                segAuto &&
                                segAuto.toLowerCase() !== prefAuto.toLowerCase()
                            ) {
                                self.dealUid = prefAuto;
                                try {
                                    if (
                                        typeof history !== 'undefined' &&
                                        history.replaceState &&
                                        typeof window !== 'undefined' &&
                                        window.location &&
                                        window.location.origin
                                    ) {
                                        var dealUrl =
                                            String(window.location.origin).trim() +
                                            self.simpleHtmlBase() +
                                            '/deal/' +
                                            encodeURIComponent(prefAuto);
                                        history.replaceState(null, '', dealUrl);
                                    }
                                } catch (eAuto) {}
                            }
                        }
                        self.resellBanner = null;
                        self.handshakeBanner = null;
                        self.copyLinkBanner = '';
                        self.showResellCommissionModal = false;
                        self.resellModalError = '';
                        // Default role choice for terms stage: set if already intermediary; otherwise keep empty (choose role).
                        try {
                            self.viewerRoleChoice = self.isCommissionerIntermediary
                                ? 'intermediary'
                                : '';
                        } catch (eRole) {
                            self.viewerRoleChoice = '';
                        }
                        if (tok) {
                            self.fetchSpaceProfileNickname();
                        }
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
            _clearTermsFeedbackLater: function() {
                var self = this;
                if (this._termsFeedbackTimer) {
                    clearTimeout(this._termsFeedbackTimer);
                }
                this._termsFeedbackTimer = setTimeout(function() {
                    self.resellBanner = null;
                    self.handshakeBanner = null;
                    self.copyLinkBanner = '';
                    self._termsFeedbackTimer = null;
                }, 3500);
            },
            closeAcceptAmountModal: function() {
                if (this.acceptSubmitting) return;
                this.showAcceptAmountModal = false;
                this.acceptModalError = '';
            },
            onAcceptTermsClick: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.acceptSubmitting) return;
                if (self.viewerRoleChoice === 'intermediary') return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                if (self.counterLegDiscussed) {
                    self.acceptModalError = '';
                    self.acceptAmountInput = '';
                    self.showAcceptAmountModal = true;
                    return;
                }
                self.submitHandshakeAccept(null);
            },
            confirmAcceptAmountModal: function() {
                var self = this;
                var cleaned = sanitizeDecimalAmountInput(self.acceptAmountInput);
                if (!cleaned || !String(cleaned).trim()) {
                    self.acceptModalError = t('main.simple.pr_resell_modal_percent_invalid');
                    return;
                }
                self.acceptModalError = '';
                self.submitHandshakeAccept(String(cleaned).trim());
            },
            submitHandshakeAccept: function(counterStableAmount) {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.acceptSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                if (self.needsWalletPrimaryMismatch()) {
                    self._walletMismatchPending = {
                        mode: 'accept',
                        counterStableAmount: counterStableAmount
                    };
                    self.showWalletMismatchModal = true;
                    return;
                }
                self._performHandshakeAccept(counterStableAmount);
            },
            _performHandshakeAccept: function(counterStableAmount) {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.acceptSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                self.acceptSubmitting = true;
                self.handshakeBanner = null;
                var bodyObj = {};
                if (
                    counterStableAmount !== undefined &&
                    counterStableAmount !== null &&
                    String(counterStableAmount).trim()
                ) {
                    bodyObj.counter_stable_amount = String(counterStableAmount).trim();
                }
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(pk)) +
                        '/accept',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify(bodyObj)
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, status: r.status, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var msg = self.simpleApiErrorMessage(res.data || {});
                            if (self.showAcceptAmountModal) {
                                self.acceptModalError = msg || t('main.simple.pr_accept_error');
                            } else {
                                self.handshakeBanner = { type: 'error', text: msg || t('main.simple.pr_accept_error') };
                                self._clearTermsFeedbackLater();
                            }
                            return;
                        }
                        self.showAcceptAmountModal = false;
                        self.acceptModalError = '';
                        var pr = res.data && res.data.payment_request;
                        if (pr) {
                            self.resolvePaymentRequest = pr;
                        }
                        self.handshakeBanner = {
                            type: 'success',
                            text: t('main.simple.pr_accept_done')
                        };
                        self._clearTermsFeedbackLater();
                        self.fetchResolve();
                        self.fetchOrders();
                    })
                    .catch(function() {
                        var msg = t('main.simple.pr_accept_error');
                        if (self.showAcceptAmountModal) {
                            self.acceptModalError = msg;
                        } else {
                            self.handshakeBanner = { type: 'error', text: msg };
                            self._clearTermsFeedbackLater();
                        }
                    })
                    .finally(function() {
                        self.acceptSubmitting = false;
                    });
            },
            submitWithdrawAcceptance: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.withdrawAcceptSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                self.withdrawAcceptSubmitting = true;
                self.handshakeBanner = null;
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(pk)) +
                        '/withdraw-acceptance',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: '{}'
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var msg = self.simpleApiErrorMessage(res.data || {});
                            self.handshakeBanner = {
                                type: 'error',
                                text: msg || t('main.simple.pr_withdraw_error')
                            };
                            self._clearTermsFeedbackLater();
                            return;
                        }
                        var pr = res.data && res.data.payment_request;
                        if (pr) {
                            self.resolvePaymentRequest = pr;
                        }
                        self.handshakeBanner = {
                            type: 'success',
                            text: t('main.simple.pr_withdraw_done')
                        };
                        self._clearTermsFeedbackLater();
                        self.fetchResolve();
                        self.fetchOrders();
                    })
                    .catch(function() {
                        self.handshakeBanner = {
                            type: 'error',
                            text: t('main.simple.pr_withdraw_error')
                        };
                        self._clearTermsFeedbackLater();
                    })
                    .finally(function() {
                        self.withdrawAcceptSubmitting = false;
                    });
            },
            submitOwnerConfirm: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.ownerConfirmSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                if (self.needsWalletPrimaryMismatch()) {
                    self._walletMismatchPending = { mode: 'confirm' };
                    self.showWalletMismatchModal = true;
                    return;
                }
                self._performOwnerConfirm();
            },
            _performOwnerConfirm: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                if (!self.resolvePaymentRequest || self.ownerConfirmSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                var pk = self.resolvePaymentRequest.pk;
                if (pk === undefined || pk === null) return;
                self.ownerConfirmSubmitting = true;
                self.handshakeBanner = null;
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(pk)) +
                        '/confirm',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: '{}'
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var msg = self.simpleApiErrorMessage(res.data || {});
                            self.handshakeBanner = {
                                type: 'error',
                                text: msg || t('main.simple.pr_confirm_error')
                            };
                            self._clearTermsFeedbackLater();
                            return;
                        }
                        var data = res.data || {};
                        var pr = data.payment_request;
                        if (pr) {
                            self.resolvePaymentRequest = pr;
                        }
                        var dealUid =
                            data.deal_uid !== undefined && data.deal_uid !== null
                                ? String(data.deal_uid).trim()
                                : '';
                        self.handshakeBanner = {
                            type: 'success',
                            text: t('main.simple.pr_confirm_done')
                        };
                        self._clearTermsFeedbackLater();
                        if (dealUid) {
                            try {
                                self.dealUid = dealUid;
                                if (
                                    typeof history !== 'undefined' &&
                                    history.replaceState &&
                                    typeof window !== 'undefined' &&
                                    window.location &&
                                    window.location.origin
                                ) {
                                    var dealUrl =
                                        String(window.location.origin).trim() +
                                        self.simpleHtmlBase() +
                                        '/deal/' +
                                        encodeURIComponent(dealUid);
                                    history.replaceState(null, '', dealUrl);
                                }
                            } catch (eNav) {}
                        }
                        self.fetchResolve();
                        self.fetchOrders();
                    })
                    .catch(function() {
                        self.handshakeBanner = {
                            type: 'error',
                            text: t('main.simple.pr_confirm_error')
                        };
                        self._clearTermsFeedbackLater();
                    })
                    .finally(function() {
                        self.ownerConfirmSubmitting = false;
                    });
            },
            submitExtendPaymentRequest: function(pk, applyToResolve, lifetime) {
                var self = this;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                if (self.extendSubmitting) return;
                if (pk === undefined || pk === null) return;
                var lt = (lifetime || '72h').trim ? String(lifetime).trim() : '72h';
                self.extendSubmitting = true;
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(pk)) +
                        '/extend',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ lifetime: lt })
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var msg = self.simpleApiErrorMessage(res.data || {});
                            self.handshakeBanner = {
                                type: 'error',
                                text: msg || t('main.simple.pr_extend_error')
                            };
                            self._clearTermsFeedbackLater();
                            return;
                        }
                        var pr = res.data && res.data.payment_request;
                        if (applyToResolve && pr) {
                            self.resolvePaymentRequest = pr;
                        }
                        self.showExpiredTermsModal = false;
                        self.showExtendLifetimeModal = false;
                        self.extendTargetPk = null;
                        self.extendApplyToResolve = false;
                        self.acceptModalError = '';
                        self.handshakeBanner = {
                            type: 'success',
                            text: t('main.simple.pr_extend_done')
                        };
                        self._clearTermsFeedbackLater();
                        self.fetchOrders();
                        if (applyToResolve) self.fetchResolve();
                    })
                    .catch(function() {
                        self.handshakeBanner = {
                            type: 'error',
                            text: t('main.simple.pr_extend_error')
                        };
                        self._clearTermsFeedbackLater();
                    })
                    .finally(function() {
                        self.extendSubmitting = false;
                    });
            },
            submitExtendFromList: function(req) {
                if (!req) return;
                if (!this.isOrdersItemOwner(req)) return;
                this.openExtendLifetimeModal(req.pk, false);
            },
            submitExtendFromDeal: function() {
                if (!this.resolvePaymentRequest) return;
                if (!this.isPaymentRequestOwner) return;
                this.openExtendLifetimeModal(this.resolvePaymentRequest.pk, true);
            },
            confirmExtendLifetimeModal: function() {
                var pk = this.extendTargetPk;
                if (pk === undefined || pk === null) return;
                this.submitExtendPaymentRequest(pk, !!this.extendApplyToResolve, this.extendLifetime);
            },
            dealPublicPageUrl: function() {
                try {
                    var o =
                        typeof window !== 'undefined' && window.location && window.location.origin
                            ? String(window.location.origin).trim()
                            : '';
                    var du = (this.dealUid || '').trim();
                    var a = (this.arbiterSpaceDid || '').trim();
                    if (!o || !du || !a) return '';
                    return o + '/arbiter/' + encodeURIComponent(a) + '/deal/' + encodeURIComponent(du);
                } catch (e) {
                    return '';
                }
            },
            /** Текущий % из своего слота посредника, иначе значение по умолчанию для поля модалки. */
            initialResellCommissionPercentForModal: function() {
                var pr = this.resolvePaymentRequest;
                if (!pr || !pr.commissioners || typeof pr.commissioners !== 'object') {
                    return '0.5';
                }
                var slot = viewerIntermediarySlot(pr, this.viewerDid);
                if (!slot || typeof slot !== 'object') return '0.5';
                var c = slot.commission;
                if (!c || typeof c !== 'object') return '0.5';
                if (String(c.kind || '').toLowerCase() !== 'percent') return '0.5';
                var raw = c.value;
                if (raw === undefined || raw === null) return '0.5';
                var s = sanitizeDecimalAmountInput(String(raw).trim());
                if (!s) return '0.5';
                var parsed = parseIntermediaryPercentForResell(s);
                if (parsed.ok) return parsed.apiValue;
                return s;
            },
            onResellClick: function() {
                if (!this.guardTermsNotExpired()) return;
                if (this.handshakeLockedByOther) {
                    this.showPrLockedByOtherModal = true;
                    return;
                }
                var tok = getToken();
                if (!tok) {
                    this.showAuthModal = true;
                    return;
                }
                if (this.viewerRoleChoice !== 'intermediary') {
                    this.setViewerRoleChoice('intermediary');
                    return;
                }
                this.resellModalError = '';
                this.resellCommissionPercent = this.initialResellCommissionPercentForModal();
                this.showResellCommissionModal = true;
            },
            closeResellCommissionModal: function() {
                if (this.resellSubmitting) return;
                this.showResellCommissionModal = false;
                this.resellModalError = '';
            },
            onResellSliderInput: function(e) {
                var t = e && e.target ? e.target : null;
                if (!t) return;
                var raw = parseFloat(t.value);
                if (!isFinite(raw)) return;
                var r = Math.round(raw * 100) / 100;
                r = Math.min(10, Math.max(0.1, r));
                this.resellCommissionPercent = String(r);
            },
            /** Только цифры и один десятичный разделитель (как sanitizeDecimalAmountInput). */
            onResellPercentFieldInput: function(e) {
                var el = e && e.target ? e.target : null;
                if (!el) return;
                var cleaned = sanitizeDecimalAmountInput(el.value);
                this.resellCommissionPercent = cleaned;
            },
            formatPercentForUi: function(dotStr) {
                var s = dotStr === undefined || dotStr === null ? '' : String(dotStr).trim();
                if (!s) return '';
                if (localePrefersCommaDecimal()) return s.replace(/\./g, ',');
                return s;
            },
            /** Строка «Комиссия X %» в списке заявок, если текущий пользователь — посредник по этой заявке. */
            orderListCommissionerPercentLine: function(req) {
                if (!req || !this.viewerDid) return '';
                var owner = (req.owner_did || '').trim();
                var vd = (this.viewerDid || '').trim();
                if (!owner || owner === vd) return '';
                var slot = viewerIntermediarySlot(req, vd);
                if (!slot || typeof slot !== 'object') return '';
                var c = slot.commission;
                if (!c || String(c.kind || '').toLowerCase() !== 'percent') return '';
                var raw = c.value != null ? String(c.value).trim() : '';
                if (!raw) return '';
                var pctUi = this.formatPercentForUi(raw) + ' %';
                return t('main.simple.orders_list_commission_line', { pct: pctUi });
            },
            /** Строка процента посредника для блока «Ваша комиссия». */
            commissionerCommissionPercentLine: function() {
                if (!this.isCommissionerIntermediary) return '—';
                var slot = viewerIntermediarySlot(this.resolvePaymentRequest, this.viewerDid);
                var c = slot && slot.commission;
                if (!c || String(c.kind || '').toLowerCase() !== 'percent') return '—';
                var raw = c.value != null ? String(c.value).trim() : '';
                if (!raw) return '—';
                return this.formatPercentForUi(raw) + ' %';
            },
            /** Доля комиссии по фиатной ноге (API payment_amount + код фиата). */
            commissionerCommissionFiatLine: function() {
                if (!this.isCommissionerIntermediary) return '—';
                var pr = this.resolvePaymentRequest;
                var slot = viewerIntermediarySlot(pr, this.viewerDid);
                var amt =
                    slot && slot.payment_amount != null
                        ? String(slot.payment_amount).trim()
                        : '';
                var leg = prLegForAsset(pr, true);
                var code = leg && leg.code ? String(leg.code).trim().toUpperCase() : '';
                var fmt = amt ? formatAmountForLocale(amt) : '';
                if (!fmt && !code) return '—';
                return fmt ? fmt + (code ? ' ' + code : '') : code;
            },
            /** Доля комиссии по залогу / базе B (API borrow_amount + код стейбла). */
            commissionerCommissionStableLine: function() {
                if (!this.isCommissionerIntermediary) return '—';
                var pr = this.resolvePaymentRequest;
                var slot = viewerIntermediarySlot(pr, this.viewerDid);
                var amt =
                    slot && slot.borrow_amount != null
                        ? String(slot.borrow_amount).trim()
                        : '';
                var leg = prLegForAsset(pr, false);
                var code = leg && leg.code ? String(leg.code).trim().toUpperCase() : '';
                var fmt = amt ? formatAmountForLocale(amt) : '';
                if (!fmt && !code) return '—';
                return fmt ? fmt + (code ? ' ' + code : '') : code;
            },
            /**
             * Суффикс к строке сумм «Условия по заявке»: дублирует комиссию посредника в стейбле (+ X USDT).
             */
            dealFlowStableCommissionSuffix: function() {
                if (!this.isCommissionerIntermediary) return '';
                var s = this.commissionerCommissionStableLine();
                if (!s || s === '—') return '';
                return t('main.simple.pr_sum_line_stable_commission_suffix', { amount: s });
            },
            /**
             * Нога со стейблом для эскроу: база + сумма комиссий по залогу (borrow_amount по всем слотам).
             * Это source-of-trust для взаиморасчётов; структура цепочки не раскрывается, показывается только итог.
             */
            viewerStableLegEscrowTotalFormatted: function() {
                if (!this.resolvePaymentRequest) return '';
                var pr = this.resolvePaymentRequest;
                var feeTotal = prStableEscrowFeesTotal(pr);
                if (!feeTotal || !isFinite(feeTotal)) return '';
                var stableLeg = prLegForAsset(pr, false);
                if (!stableLeg || String(stableLeg.asset_type || '').toLowerCase() !== 'stable') {
                    return '';
                }
                var baseRaw =
                    stableLeg.amount != null ? String(stableLeg.amount).trim() : '';
                if (!baseRaw) return '';
                var ba = parseFloat(sanitizeDecimalAmountInput(baseRaw));
                if (!isFinite(ba) || !isFinite(feeTotal)) return '';
                var sum = ba + feeTotal;
                var code = stableLeg.code ? String(stableLeg.code).trim().toUpperCase() : '';
                var sumStr = formatAmountForLocale(String(sum));
                return sumStr + (code ? ' ' + code : '');
            },
            /**
             * Для посредника: «получают» = база B + комиссии предыдущей цепочки (без моей комиссии).
             */
            viewerStableLegPrevChainTotalFormatted: function(req) {
                var pr = req || this.resolvePaymentRequest;
                if (!pr) return '';
                var feeBefore = prStableEscrowFeesBeforeViewer(pr, this.viewerDid);
                if (!isFinite(feeBefore) || feeBefore <= 0) return '';
                var stableLeg = prLegForAsset(pr, false);
                if (!stableLeg || String(stableLeg.asset_type || '').toLowerCase() !== 'stable') {
                    return '';
                }
                var baseRaw =
                    stableLeg.amount != null ? String(stableLeg.amount).trim() : '';
                if (!baseRaw) return '';
                var ba = parseFloat(sanitizeDecimalAmountInput(baseRaw));
                if (!isFinite(ba)) return '';
                var sum = ba + feeBefore;
                var code = stableLeg.code ? String(stableLeg.code).trim().toUpperCase() : '';
                var sumStr = formatAmountForLocale(String(sum));
                return sumStr + (code ? ' ' + code : '');
            },
            /** «Вторая нога» / залог для посредника: сумма + комиссия (эскроу). */
            dealViewStatReceiveEscrowTotal: function() {
                if (this.resolveKind !== 'payment_request_only' || !this.resolvePaymentRequest) {
                    return '—';
                }
                // Owner always sees the exact amount from the request (без надбавок escrow).
                if (this.isPaymentRequestOwner) {
                    return this.dealViewStatReceive();
                }
                // intermediary: base + prev chain (без своей комиссии)
                if (this.viewerRoleChoice === 'intermediary') {
                    var prev = this.viewerStableLegPrevChainTotalFormatted(this.resolvePaymentRequest);
                    return prev || this.dealViewStatReceive();
                }
                // participant/counterparty/не выбрано: base + all fees (escrow lock)
                var esc = this.viewerStableLegEscrowTotalFormatted();
                return esc || this.dealViewStatReceive();
            },
            /** Текст в блоке lockbox: сумма залога для escrow lock (base + все комиссии по залогу). */
            dealLockboxHintEscrowFromPr: function(req) {
                if (!req) return '';
                if (this.resolvePaymentRequest && req.pk === this.resolvePaymentRequest.pk) {
                    var esc = this.viewerStableLegEscrowTotalFormatted();
                    if (esc) return esc;
                }
                return this.dealLockboxHintFromPr(req);
            },
            confirmResellCommissionModal: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                self.resellModalError = '';
                var parsed = parseIntermediaryPercentForResell(self.resellCommissionPercent);
                if (!parsed.ok) {
                    if (parsed.code === 'range') {
                        self.resellModalError = t('main.simple.pr_resell_modal_percent_range');
                    } else {
                        self.resellModalError = t('main.simple.pr_resell_modal_percent_invalid');
                    }
                    return;
                }
                self.submitResellIntermediary(parsed.apiValue);
            },
            submitResellIntermediary: function(intermediaryPercent) {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                var pctStr =
                    intermediaryPercent !== undefined && intermediaryPercent !== null
                        ? String(intermediaryPercent).trim()
                        : '0.5';
                if (!self.dealUid || self.resellSubmitting) return;
                var tok = getToken();
                if (!tok) {
                    self.showAuthModal = true;
                    return;
                }
                self.resellSubmitting = true;
                self.resellBanner = null;
                fetch(
                    self.simpleV1Prefix() +
                        'payment-requests/' +
                        encodeURIComponent(String(self.dealUid).trim()) +
                        '/resell',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: 'Bearer ' + tok
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ intermediary_percent: pctStr })
                    }
                )
                    .then(function(r) {
                        return r.json().then(function(data) {
                            return { ok: r.ok, data: data };
                        });
                    })
                    .then(function(res) {
                        if (!res.ok) {
                            var d = res.data && res.data.detail;
                            var msg = typeof d === 'string' ? d : t('main.simple.pr_resell_error');
                            if (self.showResellCommissionModal) {
                                self.resellModalError = msg;
                            } else {
                                self.resellBanner = { type: 'error', text: msg };
                                self._clearTermsFeedbackLater();
                            }
                            return;
                        }
                        self.showResellCommissionModal = false;
                        self.resellModalError = '';
                        var pr = res.data && res.data.payment_request;
                        var pctDisp = pctStr;
                        var vmSlot =
                            pr && self.viewerDid ? viewerIntermediarySlot(pr, self.viewerDid) : null;
                        if (vmSlot && vmSlot.commission) {
                            var v = vmSlot.commission.value;
                            if (v !== undefined && v !== null && String(v).trim()) {
                                pctDisp = String(v).trim();
                            }
                        }
                        if (pr) {
                            self.resolvePaymentRequest = pr;
                        }
                        self.resellBanner = {
                            type: 'success',
                            text: t('main.simple.pr_resell_done', {
                                percent: self.formatPercentForUi(pctDisp)
                            })
                        };
                        self._clearTermsFeedbackLater();
                    })
                    .catch(function() {
                        var msg = t('main.simple.pr_resell_error');
                        if (self.showResellCommissionModal) {
                            self.resellModalError = msg;
                        } else {
                            self.resellBanner = { type: 'error', text: msg };
                            self._clearTermsFeedbackLater();
                        }
                    })
                    .finally(function() {
                        self.resellSubmitting = false;
                    });
            },
            copyDealPublicLink: function() {
                var self = this;
                if (!self.guardTermsNotExpired()) return;
                var text = self.dealPublicPageUrl();
                if (!text) return;
                var done = function() {
                    self.copyLinkBanner = t('main.simple.pr_copy_link_done');
                    self._clearTermsFeedbackLater();
                };
                if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(done).catch(function() {
                        self._copyDealLinkFallback(text, done);
                    });
                } else {
                    self._copyDealLinkFallback(text, done);
                }
            },
            _copyDealLinkFallback: function(text, done) {
                try {
                    var ta = document.createElement('textarea');
                    ta.value = text;
                    ta.setAttribute('readonly', '');
                    ta.style.position = 'fixed';
                    ta.style.left = '-9999px';
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    if (typeof done === 'function') done();
                } catch (e) {}
            },
            /** Подзаголовок шага 02 в сайдбаре (динамика из resolve). */
            navStepActiveSub: function(step) {
                if (step.status !== 'active') return '';
                if (step.num !== '02') return t(step.subKey);
                if (this.resolveLoading) return '…';
                if (this.resolveKind === 'payment_request_only' && this.resolvePaymentRequest) {
                    var pr = this.resolvePaymentRequest;
                    if (pr.deal_id) {
                        return t('main.simple.handshake_nav_deal_created');
                    }
                    if (pr.owner_confirm_pending && !pr.deal_id) {
                        var v = (this.viewerDid || '').trim();
                        var owner = (pr.owner_did || '').trim();
                        var acc = (pr.counterparty_accept_did || '').trim();
                        if (v === owner) return t('main.simple.handshake_nav_owner_pending');
                        if (acc && v === acc) return t('main.simple.handshake_nav_counterparty_waiting');
                        if (pr.handshake_locked_by_other) return t('main.simple.handshake_nav_locked_viewer');
                        return t('main.simple.handshake_nav_negotiating');
                    }
                    var line = this.dealLockboxHintFromPr(pr);
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
                // In deal_only we still have resolvePaymentRequest (linked PR); reuse the same display logic.
                if (!this.resolvePaymentRequest) return '—';
                return formatPaymentRequestLegLine(prLegForAsset(this.resolvePaymentRequest, true), false);
            },
            /** Карточка «Залог»: только стейбл-нога. */
            dealViewStatStableAmount: function() {
                if (!this.resolvePaymentRequest) return '—';
                // Escrow total (base + fees) when available; fallback to raw stable leg line.
                var esc = this.viewerStableLegEscrowTotalFormatted();
                return esc || formatPaymentRequestLegLine(prLegForAsset(this.resolvePaymentRequest, false), true);
            },
            dealViewStatRate: function() {
                if (!this.resolvePaymentRequest) return '—';
                var m = paymentRequestDisplayRateMeta(this.resolvePaymentRequest);
                if (!m) return '—';
                return m.display.toFixed(4);
            },
            /**
             * Подпись к числу курса: ось совпадает с отображаемым значением
             * (при raw < 1 — обратный курс и переставленная ось через те же ключи i18n).
             */
            dealViewStatRateLabel: function() {
                if (!this.resolvePaymentRequest) {
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
             * Контрагент/acceptor: только итоговые суммы ног; разбивка комиссий — только у посредника (isCommissionerIntermediary).
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
                // Для non-owner "истинная" сумма в stable-ноге (escrow lock): base + fees.
                // Owner всегда видит raw amount из заявки.
                var stableIsReceive = String(req.direction || '') === 'fiat_to_stable';
                var vd = (this.viewerDid || '').trim();
                var amOwnerForReq = !!(vd && (req.owner_did || '').trim() === vd);
                var amIntermediaryForReq = !!(vd && !amOwnerForReq && viewerIntermediarySlot(req, vd));
                if (amIntermediaryForReq) {
                    var prevStable = this.viewerStableLegPrevChainTotalFormatted(req);
                    if (prevStable) {
                        // prevStable already contains code; override stable leg display without раскрытия структуры
                        if (stableIsReceive) {
                            ra = prevStable;
                            rc = '';
                        } else {
                            ga = prevStable;
                            gc = '';
                        }
                    }
                } else if (!amOwnerForReq) {
                    try {
                        var feeTotal = prStableEscrowFeesTotal(req);
                        if (feeTotal && isFinite(feeTotal)) {
                            var stableLeg = prLegForAsset(req, false);
                            if (stableLeg && String(stableLeg.asset_type || '').toLowerCase() === 'stable') {
                                var baseRaw =
                                    stableLeg.amount != null ? String(stableLeg.amount).trim() : '';
                                if (baseRaw) {
                                    var ba = parseFloat(sanitizeDecimalAmountInput(baseRaw));
                                    if (isFinite(ba)) {
                                        var sum = ba + feeTotal;
                                        var code = stableLeg.code ? String(stableLeg.code).trim().toUpperCase() : '';
                                        var sumStr = formatAmountForLocale(String(sum));
                                        var escStable = sumStr + (code ? ' ' + code : '');
                                        if (stableIsReceive) {
                                            ra = escStable;
                                            rc = '';
                                        } else {
                                            ga = escStable;
                                            gc = '';
                                        }
                                    }
                                }
                            }
                        }
                    } catch (eEsc) {}
                }
                var arrow = ' → ';
                var lbGive = t('main.simple.pr_give_label');
                var lbRecv = t('main.simple.pr_receive_label');
                if (this.orderHasReceiveAmount(req)) {
                    var leftInv = ga ? ga + ' ' + gc : (gc || '—');
                    var rightInv = ra ? (rc ? ra + ' ' + rc : ra) : (rc || '—');
                    return lbGive + ' ' + leftInv + arrow + lbRecv + ' ' + rightInv;
                }
                var leftTerms = ga ? ga + ' ' + gc : (gc || '—');
                var rightTerms = rc || '—';
                return lbGive + ' ' + leftTerms + arrow + lbRecv + ' ' + rightTerms;
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
            /** Владелец заявки в списке (для кнопки деактивации). */
            isOrdersItemOwner: function(req) {
                var v = (this.viewerDid || '').trim();
                var o = req && (req.owner_did || '').trim();
                return !!(v && o && v === o);
            },
            /** Краткий статус рукопожатия в карточке списка заявок. */
            orderHandshakeBadgeText: function(req) {
                if (!req || req.deactivated_at) return '';
                if (req.deal_id) return t('main.simple.handshake_list_deal_created');
                if (!req.owner_confirm_pending) return '';
                var v = (this.viewerDid || '').trim();
                var owner = (req.owner_did || '').trim();
                var acc = (req.counterparty_accept_did || '').trim();
                if (v === owner) return t('main.simple.handshake_list_owner_confirm');
                if (acc && v === acc) return t('main.simple.handshake_list_you_accepted');
                if (req.handshake_locked_by_other) return t('main.simple.handshake_list_locked_other');
                return '';
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
                ensureSpace(token)
                    .then(function(res) {
                        if (!res || res.status !== 200 || !res.data || !res.data.space) {
                            self.authError =
                                res && res.data && res.data.detail
                                    ? String(res.data.detail)
                                    : t('main.simple.auth_error');
                            return Promise.reject(new Error('ensure-space'));
                        }
                        var target = String(res.data.space || '').trim();
                        self.activeSpace = target;
                        setSpace(target);
                        return self.fetchAuthOwnSpace();
                    })
                    .then(function() {
                        self.showAuthModal = false;
                        self.fetchSpaceProfileNickname();
                        self.maybeFetchOrders();
                        self.maybeFetchResolve();
                    })
                    .catch(function() {
                        if (!self.authError) self.authError = t('main.simple.auth_error');
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
            <input type="text" class="simple-create__input" :value="receiveAmountInputDisplay" inputmode="decimal" autocomplete="off" :disabled="receiveLocked" :placeholder="t(\'main.simple.amount_required_ph\')" @focus="onReceiveAmountFocus" @blur="onReceiveAmountBlur" @keydown="onAmountFieldKeydown" @input="onReceiveAmountInput" @compositionend="onReceiveAmountInput" />\
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
  <div v-if="showResellCommissionModal" class="simple-deactivate__overlay" @click.self="closeResellCommissionModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-resell-modal-title" @click.stop>\
      <h2 id="simple-resell-modal-title" class="simple-create__title">{{ t(\'main.simple.pr_resell_modal_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.pr_resell_modal_hint\') }}</p>\
      <label class="simple-create__label" for="simple-resell-pct">{{ t(\'main.simple.pr_resell_modal_label\') }}</label>\
      <input id="simple-resell-pct" type="text" class="simple-create__input" :value="resellCommissionPercent" inputmode="decimal" autocomplete="off" :placeholder="t(\'main.simple.pr_resell_modal_placeholder\')" @input="onResellPercentFieldInput" @compositionend="onResellPercentFieldInput" />\
      <input type="range" class="simple-page__resell-pct-slider" min="0.1" max="10" step="0.01" :value="resellSliderValue" @input="onResellSliderInput" :aria-label="t(\'main.simple.pr_resell_modal_slider_aria\')" />\
      <div v-if="resellModalError" class="simple-create__err">{{ resellModalError }}</div>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeResellCommissionModal" :disabled="resellSubmitting">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="confirmResellCommissionModal" :disabled="resellModalSubmitDisabled">\
          <span v-if="resellSubmitting" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.pr_resell_modal_submit\') }}\
        </button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showAcceptAmountModal" class="simple-deactivate__overlay" @click.self="closeAcceptAmountModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-accept-amt-title" @click.stop>\
      <h2 id="simple-accept-amt-title" class="simple-create__title">{{ t(\'main.simple.pr_accept_modal_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.pr_accept_modal_hint\') }}</p>\
      <label class="simple-create__label" for="simple-accept-amt-input">{{ t(\'main.simple.pr_accept_modal_label\') }}</label>\
      <input id="simple-accept-amt-input" type="text" class="simple-create__input" v-model.trim="acceptAmountInput" inputmode="decimal" autocomplete="off" />\
      <div v-if="acceptModalError" class="simple-create__err">{{ acceptModalError }}</div>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeAcceptAmountModal" :disabled="acceptSubmitting">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="confirmAcceptAmountModal" :disabled="acceptModalSubmitDisabled">\
          <span v-if="acceptSubmitting" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.pr_accept_modal_submit\') }}\
        </button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showExpiredTermsModal" class="simple-deactivate__overlay" @click.self="closeExpiredTermsModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-expired-terms-title" @click.stop>\
      <h2 id="simple-expired-terms-title" class="simple-create__title">{{ t(\'main.simple.pr_expired_terms_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.pr_expired_terms_warn\') }}</p>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="closeExpiredTermsModal">{{ t(\'main.simple.pr_expired_terms_close\') }}</button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showExtendLifetimeModal" class="simple-deactivate__overlay" @click.self="closeExtendLifetimeModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-extend-lifetime-title" @click.stop>\
      <h2 id="simple-extend-lifetime-title" class="simple-create__title">{{ t(\'main.simple.pr_extend_modal_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.pr_extend_modal_hint\') }}</p>\
      <label class="simple-create__label" for="simple-extend-lifetime">{{ t(\'main.simple.pr_extend_modal_label\') }}</label>\
      <select id="simple-extend-lifetime" v-model="extendLifetime" class="simple-create__select">\
        <option value="24h">{{ t(\'main.simple.lifetime_24h\') }}</option>\
        <option value="48h">{{ t(\'main.simple.lifetime_48h\') }}</option>\
        <option value="72h">{{ t(\'main.simple.lifetime_72h\') }}</option>\
      </select>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeExtendLifetimeModal" :disabled="extendSubmitting">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="confirmExtendLifetimeModal" :disabled="extendSubmitting">\
          <span v-if="extendSubmitting" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.pr_extend_modal_submit\') }}\
        </button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showWalletMismatchModal" class="simple-deactivate__overlay" @click.self="closeWalletMismatchModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-wallet-mismatch-title" @click.stop>\
      <h2 id="simple-wallet-mismatch-title" class="simple-create__title">{{ t(\'main.simple.wallet_mismatch_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.wallet_mismatch_intro\', { primary: profilePrimaryWalletAddress || \'—\' }) }}</p>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.wallet_mismatch_admin\') }}</p>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeWalletMismatchModal">{{ t(\'main.simple.wallet_mismatch_cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="confirmWalletMismatchProceed">{{ t(\'main.simple.wallet_mismatch_proceed\') }}</button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showPrLockedByOtherModal" class="simple-deactivate__overlay" @click.self="closePrLockedByOtherModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-pr-locked-title" @click.stop>\
      <h2 id="simple-pr-locked-title" class="simple-create__title">{{ t(\'main.simple.pr_locked_other_title\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.pr_locked_other_text\') }}</p>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="closePrLockedByOtherModal">{{ t(\'main.simple.pr_locked_other_close\') }}</button>\
      </div>\
    </div>\
  </div>\
  <div v-if="showSpaceNicknameModal" class="simple-deactivate__overlay" @click.self="closeSpaceNicknameModal">\
    <div class="simple-create__modal simple-deactivate__modal" role="dialog" aria-modal="true" aria-labelledby="simple-space-nick-title" @click.stop>\
      <h2 id="simple-space-nick-title" class="simple-create__title">{{ t(\'main.space_profile.form_company_name\') }}</h2>\
      <p class="simple-deactivate__hint">{{ t(\'main.simple.space_nickname_modal_hint\') }}</p>\
      <label class="simple-create__label" for="simple-space-nick-input">{{ t(\'main.space_profile.form_company_name\') }}</label>\
      <input id="simple-space-nick-input" type="text" class="simple-create__input" v-model.trim="spaceLabelEdit" maxlength="100" autocomplete="organization" />\
      <div v-if="spaceLabelError" class="simple-create__err">{{ spaceLabelError }}</div>\
      <div class="simple-create__actions">\
        <button type="button" class="simple-create__btn simple-create__btn--ghost" @click="closeSpaceNicknameModal" :disabled="spaceLabelSaving">{{ t(\'main.simple.cancel\') }}</button>\
        <button type="button" class="simple-create__btn simple-create__btn--primary" @click="submitSpaceNickname" :disabled="spaceLabelSaving">\
          <span v-if="spaceLabelSaving" class="simple-create__btn-spinner" aria-hidden="true"></span>\
          {{ t(\'main.simple.space_nickname_save\') }}\
        </button>\
      </div>\
    </div>\
  </div>\
  <div class="simple-page__window">\
    <div class="simple-page__titlebar">\
      <div class="simple-page__titlebar-left">\
        <div v-if="authReady && !showAuthModal && titlebarSpaceLabel" class="simple-page__titlebar-left-inner">\
          <span class="simple-page__space-nick-caption">{{ t(\'main.simple.space_nickname_caption\') }}</span>\
          <button\
            v-if="simpleSpaceIsOwner"\
            type="button"\
            class="simple-page__space-nick-btn"\
            @click="openSpaceNicknameModal"\
            :aria-label="t(\'main.simple.space_nickname_rename_aria\')"\
            :title="t(\'main.simple.space_nickname_rename_aria\')"\
          >\
            <span class="simple-page__space-nick-text">{{ titlebarSpaceLabel }}</span>\
            <svg class="simple-page__space-nick-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L7.5 21H3v-4.5L14.732 3.732z"/>\
            </svg>\
          </button>\
          <span v-else class="simple-page__space-nick-static">\
            <span class="simple-page__space-nick-text">{{ titlebarSpaceLabel }}</span>\
          </span>\
        </div>\
      </div>\
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
            <div v-for="req in ordersItems" :key="req.uid" class="simple-page__order-card" :class="{ \'simple-page__order-card--deactivated\': req.deactivated_at, \'simple-page__order-card--needs-confirm\': isOrdersItemOwner(req) && req && req.owner_confirm_pending && !req.deal_id && !req.deactivated_at }" role="listitem">\
              <a class="simple-page__order-card-hit" :href="simpleHtmlBase() + \'/deal/\' + encodeURIComponent(String(req.public_ref || req.uid))">\
                <div class="simple-page__order-card-main">\
                  <div class="simple-page__order-titles">\
                    <span class="simple-page__order-list-title">{{ orderListTitle(req) }}</span>\
                    <span v-if="orderHandshakeBadgeText(req)" class="simple-page__order-handshake-badge" :class="{ \'simple-page__order-handshake-badge--pulse\': isOrdersItemOwner(req) && req && req.owner_confirm_pending && !req.deal_id && !req.deactivated_at }">{{ orderHandshakeBadgeText(req) }}</span>\
                  </div>\
                </div>\
                <div class="simple-page__order-card-sub">\
                  <div class="simple-page__order-card-sub-primary">\
                    <span class="simple-page__order-amounts">{{ orderAmountsLine(req) }}</span>\
                    <span v-if="orderListCommissionerPercentLine(req)" class="simple-page__order-commission-pct">{{ orderListCommissionerPercentLine(req) }}</span>\
                  </div>\
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
                <button v-if="isOrdersItemOwner(req)" type="button" class="simple-page__order-deactivate-btn" @click.stop="submitExtendFromList(req)" :disabled="extendSubmitting" :aria-busy="extendSubmitting ? \'true\' : \'false\'">{{ t(\'main.simple.pr_btn_extend\') }}</button>\
                <button v-if="!req.deactivated_at && isOrdersItemOwner(req)" type="button" class="simple-page__order-deactivate-btn" @click.stop="openDeactivateModal(req)">{{ t(\'main.simple.deactivate_btn\') }}</button>\
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
          <div v-if="isCommissionerIntermediary" class="simple-page__commissioner-panel" role="region" :aria-label="t(\'main.simple.commission_detail_section_title\')">\
            <div class="simple-page__commissioner-panel-head">{{ t(\'main.simple.commission_detail_section_title\') }}</div>\
            <dl class="simple-page__commissioner-rows">\
              <div class="simple-page__commissioner-row">\
                <dt class="simple-page__commissioner-dt">{{ t(\'main.simple.commission_detail_rate\') }}</dt>\
                <dd class="simple-page__commissioner-dd">{{ commissionerCommissionPercentLine() }}</dd>\
              </div>\
              <div class="simple-page__commissioner-row">\
                <dt class="simple-page__commissioner-dt">{{ t(\'main.simple.commission_detail_on_fiat\') }}</dt>\
                <dd class="simple-page__commissioner-dd">{{ commissionerCommissionFiatLine() }}</dd>\
              </div>\
              <div class="simple-page__commissioner-row">\
                <dt class="simple-page__commissioner-dt">{{ t(\'main.simple.commission_detail_on_pledge\') }}</dt>\
                <dd class="simple-page__commissioner-dd">{{ commissionerCommissionStableLine() }}</dd>\
              </div>\
            </dl>\
          </div>\
          <div v-if="dealPrTermsPhase && handshakeLockedByOther && !isPaymentRequestOwner" class="simple-page__pr-handshake-locked-hint" role="status">{{ t(\'main.simple.handshake_locked_hint\') }}</div>\
          <div v-if="showOwnerConfirmBanner" class="simple-page__pr-handshake-banner simple-page__pr-handshake-banner--pulse" role="status">\
            <p class="simple-page__pr-handshake-banner-text">{{ t(\'main.simple.pr_owner_confirm_banner\') }}</p>\
            <button type="button" class="simple-page__pr-handshake-banner-btn" @click="submitOwnerConfirm" :disabled="ownerConfirmSubmitting" :aria-busy="ownerConfirmSubmitting ? \'true\' : \'false\'">\
              <span v-if="ownerConfirmSubmitting" class="simple-create__btn-spinner simple-page__pr-handshake-spinner" aria-hidden="true"></span>\
              {{ t(\'main.simple.pr_btn_owner_confirm\') }}\
            </button>\
          </div>\
          <div class="simple-page__flow-shell">\
            <div class="simple-page__flow-row" :class="{ \'simple-page__flow-row--pr-split\': dealPrTermsPhase }">\
              <div class="simple-page__flow-icon">\
                <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
              </div>\
              <div class="simple-page__flow-body">\
                <div class="simple-page__flow-title-row" :class="{ \'simple-page__flow-title-row--pr-tools\': dealPrTermsPhase }">\
                  <div v-if="!dealPrTermsPhase" class="simple-page__flow-title-cluster">\
                    <span class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_offer_title\') }}</span>\
                  </div>\
                  <template v-else>\
                    <span class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_offer_title\') }}</span>\
                    <div class="simple-page__pr-terms-actions">\
                      <div v-if="!isPaymentRequestOwner && !viewerAcceptancePending" class="simple-page__pr-role-switch">\
                        <select class="simple-page__pr-role-select" :value="viewerRoleChoice" @change="setViewerRoleChoice($event && $event.target ? $event.target.value : \'\')" :disabled="roleSubmitting || handshakeLockedByOther">\
                          <option value="">{{ t(\'main.simple.pr_role_choose\') }}</option>\
                          <option value="counterparty">{{ t(\'main.simple.pr_role_counterparty\') }}</option>\
                          <option value="intermediary">{{ t(\'main.simple.pr_role_intermediary\') }}</option>\
                        </select>\
                      </div>\
                      <button v-if="isPaymentRequestOwner" type="button" class="simple-page__pr-terms-btn simple-page__pr-terms-btn--link" @click="submitExtendFromDeal" :disabled="extendSubmitting" :aria-busy="extendSubmitting ? \'true\' : \'false\'">\
                        <span class="simple-page__pr-terms-btn-label">{{ t(\'main.simple.pr_btn_extend\') }}</span>\
                      </button>\
                      <button v-if="showAcceptTermsButton && viewerRoleChoice === \'counterparty\'" type="button" class="simple-page__pr-terms-btn simple-page__pr-terms-btn--accept" @click="onAcceptTermsClick" :disabled="acceptSubmitting || withdrawAcceptSubmitting" :aria-busy="acceptSubmitting ? \'true\' : \'false\'">\
                        <svg class="simple-page__pr-terms-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>\
                        </svg>\
                        <span class="simple-page__pr-terms-btn-label">{{ t(\'main.simple.pr_btn_accept\') }}</span>\
                      </button>\
                      <button v-if="showWithdrawAcceptButton" type="button" class="simple-page__pr-terms-btn simple-page__pr-terms-btn--withdraw" @click="submitWithdrawAcceptance" :disabled="withdrawAcceptSubmitting || acceptSubmitting" :aria-busy="withdrawAcceptSubmitting ? \'true\' : \'false\'">\
                        <span class="simple-page__pr-terms-btn-label">{{ t(\'main.simple.pr_btn_withdraw_accept\') }}</span>\
                      </button>\
                      <button v-if="!isPaymentRequestOwner && viewerRoleChoice === \'intermediary\'" type="button" class="simple-page__pr-terms-btn simple-page__pr-terms-btn--resell" @click="onResellClick" :disabled="resellSubmitting" :aria-busy="resellSubmitting ? \'true\' : \'false\'">\
                        <svg class="simple-page__pr-terms-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                          <path stroke-linecap="round" stroke-linejoin="round" d="M7 16V4m0 0L3 8m4-4 4 4m6 0v12m0 0l4-4m-4 4-4-4"/>\
                        </svg>\
                        <span class="simple-page__pr-terms-btn-label">{{ t(\'main.simple.pr_btn_resell\') }}</span><span v-if="commissionerResellButtonPctLabel" class="simple-page__pr-terms-btn-pct">{{ commissionerResellButtonPctLabel }}</span>\
                      </button>\
                      <button v-if="isPaymentRequestOwner || viewerRoleChoice === \'intermediary\'" type="button" class="simple-page__pr-terms-btn simple-page__pr-terms-btn--link" @click="copyDealPublicLink">\
                        <svg class="simple-page__pr-terms-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                          <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>\
                        </svg>\
                        <span>{{ t(\'main.simple.pr_btn_copy_link\') }}</span>\
                      </button>\
                    </div>\
                  </template>\
                  <span v-if="!dealPrTermsPhase && resolvePaymentRequest && resolvePaymentRequest.expires_at && !resolvePaymentRequest.deactivated_at" class="simple-page__flow-deadline" role="status" :aria-label="t(\'main.simple.deal_flow_deadline_aria\')">\
                    <svg class="simple-page__ico-clock simple-page__ico-clock--flow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                      <circle cx="12" cy="12" r="10" stroke-linecap="round"/>\
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l4 2"/>\
                    </svg>\
                    <span class="simple-page__flow-deadline-text">{{ formatExpiryCountdown(resolvePaymentRequest) }}</span>\
                  </span>\
                </div>\
                <div v-if="dealPrTermsPhase && (resellBanner || handshakeBanner || copyLinkBanner)" class="simple-page__pr-terms-feedback">\
                  <div v-if="resellBanner" class="simple-page__pr-inline-msg" :class="resellBanner.type === \'error\' ? \'simple-page__pr-inline-msg--err\' : \'\'">{{ resellBanner.text }}</div>\
                  <div v-if="handshakeBanner" class="simple-page__pr-inline-msg" :class="handshakeBanner.type === \'error\' ? \'simple-page__pr-inline-msg--err\' : \'\'">{{ handshakeBanner.text }}</div>\
                  <div v-if="copyLinkBanner" class="simple-page__pr-inline-msg">{{ copyLinkBanner }}</div>\
                </div>\
                <div class="simple-page__flow-mono simple-page__flow-mono--pr-sum-line">{{ orderAmountsLine(resolvePaymentRequest) }}<template v-if="isCommissionerIntermediary"><span class="simple-page__flow-mono-comm">{{ dealFlowStableCommissionSuffix() }}</span></template></div>\
              </div>\
              <span v-if="dealPrTermsPhase && resolvePaymentRequest && resolvePaymentRequest.expires_at && !resolvePaymentRequest.deactivated_at" class="simple-page__flow-deadline simple-page__flow-deadline--pr-split" role="status" :aria-label="t(\'main.simple.deal_flow_deadline_aria\')">\
                <svg class="simple-page__ico-clock simple-page__ico-clock--flow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">\
                  <circle cx="12" cy="12" r="10" stroke-linecap="round"/>\
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l4 2"/>\
                </svg>\
                <span class="simple-page__flow-deadline-text">{{ formatExpiryCountdown(resolvePaymentRequest) }}</span>\
              </span>\
              <div class="simple-page__flow-status" :class="{ \'simple-page__flow-status--deactivated\': dealPrDeactivated }">{{ dealPrFlowStatusLabel }}</div>\
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
                {{ dealLockboxHintEscrowFromPr(resolvePaymentRequest) || t(\'main.simple.lockbox_inner_placeholder\') }}\
              </div>\
              <div v-if="!dealPrDeactivated && dealPrExpiredDuringTerms" class="simple-page__lockbox-pending-foot" role="status">\
                <p class="simple-page__lockbox-pending-text">{{ t(\'main.simple.lockbox_terms_expired\') }}</p>\
              </div>\
              <div v-else-if="!dealPrDeactivated" class="simple-page__lockbox-pending-foot" role="status">\
                <div class="simple-page__lockbox-spinner" aria-hidden="true"></div>\
                <p class="simple-page__lockbox-pending-text">{{ (resolvePaymentRequest && resolvePaymentRequest.owner_confirm_pending) ? t(\'main.simple.lockbox_owner_confirm_pending\') : t(\'main.simple.lockbox_terms_pending_detail\') }}</p>\
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
                  <div class="simple-page__flow-mono">{{ dealViewStatReceiveEscrowTotal() }}</div>\
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
          <div v-if="resolvePaymentRequest" class="simple-page__flow-shell" style="margin-bottom:0.75rem">\
            <div class="simple-page__flow-row" :class="{ \'simple-page__flow-row--pr-split\': true }">\
              <div class="simple-page__flow-icon">\
                <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V7a2 2 0 00-2-2h-2.5M4 13V7a2 2 0 012-2h2.5M8.5 19h7M12 5v14"/></svg>\
              </div>\
              <div class="simple-page__flow-body">\
                <div class="simple-page__flow-title-row" :class="{ \'simple-page__flow-title-row--pr-tools\': true }">\
                  <span class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_offer_title\') }}</span>\
                </div>\
                <div class="simple-page__flow-mono simple-page__flow-mono--pr-sum-line">{{ orderAmountsLine(resolvePaymentRequest) }}</div>\
              </div>\
            </div>\
          </div>\
          <div class="simple-page__flow-shell">\
            <div class="simple-page__flow-row">\
              <div class="simple-page__flow-icon">\
                <svg class="simple-page__svg--lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>\
              </div>\
              <div class="simple-page__flow-body">\
                <div class="simple-page__flow-title">{{ t(\'main.simple.deal_flow_deal_title\') }}</div>\
                <div class="simple-page__flow-mono">\
                  <span v-if="resolveDealPaymentRequestPk" style="color:var(--simple-muted);font-weight:700">#{{ resolveDealPaymentRequestPk }}</span>\
                  <span v-if="resolveDealPaymentRequestHeading" style="margin-left:0.45rem">{{ resolveDealPaymentRequestHeading }}</span>\
                  <span style="margin-left:0.45rem">{{ dealDealLabelPreview() }} · {{ resolveDeal.uid }}</span>\
                </div>\
                <div v-if="resolveDeal && resolveDeal.signers" class="simple-page__flow-mono" style="margin-top:0.4rem;color:var(--simple-muted);font-size:12px;line-height:1.45">\
                  <div><span style="font-weight:700">Sender:</span> {{ (resolveDeal.signers.sender && resolveDeal.signers.sender.address) || \'—\' }}</div>\
                  <div><span style="font-weight:700">Receiver:</span> {{ (resolveDeal.signers.receiver && resolveDeal.signers.receiver.address) || \'—\' }}</div>\
                  <div><span style="font-weight:700">Arbiter:</span> {{ (resolveDeal.signers.arbiter && resolveDeal.signers.arbiter.address) || \'—\' }}</div>\
                </div>\
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
    <span>{{ fabProtectedBadgeLabel }}</span>\
  </div>\
</div>'
    });
})();
