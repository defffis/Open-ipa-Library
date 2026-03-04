# AGENTS.md — руководство для AI-агентов

Этот файл описывает архитектуру, соглашения и правила работы в репозитории **Open-ipa-Library**. Прочитай его целиком перед тем, как вносить изменения.

---

## Что делает проект

Ежедневно собирает GBox-каталог IPA-файлов из нескольких источников (PlayCover JSON-фиды, HTML-каталоги, статические зеркала) и коммитит результат обратно в репозиторий через GitHub Actions.

Точка входа: `python src/app.py`

---

## Ключевые файлы

| Файл | Назначение |
|---|---|
| `src/app.py` | Точка входа, argparse |
| `src/orchestrator.py` | Основной пайплайн |
| `src/registry.py` | Загрузка `config/sources.json` |
| `src/models/canonical.py` | `CanonicalApp` — единый формат приложения |
| `src/models/source_config.py` | `SourceConfig` — конфигурация источника |
| `src/adapters/base.py` | Протокол `SourceAdapter`, `FetchResult` |
| `src/services/http_client.py` | `HttpClient` — все HTTP-запросы идут через него |
| `src/services/exporter_gbox.py` | Сборка итогового GBox-каталога |
| `config/sources.json` | Реестр источников |
| `config/defaults.json` | Метаданные каталога по умолчанию |
| `tests/test_converter.py` | Все тесты |

---

## Архитектура

```
sources.json → registry.py → orchestrator.py
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                       ▼
    PlayCoverJsonAdapter   DecryptDayHtmlAdapter   ArmConverterHtmlAdapter
              │                     │                       │
              └─────────────────────┴───────────────────────┘
                                    │
                              CanonicalApp[]
                                    │
                          validator.py → deduplicator.py → exporter_gbox.py
                                                                  │
                                                       output/catalog.json
```

**Правило экспорта:** в `output/catalog.json` попадают только `CanonicalApp` где `download_url is not None` и `availability == "public"`. Проверяй через `app.is_exportable`.

---

## Соглашения

### Python

- Python 3.11+, аннотации через `from __future__ import annotations`
- Dataclasses — `@dataclass` (не Pydantic)
- Нет глобальных исключений кроме `except Exception as exc:  # noqa: BLE001` в адаптерах — там это намеренно, чтобы один сломанный источник не роняло весь пайплайн
- Зависимости минимальны: только `beautifulsoup4` в `requirements.txt`

### Добавление адаптера

1. Создай `src/adapters/<name>.py` — унаследуй от `HtmlCatalogAdapter` (HTML) или реализуй `fetch() -> FetchResult` напрямую
2. Зарегистрируй в `_ADAPTER_MAP` в `src/orchestrator.py`
3. Добавь имя в `VALID_ADAPTERS` в `src/registry.py`
4. Добавь запись в `config/sources.json`

### Изменение моделей

- `CanonicalApp` — единственный формат передачи приложений между слоями. Не добавляй поля, специфичные для одного источника — используй `raw: dict` для сырых данных.
- Приоритет источника для дедупликации пробрасывается через `app.raw["_source_priority"]` (устанавливает оркестратор).

### HTTP-запросы

Всегда используй `HttpClient` из `src/services/http_client.py`. Не используй `urllib` или `requests` напрямую в адаптерах.

Исключения, которые нужно обрабатывать:
- `NetworkError` — сеть недоступна
- `HttpStatusError` — нештатный HTTP-статус (`.status` содержит код)
- `HtmlChallengeError` — Cloudflare/anti-bot страница
- `AuthRequiredError` — login-wall
- `JsonParseError` — тело не JSON

---

## Запуск тестов

```bash
python -m pytest tests/test_converter.py -v
```

Тесты используют `tmp_path` и `monkeypatch` из pytest. Для тестов адаптеров используй `file://` URI через `Path.as_uri()` — не `file://C:\...` с обратными слэшами.

Старые тесты (`test_parse_sources_newline` и др.) проверяют `src/convert.py` — не удаляй их, это обратная совместимость.

---

## Что не трогать без необходимости

- `src/convert.py` и `src/mappers/playcover_to_gbox.py` — устаревший код, сохранён для обратной совместимости тестов
- `src/validators.py` — используется `exporter_gbox.py`, не дублируй логику
- `config/defaults.json` — шаблонные значения, `<owner>/<repo>` заменяются через env-переменные в CI

---

## GitHub Actions

Workflow: `.github/workflows/update-catalog.yml`

- Запуск: ежедневно 02:17 UTC + вручную
- Точка входа: `python src/app.py`
- Коммитит: `output/catalog.json`, `output/last-run.json`, `output/sources-status.json`
- Метаданные каталога берутся из Repository Variables окружения `Open-ipa-Library`
- Секреты для авторизованных источников: `SOURCE_COOKIE_*`, `SOURCE_TOKEN_*`
