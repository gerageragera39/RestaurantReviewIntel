(() => {
  if (globalThis.RRI.listenerInstalled) return;
  const R = globalThis.RRI; R.listenerInstalled = true;
  let collector;
  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id !== chrome.runtime.id || message?.type !== 'RRI') return;
    (async () => {
      if (message.command === 'detect') return R.diagnostics();
      if (message.command === 'start') {
        if (collector && ['waiting_for_reviews', 'running', 'paused', 'stopping'].includes(collector.state)) throw new Error('Stop the current collection first.');
        collector = new R.Collector(); return await collector.start(message.options);
      }
      if (!collector || (message.runId && message.runId !== collector.runId)) throw new Error('Collection is no longer running in this tab. Saved reviews remain exportable.');
      if (message.command === 'status') return collector.status();
      if (message.command === 'pause') return await collector.pause();
      if (message.command === 'resume') return await collector.resume();
      if (message.command === 'stop') return await collector.finish();
      throw new Error('Unknown command');
    })().then(data => respond({ok: true, data}), e => respond({ok: false, error: e.message,
      diagnostics: {...R.diagnostics(), start_failed_panel_detection: collector?.startFailedPanelDetection || false,
        stopping_reason: collector?.reason || e.code || 'command_failed'}}));
    return true;
  });
})();
