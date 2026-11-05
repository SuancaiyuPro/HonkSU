(function () {
  'use strict';
  let counter = 0;
  const available = typeof window.ksu === 'object' && typeof window.ksu.exec === 'function';
  function command(action, args = []) {
    if (!available) return Promise.reject(new Error('请从 KernelSU 模块 WebUI 打开'));
    const callback = `honksu_${Date.now()}_${counter++}`;
    const input = ['/data/adb/modules/honksu/scripts/honksuctl', action, ...args].map(window.HonkSUData.quote).join(' ');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        delete window[callback];
        reject(new Error('操作超时，请刷新状态确认结果'));
      }, action === 'probe' ? 65000 : 30000);
      window[callback] = (errno, stdout, stderr) => {
        clearTimeout(timer);
        delete window[callback];
        if (Number(errno) !== 0) reject(new Error(String(stderr || stdout || '模块操作失败').trim()));
        else resolve(String(stdout || ''));
      };
      try { window.ksu.exec(input, '{}', callback); }
      catch (error) { clearTimeout(timer); delete window[callback]; reject(error); }
    });
  }
  window.HonkSUBridge = Object.freeze({ available, command });
})();
