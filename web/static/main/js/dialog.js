/**
 * Переиспользуемые модальные диалоги (по образцу garantex).
 * API:
 *   showConfirm({ title, message, onConfirm, onCancel, danger? })
 *   showAlert({ title, message, onOk? }) — одна кнопка «OK».
 *   Оба оверлея z-[110], чтобы быть поверх внутренних модалок (напр. Ramp).
 * Подключать после vue.min.js. Использует window.__TRANSLATIONS__ для подписей кнопок.
 */
(function() {
    function t(key) {
        var tr = window.__TRANSLATIONS__;
        return (tr && tr[key] !== undefined) ? tr[key] : key;
    }

    var container = null;
    var callbacks = { onConfirm: null, onCancel: null };

    function hide() {
        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
            container = null;
        }
        callbacks = { onConfirm: null, onCancel: null };
    }

    function showConfirm(options) {
        var title = (options && options.title) || '';
        var message = (options && options.message) || '';
        var danger = !!(options && options.danger);
        callbacks.onConfirm = options && options.onConfirm;
        callbacks.onCancel = options && options.onCancel;

        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }

        var confirmBtnClass = danger
            ? 'px-4 py-2 text-[13px] font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors'
            : 'px-4 py-2 text-[13px] font-semibold text-white bg-main-blue hover:bg-main-blue/90 rounded-lg transition-colors';

        container = document.createElement('div');
        container.setAttribute('role', 'dialog');
        container.setAttribute('aria-modal', 'true');
        container.setAttribute('aria-labelledby', 'dialog-title');
        container.className = 'fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm';
        container.innerHTML =
            '<div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-[#eff2f5]">' +
            '  <h2 id="dialog-title" class="text-lg font-bold text-[#191d23] mb-2">' + (title.replace(/</g, '&lt;')) + '</h2>' +
            '  <p class="text-sm text-[#58667e] mb-6">' + (message.replace(/</g, '&lt;')) + '</p>' +
            '  <div class="flex justify-end gap-3">' +
            '    <button type="button" data-dialog-action="cancel" class="px-4 py-2 text-[13px] font-medium text-[#58667e] hover:bg-[#f8fafd] rounded-lg transition-colors">' + (t('main.space.switch_no').replace(/</g, '&lt;')) + '</button>' +
            '    <button type="button" data-dialog-action="confirm" class="' + confirmBtnClass + '">' + (t('main.space.switch_yes').replace(/</g, '&lt;')) + '</button>' +
            '  </div>' +
            '</div>';

        container.addEventListener('click', function(e) {
            if (e.target === container) {
                if (typeof callbacks.onCancel === 'function') callbacks.onCancel();
                hide();
                return;
            }
            var btn = e.target.closest('[data-dialog-action]');
            if (!btn) return;
            var action = btn.getAttribute('data-dialog-action');
            if (action === 'confirm') {
                if (typeof callbacks.onConfirm === 'function') callbacks.onConfirm();
            } else {
                if (typeof callbacks.onCancel === 'function') callbacks.onCancel();
            }
            hide();
        });

        document.body.appendChild(container);
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Информация или ошибка: один первичный «OK», без второй кнопки.
     */
    function showAlert(options) {
        var title = (options && options.title) ? String(options.title) : '';
        var message = (options && options.message) ? String(options.message) : '';
        var onOk = options && options.onOk;
        var okLabel = t('main.dialog.ok');

        var el = document.createElement('div');
        el.setAttribute('role', 'alertdialog');
        el.setAttribute('aria-modal', 'true');
        el.setAttribute('aria-labelledby', 'dialog-alert-title');
        el.className = 'fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm';
        el.innerHTML =
            '<div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-[#eff2f5]">' +
            '  <h2 id="dialog-alert-title" class="text-lg font-bold text-[#191d23] mb-2">' + escHtml(title) + '</h2>' +
            '  <p class="text-sm text-[#58667e] mb-6 whitespace-pre-wrap break-words">' + escHtml(message) + '</p>' +
            '  <div class="flex justify-end">' +
            '    <button type="button" data-dialog-alert-ok class="px-4 py-2 text-[13px] font-semibold text-white bg-main-blue hover:bg-main-blue/90 rounded-lg transition-colors">' + escHtml(okLabel) + '</button>' +
            '  </div>' +
            '</div>';

        function hide() {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        }

        el.addEventListener('click', function(e) {
            if (e.target === el) {
                if (typeof onOk === 'function') onOk();
                hide();
                return;
            }
            if (e.target.closest('[data-dialog-alert-ok]')) {
                if (typeof onOk === 'function') onOk();
                hide();
            }
        });

        document.body.appendChild(el);
    }

    /**
     * Модальное предупреждение после приглашения: ранее был другой адрес в TronLink.
     * options: { previous, masked, onContinue, onRelogin } — previous (полный base58) или masked для {previous}.
     */
    function showInviteWalletReminderModal(options) {
        var previous = (options && options.previous) ? String(options.previous) : '';
        if (!previous && options && options.masked) previous = String(options.masked);
        var onContinue = options && options.onContinue;
        var onRelogin = options && options.onRelogin;

        function t(key) {
            var tr = window.__TRANSLATIONS__;
            return (tr && tr[key] !== undefined) ? tr[key] : key;
        }

        function substitute(str) {
            return String(str || '').replace(/\{previous\}/g, previous);
        }

        function esc(s) {
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        var title = esc(substitute(t('main.invite.wallet_reminder_modal_title')));
        var body = esc(substitute(t('main.invite.wallet_reminder_modal_body')));
        var btnContinue = esc(t('main.invite.wallet_reminder_continue'));
        var btnRelogin = esc(substitute(t('main.invite.wallet_reminder_relogin')));

        var container = document.createElement('div');
        container.setAttribute('role', 'dialog');
        container.setAttribute('aria-modal', 'true');
        container.setAttribute('aria-labelledby', 'invite-reminder-dialog-title');
        container.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm';
        container.innerHTML =
            '<div class="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 border border-amber-200 ring-1 ring-amber-100">' +
            '  <div class="flex gap-3 mb-4">' +
            '    <div class="shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-lg" aria-hidden="true">!</div>' +
            '    <div class="min-w-0">' +
            '      <h2 id="invite-reminder-dialog-title" class="text-lg font-bold text-[#191d23] mb-2">' + title + '</h2>' +
            '      <p class="text-sm text-[#58667e] leading-relaxed break-words">' + body + '</p>' +
            '    </div>' +
            '  </div>' +
            '  <div class="flex flex-col sm:flex-row sm:justify-end sm:flex-wrap gap-3 pt-2">' +
            '    <button type="button" data-invite-reminder-action="continue" class="w-full sm:w-auto px-4 py-2 text-[13px] font-medium text-[#58667e] hover:bg-[#f8fafd] rounded-lg transition-colors border border-[#eff2f5]">' + btnContinue + '</button>' +
            '    <button type="button" data-invite-reminder-action="relogin" class="w-full sm:w-auto px-4 py-2 text-[13px] font-semibold text-white bg-main-blue hover:bg-main-blue/90 rounded-lg transition-colors">' + btnRelogin + '</button>' +
            '  </div>' +
            '</div>';

        function hide() {
            if (container && container.parentNode) {
                container.parentNode.removeChild(container);
            }
        }

        container.addEventListener('click', function(e) {
            if (e.target === container) {
                if (typeof onContinue === 'function') onContinue();
                hide();
                return;
            }
            var btn = e.target.closest('[data-invite-reminder-action]');
            if (!btn) return;
            var action = btn.getAttribute('data-invite-reminder-action');
            if (action === 'relogin') {
                if (typeof onRelogin === 'function') onRelogin();
            } else {
                if (typeof onContinue === 'function') onContinue();
            }
            hide();
        });

        document.body.appendChild(container);
    }

    window.showConfirm = showConfirm;
    window.showAlert = showAlert;
    window.showInviteWalletReminderModal = showInviteWalletReminderModal;
})();
