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
        // fiat_to_stable: комиссии удерживаются из залога; контрагент/акцептор видит базу B.
        return base;
    }
    return base;
}

function prStableNetForOwner(pr) {
    if (!pr) return NaN;
    var base = prStableBaseAmount(pr);
    if (!isFinite(base)) return NaN;
    var direction = String(pr.direction || '');
    if (direction !== 'fiat_to_stable') return base;
    var fees = prStableEscrowFeesTotal(pr);
    if (!isFinite(fees) || fees <= 0) return base;
    var net = base - fees;
    return net > 0 ? net : 0;
}

function prStableNetForIntermediary(pr, viewerDid) {
    if (!pr) return NaN;
    var base = prStableBaseAmount(pr);
    if (!isFinite(base)) return NaN;
    var direction = String(pr.direction || '');
    if (direction !== 'fiat_to_stable') return base;
    var slot = viewerIntermediarySlot(pr, viewerDid);
    if (!slot) return base;
    var feeRaw = slot.borrow_amount != null ? String(slot.borrow_amount).trim() : '';
    if (!feeRaw) return base;
    var fa = parseFloat(sanitizeDecimalAmountInput(feeRaw));
    if (!isFinite(fa) || fa <= 0) return base;
    var net = base - fa;
    return net > 0 ? net : 0;
}

function _fmt2(n) {
    if (!isFinite(n)) return '';
    return (Math.round(n * 1e2) / 1e2).toFixed(2);
}

function _legCode(leg) {
    return leg && leg.code ? String(leg.code).trim().toUpperCase() : '';
}

function _legAmountStr(leg) {
    if (!leg) return '';
    var raw = leg.amount != null ? String(leg.amount).trim() : '';
    if (!raw) return '';
    var v = parseFloat(sanitizeDecimalAmountInput(raw));
    return isFinite(v) ? _fmt2(v) : '';
}

/**
 * Unit-test helper: builds the same "give/receive" amounts selection as simple.js orderAmountsLine,
 * but with deterministic formatting (dot decimal, 2 digits) for assertions.
 *
 * Returns: { give: "10000.00 CNY", receive: "993.00 USDT", hasReceiveAmount: boolean }
 */
function orderAmountsLineParts(pr, viewerDid) {
    if (!pr) return { give: '', receive: '', hasReceiveAmount: false };
    var pl = pr.primary_leg || {};
    var cl = pr.counter_leg || {};
    var direction = String(pr.direction || '');
    var stableIsReceive = direction === 'fiat_to_stable';
    var vd = (viewerDid || '').trim();
    var ownerDid = (pr.owner_did || '').trim();
    var amOwner = !!(vd && ownerDid && vd === ownerDid);
    var amIntermediary = !!(vd && !amOwner && viewerIntermediarySlot(pr, vd));

    var giveLeg = stableIsReceive ? pl : cl;
    var recvLeg = stableIsReceive ? cl : pl;
    var giveCode = _legCode(giveLeg);
    var recvCode = _legCode(recvLeg);
    var giveAmt = _legAmountStr(giveLeg);
    var recvAmt = _legAmountStr(recvLeg);
    var hasReceiveAmount = !!recvAmt;

    if (direction === 'fiat_to_stable' && hasReceiveAmount) {
        if (amOwner) {
            var ownNet = prStableNetForOwner(pr);
            recvAmt = _fmt2(ownNet);
        } else if (amIntermediary) {
            var intermNet = prStableNetForIntermediary(pr, vd);
            recvAmt = _fmt2(intermNet);
        } else {
            // acceptor/counterparty sees base B
            var base = prStableBaseAmount(pr);
            recvAmt = _fmt2(base);
        }
    }

    // stable_to_fiat: for non-owner use prStableNetForDisplay (base - fees); owner sees raw legs
    if (direction === 'stable_to_fiat' && hasReceiveAmount) {
        var stableLeg = prLegForAsset(pr, false);
        var stableCode = _legCode(stableLeg);
        var netStable = prStableNetForDisplay(pr);
        if (!amOwner && isFinite(netStable)) {
            if (stableIsReceive) {
                recvAmt = _fmt2(netStable);
                recvCode = stableCode;
            } else {
                giveAmt = _fmt2(netStable);
                giveCode = stableCode;
            }
        }
    }

    var give = (giveAmt ? giveAmt + (giveCode ? ' ' + giveCode : '') : (giveCode || ''));
    var receive = (recvAmt ? recvAmt + (recvCode ? ' ' + recvCode : '') : (recvCode || ''));
    return { give: give, receive: receive, hasReceiveAmount: hasReceiveAmount };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        sanitizeDecimalAmountInput: sanitizeDecimalAmountInput,
        viewerIntermediarySlot: viewerIntermediarySlot,
        prLegForAsset: prLegForAsset,
        prStableEscrowFeesTotal: prStableEscrowFeesTotal,
        prStableBaseAmount: prStableBaseAmount,
        prStableNetForDisplay: prStableNetForDisplay,
        prStableNetForOwner: prStableNetForOwner,
        prStableNetForIntermediary: prStableNetForIntermediary,
        orderAmountsLineParts: orderAmountsLineParts
    };
}
