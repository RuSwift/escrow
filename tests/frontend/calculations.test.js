const { describe, it, expect } = require('vitest');
const { 
    prStableNetForDisplay, 
    prStableEscrowFeesTotal,
    prStableBaseAmount,
    prStableNetForOwner,
    prStableNetForIntermediary
} = require('../../web/static/main/js/logic.js');

describe('Frontend Calculation Logic', () => {
    
    describe('TC-1: fiat_to_stable (CNY -> USDT)', () => {
        const pr = {
            direction: 'fiat_to_stable',
            primary_leg: { asset_type: 'fiat', amount: '1000', code: 'CNY' },
            counter_leg: { asset_type: 'stable', amount: '100', code: 'USDT' },
            commissioners: {
                'system': { role: 'system', borrow_amount: '0.5' },
                'intermediary1': { role: 'intermediary', borrow_amount: '0.5' }
            }
        };

        it('should correctly sum total fees', () => {
            expect(prStableEscrowFeesTotal(pr)).toBe(1.0);
        });

        it('should return base amount for stable leg', () => {
            expect(prStableBaseAmount(pr)).toBe(100);
        });

        it('should return base for acceptor display (100.00 USDT)', () => {
            expect(prStableNetForDisplay(pr)).toBe(100.0);
        });

        it('should return base - fees for owner receive display (99.00 USDT)', () => {
            expect(prStableNetForOwner(pr)).toBe(99.0);
        });
    });

    describe('TC-2: stable_to_fiat (USDT -> CNY)', () => {
        const pr = {
            direction: 'stable_to_fiat',
            primary_leg: { asset_type: 'stable', amount: '100', code: 'USDT' },
            counter_leg: { asset_type: 'fiat', amount: '1000', code: 'CNY' },
            commissioners: {
                'system': { role: 'system', borrow_amount: '0.2' },
                'intermediary1': { role: 'intermediary', borrow_amount: '0.8' }
            }
        };

        it('should correctly sum total fees', () => {
            expect(prStableEscrowFeesTotal(pr)).toBe(1.0);
        });

        it('should return base amount for stable leg', () => {
            expect(prStableBaseAmount(pr)).toBe(100);
        });

        it('should return base - fees for acceptor display (99.00 USDT)', () => {
            expect(prStableNetForDisplay(pr)).toBe(99.0);
        });
    });

    describe('Edge Cases', () => {
        it('should return base if no fees present', () => {
            const pr = {
                direction: 'fiat_to_stable',
                counter_leg: { asset_type: 'stable', amount: '100', code: 'USDT' },
                commissioners: {}
            };
            expect(prStableNetForDisplay(pr)).toBe(100);
        });

        it('should handle string amounts with commas and spaces', () => {
            const pr = {
                direction: 'fiat_to_stable',
                counter_leg: { asset_type: 'stable', amount: '1 000,00', code: 'USDT' },
                commissioners: {
                    'system': { role: 'system', borrow_amount: '10,50' }
                }
            };
            expect(prStableNetForDisplay(pr)).toBe(1000.0);
            expect(prStableNetForOwner(pr)).toBe(989.5);
        });

        it('should return NaN if stable leg is missing', () => {
            const pr = {
                direction: 'fiat_to_stable',
                primary_leg: { asset_type: 'fiat', amount: '1000' }
            };
            expect(prStableNetForDisplay(pr)).toBeNaN();
        });
    });

    describe('TC-3: fiat_to_stable negotiated stable (commissioner & owner views)', () => {
        const pr = {
            direction: 'fiat_to_stable',
            primary_leg: { asset_type: 'fiat', amount: '10000', code: 'CNY' },
            counter_leg: { asset_type: 'stable', amount: '1000', code: 'USDT' },
            commissioners: {
                'system': { role: 'system', borrow_amount: '3' },
                'i_me': { role: 'intermediary', did: 'did:me', borrow_amount: '7' }
            }
        };

        it('owner should see net receive (990 USDT)', () => {
            expect(prStableNetForOwner(pr)).toBe(990.0);
        });

        it('acceptor should see base (1000 USDT)', () => {
            expect(prStableNetForDisplay(pr)).toBe(1000.0);
        });

        it('intermediary should see base - my fee (993 USDT)', () => {
            expect(prStableNetForIntermediary(pr, 'did:me')).toBe(993.0);
        });
    });
});
