# AGENTS.md

## Cursor Cloud specific instructions

**Project:** Open-ipa-Library — CLI-конвертер PlayCover source JSON → GBox catalog JSON. Чистый Python (stdlib only), без сторонних runtime-зависимостей.

### Запуск и тестирование

- **Тесты:** `PLAYCOVER_SOURCES="" python3 -m pytest tests/ -v` — переменную `PLAYCOVER_SOURCES` нужно явно обнулять, иначе тесты могут подхватить значение из окружения и `test_empty_sources_is_skipped` провалится.
- **Линтинг:** `ruff check src/ tests/`
- **Запуск CLI:** `python3 src/convert.py --dry-run` (без записи файлов) или `python3 src/convert.py` (с записью каталога по пути из `OUTPUT_PATH`).
- **Локальный E2E-тест:** создать JSON-файл в формате PlayCover и передать через `PLAYCOVER_SOURCES="file:///path/to/source.json" python3 src/convert.py`.

### Важные нюансы

- В окружении может быть установлена переменная `PLAYCOVER_SOURCES`. Если тесты падают на `test_empty_sources_is_skipped`, убедитесь, что переменная пуста при запуске pytest.
- Проект не использует Docker, базы данных или внешние сервисы.
- `requirements.txt` содержит только комментарий (нет runtime-зависимостей). Для разработки нужен только `pytest` и опционально `ruff`.
- Отчёт последнего запуска: `output/last-run.json`. Итоговый каталог: путь задаётся переменной `OUTPUT_PATH`.
