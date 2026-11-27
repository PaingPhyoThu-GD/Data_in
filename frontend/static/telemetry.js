/**
 * Telemetry.js - Ultra-lightweight (~1.1 KB) Cookieless Traffic & Event Beacon.
 * Automatically tracks pageviews, dwell time, and SPA route changes.
 * GDPR & ePrivacy Compliant: Zero cookies, zero localStorage, zero fingerprinting.
 */
(function () {
    'use strict';

    // Respect Do Not Track / Global Privacy Control
    if (navigator.doNotTrack === '1' || window.doNotTrack === '1' || navigator.globalPrivacyControl === true) {
        return;
    }

    const currentScript = document.currentScript;
    const siteId = (currentScript && currentScript.getAttribute('data-site')) || 'default';
    const endpoint = (currentScript && currentScript.getAttribute('data-endpoint')) || '/api/telemetry/collect';

    let lastPath = window.location.pathname;
    let pageStartTime = Date.now();

    function sendEvent(path, dwellSeconds) {
        const payload = JSON.stringify({
            site_id: siteId,
            p: path || window.location.pathname,
            r: document.referrer || '',
            d: dwellSeconds || 0,
            ts: Date.now()
        });

        if (navigator.sendBeacon) {
            navigator.sendBeacon(endpoint, payload);
        } else {
            fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true
            }).catch(function () {});
        }
    }

    // Initial pageview
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        sendEvent(lastPath, 0);
    } else {
        window.addEventListener('DOMContentLoaded', function () {
            sendEvent(lastPath, 0);
        });
    }

    // Track dwell duration when switching tabs or unloading
    function flushDwell() {
        if (!pageStartTime) return;
        const dwellSeconds = Math.round((Date.now() - pageStartTime) / 1000);
        if (dwellSeconds > 0) {
            sendEvent(lastPath, dwellSeconds);
            pageStartTime = Date.now();
        }
    }

    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') {
            flushDwell();
        } else {
            pageStartTime = Date.now();
        }
    });

    window.addEventListener('pagehide', flushDwell);

    // SPA Route Navigation Listeners
    function handleSpaRoute() {
        const currentPath = window.location.pathname;
        if (currentPath !== lastPath) {
            flushDwell();
            lastPath = currentPath;
            pageStartTime = Date.now();
            sendEvent(currentPath, 0);
        }
    }

    const origPushState = history.pushState;
    if (origPushState) {
        history.pushState = function () {
            origPushState.apply(this, arguments);
            handleSpaRoute();
        };
    }

    const origReplaceState = history.replaceState;
    if (origReplaceState) {
        history.replaceState = function () {
            origReplaceState.apply(this, arguments);
            handleSpaRoute();
        };
    }

    window.addEventListener('popstate', handleSpaRoute);
})();
