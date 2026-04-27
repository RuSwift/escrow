/**
 * Простейший тестовый раннер для проверки логики без внешних зависимостей
 */
const { 
    prStableNetForDisplay, 
    prStableEscrowFeesTotal,
    prStableBaseAmount 
} = require('../../web/static/main/js/logic.js');

const tests = [];

function describe(name, fn) {
    console.log(`\n${name}`);
    fn();
}

function it(name, fn) {
    try {
        fn();
        console.log(`  ✓ ${name}`);
    } catch (err) {
        console.log(`  ✗ ${name}`);
        console.error(err);
        process.exit(1);
    }
}

function expect(actual) {
    return {
        toBe: (expected) => {
            if (actual !== expected) {
                throw new Error(`Expected ${expected} but got ${actual}`);
            }
        },
        toBeNaN: () => {
            if (!isNaN(actual)) {
                throw new Error(`Expected NaN but got ${actual}`);
            }
        }
    };
}

// --- Тесты ---

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

    it('should return base + fees for acceptor display (101.00 USDT)', () => {
        expect(prStableNetForDisplay(pr)).toBe(101.0);
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
        expect(prStableNetForDisplay(pr)).toBe(1010.5);
    });

    it('should return NaN if stable leg is missing', () => {
        const pr = {
            direction: 'fiat_to_stable',
            primary_leg: { asset_type: 'fiat', amount: '1000' }
        };
        expect(prStableNetForDisplay(pr)).toBeNaN();
    });
});

console.log('\nAll tests passed successfully!');
