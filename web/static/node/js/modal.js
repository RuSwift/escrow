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
        title: { type: String, default: '' },
        size: { type: String, default: 'default' }  // 'default' | 'large'
    },
    template: `
    <div v-show="show" class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" :aria-label="title">
      <div class="modal-box" :class="{ 'modal-box--large': size === 'large' }">
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

/**
 * Модальное диалоговое окно с подтверждением (Confirm/Cancel).
 * Использование:
 *   <modal-dialog :show="show" :title="title" :message="message"
 *     confirm-label="Удалить" cancel-label="Отмена" confirm-class="bg-red-600 hover:bg-red-700 text-white"
 *     @confirm="onConfirm" @cancel="show = false">
 *   </modal-dialog>
 */
Vue.component('modal-dialog', {
    delimiters: ['[[', ']]'],
    props: {
        show: { type: Boolean, default: false },
        title: { type: String, default: '' },
        message: { type: String, default: '' },
        confirmLabel: { type: String, default: 'OK' },
        cancelLabel: { type: String, default: 'Cancel' },
        confirmClass: { type: String, default: 'bg-blue-600 hover:bg-blue-700 text-white' }
    },
    template: `
    <modal :show="show" :title="title" @close="$emit('cancel')">
      <p class="text-zinc-700 text-[13px]">[[ message ]]</p>
      <template slot="footer">
        <button type="button" class="px-4 py-2 bg-zinc-200 text-zinc-700 rounded-lg text-sm font-medium hover:bg-zinc-300" @click="$emit('cancel')">[[ cancelLabel ]]</button>
        <button type="button" class="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50" :class="confirmClass" @click="$emit('confirm')">[[ confirmLabel ]]</button>
      </template>
    </modal>
    `
});
