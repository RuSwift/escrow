/**
 * Vue 2: панель гаранта — данные с API, модалка нового направления, автокомплит BestChange.
 */
(function() {
    var DEBOUNCE_MS = 280;
    var COMMISSION_SAVE_MS = 500;
    var AC_LIMIT_FOCUS = 5;
    /** Пустой q: сколько способов оплаты показывать при фокусе / открытии списка */
    var AC_LIMIT_PAYMENT_FOCUS = 10;
    var AC_LIMIT_TYPE = 40;
    var MODAL_AC_BLUR_MS = 180;

    function draftAutocomplete() {
        return {
            currencyCode: '',
            paymentCode: '',
            paymentName: '',
            currencyInput: '',
            paymentInput: '',
            currencyOpen: false,
            paymentOpen: false,
            currencySuggestions: [],
            paymentSuggestions: [],
            paymentTotalForCur: null,
            currencyNoHits: false,
            paymentNoHits: false,
            _currencyTimer: null,
            _paymentTimer: null
        };
    }

    function appLocale() {
        if (typeof window !== 'undefined' && window.__LOCALE__) {
            return String(window.__LOCALE__).trim() || 'en';
        }
        return 'en';
    }

    Vue.component('guarantor', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                loading: true,
                loadError: null,
                directions: [],
                commissionPercent: 0.1,
                isVerified: true,
                showAddModal: false,
                showAddDirectionErrorModal: false,
                addDirectionErrorMessage: '',
                showVerificationInfoModal: false,
                modal: draftAutocomplete(),
                conditionsDraft: '',
                commissionSyncing: false,
                commissionFeedback: null,
                _commissionTimer: null,
                _commissionInflight: 0,
                _commissionSuppressInput: false,
                _commissionFeedbackTimer: null,
                _modalCurrencyBlurTimer: null,
                _modalPaymentBlurTimer: null,
                _docClick: null,
                directionEditingId: null,
                directionEditDraft: '',
                directionEditSaving: false,
                directionEditError: null
            };
        },
        mounted: function() {
            var self = this;
            this._docClick = this.onDocumentClick.bind(this);
            document.addEventListener('click', this._docClick);
            this.fetchState();
        },
        beforeDestroy: function() {
            document.removeEventListener('click', this._docClick);
            if (this._commissionTimer) {
                clearTimeout(this._commissionTimer);
            }
            if (this._commissionFeedbackTimer) {
                clearTimeout(this._commissionFeedbackTimer);
            }
            if (this._modalCurrencyBlurTimer) {
                clearTimeout(this._modalCurrencyBlurTimer);
            }
            if (this._modalPaymentBlurTimer) {
                clearTimeout(this._modalPaymentBlurTimer);
            }
        },
        methods: {
            apiBase: function() {
                var space =
                    typeof window !== 'undefined' && window.__CURRENT_SPACE__
                        ? String(window.__CURRENT_SPACE__).trim()
                        : '';
                if (!space) {
                    return '';
                }
                return '/v1/spaces/' + encodeURIComponent(space) + '/guarantor';
            },
            authHeaders: function() {
                var token = null;
                try {
                    var key =
                        typeof window !== 'undefined' && window.main_auth_token_key
                            ? window.main_auth_token_key
                            : 'main_auth_token';
                    token = localStorage.getItem(key);
                } catch (e) {}
                var h = { 'Content-Type': 'application/json' };
                if (token) {
                    h.Authorization = 'Bearer ' + token;
                }
                return h;
            },
            fetchState: function() {
                var self = this;
                var base = this.apiBase();
                if (!base) {
                    this.loading = false;
                    this.loadError = this.$t('main.guarantor.error_no_space');
                    return;
                }
                this.loading = true;
                this.loadError = null;
                fetch(base, { method: 'GET', headers: this.authHeaders(), credentials: 'include' })
                    .then(function(r) {
                        if (r.status === 403) {
                            throw new Error(self.$t('main.guarantor.error_403'));
                        }
                        if (!r.ok) {
                            throw new Error(self.$t('main.guarantor.error_load'));
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.directions = (data && data.directions) || [];
                        self.isVerified = !!(data && data.is_verified);
                        var cp =
                            data &&
                            data.profile &&
                            data.profile.commission_percent !== null &&
                            data.profile.commission_percent !== undefined
                                ? Number(data.profile.commission_percent)
                                : 0.1;
                        self.commissionPercent = isNaN(cp) ? 0.1 : cp;
                    })
                    .catch(function(e) {
                        self.loadError = (e && e.message) || self.$t('main.guarantor.error_load');
                    })
                    .finally(function() {
                        self.loading = false;
                    });
            },
            onCommissionInput: function() {
                var self = this;
                if (this._commissionSuppressInput) {
                    this._commissionSuppressInput = false;
                    return;
                }
                this.commissionSyncing = true;
                /* Не сбрасываем commissionFeedback здесь: после PATCH срабатывает echo input и
                   затирало бы текст успеха/ошибки. Очистка — в начале saveCommission. */
                if (this._commissionFeedbackTimer) {
                    clearTimeout(this._commissionFeedbackTimer);
                    this._commissionFeedbackTimer = null;
                }
                if (this._commissionTimer) {
                    clearTimeout(this._commissionTimer);
                }
                this._commissionTimer = setTimeout(function() {
                    self.saveCommission();
                }, COMMISSION_SAVE_MS);
            },
            _applyCommissionPercentSilent: function(next) {
                var self = this;
                var n = Number(next);
                if (isNaN(n)) {
                    return;
                }
                this._commissionSuppressInput = true;
                this.commissionPercent = n;
                this.$nextTick(function() {
                    if (self._commissionSuppressInput) {
                        self._commissionSuppressInput = false;
                    }
                });
            },
            _setCommissionSpinnerFromState: function() {
                this.commissionSyncing =
                    this._commissionInflight > 0 || !!this._commissionTimer;
            },
            _formatPatchErrorBody: function(j) {
                if (!j || j.detail === undefined || j.detail === null) {
                    return '';
                }
                var d = j.detail;
                if (typeof d === 'string') {
                    return d;
                }
                if (Array.isArray(d)) {
                    return d
                        .map(function(x) {
                            return x && (x.msg || x.message) ? String(x.msg || x.message) : '';
                        })
                        .filter(Boolean)
                        .join('; ');
                }
                return String(d);
            },
            /** POST /guarantor/directions: detail = { code, message } — показываем перевод по code */
            _guarantorDirectionCreateErrorMessage: function(j) {
                var d = j && j.detail;
                if (d && typeof d === 'object' && !Array.isArray(d) && d.code) {
                    var key = 'main.guarantor.errors.' + d.code;
                    var t = this.$t(key);
                    if (t && t !== key) {
                        return t;
                    }
                    if (d.message) {
                        return String(d.message);
                    }
                }
                var fallback = this._formatPatchErrorBody(j);
                return fallback || this.$t('main.guarantor.error_load');
            },
            _scheduleClearCommissionFeedback: function() {
                var self = this;
                if (this._commissionFeedbackTimer) {
                    clearTimeout(this._commissionFeedbackTimer);
                }
                this._commissionFeedbackTimer = setTimeout(function() {
                    if (self.commissionFeedback && self.commissionFeedback.type === 'success') {
                        self.commissionFeedback = null;
                    }
                    self._commissionFeedbackTimer = null;
                }, 4000);
            },
            saveCommission: function() {
                var self = this;
                /* setTimeout уже отработал, но id в _commissionTimer остаётся truthy — иначе
                   _setCommissionSpinnerFromState() считает, что debounce ещё ждёт, и спиннер не гаснет. */
                this._commissionTimer = null;
                this.commissionFeedback = null;
                var base = this.apiBase();
                if (!base) {
                    this._setCommissionSpinnerFromState();
                    return;
                }
                var v = Number(this.commissionPercent);
                if (isNaN(v) || v < 0.1) {
                    v = 0.1;
                    this._applyCommissionPercentSilent(v);
                }
                this._commissionInflight++;
                fetch(base + '/profile', {
                    method: 'PATCH',
                    headers: this.authHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ commission_percent: v })
                })
                    .then(function(r) {
                        if (r.status === 403) {
                            throw new Error(self.$t('main.guarantor.error_403'));
                        }
                        if (!r.ok) {
                            return r.json().then(
                                function(j) {
                                    var msg = self._formatPatchErrorBody(j);
                                    throw new Error(msg || self.$t('main.guarantor.commission_save_error'));
                                },
                                function() {
                                    throw new Error(self.$t('main.guarantor.commission_save_error'));
                                }
                            );
                        }
                        return r.json();
                    })
                    .then(function(data) {
                        self.commissionFeedback = {
                            type: 'success',
                            text: self.$t('main.guarantor.commission_saved')
                        };
                        self._scheduleClearCommissionFeedback();
                        if (data && data.commission_percent !== undefined && data.commission_percent !== null) {
                            self._applyCommissionPercentSilent(data.commission_percent);
                        }
                    })
                    .catch(function(e) {
                        self.commissionFeedback = {
                            type: 'error',
                            text: (e && e.message) || self.$t('main.guarantor.commission_save_error')
                        };
                    })
                    .finally(function() {
                        self._commissionInflight = Math.max(0, self._commissionInflight - 1);
                        self._setCommissionSpinnerFromState();
                    });
            },
            openAddModal: function() {
                this._clearModalCurrencyBlurTimer();
                this._clearModalPaymentBlurTimer();
                this.modal = draftAutocomplete();
                this.conditionsDraft = '';
                this.showAddModal = true;
            },
            closeAddModal: function() {
                this.showAddModal = false;
                this.showAddDirectionErrorModal = false;
                this.addDirectionErrorMessage = '';
            },
            closeAddDirectionErrorModal: function() {
                this.showAddDirectionErrorModal = false;
                this.addDirectionErrorMessage = '';
            },
            openVerificationInfoModal: function() {
                this.showVerificationInfoModal = true;
            },
            closeVerificationInfoModal: function() {
                this.showVerificationInfoModal = false;
            },
            submitAddModal: function() {
                var self = this;
                var m = this.modal;
                if (!m.currencyCode || !m.paymentCode) {
                    return;
                }
                if (!(this.conditionsDraft || '').trim().length) {
                    return;
                }
                var base = this.apiBase();
                if (!base) {
                    return;
                }
                fetch(base + '/directions', {
                    method: 'POST',
                    headers: this.authHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({
                        currency_code: m.currencyCode,
                        payment_code: m.paymentCode,
                        payment_name: m.paymentName || null,
                        conditions_text: this.conditionsDraft.trim() || null,
                        sort_order: 0
                    })
                })
                    .then(function(r) {
                        if (r.status === 403) {
                            throw new Error(self.$t('main.guarantor.error_403'));
                        }
                        if (!r.ok) {
                            return r.json().then(
                                function(j) {
                                    var msg = self._guarantorDirectionCreateErrorMessage(j);
                                    throw new Error(msg);
                                },
                                function() {
                                    throw new Error(self.$t('main.guarantor.error_load'));
                                }
                            );
                        }
                        return r.json();
                    })
                    .then(function() {
                        self.closeAddModal();
                        self.fetchState();
                    })
                    .catch(function(e) {
                        var msg = (e && e.message) || self.$t('main.guarantor.error_load');
                        self.addDirectionErrorMessage = msg;
                        self.showAddDirectionErrorModal = true;
                    });
            },
            confirmDeleteDirection: function(d) {
                var self = this;
                var title = this.$t('main.guarantor.delete_confirm_title');
                var message = this.$t('main.guarantor.delete_confirm_message');
                if (typeof window.showConfirm !== 'function') {
                    if (!window.confirm(message)) {
                        return;
                    }
                    self.doDeleteDirection(d.id);
                    return;
                }
                window.showConfirm({
                    title: title,
                    message: message,
                    danger: true,
                    onConfirm: function() {
                        self.doDeleteDirection(d.id);
                    }
                });
            },
            doDeleteDirection: function(directionId) {
                var self = this;
                var base = this.apiBase();
                if (!base) {
                    return;
                }
                fetch(base + '/directions/' + encodeURIComponent(String(directionId)), {
                    method: 'DELETE',
                    headers: this.authHeaders(),
                    credentials: 'include'
                })
                    .then(function(r) {
                        if (!r.ok && r.status !== 204) {
                            throw new Error(self.$t('main.guarantor.error_load'));
                        }
                        if (self.directionEditingId === directionId) {
                            self.cancelEditDirection();
                        }
                        self.fetchState();
                    })
                    .catch(function() {});
            },
            startEditDirection: function(d) {
                this.directionEditingId = d.id;
                this.directionEditDraft =
                    d.conditions_text !== null && d.conditions_text !== undefined
                        ? String(d.conditions_text)
                        : '';
                this.directionEditError = null;
            },
            cancelEditDirection: function() {
                this.directionEditingId = null;
                this.directionEditDraft = '';
                this.directionEditError = null;
            },
            saveDirectionConditions: function(d) {
                var self = this;
                if (this.directionEditingId !== d.id) {
                    return;
                }
                var base = this.apiBase();
                if (!base) {
                    return;
                }
                var text = (this.directionEditDraft || '').trim();
                this.directionEditSaving = true;
                this.directionEditError = null;
                fetch(base + '/directions/' + encodeURIComponent(String(d.id)), {
                    method: 'PATCH',
                    headers: this.authHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ conditions_text: text ? text : null })
                })
                    .then(function(r) {
                        if (r.status === 403) {
                            throw new Error(self.$t('main.guarantor.error_403'));
                        }
                        if (!r.ok) {
                            return r.json().then(function(j) {
                                var msg = self._formatPatchErrorBody(j);
                                throw new Error(msg || self.$t('main.guarantor.error_load'));
                            });
                        }
                        return r.json();
                    })
                    .then(function() {
                        self.cancelEditDirection();
                        self.fetchState();
                    })
                    .catch(function(e) {
                        self.directionEditError = (e && e.message) || self.$t('main.guarantor.error_load');
                    })
                    .finally(function() {
                        self.directionEditSaving = false;
                    });
            },
            onDocumentClick: function(e) {
                if (!this.$el || !this.$el.contains(e.target)) {
                    return;
                }
                if (e.target.closest('[data-guarantor-ac]')) {
                    return;
                }
                if (this.modal) {
                    this.modal.currencyOpen = false;
                    this.modal.paymentOpen = false;
                }
            },
            _clearModalCurrencyBlurTimer: function() {
                if (this._modalCurrencyBlurTimer) {
                    clearTimeout(this._modalCurrencyBlurTimer);
                    this._modalCurrencyBlurTimer = null;
                }
            },
            _clearModalPaymentBlurTimer: function() {
                if (this._modalPaymentBlurTimer) {
                    clearTimeout(this._modalPaymentBlurTimer);
                    this._modalPaymentBlurTimer = null;
                }
            },
            onModalCurrencyFocus: function() {
                this._clearModalCurrencyBlurTimer();
                var m = this.modal;
                m.currencyOpen = true;
                this.fetchCurrenciesList(m, (m.currencyInput || '').trim(), AC_LIMIT_FOCUS);
            },
            onModalCurrencyBlur: function() {
                var self = this;
                this._clearModalCurrencyBlurTimer();
                this._modalCurrencyBlurTimer = setTimeout(function() {
                    self._modalCurrencyBlurTimer = null;
                    if (self.modal) {
                        self.modal.currencyOpen = false;
                    }
                }, MODAL_AC_BLUR_MS);
            },
            toggleModalCurrencyDropdown: function() {
                this._clearModalCurrencyBlurTimer();
                var m = this.modal;
                if (m.currencyOpen) {
                    m.currencyOpen = false;
                } else {
                    m.currencyOpen = true;
                    this.fetchCurrenciesList(m, (m.currencyInput || '').trim(), AC_LIMIT_FOCUS);
                }
            },
            onModalPaymentFocus: function() {
                this._clearModalPaymentBlurTimer();
                var m = this.modal;
                if (!m.currencyCode) {
                    return;
                }
                if (m.paymentCode === '*') {
                    return;
                }
                m.paymentOpen = true;
                this.fetchPaymentsList(m, (m.paymentInput || '').trim(), AC_LIMIT_PAYMENT_FOCUS);
            },
            onModalPaymentBlur: function() {
                var self = this;
                this._clearModalPaymentBlurTimer();
                this._modalPaymentBlurTimer = setTimeout(function() {
                    self._modalPaymentBlurTimer = null;
                    if (self.modal) {
                        self.modal.paymentOpen = false;
                    }
                }, MODAL_AC_BLUR_MS);
            },
            toggleModalPaymentDropdown: function() {
                this._clearModalPaymentBlurTimer();
                var m = this.modal;
                if (!m.currencyCode) {
                    return;
                }
                if (m.paymentCode === '*') {
                    return;
                }
                if (m.paymentOpen) {
                    m.paymentOpen = false;
                } else {
                    m.paymentOpen = true;
                    this.fetchPaymentsList(m, (m.paymentInput || '').trim(), AC_LIMIT_PAYMENT_FOCUS);
                }
            },
            onModalCurrencyInput: function() {
                var self = this;
                var m = this.modal;
                var v = (m.currencyInput || '').trim();
                m.currencyNoHits = false;
                if (m.currencyCode && v !== m.currencyCode) {
                    m.currencyCode = '';
                    m.paymentCode = '';
                    m.paymentName = '';
                    m.paymentInput = '';
                    m.paymentSuggestions = [];
                    m.paymentTotalForCur = null;
                    m.paymentNoHits = false;
                }
                if (!m.currencyCode) {
                    m.paymentCode = '';
                    m.paymentName = '';
                    m.paymentInput = '';
                    m.paymentSuggestions = [];
                    m.paymentTotalForCur = null;
                    m.paymentNoHits = false;
                }
                clearTimeout(m._currencyTimer);
                m._currencyTimer = setTimeout(function() {
                    self.fetchCurrenciesList(m, (m.currencyInput || '').trim(), AC_LIMIT_TYPE);
                }, DEBOUNCE_MS);
            },
            onModalPaymentInput: function() {
                var self = this;
                var m = this.modal;
                if (m.paymentCode === '*') {
                    return;
                }
                var v = (m.paymentInput || '').trim();
                m.paymentNoHits = false;
                if (m.paymentCode && v !== (m.paymentName || '').trim()) {
                    m.paymentCode = '';
                    m.paymentName = '';
                }
                clearTimeout(m._paymentTimer);
                m._paymentTimer = setTimeout(function() {
                    self.fetchPaymentsList(m, (m.paymentInput || '').trim(), AC_LIMIT_TYPE);
                }, DEBOUNCE_MS);
            },
            fetchCurrenciesList: function(b, q, limit) {
                var self = this;
                if (!b._currencyFetchGen) {
                    b._currencyFetchGen = 0;
                }
                b._currencyFetchGen += 1;
                var gen = b._currencyFetchGen;
                var url =
                    '/v1/autocomplete/currencies?is_fiat=true&limit=' +
                    encodeURIComponent(String(limit)) +
                    (q ? '&q=' + encodeURIComponent(q) : '');
                fetch(url, { credentials: 'same-origin' })
                    .then(function(r) {
                        return r.json();
                    })
                    .then(function(data) {
                        if (gen !== b._currencyFetchGen) {
                            return;
                        }
                        b.currencySuggestions = data.items || [];
                        b.currencyNoHits = b.currencySuggestions.length === 0 && (q && q.length >= 1);
                        b.currencyOpen = true;
                        self.$forceUpdate();
                    })
                    .catch(function() {
                        if (gen !== b._currencyFetchGen) {
                            return;
                        }
                        b.currencySuggestions = [];
                        b.currencyNoHits = false;
                        self.$forceUpdate();
                    });
            },
            fetchPaymentsList: function(b, q, limit) {
                if (!b.currencyCode) {
                    b.paymentSuggestions = [];
                    b.paymentTotalForCur = null;
                    return;
                }
                if (b.paymentCode === '*') {
                    return;
                }
                var self = this;
                if (!b._paymentFetchGen) {
                    b._paymentFetchGen = 0;
                }
                b._paymentFetchGen += 1;
                var gen = b._paymentFetchGen;
                var loc = appLocale();
                var url =
                    '/v1/autocomplete/directions?locale=' +
                    encodeURIComponent(loc) +
                    '&limit=' +
                    encodeURIComponent(String(limit)) +
                    '&cur=' +
                    encodeURIComponent(b.currencyCode) +
                    (q ? '&q=' + encodeURIComponent(q) : '');
                fetch(url, { credentials: 'same-origin' })
                    .then(function(r) {
                        return r.json();
                    })
                    .then(function(data) {
                        if (gen !== b._paymentFetchGen) {
                            return;
                        }
                        b.paymentSuggestions = data.items || [];
                        b.paymentTotalForCur =
                            typeof data.total_for_cur === 'number' ? data.total_for_cur : null;
                        b.paymentNoHits = b.paymentSuggestions.length === 0 && (q && q.length >= 1);
                        b.paymentOpen = true;
                        self.$forceUpdate();
                    })
                    .catch(function() {
                        if (gen !== b._paymentFetchGen) {
                            return;
                        }
                        b.paymentSuggestions = [];
                        b.paymentTotalForCur = null;
                        b.paymentNoHits = false;
                        self.$forceUpdate();
                    });
            },
            selectModalCurrency: function(item) {
                this._clearModalCurrencyBlurTimer();
                var m = this.modal;
                m.currencyCode = item.code;
                m.currencyInput = item.code;
                m.currencyOpen = false;
                m.currencyNoHits = false;
                m.paymentCode = '';
                m.paymentName = '';
                m.paymentInput = '';
                m.paymentSuggestions = [];
                m.paymentTotalForCur = null;
                m.paymentNoHits = false;
            },
            selectModalPayment: function(item) {
                this._clearModalPaymentBlurTimer();
                var m = this.modal;
                m.paymentCode = item.payment_code;
                m.paymentName = item.name;
                m.paymentInput = item.name;
                m.paymentOpen = false;
                m.paymentNoHits = false;
            },
            onToggleAllPaymentMethods: function(e) {
                var m = this.modal;
                if (e.target.checked) {
                    m.paymentCode = '*';
                    var label = this.$t('main.guarantor.all_payment_methods_label');
                    m.paymentName = label;
                    m.paymentInput = label;
                    m.paymentOpen = false;
                    m.paymentSuggestions = [];
                    m.paymentTotalForCur = null;
                    m.paymentNoHits = false;
                } else {
                    m.paymentCode = '';
                    m.paymentName = '';
                    m.paymentInput = '';
                    m.paymentSuggestions = [];
                    m.paymentTotalForCur = null;
                    m.paymentNoHits = false;
                }
            },
            directionCurrencyLabel: function(d) {
                return d.currency_code || '—';
            },
            directionPaymentLabel: function(d) {
                if (d.payment_code === '*') {
                    return this.$t('main.guarantor.all_payment_methods_label');
                }
                return d.payment_name || d.payment_code || '—';
            }
        },
        template: [
            '<div class="max-w-7xl mx-auto px-4 py-6 md:py-8">',
            '  <div v-if="loading" class="text-sm text-[#58667e] py-8">[[ $t(\'main.guarantor.loading\') ]]</div>',
            '  <div v-else-if="loadError" class="rounded-xl border border-red-200 bg-red-50 text-red-800 px-4 py-3 text-sm">[[ loadError ]]</div>',
            '  <div v-else class="flex flex-col lg:flex-row gap-6 lg:gap-8 lg:items-start">',
            '    <div class="flex-1 min-w-0 space-y-6">',
            '      <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">',
            '        <div class="min-w-0">',
            '          <h1 class="text-xl md:text-2xl font-bold text-[#191d23] flex items-center gap-3">',
            '            <span class="inline-flex w-9 h-9 md:w-10 md:h-10 rounded-xl bg-main-blue/10 text-main-blue items-center justify-center shrink-0">',
            '              <svg class="w-5 h-5 md:w-6 md:h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>',
            '            </span>',
            '            <span>[[ $t(\'main.guarantor.title\') ]]</span>',
            '          </h1>',
            '          <p class="text-sm text-[#58667e] mt-1 max-w-2xl">[[ $t(\'main.guarantor.subtitle\') ]]</p>',
            '        </div>',
            '      </div>',
            '      <div class="flex flex-col sm:flex-row gap-4 sm:items-stretch">',
            '        <div class="rounded-xl border border-[#eff2f5] bg-white shadow-sm p-4 md:p-5 sm:flex-1 min-w-0">',
            '          <div class="text-xs font-medium text-[#58667e] mb-2">[[ $t(\'main.guarantor.commission_card_label\') ]]</div>',
            '          <div class="flex items-center gap-2 flex-wrap">',
            '            <input v-model.number="commissionPercent" type="number" min="0.1" max="100" step="0.1" @input="onCommissionInput" :disabled="loading" :aria-busy="commissionSyncing ? \'true\' : \'false\'" class="w-20 px-2 py-1.5 rounded-lg border border-[#eff2f5] text-sm font-bold text-main-blue text-center focus:outline-none focus:ring-2 focus:ring-main-blue/20 disabled:opacity-60" />',
            '            <span class="text-sm text-[#58667e]">%</span>',
            '            <span v-show="commissionSyncing" class="inline-flex h-5 w-5 shrink-0 text-main-blue" aria-hidden="true">',
            '              <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
            '            </span>',
            '          </div>',
            '          <p v-if="commissionFeedback" class="mt-2 text-xs leading-snug" :class="commissionFeedback.type === \'success\' ? \'text-emerald-700\' : \'text-red-600\'">[[ commissionFeedback.text ]]</p>',
            '        </div>',
            '        <div class="rounded-xl border border-main-blue/20 bg-main-blue/[0.06] p-4 md:p-5 sm:flex-1 min-w-0">',
            '          <template v-if="isVerified">',
            '            <h3 class="text-sm font-bold text-[#191d23] mb-2">[[ $t(\'main.guarantor.verification_title\') ]]</h3>',
            '            <p class="text-xs text-[#58667e] leading-relaxed mb-4">[[ $t(\'main.guarantor.verification_text\') ]]</p>',
            '            <div class="inline-flex items-center gap-2 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 px-3 py-1.5 text-xs font-semibold">',
            '              <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>',
            '              [[ $t(\'main.guarantor.status_active\') ]]',
            '            </div>',
            '          </template>',
            '          <template v-else>',
            '            <h3 class="text-sm font-bold text-[#191d23] mb-2">[[ $t(\'main.guarantor.verification_title_none\') ]]</h3>',
            '            <p class="text-xs text-[#58667e] leading-relaxed mb-4">[[ $t(\'main.guarantor.verification_need_kyc\') ]]</p>',
            '            <div class="flex flex-wrap items-center justify-between gap-3">',
            '              <div class="inline-flex items-center gap-2 rounded-full bg-amber-50 text-amber-800 border border-amber-200/80 px-3 py-1.5 text-xs font-semibold">',
            '                [[ $t(\'main.guarantor.status_not_verified\') ]]',
            '              </div>',
            '              <button type="button" @click="openVerificationInfoModal" class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-main-blue text-white shadow-md shadow-main-blue/30 ring-2 ring-white hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-main-blue/40" :title="$t(\'main.guarantor.verification_info_aria\')" :aria-label="$t(\'main.guarantor.verification_info_aria\')">',
            '                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '              </button>',
            '            </div>',
            '          </template>',
            '        </div>',
            '      </div>',
            '      <section>',
            '        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">',
            '          <h2 class="text-sm font-bold text-[#191d23] tracking-tight">[[ $t(\'main.guarantor.section_directions\') ]]</h2>',
            '          <button type="button" @click="openAddModal" class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-main-blue text-white hover:opacity-90 transition-opacity shrink-0">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '            [[ $t(\'main.guarantor.add_block\') ]]',
            '          </button>',
            '        </div>',
            '        <div class="space-y-4">',
            '          <article v-for="d in directions" :key="d.id" class="rounded-xl border border-[#eff2f5] bg-white shadow-sm p-4 md:p-5">',
            '            <div class="flex flex-wrap items-start justify-between gap-3" :class="d.payment_code === \'*\' ? \'mb-2\' : \'mb-3\'">',
            '              <div class="flex flex-wrap items-center gap-2 min-w-0">',
            '                <span class="inline-flex items-center gap-1.5 rounded-full bg-[#f8fafd] border border-[#eff2f5] px-3 py-1 text-xs font-semibold text-[#191d23]">',
            '                  <svg class="w-3.5 h-3.5 text-main-blue shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '                  [[ directionCurrencyLabel(d) ]]',
            '                </span>',
            '                <span class="inline-flex items-center gap-1.5 rounded-full bg-[#f8fafd] border border-[#eff2f5] px-3 py-1 text-xs font-semibold text-[#191d23]">',
            '                  <svg class="w-3.5 h-3.5 text-main-blue shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>',
            '                  [[ directionPaymentLabel(d) ]]',
            '                </span>',
            '              </div>',
            '              <button type="button" @click="confirmDeleteDirection(d)" class="shrink-0 text-xs font-semibold text-red-600 hover:text-red-700 px-2 py-1 rounded-lg hover:bg-red-50">[[ $t(\'main.guarantor.delete_direction\') ]]</button>',
            '            </div>',
            '            <p v-if="d.payment_code === \'*\'" class="mb-3 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">[[ $t(\'main.guarantor.all_methods_geo_rank_hint\', { currency: d.currency_code }) ]]</p>',
            '            <div class="rounded-lg bg-[#f8fafd] border border-[#eff2f5] p-3 md:p-4">',
            '              <div class="flex flex-wrap items-center justify-between gap-2 mb-2">',
            '                <div class="text-[10px] font-bold text-[#58667e] uppercase tracking-wider min-w-0">[[ $t(\'main.guarantor.conditions_label\') ]]</div>',
            '                <template v-if="directionEditingId === d.id">',
            '                  <div class="flex flex-wrap items-center gap-2 shrink-0">',
            '                    <button type="button" @click="cancelEditDirection" :disabled="directionEditSaving" class="text-xs font-medium text-[#58667e] hover:bg-[#eff2f5] px-2 py-1 rounded-lg disabled:opacity-50">[[ $t(\'main.guarantor.modal_cancel\') ]]</button>',
            '                    <button type="button" @click="saveDirectionConditions(d)" :disabled="directionEditSaving" class="text-xs font-semibold text-white bg-main-blue px-3 py-1 rounded-lg hover:opacity-90 disabled:opacity-50">[[ $t(\'main.guarantor.save_conditions\') ]]</button>',
            '                  </div>',
            '                </template>',
            '                <button v-else type="button" @click="startEditDirection(d)" class="text-xs font-semibold text-main-blue hover:underline px-2 py-1 rounded-lg shrink-0">[[ $t(\'main.guarantor.edit_conditions\') ]]</button>',
            '              </div>',
            '              <textarea v-if="directionEditingId === d.id" v-model="directionEditDraft" rows="4" class="w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm text-[#191d23] focus:outline-none focus:ring-2 focus:ring-main-blue/20" :placeholder="$t(\'main.guarantor.placeholder_conditions\')"></textarea>',
            '              <p v-else class="text-sm text-[#191d23] leading-relaxed whitespace-pre-wrap">[[ (d.conditions_text && d.conditions_text.length) ? d.conditions_text : $t(\'main.guarantor.placeholder_conditions\') ]]</p>',
            '              <p v-if="directionEditError && directionEditingId === d.id" class="mt-2 text-xs text-red-600">[[ directionEditError ]]</p>',
            '            </div>',
            '          </article>',
            '          <p v-if="!directions.length" class="text-sm text-[#58667e] py-2">[[ $t(\'main.guarantor.no_directions\') ]]</p>',
            '        </div>',
            '      </section>',
            '    </div>',
            '    <aside class="w-full lg:w-80 shrink-0 space-y-4">',
            '      <div class="rounded-xl border border-[#0a0b0d]/10 bg-[#0a0b0d] text-white p-4 md:p-5 shadow-sm">',
            '        <div class="flex items-start gap-3">',
            '          <span class="inline-flex w-8 h-8 rounded-lg bg-main-blue/20 text-main-blue items-center justify-center shrink-0">',
            '            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            '          </span>',
            '          <div class="min-w-0">',
            '            <h3 class="text-sm font-bold mb-2">[[ $t(\'main.guarantor.rules_title\') ]]</h3>',
            '            <ul class="text-xs text-white/80 space-y-2 list-disc list-inside leading-relaxed">',
            '              <li>[[ $t(\'main.guarantor.rules_item_1\') ]]</li>',
            '              <li>[[ $t(\'main.guarantor.rules_item_2\') ]]</li>',
            '              <li>[[ $t(\'main.guarantor.rules_item_3\') ]]</li>',
            '            </ul>',
            '          </div>',
            '        </div>',
            '      </div>',
            '    </aside>',
            '  </div>',
            '  <div v-if="showAddDirectionErrorModal" class="fixed inset-0 z-[92] flex items-center justify-center p-4 bg-black/50" @click.self="closeAddDirectionErrorModal">',
            '    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-5 md:p-6 border border-amber-200 ring-1 ring-amber-100" @click.stop role="alertdialog" aria-modal="true" aria-labelledby="guarantor-direction-error-title">',
            '      <h2 id="guarantor-direction-error-title" class="text-lg font-bold text-[#191d23] mb-3">[[ $t(\'main.guarantor.direction_error_modal_title\') ]]</h2>',
            '      <p class="text-sm text-[#58667e] leading-relaxed mb-6 whitespace-pre-wrap break-words">[[ addDirectionErrorMessage ]]</p>',
            '      <div class="flex justify-end">',
            '        <button type="button" @click="closeAddDirectionErrorModal" class="px-4 py-2 text-sm font-semibold text-white bg-main-blue rounded-lg hover:opacity-90">[[ $t(\'main.guarantor.direction_error_modal_close\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '  <div v-if="showVerificationInfoModal" class="fixed inset-0 z-[91] flex items-center justify-center p-4 bg-black/50" @click.self="closeVerificationInfoModal">',
            '    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-5 md:p-6 border border-[#eff2f5]" @click.stop role="dialog" aria-modal="true" :aria-label="$t(\'main.guarantor.verification_info_aria\')">',
            '      <h2 class="text-lg font-bold text-[#191d23] mb-3">[[ $t(\'main.guarantor.verification_info_modal_title\') ]]</h2>',
            '      <p class="text-sm text-[#58667e] leading-relaxed mb-6">[[ $t(\'main.guarantor.verification_info_modal_text\') ]]</p>',
            '      <div class="flex justify-end">',
            '        <button type="button" @click="closeVerificationInfoModal" class="px-4 py-2 text-sm font-semibold text-white bg-main-blue rounded-lg hover:opacity-90">[[ $t(\'main.guarantor.verification_info_modal_close\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '  <div v-if="showAddModal" class="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/50" @click.self="closeAddModal">',
            '    <div class="bg-white rounded-2xl shadow-xl max-w-lg w-full p-5 md:p-6 border border-[#eff2f5] max-h-[90vh] overflow-y-auto" @click.stop>',
            '      <h2 class="text-lg font-bold text-[#191d23] mb-4">[[ $t(\'main.guarantor.modal_add_title\') ]]</h2>',
            '      <div data-guarantor-ac class="space-y-4 mb-4">',
            '        <div class="relative">',
            '          <label class="block text-xs font-medium text-[#58667e] mb-1">[[ $t(\'main.guarantor.currency_placeholder\') ]]</label>',
            '          <div class="flex rounded-lg border border-[#eff2f5] bg-white overflow-hidden focus-within:ring-2 focus-within:ring-main-blue/20">',
            '            <input v-model="modal.currencyInput" type="text" :placeholder="$t(\'main.guarantor.currency_placeholder\')" autocomplete="off" @focus="onModalCurrencyFocus" @blur="onModalCurrencyBlur" @input="onModalCurrencyInput" class="flex-1 min-w-0 border-0 rounded-none px-3 py-2 text-sm text-[#191d23] focus:outline-none focus:ring-0" />',
            '            <button type="button" @mousedown.prevent @click.stop="toggleModalCurrencyDropdown" :aria-expanded="modal.currencyOpen ? \'true\' : \'false\'" :aria-label="$t(\'main.guarantor.ac_open_currency_list\')" class="shrink-0 px-2.5 border-l border-[#eff2f5] bg-[#f8fafd] text-main-blue hover:bg-main-blue/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-main-blue/30">',
            '              <svg class="w-5 h-5 transition-transform duration-200" :class="modal.currencyOpen ? \'rotate-180\' : \'\'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>',
            '            </button>',
            '          </div>',
            '          <ul v-show="modal.currencyOpen && (modal.currencySuggestions.length > 0 || modal.currencyNoHits || (modal.currencyInput || \'\').trim().length < 1)" @mousedown="_clearModalCurrencyBlurTimer" class="absolute left-0 right-0 top-full mt-1 z-30 max-h-40 overflow-y-auto rounded-lg border border-[#eff2f5] bg-white shadow-lg py-1 text-sm">',
            '            <li v-for="c in modal.currencySuggestions" :key="c.code"><button type="button" class="w-full text-left px-3 py-2 hover:bg-[#f8fafd]" @mousedown.prevent @click.stop="selectModalCurrency(c)">[[ c.code ]]</button></li>',
            '            <li v-if="modal.currencyNoHits && !modal.currencySuggestions.length" class="px-3 py-2 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</li>',
            '          </ul>',
            '        </div>',
            '        <div class="relative">',
            '          <label class="block text-xs font-medium text-[#58667e] mb-1">[[ $t(\'main.guarantor.payment_placeholder\') ]]</label>',
            '          <label v-if="modal.currencyCode" class="flex items-start gap-2 mb-2 text-xs text-[#58667e] cursor-pointer select-none">',
            '            <input type="checkbox" :checked="modal.paymentCode === \'*\'" @change="onToggleAllPaymentMethods" class="mt-0.5 rounded border-[#cbd6e2] text-main-blue focus:ring-main-blue/30" />',
            '            <span>[[ $t(\'main.guarantor.all_payment_methods_option\') ]]</span>',
            '          </label>',
            '          <div :class="!modal.currencyCode ? \'flex rounded-lg border border-[#eff2f5] bg-[#f8fafd] overflow-hidden opacity-90\' : (modal.paymentCode === \'*\' ? \'flex rounded-lg border border-[#eff2f5] bg-[#f8fafd] overflow-hidden opacity-90\' : \'flex rounded-lg border border-[#eff2f5] bg-white overflow-hidden focus-within:ring-2 focus-within:ring-main-blue/20\')">',
            '            <input v-model="modal.paymentInput" type="text" :disabled="!modal.currencyCode || modal.paymentCode === \'*\'" :placeholder="modal.currencyCode ? $t(\'main.guarantor.payment_placeholder\') : $t(\'main.guarantor.select_currency_first\')" autocomplete="off" @focus="onModalPaymentFocus" @blur="onModalPaymentBlur" @input="onModalPaymentInput" :class="!modal.currencyCode || modal.paymentCode === \'*\' ? \'flex-1 min-w-0 border-0 rounded-none px-3 py-2 text-sm bg-transparent text-[#58667e] cursor-not-allowed\' : \'flex-1 min-w-0 border-0 rounded-none px-3 py-2 text-sm text-[#191d23] focus:outline-none focus:ring-0\'" />',
            '            <button type="button" :disabled="!modal.currencyCode || modal.paymentCode === \'*\'" @mousedown.prevent @click.stop="toggleModalPaymentDropdown" :aria-expanded="modal.paymentOpen ? \'true\' : \'false\'" :aria-label="$t(\'main.guarantor.ac_open_payment_list\')" :class="!modal.currencyCode || modal.paymentCode === \'*\' ? \'shrink-0 px-2.5 border-l border-[#eff2f5] bg-[#f8fafd] text-[#58667e] cursor-not-allowed\' : \'shrink-0 px-2.5 border-l border-[#eff2f5] bg-[#f8fafd] text-main-blue hover:bg-main-blue/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-main-blue/30\'">',
            '              <svg class="w-5 h-5 transition-transform duration-200" :class="modal.paymentOpen ? \'rotate-180\' : \'\'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>',
            '            </button>',
            '          </div>',
            '          <ul v-show="modal.paymentOpen && modal.currencyCode && modal.paymentCode !== \'*\' && (modal.paymentSuggestions.length > 0 || modal.paymentNoHits || (modal.paymentInput || \'\').trim().length < 1)" @mousedown="_clearModalPaymentBlurTimer" class="absolute left-0 right-0 top-full mt-1 z-30 max-h-40 overflow-y-auto rounded-lg border border-[#eff2f5] bg-white shadow-lg py-1 text-sm">',
            '            <li v-if="modal.paymentTotalForCur != null" class="sticky top-0 z-10 px-3 py-1.5 text-[10px] font-medium text-[#58667e] bg-[#fafbfc] border-b border-[#eff2f5]">[[ $t(\'main.guarantor.payment_total_for_currency\', { count: modal.paymentTotalForCur }) ]]</li>',
            '            <li v-for="p in modal.paymentSuggestions" :key="p.payment_code"><button type="button" class="w-full text-left px-3 py-2 hover:bg-[#f8fafd]" @mousedown.prevent @click.stop="selectModalPayment(p)"><span class="font-medium">[[ p.name ]]</span><span class="text-[#58667e] text-xs ml-1">[[ p.cur ]] · [[ p.payment_code ]]</span></button></li>',
            '            <li v-if="modal.paymentNoHits && !modal.paymentSuggestions.length" class="px-3 py-2 text-xs text-[#58667e]">[[ $t(\'main.guarantor.no_results\') ]]</li>',
            '          </ul>',
            '          <p v-if="modal.paymentCode === \'*\'" class="mt-2 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">[[ $t(\'main.guarantor.all_methods_geo_rank_hint\', { currency: modal.currencyCode }) ]]</p>',
            '        </div>',
            '        <div>',
            '          <label class="block text-xs font-medium text-[#58667e] mb-1">[[ $t(\'main.guarantor.conditions_label\') ]]</label>',
            '          <textarea v-model="conditionsDraft" rows="3" class="w-full px-3 py-2 rounded-lg border border-[#eff2f5] text-sm text-[#191d23] focus:outline-none focus:ring-2 focus:ring-main-blue/20" :placeholder="$t(\'main.guarantor.placeholder_conditions\')"></textarea>',
            '        </div>',
            '      </div>',
            '      <div class="flex justify-end gap-2 flex-wrap">',
            '        <button type="button" @click="closeAddModal" class="px-4 py-2 text-sm font-medium text-[#58667e] hover:bg-[#f8fafd] rounded-lg">[[ $t(\'main.guarantor.modal_cancel\') ]]</button>',
            '        <button type="button" @click="submitAddModal" :disabled="!modal.currencyCode || !modal.paymentCode || !(conditionsDraft || \'\').trim().length" class="px-4 py-2 text-sm font-semibold text-white bg-main-blue rounded-lg hover:opacity-90 disabled:opacity-50">[[ $t(\'main.guarantor.modal_save\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
