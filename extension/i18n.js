(() => {
  const R = globalThis.RRI = globalThis.RRI || {};
  const strings = {
    en: {
      reloadMaps: 'Refresh the Google Maps tab: it still has an older content script. Reloading only the extension is not enough.',
      logTitle: 'Collection log', logs: 'Download log', logHint: 'After Start, download the log even if collection fails. It contains stages and scroll measurements, without review text or account data.',
      detecting: 'Detecting restaurant…', limit: 'Text review limit (0 = unlimited)', auto: 'Scroll review panel automatically',
      start: 'Start Scraping', pause: 'Pause', resume: 'Resume', stop: 'Stop', saved: 'Saved collection', empty: 'No saved collections',
      observed: 'Collected card versions', unique: 'Unique reviews', withText: 'With text', withDates: 'With dates', unexpanded: 'Unexpanded / skipped',
      diagnostics: 'Panel diagnostics', json: 'Export JSON', csv: 'Export CSV',
      hint: 'Start clicks Reviews or More reviews, waits for the list, then scrolls it when automatic scrolling is enabled. Keep Maps open. Unlimited has safety bounds and does not guarantee completeness.',
      ready: 'Full reviews panel ready.', preview: 'Preview mode. Start opens Reviews or More reviews and waits for the full list.',
      waiting: 'Waiting for a scrollable full reviews panel.', opening: 'Opening or detecting full reviews; waiting for the restaurant and review list…',
      open: 'Start clicks Reviews or More reviews. You can also open the list yourself.', select: 'Select a Google Maps restaurant tab',
      unknown: 'Restaurant identity unavailable', fromURL: ' (from Maps URL)', invalidLimit: 'Enter a nonnegative whole-number limit.',
      idle: 'idle', running: 'running', paused: 'paused', stopped: 'stopped', stopping: 'stopping', error: 'error', interrupted: 'interrupted', waiting_for_reviews: 'waiting_for_reviews',
      text_limit: 'text_limit', user_stop: 'user_stop', no_progress: 'no_progress', accessible_end: 'accessible_end', scroll_budget: 'scroll_budget', time_budget: 'time_budget',
      page_changed: 'page_changed', page_unloaded: 'page_unloaded', review_panel_closed: 'review_panel_closed', restaurant_identity_unverified: 'restaurant_identity_unverified',
      restricted_view: 'restricted_view', access_restricted: 'access_restricted', access_dialog: 'access_dialog', captcha: 'captcha', browser_security_block: 'browser_security_block',
      full_panel_not_ready: 'The full Reviews panel was not detected. Open More reviews and retry.',
      interruptedDetail: 'Tab closed, navigated, or extension reloaded. Saved data retained.'
    },
    de: {
      reloadMaps: 'Google-Maps-Tab aktualisieren: Dort läuft noch ein älteres Inhaltsskript. Nur die Erweiterung neu zu laden reicht nicht.',
      logTitle: 'Sammlungsprotokoll', logs: 'Protokoll herunterladen', logHint: 'Nach Start ist das Protokoll auch bei Fehlern verfügbar. Es enthält Schritte und Scrollmessungen ohne Rezensionstexte oder Kontodaten.',
      detecting: 'Restaurant wird erkannt…', limit: 'Limit für Textrezensionen (0 = unbegrenzt)', auto: 'Rezensionsliste automatisch scrollen',
      start: 'Sammlung starten', pause: 'Pausieren', resume: 'Fortsetzen', stop: 'Stoppen', saved: 'Gespeicherte Sammlung', empty: 'Keine gespeicherten Sammlungen',
      observed: 'Erfasste Kartenversionen', unique: 'Eindeutige Rezensionen', withText: 'Mit Text', withDates: 'Mit Datum', unexpanded: 'Nicht erweitert / übersprungen',
      diagnostics: 'Bereichsdiagnose', json: 'JSON exportieren', csv: 'CSV exportieren',
      hint: 'Start klickt Rezensionen oder Weitere Rezensionen, wartet auf die Liste und scrollt bei aktivierter Automatik. Maps geöffnet lassen. Unbegrenzt hat Sicherheitsgrenzen und garantiert keine Vollständigkeit.',
      ready: 'Vollständige Rezensionsliste bereit.', preview: 'Vorschaumodus. Start öffnet Rezensionen oder Weitere Rezensionen und wartet auf die Liste.',
      waiting: 'Warte auf eine scrollbare Rezensionsliste.', opening: 'Rezensionsliste wird geöffnet oder erkannt; warte auf Restaurant und Rezensionen…',
      open: 'Start klickt Rezensionen oder Weitere Rezensionen. Die Liste kann auch manuell geöffnet werden.', select: 'Einen Google-Maps-Restauranttab auswählen',
      unknown: 'Restaurant konnte nicht erkannt werden', fromURL: ' (aus der Maps-URL)', invalidLimit: 'Eine nicht negative ganze Zahl als Limit eingeben.',
      idle: 'bereit', running: 'Sammlung läuft', paused: 'pausiert', stopped: 'gestoppt', stopping: 'wird gestoppt', error: 'Fehler', interrupted: 'unterbrochen', waiting_for_reviews: 'warte auf Rezensionen',
      text_limit: 'Textlimit erreicht', user_stop: 'manuell gestoppt', no_progress: 'keine neuen Rezensionen', accessible_end: 'Ende der zugänglichen Liste', scroll_budget: 'Scrollgrenze erreicht', time_budget: 'Zeitlimit erreicht',
      page_changed: 'Restaurant gewechselt', page_unloaded: 'Seite geschlossen oder neu geladen', review_panel_closed: 'Rezensionsbereich geschlossen', restaurant_identity_unverified: 'Restaurant nicht sicher erkannt',
      restricted_view: 'eingeschränkte Ansicht', access_restricted: 'Zugriff eingeschränkt', access_dialog: 'Anmeldung oder Zustimmung erforderlich', captcha: 'CAPTCHA erkannt', browser_security_block: 'Browser-Sicherheitswarnung',
      full_panel_not_ready: 'Vollständige Rezensionsliste nicht erkannt. Weitere Rezensionen öffnen und erneut starten.',
      interruptedDetail: 'Tab geschlossen, Seite gewechselt oder Erweiterung neu geladen. Gespeicherte Daten bleiben erhalten.'
    },
    ru: {
      reloadMaps: 'Обновите вкладку Google Карт: в ней остался старый скрипт. Одной перезагрузки расширения недостаточно.',
      logTitle: 'Журнал сбора', logs: 'Скачать журнал', logHint: 'После запуска журнал можно скачать даже при ошибке. В нём есть этапы и измерения прокрутки, без текстов отзывов и данных аккаунта.',
      detecting: 'Определяем ресторан…', limit: 'Лимит текстовых отзывов (0 = без лимита)', auto: 'Прокручивать список отзывов автоматически',
      start: 'Начать сбор', pause: 'Пауза', resume: 'Продолжить', stop: 'Остановить', saved: 'Сохранённый сбор', empty: 'Нет сохранённых данных',
      observed: 'Обработано версий карточек', unique: 'Уникальных отзывов', withText: 'С текстом', withDates: 'С датой', unexpanded: 'Не раскрыто / пропущено',
      diagnostics: 'Диагностика панели', json: 'Экспорт JSON', csv: 'Экспорт CSV',
      hint: 'Старт нажимает «Отзывы» или «Ещё отзывы», ожидает список и прокручивает его при включённой автоматике. Оставьте Карты открытыми. У сбора без лимита есть защитные ограничения; полнота не гарантируется.',
      ready: 'Полный список отзывов готов.', preview: 'Режим предпросмотра. Старт открывает «Отзывы» или «Ещё отзывы» и ожидает список.',
      waiting: 'Ожидаем прокручиваемый список отзывов.', opening: 'Открываем или определяем полный список; ожидаем ресторан и отзывы…',
      open: 'Старт нажимает «Отзывы» или «Ещё отзывы». Список можно открыть вручную.', select: 'Выберите вкладку ресторана в Google Картах',
      unknown: 'Не удалось определить ресторан', fromURL: ' (из адреса Google Карт)', invalidLimit: 'Введите целое неотрицательное число.',
      idle: 'готово', running: 'идёт сбор', paused: 'пауза', stopped: 'остановлено', stopping: 'останавливаем', error: 'ошибка', interrupted: 'прервано', waiting_for_reviews: 'ожидаем отзывы',
      text_limit: 'достигнут лимит текстовых отзывов', user_stop: 'остановлено пользователем', no_progress: 'нет новых отзывов', accessible_end: 'конец доступного списка', scroll_budget: 'достигнут предел прокруток', time_budget: 'истекло время сбора',
      page_changed: 'выбран другой ресторан', page_unloaded: 'страница закрыта или обновлена', review_panel_closed: 'панель отзывов закрыта', restaurant_identity_unverified: 'ресторан не удалось подтвердить',
      restricted_view: 'ограниченная версия Карт', access_restricted: 'доступ ограничен', access_dialog: 'необходим вход или согласие', captcha: 'обнаружена CAPTCHA', browser_security_block: 'предупреждение безопасности браузера',
      full_panel_not_ready: 'Полный список отзывов не найден. Откройте «Ещё отзывы» и повторите запуск.',
      interruptedDetail: 'Вкладка закрыта, страница изменена или расширение перезагружено. Сохранённые данные доступны.'
    }
  };
  R.uiLanguage = 'en';
  R.t = key => strings[R.uiLanguage]?.[key] ?? strings.en[key] ?? key;
  R.setUILanguage = language => {
    R.uiLanguage = Object.hasOwn(strings, language) ? language : 'en';
    document.documentElement.lang = R.uiLanguage;
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = R.t(node.dataset.i18n); });
  };
})();
