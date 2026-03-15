/**
 * Переиспользуемый диалог подтверждения (по образцу garantex).
 * API: showConfirm({ title, message, onConfirm, onCancel }).
 * Подключать после vue.min.js. Использует window.__TRANSLATIONS__ для кнопок.
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
        callbacks.onConfirm = options && options.onConfirm;
        callbacks.onCancel = options && options.onCancel;

        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }

        container = document.createElement('div');
        container.setAttribute('role', 'dialog');
        container.setAttribute('aria-modal', 'true');
        container.setAttribute('aria-labelledby', 'dialog-title');
        container.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm';
        container.innerHTML =
            '<div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-[#eff2f5]">' +
            '  <h2 id="dialog-title" class="text-lg font-bold text-[#191d23] mb-2">' + (title.replace(/</g, '&lt;')) + '</h2>' +
            '  <p class="text-sm text-[#58667e] mb-6">' + (message.replace(/</g, '&lt;')) + '</p>' +
            '  <div class="flex justify-end gap-3">' +
            '    <button type="button" data-dialog-action="cancel" class="px-4 py-2 text-[13px] font-medium text-[#58667e] hover:bg-[#f8fafd] rounded-lg transition-colors">' + (t('main.space.switch_no').replace(/</g, '&lt;')) + '</button>' +
            '    <button type="button" data-dialog-action="confirm" class="px-4 py-2 text-[13px] font-semibold text-white bg-main-blue hover:bg-main-blue/90 rounded-lg transition-colors">' + (t('main.space.switch_yes').replace(/</g, '&lt;')) + '</button>' +
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

    window.showConfirm = showConfirm;
})();
