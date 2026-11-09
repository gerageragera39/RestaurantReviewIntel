(() => {
  const R = globalThis.RRI = globalThis.RRI || {};
  R.selectors = {
    card: '.jftiEf, [role="article"][data-review-id]',
    text: '.wiI7pd, [data-review-text]',
    date: '.rsqaWe, [data-review-date]',
    rating: '.kvMYJc[aria-label], [role="img"][aria-label*="star" i], [role="img"][aria-label*="stern" i]'
  };
  const months = [
    'january jan januar', 'february feb februar', 'march mar märz mär', 'april apr',
    'may mai', 'june jun juni', 'july jul juli', 'august aug', 'september sep sept',
    'october oct oktober okt', 'november nov', 'december dec dezember dez'
  ];
  const iso = d => d.toISOString().slice(0, 10);
  R.parseDate = (raw, now = new Date()) => {
    const unknown = {date_estimate: null, date_is_exact: false};
    // Relative labels use the browser's local calendar day, independent of UTC scrape time.
    const ref = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    const s = raw.toLocaleLowerCase().replace(/\s+/g, ' ').trim();
    let y, m, d, match, result, exact = false;
    if ((match = s.match(/^(\d{4})-(\d{2})-(\d{2})$/))) [, y, m, d] = match;
    else if ((match = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/))) [, d, m, y] = match;
    else if ((match = s.match(/^(\d{1,2})\.? ([a-zäöü]+)\.? (\d{4})$/))) {
      d = match[1]; y = match[3]; m = months.findIndex(v => v.split(' ').includes(match[2])) + 1;
    } else if ((match = s.match(/^([a-z]+) (\d{1,2}), (\d{4})$/))) {
      d = match[2]; y = match[3]; m = months.findIndex(v => v.split(' ').includes(match[1])) + 1;
    }
    if (y !== undefined) {
      result = new Date(Date.UTC(+y, +m - 1, +d)); exact = true;
      if (result.getUTCFullYear() !== +y || result.getUTCMonth() !== +m - 1 || result.getUTCDate() !== +d) return unknown;
    } else {
      result = new Date(ref);
      if (/^(today|heute|yesterday|gestern)$/.test(s)) result.setUTCDate(result.getUTCDate() - (/yesterday|gestern/.test(s) ? 1 : 0));
      else {
        match = s.match(/^(a|an|\d+) (day|week|month|year)s? ago$/) || s.match(/^vor (einem|einer|ein|\d+) (tag(?:en|e)?|woche[n]?|monat(?:en|e)?|jahr(?:en|e)?)$/);
        if (!match) return unknown;
        const count = /^\d+$/.test(match[1]) ? +match[1] : 1;
        const unit = match[2];
        if (/^(month|monat|year|jahr)/.test(unit)) {
          const offset = count * (/^(year|jahr)/.test(unit) ? 12 : 1);
          result.setUTCDate(1); result.setUTCMonth(result.getUTCMonth() - offset);
          const end = new Date(result); end.setUTCMonth(end.getUTCMonth() + 1); end.setUTCDate(0);
          result.setUTCDate(Math.min(ref.getUTCDate(), end.getUTCDate()));
        } else result.setUTCDate(result.getUTCDate() - count * (/^(week|woche)/.test(unit) ? 7 : 1));
      }
    }
    return Number.isFinite(+result) && result <= ref && result.getUTCFullYear() >= 1000
      ? {date_estimate: iso(result), date_is_exact: exact} : unknown;
  };
  R.moreButtons = card => [...card.querySelectorAll('button')].filter(b =>
    !b.closest('.owner-response, .CDe7pd') && /^(more|see more|read more|mehr|mehr anzeigen|weiterlesen)$/i.test((b.textContent || b.getAttribute('aria-label') || '').trim()));
  R.restaurant = (doc = document) => (doc.querySelector('h1.DUwDvf, [role="main"] h1, h1')?.textContent || '').trim();
  R.snapshot = (card, context) => {
    const label = card.querySelector(R.selectors.rating)?.getAttribute('aria-label') || '';
    const match = label.trim().match(/^([1-5])(?:[.,]0)?\s*(?:out of 5\s*|von 5\s*)?(?:stars?|sterne?n?)\b/i);
    if (!match || R.moreButtons(card).length) return null;
    const textNode = [...card.querySelectorAll(R.selectors.text)].find(n => !n.closest('.owner-response, .CDe7pd'));
    // textContent works on detached virtualized nodes too. Preserve displayed date verbatim.
    const copy = textNode?.cloneNode(true);
    copy?.querySelectorAll('br').forEach(n => n.replaceWith('\n'));
    const text = copy?.textContent.trim() || '';
    if (/[.…]{1,3}$/.test(text) && card.querySelector('button.w8nwRe[aria-expanded="false"]')) return null;
    const date_raw = card.querySelector(R.selectors.date)?.textContent || '';
    const nativeId = card.getAttribute('data-review-id') || card.querySelector('[data-review-id]')?.getAttribute('data-review-id');
    return {...context, review_id: nativeId ? `google_maps:native:${nativeId}` : null,
      rating: +match[1], text, date_raw, ...R.parseDate(date_raw), scraped_at: new Date().toISOString()};
  };
  R.identify = async record => {
    if (record.review_id) return record;
    const payload = [record.restaurant_url, record.rating, record.text.normalize('NFC').replace(/\s+/g, ' '), record.date_raw];
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(payload)));
    return {...record, review_id: 'google_maps:fallback:' + [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('')};
  };
  R.findPanel = (doc = document) => {
    // Previews alone aren't enough: require the selected Reviews tab or review sort UI.
    const tabs = [...doc.querySelectorAll('[role="tab"][aria-selected="true"]')];
    const selected = tabs.some(t => /reviews|rezensionen|bewertungen/i.test(t.textContent + ' ' + t.getAttribute('aria-label')));
    const sort = [...doc.querySelectorAll('button')].some(b => /^(sort(?: reviews)?|sortieren|rezensionen sortieren)$/i.test((b.getAttribute('aria-label') || b.textContent).trim()));
    const feed = doc.querySelector('[role="feed"][aria-label*="review" i], [role="feed"][aria-label*="rezension" i]');
    if (!selected && !sort && !feed) return null;
    for (const card of doc.querySelectorAll(R.selectors.card)) {
      for (let n = card.parentElement; n && n !== doc.body && n !== doc.documentElement; n = n.parentElement) {
        if (/(auto|scroll)/.test(getComputedStyle(n).overflowY) && n.clientHeight > 0) return n;
      }
    }
    return null;
  };
  R.restriction = (doc = document) => {
    const visible = n => n.getClientRects().length > 0;
    if ([...doc.querySelectorAll('#captcha-form, #recaptcha, .g-recaptcha, iframe[src*="recaptcha"], iframe[src*="captcha"]')].some(visible)) return 'captcha';
    // Ignore review text, so a review mentioning a CAPTCHA cannot stop the run.
    const copy = doc.body.cloneNode(true);
    copy.querySelectorAll(`${R.selectors.card}, script, style`).forEach(n => n.remove());
    const text = copy.textContent;
    if (/unusual traffic|ungewöhnlichen datenverkehr|automated queries|access denied|zugriff verweigert/i.test(text)) return 'access_restricted';
    if (/die ansicht ist beschränkt|limited view of google maps|using a limited view|seeing a limited view/i.test(text)) return 'restricted_view';
    if (/this browser or app may not be secure|dieser browser oder diese app ist.*nicht sicher/i.test(text)) return 'browser_security_block';
    if ([...doc.querySelectorAll('[role="dialog"]')].filter(visible).some(n => /sign in|anmelden|before you continue|bevor sie.*google/i.test(n.textContent))) return 'access_dialog';
    return null;
  };
})();
