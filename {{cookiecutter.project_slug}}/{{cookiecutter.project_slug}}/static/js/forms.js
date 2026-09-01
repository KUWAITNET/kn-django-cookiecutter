/* ---------------------------------------------------------------------------
 * Progressive enhancement for forms.
 *
 * Two jobs, both of which the page works without:
 *
 *   1. Clear a field's validation error as soon as the visitor edits the field,
 *      so the message stops contradicting what they just typed.
 *   2. Keep the CSRF token in every form current, so a page left open in a tab
 *      does not 403 on submit.
 *
 * Both are wired with DELEGATED listeners on `document`, not with one listener
 * per form or per field. That is deliberate: a formset row cloned from a
 * <template>, a field revealed by a conditional block, or a form injected by a
 * modal is covered with no extra wiring. The reference project bound per form at
 * DOMContentLoaded, and shipped the CSRF helper but called it from exactly one
 * page - so the stale-token 403 stayed live on every other form in the site.
 *
 * No dependencies, no build step, no inline script (there is no 'unsafe-inline'
 * in the Content-Security-Policy).
 * ------------------------------------------------------------------------- */

(function () {
    "use strict";

    var CSRF_COOKIE_NAME = "csrftoken";
    var CSRF_FIELD_NAME = "csrfmiddlewaretoken";
    var ERROR_SELECTOR = ".form-error";
    var GROUP_SELECTOR = ".form-group";
    var CONTROL_SELECTOR = "input, select, textarea";

    /* --- CSRF ------------------------------------------------------------ */

    function readCookie(name) {
        var prefix = name + "=";
        var parts = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < parts.length; i += 1) {
            var part = parts[i].trim();
            if (part.indexOf(prefix) === 0) {
                return decodeURIComponent(part.slice(prefix.length));
            }
        }
        return null;
    }

    function csrfToken() {
        return readCookie(CSRF_COOKIE_NAME);
    }

    /* Rewrite every hidden CSRF input from the current cookie.
     *
     * Django rotates the CSRF token on login and on logout. A page rendered
     * before that rotation - a long-lived tab, a page restored from the back /
     * forward cache, a form opened in a second tab while the first one logged in
     * - still carries the old value, and submitting it is a 403 the visitor
     * cannot diagnose and usually reads as "the site is broken".
     *
     * When the cookie is absent (CSRF_USE_SESSIONS, or a first visit with no
     * cookie yet) this is a no-op: overwriting a server-rendered token with an
     * empty string would create the failure it is meant to prevent. */
    function refreshCsrfTokens(root) {
        var token = csrfToken();
        if (!token) {
            return;
        }
        var scope = root || document;
        var inputs = scope.querySelectorAll('input[name="' + CSRF_FIELD_NAME + '"]');
        for (var i = 0; i < inputs.length; i += 1) {
            if (inputs[i].value !== token) {
                inputs[i].value = token;
            }
        }
    }

    /* --- Field errors ---------------------------------------------------- */

    function clearFieldErrors(field) {
        var group = field.closest(GROUP_SELECTOR) || field.parentElement;
        if (!group) {
            return;
        }
        var messages = group.querySelectorAll(ERROR_SELECTOR);
        for (var i = 0; i < messages.length; i += 1) {
            messages[i].remove();
        }
        group.classList.remove("has-error");
        field.removeAttribute("aria-invalid");
        /* The description is gone, so the reference to it has to go too, or a
         * screen reader announces an element that is no longer in the document. */
        var describedBy = field.getAttribute("aria-describedby");
        if (describedBy && messages.length) {
            var remaining = describedBy
                .split(/\s+/)
                .filter(function (id) {
                    return id && document.getElementById(id);
                })
                .join(" ");
            if (remaining) {
                field.setAttribute("aria-describedby", remaining);
            } else {
                field.removeAttribute("aria-describedby");
            }
        }
    }

    function handleEdit(event) {
        var target = event.target;
        if (target && target.matches && target.matches(CONTROL_SELECTOR)) {
            clearFieldErrors(target);
        }
    }

    /* --- Wiring ---------------------------------------------------------- */

    /* `input` and `change` both bubble, so one listener on the document covers
     * every field on the page, including ones added after this ran. */
    document.addEventListener("input", handleEdit, true);
    document.addEventListener("change", handleEdit, true);

    /* Capture phase: the token is refreshed before any other submit handler runs,
     * including one that serialises the form for an AJAX request. */
    document.addEventListener(
        "submit",
        function (event) {
            if (event.target && event.target.tagName === "FORM") {
                refreshCsrfTokens(event.target);
            }
        },
        true
    );

    /* A tab restored from the back/forward cache keeps its stale DOM, and
     * `pageshow` is the only event that fires for it. `visibilitychange` covers
     * the tab that was simply left open while the visitor logged in elsewhere. */
    window.addEventListener("pageshow", function () {
        refreshCsrfTokens();
    });

    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            refreshCsrfTokens();
        }
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            refreshCsrfTokens();
        });
    } else {
        refreshCsrfTokens();
    }

    /* Exposed so fetch/XHR callers use the same source of truth rather than
     * scraping the DOM for a token that may already be stale:
     *
     *   fetch(url, { method: "POST", headers: { "X-CSRFToken": window.KNForms.csrfToken() } })
     */
    window.KNForms = {
        csrfToken: csrfToken,
        refreshCsrfTokens: refreshCsrfTokens,
        clearFieldErrors: clearFieldErrors
    };
})();
