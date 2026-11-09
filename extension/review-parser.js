(() => {
  const R = globalThis.RRI = globalThis.RRI || {};
  R.version = '0.1.7';
  R.selectors = {
    card: '.jftiEf, [role="article"][data-review-id], div[data-review-id]',
    text: '.wiI7pd, [data-review-text]',
    date: '.rsqaWe, [data-review-date]',
    rating: '.kvMYJc[aria-label], [role="img"][aria-label*="star" i], [role="img"][aria-label*="stern" i], [role="img"][aria-label*="зв" i]'
  };
  const months = [
    'january jan januar январь января', 'february feb februar февраль февраля', 'march mar märz mär март марта', 'april apr апрель апреля',
    'may mai май мая', 'june jun juni июнь июня', 'july jul juli июль июля', 'august aug август августа', 'september sep sept сентябрь сентября',
    'october oct oktober okt октябрь октября', 'november nov ноябрь ноября', 'december dec dezember dez декабрь декабря'
  ];
  const iso = d => d.toISOString().slice(0, 10);
  R.parseDate = (raw, now = new Date()) => {
    const unknown = {date_estimate: null, date_is_exact: false};
    // Relative labels use the browser's local calendar day, independent of UTC scrape time.
    const ref = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    let s = raw.toLocaleLowerCase().replace(/\s+/g, ' ').trim();
    // Translate only recognized complete date labels for shared calendar math.
    // The record still stores the untouched Russian/English/German DOM string.
    const ru = s.match(/^(?:(\d+|один|одна|одну|одно) )?(день|дня|дней|недел(?:ю|я|и|ь)|месяц(?:а|ев)?|год|года|лет) назад$/);
    if (ru) {
      const count = /^\d+$/.test(ru[1] || '') ? ru[1] : '1';
      const unit = /^(год|года|лет)$/.test(ru[2]) ? 'year' : ru[2].startsWith('месяц') ? 'month' : ru[2].startsWith('недел') ? 'week' : 'day';
      s = `${count} ${unit} ago`;
    } else if (s === 'сегодня' || s === 'вчера') s = s === 'сегодня' ? 'today' : 'yesterday';
    let y, m, d, match, result, exact = false;
    if ((match = s.match(/^(\d{4})-(\d{2})-(\d{2})$/))) [, y, m, d] = match;
    else if ((match = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/))) [, d, m, y] = match;
    else if ((match = s.match(/^(\d{1,2})\.? ([a-zäöüа-яё]+)\.? (\d{4})(?:\s*г\.?)?$/))) {
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
  R.reviewTextNode = card => [...card.querySelectorAll(R.selectors.text)].find(n => !n.closest('.owner-response, .CDe7pd'));
  R.nativeReviewId = card => card.getAttribute('data-review-id') || card.querySelector('[data-review-id]')?.getAttribute('data-review-id') || null;
  R.moreButtons = card => {
    const text = R.reviewTextNode(card);
    if (!text) return [];
    return [...card.querySelectorAll('button, [role="button"]')].filter(b => {
      if (b.closest('.owner-response, .CDe7pd') || b.getAttribute('aria-expanded') === 'true') return false;
      const more = [b.textContent, b.getAttribute('aria-label')].some(value =>
        /^(?:more|see more|read more|show more|read full review|mehr|mehr anzeigen|weiterlesen|ещ[её]|читать дальше|показать полностью|подробнее)(?:\s*(?:…|\.\.\.))?$/i.test((value || '').trim()));
      if (!more) return false;
      if (text.contains(b) || (text.id && b.getAttribute('aria-controls') === text.id)) return true;
      // Text-expansion controls share the review-body branch. More buttons in
      // price/service metadata or owner replies must not block the body export.
      if (b.parentElement === card) return b.previousElementSibling === text;
      for (let branch = b.parentElement, depth = 0; branch && branch !== card && depth < 3; branch = branch.parentElement, depth++) {
        if (branch.contains(text)) return true;
      }
      return false;
    });
  };
  R.visible = node => !!node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
  const label = node => (node.getAttribute('aria-label') || node.textContent || '').replace(/\s+/g, ' ').trim();
  const reviewLabel = /reviews|rezensionen|bewertungen|отзыв/i;
  const genericHeading = /^(reviews|rezensionen|bewertungen|overview|übersicht|отзывы|все отзывы|обзор)$/i;
  const moreReviews = /^(?:(?:more|see all|all|additional) reviews|(?:weitere|mehr|alle) (?:rezensionen|bewertungen)|(?:ещ[её]|все|другие|больше|показать все) отзывы)(?:\s*\([\d.,\s]+\))?$/i;
  const allReviews = /^(?:all reviews|alle (?:rezensionen|bewertungen)|все отзывы)(?:\s*\([\d.,\s]+\))?$/i;
  const sortReviews = /^(sort(?: reviews)?|sortieren|rezensionen sortieren|сортировать(?: отзывы)?|сортировка(?: отзывов)?|упорядочить)$/i;
  R.endOfReviews = text => /no more reviews|keine weiteren rezensionen|you.ve reached the end|ende der liste|больше нет отзывов|других отзывов нет|вы просмотрели все отзывы|вы достигли конца списка/i.test(text);
  const normalize = value => value.normalize('NFC').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
  R.reviewOpener = (doc = document, {ignoreAllReviews = false} = {}) => [...doc.querySelectorAll('button, [role="button"], a')].find(n =>
    R.visible(n) && !n.closest(R.selectors.card) && moreReviews.test(label(n)) &&
    !(allReviews.test(label(n)) && (typeof ignoreAllReviews === 'function' ? ignoreAllReviews(n) : ignoreAllReviews)));
  R.reviewEntry = (doc = document) => {
    const enabled = n => R.visible(n) && !n.disabled && n.getAttribute('aria-disabled') !== 'true' && !n.closest(R.selectors.card);
    const tabs = [...doc.querySelectorAll('[role="tab"]')].filter(n => enabled(n) && reviewLabel.test(label(n)));
    const tab = tabs.find(n => n.getAttribute('aria-selected') !== 'true') || tabs[0];
    if (tab) return {node: tab, kind: 'reviews_tab'};
    const more = R.reviewOpener(doc); if (more && enabled(more)) return {node: more, kind: 'more_reviews'};
    const count = [...doc.querySelectorAll('button, [role="button"]')].find(n => enabled(n) &&
      /^(?:[\d.,\s]+\s+(?:reviews|rezensionen|bewertungen|отзыв(?:а|ов)?)|(?:reviews|rezensionen|bewertungen|отзывов|отзывы):?\s*[\d.,\s]+)$/i.test(label(n)));
    return count ? {node: count, kind: 'review_count'} : null;
  };
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
      const match = (dialog.getAttribute('aria-label') || '').match(/^(?:reviews (?:for|of)|(?:rezensionen|bewertungen) (?:für|zu)|отзывы (?:о месте|о|на))\s+(.+)$/i);
      if (match) return {name: match[1].trim().replace(/^["«“](.*)["»”]$/, '$1'), source: 'reviews_label'};
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
    const match = label.trim().match(/^([1-5])(?:[.,]0)?\s*(?:out of 5\s*|von 5\s*|из 5\s*)?(?:stars?|sterne?n?|зв[её]зд(?:а|ы)?)(?=$|\s)/i);
    if (!match || R.moreButtons(card).length) return null;
    const textNode = R.reviewTextNode(card);
    // textContent works on detached virtualized nodes too. Preserve displayed date verbatim.
    const copy = textNode?.cloneNode(true);
    copy?.querySelectorAll('button, [role="button"]').forEach(n => n.remove());
    copy?.querySelectorAll('br').forEach(n => n.replaceWith('\n'));
    const text = copy?.textContent.trim() || '';
    const date_raw = card.querySelector(R.selectors.date)?.textContent || '';
    const nativeId = R.nativeReviewId(card);
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
    const selectedTab = [...doc.querySelectorAll('[role="tab"][aria-selected="true"]')].find(n => R.visible(n) && reviewLabel.test(label(n)));
    const route = R.placeRoute();
    // All reviews / Alle Rezensionen / Все отзывы can be an overview entry or
    // a filter in the opened list. An active tab, review route, or sort control
    // provides context; its caption alone cannot turn that list into a preview.
    const filterContext = !!selectedTab || route.review_route_hint || controls.some(n => sortReviews.test(label(n)));
    const isListFilter = node => {
      if (!filterContext) return false;
      if (node.matches('[role="radio"], [role="option"], [aria-pressed]')) return true;
      for (let scope = node.parentElement; scope && scope !== doc.body && scope !== doc.documentElement; scope = scope.parentElement) {
        if (!/(auto|scroll)/.test(getComputedStyle(scope).overflowY) || !scope.clientHeight) continue;
        const hasVisible = selector => [...scope.querySelectorAll(selector)].some(n => R.visible(n) && !n.closest(R.selectors.card));
        if (hasVisible('[data-item-id="address"], [data-item-id^="phone"], [data-item-id="authority"]')) return false;
        return !!(route.review_route_hint && selectedTab) || !hasVisible('h1.DUwDvf, [role="tab"]');
      }
      return false;
    };
    const previewControl = root => R.reviewOpener(root, {ignoreAllReviews: isListFilter});
    const previewOpener = previewControl(doc);
    for (const dialog of doc.querySelectorAll('[role="dialog"]')) {
      const heading = [...dialog.querySelectorAll('h1, h2, [role="heading"]')].some(n => genericHeading.test(label(n)) && reviewLabel.test(label(n)));
      if (reviewLabel.test(dialog.getAttribute('aria-label') || '') || heading || hasSort(dialog)) add(dialog, 500, 'reviews_dialog');
    }
    for (const root of doc.querySelectorAll('[role="feed"], [role="region"], [role="main"]')) {
      if (reviewLabel.test(root.getAttribute('aria-label') || '') && !previewControl(root) &&
        (!previewOpener || hasSort(root) || root.closest('[role="dialog"]'))) add(root, 350, 'labelled_reviews_panel');
    }
    // Scope generic sort controls to their own branch, rather than using a global
    // signal to bless the first preview cards elsewhere in the sidebar.
    for (const button of controls.filter(n => sortReviews.test(label(n)))) {
      for (let root = button.parentElement; root && root !== doc.body; root = root.parentElement) {
        if (R.cards(root).length) { if (!previewControl(root)) add(root, 200, 'scoped_review_sort'); break; }
      }
    }
    if (selectedTab) {
      const root = selectedTab.closest('[role="main"], [role="dialog"]') || selectedTab.parentElement?.parentElement;
      if (root && !previewControl(root)) add(root, 100, 'selected_reviews_tab');
    }
    // Some full-list layouts have neither a labelled feed/dialog nor a selected
    // Reviews tab. Inspect actual scroll ancestors independently of those labels.
    // A route hint PLUS a dedicated review-only scroller is required: card count
    // alone never authorizes collection, and no total-review match is required.
    const facts = new Map();
    const containerFacts = node => {
      if (facts.has(node)) return facts.get(node);
      const outsideCards = selector => [...node.querySelectorAll(selector)].some(n => R.visible(n) && !n.closest(R.selectors.card));
      const opener = previewControl(node);
      const result = {
        heading_inside: outsideCards('h1.DUwDvf'),
        tabs_inside: outsideCards('[role="tab"]'),
        business_details_inside: outsideCards('[data-item-id="address"], [data-item-id^="phone"], [data-item-id="authority"]'),
        opener_inside: !!opener,
        opener_kind: opener ? (allReviews.test(label(opener)) ? 'all_reviews_entry' : 'more_reviews_entry') : null,
        ignored_all_reviews_filters: controls.filter(n => node.contains(n) && !n.closest(R.selectors.card) && allReviews.test(label(n)) && isListFilter(n)).length,
        confirmed_reviews_tab: !!selectedTab && !!selectedTab.closest('[role="main"], [role="dialog"]')?.contains(node),
        opener_in_shared_main: !!previewOpener && !!node.closest('[role="main"]') &&
          previewOpener.closest('[role="main"]') === node.closest('[role="main"]')
      };
      // The supplied co:Lab log proves the same-place Reviews tab and route are
      // active, with a dedicated ten-card scroller lacking overview content.
      // A residual entry/pagination button inside that verified list must not
      // override those positive signals. Ordinary previews retain their veto.
      result.verified_dedicated_list = result.confirmed_reviews_tab && route.review_route_hint &&
        !result.heading_inside && !result.tabs_inside && !result.business_details_inside;
      result.opener_ignored_in_verified_list = result.opener_inside && result.verified_dedicated_list;
      // Only local, visible overview content disqualifies a scroller. Sharing
      // <main> with an opener, retaining a title/tab strip, or containing hidden
      // overview nodes does not establish that this is the preview container.
      result.blocker = node === doc.scrollingElement ? 'document_scroller'
        : result.business_details_inside && !result.confirmed_reviews_tab ? 'business_details_in_scroller'
        : result.opener_inside && !result.verified_dedicated_list ? 'preview_opener_in_scroller' : '';
      facts.set(node, result); return result;
    };
    const scrollers = new Set();
    for (const card of R.cards(doc)) {
      for (let node = card.parentElement; node && node !== doc.body && node !== doc.documentElement; node = node.parentElement) {
        if (/(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.clientHeight > 0) { scrollers.add(node); break; }
      }
    }
    const scroll_candidates = [...scrollers].map(node => {
      const count = R.cards(node).length;
      const local = containerFacts(node);
      const rejected = local.blocker || (!route.review_route_hint ? 'no_active_reviews_route_hint'
        : node.scrollHeight <= node.clientHeight + 4 ? 'not_scrollable_yet' : '');
      if (!rejected) add(node, 150, 'reviews_route_scroller');
      return {tag: node.tagName.toLowerCase(), role: node.getAttribute('role') || '', cards: count,
        client_height: node.clientHeight, scroll_height: node.scrollHeight, scroll_top: node.scrollTop,
        ...local, rejection: rejected || null};
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
            (node.getAttribute('role') === 'main' && !route.review_route_hint && !containerFacts(node).confirmed_reviews_tab)) break;
          if (/(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.clientHeight > 0 &&
            !containerFacts(node).blocker && (route.review_route_hint || containerFacts(node).confirmed_reviews_tab ||
              (!containerFacts(node).heading_inside && !containerFacts(node).tabs_inside))) {
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
  R.diagnostics = (detection = R.inspect()) => ({extension_version: R.version, current_url: location.href, restaurant_name: R.restaurant(),
    content_script_version: R.contentVersion || null,
    page_language: document.documentElement.lang || 'unknown', supported_languages: ['en', 'de', 'ru'],
    restaurant_name_source: R.restaurantInfo().source, review_route_hint: detection.review_route_hint,
    mode: detection.mode, detected_review_cards: detection.detected_review_cards, full_review_cards: detection.full_review_cards,
    scrollable_found: !!detection.panel, panel_evidence: detection.evidence, scroll_candidates: detection.scroll_candidates,
    loading_scope: 'Currently rendered reviews; more may load on scroll. No total-count match required.'});
  R.waitForPanel = (check, timeoutMs) => new Promise((resolve, reject) => {
    let observer, timer, poll, done = false;
    const finish = (value, error) => { if (done) return; done = true; observer?.disconnect(); clearTimeout(timer); clearInterval(poll); error ? reject(error) : resolve(value); };
    const inspect = () => { try { const result = check(); if (result) finish(result); } catch (error) { finish(null, error); } };
    observer = new MutationObserver(inspect);
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
    timer = setTimeout(() => { const error = new Error('Full Reviews / Rezensionen / Отзывы panel was not ready. Open More reviews / Weitere Rezensionen / Ещё отзывы and retry.'); error.code = 'full_panel_not_ready'; finish(null, error); }, timeoutMs);
    poll = setInterval(inspect, 250);
    inspect();
  });
  R.restriction = (doc = document) => {
    const visible = n => n.getClientRects().length > 0;
    if ([...doc.querySelectorAll('#captcha-form, #recaptcha, .g-recaptcha, iframe[src*="recaptcha"], iframe[src*="captcha"]')].some(visible)) return 'captcha';
    // Ignore review text, so a review mentioning a CAPTCHA cannot stop the run.
    const copy = doc.body.cloneNode(true);
    copy.querySelectorAll(`${R.selectors.card}, script, style`).forEach(n => n.remove());
    const text = copy.textContent;
    if (/unusual traffic|ungewöhnlichen datenverkehr|automated queries|access denied|zugriff verweigert|необычный трафик|подозрительный трафик|автоматические запросы|доступ запрещ[её]н/i.test(text)) return 'access_restricted';
    if (/die ansicht ist beschränkt|limited view of google maps|using a limited view|seeing a limited view|ограниченная версия google карт/i.test(text)) return 'restricted_view';
    if (/this browser or app may not be secure|dieser browser oder diese app ist.*nicht sicher|этот браузер или приложение.*небезопас/i.test(text)) return 'browser_security_block';
    if ([...doc.querySelectorAll('[role="dialog"]')].filter(visible).some(n =>
      !R.cards(n).length && /sign in|anmelden|before you continue|bevor sie.*google|войдите в аккаунт|войти|прежде чем перейти к google/i.test(n.textContent))) return 'access_dialog';
    return null;
  };
})();
