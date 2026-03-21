"""
Скрипт для запуска миграций Alembic
Использование: python run_migrations.py [команда] [аргументы]
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем корень проекта в путь
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

import yaml
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import BestchangeYamlSnapshot
from settings import DatabaseSettings


def _parse_meta_exported_at(value) -> datetime:
    if value is None:
        raise ValueError("meta.exported_at отсутствует в bc.yaml")
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    s = str(value).strip().strip("'\"")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _payload_json_safe(data: dict) -> dict:
    """Приводит дерево YAML к JSON-совместимому виду для JSONB."""
    return json.loads(json.dumps(data, default=str))


def seed_bestchange_yaml_snapshot(repo_root: Path) -> None:
    """После upgrade: при отсутствии хеша в БД добавить строку из bc.yaml."""
    path = repo_root / "bc.yaml"
    if not path.is_file():
        print("ℹ bc.yaml не найден — пропуск обновления bestchange_yaml_snapshots.")
        return

    raw = path.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()

    try:
        tree = yaml.safe_load(raw.decode("utf-8"))
    except Exception as e:
        print(f"✗ Не удалось разобрать bc.yaml: {e}")
        return

    if not isinstance(tree, dict):
        print("✗ bc.yaml: ожидается корневой объект YAML.")
        return

    meta = tree.get("meta") or {}
    try:
        exported_at = _parse_meta_exported_at(meta.get("exported_at"))
    except ValueError as e:
        print(f"✗ {e}")
        return

    payload = _payload_json_safe(tree)

    db_settings = DatabaseSettings()
    engine = create_engine(db_settings.url)
    try:
        with Session(engine) as session:
            stmt = (
                select(BestchangeYamlSnapshot.id)
                .where(BestchangeYamlSnapshot.file_hash == file_hash)
                .limit(1)
            )
            if session.execute(stmt).scalar_one_or_none() is not None:
                print("ℹ bestchange_yaml_snapshots: хеш bc.yaml уже есть — запись не добавлена.")
                return

            row = BestchangeYamlSnapshot(
                file_hash=file_hash,
                exported_at=exported_at,
                payload=payload,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                print("ℹ bestchange_yaml_snapshots: хеш уже есть (гонка) — пропуск.")
                return
        print("✓ bestchange_yaml_snapshots: добавлена запись из bc.yaml.")
    finally:
        engine.dispose()


def run_migrations(target="head"):
    """Запуск миграций Alembic"""
    try:
        # Получаем настройки БД
        db_settings = DatabaseSettings()
        print(f"Подключение к БД: {db_settings.host}:{db_settings.port}/{db_settings.database}")
        
        # Настраиваем Alembic
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_settings.url)
        
        # Запускаем миграции
        print(f"Применение миграций до версии: {target}")
        command.upgrade(alembic_cfg, target)
        print("✓ Миграции успешно применены!")
        seed_bestchange_yaml_snapshot(_REPO_ROOT)

    except Exception as e:
        print(f"✗ Ошибка при применении миграций: {e}")
        sys.exit(1)


def downgrade_migrations(revision="-1"):
    """Откат миграций Alembic"""
    try:
        db_settings = DatabaseSettings()
        print(f"Подключение к БД: {db_settings.host}:{db_settings.port}/{db_settings.database}")
        
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_settings.url)
        
        print(f"Откат миграций: {revision}")
        command.downgrade(alembic_cfg, revision)
        print("✓ Миграции успешно откачены!")
        
    except Exception as e:
        print(f"✗ Ошибка при откате миграций: {e}")
        sys.exit(1)


def show_current():
    """Показать текущую версию миграций"""
    try:
        db_settings = DatabaseSettings()
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_settings.url)
        
        command.current(alembic_cfg)
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        sys.exit(1)


def show_history():
    """Показать историю миграций"""
    try:
        db_settings = DatabaseSettings()
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_settings.url)
        
        command.history(alembic_cfg)
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        sys.exit(1)


def create_revision(message, autogenerate=False):
    """Создать новую миграцию"""
    try:
        db_settings = DatabaseSettings()
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_settings.url)
        
        if autogenerate:
            print(f"Создание автоматической миграции: {message}")
            command.revision(alembic_cfg, message=message, autogenerate=True)
        else:
            print(f"Создание пустой миграции: {message}")
            command.revision(alembic_cfg, message=message)
        
        print("✓ Миграция успешно создана!")
        
    except Exception as e:
        print(f"✗ Ошибка при создании миграции: {e}")
        sys.exit(1)


def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python run_migrations.py upgrade [revision]  - Применить миграции (по умолчанию: head)")
        print("  python run_migrations.py downgrade [revision] - Откатить миграции (по умолчанию: -1)")
        print("  python run_migrations.py current              - Показать текущую версию")
        print("  python run_migrations.py history             - Показать историю миграций")
        print("  python run_migrations.py create <message>     - Создать новую миграцию")
        print("  python run_migrations.py autogenerate <message> - Создать автоматическую миграцию")
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "upgrade":
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        run_migrations(target)
    elif cmd == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        downgrade_migrations(revision)
    elif cmd == "current":
        show_current()
    elif cmd == "history":
        show_history()
    elif cmd == "create":
        if len(sys.argv) < 3:
            print("✗ Укажите сообщение для миграции: python run_migrations.py create 'описание'")
            sys.exit(1)
        message = sys.argv[2]
        create_revision(message, autogenerate=False)
    elif cmd == "autogenerate":
        if len(sys.argv) < 3:
            print("✗ Укажите сообщение для миграции: python run_migrations.py autogenerate 'описание'")
            sys.exit(1)
        message = sys.argv[2]
        create_revision(message, autogenerate=True)
    else:
        print(f"✗ Неизвестная команда: {cmd}")
        print("Используйте: upgrade, downgrade, current, history, create, autogenerate")
        sys.exit(1)


if __name__ == "__main__":
    main()
