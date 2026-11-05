const { test } = require('node:test');
const assert = require('node:assert/strict');
const data = require('../module/webroot/domain.js');

test('subscription URLs keep query credentials and encode dae quote characters', () => {
  assert.equal(data.canonicalUrl("https://example.com/sub?a='abc'&token=123"), 'https://example.com/sub?a=%27abc%27&token=123');
  assert.equal(data.canonicalUrl(' https://example.com/sub '), 'https://example.com/sub');
  assert.match(data.canonicalUrl('https://例子.中国/订阅'), /^https:\/\/xn--/);
});
test('subscription URL validation rejects scripts, files, missing hosts and control bytes', () => {
  for (const value of ['javascript:alert(1)', 'file:///data/adb/x', 'https://', 'https://a.test/\nnode', 'https://a.test/\u0000']) assert.throws(() => data.canonicalUrl(value));
});
test('provider display does not reveal userinfo, paths, query strings or fragments', () => {
  assert.equal(data.displayOrigin('https://user:password@example.com:9443/private?token=123#secret'), 'https://example.com:9443');
});
test('settings use distinct ports and a valid IPv4 resolver', () => {
  assert.deepEqual(data.settings('test', '12345', '9090', '223.5.5.5:53', false), ['test', '12345', '9090', '223.5.5.5:53', '0']);
  assert.deepEqual(data.settings('test', '01024', '09090', '001.1.1.1:053', true), ['test', '1024', '9090', '1.1.1.1:53', '1']);
  for (const [port, api, dns] of [['12345', '12345', '1.1.1.1:53'], ['0', '9090', '1.1.1.1:53'], ['65536', '9090', '1.1.1.1:53'], ['12345', '9090', '256.1.1.1:53'], ['12345', '9090', '1.1.1.1:0'], ['12345', '9090', 'dns.google:53']]) assert.throws(() => data.settings('test', port, api, dns, false));
  assert.throws(() => data.settings('ebpf', '12345', '9090', '1.1.1.1:53', false));
});
test('shell arguments are quoted without evaluation', () => {
  assert.equal(data.quote("a'b"), "'a'\\''b'");
  assert.equal(data.quote('$(id); `id`'), "'$(id); `id`'");
});
test('status parsing preserves equal signs and avoids prototype mutation', () => {
  const status = data.parseStatus('running=1\nsecret=a=b\n__proto__=bad\n');
  assert.equal(Object.getPrototypeOf(status), null);
  assert.equal(status.secret, 'a=b');
  assert.equal(status.running, '1');
});

test('KernelSU bridge passes the documented callback signature and cleans up', async () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const window = { HonkSUData: data };
  let recorded;
  window.ksu = { exec(command, options, callback) {
    recorded = { command, options, callback };
    window[callback](0, 'running=1', '');
  } };
  vm.runInNewContext(fs.readFileSync(require.resolve('../module/webroot/bridge.js'), 'utf8'), { window, setTimeout, clearTimeout });
  assert.equal(await window.HonkSUBridge.command('add', ["a'b", '$(id)']), 'running=1');
  assert.equal(recorded.options, '{}');
  assert.equal(recorded.command, "'/data/adb/modules/honksu/scripts/honksuctl' 'add' 'a'\\''b' '$(id)'");
  assert.equal(window[recorded.callback], undefined);
});

test('bridge failures reject instead of reporting a successful operation', async () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const window = { HonkSUData: data, ksu: { exec(command, options, callback) { window[callback](1, '', 'controller failed'); } } };
  vm.runInNewContext(fs.readFileSync(require.resolve('../module/webroot/bridge.js'), 'utf8'), { window, setTimeout, clearTimeout });
  await assert.rejects(window.HonkSUBridge.command('start'), /controller failed/);
});

test('browser preview cannot pretend to execute root commands', async () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const window = { HonkSUData: data };
  vm.runInNewContext(fs.readFileSync(require.resolve('../module/webroot/bridge.js'), 'utf8'), { window, setTimeout, clearTimeout });
  assert.equal(window.HonkSUBridge.available, false);
  await assert.rejects(window.HonkSUBridge.command('start'), /KernelSU/);
});
