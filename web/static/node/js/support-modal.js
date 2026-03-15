/**
 * Модалка «Поддержка» для node: монтируется вне сайдбара (#support-modal-mount),
 * открывается по событию 'open-support-modal'. Подключать после modal.js и sidebar.js.
 */
(function() {
    var mountEl = document.getElementById('support-modal-mount');
    if (!mountEl || typeof Vue === 'undefined') return;

    var t = window.__TRANSLATIONS__ || {};
    var supportTitle = t['node.sidebar.support'] !== undefined ? t['node.sidebar.support'] : 'Поддержка';
    var description = t['node.support.description'] !== undefined ? t['node.support.description'] : '';
    var telegramText = t['node.support.telegram_text'] !== undefined ? t['node.support.telegram_text'] : '';

    new Vue({
        el: '#support-modal-mount',
        delimiters: ['[[', ']]'],
        data: {
            show: false,
            supportTitle: supportTitle,
            description: description,
            telegramText: telegramText
        },
        mounted: function() {
            var self = this;
            window.addEventListener('open-support-modal', function() {
                self.show = true;
            });
        },
        template: [
            '<modal :show="show" :title="supportTitle" @close="show = false">',
            '  <p class="text-[13px] text-zinc-700 mb-3">[[ description ]]</p>',
            '  <p class="text-[13px] text-zinc-700">[[ telegramText ]] <a href="https://t.me/ruswift_support" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline font-medium">@ruswift_support</a></p>',
            '</modal>'
        ].join('')
    });
})();
