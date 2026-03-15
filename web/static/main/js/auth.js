/**
 * Глобальная авторизация Main: get_current_user, logout.
 * Токен хранится в localStorage под ключом main_auth_token (сохранять при успехе tron-login).
 * Подключать после vue.min.js. Функции доступны как window.get_current_user / window.logout и this.get_current_user / this.logout в компонентах.
 */
(function() {
    var AUTH_ME_TRON = '/v1/auth/tron/me';
    var AUTH_ME_WEB3 = '/v1/auth/me';
    var TOKEN_KEY = 'main_auth_token';

    function getToken() {
        try {
            return localStorage.getItem(TOKEN_KEY) || '';
        } catch (e) {
            return '';
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
        } catch (e) {}
    }

    /**
     * Возвращает Promise<{ did, wallet_address, space } | null>.
     * Сначала пробует TRON (/v1/auth/tron/me), при 401 — Web3 (/v1/auth/me).
     */
    function get_current_user() {
        var token = getToken();
        if (!token || !token.trim()) {
            return Promise.resolve(null);
        }
        var headers = { 'Authorization': 'Bearer ' + token.trim() };

        function tryTron() {
            return fetch(AUTH_ME_TRON, { method: 'GET', headers: headers, credentials: 'same-origin' })
                .then(function(r) {
                    if (r.status === 200) return r.json();
                    if (r.status === 401) { clearToken(); return null; }
                    return null;
                })
                .catch(function() { return null; });
        }

        function tryWeb3() {
            return fetch(AUTH_ME_WEB3, { method: 'GET', headers: headers, credentials: 'same-origin' })
                .then(function(r) {
                    if (r.status === 200) return r.json();
                    if (r.status === 401) { clearToken(); return null; }
                    return null;
                })
                .catch(function() { return null; });
        }

        return tryTron().then(function(user) {
            if (user && user.did) return user;
            return tryWeb3();
        });
    }

    /**
     * Выход: удаляет токен из localStorage. Редирект не выполняет — вызывающий код может перенаправить на /.
     */
    function logout() {
        clearToken();
    }

    window.get_current_user = get_current_user;
    window.logout = logout;
    window.main_auth_token_key = TOKEN_KEY;
    if (typeof Vue !== 'undefined') {
        Vue.prototype.get_current_user = get_current_user;
        Vue.prototype.logout = logout;
    }
})();
