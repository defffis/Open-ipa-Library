# Open-ipa-Library

Репозиторий для ежедневной автоматической сборки [GBox](https://github.com/Astolfo-Official/GBox)-каталога из нескольких IPA-источников: PlayCover JSON-фидов, HTML-каталогов (decrypt.day, armconverter.com) и статических JSON-зеркал. GitHub Actions коммитит обновлённый каталог обратно в репозиторий.

---

## Что делает проект

```
config/sources.json
        │
        ▼
  PlayCoverJsonAdapter  ──┐
  DecryptDayHtmlAdapter ──┼──▶  CanonicalApp  ──▶  Validator  ──▶  Deduplicator  ──▶  GBoxExporter
  ArmConverterHtmlAdapter─┘
  StaticJsonMirrorAdapter
                                                                                            │
                                                              ┌─────────────────────────────┤
                                                              ▼                             ▼
                                                    output/catalog.json    output/sources-status.json
                                                    output/last-run.json
```

1. Реестр загружает список источников из `config/sources.json`.
2. Каждый источник обрабатывается своим адаптером → список `CanonicalApp`.
3. Приложения валидируются и дедуплицируются (ключ: `bundle_id` → `name+version` → `app_page_url`).
4. В `output/catalog.json` попадают только приложения с `download_url` и `availability=public`.
5. Статусы источников сохраняются в `output/sources-status.json`.

---

## Структура проекта

```
config/
  defaults.json          — метаданные каталога по умолчанию
  sources.json           — реестр источников
  dedupe.json            — правила дедупликации

src/
  app.py                 — точка входа (python src/app.py)
  orchestrator.py        — пайплайн: fetch → validate → dedupe → export
  registry.py            — загрузка и валидация sources.json
  validators.py          — валидация итогового GBox JSON

  models/
    source_config.py     — SourceConfig, AuthConfig, RateLimit
    canonical.py         — CanonicalApp (единый формат приложения)
    reports.py           — RunReport, SourceStatus, FetchResult

  adapters/
    base.py              — протокол SourceAdapter, FetchResult, AppRef
    playcover_json.py    — PlayCover JSON-фид
    html_base.py         — абстрактный HtmlCatalogAdapter
    decrypt_day_html.py  — decrypt.day HTML-каталог
    armconverter_html.py — armconverter.com HTML-каталог
    static_json_mirror.py— статическое GBox/generic JSON-зеркало

  services/
    http_client.py       — HttpClient (таймауты, ретраи, детекция challenge)
    html_parser.py       — обёртка над BeautifulSoup
    deduplicator.py      — дедупликация CanonicalApp
    validator.py         — валидация CanonicalApp
    exporter_gbox.py     — сборка GBox-каталога из CanonicalApp
    reporter.py          — запись last-run.json и sources-status.json

  mappers/
    playcover_to_gbox.py — (устаревший, сохранён для обратной совместимости)

output/
  catalog.json           — итоговый GBox-каталог (raw-ссылка для GBox)
  last-run.json          — метрики последнего запуска
  sources-status.json    — статус каждого источника

tests/
  test_converter.py      — тесты: старые (convert.py) + новые (вся архитектура)
```

---

## Быстрый старт (fork)

### 1. Настройте источники

Отредактируйте `config/sources.json` — добавьте или включите (`"enabled": true`) нужные источники. Пример:

```json
[
  {
    "id": "my-playcover-feed",
    "name": "My PlayCover Feed",
    "type": "playcover_json",
    "adapter": "playcover_json",
    "catalogUrl": "https://example.com/my-source.json",
    "enabled": true,
    "priority": 10
  }
]
```

### 2. Настройте метаданные каталога

Создайте GitHub Repository Variables (Settings → Variables → Actions) в окружении `Open-ipa-Library`:

| Переменная | Пример |
|---|---|
| `GBOX_SOURCE_NAME` | `My IPA Library` |
| `GBOX_SOURCE_AUTHOR` | `username` |
| `GBOX_SOURCE_DESCRIPTION` | `Daily IPA catalog` |
| `GBOX_SOURCE_IMAGE` | `https://example.com/icon.png` |
| `GBOX_DEFAULT_APP_TYPE` | `SELF_SIGN` |
| `GBOX_FALLBACK_ICON` | `https://example.com/fallback.png` |
| `OUTPUT_PATH` | `output/catalog.json` |

Для источников с авторизацией — добавьте в Secrets: `SOURCE_COOKIE_<ID>`, `SOURCE_TOKEN_<ID>`.

### 3. Запустите workflow

**Actions → Update GBox catalog → Run workflow**

### 4. Получите raw-ссылку

```
https://raw.githubusercontent.com/<owner>/<repo>/main/output/catalog.json
```

Вставьте эту ссылку в GBox как источник.

---

## Запуск локально

```bash
pip install -r requirements.txt

python src/app.py
python src/app.py --dry-run
python src/app.py --fail-on-no-sources --fail-on-no-apps
python src/app.py --sources config/sources.json --output output/catalog.json
```

Запуск тестов:

```bash
python -m pytest tests/
```

---

## Добавление нового адаптера

1. Создайте `src/adapters/my_adapter.py`, унаследовавшись от `HtmlCatalogAdapter` (для HTML) или реализовав метод `fetch() -> FetchResult` напрямую.
2. Зарегистрируйте имя адаптера в `src/orchestrator.py` (`_ADAPTER_MAP`) и в `src/registry.py` (`VALID_ADAPTERS`).
3. Добавьте запись в `config/sources.json` с `"adapter": "my_adapter"`.

---

## Форматы данных

### CanonicalApp (внутренний)

| Поле | Тип | Описание |
|---|---|---|
| `source_id` | str | ID источника из sources.json |
| `bundle_id` | str\|None | Apple bundle identifier |
| `name` | str | Название приложения |
| `version` | str\|None | Версия |
| `download_url` | str\|None | Прямая ссылка на .ipa (None → не экспортируется) |
| `app_page_url` | str\|None | Страница приложения |
| `availability` | str | `public` / `login_required` / `unavailable` / `unknown` |

### GBox App (output)

`appType`, `appCateIndex`, `appUpdateTime`, `appName`, `appVersion`, `appImage`, `appPackage`, `appDescription`

---

## Мониторинг

- **`output/last-run.json`** — сводные метрики: `status`, `sourcesOk`, `appsExportable`, `duplicatesRemoved`, `sourceErrors`.
- **`output/sources-status.json`** — статус каждого источника отдельно.
- **Actions → Summary** — `last-run.json` отображается в сводке workflow.

Возможные значения `status`: `ok`, `partial`, `skipped`, `error`.

---

## Troubleshooting

**`status: skipped` — нет включённых источников**  
Убедитесь, что в `config/sources.json` хотя бы одна запись имеет `"enabled": true`.

**`status: partial` — нет экспортируемых приложений**  
Источник доступен, но ни одно приложение не имеет прямого `.ipa`-URL. Проверьте `output/sources-status.json`.

**HTML/Cloudflare challenge в `sourceErrors`**  
Источник отдаёт anti-bot страницу вместо данных. Используйте прямой JSON-фид или проксирующий endpoint.

**Источник требует авторизации**  
Добавьте cookie/токен в Secrets и укажите `auth` в `config/sources.json`:
```json
"auth": { "type": "cookie", "cookieEnv": "SOURCE_COOKIE_MY_SOURCE" }
```

---

## Известные ограничения

- HTML-адаптеры (decrypt.day, armconverter) используют эвристический парсинг — при изменении верстки сайта может потребоваться обновление адаптера.
- Версии при дедупликации сравниваются через приоритет источника и полноту метаданных, а не семантическое версионирование.
- Иконки приложений из HTML-источников заполняются только если сайт явно их публикует; иначе используется `fallbackAppImage`.
