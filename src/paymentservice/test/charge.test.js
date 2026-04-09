const test = require('node:test');
const assert = require('node:assert/strict');

const charge = require('../charge');

const validRequest = {
  amount: { currency_code: 'USD', units: 10, nanos: 0 },
  credit_card: {
    credit_card_number: '4111111111111111',
    credit_card_cvv: 123,
    credit_card_expiration_year: new Date().getFullYear() + 1,
    credit_card_expiration_month: 12,
  },
};

test('charge returns transaction id for valid visa card', () => {
  const result = charge(validRequest);
  assert.equal(typeof result.transaction_id, 'string');
  assert.ok(result.transaction_id.length > 8);
});

test('charge throws for invalid card number', () => {
  const badRequest = {
    ...validRequest,
    credit_card: {
      ...validRequest.credit_card,
      credit_card_number: '123456',
    },
  };

  assert.throws(() => charge(badRequest));
});
