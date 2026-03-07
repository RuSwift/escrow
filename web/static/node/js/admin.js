/**
 * Vue 2 компонент: Админ
 * Подключение: после vue.min.js, перед app.js
 */
Vue.component('admin', {
    delimiters: ['[[', ']]'],
    props: { isNodeInitialized: { type: Boolean, default: false } },
    data: function() {
        return {
            account: {
                username: 'root',
                createdAt: '19 февраля 2026 г. в 19:34',
                updatedAt: '21 февраля 2026 г. в 01:48',
                status: 'active'
            },
            passwordForm: {
                oldPassword: '',
                newPassword: '',
                confirmPassword: ''
            },
            tronForm: {
                label: '',
                address: ''
            },
            tronAddresses: [
                { id: 1, label: 'Main Hot Wallet', address: 'TR9unofXCt9xK475pS9YNNNNNNNNNNNN' },
                { id: 2, label: 'USDT Contract', address: 'TR7NHqJeKQyGiG9gKbnXhyUaX3Ce6653' }
            ]
        };
    },
    methods: {
        shortAddress: function(addr) {
            if (!addr || addr.length < 14) return addr;
            return addr.substring(0, 8) + '...' + addr.substring(addr.length - 6);
        },
        changePassword: function() {
            if (!this.passwordForm.newPassword || this.passwordForm.newPassword.length < 8) return;
            if (this.passwordForm.newPassword !== this.passwordForm.confirmPassword) return;
            this.passwordForm = { oldPassword: '', newPassword: '', confirmPassword: '' };
        },
        addTronAddress: function() {
            if (!this.tronForm.label.trim() || !this.tronForm.address.trim()) return;
            this.tronAddresses.push({
                id: this.tronAddresses.length + 1,
                label: this.tronForm.label.trim(),
                address: this.tronForm.address.trim()
            });
            this.tronForm = { label: '', address: '' };
        },
        removeTronAddress: function(id) {
            this.tronAddresses = this.tronAddresses.filter(function(a) { return a.id !== id; });
        }
    },
    template: `
    <div class="p-8 bg-zinc-50/50 flex-1 overflow-y-auto">
      <div class="max-w-7xl mx-auto">
        <nav class="text-[13px] text-blue-600 font-semibold mb-6">Админ</nav>
        <h2 class="text-xl font-bold text-zinc-900 mb-6 tracking-tight">Администрирование аккаунта</h2>

        <div class="space-y-6">
          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <div class="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 shrink-0">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Информация об аккаунте</span>
            </div>
            <div class="p-6 space-y-4">
              <div>
                <p class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1.5">Методы аутентификации:</p>
                <button type="button" class="px-3 py-1.5 bg-blue-100 text-blue-800 rounded-lg text-[13px] font-semibold hover:bg-blue-200">Пароль</button>
              </div>
              <div>
                <p class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1">Имя пользователя:</p>
                <p class="text-[13px] font-medium text-zinc-800">[[ account.username ]]</p>
              </div>
              <div>
                <p class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1">Создан:</p>
                <p class="text-[13px] text-zinc-600">[[ account.createdAt ]]</p>
              </div>
              <div>
                <p class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1">Обновлен:</p>
                <p class="text-[13px] text-zinc-600">[[ account.updatedAt ]]</p>
              </div>
              <div>
                <p class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1.5">Статус:</p>
                <span class="inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">Активен</span>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <div class="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center text-amber-600 shrink-0">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
              </div>
              <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Сменить пароль</span>
            </div>
            <div class="p-6 space-y-4">
              <div>
                <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Старый пароль</label>
                <input type="password" v-model="passwordForm.oldPassword" placeholder="Введите текущий пароль" class="w-full px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              </div>
              <div>
                <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Новый пароль</label>
                <input type="password" v-model="passwordForm.newPassword" placeholder="Минимум 8 символов" class="w-full px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              </div>
              <div>
                <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Подтвердите новый пароль</label>
                <input type="password" v-model="passwordForm.confirmPassword" placeholder="Повторите новый пароль" class="w-full px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400">
              </div>
              <button type="button" @click="changePassword" class="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700">Сменить пароль</button>
            </div>
          </div>

          <div class="bg-white rounded-2xl shadow-sm border border-zinc-200/60 overflow-hidden">
            <div class="p-5 border-b border-zinc-100 bg-zinc-50/30 flex items-center gap-2">
              <span class="text-[13px] font-bold text-zinc-800 uppercase tracking-tight">Управление TRON адресами</span>
            </div>
            <div class="p-6 space-y-4">
              <div class="flex flex-wrap items-end gap-3">
                <div>
                  <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">Метка</label>
                  <input type="text" v-model="tronForm.label" placeholder="Напр. Основной" class="w-48 px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                </div>
                <div class="flex-1 min-w-[200px]">
                  <label class="block text-[11px] font-bold text-zinc-600 uppercase tracking-wider mb-1.5">TRON адрес</label>
                  <input type="text" v-model="tronForm.address" placeholder="T..." class="w-full px-4 py-2.5 border border-zinc-200 rounded-xl text-[13px] font-mono placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                </div>
                <button type="button" @click="addTronAddress" class="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-[13px] font-semibold hover:bg-blue-700 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  Добавить
                </button>
              </div>
              <div class="overflow-x-auto rounded-xl border border-zinc-200">
                <table class="w-full text-left text-[13px]">
                  <thead class="bg-zinc-50 border-b border-zinc-200">
                    <tr>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Метка</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider">Адрес</th>
                      <th class="px-4 py-3 font-bold text-zinc-500 uppercase tracking-wider w-24">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in tronAddresses" :key="a.id" class="border-b border-zinc-100 hover:bg-zinc-50/80 transition-colors">
                      <td class="px-4 py-3 font-medium text-zinc-800">[[ a.label ]]</td>
                      <td class="px-4 py-3 font-mono text-zinc-600">[[ shortAddress(a.address) ]]</td>
                      <td class="px-4 py-3">
                        <button type="button" @click="removeTronAddress(a.id)" class="p-1.5 text-zinc-400 hover:text-red-600 rounded" title="Удалить">
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="rounded-xl bg-sky-50 border border-sky-100 p-4 flex items-start gap-3">
            <svg class="w-5 h-5 text-sky-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
            <p class="text-[13px] font-medium text-sky-900 leading-relaxed"><span class="font-bold">Безопасность:</span> Убедитесь, что вы находитесь в безопасном месте при изменении учетных данных. После смены пароля или TRON адреса вам потребуется повторная аутентификация.</p>
          </div>
        </div>
      </div>
    </div>
    `
});
