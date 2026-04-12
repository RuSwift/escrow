/**
 * Vue 2 компонент: Мой Бизнес. Интерфейс из _temp/MyBusiness.vue.
 * Управление платежными сервисами (направления) и контрагентами (партнерская сеть).
 * Модалка multisig: multisig_config_modal.js → <multisig-config-modal>.
 * Справка по направлению: new_service_help_modal.js → <new-service-help-modal>.
 * Форма реквизитов (просмотр / редактирование): payment_form_preview_modal.js → <payment-form-preview-modal>.
 * Создание и полное редактирование направления: одна модалка (editingExchangeServiceId → PATCH).
 */
(function() {
    var PAYMENT_CODE_AC_DEBOUNCE_MS = 280;
    var PAYMENT_CODE_AC_LIMIT = 50;
    var CASH_CITY_AC_DEBOUNCE_MS = 280;
    var CASH_CITY_AC_LIMIT = 50;
    var FIAT_AC_DEBOUNCE_MS = 280;
    var FIAT_AC_LIMIT = 50;
    /** Таймаут fetch фиатного autocomplete: иначе при зависании бэка индикатор «Загрузка…» не сбрасывается. */
    var FIAT_AC_FETCH_TIMEOUT_MS = 15000;
    var PAYMENT_CODE_FETCH_TIMEOUT_MS = 15000;
    var CRYPTO_OPTIONS = ['USDT TRC20', 'A7A5 TRC20'];
    /** Подписи UI → поля API (синхронно с дефолтным каталогом collateral stablecoin). */
    var CRYPTO_META = {
        'USDT TRC20': {
            symbol: 'USDT',
            network: 'TRON',
            contract_address: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
            base_currency: 'USD'
        },
        'A7A5 TRC20': {
            symbol: 'A7A5',
            network: 'TRON',
            contract_address: 'TLeVfrdym8RoJreJ23dAGyfJDygRtiWKBZ',
            base_currency: 'RUB'
        }
    };

    function unwrapApiRoot(data) {
        if (data && data.root && typeof data.root === 'object') return data.root;
        return data;
    }

    /** Заголовки JSON API как в fetchCreateModalRatios (Bearer из localStorage). */
    function mainAppJsonFetchHeaders() {
        var h = { Accept: 'application/json' };
        try {
            var key = (typeof window !== 'undefined' && window.main_auth_token_key)
                ? window.main_auth_token_key
                : 'main_auth_token';
            var token = localStorage.getItem(key);
            if (token) h.Authorization = 'Bearer ' + token;
        } catch (e) {}
        return h;
    }

    /** Сколько USD в 1 единице фиата по строкам одного движка (как в ExchangePair на бэке). */
    function usdPerOneFiatFromEngineRows(rows, fiat) {
        if (!Array.isArray(rows)) return null;
        var i;
        var row;
        var p;
        var r;
        for (i = 0; i < rows.length; i++) {
            row = rows[i];
            p = row && row.pair;
            if (!p || typeof p.ratio !== 'number' || !isFinite(p.ratio) || p.ratio <= 0) continue;
            r = p.ratio;
            if (row.base === 'USD' && row.quote === fiat) return 1 / r;
            if (row.base === fiat && row.quote === 'USD') return r;
        }
        return null;
    }

    function resolveRatiosEngineKey(ratiosRaw, preferred) {
        if (!ratiosRaw || typeof ratiosRaw !== 'object') return null;
        var keys = Object.keys(ratiosRaw).filter(function(k) {
            return Array.isArray(ratiosRaw[k]);
        });
        if (!keys.length) return null;
        var p = (preferred || '').trim().toLowerCase();
        var i;
        if (p) {
            for (i = 0; i < keys.length; i++) {
                if (keys[i].toLowerCase() === p) return keys[i];
            }
        }
        for (i = 0; i < keys.length; i++) {
            if (keys[i].toLowerCase() === 'forex') return keys[i];
        }
        return keys.sort()[0];
    }

    /**
     * Разбор суммы из поля ввода (пробелы, тысячные запятые/точки en, десятичная «10,5»).
     */
    function mainAppLocale() {
        if (typeof window !== 'undefined' && window.__LOCALE__) {
            return String(window.__LOCALE__).trim() || 'en';
        }
        return 'en';
    }

    /** Локаль для GET /v1/autocomplete/cities — как язык UI (профиль спейса / Vue i18n). */
    function autocompleteUiLocale(vm) {
        var raw = '';
        try {
            if (vm && vm.$i18n && vm.$i18n.locale) {
                raw = String(vm.$i18n.locale);
            }
        } catch (e) {}
        if (!raw) raw = mainAppLocale();
        var code = String(raw).trim().split('-')[0].toLowerCase();
        return code === 'ru' ? 'ru' : 'en';
    }

    function parseFiatAmountInputString(str) {
        var s = String(str == null ? '' : str).replace(/[\s\u00a0\u202f]/g, '');
        if (!s) return NaN;
        var hasComma = s.indexOf(',') >= 0;
        var hasDot = s.indexOf('.') >= 0;
        if (hasComma && hasDot) {
            if (s.lastIndexOf(',') > s.lastIndexOf('.')) {
                s = s.replace(/\./g, '').replace(',', '.');
            } else {
                s = s.replace(/,/g, '');
            }
        } else if (hasComma && !hasDot) {
            var parts = s.split(',');
            if (parts.length === 2 && parts[1].length <= 2) {
                s = parts[0].replace(/\./g, '') + '.' + parts[1];
            } else {
                s = s.replace(/,/g, '');
            }
        } else {
            s = s.replace(/,/g, '');
        }
        var n = parseFloat(s);
        return isFinite(n) ? n : NaN;
    }

    function usdPerOneFiatFromRatios(ratiosRaw, fiatCode, preferredEngineKey) {
        var f = (fiatCode || '').trim().toUpperCase();
        if (!f) return null;
        if (f === 'USD') return 1;
        if (!ratiosRaw || typeof ratiosRaw !== 'object') return null;
        var eng = resolveRatiosEngineKey(ratiosRaw, preferredEngineKey);
        var u;
        if (eng && ratiosRaw[eng]) {
            u = usdPerOneFiatFromEngineRows(ratiosRaw[eng], f);
            if (u != null) return u;
        }
        var keys = Object.keys(ratiosRaw).filter(function(k) {
            return Array.isArray(ratiosRaw[k]);
        });
        var j;
        for (j = 0; j < keys.length; j++) {
            u = usdPerOneFiatFromEngineRows(ratiosRaw[keys[j]], f);
            if (u != null) return u;
        }
        return null;
    }

    /** Подобрать опцию селекта стейбла по полям API. */
    function resolveCryptoOptionFromApi(api) {
        if (!api || typeof api !== 'object') return CRYPTO_OPTIONS[0] || 'USDT TRC20';
        var sym = (api.stablecoin_symbol || '').trim();
        var net = (api.network || '').trim().toUpperCase();
        var ca = (api.contract_address || '').trim();
        var k;
        var m;
        for (k in CRYPTO_META) {
            if (!Object.prototype.hasOwnProperty.call(CRYPTO_META, k)) continue;
            m = CRYPTO_META[k];
            if (m.symbol === sym && String(m.network).toUpperCase() === net && m.contract_address === ca) return k;
        }
        for (k in CRYPTO_META) {
            if (!Object.prototype.hasOwnProperty.call(CRYPTO_META, k)) continue;
            m = CRYPTO_META[k];
            if (m.symbol === sym && String(m.network).toUpperCase() === net) return k;
        }
        return CRYPTO_OPTIONS[0] || 'USDT TRC20';
    }

    function isoToDatetimeLocal(iso) {
        if (!iso) return '';
        var d = new Date(iso);
        if (isNaN(d.getTime())) return '';
        var pad = function(n) { return n < 10 ? '0' + n : String(n); };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
            + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    function datetimeLocalToIso(local) {
        if (local == null || String(local).trim() === '') return null;
        var d = new Date(local);
        if (isNaN(d.getTime())) return null;
        return d.toISOString();
    }

    function mapExchangeItemFromApi(it) {
        var rt = 'request';
        if (it.rate_mode === 'ratios') rt = 'forex';
        else if (it.rate_mode === 'manual') rt = 'manual';
        var comm = 0;
        if (it.fee_tiers && it.fee_tiers.length) {
            comm = parseFloat(it.fee_tiers[0].fee_percent) || 0;
        } else if (it.ratios_commission_percent != null) {
            comm = parseFloat(it.ratios_commission_percent) || 0;
        }
        var cry = (it.stablecoin_symbol || '') + ' ' + String(it.network || '').toUpperCase();
        var vr = it.verification_requirements && typeof it.verification_requirements === 'object'
            ? it.verification_requirements
            : {};
        var cash = vr.cash === true;
        var cashCities = Array.isArray(vr.cash_cities) ? vr.cash_cities : [];
        return {
            id: it.id,
            type: it.service_type === 'on_ramp' ? 'onRamp' : 'offRamp',
            title: (it.title || '').trim(),
            fiatCurrency: it.fiat_currency_code,
            cryptoCurrency: cry,
            rateType: rt,
            commission: comm,
            status: it.is_active ? 'active' : 'paused',
            description: it.description || '',
            payment_code: it.payment_code || '',
            rate_mode: it.rate_mode,
            cash: cash,
            cashCities: cashCities,
            spaceWalletId: it.space_wallet_id != null ? it.space_wallet_id : '',
            _api: it
        };
    }

    Vue.component('my-business', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                services: [],
                partners: [
                    { id: 'p1', name: 'GlobalPay Solutions', serviceType: 'onRamp (EUR/USDT)', baseCommission: 0.5, myCommission: 0.3, status: 'connected' },
                    { id: 'p2', name: 'CryptoBridge Ltd', serviceType: 'offRamp (GBP/USDT)', baseCommission: 0.8, myCommission: 0.5, status: 'connected' }
                ],
                showCreateModal: false,
                /** Редактирование существующего exchange_services; null — режим создания. */
                editingExchangeServiceId: null,
                showNewServiceHelpModal: false,
                exchangeServicesLoading: false,
                exchangeServicesError: null,
                exchangeSaving: false,
                showFormPreviewModal: false,
                formPreviewCode: '',
                formModalVariant: 'preview',
                formModalInitialSchema: {},
                formModalServiceId: null,
                showPartnerModal: false,
                newService: {
                    type: 'onRamp',
                    title: '',
                    fiatCurrency: '',
                    cryptoCurrency: 'USDT TRC20',
                    rateType: 'forex',
                    commission: 1.0,
                    minFiat: 1,
                    maxFiat: 1000000,
                    description: '',
                    payment_code: '',
                    ratiosEngineKey: 'forex',
                    cash: false,
                    cashCities: [],
                    cashCityInput: '',
                    _paymentCodeBackup: '',
                    requisites_form_schema: {},
                    manualRate: null,
                    manualRateValidUntil: '',
                    spaceWalletId: ''
                },
                newPartner: {
                    name: '',
                    serviceType: '',
                    baseCommission: 0.5,
                    myCommission: 0.3
                },
                cryptoOptions: ['USDT TRC20', 'A7A5 TRC20'],
                rampWallets: [],
                /** ID корп. кошелька = primary wallet спейса (если список пуст). С бэка: GET exchange-wallets. */
                primaryRampWalletId: null,
                rampLoading: false,
                rampError: null,
                showRampModal: false,
                rampEditingId: null,
                rampForm: {
                    name: '',
                    role: 'external',
                    blockchain: 'tron',
                    tron_address: '',
                    ethereum_address: '',
                    mnemonic: '',
                    participant_sub_id: null
                },
                rampSaving: false,
                rampParticipants: [],
                rampAddrOpen: false,
                rampAddrBlurTimer: null,
                rampExternalCustom: false,
                rampBalancesByWalletId: {},
                rampBalancesLoading: false,
                rampBalancesError: null,
                rampBalancesRowRefreshingId: null,
                showRampMultisigWizard: false,
                rampMultisigWizardWallet: null,
                rampWalletsExpanded: true,
                /** Показ autocomplete по фиату: GET /v1/autocomplete/currencies?is_fiat=true (как guarantor.js). */
                fiatAutocompleteOpen: false,
                fiatCurrencySuggestions: [],
                fiatCurrencyLoading: false,
                fiatCurrencyNoHits: false,
                fiatCurrencyFetchGen: 0,
                fiatCurrencyTimer: null,
                /** Autocomplete кодов оплаты: GET /v1/autocomplete/directions?cur=… */
                paymentCodeAutocompleteOpen: false,
                paymentCodeSuggestions: [],
                paymentCodeTotalForCur: null,
                paymentCodeNoHits: false,
                paymentCodeLoading: false,
                paymentCodeFetchGen: 0,
                paymentCodeTimer: null,
                /** GET /v1/autocomplete/cities — города из bc.yaml (наличные). */
                cashCityAutocompleteOpen: false,
                cashCitySuggestions: [],
                cashCityLoading: false,
                cashCityFetchGen: 0,
                cashCityTimer: null,
                /** Снимок GET /v1/dashboard/ratios для ориентира лимитов в USD в модалке создания сервиса. */
                createModalRatiosRaw: null,
                /** После завершения запроса котировок (успех или ошибка) — чтобы не показывать «курсы не найдены» до ответа. */
                createModalRatiosFetchDone: false,
                /** Отображаемые строки лимитов фиата (с группировкой разрядов); числа — в newService.minFiat / maxFiat. */
                createModalMinFiatText: '1',
                createModalMaxFiatText: '1000000',
                /** Фильтр карточек направлений: null — все, onRamp / offRamp — только тип. */
                serviceTypeFilter: null
            };
        },
        mounted: function() {
            this.fetchUiPrefs();
            this.fetchRampWallets();
            this.fetchExchangeServices();
            this.syncCreateModalFiatLimitTexts();
        },
        computed: {
            onRampCount: function() { return this.services.filter(function(s) { return s.type === 'onRamp'; }).length; },
            offRampCount: function() { return this.services.filter(function(s) { return s.type === 'offRamp'; }).length; },
            filteredServices: function() {
                var f = this.serviceTypeFilter;
                if (!f) return this.services;
                return this.services.filter(function(s) { return s.type === f; });
            },
            rampParticipantCandidates: function() {
                var taken = {};
                (this.rampWallets || []).forEach(function(w) {
                    var a = (w.tron_address || '').trim();
                    if (a) taken[a] = true;
                });
                return (this.rampParticipants || []).filter(function(p) {
                    if ((p.blockchain || '').toLowerCase() !== 'tron') return false;
                    var addr = (p.wallet_address || '').trim();
                    return addr && !taken[addr];
                });
            },
            rampAddressPickerParticipants: function() {
                var list = (this.rampParticipantCandidates || []).slice();
                var sid = this.rampForm.participant_sub_id;
                if (sid == null) return list;
                var found = list.some(function(p) { return p.id === sid; });
                if (found) return list;
                (this.rampParticipants || []).forEach(function(p) {
                    if (p.id === sid) list.unshift(p);
                });
                return list;
            },
            rampSaveAddDisabled: function() {
                if (this.rampEditingId) return false;
                if (this.rampForm.role === 'multisig') {
                    return !(this.rampForm.name || '').trim();
                }
                if (this.rampForm.participant_sub_id != null) return false;
                if (!this.rampExternalCustom) return true;
                return !(this.rampForm.name || '').trim() || !(this.rampForm.tron_address || '').trim();
            },
            rampSaveEditDisabled: function() {
                if (!this.rampEditingId) return false;
                return !(this.rampForm.name || '').trim()
                    || !(this.rampForm.tron_address || '').trim();
            },
            rampExternalWalletCount: function() {
                return (this.rampWallets || []).filter(function(w) { return w.role === 'external'; }).length;
            },
            rampMultisigWalletCount: function() {
                return (this.rampWallets || []).filter(function(w) { return w.role === 'multisig'; }).length;
            },
            rampAggregatedBalanceRows: function() {
                var sums = {};
                var self = this;
                (this.rampWallets || []).forEach(function(rw) {
                    var bag = self.rampBalancesByWalletId[rw.id];
                    if (!bag || !bag.rows) return;
                    bag.rows.forEach(function(br) {
                        var sym = String(br.symbol || '').trim();
                        if (!sym) return;
                        var n = parseFloat(String(br.amount == null ? '0' : br.amount).replace(/,/g, ''), 10);
                        if (!isFinite(n)) n = 0;
                        sums[sym] = (sums[sym] || 0) + n;
                    });
                });
                return Object.keys(sums).sort().map(function(sym) {
                    return { symbol: sym, amount: sums[sym] };
                });
            },
            createModalHasFiat: function() {
                return !!(this.newService.fiatCurrency || '').trim();
            },
            /** Нормализованный трёхбуквенный ISO-код или '' если ввод неполный/неверный. */
            createModalFiatIso3: function() {
                var t = (this.newService.fiatCurrency || '').trim().toUpperCase();
                return /^[A-Z]{3}$/.test(t) ? t : '';
            },
            /** Есть котировка к USD в снимке дашборда (USD всегда без запроса). */
            createModalFiatRatesOk: function() {
                if (!this.createModalHasFiat) return false;
                var iso = this.createModalFiatIso3;
                if (!iso) return false;
                if (iso === 'USD') return true;
                if (!this.createModalRatiosFetchDone) return false;
                var per = usdPerOneFiatFromRatios(
                    this.createModalRatiosRaw,
                    iso,
                    this.newService.ratiosEngineKey
                );
                return per != null;
            },
            /** Неверный код или нет пары в снимке после загрузки — честное предупреждение, лимиты остаются доступны. */
            createModalShowRatesNotFound: function() {
                if (!this.createModalHasFiat) return false;
                var iso = this.createModalFiatIso3;
                if (!iso) return true;
                if (iso === 'USD') return false;
                if (!this.createModalRatiosFetchDone) return false;
                return usdPerOneFiatFromRatios(
                    this.createModalRatiosRaw,
                    iso,
                    this.newService.ratiosEngineKey
                ) == null;
            },
            createModalFiatUsdHintLine: function() {
                if (!this.createModalFiatRatesOk) return '';
                var fiat = this.createModalFiatIso3;
                if (!fiat) return '';
                var min = parseFloat(this.newService.minFiat);
                var max = parseFloat(this.newService.maxFiat);
                if (!isFinite(min) || !isFinite(max)) return '';
                var per = usdPerOneFiatFromRatios(
                    this.createModalRatiosRaw,
                    fiat,
                    this.newService.ratiosEngineKey
                );
                if (per == null) return '';
                return this.$t('main.my_business.fiat_limits_usd_hint', {
                    min: this.formatUsdApproxForHint(min * per),
                    max: this.formatUsdApproxForHint(max * per)
                });
            },
            /** Наличные: автокод CASH+FIAT и блокировка поля кода при >=1 городе. */
            cashLocked: function() {
                return !!(this.newService.cash
                    && (this.newService.cashCities || []).length >= 1
                    && this.createModalFiatIso3);
            },
            /** offRamp: выбранный id или primary при пустом списке корп. кошельков. */
            offRampEffectiveWalletId: function() {
                if (this.newService.type !== 'offRamp') return null;
                var sw = this.newService.spaceWalletId;
                if (sw !== '' && sw !== null && sw !== undefined && isFinite(Number(sw))) {
                    return Number(sw);
                }
                if (!(this.rampWallets || []).length && this.primaryRampWalletId != null) {
                    return Number(this.primaryRampWalletId);
                }
                return null;
            },
            createModalLaunchDisabled: function() {
                if (this.exchangeSaving) return true;
                if (!(this.newService.fiatCurrency || '').trim()) return true;
                if (!(this.newService.title || '').trim()) return true;
                if (this.newService.cash) {
                    if (!this.createModalFiatIso3) return true;
                    if (!(this.newService.cashCities || []).length) return true;
                }
                if (this.newService.type === 'offRamp') {
                    var oid = this.offRampEffectiveWalletId;
                    if (oid == null || !isFinite(Number(oid))) return true;
                }
                if (this.newService.rateType === 'manual') {
                    var mr = parseFloat(this.newService.manualRate);
                    if (!isFinite(mr) || mr <= 0) return true;
                }
                return false;
            },
            isEditExchangeModal: function() {
                return this.editingExchangeServiceId != null;
            }
        },
        methods: {
            serviceRateLabel: function(s) {
                if (!s) return '';
                if (s.rateType === 'forex') return this.$t('main.my_business.rate_forex');
                if (s.rateType === 'manual') return this.$t('main.my_business.rate_manual');
                return this.$t('main.my_business.rate_request');
            },
            openCreateServiceModal: function() {
                this.resetNewServiceForm();
                this.exchangeServicesError = null;
                this.fiatAutocompleteOpen = false;
                this.showCreateModal = true;
                this.fetchCreateModalRatios();
                this.applyPrimaryRampWalletFallback();
            },
            toggleServiceTypeFilter: function(type) {
                if (this.serviceTypeFilter === type) {
                    this.serviceTypeFilter = null;
                } else {
                    this.serviceTypeFilter = type;
                }
            },
            setNewServiceTypeOnRamp: function() {
                this.newService.type = 'onRamp';
            },
            setNewServiceTypeOffRamp: function() {
                this.newService.type = 'offRamp';
                this.applyPrimaryRampWalletFallback();
            },
            applyPrimaryRampWalletFallback: function() {
                if (this.newService.type !== 'offRamp') return;
                if ((this.rampWallets || []).length) return;
                if (this.primaryRampWalletId == null) return;
                this.newService.spaceWalletId = this.primaryRampWalletId;
            },
            closeCreateModal: function() {
                this.showCreateModal = false;
                this.resetNewServiceForm();
            },
            hydrateNewServiceFromApi: function(api) {
                if (!api || typeof api !== 'object') return;
                var vr = api.verification_requirements && typeof api.verification_requirements === 'object'
                    ? api.verification_requirements
                    : {};
                var cash = vr.cash === true;
                var cashCities = Array.isArray(vr.cash_cities)
                    ? vr.cash_cities.map(function(c) {
                        if (c && typeof c === 'object') {
                            return { id: c.id, name: String(c.name || '').trim() };
                        }
                        if (typeof c === 'string') return { name: c.trim() };
                        return { name: '' };
                    }).filter(function(x) { return x.name; })
                    : [];
                var rt = 'request';
                if (api.rate_mode === 'ratios') rt = 'forex';
                else if (api.rate_mode === 'manual') rt = 'manual';
                var comm = 1;
                if (api.fee_tiers && api.fee_tiers.length) {
                    comm = parseFloat(api.fee_tiers[0].fee_percent) || 1;
                } else if (api.ratios_commission_percent != null) {
                    comm = parseFloat(String(api.ratios_commission_percent)) || 1;
                }
                if (!isFinite(comm)) comm = 1;
                var req = api.requisites_form_schema && typeof api.requisites_form_schema === 'object'
                    ? JSON.parse(JSON.stringify(api.requisites_form_schema))
                    : {};
                var mr = api.manual_rate != null ? parseFloat(String(api.manual_rate)) : null;
                if (!isFinite(mr)) mr = null;
                this.newService = {
                    type: api.service_type === 'on_ramp' ? 'onRamp' : 'offRamp',
                    title: (api.title || '').trim(),
                    fiatCurrency: (api.fiat_currency_code || '').trim(),
                    cryptoCurrency: resolveCryptoOptionFromApi(api),
                    rateType: rt,
                    commission: comm,
                    minFiat: parseFloat(String(api.min_fiat_amount)) || 1,
                    maxFiat: parseFloat(String(api.max_fiat_amount)) || 1000000,
                    description: api.description || '',
                    payment_code: api.payment_code || '',
                    ratiosEngineKey: (api.ratios_engine_key && String(api.ratios_engine_key).trim())
                        ? String(api.ratios_engine_key).trim()
                        : 'forex',
                    cash: cash,
                    cashCities: cashCities,
                    cashCityInput: '',
                    _paymentCodeBackup: '',
                    requisites_form_schema: req,
                    manualRate: mr,
                    manualRateValidUntil: isoToDatetimeLocal(api.manual_rate_valid_until),
                    spaceWalletId: api.space_wallet_id != null ? api.space_wallet_id : ''
                };
                this.syncCreateModalFiatLimitTexts();
            },
            openEditExchangeServiceModal: function(s) {
                if (!s || !s._api) return;
                this.resetNewServiceForm(true);
                this.editingExchangeServiceId = s.id;
                this.hydrateNewServiceFromApi(s._api);
                this.exchangeServicesError = null;
                this.fiatAutocompleteOpen = false;
                this.showCreateModal = true;
                this.fetchCreateModalRatios();
            },
            buildExchangeServicePayload: function(forPatch) {
                var meta = CRYPTO_META[this.newService.cryptoCurrency] || CRYPTO_META['USDT TRC20'];
                var rateModeUi = this.newService.rateType;
                var rateMode = rateModeUi === 'forex' ? 'ratios' : (rateModeUi === 'manual' ? 'manual' : 'on_request');
                var comm = parseFloat(this.newService.commission);
                if (isNaN(comm)) comm = 1;
                var verif = {};
                if (this.newService.cash && (this.newService.cashCities || []).length) {
                    verif.cash = true;
                    verif.cash_cities = (this.newService.cashCities || []).map(function(c) {
                        var o = { name: String(c.name || '').trim() };
                        if (c.id != null && c.id !== '') o.id = c.id;
                        return o;
                    }).filter(function(x) { return x.name; });
                }
                var body = {
                    service_type: this.newService.type === 'onRamp' ? 'on_ramp' : 'off_ramp',
                    fiat_currency_code: this.newService.fiatCurrency.trim().toUpperCase(),
                    stablecoin_symbol: meta.symbol,
                    network: meta.network,
                    contract_address: meta.contract_address,
                    stablecoin_base_currency: meta.base_currency || null,
                    title: (this.newService.title || '').trim(),
                    description: (this.newService.description || '').trim() || null,
                    payment_code: (this.newService.payment_code || '').trim() || null,
                    rate_mode: rateMode,
                    min_fiat_amount: this.newService.minFiat,
                    max_fiat_amount: this.newService.maxFiat,
                    requisites_form_schema: (this.newService.requisites_form_schema && typeof this.newService.requisites_form_schema === 'object')
                        ? this.newService.requisites_form_schema
                        : {},
                    verification_requirements: verif
                };
                if (rateMode === 'ratios') {
                    body.manual_rate = null;
                    body.manual_rate_valid_until = null;
                    body.ratios_engine_key = (this.newService.ratiosEngineKey || '').trim() || 'forex';
                    body.ratios_commission_percent = comm;
                    if (forPatch) {
                        body.replace_fee_tiers = true;
                        body.fee_tiers = [];
                    } else {
                        body.fee_tiers = null;
                    }
                } else if (rateMode === 'on_request') {
                    body.manual_rate = null;
                    body.manual_rate_valid_until = null;
                    body.ratios_engine_key = null;
                    body.ratios_commission_percent = null;
                    var tier = { fiat_min: 0, fiat_max: 999999999, fee_percent: comm, sort_order: 0 };
                    if (forPatch) {
                        body.replace_fee_tiers = true;
                        body.fee_tiers = [tier];
                    } else {
                        body.fee_tiers = [tier];
                    }
                } else {
                    body.ratios_engine_key = null;
                    body.ratios_commission_percent = null;
                    var mrv = datetimeLocalToIso(this.newService.manualRateValidUntil);
                    body.manual_rate = this.newService.manualRate != null ? Number(this.newService.manualRate) : null;
                    body.manual_rate_valid_until = mrv;
                    var tierM = { fiat_min: 0, fiat_max: 999999999, fee_percent: comm, sort_order: 0 };
                    if (forPatch) {
                        body.replace_fee_tiers = true;
                        body.fee_tiers = [tierM];
                    } else {
                        body.fee_tiers = [tierM];
                    }
                }
                if (!forPatch) {
                    body.is_active = true;
                }
                if (this.newService.type === 'offRamp') {
                    var oid = this.offRampEffectiveWalletId;
                    body.space_wallet_id = oid != null ? parseInt(String(oid), 10) : null;
                } else {
                    body.space_wallet_id = null;
                }
                return body;
            },
            fetchCreateModalRatios: function() {
                var self = this;
                self.createModalRatiosFetchDone = false;
                return fetch('/v1/dashboard/ratios', {
                    method: 'GET',
                    headers: mainAppJsonFetchHeaders(),
                    credentials: 'include'
                })
                    .then(function(res) {
                        if (!res.ok) throw new Error('HTTP ' + res.status);
                        return res.json();
                    })
                    .then(function(data) {
                        data = unwrapApiRoot(data);
                        self.createModalRatiosRaw = data && typeof data === 'object' ? data : null;
                    })
                    .catch(function() {
                        self.createModalRatiosRaw = null;
                    })
                    .finally(function() {
                        self.createModalRatiosFetchDone = true;
                    });
            },
            formatUsdApproxForHint: function(n) {
                if (!isFinite(n)) return '—';
                var abs = Math.abs(n);
                var maxFrac = abs >= 1000 ? 0 : 2;
                return '$' + Number(n).toLocaleString('en-US', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: maxFrac
                });
            },
            selectFiat: function(fiat) {
                this.newService.fiatCurrency = fiat;
                this.fiatAutocompleteOpen = false;
                this.fiatCurrencySuggestions = [];
                this.fiatCurrencyNoHits = false;
                this.newService.payment_code = '';
                this.newService._paymentCodeBackup = '';
                this.newService.requisites_form_schema = {};
                this.paymentCodeSuggestions = [];
                this.paymentCodeAutocompleteOpen = false;
                this.paymentCodeLoading = false;
                this._abortCreateModalPaymentCodeRequest();
                this.applyCashPaymentRules();
            },
            clearCreateModalFiatCurrency: function() {
                this.newService.fiatCurrency = '';
                this._abortCreateModalFiatCurrencyRequest();
                this.newService.payment_code = '';
                this.newService._paymentCodeBackup = '';
                this.paymentCodeSuggestions = [];
                this.paymentCodeAutocompleteOpen = false;
                this.paymentCodeLoading = false;
                this._abortCreateModalPaymentCodeRequest();
                this.applyCashPaymentRules();
                this.fiatAutocompleteOpen = true;
                this.fetchCreateModalFiatCurrencies('');
                this.newService.requisites_form_schema = {};
            },
            clearCreateModalPaymentCode: function() {
                if (this.cashLocked) return;
                if (!this.createModalFiatIso3) return;
                this.newService.payment_code = '';
                this.newService.requisites_form_schema = {};
                if (this.newService.cash) this.newService._paymentCodeBackup = '';
                this.paymentCodeAutocompleteOpen = true;
                this.fetchCreateModalPaymentDirections('');
            },
            _abortCreateModalFiatCurrencyRequest: function() {
                if (this._fiatCurrencyAbortController) {
                    try {
                        this._fiatCurrencyAbortController.abort();
                    } catch (e) {}
                    this._fiatCurrencyAbortController = null;
                }
            },
            fetchCreateModalFiatCurrencies: function(q) {
                var self = this;
                if (self._fiatCurrencyTimeoutId) {
                    clearTimeout(self._fiatCurrencyTimeoutId);
                    self._fiatCurrencyTimeoutId = null;
                }
                self._abortCreateModalFiatCurrencyRequest();
                var fetchOpts = {
                    credentials: 'include',
                    headers: mainAppJsonFetchHeaders()
                };
                if (typeof AbortController !== 'undefined') {
                    self._fiatCurrencyAbortController = new AbortController();
                    fetchOpts.signal = self._fiatCurrencyAbortController.signal;
                }
                self.fiatCurrencyFetchGen += 1;
                var gen = self.fiatCurrencyFetchGen;
                self.fiatCurrencyLoading = true;
                self.fiatCurrencyNoHits = false;
                var url =
                    '/v1/autocomplete/currencies?is_fiat=true&limit=' +
                    encodeURIComponent(String(FIAT_AC_LIMIT)) +
                    (q ? '&q=' + encodeURIComponent(q) : '');
                if (self._fiatCurrencyAbortController && FIAT_AC_FETCH_TIMEOUT_MS > 0) {
                    self._fiatCurrencyTimeoutId = setTimeout(function() {
                        self._fiatCurrencyTimeoutId = null;
                        try {
                            if (self._fiatCurrencyAbortController) self._fiatCurrencyAbortController.abort();
                        } catch (e) {}
                    }, FIAT_AC_FETCH_TIMEOUT_MS);
                }
                fetch(url, fetchOpts)
                    .then(function(r) {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    })
                    .then(function(data) {
                        if (gen !== self.fiatCurrencyFetchGen) return;
                        var payload = data && data.root && typeof data.root === 'object' ? data.root : data;
                        var items = (payload && payload.items) ? payload.items : [];
                        self.fiatCurrencySuggestions = items;
                        self.fiatCurrencyNoHits =
                            items.length === 0 && q && String(q).trim().length >= 1;
                        self.fiatAutocompleteOpen = true;
                    })
                    .catch(function(err) {
                        if (err && err.name === 'AbortError') return;
                        if (gen !== self.fiatCurrencyFetchGen) return;
                        self.fiatCurrencySuggestions = [];
                        self.fiatCurrencyNoHits = false;
                    })
                    .then(function() {
                        if (self._fiatCurrencyTimeoutId) {
                            clearTimeout(self._fiatCurrencyTimeoutId);
                            self._fiatCurrencyTimeoutId = null;
                        }
                        if (gen !== self.fiatCurrencyFetchGen) return;
                        self.fiatCurrencyLoading = false;
                    });
            },
            onFiatInputFocus: function() {
                this.fiatAutocompleteOpen = true;
                this.fetchCreateModalFiatCurrencies((this.newService.fiatCurrency || '').trim());
            },
            onFiatInputInput: function() {
                this.fiatAutocompleteOpen = true;
                var self = this;
                if (self.fiatCurrencyTimer) clearTimeout(self.fiatCurrencyTimer);
                self.fiatCurrencyTimer = setTimeout(function() {
                    self.fetchCreateModalFiatCurrencies((self.newService.fiatCurrency || '').trim());
                }, FIAT_AC_DEBOUNCE_MS);
            },
            onFiatInputBlur: function() {
                var self = this;
                setTimeout(function() {
                    self.fiatAutocompleteOpen = false;
                }, 200);
            },
            fetchCreateModalPaymentDirections: function(q) {
                var iso = this.createModalFiatIso3;
                if (!iso) {
                    this.paymentCodeSuggestions = [];
                    this.paymentCodeTotalForCur = null;
                    this.paymentCodeLoading = false;
                    this._abortCreateModalPaymentCodeRequest();
                    return;
                }
                var self = this;
                if (self._paymentCodeTimeoutId) {
                    clearTimeout(self._paymentCodeTimeoutId);
                    self._paymentCodeTimeoutId = null;
                }
                self._abortCreateModalPaymentCodeRequest();
                var fetchOpts = {
                    credentials: 'include',
                    headers: mainAppJsonFetchHeaders()
                };
                if (typeof AbortController !== 'undefined') {
                    self._paymentCodeAbortController = new AbortController();
                    fetchOpts.signal = self._paymentCodeAbortController.signal;
                }
                self.paymentCodeFetchGen += 1;
                var gen = self.paymentCodeFetchGen;
                self.paymentCodeLoading = true;
                self.paymentCodeNoHits = false;
                var url =
                    '/v1/autocomplete/directions?locale=' +
                    encodeURIComponent(mainAppLocale()) +
                    '&limit=' +
                    encodeURIComponent(String(PAYMENT_CODE_AC_LIMIT)) +
                    '&cur=' +
                    encodeURIComponent(iso) +
                    (q ? '&q=' + encodeURIComponent(q) : '');
                if (self._paymentCodeAbortController && PAYMENT_CODE_FETCH_TIMEOUT_MS > 0) {
                    self._paymentCodeTimeoutId = setTimeout(function() {
                        self._paymentCodeTimeoutId = null;
                        try {
                            if (self._paymentCodeAbortController) self._paymentCodeAbortController.abort();
                        } catch (e) {}
                    }, PAYMENT_CODE_FETCH_TIMEOUT_MS);
                }
                fetch(url, fetchOpts)
                    .then(function(r) {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    })
                    .then(function(data) {
                        if (gen !== self.paymentCodeFetchGen) return;
                        var payload = data && data.root && typeof data.root === 'object' ? data.root : data;
                        self.paymentCodeSuggestions = (payload && payload.items) ? payload.items : [];
                        self.paymentCodeTotalForCur =
                            payload && typeof payload.total_for_cur === 'number' ? payload.total_for_cur : null;
                        self.paymentCodeNoHits =
                            self.paymentCodeSuggestions.length === 0 && q && String(q).trim().length >= 1;
                        self.paymentCodeAutocompleteOpen = true;
                    })
                    .catch(function(err) {
                        if (err && err.name === 'AbortError') return;
                        if (gen !== self.paymentCodeFetchGen) return;
                        self.paymentCodeSuggestions = [];
                        self.paymentCodeTotalForCur = null;
                        self.paymentCodeNoHits = true;
                    })
                    .then(function() {
                        if (self._paymentCodeTimeoutId) {
                            clearTimeout(self._paymentCodeTimeoutId);
                            self._paymentCodeTimeoutId = null;
                        }
                        if (gen !== self.paymentCodeFetchGen) return;
                        self.paymentCodeLoading = false;
                    });
            },
            /** Отмена предыдущего запроса автокомплита способов оплаты (новый fetch перезапускает). */
            _abortCreateModalPaymentCodeRequest: function() {
                if (this._paymentCodeAbortController) {
                    try {
                        this._paymentCodeAbortController.abort();
                    } catch (e) {}
                    this._paymentCodeAbortController = null;
                }
            },
            onPaymentCodeFocus: function() {
                if (this.cashLocked) return;
                if (!this.createModalFiatIso3) return;
                this.paymentCodeAutocompleteOpen = true;
                this.fetchCreateModalPaymentDirections((this.newService.payment_code || '').trim());
            },
            onPaymentCodeInput: function() {
                if (this.cashLocked) return;
                if (!this.createModalFiatIso3) return;
                this.paymentCodeAutocompleteOpen = true;
                var self = this;
                if (self.paymentCodeTimer) clearTimeout(self.paymentCodeTimer);
                self.paymentCodeTimer = setTimeout(function() {
                    self.fetchCreateModalPaymentDirections((self.newService.payment_code || '').trim());
                }, PAYMENT_CODE_AC_DEBOUNCE_MS);
            },
            onPaymentCodeBlur: function() {
                var self = this;
                setTimeout(function() {
                    self.paymentCodeAutocompleteOpen = false;
                }, 200);
            },
            selectPaymentCodeFromAutocomplete: function(item) {
                if (!item || !item.payment_code) return;
                this.newService.payment_code = item.payment_code;
                this.newService.requisites_form_schema = {};
                this.paymentCodeAutocompleteOpen = false;
                this.paymentCodeNoHits = false;
            },
            applyCashPaymentRules: function() {
                if (!this.newService.cash) return;
                var iso = this.createModalFiatIso3;
                var cities = this.newService.cashCities || [];
                if (cities.length >= 1 && iso) {
                    this.newService.payment_code = 'CASH' + iso;
                } else {
                    var bak = this.newService._paymentCodeBackup;
                    this.newService.payment_code = typeof bak === 'string' ? bak : '';
                }
            },
            onCashCheckboxChange: function() {
                var self = this;
                if (this.newService.cash) {
                    this.newService._paymentCodeBackup = this.newService.payment_code || '';
                    this.applyCashPaymentRules();
                } else {
                    this.newService.cashCities = [];
                    this.newService.cashCityInput = '';
                    this.cashCityAutocompleteOpen = false;
                    this.newService.payment_code = this.newService._paymentCodeBackup != null
                        ? this.newService._paymentCodeBackup
                        : '';
                    this.newService._paymentCodeBackup = '';
                    this._abortCreateModalCashCityRequest();
                }
            },
            _abortCreateModalCashCityRequest: function() {
                if (this._cashCityAbortController) {
                    try {
                        this._cashCityAbortController.abort();
                    } catch (e) {}
                    this._cashCityAbortController = null;
                }
            },
            fetchCreateModalCashCities: function(q) {
                var self = this;
                if (self._cashCityTimeoutId) {
                    clearTimeout(self._cashCityTimeoutId);
                    self._cashCityTimeoutId = null;
                }
                self._abortCreateModalCashCityRequest();
                var fetchOpts = {
                    credentials: 'include',
                    headers: mainAppJsonFetchHeaders()
                };
                if (typeof AbortController !== 'undefined') {
                    self._cashCityAbortController = new AbortController();
                    fetchOpts.signal = self._cashCityAbortController.signal;
                }
                self.cashCityFetchGen += 1;
                var gen = self.cashCityFetchGen;
                self.cashCityLoading = true;
                var url =
                    '/v1/autocomplete/cities?locale=' +
                    encodeURIComponent(autocompleteUiLocale(self)) +
                    '&limit=' +
                    encodeURIComponent(String(CASH_CITY_AC_LIMIT)) +
                    (q ? '&q=' + encodeURIComponent(q) : '');
                if (self._cashCityAbortController && FIAT_AC_FETCH_TIMEOUT_MS > 0) {
                    self._cashCityTimeoutId = setTimeout(function() {
                        self._cashCityTimeoutId = null;
                        try {
                            if (self._cashCityAbortController) self._cashCityAbortController.abort();
                        } catch (e) {}
                    }, FIAT_AC_FETCH_TIMEOUT_MS);
                }
                fetch(url, fetchOpts)
                    .then(function(r) {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    })
                    .then(function(data) {
                        if (gen !== self.cashCityFetchGen) return;
                        var payload = data && data.root && typeof data.root === 'object' ? data.root : data;
                        self.cashCitySuggestions = (payload && payload.items) ? payload.items : [];
                        self.cashCityAutocompleteOpen = true;
                    })
                    .catch(function(err) {
                        if (err && err.name === 'AbortError') return;
                        if (gen !== self.cashCityFetchGen) return;
                        self.cashCitySuggestions = [];
                    })
                    .then(function() {
                        if (self._cashCityTimeoutId) {
                            clearTimeout(self._cashCityTimeoutId);
                            self._cashCityTimeoutId = null;
                        }
                        if (gen !== self.cashCityFetchGen) return;
                        self.cashCityLoading = false;
                    });
            },
            onCashCityFocus: function() {
                if (!this.newService.cash) return;
                this.cashCityAutocompleteOpen = true;
                this.fetchCreateModalCashCities((this.newService.cashCityInput || '').trim());
            },
            onCashCityInput: function() {
                if (!this.newService.cash) return;
                this.cashCityAutocompleteOpen = true;
                var self = this;
                if (self.cashCityTimer) clearTimeout(self.cashCityTimer);
                self.cashCityTimer = setTimeout(function() {
                    self.fetchCreateModalCashCities((self.newService.cashCityInput || '').trim());
                }, CASH_CITY_AC_DEBOUNCE_MS);
            },
            onCashCityBlur: function() {
                var self = this;
                setTimeout(function() {
                    self.cashCityAutocompleteOpen = false;
                }, 200);
            },
            onCashCityInputKeydown: function(e) {
                if (!e || e.key !== 'Enter') return;
                e.preventDefault();
                var raw = (this.newService.cashCityInput || '').trim();
                if (!raw) return;
                this.addCashCityManual(raw);
            },
            addCashCityFromAutocomplete: function(item) {
                if (!item || item.name == null) return;
                var name = String(item.name).trim();
                if (!name) return;
                var id = item.id != null ? item.id : null;
                var list = this.newService.cashCities.slice();
                var exists = list.some(function(c) {
                    return (c.name || '').trim().toLowerCase() === name.toLowerCase();
                });
                if (exists) {
                    this.cashCityAutocompleteOpen = false;
                    this.newService.cashCityInput = '';
                    return;
                }
                list.push({ id: id, name: name });
                this.newService.cashCities = list;
                this.newService.cashCityInput = '';
                this.cashCityAutocompleteOpen = false;
                this.applyCashPaymentRules();
            },
            addCashCityManual: function(name) {
                var n = String(name || '').trim();
                if (!n) return;
                var list = this.newService.cashCities.slice();
                var exists = list.some(function(c) {
                    return (c.name || '').trim().toLowerCase() === n.toLowerCase();
                });
                if (exists) {
                    this.newService.cashCityInput = '';
                    this.cashCityAutocompleteOpen = false;
                    return;
                }
                list.push({ id: null, name: n });
                this.newService.cashCities = list;
                this.newService.cashCityInput = '';
                this.cashCityAutocompleteOpen = false;
                this.applyCashPaymentRules();
            },
            removeCashCity: function(index) {
                var list = (this.newService.cashCities || []).slice();
                if (index < 0 || index >= list.length) return;
                list.splice(index, 1);
                this.newService.cashCities = list;
                this.applyCashPaymentRules();
            },
            serviceCashLockedForCard: function(s) {
                return !!(s && s.cash && (s.cashCities || []).length);
            },
            serviceCashCitiesLine: function(s) {
                if (!s || !s.cash || !(s.cashCities || []).length) return '';
                var names = [];
                (s.cashCities || []).forEach(function(c) {
                    var nm = '';
                    if (c && typeof c === 'object') nm = (c.name || '').trim();
                    else if (typeof c === 'string') nm = c.trim();
                    if (nm) names.push(nm);
                });
                if (!names.length) return '';
                return this.$t('main.my_business.service_cash_cities_line', { cities: names.join(', ') });
            },
            exchangeServicesApiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/exchange-services';
            },
            resetNewServiceForm: function(keepEditing) {
                this.newService = {
                    type: 'onRamp',
                    title: '',
                    fiatCurrency: '',
                    cryptoCurrency: 'USDT TRC20',
                    rateType: 'forex',
                    commission: 1.0,
                    minFiat: 1,
                    maxFiat: 1000000,
                    description: '',
                    payment_code: '',
                    ratiosEngineKey: 'forex',
                    cash: false,
                    cashCities: [],
                    cashCityInput: '',
                    _paymentCodeBackup: '',
                    requisites_form_schema: {},
                    manualRate: null,
                    manualRateValidUntil: '',
                    spaceWalletId: ''
                };
                if (!keepEditing) {
                    this.editingExchangeServiceId = null;
                }
                this.cashCityAutocompleteOpen = false;
                this.cashCitySuggestions = [];
                this.cashCityLoading = false;
                this._abortCreateModalCashCityRequest();
                if (this._cashCityTimeoutId) {
                    clearTimeout(this._cashCityTimeoutId);
                    this._cashCityTimeoutId = null;
                }
                if (this.cashCityTimer) {
                    clearTimeout(this.cashCityTimer);
                    this.cashCityTimer = null;
                }
                this.fiatAutocompleteOpen = false;
                this.fiatCurrencySuggestions = [];
                this.fiatCurrencyNoHits = false;
                this.fiatCurrencyLoading = false;
                this._abortCreateModalFiatCurrencyRequest();
                if (this._fiatCurrencyTimeoutId) {
                    clearTimeout(this._fiatCurrencyTimeoutId);
                    this._fiatCurrencyTimeoutId = null;
                }
                if (this.fiatCurrencyTimer) {
                    clearTimeout(this.fiatCurrencyTimer);
                    this.fiatCurrencyTimer = null;
                }
                this.paymentCodeAutocompleteOpen = false;
                this.paymentCodeSuggestions = [];
                this.paymentCodeTotalForCur = null;
                this.paymentCodeNoHits = false;
                this.paymentCodeLoading = false;
                this._abortCreateModalPaymentCodeRequest();
                if (this._paymentCodeTimeoutId) {
                    clearTimeout(this._paymentCodeTimeoutId);
                    this._paymentCodeTimeoutId = null;
                }
                if (this.paymentCodeTimer) {
                    clearTimeout(this.paymentCodeTimer);
                    this.paymentCodeTimer = null;
                }
                this.syncCreateModalFiatLimitTexts();
            },
            fiatLimitsLocale: function() {
                try {
                    var loc = this.$i18n && this.$i18n.locale;
                    if (loc && String(loc).toLowerCase().indexOf('ru') === 0) return 'ru-RU';
                } catch (e) {}
                return 'en-US';
            },
            formatFiatAmountForLimits: function(n) {
                if (n == null || !isFinite(Number(n))) return '';
                return Number(n).toLocaleString(this.fiatLimitsLocale(), {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2
                });
            },
            syncCreateModalFiatLimitTexts: function() {
                this.createModalMinFiatText = this.formatFiatAmountForLimits(this.newService.minFiat);
                this.createModalMaxFiatText = this.formatFiatAmountForLimits(this.newService.maxFiat);
            },
            applyCreateModalFiatLimitTextsToNumbers: function() {
                var min = parseFiatAmountInputString(this.createModalMinFiatText);
                var max = parseFiatAmountInputString(this.createModalMaxFiatText);
                if (isFinite(min) && min >= 0) this.newService.minFiat = min;
                if (isFinite(max) && max >= 0) this.newService.maxFiat = max;
            },
            onCreateModalMinFiatLimitInput: function() {
                var n = parseFiatAmountInputString(this.createModalMinFiatText);
                if (isFinite(n) && n >= 0) this.newService.minFiat = n;
            },
            onCreateModalMinFiatLimitBlur: function() {
                var n = parseFiatAmountInputString(this.createModalMinFiatText);
                if (!isFinite(n) || n < 0) n = this.newService.minFiat;
                this.newService.minFiat = n;
                this.createModalMinFiatText = this.formatFiatAmountForLimits(n);
            },
            onCreateModalMaxFiatLimitInput: function() {
                var n = parseFiatAmountInputString(this.createModalMaxFiatText);
                if (isFinite(n) && n >= 0) this.newService.maxFiat = n;
            },
            onCreateModalMaxFiatLimitBlur: function() {
                var n = parseFiatAmountInputString(this.createModalMaxFiatText);
                if (!isFinite(n) || n < 0) n = this.newService.maxFiat;
                this.newService.maxFiat = n;
                this.createModalMaxFiatText = this.formatFiatAmountForLimits(n);
            },
            fetchExchangeServices: function() {
                var self = this;
                var base = this.exchangeServicesApiBase();
                if (!base) {
                    this.services = [];
                    return Promise.resolve();
                }
                this.exchangeServicesLoading = true;
                this.exchangeServicesError = null;
                return fetch(base, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (r.status === 403) throw new Error('403');
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        var items = (data && data.items) ? data.items : [];
                        self.services = items.map(mapExchangeItemFromApi);
                    })
                    .catch(function() {
                        self.exchangeServicesError = 'load';
                        self.services = [];
                    })
                    .then(function() {
                        self.exchangeServicesLoading = false;
                    });
            },
            saveExchangeService: function() {
                if (!(this.newService.fiatCurrency || '').trim()) return;
                if (!(this.newService.title || '').trim()) return;
                this.applyCreateModalFiatLimitTextsToNumbers();
                var self = this;
                var base = this.exchangeServicesApiBase();
                if (!base) return;
                var editId = this.editingExchangeServiceId;
                var forPatch = editId != null;
                var body = this.buildExchangeServicePayload(forPatch);
                if (forPatch) {
                    delete body.is_active;
                }
                this.exchangeSaving = true;
                var url = forPatch
                    ? base + '/' + encodeURIComponent(String(editId))
                    : base;
                var method = forPatch ? 'PATCH' : 'POST';
                fetch(url, {
                    method: method,
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        if (!r.ok) {
                            return r.json().then(function(d) { throw d; }, function() { throw new Error(String(r.status)); });
                        }
                        return forPatch ? r.json() : r.json();
                    })
                    .then(function() {
                        self.closeCreateModal();
                        return self.fetchExchangeServices();
                    })
                    .catch(function(e) {
                        console.error(forPatch ? 'exchange-service patch' : 'exchange-service create', e);
                        self.exchangeServicesError = 'save';
                    })
                    .then(function() {
                        self.exchangeSaving = false;
                    });
            },
            toggleStatus: function(id) {
                var s = this.services.find(function(x) { return x.id === id; });
                if (!s || !s._api) return;
                var self = this;
                var base = this.exchangeServicesApiBase();
                if (!base) return;
                var nextActive = !(s._api.is_active === true);
                fetch(base + '/' + encodeURIComponent(String(id)), {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ is_active: nextActive })
                })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return self.fetchExchangeServices();
                    })
                    .catch(function() {
                        self.exchangeServicesError = 'save';
                    });
            },
            deleteExchangeService: function(id) {
                if (typeof window !== 'undefined' && window.showConfirm) {
                    var self = this;
                    window.showConfirm({
                        title: this.$t('main.my_business.delete_service_confirm_title'),
                        message: this.$t('main.my_business.delete_service_confirm_message'),
                        onConfirm: function() { self._deleteExchangeService(id); }
                    });
                } else if (window.confirm(this.$t('main.my_business.delete_service_confirm_message'))) {
                    this._deleteExchangeService(id);
                }
            },
            _deleteExchangeService: function(id) {
                var self = this;
                var base = this.exchangeServicesApiBase();
                if (!base) return;
                fetch(base + '/' + encodeURIComponent(String(id)), {
                    method: 'DELETE',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include'
                })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return self.fetchExchangeServices();
                    })
                    .catch(function() {
                        self.exchangeServicesError = 'save';
                    });
            },
            openFormPreview: function(code) {
                if (this.showCreateModal && this.cashLocked) return;
                var c = (code || '').trim();
                if (!c) return;
                this.formPreviewCode = c;
                this.formModalVariant = 'preview';
                this.formModalServiceId = this.editingExchangeServiceId != null
                    ? this.editingExchangeServiceId
                    : null;
                this.formModalInitialSchema = {};
                this.showFormPreviewModal = true;
            },
            openFormPreviewForService: function(s) {
                if (this.serviceCashLockedForCard(s)) return;
                var c = (s && s.payment_code || '').trim();
                if (!c) return;
                this.formPreviewCode = c;
                this.formModalVariant = 'preview';
                this.formModalServiceId = s && s.id != null ? s.id : null;
                this.formModalInitialSchema = {};
                this.showFormPreviewModal = true;
            },
            openFormEditorNew: function() {
                if (this.cashLocked) return;
                var c = (this.newService.payment_code || '').trim();
                if (!c) return;
                this.formPreviewCode = c;
                this.formModalVariant = 'edit';
                this.formModalServiceId = this.editingExchangeServiceId != null
                    ? this.editingExchangeServiceId
                    : null;
                this.formModalInitialSchema = this.newService.requisites_form_schema
                    && typeof this.newService.requisites_form_schema === 'object'
                    ? JSON.parse(JSON.stringify(this.newService.requisites_form_schema))
                    : {};
                this.showFormPreviewModal = true;
            },
            openFormEditorForService: function(s) {
                if (this.serviceCashLockedForCard(s)) return;
                var c = (s && s.payment_code || '').trim();
                if (!c) return;
                this.formPreviewCode = c;
                this.formModalVariant = 'edit';
                this.formModalServiceId = s.id;
                var api = s._api || {};
                var rs = api.requisites_form_schema;
                this.formModalInitialSchema = rs && typeof rs === 'object'
                    ? JSON.parse(JSON.stringify(rs))
                    : {};
                this.showFormPreviewModal = true;
            },
            onRequisitesSaved: function(payload) {
                var schema = payload && payload.schema && typeof payload.schema === 'object'
                    ? payload.schema
                    : {};
                if (this.formModalServiceId != null) {
                    this.patchExchangeServiceRequisites(this.formModalServiceId, schema);
                } else {
                    this.newService.requisites_form_schema = schema;
                    this.showFormPreviewModal = false;
                }
            },
            patchExchangeServiceRequisites: function(serviceId, schema) {
                var self = this;
                var base = this.exchangeServicesApiBase();
                if (!base) return;
                this.exchangeSaving = true;
                fetch(base + '/' + encodeURIComponent(serviceId), {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ requisites_form_schema: schema || {} })
                })
                    .then(function(r) {
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function() {
                        self.showFormPreviewModal = false;
                        if (self.editingExchangeServiceId === serviceId) {
                            self.newService.requisites_form_schema = schema && typeof schema === 'object'
                                ? schema
                                : {};
                        }
                        return self.fetchExchangeServices();
                    })
                    .catch(function() {
                        self.exchangeServicesError = 'save';
                    })
                    .then(function() {
                        self.exchangeSaving = false;
                    });
            },
            openPartnerModal: function() {
                this.newPartner = { name: '', serviceType: '', baseCommission: 0.5, myCommission: 0.3 };
                this.showPartnerModal = true;
            },
            addPartner: function() {
                if (!(this.newPartner.name || '').trim()) return;
                this.partners.push({
                    id: 'p' + Date.now(),
                    name: this.newPartner.name.trim(),
                    serviceType: (this.newPartner.serviceType || '').trim() || '—',
                    baseCommission: parseFloat(this.newPartner.baseCommission) || 0,
                    myCommission: parseFloat(this.newPartner.myCommission) || 0,
                    status: 'connected'
                });
                this.showPartnerModal = false;
            },
            rampApiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/exchange-wallets';
            },
            rampSpaceParticipantsUrl: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/participants';
            },
            fetchRampParticipants: function() {
                var self = this;
                var url = this.rampSpaceParticipantsUrl();
                if (!url) {
                    this.rampParticipants = [];
                    return;
                }
                fetch(url, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) return [];
                        return r.json();
                    })
                    .then(function(data) {
                        self.rampParticipants = Array.isArray(data) ? data : [];
                    })
                    .catch(function() {
                        self.rampParticipants = [];
                    });
            },
            clearRampAddrBlurTimer: function() {
                if (this.rampAddrBlurTimer) {
                    clearTimeout(this.rampAddrBlurTimer);
                    this.rampAddrBlurTimer = null;
                }
            },
            openRampAddrDropdown: function() {
                if (this.rampEditingId || this.rampForm.role !== 'external') return;
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = true;
            },
            onRampAddrFocus: function() {
                this.openRampAddrDropdown();
            },
            onRampAddrInputClick: function() {
                this.openRampAddrDropdown();
            },
            onRampTronAddressInput: function() {
                // Пользователь вручную вводит/вставляет внешний TRON-адрес.
                // Если participant_sub_id не выбран — включаем режим custom, чтобы кнопка сохранения стала доступна.
                if (this.rampForm.participant_sub_id != null) return;
                this.rampExternalCustom = true;
                var tr = (this.rampForm.tron_address || '').trim();
                // Для custom-address backend требует name, поэтому подставим имя из адреса при пустом поле.
                if (!(this.rampForm.name || '').trim() && tr) {
                    this.rampForm.name = tr;
                }
            },
            onRampAddrFocusOut: function(e) {
                var self = this;
                if (this.rampEditingId) return;
                var rel = e.relatedTarget;
                if (rel && e.currentTarget.contains(rel)) {
                    return;
                }
                this.clearRampAddrBlurTimer();
                this.rampAddrBlurTimer = setTimeout(function() {
                    self.rampAddrOpen = false;
                    self.rampAddrBlurTimer = null;
                }, 200);
            },
            toggleRampAddrDropdown: function() {
                if (this.rampEditingId || this.rampForm.role !== 'external') return;
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = !this.rampAddrOpen;
            },
            pickRampCustomAddress: function() {
                this.clearRampAddrBlurTimer();
                this.rampForm.participant_sub_id = null;
                this.rampExternalCustom = true;
                this.rampForm.tron_address = '';
                this.rampForm.name = '';
                this.rampAddrOpen = false;
            },
            pickRampParticipantSub: function(p) {
                this.clearRampAddrBlurTimer();
                if (!p || !p.id) return;
                this.rampForm.participant_sub_id = p.id;
                this.rampExternalCustom = false;
                this.rampForm.tron_address = (p.wallet_address || '').trim();
                this.rampForm.name = ((p.nickname || '').trim()) || this.rampForm.tron_address;
                this.rampAddrOpen = false;
            },
            onRampRoleChange: function() {
                if (this.rampEditingId) return;
                this.rampForm.participant_sub_id = null;
                this.rampExternalCustom = false;
                this.rampForm.tron_address = '';
                if (this.rampForm.role === 'multisig') {
                    this.rampForm.name = '';
                }
                this.rampAddrOpen = false;
            },
            rampAuthHeaders: function() {
                var token = null;
                try {
                    var key = (typeof window !== 'undefined' && window.main_auth_token_key)
                        ? window.main_auth_token_key
                        : 'main_auth_token';
                    token = localStorage.getItem(key);
                } catch (e) {}
                var h = { 'Content-Type': 'application/json' };
                if (token) h.Authorization = 'Bearer ' + token;
                return h;
            },
            uiPrefsApiBase: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/ui-prefs';
            },
            fetchUiPrefs: function() {
                var self = this;
                var url = this.uiPrefsApiBase();
                if (!url) return Promise.resolve();
                return fetch(url, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (!r.ok) return null;
                        return r.json();
                    })
                    .then(function(data) {
                        if (!data || typeof data !== 'object') return;
                        var p = data.payload && typeof data.payload === 'object' ? data.payload : {};
                        var mb = p.my_business && typeof p.my_business === 'object' ? p.my_business : {};
                        if (typeof mb.ramp_wallets_expanded === 'boolean') {
                            self.rampWalletsExpanded = mb.ramp_wallets_expanded;
                        }
                    })
                    .catch(function() { /* ignore */ });
            },
            persistRampWalletsExpanded: function(expanded) {
                var self = this;
                this.rampWalletsExpanded = !!expanded;
                var url = this.uiPrefsApiBase();
                if (!url) return;
                fetch(url, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ my_business: { ramp_wallets_expanded: self.rampWalletsExpanded } })
                }).catch(function() { /* ignore */ });
            },
            toggleRampWalletsSection: function() {
                this.persistRampWalletsExpanded(!this.rampWalletsExpanded);
            },
            fetchRampWallets: function(opts) {
                var self = this;
                opts = opts || {};
                var skipBalances = !!opts.skipBalances;
                var base = this.rampApiBase();
                if (!base) {
                    this.rampLoading = false;
                    this.rampError = null;
                    this.rampWallets = [];
                    this.primaryRampWalletId = null;
                    return Promise.resolve();
                }
                this.rampLoading = true;
                this.rampError = null;
                return fetch(base, { method: 'GET', headers: this.rampAuthHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (r.status === 403) throw new Error('403');
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        self.rampWallets = (data && data.items) ? data.items : [];
                        self.primaryRampWalletId = (data && data.primary_ramp_wallet_id != null)
                            ? data.primary_ramp_wallet_id
                            : null;
                        self.applyPrimaryRampWalletFallback();
                    })
                    .catch(function() {
                        self.rampError = self.$t('main.my_business.ramp_loading_error');
                        self.rampWallets = [];
                        self.primaryRampWalletId = null;
                    })
                    .finally(function() {
                        self.rampLoading = false;
                        if (!self.rampError) {
                            if (!skipBalances) {
                                self.fetchRampBalances();
                            }
                        } else {
                            self.rampBalancesByWalletId = {};
                            self.rampBalancesLoading = false;
                            self.rampBalancesError = null;
                        }
                    });
            },
            openRampModal: function(editWallet) {
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = false;
                this.rampEditingId = editWallet ? editWallet.id : null;
                if (editWallet) {
                    this.rampForm = {
                        name: editWallet.name || '',
                        role: editWallet.role === 'multisig' ? 'multisig' : 'external',
                        blockchain: 'tron',
                        tron_address: editWallet.tron_address || '',
                        ethereum_address: editWallet.ethereum_address || '',
                        mnemonic: '',
                        participant_sub_id: null
                    };
                    this.rampExternalCustom = false;
                } else {
                    this.rampForm = {
                        name: '',
                        role: 'external',
                        blockchain: 'tron',
                        tron_address: '',
                        ethereum_address: '',
                        mnemonic: '',
                        participant_sub_id: null
                    };
                    this.rampExternalCustom = false;
                    this.fetchRampParticipants();
                }
                this.showRampModal = true;
            },
            closeRampModal: function() {
                this.clearRampAddrBlurTimer();
                this.rampAddrOpen = false;
                this.showRampModal = false;
                this.rampEditingId = null;
            },
            saveRampWallet: function() {
                var self = this;
                var base = this.rampApiBase();
                if (!base) return;
                var name = (this.rampForm.name || '').trim();
                var tron = (this.rampForm.tron_address || '').trim();
                var url = base;
                var method = 'POST';
                var body;

                if (this.rampEditingId) {
                    if (!name || !tron) return;
                    method = 'PATCH';
                    url = base + '/' + this.rampEditingId;
                    body = { name: name, tron_address: tron };
                } else {
                    if (this.rampSaveAddDisabled) return;
                    if (this.rampForm.role === 'multisig') {
                        body = {
                            role: 'multisig',
                            blockchain: 'tron',
                            name: name
                        };
                    } else {
                        body = { role: 'external', blockchain: 'tron' };
                        if (this.rampForm.participant_sub_id != null) {
                            body.participant_sub_id = this.rampForm.participant_sub_id;
                        } else {
                            body.name = name;
                            body.tron_address = tron;
                        }
                    }
                }

                this.rampSaving = true;
                fetch(url, {
                    method: method,
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(body)
                })
                    .then(function(r) {
                        if (r.status === 403) {
                            return Promise.reject(new Error('403'));
                        }
                        if (!r.ok) {
                            return r.text().then(function(t) {
                                var msg = self.$t('main.my_business.ramp_loading_error');
                                try {
                                    var j = JSON.parse(t);
                                    if (j && typeof j.detail === 'string') {
                                        msg = j.detail;
                                    } else if (j && Array.isArray(j.detail) && j.detail[0] && j.detail[0].msg) {
                                        msg = j.detail[0].msg;
                                    }
                                } catch (e) { /* ignore */ }
                                return Promise.reject(new Error(msg));
                            });
                        }
                        return r.json();
                    })
                    .then(function() {
                        self.closeRampModal();
                        self.fetchRampWallets();
                    })
                    .catch(function(err) {
                        var msg = err && err.message ? err.message : self.$t('main.my_business.ramp_loading_error');
                        if (msg === '403') {
                            msg = self.$t('main.my_business.ramp_error_forbidden');
                        }
                        if (typeof window.showAlert === 'function') {
                            window.showAlert({
                                title: self.$t('main.dialog.error_title'),
                                message: msg
                            });
                        } else {
                            alert(msg);
                        }
                    })
                    .finally(function() {
                        self.rampSaving = false;
                    });
            },
            deleteRampWallet: function(w) {
                var self = this;
                if (!w || !w.id) return;
                var base = this.rampApiBase();
                if (!base) return;

                function runDelete() {
                    fetch(base + '/' + w.id, {
                        method: 'DELETE',
                        headers: self.rampAuthHeaders(),
                        credentials: 'include'
                    })
                        .then(function(r) {
                            if (r.status === 409) {
                                return r.json().then(function(body) {
                                    var d = body && body.detail;
                                    var code = typeof d === 'object' && d !== null ? d.code : null;
                                    var key = 'main.my_business.ramp_delete_blocked_stable';
                                    if (code === 'trx_balance_too_high') {
                                        key = 'main.my_business.ramp_delete_blocked_trx';
                                    } else if (code === 'forex_unavailable') {
                                        key = 'main.my_business.ramp_delete_blocked_forex';
                                    } else if (code === 'used_by_exchange_services') {
                                        var titles = (d && Array.isArray(d.direction_titles))
                                            ? d.direction_titles.filter(Boolean).join(', ')
                                            : '';
                                        throw new Error(self.$t('main.my_business.ramp_delete_blocked_directions', { titles: titles }));
                                    }
                                    throw new Error(self.$t(key));
                                });
                            }
                            if (!r.ok && r.status !== 204) throw new Error();
                            self.fetchRampWallets();
                        })
                        .catch(function(err) {
                            var msg = err && err.message ? err.message : self.$t('main.my_business.ramp_loading_error');
                            if (msg === '403') {
                                msg = self.$t('main.my_business.ramp_error_forbidden');
                            }
                            if (typeof window.showAlert === 'function') {
                                window.showAlert({
                                    title: self.$t('main.dialog.error_title'),
                                    message: msg
                                });
                            } else {
                                alert(msg);
                            }
                        });
                }

                var msgConfirm = self.$t('main.my_business.ramp_delete_confirm');
                if (typeof window.showConfirm === 'function') {
                    window.showConfirm({
                        title: self.$t('main.dialog.confirm_title'),
                        message: msgConfirm,
                        danger: true,
                        onConfirm: function() {
                            runDelete();
                        }
                    });
                } else if (window.confirm(msgConfirm)) {
                    runDelete();
                }
            },
            copyRampAddress: function(addr) {
                var a = (addr || '').trim();
                if (!a || !navigator.clipboard) return;
                navigator.clipboard.writeText(a).then(function() {}).catch(function() {});
            },
            tronscanUrl: function(tronAddress) {
                var a = (tronAddress || '').trim();
                if (!a) return '#';
                return 'https://tronscan.org/#/address/' + encodeURIComponent(a);
            },
            truncateMiddle: function(s, left, right) {
                var t = (s || '').trim();
                if (t.length <= left + right + 3) return t;
                return t.slice(0, left) + '...' + t.slice(-right);
            },
            collateralTronTokens: function() {
                try {
                    var raw = (typeof window !== 'undefined' && window.__COLLATERAL_STABLECOIN_TOKENS__)
                        ? window.__COLLATERAL_STABLECOIN_TOKENS__
                        : [];
                    if (!Array.isArray(raw)) return [];
                    return raw.filter(function(t) {
                        return (t.network || '').toUpperCase() === 'TRON';
                    });
                } catch (e) {
                    return [];
                }
            },
            formatRawTokenAmount: function(rawStr, decimals) {
                var d = parseInt(decimals, 10);
                if (isNaN(d) || d < 0) d = 6;
                var s = String(rawStr == null ? '0' : rawStr).replace(/\s/g, '');
                if (!/^\d+$/.test(s)) return '0';
                try {
                    var bi = BigInt(s);
                    var base = BigInt(10) ** BigInt(d);
                    var whole = bi / base;
                    var frac = bi % base;
                    if (frac === BigInt(0)) return whole.toString();
                    var fs = frac.toString().padStart(d, '0').replace(/0+$/, '');
                    return fs ? whole.toString() + '.' + fs : whole.toString();
                } catch (e) {
                    return s;
                }
            },
            /** Округление до 2 знаков и разделители как 5,240.50 (для UI). */
            formatCollateralAmountDisplay: function(amountStr) {
                var n = parseFloat(String(amountStr == null ? '0' : amountStr).replace(/,/g, ''), 10);
                if (!isFinite(n)) return '0.00';
                var rounded = Math.round(n * 100) / 100;
                return rounded.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            },
            collateralStablecoinIconUrl: function(symbol) {
                var s = String(symbol || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
                if (!s) return '';
                return '/static/main/img/collateral_stablecoin/' + encodeURIComponent(s) + '.svg';
            },
            rampBalancesUrl: function() {
                var space = (typeof window !== 'undefined' && window.__CURRENT_SPACE__)
                    ? String(window.__CURRENT_SPACE__).trim()
                    : '';
                if (!space) return '';
                return '/v1/spaces/' + encodeURIComponent(space) + '/balances';
            },
            fetchRampBalances: function(opts) {
                var self = this;
                opts = opts || {};
                var singleWalletId = opts.walletId;
                var forceUpdate = !!opts.forceUpdate;
                var url = this.rampBalancesUrl();
                if (!url) {
                    this.rampBalancesByWalletId = {};
                    this.rampBalancesLoading = false;
                    this.rampBalancesError = null;
                    this.rampBalancesRowRefreshingId = null;
                    return;
                }
                var payloadItems = [];
                var walletIds = [];
                (this.rampWallets || []).forEach(function(rw) {
                    var tr = (rw.tron_address || '').trim();
                    if (!tr) return;
                    if (singleWalletId != null && rw.id !== singleWalletId) return;
                    payloadItems.push({
                        address: tr,
                        blockchain: 'TRON',
                        force_update: forceUpdate
                    });
                    walletIds.push(rw.id);
                });
                if (!payloadItems.length) {
                    if (singleWalletId == null) {
                        this.rampBalancesByWalletId = {};
                        this.rampBalancesLoading = false;
                        this.rampBalancesError = null;
                    }
                    this.rampBalancesRowRefreshingId = null;
                    return;
                }
                if (singleWalletId != null) {
                    this.rampBalancesRowRefreshingId = singleWalletId;
                } else {
                    this.rampBalancesLoading = true;
                    this.rampBalancesError = null;
                }
                fetch(url, {
                    method: 'POST',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ items: payloadItems })
                })
                    .then(function(r) {
                        if (r.status === 401 || r.status === 403) throw new Error('auth');
                        if (!r.ok) throw new Error(String(r.status));
                        return r.json();
                    })
                    .then(function(data) {
                        var meta = self.collateralTronTokens();
                        var itemsOut = (data && data.items) ? data.items : [];
                        var rowsFromApiRow = function(row) {
                            var rawMap = row.balances_raw || {};
                            var nb = row.native_balances || {};
                            var rows = [];
                            if (nb.TRX != null && String(nb.TRX).trim() !== '') {
                                rows.push({
                                    symbol: 'TRX',
                                    amount: self.formatRawTokenAmount(String(nb.TRX), 6)
                                });
                            }
                            meta.forEach(function(t) {
                                var c = (t.contract_address || '').trim();
                                var raw = rawMap[c] != null ? String(rawMap[c]) : '0';
                                rows.push({
                                    symbol: (t.symbol || c || '?').toUpperCase(),
                                    amount: self.formatRawTokenAmount(raw, t.decimals)
                                });
                            });
                            return rows;
                        };
                        var mapOne = function(row, wid) {
                            if (wid == null) return;
                            self.$set(self.rampBalancesByWalletId, wid, {
                                rows: rowsFromApiRow(row),
                                itemError: row.error || null
                            });
                        };
                        if (singleWalletId != null) {
                            if (itemsOut.length && itemsOut[0]) {
                                mapOne(itemsOut[0], walletIds[0]);
                            }
                        } else {
                            var byId = {};
                            itemsOut.forEach(function(row, i) {
                                var wid = walletIds[i];
                                if (wid == null) return;
                                byId[wid] = {
                                    rows: rowsFromApiRow(row),
                                    itemError: row.error || null
                                };
                            });
                            self.rampBalancesByWalletId = byId;
                        }
                    })
                    .catch(function() {
                        if (singleWalletId != null) {
                            if (typeof window.showAlert === 'function') {
                                window.showAlert({
                                    title: self.$t('main.dialog.error_title'),
                                    message: self.$t('main.my_business.ramp_balances_error')
                                });
                            }
                        } else {
                            self.rampBalancesError = self.$t('main.my_business.ramp_balances_error');
                            self.rampBalancesByWalletId = {};
                        }
                    })
                    .finally(function() {
                        if (singleWalletId != null) {
                            self.rampBalancesRowRefreshingId = null;
                        } else {
                            self.rampBalancesLoading = false;
                        }
                    });
            },
            refreshRampBalancesForWallet: function(rw) {
                if (!rw || !rw.id) return;
                if (this.rampBalancesRowRefreshingId != null) return;
                this.fetchRampBalances({ walletId: rw.id, forceUpdate: true });
            },
            rampBalanceItemErrorMessage: function(entry) {
                if (!entry || !entry.itemError) return '';
                if (entry.itemError === 'eth_balances_not_implemented') {
                    return this.$t('main.my_business.ramp_balances_eth_pending');
                }
                return entry.itemError;
            },
            multisigStatusLabel: function(rw) {
                var st = (rw && rw.multisig_setup_status) ? String(rw.multisig_setup_status) : '';
                if (!st) return '';
                var k = 'main.my_business.multisig_status_' + st;
                var t = this.$t(k);
                return (t && t !== k) ? t : st;
            },
            openMultisigWizard: function(rw) {
                if (!rw) return;
                this.rampMultisigWizardWallet = rw;
                this.showRampMultisigWizard = true;
            },
            beginMultisigReconfigure: function(rw) {
                var self = this;
                if (!rw || !rw.id) return;
                var base = this.rampApiBase();
                if (!base) return;
                fetch(base + '/' + rw.id, {
                    method: 'PATCH',
                    headers: this.rampAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ multisig_begin_reconfigure: true })
                })
                    .then(function(r) {
                        if (!r.ok) {
                            return r.json().then(function(j) {
                                var d = j && j.detail;
                                var msg = typeof d === 'string' ? d : (d ? JSON.stringify(d) : String(r.status));
                                throw new Error(msg);
                            });
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.fetchRampWallets({ skipBalances: true });
                        self.openMultisigWizard(data);
                    })
                    .catch(function(e) {
                        self.rampError = (e && e.message) ? e.message : self.$t('main.my_business.ramp_loading_error');
                    });
            },
            closeMultisigWizard: function() {
                this.showRampMultisigWizard = false;
                this.rampMultisigWizardWallet = null;
            },
            onMultisigConfigModalSaved: function(payload) {
                var self = this;
                var wid = payload && payload.walletId != null ? payload.walletId : null;
                this.fetchRampWallets({ skipBalances: true }).then(function() {
                    if (wid != null && !self.rampError) {
                        self.fetchRampBalances({ walletId: wid, forceUpdate: true });
                    }
                });
            }
        },
        template: [
            '<div class="max-w-7xl mx-auto px-4 py-8 space-y-8">',
            '  <div>',
            '    <h1 class="text-2xl font-bold text-[#191d23] flex items-center gap-3">',
            '      <svg class="w-8 h-8 text-[#3861fb]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>',
            '      [[ $t(\'main.my_business.title\') ]]',
            '    </h1>',
            '    <p class="text-[#58667e] text-sm mt-1">[[ $t(\'main.my_business.subtitle\') ]]</p>',
            '  </div>',

            '  <section class="bg-white rounded-2xl border border-[#eff2f5] p-5 md:p-6 shadow-sm">',
            '    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">',
            '      <div class="flex items-start gap-3 min-w-0 flex-1">',
            '        <div class="p-2 rounded-xl bg-blue-50 text-[#3861fb] shrink-0">',
            '          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>',
            '        </div>',
            '        <div class="min-w-0">',
            '          <div class="flex items-center gap-1 flex-wrap">',
            '            <h2 class="text-lg font-bold text-[#191d23]">[[ $t(\'main.my_business.ramp_section_title\') ]]</h2>',
            '            <button v-if="rampWallets.length" type="button" @click="toggleRampWalletsSection" class="p-1.5 rounded-lg text-[#58667e] hover:bg-[#eff2f5] hover:text-[#3861fb] transition-colors shrink-0" :aria-expanded="rampWalletsExpanded" :title="rampWalletsExpanded ? $t(\'main.my_business.ramp_collapse\') : $t(\'main.my_business.ramp_expand\')">',
            '              <svg class="w-5 h-5 transition-transform duration-200" :class="rampWalletsExpanded ? \'rotate-180\' : \'\'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>',
            '            </button>',
            '          </div>',
            '          <p class="text-xs text-[#58667e] mt-0.5">[[ $t(\'main.my_business.ramp_network\') ]]</p>',
            '        </div>',
            '      </div>',
            '      <button type="button" @click="openRampModal(null)" class="border-2 border-dashed border-[#eff2f5] rounded-xl inline-flex items-center justify-center gap-2 text-sm font-bold py-2 px-3 sm:py-2.5 sm:px-4 text-[#58667e] hover:border-[#3861fb] hover:bg-blue-50/30 hover:text-[#3861fb] transition-all self-start sm:self-center shrink-0">',
            '        <svg class="w-4 h-4 sm:w-5 sm:h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '        [[ $t(\'main.my_business.ramp_add_wallet\') ]]',
            '      </button>',
            '    </div>',
            '    <p v-if="rampError" class="text-sm text-red-600 mb-4">[[ rampError ]]</p>',
            '    <div v-if="rampLoading" class="text-sm text-[#58667e] py-6 text-center">…</div>',
            '    <div v-else-if="!rampWallets.length" class="text-sm text-[#58667e] py-6 text-center border border-dashed border-[#eff2f5] rounded-xl">[[ $t(\'main.my_business.ramp_empty\') ]]</div>',
            '    <div v-else>',
            '    <div v-show="!rampWalletsExpanded" class="rounded-2xl border border-[#eff2f5] bg-[#fafbfc] p-4 mb-3 space-y-3">',
            '      <div class="flex flex-wrap items-center gap-2 text-xs font-bold">',
            '        <span class="inline-flex items-center px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 border border-blue-100">[[ $t(\'main.my_business.ramp_stats_external\', { count: rampExternalWalletCount }) ]]</span>',
            '        <span class="inline-flex items-center px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 border border-purple-100">[[ $t(\'main.my_business.ramp_stats_multisig\', { count: rampMultisigWalletCount }) ]]</span>',
            '      </div>',
            '      <div v-if="rampBalancesLoading" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_loading\') ]]</div>',
            '      <p v-else-if="rampBalancesError" class="text-xs text-red-600">[[ rampBalancesError ]]</p>',
            '      <div v-else class="flex flex-wrap gap-x-4 gap-y-2 text-sm font-semibold text-emerald-600">',
            '        <span v-for="row in rampAggregatedBalanceRows" :key="\'agg-\' + row.symbol" class="inline-flex items-center gap-1.5 min-w-0">',
            '          <img :src="collateralStablecoinIconUrl(row.symbol)" :alt="row.symbol" width="16" height="16" class="w-4 h-4 rounded-full object-contain shrink-0 bg-white ring-1 ring-emerald-100" @error="$event.target.style.display=\'none\'" />',
            '          <span class="font-mono tabular-nums tracking-tight">[[ formatCollateralAmountDisplay(String(row.amount)) ]] [[ row.symbol ]]</span>',
            '        </span>',
            '        <span v-if="!rampAggregatedBalanceRows.length" class="text-xs font-normal text-[#58667e]">[[ $t(\'main.my_business.ramp_collapsed_no_balances\') ]]</span>',
            '      </div>',
            '    </div>',
            '    <div v-show="rampWalletsExpanded" class="grid grid-cols-1 md:grid-cols-2 gap-3">',
            '      <div v-for="rw in rampWallets" :key="rw.id" class="bg-[#fafbfc] rounded-2xl border border-[#eff2f5] p-3 md:p-4 relative">',
            '        <div class="flex items-start justify-between gap-2 mb-2">',
            '          <div class="flex items-center gap-2 min-w-0">',
            '            <span class="w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex items-center justify-center shrink-0">U</span>',
            '            <div class="min-w-0">',
            '              <div class="font-bold text-[#191d23] truncate">[[ rw.name ]]</div>',
            '              <span v-if="rw.role === \'external\'" class="inline-block mt-0.5 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-100">[[ $t(\'main.my_business.ramp_badge_external\') ]]</span>',
            '              <span v-else class="inline-block mt-0.5 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-100">[[ $t(\'main.my_business.ramp_badge_multisig\') ]]</span>',
            '            </div>',
            '          </div>',
            '          <div class="flex items-center gap-1 shrink-0">',
            '            <button type="button" @click="openRampModal(rw)" :title="$t(\'main.my_business.ramp_edit\')" class="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-[#eff2f5] text-[#58667e]">',
            '              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>',
            '            </button>',
            '            <button type="button" @click="copyRampAddress(rw.tron_address || \'\')" :title="$t(\'main.my_business.ramp_copy\')" class="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-[#eff2f5] text-[#58667e]">',
            '              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>',
            '            </button>',
            '          </div>',
            '        </div>',
            '        <div v-if="rw.role === \'multisig\' && rw.multisig_setup_status === \'active\'" class="mb-2 flex flex-wrap items-center gap-2">',
            '          <button type="button" @click="beginMultisigReconfigure(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_reconfigure_begin\') ]]</button>',
            '        </div>',
            '        <div v-if="rw.role === \'multisig\' && rw.multisig_setup_status && rw.multisig_setup_status !== \'active\'" class="mb-2 flex flex-wrap items-center gap-2">',
            '          <span class="inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-md bg-amber-50 text-amber-900 border border-amber-100 pl-2 pr-1.5 py-0.5">',
            '            <span class="text-[10px] font-bold uppercase truncate">[[ multisigStatusLabel(rw) ]]</span>',
            '            <svg v-if="rw.multisig_setup_status !== \'failed\' && rw.multisig_setup_status !== \'reconfigure\'" class="w-3.5 h-3.5 shrink-0 animate-spin text-amber-800 opacity-90" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
            '          </span>',
            '          <button type="button" @click="openMultisigWizard(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_wizard_open\') ]]</button>',
            '          <button v-if="rw.multisig_setup_status === \'failed\'" type="button" @click="beginMultisigReconfigure(rw)" class="text-xs font-bold text-[#3861fb] hover:underline shrink-0">[[ $t(\'main.my_business.multisig_reconfigure_begin\') ]]</button>',
            '        </div>',
            '        <div class="mb-2 rounded-xl border border-[#eff2f5] bg-white px-3 py-2.5">',
            '          <div v-if="rampBalancesLoading" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_loading\') ]]</div>',
            '          <p v-else-if="rampBalancesError" class="text-xs text-red-600">[[ rampBalancesError ]]</p>',
            '          <p v-else-if="(rw.ethereum_address || \'\').trim() && !(rw.tron_address || \'\').trim()" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_tron_only_hint\') ]]</p>',
            '          <p v-else-if="!(rw.tron_address || \'\').trim()" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balance_no_tron\') ]]</p>',
            '          <template v-else>',
            '            <p v-if="rampBalancesByWalletId[rw.id] && rampBalanceItemErrorMessage(rampBalancesByWalletId[rw.id])" class="text-xs text-amber-700 mb-2">[[ rampBalanceItemErrorMessage(rampBalancesByWalletId[rw.id]) ]]</p>',
            '            <div v-if="rampBalancesByWalletId[rw.id] && rampBalancesByWalletId[rw.id].rows && rampBalancesByWalletId[rw.id].rows.length" class="flex flex-wrap items-center justify-between gap-2">',
            '              <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm font-semibold text-emerald-600 min-w-0 flex-1">',
            '                <span v-for="br in rampBalancesByWalletId[rw.id].rows" :key="rw.id + \'-bal-\' + br.symbol" class="inline-flex items-center gap-1.5 min-w-0">',
            '                  <img :src="collateralStablecoinIconUrl(br.symbol)" :alt="br.symbol" width="16" height="16" class="w-4 h-4 rounded-full object-contain shrink-0 bg-white ring-1 ring-emerald-100" @error="$event.target.style.display=\'none\'" />',
            '                  <span class="font-mono tabular-nums tracking-tight">[[ formatCollateralAmountDisplay(br.amount) ]] [[ br.symbol ]]</span>',
            '                </span>',
            '              </div>',
            '              <button type="button" @click="refreshRampBalancesForWallet(rw)" :disabled="rampBalancesRowRefreshingId === rw.id || rampBalancesLoading" :title="$t(\'main.my_business.ramp_balances_refresh\')" :aria-label="$t(\'main.my_business.ramp_balances_refresh\')" class="shrink-0 p-1.5 rounded-lg border border-[#eff2f5] bg-white text-[#58667e] hover:text-[#3861fb] hover:border-[#3861fb]/30 disabled:opacity-50 disabled:pointer-events-none">',
            '                <svg class="w-4 h-4" :class="{\'animate-spin\': rampBalancesRowRefreshingId === rw.id}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>',
            '              </button>',
            '            </div>',
            '            <p v-else-if="!rampBalancesLoading && !rampBalancesError" class="text-xs text-[#58667e]">[[ $t(\'main.my_business.ramp_balances_empty\') ]]</p>',
            '          </template>',
            '        </div>',
            '        <div class="flex items-center gap-2 bg-white border border-[#eff2f5] rounded-xl px-2 py-1.5 text-[11px] font-mono text-[#191d23]">',
            '          <span class="truncate flex-1 min-w-0 sm:hidden">[[ truncateMiddle(rw.tron_address || \'\', 6, 4) ]]</span>',
            '          <span class="truncate flex-1 min-w-0 hidden sm:inline">[[ rw.tron_address || \'\' ]]</span>',
            '          <a :href="tronscanUrl(rw.tron_address || \'\')" target="_blank" rel="noopener noreferrer" class="shrink-0 p-1 text-[#3861fb] hover:opacity-80" :title="$t(\'main.my_business.ramp_open_explorer\')">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>',
            '          </a>',
            '        </div>',
            '        <button type="button" @click="deleteRampWallet(rw)" class="mt-2 text-xs font-bold text-[#58667e] hover:text-red-600">[[ $t(\'main.my_business.ramp_delete\') ]]</button>',
            '      </div>',
            '    </div>',
            '    </div>',
            '  </section>',

            '  <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">',
            '    <div class="lg:col-span-2 space-y-6">',
            '      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">',
            '        <div class="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">',
            '          <h2 class="text-lg font-bold text-[#191d23]">[[ $t(\'main.my_business.my_services\') ]]</h2>',
            '          <button type="button" @click="openCreateServiceModal" class="border-2 border-dashed border-[#eff2f5] rounded-xl inline-flex items-center justify-center gap-2 text-sm font-bold py-2 px-3 sm:py-2.5 sm:px-4 text-[#58667e] hover:border-[#3861fb] hover:bg-blue-50/30 hover:text-[#3861fb] transition-all shrink-0">',
            '            <svg class="w-4 h-4 sm:w-5 sm:h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '            [[ $t(\'main.my_business.create_service\') ]]',
            '          </button>',
            '        </div>',
            '        <div class="flex flex-col items-stretch sm:items-end gap-1.5 shrink-0 w-full sm:w-auto">',
            '          <div class="flex flex-wrap gap-2 justify-end">',
            '            <button type="button" @click="toggleServiceTypeFilter(\'onRamp\')" :class="[\'text-xs font-medium px-2 py-1 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-400\', serviceTypeFilter === \'onRamp\' ? \'bg-blue-100 text-blue-800 border-blue-300 ring-1 ring-blue-300\' : \'bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100\']" :title="$t(\'main.my_business.filter_on_ramp_hint\')" :aria-pressed="serviceTypeFilter === \'onRamp\' ? \'true\' : \'false\'">onRamp: [[ onRampCount ]]</button>',
            '            <button type="button" @click="toggleServiceTypeFilter(\'offRamp\')" :class="[\'text-xs font-medium px-2 py-1 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-purple-400\', serviceTypeFilter === \'offRamp\' ? \'bg-purple-100 text-purple-800 border-purple-300 ring-1 ring-purple-300\' : \'bg-purple-50 text-purple-600 border-purple-100 hover:bg-purple-100\']" :title="$t(\'main.my_business.filter_off_ramp_hint\')" :aria-pressed="serviceTypeFilter === \'offRamp\' ? \'true\' : \'false\'">offRamp: [[ offRampCount ]]</button>',
            '          </div>',
            '          <p v-if="serviceTypeFilter === \'onRamp\'" role="status" class="text-[10px] sm:text-xs text-[#58667e] leading-snug text-left sm:text-right max-w-[20rem] sm:ml-auto">[[ $t(\'main.my_business.filter_active_banner_on_ramp\') ]]</p>',
            '          <p v-else-if="serviceTypeFilter === \'offRamp\'" role="status" class="text-[10px] sm:text-xs text-[#58667e] leading-snug text-left sm:text-right max-w-[20rem] sm:ml-auto">[[ $t(\'main.my_business.filter_active_banner_off_ramp\') ]]</p>',
            '        </div>',
            '      </div>',
            '      <p v-if="exchangeServicesLoading" class="text-sm text-[#58667e]">[[ $t(\'main.my_business.exchange_loading\') ]]</p>',
            '      <p v-else-if="exchangeServicesError" class="text-sm text-red-600">[[ $t(\'main.my_business.exchange_error\') ]]</p>',
            '      <p v-else-if="!exchangeServicesLoading && services.length && !filteredServices.length" class="text-sm text-[#58667e] py-4">[[ $t(\'main.my_business.filter_no_services_of_type\') ]]</p>',
            '      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">',
            '        <div v-for="service in filteredServices" :key="service.id" class="bg-white rounded-2xl border border-[#eff2f5] p-5 hover:border-[#3861fb] transition-all relative overflow-hidden group">',
            '          <div :class="[\'pointer-events-none absolute top-0 right-0 w-24 h-24 -mr-8 -mt-8 rounded-full opacity-5 group-hover:opacity-10 transition-opacity\', service.type === \'onRamp\' ? \'bg-blue-500\' : \'bg-purple-500\']"></div>',
            '          <div class="flex items-center justify-between mb-4">',
            '            <div :class="[\'p-2 rounded-xl\', service.type === \'onRamp\' ? \'bg-blue-50 text-blue-600\' : \'bg-purple-50 text-purple-600\']">',
            '              <!-- onRamp: Lucide arrow-up-right (lucide-icons/lucide) -->',
            '              <svg v-if="service.type === \'onRamp\'" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>',
            '              <!-- offRamp: Lucide arrow-down-left, −90° (против часовой) относительно onRamp -->',
            '              <svg v-else class="w-5 h-5 -rotate-90" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M17 7 7 17"/><path d="M17 17H7V7"/></svg>',
            '            </div>',
            '            <div class="flex items-center gap-2">',
            '              <button type="button" @click.stop="toggleStatus(service.id)" :class="[\'inline-flex items-center justify-center min-h-11 shrink-0 text-[10px] font-bold uppercase px-3 py-2 rounded-full cursor-pointer border-0\', service.status === \'active\' ? \'bg-emerald-50 text-emerald-600 hover:bg-emerald-100\' : \'bg-orange-50 text-orange-600 hover:bg-orange-100\']" :title="$t(\'main.my_business.toggle_status_hint\')">[[ service.status === \'active\' ? $t(\'main.my_business.status_active\') : $t(\'main.my_business.status_paused\') ]]</button>',
            '              <button type="button" @click.stop="openEditExchangeServiceModal(service)" class="inline-flex items-center justify-center min-h-11 min-w-11 shrink-0 p-2 hover:bg-gray-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#3861fb]/30" :title="$t(\'main.my_business.edit_service_open\')" :aria-label="$t(\'main.my_business.edit_service_open\')"><svg class="w-5 h-5 text-[#58667e]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg></button>',
            '            </div>',
            '          </div>',
            '          <div class="space-y-3">',
            '            <div v-if="(service.title || \'\').trim()" class="text-base font-bold text-[#191d23] leading-snug pr-2">[[ service.title ]]</div>',
            '            <p v-if="serviceCashCitiesLine(service)" class="text-xs text-[#58667e] leading-snug pr-2">[[ serviceCashCitiesLine(service) ]]</p>',
            '            <div class="flex items-end justify-between">',
            '              <div>',
            '                <div class="text-xs text-[#58667e] uppercase font-bold tracking-wider">[[ $t(\'main.my_business.direction\') ]]</div>',
            '                <div class="text-lg font-bold text-[#191d23] flex items-center gap-2">[[ service.fiatCurrency ]] <svg class="w-3.5 h-3.5 text-[#eff2f5]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg> [[ service.cryptoCurrency ]]</div>',
            '                <p v-if="(service.description || \'\').trim()" class="text-xs text-[#58667e] mt-2 line-clamp-3">[[ service.description ]]</p>',
            '              </div>',
            '              <div class="text-right">',
            '                <div class="text-xs text-[#58667e] uppercase font-bold tracking-wider">[[ $t(\'main.my_business.commission\') ]]</div>',
            '                <div class="text-lg font-bold text-[#3861fb]">[[ service.commission ]]%</div>',
            '              </div>',
            '            </div>',
            '            <div class="pt-3 border-t border-[#eff2f5] space-y-2">',
            '              <div v-if="(service.payment_code || \'\').trim()" class="flex flex-wrap items-center gap-2 text-xs text-[#58667e]">',
            '                <span class="font-mono bg-gray-50 px-2 py-0.5 rounded">[[ service.payment_code ]]</span>',
            '                <button type="button" @click="openFormPreviewForService(service)" :disabled="serviceCashLockedForCard(service)" class="text-[#3861fb] font-bold hover:underline disabled:opacity-45 disabled:cursor-not-allowed disabled:no-underline">[[ $t(\'main.my_business.preview_payment_form\') ]]</button>',
            '                <button type="button" @click="openFormEditorForService(service)" :disabled="serviceCashLockedForCard(service)" class="text-[#58667e] font-bold hover:underline disabled:opacity-45 disabled:cursor-not-allowed disabled:no-underline">[[ $t(\'main.my_business.form_edit_open\') ]]</button>',
            '              </div>',
            '              <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">',
            '                <div class="flex items-center gap-1.5 text-xs text-[#58667e] min-w-0"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0h.5a2.5 2.5 0 002.5-2.5V3.935M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> <span class="truncate">[[ $t(\'main.my_business.rate_label\') ]]: [[ serviceRateLabel(service) ]]</span></div>',
            '                <div class="flex items-center gap-2 shrink-0">',
            '                  <button type="button" @click="deleteExchangeService(service.id)" class="text-xs font-bold text-red-600 hover:underline">[[ $t(\'main.my_business.delete_service\') ]]</button>',
            '                </div>',
            '              </div>',
            '            </div>',
            '          </div>',
            '        </div>',
            '        <button type="button" @click="openCreateServiceModal" class="border-2 border-dashed border-[#eff2f5] rounded-2xl p-5 flex flex-col items-center justify-center gap-3 hover:border-[#3861fb] hover:bg-blue-50/30 transition-all group">',
            '          <div class="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center text-[#58667e] group-hover:bg-[#3861fb] group-hover:text-white transition-all"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></div>',
            '          <span class="text-sm font-bold text-[#58667e] group-hover:text-[#3861fb]">[[ $t(\'main.my_business.add_service\') ]]</span>',
            '        </button>',
            '      </div>',
            '    </div>',

            '    <div class="space-y-6">',
            '      <h2 class="text-lg font-bold text-[#191d23] flex items-center gap-2">[[ $t(\'main.my_business.partner_network\') ]] <span class="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">[[ partners.length ]]</span></h2>',
            '      <div class="space-y-3">',
            '        <div v-for="partner in partners" :key="partner.id" class="bg-white border border-[#eff2f5] rounded-2xl p-4 hover:shadow-sm transition-all">',
            '          <div class="flex items-center gap-3 mb-3">',
            '            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center text-[#3861fb] font-bold">[[ (partner.name || \'\').charAt(0) ]]</div>',
            '            <div class="flex-1 min-w-0">',
            '              <div class="text-sm font-bold text-[#191d23] truncate">[[ partner.name ]]</div>',
            '              <div class="text-[10px] text-[#58667e] truncate">[[ partner.serviceType ]]</div>',
            '            </div>',
            '            <div class="w-2 h-2 rounded-full bg-emerald-500"></div>',
            '          </div>',
            '          <div class="grid grid-cols-2 gap-2 mb-3">',
            '            <div class="bg-gray-50 rounded-xl p-2"><div class="text-[8px] text-[#58667e] uppercase font-bold">[[ $t(\'main.my_business.base_commission\') ]]</div><div class="text-xs font-bold text-[#191d23]">[[ partner.baseCommission ]]%</div></div>',
            '            <div class="bg-blue-50 rounded-xl p-2"><div class="text-[8px] text-[#3861fb] uppercase font-bold">[[ $t(\'main.my_business.my_margin\') ]]</div><div class="text-xs font-bold text-[#3861fb]">+[[ partner.myCommission ]]%</div></div>',
            '          </div>',
            '          <button type="button" class="w-full py-2 text-[10px] font-bold text-[#58667e] hover:text-[#3861fb] hover:bg-blue-50 rounded-lg transition-all flex items-center justify-center gap-2 border border-transparent hover:border-blue-100"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg> [[ $t(\'main.my_business.configure_resale\') ]]</button>',
            '        </div>',
            '        <button type="button" @click="openPartnerModal" class="w-full py-4 border-2 border-dashed border-[#eff2f5] rounded-2xl text-xs font-bold text-[#58667e] hover:border-[#3861fb] hover:text-[#3861fb] transition-all">+ [[ $t(\'main.my_business.add_partner\') ]]</button>',
            '      </div>',
            '      <div class="bg-gradient-to-br from-[#3861fb] to-indigo-600 rounded-2xl p-5 text-white shadow-lg" style="box-shadow: 0 10px 40px -10px rgba(56,97,251,0.3);">',
            '        <div class="flex items-center gap-3 mb-3"><div class="p-2 bg-white/20 rounded-xl"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg></div><div class="text-sm font-bold">[[ $t(\'main.my_business.help_title\') ]]</div></div>',
            '        <p class="text-xs text-white/80 leading-relaxed mb-4">[[ $t(\'main.my_business.help_text\') ]]</p>',
            '        <button type="button" class="w-full py-2 bg-white text-[#3861fb] rounded-xl text-xs font-bold hover:bg-blue-50 transition-colors">[[ $t(\'main.my_business.contact_support\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <div v-if="showCreateModal" class="fixed inset-0 z-[100] overflow-y-auto overscroll-contain">',
            '    <div class="min-h-[100dvh] min-h-[100svh] flex items-end justify-center sm:items-center p-0 sm:p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="closeCreateModal"></div>',
            '    <div class="relative z-10 bg-white w-full max-w-full sm:max-w-2xl lg:max-w-3xl rounded-t-3xl sm:rounded-3xl shadow-2xl grid grid-rows-[auto_minmax(0,1fr)_auto] h-[90dvh] max-h-[90dvh] overflow-hidden my-0 sm:my-4">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between gap-3 shrink-0">',
            '        <div class="flex items-center gap-2 min-w-0 flex-1">',
            '          <h3 class="text-xl font-bold text-[#191d23] truncate">[[ isEditExchangeModal ? $t(\'main.my_business.modal_edit_service_title\') : $t(\'main.my_business.modal_new_service_title\') ]]</h3>',
            '          <button v-if="!isEditExchangeModal" type="button" @click.stop="showNewServiceHelpModal = true" class="shrink-0 w-9 h-9 rounded-full bg-[#3861fb] text-white text-lg font-bold leading-none flex items-center justify-center shadow-md hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[#3861fb] focus:ring-offset-2" :title="$t(\'main.my_business.new_service_help_open\')" :aria-label="$t(\'main.my_business.new_service_help_open\')">?</button>',
            '        </div>',
            '        <button type="button" @click="closeCreateModal" class="p-2 hover:bg-gray-100 rounded-full shrink-0"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain touch-pan-y p-6 space-y-6 [scrollbar-gutter:stable]">',
            '        <div class="grid grid-cols-2 gap-4">',
            '          <button type="button" :disabled="isEditExchangeModal" @click="setNewServiceTypeOnRamp" :class="[\'p-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-2\', newService.type === \'onRamp\' ? (isEditExchangeModal ? \'border-gray-300 bg-gray-100 text-[#58667e]\' : \'border-[#3861fb] bg-blue-50 text-[#3861fb]\') : (isEditExchangeModal ? \'border-gray-200 bg-gray-50 text-gray-400\' : \'border-[#eff2f5]\'), !isEditExchangeModal && newService.type !== \'onRamp\' ? \'hover:border-gray-300\' : \'\', isEditExchangeModal ? \'cursor-not-allowed\' : \'\']">',
            '            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>',
            '            <span class="text-xs font-bold uppercase">[[ $t(\'main.my_business.on_ramp\') ]]</span>',
            '            <span class="text-[10px] opacity-60">[[ $t(\'main.my_business.on_ramp_desc\') ]]</span>',
            '          </button>',
            '          <button type="button" :disabled="isEditExchangeModal" @click="setNewServiceTypeOffRamp" :class="[\'p-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-2\', newService.type === \'offRamp\' ? (isEditExchangeModal ? \'border-gray-300 bg-gray-100 text-[#58667e]\' : \'border-[#3861fb] bg-blue-50 text-[#3861fb]\') : (isEditExchangeModal ? \'border-gray-200 bg-gray-50 text-gray-400\' : \'border-[#eff2f5]\'), !isEditExchangeModal && newService.type !== \'offRamp\' ? \'hover:border-gray-300\' : \'\', isEditExchangeModal ? \'cursor-not-allowed\' : \'\']">',
            '            <svg class="w-6 h-6 -rotate-90" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M17 7 7 17"/><path d="M17 17H7V7"/></svg>',
            '            <span class="text-xs font-bold uppercase">[[ $t(\'main.my_business.off_ramp\') ]]</span>',
            '            <span class="text-[10px] opacity-60">[[ $t(\'main.my_business.off_ramp_desc\') ]]</span>',
            '          </button>',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.exchange_service_title_label\') ]]</label>',
            '          <input type="text" v-model="newService.title" maxlength="255" :class="[\'w-full px-4 py-3 rounded-xl text-sm shadow-sm focus:outline-none\', !(newService.title || \'\').trim() ? \'border-2 border-amber-300 bg-amber-50/80 focus:border-amber-400 focus:ring-2 focus:ring-amber-100\' : \'border border-[#eff2f5] bg-white focus:border-[#3861fb]\']" :placeholder="$t(\'main.my_business.exchange_service_title_placeholder\')" :aria-invalid="!(newService.title || \'\').trim() ? \'true\' : \'false\'" />',
            '          <div v-if="!(newService.title || \'\').trim()" role="alert" class="mt-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5 text-sm font-semibold text-amber-900 leading-snug">[[ $t(\'main.my_business.exchange_service_title_required\') ]]</div>',
            '        </div>',
            '        <div class="create-modal-currency-panel">',
            '          <p class="create-modal-currency-panel-title">[[ $t(\'main.my_business.currency_pair_section_title\') ]]</p>',
            '        <div class="create-modal-currency-row">',
            '          <div class="relative min-w-0" :class="newService.type === \'onRamp\' ? \'order-1\' : \'order-3\'">',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.fiat_label\') ]]</label>',
            '            <div class="relative">',
            '              <input type="text" v-model="newService.fiatCurrency" :placeholder="$t(\'main.my_business.fiat_placeholder\')" @focus="onFiatInputFocus" @input="onFiatInputInput" @blur="onFiatInputBlur" :class="[\'w-full min-w-0 max-w-full pl-9 py-3 bg-white border border-[#eff2f5] rounded-xl text-sm shadow-sm focus:outline-none focus:border-[#3861fb]\', (newService.fiatCurrency || \'\').trim() ? \'pr-10\' : \'pr-4\']" />',
            '              <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#58667e] pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>',
            '              <button v-if="(newService.fiatCurrency || \'\').trim()" type="button" @click="clearCreateModalFiatCurrency" @mousedown.prevent class="absolute right-1.5 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-[#58667e] hover:bg-[#eff2f5] hover:text-[#191d23] focus:outline-none focus:ring-2 focus:ring-[#3861fb]/40" :title="$t(\'main.my_business.fiat_clear\')" :aria-label="$t(\'main.my_business.fiat_clear\')">',
            '                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>',
            '              </button>',
            '            </div>',
            '            <div v-if="fiatAutocompleteOpen && (fiatCurrencyLoading || fiatCurrencySuggestions.length > 0 || fiatCurrencyNoHits)" class="absolute z-10 w-full mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-xl overflow-hidden max-h-48 overflow-y-auto">',
            '              <div v-if="fiatCurrencyLoading" class="px-3 py-2.5 text-xs text-[#58667e]">[[ $t(\'main.loading\') ]]</div>',
            '              <template v-else>',
            '              <button type="button" v-for="item in fiatCurrencySuggestions" :key="item.code" @mousedown.prevent="selectFiat(item.code)" class="w-full px-4 py-2.5 text-left text-sm hover:bg-blue-50 flex items-center justify-between">[[ item.code ]]</button>',
            '              <div v-if="fiatCurrencyNoHits && !fiatCurrencySuggestions.length" class="px-3 py-2.5 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</div>',
            '              </template>',
            '            </div>',
            '            <div v-if="createModalHasFiat" class="mt-3 space-y-2">',
            '              <label class="flex items-center gap-2 cursor-pointer select-none">',
            '                <input type="checkbox" v-model="newService.cash" @change="onCashCheckboxChange" class="rounded border-[#eff2f5] text-[#3861fb] focus:ring-[#3861fb]" />',
            '                <span class="text-xs font-bold text-[#58667e]">[[ $t(\'main.my_business.cash_label\') ]]</span>',
            '              </label>',
            '              <div v-show="newService.cash" class="space-y-2">',
            '                <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1 ml-0.5">[[ $t(\'main.my_business.cash_cities_label\') ]]</label>',
            '                <div class="flex flex-wrap gap-1.5 mb-1 min-h-[1.25rem]">',
            '                  <span v-for="(c, idx) in newService.cashCities" :key="\'cc-\' + idx + \'-\' + (c.name || \'\')" class="inline-flex items-center gap-1 pl-2.5 pr-1 py-0.5 rounded-lg bg-[#eff2f5] text-xs font-medium text-[#191d23] max-w-full">',
            '                    <span class="truncate max-w-[12rem]">[[ c.name ]]</span>',
            '                    <button type="button" @click="removeCashCity(idx)" class="shrink-0 p-0.5 rounded hover:bg-white/80 text-[#58667e] leading-none" :aria-label="$t(\'main.my_business.cash_city_remove\')">×</button>',
            '                  </span>',
            '                </div>',
            '                <div class="relative">',
            '                  <input type="text" v-model="newService.cashCityInput" autocomplete="off" @focus="onCashCityFocus" @input="onCashCityInput" @blur="onCashCityBlur" @keydown="onCashCityInputKeydown" class="w-full px-4 py-2.5 bg-white border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" :placeholder="$t(\'main.my_business.cash_city_placeholder\')" />',
            '                  <div v-if="cashCityAutocompleteOpen && (cashCityLoading || cashCitySuggestions.length)" class="absolute z-20 w-full mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-xl overflow-hidden max-h-40 overflow-y-auto">',
            '                    <div v-if="cashCityLoading" class="px-3 py-2 text-xs text-[#58667e]">[[ $t(\'main.loading\') ]]</div>',
            '                    <button type="button" v-for="(it, iti) in cashCitySuggestions" :key="\'cct-\' + iti + \'-\' + it.id" @mousedown.prevent="addCashCityFromAutocomplete(it)" class="w-full px-3 py-2.5 text-left text-sm hover:bg-blue-50">[[ it.name ]]</button>',
            '                  </div>',
            '                </div>',
            '              </div>',
            '            </div>',
            '          </div>',
            '          <div class="order-2 flex items-center justify-center py-1 md:py-0" aria-hidden="true">',
            '            <svg class="create-modal-currency-arrow" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>',
            '          </div>',
            '          <div class="min-w-0" :class="newService.type === \'onRamp\' ? \'order-3\' : \'order-1\'">',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.crypto_label\') ]]</label>',
            '            <select v-model="newService.cryptoCurrency" class="w-full min-w-0 max-w-full px-4 py-3 bg-white border border-[#eff2f5] rounded-xl text-sm shadow-sm focus:outline-none focus:border-[#3861fb] appearance-none">',
            '              <option v-for="opt in cryptoOptions" :key="opt" :value="opt">[[ opt ]]</option>',
            '            </select>',
            '          </div>',
            '        </div>',
            '        <div v-if="newService.type === \'onRamp\'" class="create-modal-currency-onramp-hint-row mt-2 sm:mt-3 pt-2 sm:pt-3 border-t border-[#eff2f5]">',
            '          <p class="create-modal-currency-onramp-hint-text text-[11px] text-[#58667e] leading-snug">[[ $t(\'main.my_business.onramp_escrow_requisites_hint\') ]]</p>',
            '        </div>',
            '        <div v-if="newService.type === \'offRamp\'" class="create-modal-currency-wallet-row mt-2 sm:mt-3 pt-2 sm:pt-3 border-t border-[#eff2f5]">',
            '          <div class="min-w-0 space-y-1">',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.space_wallet_label\') ]]</label>',
            '            <select v-model="newService.spaceWalletId" class="w-full min-w-0 max-w-full px-4 py-3 bg-white border border-[#eff2f5] rounded-xl text-sm shadow-sm focus:outline-none focus:border-[#3861fb]">',
            '              <option disabled value="">[[ $t(\'main.my_business.space_wallet_placeholder\') ]]</option>',
            '              <option v-if="!rampWallets.length && primaryRampWalletId" :value="primaryRampWalletId">[[ $t(\'main.my_business.space_wallet_primary_option\') ]]</option>',
            '              <option v-for="w in rampWallets" :key="w.id" :value="w.id">[[ w.name || (\'#\' + w.id) ]]</option>',
            '            </select>',
            '            <p class="text-[11px] text-[#58667e] leading-snug mt-1.5">[[ $t(\'main.my_business.space_wallet_escrow_hint\') ]]</p>',
            '            <p v-if="!rampWallets.length && !primaryRampWalletId" class="text-xs text-amber-900 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 mt-1">[[ $t(\'main.my_business.space_wallet_empty\') ]]</p>',
            '          </div>',
            '          <div class="hidden md:block" aria-hidden="true"></div>',
            '          <div class="hidden md:block" aria-hidden="true"></div>',
            '        </div>',
            '        </div>',
            '        <p v-if="!createModalHasFiat" class="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5 text-sm font-semibold text-amber-900 leading-snug">[[ $t(\'main.my_business.fiat_required_for_limits\') ]]</p>',
            '        <p v-else-if="createModalShowRatesNotFound" class="rounded-xl border border-orange-300 bg-orange-50 px-3 py-2.5 text-sm font-semibold text-orange-950 leading-snug">[[ $t(\'main.my_business.fiat_rates_not_found_for_limits\') ]]</p>',
            '        <div class="create-modal-fiat-limits-row">',
            '          <div class="min-w-0">',
            '            <label :class="[\'block text-[10px] font-bold uppercase mb-1.5 ml-1\', createModalHasFiat ? \'text-[#58667e]\' : \'text-amber-800\']">[[ $t(\'main.my_business.min_fiat_label\') ]]</label>',
            '            <input type="text" inputmode="decimal" autocomplete="off" v-model="createModalMinFiatText" @input="onCreateModalMinFiatLimitInput" @blur="onCreateModalMinFiatLimitBlur" :disabled="!createModalHasFiat" :class="[\'w-full px-4 py-3 border rounded-xl text-sm focus:outline-none focus:border-[#3861fb] tabular-nums\', createModalHasFiat ? \'bg-gray-50 border-[#eff2f5]\' : \'bg-gray-100 border-amber-200 text-gray-500 cursor-not-allowed opacity-80\']" />',
            '          </div>',
            '          <div class="min-w-0">',
            '            <label :class="[\'block text-[10px] font-bold uppercase mb-1.5 ml-1\', createModalHasFiat ? \'text-[#58667e]\' : \'text-amber-800\']">[[ $t(\'main.my_business.max_fiat_label\') ]]</label>',
            '            <input type="text" inputmode="decimal" autocomplete="off" v-model="createModalMaxFiatText" @input="onCreateModalMaxFiatLimitInput" @blur="onCreateModalMaxFiatLimitBlur" :disabled="!createModalHasFiat" :class="[\'w-full px-4 py-3 border rounded-xl text-sm focus:outline-none focus:border-[#3861fb] tabular-nums\', createModalHasFiat ? \'bg-gray-50 border-[#eff2f5]\' : \'bg-gray-100 border-amber-200 text-gray-500 cursor-not-allowed opacity-80\']" />',
            '          </div>',
            '        </div>',
            '        <p v-if="createModalFiatUsdHintLine" class="text-[10px] text-[#58667e] mt-1 ml-1 leading-snug">[[ createModalFiatUsdHintLine ]]</p>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.payment_code_label\') ]]</label>',
            '          <div class="flex flex-col sm:flex-row gap-2 items-stretch">',
            '            <div class="relative flex-1 min-w-0">',
            '            <input type="text" v-model="newService.payment_code" autocomplete="off" :disabled="!createModalFiatIso3 || cashLocked" @focus="onPaymentCodeFocus" @input="onPaymentCodeInput" @blur="onPaymentCodeBlur" :class="[\'w-full py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] font-mono disabled:bg-gray-100 disabled:text-gray-500 disabled:cursor-not-allowed\', (newService.payment_code || \'\').trim() && createModalFiatIso3 && !cashLocked ? \'pl-4 pr-10\' : \'px-4\']" :placeholder="createModalFiatIso3 ? $t(\'main.my_business.payment_code_placeholder\') : $t(\'main.my_business.payment_code_placeholder_disabled\')" />',
            '            <button v-if="(newService.payment_code || \'\').trim() && createModalFiatIso3 && !cashLocked" type="button" @click="clearCreateModalPaymentCode" @mousedown.prevent class="absolute right-1.5 top-1/2 -translate-y-1/2 z-[1] p-1.5 rounded-lg text-[#58667e] hover:bg-[#eff2f5] hover:text-[#191d23] focus:outline-none focus:ring-2 focus:ring-[#3861fb]/40" :title="$t(\'main.my_business.payment_code_clear\')" :aria-label="$t(\'main.my_business.payment_code_clear\')">',
            '              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>',
            '            </button>',
            '            <div v-if="paymentCodeAutocompleteOpen && createModalFiatIso3 && !cashLocked" class="absolute z-[60] w-full mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-xl overflow-hidden max-h-48 overflow-y-auto">',
            '              <div v-if="paymentCodeLoading" class="px-3 py-2.5 text-xs text-[#58667e]">[[ $t(\'main.loading\') ]]</div>',
            '              <div v-else>',
            '              <div v-if="paymentCodeTotalForCur != null" class="sticky top-0 z-10 px-3 py-1.5 text-[10px] font-medium text-[#58667e] bg-[#fafbfc] border-b border-[#eff2f5]">[[ $t(\'main.guarantor.payment_total_for_currency\', { count: paymentCodeTotalForCur }) ]]</div>',
            '              <button type="button" v-for="p in paymentCodeSuggestions" :key="p.payment_code" @mousedown.prevent="selectPaymentCodeFromAutocomplete(p)" class="w-full px-3 py-2.5 text-left text-sm hover:bg-blue-50 border-b border-[#eff2f5] last:border-b-0">',
            '                <span class="font-medium text-[#191d23]">[[ p.name ]]</span>',
            '                <span class="block text-[10px] text-[#58667e] font-mono mt-0.5">[[ p.cur ]] · [[ p.payment_code ]]</span>',
            '              </button>',
            '              <div v-if="paymentCodeNoHits && !paymentCodeSuggestions.length" class="px-3 py-2.5 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</div>',
            '              </div>',
            '            </div>',
            '            </div>',
            '            <div class="flex flex-col sm:flex-row gap-2 shrink-0 w-full sm:w-auto">',
            '            <button type="button" @click="openFormPreview(newService.payment_code)" :disabled="cashLocked || !(newService.payment_code || \'\').trim()" :title="$t(\'main.my_business.payment_code_show_requisites\')" class="shrink-0 px-4 py-3 rounded-xl border border-[#3861fb]/40 bg-white text-xs font-bold text-[#3861fb] hover:bg-blue-50 disabled:opacity-45 disabled:cursor-not-allowed whitespace-nowrap self-stretch sm:self-auto">[[ $t(\'main.my_business.payment_code_show_requisites\') ]]</button>',
            '            <button type="button" @click="openFormEditorNew" :disabled="cashLocked || !(newService.payment_code || \'\').trim()" :title="$t(\'main.my_business.form_edit_open\')" class="shrink-0 px-4 py-3 rounded-xl border border-[#eff2f5] bg-white text-xs font-bold text-[#58667e] hover:bg-gray-50 disabled:opacity-45 disabled:cursor-not-allowed whitespace-nowrap self-stretch sm:self-auto">[[ $t(\'main.my_business.form_edit_open\') ]]</button>',
            '            </div>',
            '          </div>',
            '          <p v-if="!createModalFiatIso3 && createModalHasFiat" class="text-[10px] text-amber-800 mt-1 ml-1 font-medium">[[ $t(\'main.my_business.payment_code_need_fiat_iso\') ]]</p>',
            '          <p class="text-[10px] text-[#58667e] mt-1 ml-1">[[ $t(\'main.my_business.payment_code_hint\') ]]</p>',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.service_description_label\') ]]</label>',
            '          <textarea v-model="newService.description" rows="2" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] resize-y min-h-[4rem]" :placeholder="$t(\'main.my_business.service_description_placeholder\')"></textarea>',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-3 ml-1">[[ $t(\'main.my_business.rate_type_label\') ]]</label>',
            '          <div :class="isEditExchangeModal ? \'grid grid-cols-1 sm:grid-cols-3 gap-3\' : \'flex flex-col sm:flex-row gap-4\'">',
            '            <label class="flex-1 min-w-0 cursor-pointer">',
            '              <input type="radio" v-model="newService.rateType" value="forex" class="hidden" />',
            '              <div :class="[\'p-3 rounded-xl border-2 text-center transition-all\', newService.rateType === \'forex\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']"><div class="text-xs font-bold">[[ $t(\'main.my_business.rate_forex\') ]]</div><div class="text-[10px] opacity-60">[[ $t(\'main.my_business.rate_forex_desc\') ]]</div></div>',
            '            </label>',
            '            <label class="flex-1 min-w-0 cursor-pointer">',
            '              <input type="radio" v-model="newService.rateType" value="request" class="hidden" />',
            '              <div :class="[\'p-3 rounded-xl border-2 text-center transition-all\', newService.rateType === \'request\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']"><div class="text-xs font-bold">[[ $t(\'main.my_business.rate_request\') ]]</div><div class="text-[10px] opacity-60">[[ $t(\'main.my_business.rate_request_desc\') ]]</div></div>',
            '            </label>',
            '            <label v-if="isEditExchangeModal" class="flex-1 min-w-0 cursor-pointer">',
            '              <input type="radio" v-model="newService.rateType" value="manual" class="hidden" />',
            '              <div :class="[\'p-3 rounded-xl border-2 text-center transition-all\', newService.rateType === \'manual\' ? \'border-[#3861fb] bg-blue-50 text-[#3861fb]\' : \'border-[#eff2f5] hover:border-gray-300\']"><div class="text-xs font-bold">[[ $t(\'main.my_business.rate_manual\') ]]</div><div class="text-[10px] opacity-60">[[ $t(\'main.my_business.rate_manual_desc\') ]]</div></div>',
            '            </label>',
            '          </div>',
            '        </div>',
            '        <div v-show="newService.rateType === \'forex\'">',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ratios_engine_key_label\') ]]</label>',
            '          <input type="text" v-model="newService.ratiosEngineKey" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] font-mono" :placeholder="$t(\'main.my_business.ratios_engine_key_placeholder\')" />',
            '        </div>',
            '        <div v-show="newService.rateType === \'manual\'">',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.manual_rate_label\') ]]</label>',
            '          <input type="number" v-model.number="newService.manualRate" step="any" min="0" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] tabular-nums" />',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mt-3 mb-1.5 ml-1">[[ $t(\'main.my_business.manual_rate_valid_until_label\') ]]</label>',
            '          <input type="datetime-local" v-model="newService.manualRateValidUntil" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '        </div>',
            '        <div>',
            '          <div class="flex items-center justify-between mb-1.5 ml-1"><label class="text-[10px] font-bold text-[#58667e] uppercase">[[ $t(\'main.my_business.commission_label\') ]]</label><span class="text-sm font-bold text-[#3861fb]">[[ newService.commission ]]%</span></div>',
            '          <input type="range" v-model.number="newService.commission" min="0.1" max="10" step="0.1" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer" style="accent-color: #3861fb;" />',
            '          <div class="flex justify-between mt-2 text-[10px] text-[#58667e] font-bold"><span>0.1%</span><span>5.0%</span><span>10.0%</span></div>',
            '        </div>',
            '      </div>',
            '      <div class="p-6 pt-4 bg-gray-50 border-t border-[#eff2f5] flex gap-3 shrink-0 pb-[max(1rem,env(safe-area-inset-bottom))]">',
            '        <button type="button" @click="closeCreateModal" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="saveExchangeService" :disabled="createModalLaunchDisabled" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ exchangeSaving ? $t(\'main.my_business.saving\') : (isEditExchangeModal ? $t(\'main.my_business.save_service_changes\') : $t(\'main.my_business.launch_service\')) ]]</button>',
            '      </div>',
            '    </div>',
            '    </div>',
            '  </div>',

            '  <payment-form-preview-modal :show="showFormPreviewModal" :payment-code="formPreviewCode" :preview-exchange-service-id="formModalVariant === \'preview\' ? formModalServiceId : null" :variant="formModalVariant" :initial-requisites-schema="formModalInitialSchema" @close="showFormPreviewModal = false" @requisites-saved="onRequisitesSaved"></payment-form-preview-modal>',

            '  <div v-if="showPartnerModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="showPartnerModal = false"></div>',
            '    <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ $t(\'main.my_business.modal_new_partner_title\') ]]</h3>',
            '        <button type="button" @click="showPartnerModal = false" class="p-2 hover:bg-gray-100 rounded-full"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="p-6 space-y-4">',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.partner_name\') ]]</label>',
            '          <input type="text" v-model="newPartner.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" placeholder="GlobalPay Solutions" />',
            '        </div>',
            '        <div>',
            '          <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.service_type\') ]]</label>',
            '          <input type="text" v-model="newPartner.serviceType" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" placeholder="onRamp (EUR/USDT)" />',
            '        </div>',
            '        <div class="grid grid-cols-2 gap-4">',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.base_commission_label\') ]]</label>',
            '            <input type="number" v-model.number="newPartner.baseCommission" min="0" step="0.1" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.my_commission_label\') ]]</label>',
            '            <input type="number" v-model.number="newPartner.myCommission" min="0" step="0.1" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '        </div>',
            '      </div>',
            '      <div class="p-6 bg-gray-50 border-t border-[#eff2f5] flex gap-3">',
            '        <button type="button" @click="showPartnerModal = false" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="addPartner" :disabled="!(newPartner.name || \'\').trim()" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ $t(\'main.my_business.connect_btn\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',

            '  <div v-if="showRampModal" class="fixed inset-0 z-[100] overflow-y-auto overscroll-contain">',
            '    <div class="min-h-[100dvh] min-h-[100svh] flex items-end justify-center sm:items-center p-0 sm:p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="closeRampModal"></div>',
            '    <div class="relative z-10 bg-white w-full max-w-full sm:max-w-lg rounded-t-3xl sm:rounded-3xl shadow-2xl grid grid-rows-[auto_minmax(0,1fr)_auto] h-[90dvh] max-h-[90dvh] overflow-hidden my-0 sm:my-4">',
            '      <div class="p-6 border-b border-[#eff2f5] flex items-center justify-between shrink-0">',
            '        <h3 class="text-xl font-bold text-[#191d23]">[[ rampEditingId ? $t(\'main.my_business.ramp_modal_edit_title\') : $t(\'main.my_business.ramp_modal_add_title\') ]]</h3>',
            '        <button type="button" @click="closeRampModal" class="p-2 hover:bg-gray-100 rounded-full"><svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>',
            '      </div>',
            '      <div class="min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain touch-pan-y p-6 space-y-4">',
            '        <template v-if="!rampEditingId">',
            '          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">',
            '            <div class="flex-1 min-w-0">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_role\') ]]</label>',
            '              <select v-model="rampForm.role" @change="onRampRoleChange" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]">',
            '                <option value="external">[[ $t(\'main.my_business.ramp_role_external\') ]]</option>',
            '                <option value="multisig">[[ $t(\'main.my_business.ramp_role_multisig\') ]]</option>',
            '              </select>',
            '            </div>',
            '            <div class="flex-1 min-w-0">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_blockchain\') ]]</label>',
            '              <select v-model="rampForm.blockchain" disabled class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm text-[#58667e] cursor-not-allowed">',
            '                <option value="tron">[[ $t(\'main.my_business.ramp_blockchain_tron\') ]]</option>',
            '              </select>',
            '            </div>',
            '          </div>',
            '          <template v-if="rampForm.role === \'multisig\'">',
            '            <div>',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '              <input type="text" v-model="rampForm.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '            </div>',
            '            <div class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">[[ $t(\'main.my_business.ramp_multisig_warning\') ]]</div>',
            '          </template>',
            '          <template v-else>',
            '            <div class="relative ramp-addr-combo" @focusout="onRampAddrFocusOut">',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_address\') ]]</label>',
            '              <div class="relative">',
            '                <input type="text" v-model="rampForm.tron_address" :readonly="rampForm.participant_sub_id != null" autocomplete="off" @focus="onRampAddrFocus" @click="onRampAddrInputClick" @input="onRampTronAddressInput" class="w-full pl-4 pr-11 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm font-mono focus:outline-none focus:border-[#3861fb] read-only:bg-gray-100 read-only:text-[#191d23] read-only:cursor-pointer" :placeholder="$t(\'main.my_business.ramp_address_placeholder\')" />',
            '                <button type="button" tabindex="-1" :aria-expanded="rampAddrOpen ? \'true\' : \'false\'" :title="$t(\'main.my_business.ramp_address_toggle_list\')" @mousedown.prevent="toggleRampAddrDropdown" class="absolute right-1 top-1/2 -translate-y-1/2 p-2 rounded-lg text-[#58667e] hover:bg-gray-200/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3861fb]/40">',
            '                  <svg class="w-4 h-4 transition-transform duration-150" :class="rampAddrOpen ? \'rotate-180\' : \'\'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>',
            '                </button>',
            '              </div>',
            '              <div v-if="rampAddrOpen" class="absolute z-20 left-0 right-0 mt-1 bg-white border border-[#eff2f5] rounded-xl shadow-lg max-h-52 overflow-y-auto">',
            '                <button type="button" class="w-full text-left px-4 py-3 text-sm hover:bg-blue-50 border-b border-[#eff2f5] font-medium text-[#3861fb]" @mousedown.prevent="pickRampCustomAddress">[[ $t(\'main.my_business.ramp_pick_custom_address\') ]]</button>',
            '                <button type="button" v-for="p in rampAddressPickerParticipants" :key="p.id" class="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 border-b border-[#eff2f5] last:border-0" @mousedown.prevent="pickRampParticipantSub(p)">',
            '                  <span class="font-mono text-xs text-[#191d23] block truncate">[[ p.wallet_address ]]</span>',
            '                  <div class="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1">',
            '                    <span v-if="p.nickname" class="text-[11px] text-[#58667e]">[[ p.nickname ]]</span>',
            '                    <span v-if="p.is_verified !== true" class="inline-flex text-[10px] font-bold uppercase tracking-wide text-amber-900 bg-amber-100 border border-amber-200 px-1.5 py-0.5 rounded-md">[[ $t(\'main.my_business.ramp_participant_not_verified\') ]]</span>',
            '                  </div>',
            '                </button>',
            '              </div>',
            '            </div>',
            '            <div>',
            '              <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '              <input type="text" v-model="rampForm.name" :disabled="rampForm.participant_sub_id != null" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb] disabled:bg-gray-100" />',
            '              <p v-if="rampForm.participant_sub_id != null" class="text-[10px] text-[#58667e] mt-1 ml-1">[[ $t(\'main.my_business.ramp_name_from_manager\') ]]</p>',
            '            </div>',
            '          </template>',
            '        </template>',
            '        <template v-else>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_name\') ]]</label>',
            '            <input type="text" v-model="rampForm.name" class="w-full px-4 py-3 bg-gray-50 border border-[#eff2f5] rounded-xl text-sm focus:outline-none focus:border-[#3861fb]" />',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_role\') ]]</label>',
            '            <select v-model="rampForm.role" disabled tabindex="-1" class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm text-[#58667e] cursor-not-allowed">',
            '              <option value="external">[[ $t(\'main.my_business.ramp_role_external\') ]]</option>',
            '              <option value="multisig">[[ $t(\'main.my_business.ramp_role_multisig\') ]]</option>',
            '            </select>',
            '          </div>',
            '          <div>',
            '            <label class="block text-[10px] font-bold text-[#58667e] uppercase mb-1.5 ml-1">[[ $t(\'main.my_business.ramp_field_tron\') ]]</label>',
            '            <input type="text" v-model="rampForm.tron_address" readonly class="w-full px-4 py-3 bg-gray-100 border border-[#eff2f5] rounded-xl text-sm font-mono text-[#191d23] cursor-default focus:outline-none" />',
            '          </div>',
            '        </template>',
            '      </div>',
            '      <div class="p-6 pt-4 bg-gray-50 border-t border-[#eff2f5] flex gap-3 shrink-0 pb-[max(1rem,env(safe-area-inset-bottom))]">',
            '        <button type="button" @click="closeRampModal" class="flex-1 py-3 border border-[#eff2f5] rounded-xl text-sm font-bold text-[#58667e] hover:bg-white transition-all">[[ $t(\'main.my_business.cancel\') ]]</button>',
            '        <button type="button" @click="saveRampWallet" :disabled="rampSaving || (rampEditingId ? rampSaveEditDisabled : rampSaveAddDisabled)" class="flex-1 py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all">[[ $t(\'main.my_business.ramp_save\') ]]</button>',
            '      </div>',
            '    </div>',
            '    </div>',
            '  </div>',

            '  <new-service-help-modal :show="showNewServiceHelpModal" @close="showNewServiceHelpModal = false"></new-service-help-modal>',
            '  <multisig-config-modal :show="showRampMultisigWizard" :wallet="rampMultisigWizardWallet" @close="closeMultisigWizard" @saved="onMultisigConfigModalSaved"></multisig-config-modal>',
            '</div>'
        ].join('')
    });
})();
