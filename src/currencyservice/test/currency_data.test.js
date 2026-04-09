const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('currency conversion dataset exists and contains key currencies', () => {
  const file = path.join(__dirname, '..', 'data', 'currency_conversion.json');
  const raw = fs.readFileSync(file, 'utf8');
  const data = JSON.parse(raw);

  assert.equal(typeof data, 'object');
  assert.ok(Object.keys(data).length > 10);
  assert.ok(data.USD > 0);
  assert.ok(data.EUR > 0);
  assert.ok(data.CNY > 0);
});
