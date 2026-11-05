(function (root, factory) {
  const value = factory();
  if (typeof module === 'object' && module.exports) module.exports = value;
  else root.HonkSUData = value;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function canonicalUrl(input) {
    const text = String(input).trim();
    if (!text || /[\u0000-\u001f\u007f]/.test(text)) throw new Error('订阅链接不能包含换行或控制字符');
    let url;
    try { url = new URL(text); } catch { throw new Error('请输入有效的订阅链接'); }
    if (!['https:', 'http:'].includes(url.protocol)) throw new Error('仅支持 HTTP / HTTPS 订阅');
    if (!url.hostname) throw new Error('订阅地址缺少服务器');
    const encoded = url.href.replace(/'/g, '%27');
    if (encoded.length > 8192) throw new Error('订阅链接过长');
    return encoded;
  }
  function displayOrigin(input) {
    try {
      const url = new URL(input);
      return `${url.protocol}//${url.host}`;
    } catch { return '已保存订阅'; }
  }
  function parseStatus(text) {
    const data = Object.create(null);
    for (const line of text.split('\n')) {
      const at = line.indexOf('=');
      if (at > 0) data[line.slice(0, at)] = line.slice(at + 1);
    }
    return data;
  }
  function settings(mode, port, apiPort, bootstrap, autostart) {
    if (mode !== 'test') throw new Error('Android eBPF 入站尚未适配');
    const validPort = value => /^\d{4,5}$/.test(String(value)) && Number(value) >= 1024 && Number(value) <= 65535;
    if (!validPort(port) || !validPort(apiPort) || Number(port) === Number(apiPort)) throw new Error('请输入两个不同的 1024–65535 端口');
    const match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3}):(\d{1,5})$/.exec(bootstrap.trim());
    if (!match || match.slice(1, 5).some(value => Number(value) > 255) || Number(match[5]) < 1 || Number(match[5]) > 65535) throw new Error('DNS 格式应为 IPv4:端口');
    return [mode, String(Number(port)), String(Number(apiPort)), match.slice(1, 5).map(Number).join('.') + ':' + Number(match[5]), autostart ? '1' : '0'];
  }
  function quote(value) { return "'" + String(value).replace(/'/g, "'\\''") + "'"; }
  return Object.freeze({ canonicalUrl, displayOrigin, parseStatus, settings, quote });
});
