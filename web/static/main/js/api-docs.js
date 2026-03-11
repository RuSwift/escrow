/**
 * Vue 2 компонент: API документация (main)
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
            codeSnippet: "// Create a new escrow via API\nconst response = await fetch('/v1/escrows', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify({ title: 'Deal', amount: 1, currency: 'USDT' })\n});"
        };
    },
    template: `
    <div class="max-w-5xl mx-auto px-4 py-16">
      <div class="inline-flex items-center gap-2 px-3 py-1 bg-main-blue/10 text-main-blue rounded-full text-xs font-bold uppercase mb-4">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
        [[ $t('main.api.badge') ]]
      </div>
      <h1 class="text-4xl font-bold mb-6 tracking-tight">[[ $t('main.api.title') ]]</h1>
      <p class="text-lg text-cmc-muted mb-8 leading-relaxed">[[ $t('main.api.subtitle') ]]</p>
      <div class="space-y-6 mb-12">
        <div v-for="ep in endpoints" :key="ep.path" class="flex flex-wrap items-center gap-4 p-4 bg-[#f8fafd] rounded-xl border border-[#eff2f5]">
          <span :class="['px-2 py-1 rounded text-[10px] font-bold uppercase', ep.method === 'GET' ? 'bg-main-green/10 text-main-green' : ep.method === 'POST' ? 'bg-main-blue/10 text-main-blue' : 'bg-amber-100 text-amber-700']">[[ ep.method ]]</span>
          <code class="text-xs font-mono font-bold">[[ ep.path ]]</code>
          <span class="text-xs text-cmc-muted ml-auto">[[ $t(ep.descKey) ]]</span>
        </div>
      </div>
      <div class="bg-[#1e1e1e] rounded-2xl overflow-hidden shadow-2xl border border-white/10">
        <div class="px-4 py-3 bg-[#2d2d2d] flex items-center justify-between border-b border-white/5">
          <div class="text-[10px] font-mono text-white/40 uppercase tracking-widest">JavaScript</div>
        </div>
        <div class="p-6 overflow-x-auto">
          <pre class="text-[11px] font-mono leading-relaxed text-blue-300 whitespace-pre">[[ codeSnippet ]]</pre>
        </div>
      </div>
      <div class="mt-6 p-6 bg-main-blue/5 rounded-2xl border border-main-blue/10">
        <div class="flex items-center gap-2 font-bold text-main-blue mb-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
          [[ $t('main.api.security_title') ]]
        </div>
        <p class="text-xs text-cmc-muted leading-relaxed">[[ $t('main.api.security_desc') ]]</p>
      </div>
    </div>
    `
});
