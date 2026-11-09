(() => {
  const R = globalThis.RRI;
  class Collector {
    constructor(storage = chrome.storage.local) {
      this.storage = storage; this.records = new Map(); this.queue = Promise.resolve(); this.state = 'idle';
      this.pending = new Set(); this.attempted = new WeakSet(); this.observed = 0;
    }
    async start({runId, tabId, limit = 30, autoScroll = true, waitMs = 1500, maxIdle = 8, maxScrolls = 1000, maxMs = 1800000, panelWaitMs = 10000}) {
      if (['waiting_for_reviews', 'running', 'paused', 'stopping'].includes(this.state)) throw new Error('A collection is already active.');
      if (!Number.isInteger(limit) || limit < 0) throw new Error('Limit must be a nonnegative integer.');
      const blocked = R.restriction(); if (blocked) throw new Error(`Access restricted: ${blocked}`);
      this.identity = R.identity();
      const name = this.identity.name || this.identity.slug; if (!name) throw new Error('Restaurant identity not detected.');
      this.options = {limit, autoScroll, waitMs, maxIdle, maxScrolls, maxMs, panelWaitMs};
      this.context = {restaurant_name: name, restaurant_url: location.href};
      this.runId = runId; this.tabId = tabId; this.state = 'waiting_for_reviews'; this.reason = '';
      this.startFailedPanelDetection = false; this.reacquisitions = 0;
      this.started = Date.now(); this.scrolls = 0; this.idle = 0; this.lastProgress = 0;
      this.metaKey = `rri:run:${runId}`; this.prefix = `rri:review:${runId}:`;
      await this.saveMeta();
      try {
        const detection = R.inspect();
        if (!detection.panel && detection.mode === 'PREVIEW_MODE') {
          const opener = R.reviewOpener();
          if (!opener && !detection.review_route_hint) {
            const error = new Error('Preview reviews only. Open More reviews / Weitere Rezensionen, then Start again.');
            error.code = 'full_panel_not_ready'; throw error;
          }
          // Only invoked following Start, using the ordinary visible Maps control.
          opener?.click();
        }
        const ready = await R.waitForPanel(() => {
          const blocked = R.restriction(); if (blocked) { const error = new Error(blocked); error.code = blocked; throw error; }
          if (R.sameRestaurant(this.identity) === 'different') { const error = new Error('Restaurant changed while opening reviews.'); error.code = 'page_changed'; throw error; }
          const found = R.inspect();
          return R.sameRestaurant(this.identity) === 'same' && found.panel && found.full_review_cards ? found : null;
        }, panelWaitMs);
        this.panel = ready.panel; this.state = 'running';
      } catch (error) {
        this.state = 'stopped'; this.reason = error.code || 'start_failed';
        this.startFailedPanelDetection = this.reason === 'full_panel_not_ready';
        await this.saveMeta(); console.info('[RRI] Start failed', this.status().diagnostics); throw error;
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
      return this.status();
    }
    refreshPanel() {
      const blocked = R.restriction();
      const identity = R.sameRestaurant(this.identity);
      if (blocked || identity === 'different') { this.finish(blocked || 'page_changed').catch(e => this.fail(e)); return false; }
      const detection = R.inspect();
      if (identity !== 'same' || !detection.panel || !detection.full_review_cards) {
        this.panelMissingSince ??= Date.now();
        if (Date.now() - this.panelMissingSince >= this.options.panelWaitMs) {
          this.finish(identity === 'unknown' ? 'restaurant_identity_unverified' : 'review_panel_closed').catch(e => this.fail(e));
        }
        return false;
      }
      this.panelMissingSince = null;
      if (detection.panel !== this.panel) {
        this.panel = detection.panel; this.idle = 0; this.reacquisitions++;
        console.info('[RRI] Review panel reacquired', this.status().diagnostics);
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
      if (!snapshot) return;
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
        this.scan(); await this.queue;
        if (this.options.limit && this.textCount() >= this.options.limit) return await this.finish('text_limit');
        const progress = this.records.size;
        this.idle = progress === this.lastProgress ? this.idle + 1 : 0; this.lastProgress = progress;
        if (this.idle >= this.options.maxIdle) return await this.finish('no_progress');
        const content = this.panel.cloneNode(true); content.querySelectorAll(R.selectors.card).forEach(n => n.remove());
        if (/no more reviews|keine weiteren rezensionen|you.ve reached the end|ende der liste/i.test(content.textContent)) return await this.finish('accessible_end');
        if (this.options.autoScroll) {
          if (this.scrolls >= this.options.maxScrolls) return await this.finish('scroll_budget');
          this.panel.scrollTop += Math.max(200, this.panel.clientHeight * 0.8);
          this.panel.dispatchEvent(new Event('scroll', {bubbles: true})); this.scrolls++;
          this.scan();
        }
        await this.saveMeta();
      } finally { this.ticking = false; }
    }
    async pause() { if (this.state === 'running') { this.state = 'paused'; await this.queue; await this.saveMeta(); } return this.status(); }
    async resume() { if (this.state === 'paused') { this.state = 'running'; this.idle = 0; if (this.refreshPanel()) this.scan(); await this.saveMeta(); } return this.status(); }
    async finish(reason = 'user_stop') {
      if (['stopped', 'error', 'stopping'].includes(this.state)) return this.status();
      this.state = 'stopping'; this.reason = reason; clearInterval(this.timer); this.observer?.disconnect();
      window.removeEventListener('pagehide', this.unload);
      await this.queue; if (this.state !== 'error') this.state = 'stopped'; await this.saveMeta(); return this.status();
    }
    fail(error) {
      this.state = 'error'; this.reason = `storage_or_collection_error: ${error.message}`;
      clearInterval(this.timer); this.observer?.disconnect();
      // Report even when persistence is unavailable; the live popup can still query status.
      this.saveMeta().catch(() => {});
    }
  }
  R.Collector = Collector;
})();
