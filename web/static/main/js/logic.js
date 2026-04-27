/**
 * Логика расчетов для фронтенда (продублирована из simple.js для тестирования)
 */

function sanitizeDecimalAmountInput(raw) {
    var s = raw === undefined || raw === null ? '' : String(raw);
    s = s.replace(/[\s\u00A0\u202F]/g, '');
    var lastComma = s.lastIndexOf(',');
    var lastDot = s.lastIndexOf('.');
    if (lastComma >= 0 && lastDot >= 0) {
        if (lastDot > lastComma) {
            s = s.split(',').join('');
        } else {
            s = s.split('.').join('');
        }
    }
    var out = '';
    var sep = false;
    for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i);
        if (c >= '0' && c <= '9') {
            out += c;
            continue;
        }
        if ((c === '.' || c === ',') && !sep) {
            sep = true;
            out += '.';
        }
    }
    return out;
}

function viewerIntermediarySlot(pr, viewerDid) {
    if (!pr || !pr.commissioners || typeof pr.commissioners !== 'object') return null;
    var v = (viewerDid || '').trim();
    if (!v) return null;
    var keys = Object.keys(pr.commissioners);
    for (var i = 0; i < keys.length; i++) {
        var slot = pr.commissioners[keys[i]];
        if (!slot || typeof slot !== 'object') continue;
        var role = String(slot.role || '').trim().toLowerCase();
        if (role !== 'intermediary') continue;
        if ((slot.did || '').trim() !== v) continue;
        return slot;
    }
    return null;
}

function prLegForAsset(pr, wantFiat) {
    if (!pr) return null;
    var d = String(pr.direction || '');
    if (d === 'fiat_to_stable') {
        return wantFiat ? pr.primary_leg : pr.counter_leg;
    }
    if (d === 'stable_to_fiat') {
        return wantFiat ? pr.counter_leg : pr.primary_leg;
    }
    return null;
}

function prStableEscrowFeesTotal(pr) {
    if (!pr || !pr.commissioners || typeof pr.commissioners !== 'object') return 0;
    var total = 0;
    var keys = Object.keys(pr.commissioners || {});
    for (var i = 0; i < keys.length; i++) {
        var slot = pr.commissioners[keys[i]];
        if (!slot || typeof slot !== 'object') continue;
        var role = String(slot.role || '').trim().toLowerCase();
        if (role !== 'system' && role !== 'intermediary') continue;
        var feeRaw = slot.borrow_amount != null ? String(slot.borrow_amount).trim() : '';
        if (!feeRaw) continue;
        var fa = parseFloat(sanitizeDecimalAmountInput(feeRaw));
        if (!isFinite(fa)) continue;
        total += fa;
    }
    return total;
}

function prStableBaseAmount(pr) {
    var stableLeg = prLegForAsset(pr, false);
    if (!stableLeg || String(stableLeg.asset_type || '').toLowerCase() !== 'stable') {
        return NaN;
    }
    var raw = stableLeg.amount != null ? String(stableLeg.amount).trim() : '';
    if (!raw) return NaN;
    var v = parseFloat(sanitizeDecimalAmountInput(raw));
    return isFinite(v) ? v : NaN;
}

function prStableNetForDisplay(pr) {
    if (!pr) return NaN;
    var base = prStableBaseAmount(pr);
    if (!isFinite(base)) return NaN;
    var direction = String(pr.direction || '');
    var fees = prStableEscrowFeesTotal(pr);
    if (!isFinite(fees) || fees <= 0) return base;

    if (direction === 'stable_to_fiat') {
        var net = base - fees;
        return net > 0 ? net : 0;
    } else if (direction === 'fiat_to_stable') {
        return base + fees;
    }
    return base;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        sanitizeDecimalAmountInput: sanitizeDecimalAmountInput,
        viewerIntermediarySlot: viewerIntermediarySlot,
        prLegForAsset: prLegForAsset,
        prStableEscrowFeesTotal: prStableEscrowFeesTotal,
        prStableBaseAmount: prStableBaseAmount,
        prStableNetForDisplay: prStableNetForDisplay
    };
}
