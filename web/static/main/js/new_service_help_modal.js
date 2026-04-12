/**
 * Справка по созданию платежного направления (onRamp/offRamp, кошельки, формы).
 * Подключать после vue.min.js / sidebar.js, до my_business.js.
 */
(function() {
    if (typeof Vue === 'undefined') return;
    Vue.component('new-service-help-modal', {
        delimiters: ['[[', ']]'],
        props: {
            show: { type: Boolean, default: false }
        },
        methods: {
            close: function() {
                this.$emit('close');
            }
        },
        template: [
            '<div v-if="show" class="fixed inset-0 z-[115] overflow-y-auto overscroll-contain">',
            '  <div class="min-h-[100dvh] min-h-[100svh] flex items-end justify-center sm:items-center p-0 sm:p-4">',
            '    <div class="absolute inset-0 bg-black/60" @click="close"></div>',
            '    <div class="relative z-10 bg-white w-full max-w-full sm:max-w-lg rounded-t-3xl sm:rounded-2xl shadow-2xl grid grid-rows-[auto_minmax(0,1fr)_auto] max-h-[85dvh] sm:max-h-[90vh] overflow-hidden my-0 sm:my-4" role="dialog" aria-modal="true" aria-labelledby="new-service-help-h">',
            '      <div class="p-5 sm:p-6 border-b border-[#eff2f5] flex items-center justify-between shrink-0">',
            '        <h3 id="new-service-help-h" class="text-lg font-bold text-[#191d23] pr-2">[[ $t(\'main.my_business.new_service_help_title\') ]]</h3>',
            '        <button type="button" @click="close" class="p-2 hover:bg-gray-100 rounded-full shrink-0" :aria-label="$t(\'main.my_business.multisig_wizard_close\')">',
            '          <svg class="w-6 h-6 text-[#58667e] rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>',
            '        </button>',
            '      </div>',
            '      <div class="min-h-0 overflow-y-auto overscroll-contain touch-pan-y p-5 sm:p-6 space-y-4 text-sm text-[#58667e] leading-relaxed">',
            '        <p class="text-[#191d23] font-medium">[[ $t(\'main.my_business.new_service_help_intro\') ]]</p>',
            '        <ul class="list-disc pl-5 space-y-3">',
            '          <li class="whitespace-pre-line">[[ $t(\'main.my_business.new_service_help_on_off\') ]]</li>',
            '          <li>[[ $t(\'main.my_business.new_service_help_corporate\') ]]</li>',
            '          <li>[[ $t(\'main.my_business.new_service_help_forms\') ]]</li>',
            '        </ul>',
            '      </div>',
            '      <div class="p-4 sm:p-5 border-t border-[#eff2f5] bg-gray-50 shrink-0 pb-[max(1rem,env(safe-area-inset-bottom))]">',
            '        <button type="button" @click="close" class="w-full py-3 bg-[#3861fb] text-white rounded-xl text-sm font-bold hover:opacity-90 transition-opacity">[[ $t(\'main.my_business.new_service_help_close\') ]]</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('')
    });
})();
