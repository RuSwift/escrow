/**
 * Vue 2 компонент: API документация (main), вёрстка как в _temp
 */
Vue.component('api', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            endpoints: [
                { method: 'GET', path: '/api/escrows', descKey: 'main.api.ep_list' },
                { method: 'POST', path: '/api/escrows', descKey: 'main.api.ep_create' },
                { method: 'GET', path: '/api/escrows/:id', descKey: 'main.api.ep_get' },
                { method: 'PATCH', path: '/api/escrows/:id/status', descKey: 'main.api.ep_update' }
            ],
            codeSnippet: '// Create a new escrow via TrustLayer API\nconst response = await fetch(\'https://api.trustlayer.com/v1/escrows\', {\n  method: \'POST\',\n  headers: {\n    \'Authorization\': \'Bearer YOUR_API_KEY\',\n    \'Content-Type\': \'application/json\'\n  },\n  body: JSON.stringify({\n    title: \'Domain Purchase: crypto-vault.com\',\n    amount: 2.5,\n    currency: \'BTC\',\n    buyer_id: \'0x71C...8976F\',\n    seller_id: \'0x42A...1122C\'\n  })\n});\n\nconst { escrowId } = await response.json();\nconsole.log(\'Escrow created:\', escrowId);'
        };
    },
    template: `
    <div class="max-w-5xl mx-auto px-4 py-16">
      <div class="flex flex-col md:flex-row gap-12 items-start">
        <div class="flex-1">
          <div class="inline-flex items-center gap-2 px-3 py-1 bg-main-blue/10 text-main-blue rounded-full text-xs font-bold uppercase mb-4">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            [[ $t('main.api.badge') ]]
          </div>
          <h1 class="text-4xl font-bold mb-6 tracking-tight">[[ $t('main.api.title') ]]</h1>
          <p class="text-lg text-cmc-muted mb-8 leading-relaxed">[[ $t('main.api.subtitle') ]]</p>

          <div class="space-y-6 mb-12">
            <div v-for="ep in endpoints" :key="ep.path" class="flex items-center gap-4 p-4 bg-[#f8fafd] rounded-xl border border-[#eff2f5]">
              <span :class="['px-2 py-1 rounded text-[10px] font-bold uppercase shrink-0', ep.method === 'GET' ? 'bg-main-green/10 text-main-green' : ep.method === 'POST' ? 'bg-main-blue/10 text-main-blue' : 'bg-amber-100 text-amber-700']">[[ ep.method ]]</span>
              <code class="text-xs font-mono font-bold text-[#191d23]">[[ ep.path ]]</code>
              <span class="text-xs text-cmc-muted ml-auto">[[ $t(ep.descKey) ]]</span>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="p-6 bg-white rounded-2xl border border-[#eff2f5] shadow-sm">
              <svg class="w-6 h-6 text-main-blue mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg>
              <h4 class="font-bold mb-2">[[ $t('main.api.api_keys_title') ]]</h4>
              <p class="text-xs text-cmc-muted leading-relaxed">[[ $t('main.api.api_keys_desc') ]]</p>
            </div>
            <div class="p-6 bg-white rounded-2xl border border-[#eff2f5] shadow-sm">
              <svg class="w-6 h-6 text-main-blue mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0h.5a2.5 2.5 0 002.5-2.5V3.935M12 12a2 2 0 104 0 2 2 0 00-4 0z" /></svg>
              <h4 class="font-bold mb-2">[[ $t('main.api.webhooks_title') ]]</h4>
              <p class="text-xs text-cmc-muted leading-relaxed">[[ $t('main.api.webhooks_desc') ]]</p>
            </div>
          </div>
        </div>

        <div class="w-full md:w-[450px] shrink-0">
          <div class="bg-[#1e1e1e] rounded-2xl overflow-hidden shadow-2xl border border-white/10">
            <div class="px-4 py-3 bg-[#2d2d2d] flex items-center justify-between border-b border-white/5">
              <div class="flex gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-main-red"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-main-green"></span>
              </div>
              <div class="text-[10px] font-mono text-white/40 uppercase tracking-widest">JavaScript SDK</div>
            </div>
            <div class="p-6 overflow-x-auto">
              <pre class="text-[11px] font-mono leading-relaxed text-blue-300 whitespace-pre">[[ codeSnippet ]]</pre>
            </div>
          </div>
          <div class="mt-6 p-6 bg-main-blue/5 rounded-2xl border border-main-blue/10">
            <div class="flex items-center gap-2 font-bold text-main-blue mb-2">
              <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
              [[ $t('main.api.security_title') ]]
            </div>
            <p class="text-xs text-cmc-muted leading-relaxed">[[ $t('main.api.security_desc') ]]</p>
          </div>
        </div>
      </div>
    </div>
    `
});
