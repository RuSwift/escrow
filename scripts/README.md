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

## `build_payment_forms_yaml.py`

Собирает **`forms.yaml`** в корне репозитория (рядом с **`bc.yaml`**): для каждого **`payment_code`** из снимка BestChange — список полей реквизитов (`id`, `type`, `required`, `label_key`). Наборы полей задаются **эвристиками** по коду и валюте (CARD, WIRE, CASH, крипто, SBP, QR и т.д.); при необходимости точечные правки — через overrides.

Подписи полей не хранятся в YAML: **`label_key`** ссылается на **`i18n/translations/ru.json`** и **`en.json`** (префикс **`forms.requisite.*`**).

### Формат `forms.yaml`

| Поле | Содержимое |
|------|------------|
| `meta` | `schema_version`, `bc_source` (`file`, `exported_at` из `bc.yaml`) |
| `forms` | Словарь `payment_code` → `{ fields: [...] }`; каждое поле: `id`, `type`, `required`, `label_key` |

Допустимые **`type`**: см. **`PaymentFormFieldType`** в **`core/bc.py`** (`string`, `text`, `phone`, `iban`, `bic`, `account_number`, `pan_last_digits`, …).

### Overrides

- Шаблон: **`i18n/payment_forms_overrides.example.yaml`** — скопируйте в **`i18n/payment_forms_overrides.yaml`** и задайте блок **`overrides.<PAYMENT_CODE>.fields`**.
- Если **`payment_forms_overrides.yaml`** существует, скрипт подхватывает его по умолчанию; иначе передайте **`--overrides /path/to.yaml`**.

### Примеры

```bash
# Пересобрать forms.yaml после обновления bc.yaml
poetry run python scripts/build_payment_forms_yaml.py -b bc.yaml -o forms.yaml

# Сверка: текущий forms.yaml должен совпадать с пересчётом из bc.yaml
poetry run python scripts/build_payment_forms_yaml.py -b bc.yaml --check

# Список уникальных label_key (для проверки ключей в i18n)
poetry run python scripts/build_payment_forms_yaml.py -b bc.yaml --print-label-keys
```

### Тесты

Проверка покрытия и соответствия генератору: **`tests/test_payment_forms_yaml.py`**. Без поднятого PostgreSQL:

```bash
ESCROW_PYTEST_NO_DB=1 pytest tests/test_payment_forms_yaml.py -v
```

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

Pydantic-модели YAML-файлов в корне репозитория:

- **`bc.yaml`**: `BestchangeExportYaml`, вложенные `meta`, `payment_methods`, `cities` — то же использует **`export_bestchange_yaml.py`**.
- **`forms.yaml`**: `PaymentFormsYaml`, `PaymentForm`, `PaymentFormField`, `PaymentFormFieldType` в **`core/bc.py`** (реэкспорт в `scripts/schemas.py`) — то же использует **`build_payment_forms_yaml.py`**.

```python
from pathlib import Path
from core.bc import load_payment_forms_yaml
from scripts.schemas import load_bestchange_export_yaml

bc = load_bestchange_export_yaml(Path("bc.yaml"))
forms = load_payment_forms_yaml(Path("forms.yaml"))
# load_payment_forms_yaml также реэкспортируется из scripts.schemas для совместимости
```

---

## Зависимости скриптов

- **`pyyaml`** — сериализация YAML
- **`pydantic`** — схема `schemas.py`
- **`aiohttp`**, настройки **`pydantic-settings`** — загрузка данных BestChange через код из `services/ratios/bestchange.py`
- **`deep-translator`** — только при использовании **`--en`** с автоматическими источниками
