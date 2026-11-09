(() => {
  const $ = id => document.getElementById(id);
  const t = key => RRI.t(key);
  let tab, selected = '', meta, busy = false, lastError = '';
  const showDiagnostics = data => { $('diagnostics').textContent = JSON.stringify(data, null, 2); };
  const verifyContentVersion = detected => {
    if (detected.content_script_version !== chrome.runtime.getManifest().version) {
      const e = new Error(t('reloadMaps')); e.diagnostics = detected; throw e;
    }
  };
  const message = async (tabId, command, extra = {}) => {
    const result = await chrome.tabs.sendMessage(tabId, {type: 'RRI', command, ...extra});
    if (!result?.ok) {
      const error = new Error(result?.error || 'No response from Maps tab.'); error.diagnostics = result?.diagnostics; error.code = result?.code; throw error;
    }
    return result.data;
  };
  const error = e => { lastError = e.code && t(e.code) !== e.code ? t(e.code) : e.message; $('status').textContent = lastError; if (e.diagnostics) showDiagnostics(e.diagnostics); };
  async function refreshLog() {
    if (!$('log-details').open || !selected) return;
    const data = await chrome.storage.local.get(`rri:log:${selected}`);
    const journal = data[`rri:log:${selected}`];
    $('log-view').textContent = journal ? journal.events.slice(-12).map(e => `${e.at} ${e.event}\n${JSON.stringify(e.details)}`).join('\n\n') : '';
  }
  const mapsURL = value => { try {
    const u = new URL(value); return u.protocol === 'https:' && /^(www\.)?google\.(com|de|co\.uk|fr|at|ch|it|es|nl|ca|com\.au)$/.test(u.hostname) && u.pathname.startsWith('/maps');
  } catch { return false; } };
  async function refresh() {
    let currentDiagnostics;
    if (!tab || !mapsURL(tab.url)) {
      $('restaurant').textContent = t('select');
      if (!selected && !lastError) $('status').textContent = t('select');
    }
    if (tab && mapsURL(tab.url) && !lastError) {
      try {
        const detected = await message(tab.id, 'detect'); currentDiagnostics = detected; showDiagnostics(detected);
        $('restaurant').textContent = detected.restaurant_name
          ? detected.restaurant_name + (detected.restaurant_name_source === 'url_path' ? t('fromURL') : '')
          : t('unknown');
        if (!selected) $('status').textContent = detected.mode === 'PREVIEW_MODE'
          ? t('preview') : (detected.scrollable_found ? t('ready') : t('waiting'));
      } catch { /* Saved collections are still exportable after navigation. */ }
    }
    const keys = (await chrome.storage.local.getKeys()).filter(k => k.startsWith('rri:run:'));
    const all = await chrome.storage.local.get(keys);
    const runs = Object.entries(all).filter(([k]) => k.startsWith('rri:run:')).map(([, v]) => v).reverse();
    if (!selected && runs.length) selected = runs[0].runId;
    const select = $('runs'); select.replaceChildren();
    if (!runs.length) { const option = document.createElement('option'); option.value = ''; option.textContent = t('empty'); select.append(option); }
    for (const run of runs) { const option = document.createElement('option'); option.value = run.runId; option.textContent = `${run.restaurant_name} · ${run.runId}`; select.append(option); }
    select.value = selected;
    meta = all[`rri:run:${selected}`];
    $('logs').disabled = !meta;
    if (!meta) return;
    let live = false;
    if (['waiting_for_reviews', 'running', 'paused', 'stopping', 'error'].includes(meta.state)) {
      try { meta = await message(meta.tabId, 'status', {runId: selected}); live = true; }
      catch { meta = {...meta, state: 'interrupted', reason: 'interruptedDetail'}; }
    }
    for (const key of ['observed', 'unique', 'withText', 'withDates', 'unexpanded']) $(key).textContent = meta[key] || 0;
    $('status').textContent = lastError || `${t(meta.state)}${meta.reason ? ': ' + t(meta.reason) : ''}`;
    if (!lastError && meta.diagnostics) showDiagnostics({...meta.diagnostics, ...currentDiagnostics,
      collection_url: meta.restaurant_url, stopping_reason: meta.reason || ''});
    $('pause').textContent = t(meta.state === 'paused' ? 'resume' : 'pause');
    $('pause').disabled = !live || !['running', 'paused'].includes(meta.state);
    $('stop').disabled = $('pause').disabled;
    $('json').disabled = $('csv').disabled = !meta.unique;
    await refreshLog();
  }
  async function start() {
    if (!tab || !mapsURL(tab.url)) throw new Error(t('select'));
    verifyContentVersion(await message(tab.id, 'detect'));
    const limit = Number($('limit').value); if (!Number.isInteger(limit) || limit < 0) throw new Error(t('invalidLimit'));
    const runId = new Date().toISOString().replaceAll(/[:.]/g, '-') + '-' + crypto.randomUUID().slice(0, 8);
    selected = runId;
    $('status').textContent = t('opening');
    await message(tab.id, 'start', {options: {runId, tabId: tab.id, limit, autoScroll: $('auto').checked}});
    selected = runId; await refresh();
  }
  function action(id, fn) { $(id).addEventListener('click', async () => {
    if (busy) return; busy = true; lastError = '';
    try { await fn(); } catch (e) { error(e); } finally { busy = false; }
  }); }
  action('start', start);
  action('pause', async () => { await message(meta.tabId, meta.state === 'paused' ? 'resume' : 'pause', {runId: selected}); await refresh(); });
  action('stop', async () => { await message(meta.tabId, 'stop', {runId: selected}); await refresh(); });
  $('logs').addEventListener('click', async () => {
    try {
      let journal;
      if (meta?.tabId != null) { try { journal = await message(meta.tabId, 'logs', {runId: selected}); } catch { /* Use persisted log after navigation. */ } }
      const stored = await chrome.storage.local.get([`rri:log:${selected}`, `rri:run:${selected}`]);
      RRI.downloadLog({type: 'rri_diagnostic_log', exported_at: new Date().toISOString(),
        run: stored[`rri:run:${selected}`] || meta || null, journal: journal || stored[`rri:log:${selected}`] || null}, selected);
    } catch (e) { error(e); }
  });
  $('log-details').addEventListener('toggle', () => refreshLog().catch(error));
  for (const format of ['json', 'csv']) action(format, async () => {
    if (['running', 'paused'].includes(meta.state)) {
      await message(meta.tabId, 'pause', {runId: selected}); await refresh();
    }
    const keys = (await chrome.storage.local.getKeys()).filter(k => k.startsWith(`rri:review:${selected}:`));
    const all = await chrome.storage.local.get(keys);
    const rows = Object.entries(all).filter(([k]) => k.startsWith(`rri:review:${selected}:`)).map(([, v]) => v);
    RRI.download(rows, format, selected);
  });
  $('runs').addEventListener('change', () => { lastError = ''; selected = $('runs').value; refresh().catch(error); });
  $('language').addEventListener('change', async () => {
    try { RRI.setUILanguage($('language').value); lastError = ''; await chrome.storage.local.set({'rri:ui_language': RRI.uiLanguage}); await refresh(); }
    catch (e) { error(e); }
  });
  (async () => {
    const language = (await chrome.storage.local.get('rri:ui_language'))['rri:ui_language'] || 'en';
    RRI.setUILanguage(language); $('language').value = RRI.uiLanguage;
    [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (tab && mapsURL(tab.url)) {
      try {
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['review-parser.js', 'collector.js', 'content.js']});
      const detected = await message(tab.id, 'detect');
      showDiagnostics(detected);
      verifyContentVersion(detected);
      $('restaurant').textContent = detected.restaurant_name
        ? detected.restaurant_name + (detected.restaurant_name_source === 'url_path' ? t('fromURL') : '')
        : t('unknown');
      if (!detected.scrollable_found) $('status').textContent = t('open');
      } catch (e) { error(e); }
    } else { $('restaurant').textContent = t('select'); $('start').disabled = true; }
    await refresh();
    setInterval(() => refresh().catch(error), 1500);
  })().catch(error);
})();
