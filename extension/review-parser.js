(() => {
  const R = globalThis.RRI = globalThis.RRI || {};
  R.selectors = {
    card: '.jftiEf, [role="article"][data-review-id], div[data-review-id]',
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
  R.visible = node => !!node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
  const label = node => (node.getAttribute('aria-label') || node.textContent || '').replace(/\s+/g, ' ').trim();
  const reviewLabel = /reviews|rezensionen|bewertungen/i;
  const genericHeading = /^(reviews|rezensionen|bewertungen|overview|übersicht)$/i;
  const moreReviews = /^(?:(?:more|see all|all|additional) reviews|(?:weitere|mehr|alle) (?:rezensionen|bewertungen))(?:\s*\([\d.,\s]+\))?$/i;
  const sortReviews = /^(sort(?: reviews)?|sortieren|rezensionen sortieren)$/i;
  const normalize = value => value.normalize('NFC').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
  R.reviewOpener = (doc = document) => [...doc.querySelectorAll('button, [role="button"], a')].find(n =>
    R.visible(n) && !n.closest(R.selectors.card) && moreReviews.test(label(n)));
  R.cards = root => [...root.querySelectorAll(R.selectors.card)].filter(n => {
    const parent = n.parentElement?.closest(R.selectors.card);
    return R.visible(n) && n.querySelector(R.selectors.rating) && (!parent || !root.contains(parent));
  });
  R.placeRoute = (href = location.href) => {
    const url = new URL(href);
    const place = url.pathname.match(/\/maps\/place\/([^/]+)/);
    let name = ''; try { name = place ? decodeURIComponent(place[1].replaceAll('+', ' ')) : ''; } catch { /* invalid escape */ }
    // A Maps URL may retain earlier businesses before the active place block.
    // The supplied Asia Imbiss Le URL contains McDonald's first, then Asia Imbiss Le.
    const placeBlocks = [...url.pathname.matchAll(/!1s(0x[\da-f]+:0x[\da-f]+|ChI[^!/?]+)/gi)];
    const active = placeBlocks.at(-1);
    const data = active ? url.pathname.slice(active.index) : url.pathname;
    const keys = {
      place_id: url.searchParams.get('query_place_id') || data.match(/!1s(ChI[^!/?]+)/)?.[1] || '',
      cid: url.searchParams.get('cid') || '',
      feature: data.match(/!1s(0x[\da-f]+:0x[\da-f]+)/i)?.[1] || '',
      entity: [...data.matchAll(/!16s([^!/?]+)/g)].at(-1)?.[1] || ''
    };
    // Observed route evidence, not a backend request or a completeness claim.
    const review_route_hint = !!place && /!9m1!1b1(?:!|$)/.test(data);
    return {name, slug: normalize(name), keys, review_route_hint};
  };
  R.restaurantInfo = (doc = document) => {
    // Full-dialog titles can replace the place heading with just "Reviews".
    for (const dialog of doc.querySelectorAll('[role="dialog"], [role="region"][aria-label]')) {
      if (!R.visible(dialog)) continue;
      const match = (dialog.getAttribute('aria-label') || '').match(/^(?:reviews (?:for|of)|(?:rezensionen|bewertungen) (?:für|zu))\s+(.+)$/i);
      if (match) return {name: match[1].trim(), source: 'reviews_label'};
      if (dialog.getAttribute('role') === 'dialog') {
        const heading = [...dialog.querySelectorAll('h1, h2')].find(n => !n.closest(R.selectors.card) && R.visible(n) && n.textContent.trim() && !genericHeading.test(n.textContent.trim()));
        if (heading) return {name: heading.textContent.trim(), source: 'heading'};
      }
    }
    for (const selector of ['h1.DUwDvf', '[role="main"] h1', '[role="dialog"] h1', 'h1']) {
      const node = [...doc.querySelectorAll(selector)].find(n => !n.closest(R.selectors.card) && R.visible(n) && n.textContent.trim() && !genericHeading.test(n.textContent.trim()));
      if (node) return {name: node.textContent.trim(), source: 'heading'};
    }
    const name = R.placeRoute().name;
    return {name, source: name ? 'url_path' : 'unavailable'};
  };
  R.restaurant = (doc = document) => R.restaurantInfo(doc).name;
  R.identity = (doc = document, href = location.href) => {
    const route = R.placeRoute(href), restaurant = R.restaurantInfo(doc);
    return {...route, name: restaurant.source === 'url_path' ? route.name : restaurant.name, name_source: restaurant.source};
  };
  R.sameRestaurant = (expected, current = R.identity()) => {
    // Compare identifiers only within the same namespace. Opening reviews can
    // drop some route tokens; a feature ID and an entity ID aren't comparable.
    const shared = Object.keys(expected.keys).filter(key => expected.keys[key] && current.keys[key]);
    if (shared.some(key => expected.keys[key] !== current.keys[key])) return 'different';
    if (!shared.length && expected.slug && current.slug && expected.slug !== current.slug) return 'different';
    if (expected.name_source !== 'url_path' && current.name_source !== 'url_path' &&
      expected.name && current.name && normalize(expected.name) !== normalize(current.name)) return 'different';
    if (shared.length || (expected.slug && expected.slug === current.slug) ||
      (expected.name && current.name && normalize(expected.name) === normalize(current.name))) return 'same';
    return 'unknown';
  };
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
  R.inspect = (doc = document) => {
    const candidates = [];
    const add = (root, score, evidence) => { if (root && R.visible(root)) candidates.push({root, score, evidence}); };
    const controls = [...doc.querySelectorAll('button, [role="button"]')].filter(R.visible);
    const hasSort = root => controls.some(n => root.contains(n) && sortReviews.test(label(n)));
    const previewOpener = R.reviewOpener(doc);
    const selectedTab = [...doc.querySelectorAll('[role="tab"][aria-selected="true"]')].find(n => R.visible(n) && reviewLabel.test(label(n)));
    for (const dialog of doc.querySelectorAll('[role="dialog"]')) {
      const heading = [...dialog.querySelectorAll('h1, h2, [role="heading"]')].some(n => genericHeading.test(label(n)) && reviewLabel.test(label(n)));
      if (reviewLabel.test(dialog.getAttribute('aria-label') || '') || heading || hasSort(dialog)) add(dialog, 500, 'reviews_dialog');
    }
    for (const root of doc.querySelectorAll('[role="feed"], [role="region"], [role="main"]')) {
      if (reviewLabel.test(root.getAttribute('aria-label') || '') && !R.reviewOpener(root) &&
        (!previewOpener || hasSort(root) || root.closest('[role="dialog"]'))) add(root, 350, 'labelled_reviews_panel');
    }
    // Scope generic sort controls to their own branch, rather than using a global
    // signal to bless the first preview cards elsewhere in the sidebar.
    for (const button of controls.filter(n => sortReviews.test(label(n)))) {
      for (let root = button.parentElement; root && root !== doc.body; root = root.parentElement) {
        if (R.cards(root).length) { if (!R.reviewOpener(root)) add(root, 200, 'scoped_review_sort'); break; }
      }
    }
    if (selectedTab) {
      const root = selectedTab.closest('[role="main"], [role="dialog"]') || selectedTab.parentElement?.parentElement;
      if (root && !R.reviewOpener(root)) add(root, 100, 'selected_reviews_tab');
    }
    // Some full-list layouts have neither a labelled feed/dialog nor a selected
    // Reviews tab. Inspect actual scroll ancestors independently of those labels.
    // A route hint PLUS a dedicated review-only scroller is required: card count
    // alone never authorizes collection, and no total-review match is required.
    const route = R.placeRoute();
    const scrollers = new Set();
    for (const card of R.cards(doc)) {
      for (let node = card.parentElement; node && node !== doc.body && node !== doc.documentElement; node = node.parentElement) {
        if (/(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.clientHeight > 0) { scrollers.add(node); break; }
      }
    }
    const scroll_candidates = [...scrollers].map(node => {
      const count = R.cards(node).length;
      const overview = !!node.querySelector('h1.DUwDvf, [role="tab"], [data-item-id="address"], [data-item-id^="phone"], [data-item-id="authority"]');
      const previewBranch = !!previewOpener && previewOpener.closest('[role="main"]') === node.closest('[role="main"]') &&
        !!node.closest('[role="main"]');
      const rejected = node === doc.scrollingElement ? 'document_scroller' : overview || R.reviewOpener(node) || previewBranch
        ? 'overview_or_preview_container' : !route.review_route_hint ? 'no_active_reviews_route_hint'
        : node.scrollHeight <= node.clientHeight + 4 ? 'not_scrollable_yet' : '';
      if (!rejected) add(node, 150, 'reviews_route_scroller');
      return {tag: node.tagName.toLowerCase(), role: node.getAttribute('role') || '', cards: count,
        client_height: node.clientHeight, scroll_height: node.scrollHeight, rejection: rejected || null};
    });
    candidates.sort((a, b) => b.score - a.score);
    // A visible active dialog takes precedence even while its cards are loading.
    const activeDialog = candidates.find(c => c.evidence === 'reviews_dialog');
    const scoped = activeDialog ? candidates.filter(c => activeDialog.root.contains(c.root)) : candidates;
    let chosen = scoped[0], panel = null;
    for (const candidate of scoped) {
      for (const card of R.cards(candidate.root)) {
        for (let node = card.parentElement; node && candidate.root.contains(node); node = node.parentElement) {
          if (node === doc.body || node === doc.documentElement ||
            (node.getAttribute('role') === 'main' && candidate.evidence !== 'reviews_route_scroller')) break;
          if (/(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.clientHeight > 0 &&
            !R.reviewOpener(node) && !node.querySelector('h1.DUwDvf') &&
            !node.querySelector('[role="tab"][aria-selected="true"]')) {
            panel = node; chosen = candidate; break;
          }
          if (node === candidate.root) break;
        }
        if (panel) break;
      }
      if (panel) break;
    }
    const cards = R.cards(doc);
    return {mode: chosen ? 'FULL_REVIEWS_MODE' : (cards.length || R.reviewOpener(doc) ? 'PREVIEW_MODE' : 'NOT_READY'),
      panel, root: chosen?.root || null, evidence: chosen?.evidence || 'no_full_reviews_interface',
      detected_review_cards: cards.length, full_review_cards: panel ? R.cards(panel).length : 0,
      scroll_candidates, review_route_hint: route.review_route_hint};
  };
  R.findPanel = (doc = document) => R.inspect(doc).panel;
  R.diagnostics = (detection = R.inspect()) => ({current_url: location.href, restaurant_name: R.restaurant(),
    restaurant_name_source: R.restaurantInfo().source, review_route_hint: detection.review_route_hint,
    mode: detection.mode, detected_review_cards: detection.detected_review_cards, full_review_cards: detection.full_review_cards,
    scrollable_found: !!detection.panel, panel_evidence: detection.evidence, scroll_candidates: detection.scroll_candidates,
    loading_scope: 'Currently rendered reviews; more may load on scroll. No total-count match required.'});
  R.waitForPanel = (check, timeoutMs) => new Promise((resolve, reject) => {
    let observer, timer, done = false;
    const finish = (value, error) => { if (done) return; done = true; observer?.disconnect(); clearTimeout(timer); error ? reject(error) : resolve(value); };
    const inspect = () => { try { const result = check(); if (result) finish(result); } catch (error) { finish(null, error); } };
    observer = new MutationObserver(inspect);
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
    timer = setTimeout(() => { const error = new Error('Full Reviews / Rezensionen panel was not ready. Open More reviews / Weitere Rezensionen and retry.'); error.code = 'full_panel_not_ready'; finish(null, error); }, timeoutMs);
    inspect();
  });
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
    if ([...doc.querySelectorAll('[role="dialog"]')].filter(visible).some(n =>
      !R.cards(n).length && /sign in|anmelden|before you continue|bevor sie.*google/i.test(n.textContent))) return 'access_dialog';
    return null;
  };
})();
