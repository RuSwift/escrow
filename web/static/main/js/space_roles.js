/**
 * Vue 2 компонент: Роли спейса (main). Только для владельца спейса.
 */
Vue.component('space-roles', {
    delimiters: ['[[', ']]'],
    data: function() {
        return {};
    },
    template: `
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="rounded-lg bg-main-blue/10 border border-main-blue/20 px-4 py-3 mb-6 text-main-blue font-medium">
        [[ $t('main.space_roles.alert_manage_roles') ]]
      </div>
      <div class="cmc-card p-6 text-cmc-muted text-sm">
        <p>[[ $t('main.space_roles.placeholder') ]]</p>
      </div>
    </div>
    `
});
