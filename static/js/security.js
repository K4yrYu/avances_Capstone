(function () {
    "use strict";

    const replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    };

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => replacements[character]);
    }

    function safeUrl(value) {
        try {
            const url = new URL(String(value ?? ""), window.location.origin);
            if (!['http:', 'https:'].includes(url.protocol)) {
                return "";
            }
            return escapeHtml(url.href);
        } catch (_error) {
            return "";
        }
    }

    window.FerremasSecurity = Object.freeze({escapeHtml, safeUrl});
})();
