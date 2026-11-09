(() => {
  const R = globalThis.RRI = globalThis.RRI || {};
  R.exportFields = ['review_id', 'restaurant_name', 'restaurant_url', 'rating', 'text', 'date_raw', 'date_estimate', 'date_is_exact', 'scraped_at', 'star_rating', 'review_date_raw', 'date_accuracy', 'review_url'];
  R.exportRecord = r => ({review_id: r.review_id, restaurant_name: r.restaurant_name, restaurant_url: r.restaurant_url,
    rating: r.rating, text: r.text, date_raw: r.date_raw, date_estimate: r.date_estimate, date_is_exact: r.date_is_exact,
    scraped_at: r.scraped_at, star_rating: r.rating, review_date_raw: r.date_raw,
    date_accuracy: r.date_estimate ? (r.date_is_exact ? 'exact' : 'estimated') : 'unknown', review_url: null});
  R.toJSON = rows => JSON.stringify(rows.map(R.exportRecord), null, 2) + '\n';
  R.toCSV = rows => {
    const cell = v => '"' + String(v ?? '').replaceAll('"', '""') + '"';
    return R.exportFields.join(',') + '\r\n' + rows.map(R.exportRecord).map(r => R.exportFields.map(f => cell(r[f])).join(',')).join('\r\n') + '\r\n';
  };
  R.download = (rows, format, runId) => {
    const body = format === 'json' ? R.toJSON(rows) : '\uFEFF' + R.toCSV(rows);
    const url = URL.createObjectURL(new Blob([body], {type: format === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8'}));
    const a = document.createElement('a'); a.href = url; a.download = `reviews-${runId}.${format}`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
  R.downloadLog = (report, runId) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2) + '\n'], {type: 'application/json;charset=utf-8'}));
    const a = document.createElement('a'); a.href = url; a.download = `rri-log-${runId}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
})();
