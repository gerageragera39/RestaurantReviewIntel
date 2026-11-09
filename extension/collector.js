(() => {
  const R = globalThis.RRI;
  class Collector {
    constructor(storage = chrome.storage.local) {
      this.storage = storage; this.records = new Map(); this.queue = Promise.resolve(); this.state = 'idle';
      this.pending = new Set(); this.attempted = new WeakSet(); this.observed = 0;
      this.events = []; this.eventSequence = 0; this.eventsDropped = 0; this.logQueue = Promise.resolve();
      this.parseRejected = 0; this.rejectedNodes = new WeakSet();
    }
    trace(event, details = {}) {
      const entry = {sequence: ++this.eventSequence, at: new Date().toISOString(), elapsed_ms: Date.now() - this.started, event, details};
      this.events.push(entry);
      if (this.events.length > 300) { this.events.splice(20, this.events.length - 300); this.eventsDropped++; }
      console.info('[RRI]', entry);
      if (this.logKey && !this.logTimer) this.logTimer = setTimeout(() => this.flushLog(), 250);
    }
    logReport() {
      return {schema_version: 1, extension_version: R.version, run_id: this.runId, events_dropped: this.eventsDropped,
        events: this.events.slice(), state: this.state, stopping_reason: this.reason || '',
        diagnostics: this.status().diagnostics};
    }
    flushLog() {
      clearTimeout(this.logTimer); this.logTimer = null;
      if (!this.logKey) return this.logQueue;
      const report = this.logReport();
      this.logQueue = this.logQueue.then(() => this.storage.set({[this.logKey]: report})).catch(() => { this.logWriteFailed = true; });
      return this.logQueue;
    }
    async start({runId, tabId, limit = 30, autoScroll = true, waitMs = 1500, maxIdle = 8, maxScrolls = 1000, maxMs = 1800000, panelWaitMs = 10000, scrollOnStart = false}) {
      if (['waiting_for_reviews', 'running', 'paused', 'stopping'].includes(this.state)) throw new Error('A collection is already active.');
      if (!Number.isInteger(limit) || limit < 0) throw new Error('Limit must be a nonnegative integer.');
      this.identity = R.identity();
      const name = this.identity.name || this.identity.slug;
      this.options = {limit, autoScroll, waitMs, maxIdle, maxScrolls, maxMs, panelWaitMs, scrollOnStart};
      this.context = {restaurant_name: name, restaurant_url: location.href};
      this.runId = runId; this.tabId = tabId; this.state = 'waiting_for_reviews'; this.reason = '';
      this.startFailedPanelDetection = false; this.reacquisitions = 0;
      this.started = Date.now(); this.scrolls = 0; this.idle = 0; this.lastProgress = 0;
      this.metaKey = `rri:run:${runId}`; this.prefix = `rri:review:${runId}:`;
      this.logKey = `rri:log:${runId}`;
      this.trace('start_requested', {options: this.options, diagnostics: R.diagnostics()});
      await this.saveMeta();
      try {
        if (!name) { const error = new Error('Restaurant identity not detected.'); error.code = 'restaurant_identity_unverified'; throw error; }
        const blocked = R.restriction(); if (blocked) { const error = new Error(`Access restricted: ${blocked}`); error.code = blocked; throw error; }
        const detection = R.inspect();
        if (!detection.panel) {
          const entry = R.reviewEntry();
          if (!entry && !detection.review_route_hint) {
            this.trace('open_control_missing', {mode: detection.mode});
            const error = new Error('Preview reviews only. Open More reviews / Weitere Rezensionen / Ещё отзывы, then Start again.');
            error.code = 'full_panel_not_ready'; throw error;
          }
          // Only invoked following Start, using the ordinary visible Maps control.
          if (entry) {
            this.trace('open_control_found', {kind: entry.kind, tag: entry.node.tagName.toLowerCase(),
              role: entry.node.getAttribute('role'), selected_before: entry.node.getAttribute('aria-selected')});
            entry.node.click();
            this.trace('open_control_clicked', {kind: entry.kind, selected_after: entry.node.getAttribute('aria-selected')});
          } else this.trace('open_control_missing', {mode: detection.mode, waiting_on_active_route: true});
        }
        let previousDetection = '';
        this.trace('waiting_for_full_panel', {timeout_ms: panelWaitMs});
        const ready = await R.waitForPanel(() => {
          const blocked = R.restriction(); if (blocked) { const error = new Error(blocked); error.code = blocked; throw error; }
          if (R.sameRestaurant(this.identity) === 'different') { const error = new Error('Restaurant changed while opening reviews.'); error.code = 'page_changed'; throw error; }
          const found = R.inspect();
          const diagnostics = R.diagnostics(found);
          const signature = JSON.stringify(diagnostics);
          if (signature !== previousDetection) { this.trace('panel_detection', diagnostics); previousDetection = signature; }
          return R.sameRestaurant(this.identity) === 'same' && found.panel && found.full_review_cards ? found : null;
        }, panelWaitMs);
        this.panel = ready.panel; this.state = 'running';
        this.trace('panel_ready', R.diagnostics(ready));
      } catch (error) {
        this.state = 'stopped'; this.reason = error.code || 'start_failed';
        this.startFailedPanelDetection = this.reason === 'full_panel_not_ready';
        this.trace('start_failed', {reason: this.reason, diagnostics: this.status().diagnostics});
        await this.saveMeta(); await this.flushLog(); throw error;
      }
      this.observer = new MutationObserver(changes => {
        if (this.state !== 'running') return;
        const previous = this.panel;
        // Ignore unrelated map animation/account UI without rescanning the DOM.
        if (previous?.isConnected && changes.every(change => !previous.contains(change.target) &&
          !change.target.parentElement?.closest('h1, [role="heading"], [role="tab"]') &&
          ![...change.addedNodes, ...change.removedNodes].some(node => node.nodeType === 1 &&
            (node.matches('[role="dialog"], h1, [role="heading"]') || node.querySelector(R.selectors.card))))) return;
        this.refreshPanel();
        if (this.state !== 'running' || R.sameRestaurant(this.identity) !== 'same') return;
        // Read synchronously inside the callback, before awaiting persistence or hashing.
        for (const change of changes) {
          // Ignore preview mutations and all unrelated page/reviewer/account UI.
          const inPanel = this.panel.contains(change.target) || previous?.contains(change.target);
          if (!inPanel) continue;
          for (const node of [...change.addedNodes, ...change.removedNodes]) this.captureTree(node);
          this.captureTree(change.target);
        }
      });
      // Observe replacement as well as card mutations. Capture remains scoped to
      // the verified review panel, never the surrounding preview sidebar.
      this.observer.observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['data-review-id', 'aria-label', 'aria-expanded', 'aria-selected', 'hidden', 'style']});
      this.scan();
      this.timer = setInterval(() => this.tick().catch(e => this.fail(e)), waitMs);
      this.unload = () => { this.finish('page_unloaded'); };
      window.addEventListener('pagehide', this.unload, {once: true});
      await this.queue;
      this.trace('initial_collection', {unique: this.records.size, with_text: this.textCount(), unexpanded: this.pending.size, parse_rejected: this.parseRejected});
      if (autoScroll && scrollOnStart) { await this.tick(); await this.queue; }
      await this.flushLog();
      return this.status();
    }
    refreshPanel() {
      const blocked = R.restriction();
      const identity = R.sameRestaurant(this.identity);
      if (blocked || identity === 'different') { this.finish(blocked || 'page_changed').catch(e => this.fail(e)); return false; }
      const detection = R.inspect();
      if (identity !== 'same' || !detection.panel || !detection.full_review_cards) {
        if (this.panelMissingSince == null) this.trace('panel_temporarily_missing', {identity, diagnostics: R.diagnostics(detection)});
        this.panelMissingSince ??= Date.now();
        if (Date.now() - this.panelMissingSince >= this.options.panelWaitMs) {
          this.finish(identity === 'unknown' ? 'restaurant_identity_unverified' : 'review_panel_closed').catch(e => this.fail(e));
        }
        return false;
      }
      this.panelMissingSince = null;
      if (detection.panel !== this.panel) {
        this.panel = detection.panel; this.idle = 0; this.reacquisitions++;
        this.trace('panel_reacquired', this.status().diagnostics);
        this.scan();
      }
      return true;
    }
    captureTree(node) {
      if (this.state !== 'running') return;
      if (node.nodeType === 3) node = node.parentElement;
      if (!node || node.nodeType !== 1) return;
      const card = node.matches(R.selectors.card) ? node : node.closest(R.selectors.card);
      if (card) this.capture(card);
      node.querySelectorAll(R.selectors.card).forEach(c => this.capture(c));
    }
    scan() { R.cards(this.panel).forEach(c => this.capture(c)); }
    capture(card) {
      const more = R.moreButtons(card);
      if (more.length) {
        this.pending.add(card);
        if (card.isConnected && !this.attempted.has(card)) {
          this.attempted.add(card); more.forEach(b => b.click());
        }
      }
      const snapshot = R.snapshot(card, this.context);
      if (!snapshot) {
        if (!R.moreButtons(card).length && !this.rejectedNodes.has(card)) { this.rejectedNodes.add(card); this.parseRejected++; }
        return;
      }
      this.pending.delete(card);
      const signature = JSON.stringify([snapshot.review_id, snapshot.rating, snapshot.text, snapshot.date_raw]);
      this.signatures = this.signatures || new WeakMap();
      if (this.signatures.get(card) === signature) return;
      this.signatures.set(card, signature); this.observed++;
      this.queue = this.queue.then(async () => {
        const record = await R.identify(snapshot);
        const old = this.records.get(record.review_id);
        if (old && old.text.length >= record.text.length && (old.date_raw || !record.date_raw)) return;
        if (!old && this.options.limit && this.textCount() >= this.options.limit) return;
        // Each review is its own storage entry: never rewrite the entire dataset per scroll.
        const retained = old ? {...record, scraped_at: old.scraped_at} : record;
        await this.storage.set({[this.prefix + record.review_id]: retained});
        this.records.set(record.review_id, retained);
        await this.saveMeta();
      }).catch(e => this.fail(e));
    }
    textCount() { return [...this.records.values()].filter(r => r.text).length; }
    status() {
      const rows = [...this.records.values()];
      return {runId: this.runId, tabId: this.tabId, ...this.context, state: this.state, reason: this.reason,
        observed: this.observed, unique: rows.length, withText: this.textCount(), withDates: rows.filter(r => r.date_raw).length,
        unexpanded: this.pending.size, scrolls: this.scrolls, updated_at: new Date().toISOString(),
        diagnostics: {...R.diagnostics(), start_failed_panel_detection: !!this.startFailedPanelDetection,
          stopping_reason: this.reason || '', panel_reacquisitions: this.reacquisitions || 0,
          automatic_scrolling: this.options?.autoScroll ?? null, scroll_attempts: this.scrolls || 0,
          last_scroll: this.lastScroll || null,
          log_events: this.eventSequence, log_events_dropped: this.eventsDropped, log_write_failed: !!this.logWriteFailed,
          parse_rejected_cards: this.parseRejected,
          waiting_for_panel: this.state === 'waiting_for_reviews' || this.panelMissingSince != null},
        scope: 'Accessible displayed reviews only; completeness not established.'};
    }
    saveMeta() { return this.storage.set({[this.metaKey]: this.status()}); }
    async tick() {
      if (!['running', 'paused'].includes(this.state) || this.ticking) return;
      this.ticking = true;
      try {
        if (Date.now() - this.started >= this.options.maxMs) return await this.finish('time_budget');
        const blocked = R.restriction(); if (blocked) return await this.finish(blocked);
        if (R.sameRestaurant(this.identity) === 'different') return await this.finish('page_changed');
        if (this.state === 'paused') return;
        if (!this.refreshPanel()) { await this.saveMeta(); return; }
        const previousCount = this.records.size;
        this.scan(); await this.queue;
        if (this.records.size !== previousCount) this.trace('collection_progress', {unique: this.records.size, with_text: this.textCount(), parse_rejected: this.parseRejected});
        if (this.options.limit && this.textCount() >= this.options.limit) return await this.finish('text_limit');
        const progress = this.records.size;
        this.idle = progress === this.lastProgress ? this.idle + 1 : 0; this.lastProgress = progress;
        if (this.idle >= this.options.maxIdle) return await this.finish('no_progress');
        const content = this.panel.cloneNode(true); content.querySelectorAll(R.selectors.card).forEach(n => n.remove());
        if (R.endOfReviews(content.textContent)) return await this.finish('accessible_end');
        if (this.options.autoScroll) {
          if (this.scrolls >= this.options.maxScrolls) return await this.finish('scroll_budget');
          const before = this.panel.scrollTop;
          this.trace('scroll_requested', {attempt: this.scrolls + 1, before, client_height: this.panel.clientHeight, scroll_height: this.panel.scrollHeight});
          this.panel.scrollTop += Math.max(200, this.panel.clientHeight * 0.8);
          this.panel.dispatchEvent(new Event('scroll', {bubbles: true})); this.scrolls++;
          this.lastScroll = {before, after: this.panel.scrollTop, client_height: this.panel.clientHeight,
            scroll_height: this.panel.scrollHeight, moved: this.panel.scrollTop !== before};
          this.trace('scroll_result', this.lastScroll);
          this.scan();
        } else if (!this.manualModeLogged) { this.manualModeLogged = true; this.trace('manual_scrolling_enabled'); }
        await this.saveMeta();
      } finally { this.ticking = false; }
    }
    async pause() { if (this.state === 'running') { this.state = 'paused'; this.trace('paused'); await this.queue; await this.saveMeta(); await this.flushLog(); } return this.status(); }
    async resume() { if (this.state === 'paused') { this.state = 'running'; this.trace('resumed'); this.idle = 0; if (this.refreshPanel()) this.scan(); await this.saveMeta(); await this.flushLog(); } return this.status(); }
    async finish(reason = 'user_stop') {
      if (['stopped', 'error', 'stopping'].includes(this.state)) return this.status();
      this.state = 'stopping'; this.reason = reason; clearInterval(this.timer); this.observer?.disconnect();
      this.trace('collection_stopped', {reason, unique: this.records.size, with_text: this.textCount(), scrolls: this.scrolls});
      window.removeEventListener('pagehide', this.unload);
      await this.queue; if (this.state !== 'error') this.state = 'stopped'; await this.saveMeta(); await this.flushLog(); return this.status();
    }
    fail(error) {
      this.state = 'error'; this.reason = `storage_or_collection_error: ${error.message}`;
      clearInterval(this.timer); this.observer?.disconnect();
      this.trace('collection_error', {reason: 'storage_or_collection_error', error_type: error.name || 'Error'});
      this.flushLog();
      // Report even when persistence is unavailable; the live popup can still query status.
      this.saveMeta().catch(() => {});
    }
  }
  R.Collector = Collector;
})();
