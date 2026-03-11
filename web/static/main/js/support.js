/**
 * Vue 2 компонент: Поддержка (main)
 */
Vue.component('support', {
    delimiters: ['[[', ']]'],
    template: `
    <div class="max-w-4xl mx-auto px-4 py-16">
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold mb-4 tracking-tight">[[ $t('main.sidebar.support') ]]</h1>
        <p class="text-lg text-cmc-muted max-w-2xl mx-auto">[[ $t('main.support.description') ]]</p>
      </div>
      <div class="cmc-card p-8 text-center">
        <p class="text-cmc-muted mb-4">[[ $t('main.support.telegram_text') ]]</p>
        <a href="https://t.me/ruswift_support" target="_blank" rel="noopener noreferrer" class="text-main-blue hover:underline font-medium">@ruswift_support</a>
      </div>
    </div>
    `
});
