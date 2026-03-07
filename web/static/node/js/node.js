/**
 * Vue 2 компонент: Нода (профиль ноды)
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('node', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            pemKey: '-----BEGIN PUBLIC KEY-----\nMFYwEAYHKoZIzj0CAQYFK4EEAAoDQgAEEBitR7R5j0EKCXZ/KimzwZBkzTiPZtyx\npnlqxVFJDsvfIQM7B6KF0mU5nqXetkbrsr9jbY38EvHUa+f40QLzIA==\n-----END PUBLIC KEY-----',
            did: 'did:peer:1:zd7ad768b178f7116',
            serviceEndpoint: 'https://gild-admin.ruswift.ru/endpoint'
        };
    },
    methods: {
        copyToClipboard: function(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text);
            }
        },
        checkEndpoint: function() {
            window.open(this.serviceEndpoint, '_blank');
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Нода</nav>
        <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
          <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
            <svg class="w-[18px] h-[18px] text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
            <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Профиль ноды</span>
          </div>
          <div class="p-8">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 shrink-0">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg>
              </div>
              <h2 class="text-xl font-bold text-zinc-900 tracking-tight">Публичная информация о ключе</h2>
            </div>
            <div class="rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3 mb-8">
              <svg class="w-5 h-5 text-sky-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <p class="text-[13px] font-medium text-sky-900 leading-relaxed"><span class="font-bold">Информация:</span> Публичный ключ, PEM, DID и DID Document можно безопасно делиться с другими. Они используются для проверки подписей, шифрования сообщений и идентификации в P2P сети.</p>
            </div>

            <div class="mb-8">
              <div class="flex items-center gap-2 mb-3">
                <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-7 0V6a2 2 0 012-2h2a2 2 0 012 2v4h-4z" /></svg>
                <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Публичный ключ (PEM):</h3>
              </div>
              <div class="relative group">
                <textarea readonly rows="5" class="w-full px-4 py-4 bg-zinc-50 border border-zinc-200 rounded-xl text-[12px] font-mono text-zinc-600 focus:outline-none resize-none leading-relaxed" :value="pemKey"></textarea>
                <button type="button" @click="copyToClipboard(pemKey)" class="absolute right-3 top-3 p-2 bg-white border border-zinc-200 rounded-lg text-zinc-400 hover:text-blue-600 hover:border-blue-200 transition-all shadow-sm opacity-0 group-hover:opacity-100" title="Копировать">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                </button>
              </div>
              <p class="mt-2 text-[11px] text-zinc-400 font-medium italic">Этот PEM ключ можно безопасно делиться — он содержит только публичную информацию</p>
            </div>

            <div class="mb-12">
              <div class="flex items-center gap-2 mb-3">
                <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-7 0V6a2 2 0 012-2h2a2 2 0 012 2v4h-4z" /></svg>
                <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">DID (Decentralized Identifier):</h3>
              </div>
              <div class="relative group">
                <input readonly type="text" :value="did" class="w-full px-4 py-3 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] font-mono text-zinc-600 focus:outline-none">
                <button type="button" @click="copyToClipboard(did)" class="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-white border border-zinc-200 rounded-lg text-zinc-400 hover:text-blue-600 hover:border-blue-200 transition-all shadow-sm opacity-0 group-hover:opacity-100" title="Копировать">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                </button>
              </div>
              <p class="mt-2 text-[11px] text-zinc-400 font-medium">Децентрализованный идентификатор для P2P сети</p>
            </div>

            <div class="h-px bg-zinc-100 mb-12"></div>

            <div class="mb-8">
              <div class="flex items-center gap-3 mb-6">
                <div class="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 shrink-0">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                </div>
                <h2 class="text-xl font-bold text-zinc-900 tracking-tight">Service Endpoint</h2>
              </div>
              <div class="mb-4">
                <div class="flex items-center gap-2 mb-3">
                  <svg class="w-4 h-4 text-zinc-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  <h3 class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Service Endpoint URL:</h3>
                </div>
                <div class="flex gap-3 flex-wrap">
                  <input readonly type="text" :value="serviceEndpoint" class="flex-1 min-w-0 px-4 py-3 bg-zinc-50 border border-zinc-200 rounded-xl text-[13px] font-mono text-zinc-600 focus:outline-none">
                  <button type="button" class="px-4 py-2 bg-white border border-blue-600 text-blue-600 rounded-lg text-[13px] font-semibold flex items-center gap-2 hover:bg-blue-50 transition-all shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                    Редактировать
                  </button>
                </div>
                <p class="mt-2 text-[11px] text-zinc-400 font-medium">HTTP адрес для приема DIDComm сообщений</p>
              </div>
              <button type="button" @click="checkEndpoint" class="px-4 py-2.5 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-[13px] font-bold flex items-center gap-2 transition-all shadow-md shadow-sky-400/20">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                Проверить GET запросом
              </button>
            </div>
          </div>
        </div>
      </div>
      <footer class="mt-auto pt-12 text-center text-[11px] text-zinc-400 font-medium tracking-wide uppercase">&copy; Escrow Node &bull; v0.1.0</footer>
    </div>
    `
});
