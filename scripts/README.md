# Скрипты

Запускайте из **корня репозитория** с активированным окружением (см. правила проекта: `.venv` / `poetry`).

```bash
cd /path/to/escrow
poetry install
poetry run python scripts/<script>.py --help
```

---

## `export_bestchange_yaml.py`

Скачивает архив BestChange (`info.zip` по умолчанию с `api.bestchange.ru`), парсит `bm_*.dat` и выгружает **YAML** со способами оплаты и городами.

### Формат выходного YAML

| Поле | Содержимое |
|------|------------|
| `meta` | `source_url`, `zip_path`, `encoding`, `exported_at` (+ блок `translation` при `--en`) |
| `payment_methods` | Список: `payment_code`, `cur`, `payment_name` (+ `payment_name_en` при `--en`) |
| `cities` | Список: `id`, `name` (+ `name_en` при `--en`) |

### Настройки

По умолчанию берутся из **`Settings().ratios.bestchange`** или **`BestChangeSettings()`** — переменные окружения с префиксом **`RATIOS_BESTCHANGE_`** (см. `settings/__init__.py`), файлы **`.env`** и **`.env.local`** в корне репозитория.

Типичные переменные:

- `RATIOS_BESTCHANGE_URL` — URL архива (по умолчанию `http://api.bestchange.ru/info.zip`)
- `RATIOS_BESTCHANGE_ZIP_PATH` — куда сохранять скачанный ZIP
- `RATIOS_BESTCHANGE_ENC` — кодировка файлов внутри архива (часто `windows-1251`)

### Примеры

```bash
# Вывод в файл (скачивание ZIP по URL из настроек)
poetry run python scripts/export_bestchange_yaml.py -o bc.yaml

# Печать в stdout
poetry run python scripts/export_bestchange_yaml.py

# Локальный архив без HTTP
poetry run python scripts/export_bestchange_yaml.py --zip /path/to/info.zip -o bc.yaml

# Переопределить URL и путь для скачивания
poetry run python scripts/export_bestchange_yaml.py \
  --url http://api.bestchange.ru/info.zip \
  --zip-path /tmp/bestchange.zip \
  -o bc.yaml
```

### Перевод на английский (`--en`)

Включает поля **`payment_name_en`** и **`name_en`**. Реализация — в **`bestchange_i18n.py`**: сначала ручной YAML, затем автоматические движки в порядке, заданном **`--en-sources`**.

```bash
poetry run python scripts/export_bestchange_yaml.py -o bc.yaml --en \
  --en-manual i18n/bestchange_en.yaml \
  --en-sources manual,google,mymemory,libre
```

Если **`--en-manual`** не указан, но существует файл **`i18n/bestchange_en.yaml`**, он подставляется автоматически.

Шаблон ручных переводов: **`i18n/bestchange_en.example.yaml`** (скопируйте в `bestchange_en.yaml` и заполните).

---

## `bestchange_i18n.py`

Модуль не запускается отдельно: его использует **`export_bestchange_yaml.py`** при флаге **`--en`**.

### Источники перевода (`--en-sources`, через запятую)

| Код | Описание |
|-----|----------|
| `manual` | YAML: `cities_by_id`, `payments_by_key` (ключ `CUR|PAYMENT_CODE`), `payments_by_name` |
| `google` | Google Translate через [deep-translator](https://github.com/nidhaloff/deep-translator) |
| `mymemory` | MyMemory |
| `libre` | LibreTranslate; URL: **`LIBRETRANSLATE_URL`** (по умолчанию публичный инстанс) |
| `deepl` | DeepL — нужен **`DEEPL_API_KEY`** |
| `bing` | Microsoft — **`BING_TRANSLATE_KEY`**, опционально **`BING_TRANSLATE_REGION`** |
| `yandex` | **`YANDEX_TRANSLATE_KEY`** |
| `chatgpt` | **`OPENAI_API_KEY`** |

Сначала для каждой строки проверяется **manual**, затем по очереди автоматические источники, пока не получится перевод. Повторяющиеся одинаковые русские строки в одном прогоне кэшируются в памяти.

Значение по умолчанию для **`--en-sources`**: `manual,google,mymemory,libre`.

### Зависимость

Автоперевод требует пакет **`deep-translator`** (указан в `pyproject.toml`).

---

## `schemas.py`

Pydantic-модели структуры выгружаемого YAML (тот же формат, что у `bc.yaml`): `BestchangeExportYaml`, вложенные `meta`, `payment_methods`, `cities`. Их же использует **`export_bestchange_yaml.py`** при сборке вывода.

```python
from pathlib import Path
from scripts.schemas import load_bestchange_export_yaml

data = load_bestchange_export_yaml(Path("bc.yaml"))
```

---

## Зависимости скриптов

- **`pyyaml`** — сериализация YAML
- **`pydantic`** — схема `schemas.py`
- **`aiohttp`**, настройки **`pydantic-settings`** — загрузка данных BestChange через код из `services/ratios/bestchange.py`
- **`deep-translator`** — только при использовании **`--en`** с автоматическими источниками
