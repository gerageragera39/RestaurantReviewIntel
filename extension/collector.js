(() => {
  const R = globalThis.RRI;
  class Collector {
    constructor(storage = chrome.storage.local) {
      this.storage = storage; this.records = new Map(); this.queue = Promise.resolve(); this.state = 'idle';
      this.pending = new Set(); this.attempted = new WeakSet(); this.observed = 0;
    }
    async start({runId, tabId, limit = 30, autoScroll = true, waitMs = 1500, maxIdle = 8, maxScrolls = 1000, maxMs = 1800000}) {
      if (['running', 'paused', 'stopping'].includes(this.state)) throw new Error('A collection is already active.');
      if (!Number.isInteger(limit) || limit < 0) throw new Error('Limit must be a nonnegative integer.');
      const blocked = R.restriction(); if (blocked) throw new Error(`Access restricted: ${blocked}`);
      this.panel = R.findPanel(); if (!this.panel) throw new Error('Open the full Reviews / Rezensionen panel first.');
      const name = R.restaurant(); if (!name) throw new Error('Restaurant name not detected.');
      this.options = {limit, autoScroll, waitMs, maxIdle, maxScrolls, maxMs};
      this.context = {restaurant_name: name, restaurant_url: location.href};
      this.runId = runId; this.tabId = tabId; this.state = 'running'; this.reason = '';
      this.started = Date.now(); this.scrolls = 0; this.idle = 0; this.lastProgress = 0;
      this.metaKey = `rri:run:${runId}`; this.prefix = `rri:review:${runId}:`;
      await this.saveMeta();
      this.observer = new MutationObserver(changes => {
        if (this.state !== 'running') return;
        // Read synchronously inside the callback, before awaiting persistence or hashing.
        for (const change of changes) {
          for (const node of [...change.addedNodes, ...change.removedNodes]) this.captureTree(node);
          this.captureTree(change.target);
        }
      });
      this.observer.observe(this.panel, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['data-review-id', 'aria-label', 'aria-expanded']});
      this.scan();
      this.timer = setInterval(() => this.tick().catch(e => this.fail(e)), waitMs);
      this.unload = () => { this.finish('page_unloaded'); };
      window.addEventListener('pagehide', this.unload, {once: true});
      await this.queue;
      return this.status();
    }
    captureTree(node) {
      if (this.state !== 'running' || node.nodeType !== 1) return;
      const card = node.matches(R.selectors.card) ? node : node.closest(R.selectors.card);
      if (card) this.capture(card);
      node.querySelectorAll(R.selectors.card).forEach(c => this.capture(c));
    }
    scan() { this.panel.querySelectorAll(R.selectors.card).forEach(c => this.capture(c)); }
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
        scope: 'Accessible displayed reviews only; completeness not established.'};
    }
    saveMeta() { return this.storage.set({[this.metaKey]: this.status()}); }
    async tick() {
      if (!['running', 'paused'].includes(this.state) || this.ticking) return;
      this.ticking = true;
      try {
        if (Date.now() - this.started >= this.options.maxMs) return await this.finish('time_budget');
        if (this.state === 'paused') return;
        const blocked = R.restriction(); if (blocked) return await this.finish(blocked);
        if (location.href !== this.context.restaurant_url || R.restaurant() !== this.context.restaurant_name) return await this.finish('page_changed');
        if (!this.panel.isConnected) return await this.finish('review_panel_closed');
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
    async resume() { if (this.state === 'paused') { this.state = 'running'; this.idle = 0; this.scan(); await this.saveMeta(); } return this.status(); }
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
