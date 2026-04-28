const { describe, it, expect } = require('vitest');
const { orderAmountsLineParts } = require('../../web/static/main/js/logic.js');

describe('orderAmountsLineParts (matches list/detail numbers)', () => {
    it('TC-3 fiat_to_stable: acceptor sees base 1000 USDT', () => {
        const pr = {
            direction: 'fiat_to_stable',
            owner_did: 'did:owner',
            primary_leg: { asset_type: 'fiat', amount: '10000', code: 'CNY' },
            counter_leg: { asset_type: 'stable', amount: '1000', code: 'USDT' },
            commissioners: {
                system: { role: 'system', borrow_amount: '3' },
                i_me: { role: 'intermediary', did: 'did:me', borrow_amount: '7' }
            }
        };
        const parts = orderAmountsLineParts(pr, 'did:acceptor');
        expect(parts.give).toBe('10000.00 CNY');
        expect(parts.receive).toBe('1000.00 USDT');
    });

    it('TC-3 fiat_to_stable: intermediary sees 993 USDT', () => {
        const pr = {
            direction: 'fiat_to_stable',
            owner_did: 'did:owner',
            primary_leg: { asset_type: 'fiat', amount: '10000', code: 'CNY' },
            counter_leg: { asset_type: 'stable', amount: '1000', code: 'USDT' },
            commissioners: {
                system: { role: 'system', borrow_amount: '3' },
                i_me: { role: 'intermediary', did: 'did:me', borrow_amount: '7' }
            }
        };
        const parts = orderAmountsLineParts(pr, 'did:me');
        expect(parts.receive).toBe('993.00 USDT');
    });

    it('TC-3 fiat_to_stable: owner sees net 990 USDT', () => {
        const pr = {
            direction: 'fiat_to_stable',
            owner_did: 'did:owner',
            primary_leg: { asset_type: 'fiat', amount: '10000', code: 'CNY' },
            counter_leg: { asset_type: 'stable', amount: '1000', code: 'USDT' },
            commissioners: {
                system: { role: 'system', borrow_amount: '3' },
                i_me: { role: 'intermediary', did: 'did:me', borrow_amount: '7' }
            }
        };
        const parts = orderAmountsLineParts(pr, 'did:owner');
        expect(parts.receive).toBe('990.00 USDT');
    });
});

