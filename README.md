# Open-ipa-Library

Автономный репозиторий для ежедневной конвертации PlayCover source JSON в единый GBox-каталог.

## Что делает проект

1. Читает список PlayCover source URL из переменной `PLAYCOVER_SOURCES`.
2. Загружает и валидирует каждый source.
3. Преобразует приложения в формат GBox.
4. Дедуплицирует приложения.
5. Сохраняет результат в `output/catalog.json`.
6. GitHub Actions коммитит обновления обратно в репозиторий.

## Структура

- `.github/workflows/update-catalog.yml` — ежедневный workflow.
- `src/convert.py` — основной конвейер.
- `src/mappers/playcover_to_gbox.py` — модели и маппинг.
- `src/validators.py` — базовая валидация GBox JSON.
- `config/defaults.json` — дефолтные значения метаданных.
- `output/catalog.json` — итоговый файл для raw-ссылки.
- `output/last-run.json` — краткий отчёт последнего запуска.

## Настройка за 5–10 минут

1. В репозитории создайте Variables:
   - `PLAYCOVER_SOURCES` (newline-separated URL или JSON-массив)
   - `GBOX_SOURCE_NAME`
   - `GBOX_SOURCE_AUTHOR`
   - `GBOX_SOURCE_DESCRIPTION`
   - `GBOX_SOURCE_IMAGE`
   - `GBOX_DEFAULT_APP_TYPE`
   - `OUTPUT_PATH` (обычно `output/catalog.json`)
2. При необходимости перенесите чувствительные параметры в Secrets.
3. Запустите workflow вручную через **Actions → Update GBox catalog → Run workflow**.
4. Получите raw-ссылку на `output/catalog.json` из основной ветки и используйте в GBox.

## Запуск локально

```bash
python src/convert.py
python src/convert.py --dry-run
```

## Формат преобразования

PlayCover app (минимум):
- `name`, `version`, `link` (`.ipa`)

GBox app:
- `appType`, `appCateIndex`, `appUpdateTime`, `appName`, `appVersion`, `appImage`, `appPackage`, `appDescription`

Дополнительные поля PlayCover (`bundleID`, `itunesLookup`) сохраняются в `appDescription`.

## Проверка последнего запуска

- Статус workflow: вкладка **Actions**.
- Метрики последнего запуска: `output/last-run.json`.

## Известные ограничения

- Версии сравниваются лексикографически (MVP).
- Иконка приложения — общий fallback (`GBOX_FALLBACK_ICON` / defaults).
- Если источник недоступен, pipeline продолжает обработку остальных источников.
