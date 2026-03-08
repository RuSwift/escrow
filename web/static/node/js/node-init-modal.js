/**
 * NodeInitModal — пошаговая модалка инициализации ноды (ключ, admin, service endpoint).
 * API: /v1/node/*, /v1/admin/*. Подключать после vue.min.js и modal.js.
 */
(function() {
    var API_BASE = '/v1';
    var NODE_API = API_BASE + '/node';
    var ADMIN_API = API_BASE + '/admin';

    Vue.component('node-init-modal', {
        delimiters: ['[[', ']]'],
        data: function() {
            return {
                show: false,
                currentStep: 1,
                currentMethod: 'pem',
                mouseEntropy: [],
                entropyProgress: 0,
                requiredEntropy: 256,
                isCollecting: false,
                lastX: 0,
                lastY: 0,
                canvas: null,
                ctx: null,
                result: null,
                status: { message: '', type: '', visible: false },
                pemFile: null,
                pemPassword: '',
                pemContent: '',
                rootCredentialMethod: 'password',
                rootUsername: '',
                rootPassword: '',
                rootPasswordConfirm: '',
                rootTronAddress: null,
                rootTronAuthenticated: false,
                savingCredentials: false,
                serviceEndpoint: '',
                testingEndpoint: false,
                endpointVerified: false,
                endpointTestResult: null,
                savingEndpoint: false,
                tronConnecting: false
            };
        },
        computed: {
            stepTitle: function() {
                return this.t('node.init.step_title', { step: this.currentStep });
            },
            entropyProgressText: function() {
                return this.t('node.init.entropy_progress', { percent: this.entropyProgressPercent });
            },
            connectedLabel: function() {
                return this.$t('node.init.connected') + ': ' + this.rootTronAddress;
            },
            footerButtonText: function() {
                if (this.currentStep === 3) return this.$t('node.init.finish_endpoint');
                if (this.currentStep === 2) return this.$t('node.init.finish_root');
                if (!this.result) return this.$t('node.init.init_node_first');
                return this.$t('node.init.close');
            },
            canGenerateFromMouse: function() {
                return this.entropyProgress >= 100;
            },
            entropyProgressPercent: function() {
                return Math.round(this.entropyProgress);
            }
        },
        mounted: function() {
            var self = this;
            var initScript = document.getElementById('is-node-initialized');
            var hasKey = false;
            var nodeInitialized = false;
            var adminConfigured = false;
            if (initScript) {
                try {
                    var data = JSON.parse(initScript.textContent);
                    if (typeof data === 'boolean') {
                        hasKey = data;
                        nodeInitialized = data;
                        adminConfigured = data;
                    } else {
                        hasKey = !!data.has_key;
                        nodeInitialized = !!data.is_node_initialized;
                        adminConfigured = !!data.is_admin_configured;
                    }
                } catch (e) {}
            }
            if (!nodeInitialized) {
                self.show = true;
                if (!hasKey) {
                    self.currentStep = 1;
                    self.$nextTick(function() { self.initCanvas(); });
                } else if (!adminConfigured) {
                    self.currentStep = 2;
                    self.result = { address: 'Already initialized', keyType: 'existing', message: self.$t('node.init.key_already_created') };
                } else {
                    self.currentStep = 3;
                    self.result = { address: 'Already initialized', keyType: 'existing' };
                    self.serviceEndpoint = self.getDefaultEndpoint();
                    self.endpointVerified = false;
                    self.loadExistingEndpoint();
                }
            }
        },
        methods: {
            t: function(key, params) {
                var s = this.$t(key);
                if (params && typeof params === 'object') {
                    for (var k in params) s = s.replace(new RegExp('\\{' + k + '\\}', 'g'), String(params[k]));
                }
                return s;
            },
            getDefaultEndpoint: function() {
                return window.location.origin + '/didcomm/endpoint';
            },
            initCanvas: function() {
                var self = this;
                this.$nextTick(function() {
                    var canvas = self.$refs.entropyCanvas;
                    if (canvas) {
                        self.canvas = canvas;
                        self.ctx = canvas.getContext('2d');
                        canvas.width = canvas.offsetWidth;
                        canvas.height = canvas.offsetHeight;
                    }
                });
            },
            switchMethod: function(method) {
                this.currentMethod = method;
                this.resetForm();
                if (method === 'mouse') this.$nextTick(function() { this.initCanvas(); });
            },
            switchRootCredentialMethod: function(method) {
                this.rootCredentialMethod = method;
                this.rootUsername = '';
                this.rootPassword = '';
                this.rootPasswordConfirm = '';
                this.rootTronAddress = null;
                this.rootTronAuthenticated = false;
                this.hideStatus();
            },
            handlePemFileSelect: function(event) {
                var file = event.target.files[0];
                if (!file) return;
                this.pemFile = file;
                var self = this;
                var reader = new FileReader();
                reader.onload = function(e) { self.pemContent = e.target.result; };
                reader.onerror = function() { self.showStatus(self.$t('node.init.error_file_read'), 'error'); };
                reader.readAsText(file);
            },
            generateFromPem: function() {
                var self = this;
                if (!this.pemContent) {
                    this.showStatus(this.$t('node.init.error_select_pem'), 'error');
                    return;
                }
                this.showStatus(this.$t('node.init.processing_pem'), 'info');
                fetch(NODE_API + '/init-pem', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pem_data: this.pemContent, password: this.pemPassword || null })
                }).then(function(r) {
                    return r.json().then(function(data) {
                        if (!r.ok) throw new Error(data.detail || self.$t('node.init.error_pem_process'));
                        return data;
                    });
                }).then(function(data) {
                    self.result = { address: data.address, keyType: data.key_type };
                    self.showStatus(self.$t('node.init.key_saved_next_step'), 'success');
                }).catch(function(err) {
                    self.showStatus(self.$t('node.init.error_prefix') + (err.message || err), 'error');
                });
            },
            proceedToStep2: function() {
                var self = this;
                if (!this.result) {
                    fetch(NODE_API + '/key-info', { credentials: 'same-origin' })
                        .then(function(r) {
                            if (r.ok) {
                                self.result = { address: 'Already initialized', keyType: 'existing', message: self.$t('node.init.key_already_created') };
                                self.currentStep = 2;
                                self.hideStatus();
                            } else {
                                self.showStatus(self.$t('node.init.finish_key_first'), 'error');
                            }
                        })
                        .catch(function() { self.showStatus(self.$t('node.init.finish_key_first'), 'error'); });
                    return;
                }
                this.currentStep = 2;
                this.hideStatus();
            },
            backToStep1: function() {
                this.currentStep = 1;
                this.hideStatus();
            },
            handleTronAuthComplete: function(address, token) {
                this.rootTronAddress = address;
                this.rootTronAuthenticated = true;
                if (token) {
                    var d = new Date();
                    d.setTime(d.getTime() + 24 * 60 * 60 * 1000);
                    document.cookie = 'admin_token=' + token + '; expires=' + d.toUTCString() + '; path=/; SameSite=Lax';
                }
                this.showStatus(this.$t('node.init.tron_connected_root'), 'success');
            },
            connectTronWallet: function() {
                var self = this;
                if (!window.tronWeb || !window.tronWeb.defaultAddress || !window.tronWeb.defaultAddress.base58) {
                    this.showStatus(this.$t('node.init.install_tronlink'), 'error');
                    return;
                }
                var tronAddress = window.tronWeb.defaultAddress.base58;
                this.tronConnecting = true;
                this.showStatus(this.$t('node.init.connecting'), 'info');
                fetch(ADMIN_API + '/tron/nonce', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tron_address: tronAddress })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    var message = data.message || data.nonce;
                    return window.tronWeb.trx.signMessageV2(message).then(function(signature) {
                        return fetch(ADMIN_API + '/tron/verify', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ tron_address: tronAddress, signature: signature, message: message })
                        });
                    });
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.token) {
                        self.handleTronAuthComplete(tronAddress, data.token);
                    } else {
                        self.showStatus(data.detail || self.$t('node.init.error_verify'), 'error');
                    }
                }).catch(function(err) {
                    self.showStatus(self.$t('node.init.error_prefix') + (err.message || err), 'error');
                }).finally(function() {
                    self.tronConnecting = false;
                });
            },
            saveRootCredentials: function() {
                var self = this;
                if (this.rootCredentialMethod === 'password') {
                    if (!this.rootUsername || !this.rootPassword) {
                        this.showStatus(this.$t('node.init.enter_login_password'), 'error');
                        return;
                    }
                    if (this.rootPassword.length < 8) {
                        this.showStatus(this.$t('node.init.password_min_8'), 'error');
                        return;
                    }
                    if (this.rootPassword !== this.rootPasswordConfirm) {
                        this.showStatus(this.$t('node.init.passwords_mismatch'), 'error');
                        return;
                    }
                } else {
                    if (!this.rootTronAuthenticated || !this.rootTronAddress) {
                        this.showStatus(this.$t('node.init.connect_tron_first'), 'error');
                        return;
                    }
                }
                this.savingCredentials = true;
                this.showStatus(this.$t('node.init.saving'), 'info');
                var url = this.rootCredentialMethod === 'password' ? ADMIN_API + '/set-password' : ADMIN_API + '/tron-addresses';
                var body = this.rootCredentialMethod === 'password'
                    ? { username: this.rootUsername, password: this.rootPassword }
                    : { tron_address: this.rootTronAddress, label: 'Root admin' };
                fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    credentials: 'same-origin'
                }).then(function(r) {
                    return r.json().then(function(data) {
                        if (!r.ok) throw new Error(data.detail || self.$t('node.init.error_saving'));
                        return data;
                    });
                }).then(function() {
                    self.showStatus(self.$t('node.init.root_creds_saved'), 'success');
                    setTimeout(function() { self.proceedToStep3(); }, 1500);
                }).catch(function(err) {
                    self.showStatus(self.$t('node.init.error_prefix') + (err.message || err), 'error');
                }).finally(function() {
                    self.savingCredentials = false;
                });
            },
            proceedToStep3: function() {
                this.currentStep = 3;
                this.hideStatus();
                this.serviceEndpoint = this.getDefaultEndpoint();
                this.endpointVerified = false;
                this.loadExistingEndpoint();
            },
            backToStep2: function() {
                this.currentStep = 2;
                this.hideStatus();
            },
            loadExistingEndpoint: function() {
                var self = this;
                fetch(NODE_API + '/service-endpoint', { credentials: 'same-origin' })
                    .then(function(r) { return r.ok ? r.json() : {}; })
                    .then(function(data) {
                        if (data.service_endpoint) {
                            self.serviceEndpoint = data.service_endpoint;
                            self.endpointVerified = true;
                        }
                    })
                    .catch(function() {});
            },
            testServiceEndpoint: function() {
                var self = this;
                if (!this.serviceEndpoint || !this.serviceEndpoint.trim()) {
                    this.showStatus(this.$t('node.init.enter_endpoint_url'), 'error');
                    return;
                }
                this.testingEndpoint = true;
                this.endpointVerified = false;
                this.endpointTestResult = null;
                this.showStatus(this.$t('node.init.checking_availability'), 'info');
                fetch(NODE_API + '/test-service-endpoint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service_endpoint: this.serviceEndpoint })
                }).then(function(r) { return r.json(); }).then(function(result) {
                    self.endpointTestResult = result;
                    if (result.success) {
                        self.endpointVerified = true;
                        self.showStatus(self.t('node.init.endpoint_available_ms', { ms: result.response_time_ms || '' }), 'success');
                    } else {
                        self.showStatus(result.message || self.$t('node.init.endpoint_unavailable'), 'error');
                    }
                }).catch(function(err) {
                    self.showStatus(self.$t('node.init.error_prefix') + (err.message || err), 'error');
                }).finally(function() {
                    self.testingEndpoint = false;
                });
            },
            saveServiceEndpoint: function() {
                var self = this;
                if (!this.serviceEndpoint || !this.serviceEndpoint.trim()) {
                    this.showStatus(this.$t('node.init.enter_endpoint_url'), 'error');
                    return;
                }
                if (!this.endpointVerified) {
                    this.showStatus(this.$t('node.init.test_endpoint_first'), 'error');
                    return;
                }
                this.savingEndpoint = true;
                this.showStatus(this.$t('node.init.saving'), 'info');
                fetch(NODE_API + '/set-service-endpoint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service_endpoint: this.serviceEndpoint }),
                    credentials: 'same-origin'
                }).then(function(r) {
                    return r.json().then(function(data) {
                        if (!r.ok) throw new Error(data.detail || self.$t('node.init.error_saving'));
                        return data;
                    });
                }).then(function() {
                    self.showStatus(self.$t('node.init.endpoint_saved_done'), 'success');
                    setTimeout(function() { self.closeModalComplete(); }, 2000);
                }).catch(function(err) {
                    self.showStatus(self.$t('node.init.error_prefix') + (err.message || err), 'error');
                }).finally(function() {
                    self.savingEndpoint = false;
                });
            },
            resetForm: function() {
                this.mouseEntropy = [];
                this.entropyProgress = 0;
                this.result = null;
                this.pemFile = null;
                this.pemPassword = '';
                this.pemContent = '';
                this.hideStatus();
                if (this.canvas && this.ctx) this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            },
            handleMouseDown: function(e) {
                if (!this.canvas) return;
                this.isCollecting = true;
                var rect = this.canvas.getBoundingClientRect();
                this.lastX = e.clientX - rect.left;
                this.lastY = e.clientY - rect.top;
            },
            handleMouseUp: function() { this.isCollecting = false; },
            handleMouseMove: function(e) {
                if (!this.isCollecting || !this.canvas || !this.ctx) return;
                var rect = this.canvas.getBoundingClientRect();
                var x = e.clientX - rect.left;
                var y = e.clientY - rect.top;
                var time = Date.now();
                this.mouseEntropy.push({ x: x, y: y, dx: x - this.lastX, dy: y - this.lastY, time: time, random: Math.random() });
                this.ctx.strokeStyle = 'hsl(' + (time % 360) + ', 70%, 50%)';
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.moveTo(this.lastX, this.lastY);
                this.ctx.lineTo(x, y);
                this.ctx.stroke();
                this.lastX = x;
                this.lastY = y;
                var estimatedBytes = this.mouseEntropy.length * 0.7;
                this.entropyProgress = Math.min(100, (estimatedBytes / this.requiredEntropy) * 100);
            },
            generateFromMouseEntropy: function() {
                var self = this;
                if (this.mouseEntropy.length < 50) {
                    this.showStatus(this.$t('node.init.move_mouse_entropy'), 'error');
                    return;
                }
                this.showStatus(this.$t('node.init.creating_key'), 'info');
                if (typeof ethers === 'undefined') {
                    this.showStatus(this.$t('node.init.need_ethers'), 'error');
                    return;
                }
                var entropyStr = '';
                this.mouseEntropy.forEach(function(entropy) {
                    entropyStr += entropy.x + ',' + entropy.y + ',' + entropy.dx + ',' + entropy.dy + ',' + entropy.time + ',' + entropy.random + '|';
                });
                entropyStr += Math.random() + ',' + Date.now() + ',' + performance.now();
                var encoder = new TextEncoder();
                var data = encoder.encode(entropyStr);
                var salt = encoder.encode('escrow-seed-' + Date.now());
                var self = this;
                crypto.subtle.importKey('raw', data, { name: 'PBKDF2' }, false, ['deriveBits']).then(function(keyMaterial) {
                    return crypto.subtle.deriveBits({ name: 'PBKDF2', salt: salt, iterations: 100000, hash: 'SHA-256' }, keyMaterial, 128);
                }).then(function(bits) {
                    var seedHex = Array.from(new Uint8Array(bits)).map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
                    var mnemonic = ethers.utils.entropyToMnemonic('0x' + seedHex);
                    return self.saveMnemonic(mnemonic).then(function() {
                        self.result = { address: 'Created', keyType: 'mnemonic' };
                        self.showStatus(self.$t('node.init.key_saved_next_step'), 'success');
                    });
                }).catch(function(err) {
                    self.showStatus((err.message || err), 'error');
                });
            },
            saveMnemonic: function(mnemonic) {
                return fetch(NODE_API + '/init', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mnemonic: mnemonic })
                }).then(function(r) {
                    return r.json().then(function(data) {
                        if (!r.ok) throw new Error(data.detail || this.$t('node.init.error_saving_mnemonic'));
                        return data;
                    });
                });
            },
            copyToClipboard: function(text) {
                var self = this;
                navigator.clipboard.writeText(text).then(function() {
                    self.showStatus(self.$t('node.init.copied'), 'success');
                    setTimeout(function() { self.hideStatus(); }, 2000);
                }).catch(function() { self.showStatus(self.$t('node.init.error_copy'), 'error'); });
            },
            showStatus: function(message, type) {
                this.status = { message: message, type: type || 'info', visible: true };
            },
            hideStatus: function() {
                this.status.visible = false;
            },
            closeModal: function() {
                if (this.currentStep === 3) {
                    this.showStatus(this.$t('node.init.finish_endpoint_setup'), 'error');
                    return;
                }
                if (this.currentStep === 2) {
                    this.showStatus(this.$t('node.init.finish_root_setup'), 'error');
                    return;
                }
                if (this.currentStep === 1 && !this.result) {
                    this.showStatus(this.$t('node.init.init_node_required'), 'error');
                    return;
                }
                this.showStatus(this.$t('node.init.finish_all_steps'), 'error');
            },
            closeModalComplete: function() {
                this.show = false;
                location.reload();
            }
        },
        template: [
            '<modal :show="show" :title="stepTitle" size="large" @close="closeModal">',
            '  <div v-if="status.visible" :class="\'rounded-lg p-3 mb-4 text-sm \' + (status.type === \'error\' ? \'bg-red-50 text-red-800\' : status.type === \'success\' ? \'bg-emerald-50 text-emerald-800\' : \'bg-blue-50 text-blue-800\')">[[ status.message ]]</div>',
            '  <div v-if="currentStep === 1">',
            '    <p class="text-zinc-600 text-sm mb-4">[[ $t(\'node.init.key_for_node\') ]]</p>',
            '    <div class="flex gap-2 mb-4">',
            '      <button type="button" :class="\'px-4 py-2 rounded-lg text-sm font-medium \' + (currentMethod === \'pem\' ? \'bg-blue-600 text-white\' : \'bg-zinc-100 text-zinc-700\')" @click="switchMethod(\'pem\')">[[ $t(\'node.init.method_pem\') ]]</button>',
            '      <button type="button" :class="\'px-4 py-2 rounded-lg text-sm font-medium \' + (currentMethod === \'mouse\' ? \'bg-blue-600 text-white\' : \'bg-zinc-100 text-zinc-700\')" @click="switchMethod(\'mouse\')">[[ $t(\'node.init.method_generate\') ]]</button>',
            '    </div>',
            '    <div v-if="currentMethod === \'pem\'" class="space-y-3">',
            '      <div class="text-xs text-zinc-500">[[ $t(\'node.init.pem_hint\') ]]</div>',
            '      <input type="file" ref="pemFileInput" @change="handlePemFileSelect" accept=".pem,.key" class="block w-full text-sm text-zinc-700 border border-zinc-300 rounded-lg p-2" />',
            '      <input v-if="pemFile" type="password" v-model="pemPassword" :placeholder="$t(\'node.init.pem_password_placeholder\')" autocomplete="off" class="block w-full border border-zinc-300 rounded-lg p-2 text-sm" />',
            '      <p v-if="pemFile" class="mt-1 text-xs text-zinc-500">[[ $t(\'node.init.pem_password_hint\') ]]</p>',
            '      <button type="button" :disabled="!pemContent" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="generateFromPem">[[ $t(\'node.init.load_pem_btn\') ]]</button>',
            '    </div>',
            '    <div v-if="currentMethod === \'mouse\'" class="space-y-3">',
            '      <div class="text-xs text-zinc-500">[[ entropyProgressText ]]</div>',
            '      <div class="w-full h-40 bg-zinc-100 rounded-lg" style="touch-action: none;">',
            '        <canvas ref="entropyCanvas" @mousedown="handleMouseDown" @mouseup="handleMouseUp" @mouseleave="handleMouseUp" @mousemove="handleMouseMove" class="w-full h-full rounded-lg" style="height: 160px;"></canvas>',
            '      </div>',
            '      <button type="button" ref="generateButton" :disabled="!canGenerateFromMouse" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="generateFromMouseEntropy">[[ $t(\'node.init.create_from_entropy_btn\') ]]</button>',
            '    </div>',
            '    <div v-if="result" ref="resultCard" class="mt-4 p-4 bg-zinc-50 rounded-xl border border-zinc-200">',
            '      <div class="font-medium text-emerald-700 mb-2">[[ $t(\'node.init.key_created\') ]]</div>',
            '      <div v-if="result.address && result.keyType !== \'existing\'" class="text-sm text-zinc-600 mb-1">[[ result.address ]]</div>',
            '      <button type="button" class="mt-2 px-3 py-1 bg-zinc-200 rounded text-xs" @click="copyToClipboard(result.address)">[[ $t(\'node.init.copy\') ]]</button>',
            '      <button type="button" class="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium" @click="proceedToStep2">[[ $t(\'node.init.next_root_creds\') ]]</button>',
            '    </div>',
            '  </div>',
            '  <div v-if="currentStep === 2">',
            '    <p class="text-zinc-600 text-sm mb-4">[[ $t(\'node.init.root_access\') ]]</p>',
            '    <div class="flex gap-2 mb-4">',
            '      <button type="button" :class="\'px-4 py-2 rounded-lg text-sm font-medium \' + (rootCredentialMethod === \'password\' ? \'bg-blue-600 text-white\' : \'bg-zinc-100 text-zinc-700\')" @click="switchRootCredentialMethod(\'password\')">[[ $t(\'node.init.login_password\') ]]</button>',
            '      <button type="button" :class="\'px-4 py-2 rounded-lg text-sm font-medium \' + (rootCredentialMethod === \'tron\' ? \'bg-blue-600 text-white\' : \'bg-zinc-100 text-zinc-700\')" @click="switchRootCredentialMethod(\'tron\')">[[ $t(\'node.init.tron\') ]]</button>',
            '    </div>',
            '    <div v-if="rootCredentialMethod === \'password\'" class="space-y-3">',
            '      <input type="text" v-model="rootUsername" :placeholder="$t(\'node.init.login_placeholder\')" class="block w-full border border-zinc-300 rounded-lg p-2 text-sm" />',
            '      <input type="password" v-model="rootPassword" :placeholder="$t(\'node.init.password_placeholder\')" class="block w-full border border-zinc-300 rounded-lg p-2 text-sm" />',
            '      <input type="password" v-model="rootPasswordConfirm" :placeholder="$t(\'node.init.password_confirm_placeholder\')" class="block w-full border border-zinc-300 rounded-lg p-2 text-sm" />',
            '      <button type="button" :disabled="!rootUsername || !rootPassword || !rootPasswordConfirm || savingCredentials" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="saveRootCredentials">[[ savingCredentials ? $t(\'node.init.saving\') : $t(\'node.init.save\') ]]</button>',
            '    </div>',
            '    <div v-if="rootCredentialMethod === \'tron\'" class="space-y-3">',
            '      <div v-if="!rootTronAuthenticated" class="p-4 bg-zinc-50 rounded-lg">',
            '        <p class="text-sm text-zinc-600 mb-2">[[ $t(\'node.init.tron_hint\') ]]</p>',
            '        <button type="button" :disabled="tronConnecting" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="connectTronWallet">[[ tronConnecting ? $t(\'node.init.connecting\') : $t(\'node.init.connect_tron\') ]]</button>',
            '      </div>',
            '      <div v-if="rootTronAuthenticated" class="p-4 bg-zinc-50 rounded-lg">',
            '        <p class="text-sm text-emerald-700 mb-2">[[ connectedLabel ]]</p>',
            '        <button type="button" :disabled="savingCredentials" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="saveRootCredentials">[[ savingCredentials ? $t(\'node.init.saving\') : $t(\'node.init.save_tron_root\') ]]</button>',
            '      </div>',
            '    </div>',
            '    <button type="button" class="mt-4 px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-sm" @click="backToStep1">[[ $t(\'node.init.back_step_1\') ]]</button>',
            '  </div>',
            '  <div v-if="currentStep === 3">',
            '    <p class="text-zinc-600 text-sm mb-4">[[ $t(\'node.init.endpoint_description\') ]]</p>',
            '    <input type="text" v-model="serviceEndpoint" placeholder="https://..." class="block w-full border border-zinc-300 rounded-lg p-2 text-sm mb-2" @input="endpointVerified = false; endpointTestResult = null" />',
            '    <button type="button" :disabled="!serviceEndpoint || testingEndpoint" class="mb-3 px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-sm disabled:opacity-50" @click="testServiceEndpoint">[[ testingEndpoint ? $t(\'node.init.testing\') : $t(\'node.init.test_availability\') ]]</button>',
            '    <div v-if="endpointTestResult" class="p-3 rounded-lg mb-3" :class="endpointVerified ? \'bg-emerald-50 text-emerald-800\' : \'bg-red-50 text-red-800\'">[[ endpointTestResult.message ]]</div>',
            '    <button type="button" :disabled="!serviceEndpoint || !endpointVerified || savingEndpoint" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50" @click="saveServiceEndpoint">[[ savingEndpoint ? $t(\'node.init.saving\') : $t(\'node.init.save_and_finish\') ]]</button>',
            '    <button type="button" class="mt-4 ml-2 px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-sm" @click="backToStep2">[[ $t(\'node.init.back_step_2\') ]]</button>',
            '  </div>',
            '  <template #footer>',
            '    <button type="button" class="px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-sm" @click="closeModal" :disabled="currentStep === 3 || (currentStep === 2 && !result)">[[ footerButtonText ]]</button>',
            '  </template>',
            '</modal>'
        ].join('')
    });

    document.addEventListener('DOMContentLoaded', function() {
        var container = document.getElementById('node-init-modal-container');
        if (container && typeof Vue !== 'undefined') {
            new Vue({ el: '#node-init-modal-container', template: '<node-init-modal></node-init-modal>' });
        }
    });
})();
