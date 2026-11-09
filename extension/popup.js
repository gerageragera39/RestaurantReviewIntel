(() => {
  const $ = id => document.getElementById(id);
  let tab, selected = '', meta, busy = false, lastError = '';
  const showDiagnostics = data => { $('diagnostics').textContent = JSON.stringify(data, null, 2); };
  const message = async (tabId, command, extra = {}) => {
    const result = await chrome.tabs.sendMessage(tabId, {type: 'RRI', command, ...extra});
    if (!result?.ok) {
      const error = new Error(result?.error || 'No response from Maps tab.'); error.diagnostics = result?.diagnostics; throw error;
    }
    return result.data;
  };
  const error = e => { lastError = e.message; $('status').textContent = e.message; if (e.diagnostics) showDiagnostics(e.diagnostics); };
  const mapsURL = value => { try {
    const u = new URL(value); return u.protocol === 'https:' && /^(www\.)?google\.(com|de|co\.uk|fr|at|ch|it|es|nl|ca|com\.au)$/.test(u.hostname) && u.pathname.startsWith('/maps');
  } catch { return false; } };
  async function refresh() {
    let currentDiagnostics;
    if (tab && mapsURL(tab.url) && !lastError) {
      try {
        const detected = await message(tab.id, 'detect'); currentDiagnostics = detected; showDiagnostics(detected);
        $('restaurant').textContent = detected.restaurant_name
          ? detected.restaurant_name + (detected.restaurant_name_source === 'url_path' ? ' (from Maps URL)' : '')
          : 'Restaurant identity unavailable';
        if (!selected) $('status').textContent = detected.mode === 'PREVIEW_MODE'
          ? 'Preview mode. Start opens More reviews / Weitere Rezensionen and waits for the full list.'
          : (detected.scrollable_found ? 'Full reviews panel ready.' : 'Waiting for a scrollable full reviews panel.');
      } catch { /* Saved collections are still exportable after navigation. */ }
    }
    const keys = (await chrome.storage.local.getKeys()).filter(k => k.startsWith('rri:run:'));
    const all = await chrome.storage.local.get(keys);
    const runs = Object.entries(all).filter(([k]) => k.startsWith('rri:run:')).map(([, v]) => v).reverse();
    if (!selected && runs.length) selected = runs[0].runId;
    const select = $('runs'); select.replaceChildren();
    for (const run of runs) { const option = document.createElement('option'); option.value = run.runId; option.textContent = `${run.restaurant_name} · ${run.runId}`; select.append(option); }
    select.value = selected;
    meta = all[`rri:run:${selected}`];
    if (!meta) return;
    let live = false;
    if (['waiting_for_reviews', 'running', 'paused', 'stopping', 'error'].includes(meta.state)) {
      try { meta = await message(meta.tabId, 'status', {runId: selected}); live = true; }
      catch { meta = {...meta, state: 'interrupted', reason: 'Tab closed, navigated, or extension reloaded. Saved data retained.'}; }
    }
    for (const key of ['observed', 'unique', 'withText', 'withDates', 'unexpanded']) $(key).textContent = meta[key] || 0;
    $('status').textContent = lastError || `${meta.state}${meta.reason ? ': ' + meta.reason : ''}`;
    if (!lastError && meta.diagnostics) showDiagnostics({...meta.diagnostics, ...currentDiagnostics,
      collection_url: meta.restaurant_url, stopping_reason: meta.reason || ''});
    $('pause').textContent = meta.state === 'paused' ? 'Resume' : 'Pause';
    $('pause').disabled = !live || !['running', 'paused'].includes(meta.state);
    $('stop').disabled = $('pause').disabled;
    $('json').disabled = $('csv').disabled = !meta.unique;
  }
  async function start() {
    if (!tab || !mapsURL(tab.url)) throw new Error('Select a Google Maps tab first.');
    const limit = Number($('limit').value); if (!Number.isInteger(limit) || limit < 0) throw new Error('Enter a nonnegative whole-number limit.');
    const runId = new Date().toISOString().replaceAll(/[:.]/g, '-') + '-' + crypto.randomUUID().slice(0, 8);
    $('status').textContent = 'Opening or detecting full reviews; waiting for the restaurant and review list…';
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
  (async () => {
    [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (tab && mapsURL(tab.url)) {
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['review-parser.js', 'collector.js', 'content.js']});
      const detected = await message(tab.id, 'detect');
      showDiagnostics(detected);
      $('restaurant').textContent = detected.restaurant_name
        ? detected.restaurant_name + (detected.restaurant_name_source === 'url_path' ? ' (from Maps URL)' : '')
        : 'Restaurant not detected';
      if (!detected.scrollable_found) $('status').textContent = 'Start opens More reviews / Weitere Rezensionen, or open the full panel yourself.';
    } else { $('restaurant').textContent = 'Select a Google Maps restaurant tab'; $('start').disabled = true; }
    await refresh();
    setInterval(() => { if (!busy) refresh().catch(error); }, 1500);
  })().catch(error);
})();
