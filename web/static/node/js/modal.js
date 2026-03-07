/**
 * Универсальный Vue 2 компонент модального окна.
 * Подключение: после vue.min.js, перед компонентами, использующими модалку.
 *
 * Использование:
 *   <modal :show="showModal" title="Заголовок" @close="showModal = false">
 *     <p>Контент модалки</p>
 *     <template slot="footer">
 *       <button @click="$emit('close')">Отмена</button>
 *       <button @click="onSubmit">Создать</button>
 *     </template>
 *   </modal>
 */
Vue.component('modal', {
    delimiters: ['[[', ']]'],
    props: {
        show: { type: Boolean, default: false },
        title: { type: String, default: '' }
    },
    template: `
    <div v-show="show" class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" :aria-label="title">
      <div class="modal-box">
        <div class="modal-header">
          <h2 class="modal-title">[[ title ]]</h2>
          <button type="button" class="modal-close" @click="$emit('close')" aria-label="Закрыть">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div class="modal-body">
          <slot></slot>
        </div>
        <div class="modal-footer" v-if="$slots.footer">
          <slot name="footer"></slot>
        </div>
      </div>
    </div>
    `
});
