(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const bridge = window.HonkSUBridge;
  const data = window.HonkSUData;
  let state = Object.create(null);
  let busy = false;
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5000);
  }
  function base64(text) {
    const bytes = new TextEncoder().encode(text);
    return btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''));
  }
  function unbase64(text) {
    return new TextDecoder().decode(Uint8Array.from(atob(text), value => value.charCodeAt(0)));
  }
  function buttons() {
    for (const id of ['add-subscription', 'save-settings', 'refresh-log', 'clear-log']) $(id).disabled = busy || !bridge.available;
    $('start').disabled = busy || !bridge.available || state.core_present !== '1' || state.running === '1';
    $('stop').disabled = busy || !bridge.available || state.running !== '1';
    $('restart').disabled = busy || !bridge.available || state.core_present !== '1';
    $('refresh').disabled = busy;
    $('run-probe').disabled = busy || !bridge.available || state.core_present !== '1' || state.probe_available !== '1';
    $('view-probe').disabled = busy || !bridge.available;
    for (const button of document.querySelectorAll('.remove')) button.disabled = busy || !bridge.available;
  }
  function render(settings = false) {
    const running = state.running === '1';
    $('status-dot').classList.toggle('running', running);
    $('status-label').textContent = running ? '核心进程运行中' : '核心已停止';
    $('hero-title').textContent = running ? '核心测试运行中' : state.core_present === '1' ? '准备启动' : '未找到核心';
    $('hero-detail').textContent = running ? '当前未接管手机流量' : state.core_present === '1' ? '导入订阅，配置入站后启动测试核心' : '请安装包含 honk-core 的模块构建产物';
    $('provider-count').textContent = `${state.providers || 0} 个`;
    $('subscription-total').textContent = `${state.providers || 0} / 32`;
    $('core-pid').textContent = running ? state.pid : '—';
    $('inbound-summary').textContent = state.port ? `:${state.port} · 不接管流量` : '—';
    $('api-summary').textContent = state.api_port ? `127.0.0.1:${state.api_port}` : '—';
    $('core-build').textContent = state.core_ebpf_compiled === '1' ? 'Clash API · VLESS / VMess · eBPF 已编译' : 'Clash API · VLESS / VMess';
    $('core-revision').textContent = state.core_commit ? state.core_commit.slice(0, 12) : '—';
    $('hot-install-status').textContent = ({ complete: '已完成', pending: '未完成，请查看安装日志', failed: '恢复失败，请查看安装日志', none: '尚无记录' })[state.hot_install] || '尚无记录';
    const result = data.probeResult(state);
    $('probe-state').textContent = result.label;
    $('probe-detail').textContent = result.detail;
    $('probe-time').textContent = /^\d+$/.test(state.probe_time || '') ? `记录时间：${new Date(Number(state.probe_time) * 1000).toLocaleString()}` : '验证由你手动运行，不会在开机时自动执行';
    $('old-core').hidden = !running || state.running_core_current !== '0';
    $('dirty').hidden = state.pending_restart !== '1';
    if (settings) {
      $('port').value = state.port || '12346';
      $('api-port').value = state.api_port || '9091';
      $('bootstrap').value = state.bootstrap || '223.5.5.5:53';
      $('autostart').checked = state.autostart === '1';
    }
    buttons();
  }
  async function refresh(settings = false) {
    state = data.parseStatus(await bridge.command('status'));
    render(settings);
  }
  async function providers() {
    const text = await bridge.command('providers');
    const list = $('subscription-list');
    list.replaceChildren();
    let count = 0;
    for (const line of text.trim().split('\n')) {
      if (!line) continue;
      const [id, name, url] = line.split('\t');
      if (!/^p\d+$/.test(id)) continue;
      let title, origin;
      try { title = unbase64(name); origin = data.displayOrigin(unbase64(url)); }
      catch { continue; }
      count++;
      const row = document.createElement('article'); row.className = 'provider';
      const body = document.createElement('div');
      const h3 = document.createElement('h3'); h3.textContent = title;
      const detail = document.createElement('p'); detail.textContent = origin;
      body.append(h3, detail);
      const button = document.createElement('button'); button.className = 'remove'; button.textContent = '移除';
      button.setAttribute('aria-label', `移除订阅 ${title}`);
      button.addEventListener('click', () => perform(async () => {
        await bridge.command('remove', [id]); await providers(); await refresh(); toast('订阅已移除，重启核心后生效');
      }));
      row.append(body, button); list.append(row);
    }
    if (!count) {
      const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = '还没有订阅，先导入一个吧'; list.append(empty);
    }
    buttons();
  }
  async function logs() { $('log-output').textContent = (await bridge.command('logs')).trim() || '尚无日志'; }
  async function probeLogs() {
    $('probe-output').hidden = false;
    $('probe-output').textContent = (await bridge.command('probe-log')).trim() || '尚无验证记录';
  }
  async function perform(action) {
    if (busy) return;
    busy = true; buttons();
    try { await action(); }
    catch (error) { toast(error.message || String(error)); }
    finally { busy = false; buttons(); }
  }
  for (const button of document.querySelectorAll('[data-page]')) button.addEventListener('click', () => {
    for (const page of document.querySelectorAll('.page')) page.hidden = page.id !== button.dataset.page;
    for (const tab of document.querySelectorAll('[data-page]')) {
      tab.classList.toggle('active', tab === button);
      if (tab === button) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
    }
    if (bridge.available && button.dataset.page === 'logs') perform(logs);
  });
  $('subscription-form').addEventListener('submit', event => {
    event.preventDefault();
    perform(async () => {
      const name = $('subscription-name').value.trim();
      if (!name || new TextEncoder().encode(name).length > 120) throw new Error('订阅名称应为 1–120 字节');
      const url = data.canonicalUrl($('subscription-url').value);
      await bridge.command('add', [base64(name), base64(url)]);
      $('subscription-form').reset(); await providers(); await refresh(); toast('订阅已保存，核心下次启动时加载');
    });
  });
  $('settings-form').addEventListener('submit', event => {
    event.preventDefault();
    perform(async () => {
      const args = data.settings('test', $('port').value, $('api-port').value, $('bootstrap').value, $('autostart').checked);
      await bridge.command('settings', args); await refresh(true); toast('设置已保存，重启核心后生效');
    });
  });
  $('start').addEventListener('click', () => perform(async () => { await bridge.command('start'); await refresh(); toast('测试核心进程已启动，流量接管未启用'); }));
  $('stop').addEventListener('click', () => perform(async () => { await bridge.command('stop'); await refresh(); toast('核心已停止'); }));
  $('restart').addEventListener('click', () => perform(async () => { await bridge.command('restart'); await refresh(); toast('核心已重启，流量接管未启用'); }));
  $('refresh').addEventListener('click', () => perform(async () => { if (!bridge.available) throw new Error('请从 KernelSU 模块 WebUI 打开'); await refresh(true); await providers(); toast('状态已刷新'); }));
  $('refresh-log').addEventListener('click', () => perform(logs));
  $('clear-log').addEventListener('click', () => perform(async () => { await bridge.command('clear-log'); await logs(); toast('日志已清空'); }));
  $('view-probe').addEventListener('click', () => perform(probeLogs));
  $('run-probe').addEventListener('click', () => perform(async () => {
    state.probe_state = 'running'; render();
    $('probe-output').hidden = false;
    $('probe-output').textContent = '正在隔离网络中验证，最长约 45 秒。完成后会显示结果。';
    try { await bridge.command('probe'); }
    finally { await refresh(); await probeLogs(); }
    toast('隔离验证通过，手机流量接管仍未启用');
  }));
  if (bridge.available) {
    perform(async () => { await refresh(true); await providers(); });
    const poll = setInterval(() => {
      if (!busy && !document.hidden) perform(() => refresh());
    }, 5000);
    window.addEventListener('pagehide', () => clearInterval(poll), { once: true });
  }
  else {
    $('environment').hidden = false;
    $('status-label').textContent = '浏览器预览';
    $('hero-title').textContent = 'HonkSU 管理器';
    $('hero-detail').textContent = '在 KernelSU 中打开模块 WebUI 后可管理本机核心';
    buttons();
  }
})();
