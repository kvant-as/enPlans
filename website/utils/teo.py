import os
import shutil
import uuid

from flask import current_app
from sqlalchemy import event as sa_event

from common_models.models import Direction, Event
from common_models.timeutils import current_utc_time
from website import db

ALLOWED_TEO_EXTENSIONS = {'.pdf', '.doc', '.docx'}

PERIOD_CODES = {'0001', '0002', '0003', '0004'}


def _ext(filename):
    return os.path.splitext(filename or '')[1].lower()


def check_disk_space(folder):
    """Проверяет, не превышен ли допустимый процент заполнения диска, на
    котором лежит папка с файлами ТЭО. Возвращает текст ошибки или None."""
    limit_percent = current_app.config.get('TEO_DISK_USAGE_LIMIT_PERCENT', 80)

    os.makedirs(folder, exist_ok=True)
    total, used, _free = shutil.disk_usage(folder)
    if total == 0:
        return None

    used_percent = used / total * 100
    if used_percent >= limit_percent:
        current_app.logger.warning(
            f'TEO upload blocked: disk usage {used_percent:.1f}% >= limit {limit_percent}% (folder={folder})'
        )
        return (
            f'Загрузка файлов ТЭО временно недоступна: диск сервера заполнен более чем на '
            f'{limit_percent}% ({used_percent:.0f}%). Обратитесь к администратору системы.'
        )

    return None


def validate_teo_file(file_storage):
    """Проверяет расширение, размер файла ТЭО и доступное место на диске.
    Возвращает текст ошибки или None, если файл допустим."""
    if not file_storage or not file_storage.filename:
        return 'Файл не выбран'

    if _ext(file_storage.filename) not in ALLOWED_TEO_EXTENSIONS:
        return 'Недопустимый формат файла. Разрешены: .doc, .docx, .pdf'

    max_size = current_app.config.get('TEO_MAX_FILE_SIZE', 20 * 1024 * 1024)
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_size:
        return f'Файл слишком большой (максимум {max_size // (1024 * 1024)} МБ)'

    disk_error = check_disk_space(current_app.config['TEO_UPLOAD_FOLDER'])
    if disk_error:
        return disk_error

    return None


def save_teo_file(event, file_storage):
    """Сохраняет файл ТЭО на диск и обновляет поля мероприятия. Если у
    мероприятия уже был прикреплён файл — старый удаляется с диска."""
    error = validate_teo_file(file_storage)
    if error:
        raise ValueError(error)

    folder = current_app.config['TEO_UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)

    old_filename = event.teo_filename

    ext = _ext(file_storage.filename)
    stored_name = f'{uuid.uuid4().hex}{ext}'
    file_storage.save(os.path.join(folder, stored_name))

    event.teo_filename = stored_name
    event.teo_original_name = file_storage.filename
    event.teo_uploaded_at = current_utc_time()

    if old_filename:
        _remove_file(folder, old_filename)


def delete_teo_file(event):
    """Удаляет прикреплённый файл ТЭО у мероприятия (с диска и из БД)."""
    if not event.teo_filename:
        return

    folder = current_app.config['TEO_UPLOAD_FOLDER']
    _remove_file(folder, event.teo_filename)

    event.teo_filename = None
    event.teo_original_name = None
    event.teo_uploaded_at = None


def _remove_file(folder, filename):
    path = os.path.join(folder, filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as e:
        current_app.logger.warning(f'Не удалось удалить файл ТЭО {path}: {e}')


def find_directions_missing_teo(plan):
    """Возвращает список (code, name) направлений плана (Часть 2 и Часть 3,
    без периодных направлений 0001-0004), у которых ни одно мероприятие не
    имеет прикреплённого файла ТЭО."""
    directions = (
        db.session.query(Direction.code, Direction.name)
        .join(Event, Event.id_direction == Direction.id)
        .filter(
            Event.id_plan == plan.id,
            db.or_(Event.is_econom == True, Event.is_increase == True),
            Direction.code.notin_(PERIOD_CODES)
        )
        .distinct()
        .all()
    )

    missing = []
    for code, name in directions:
        has_teo = (
            db.session.query(Event.id)
            .join(Direction, Event.id_direction == Direction.id)
            .filter(
                Event.id_plan == plan.id,
                Direction.code == code,
                Event.teo_filename.isnot(None)
            )
            .first()
        )
        if not has_teo:
            missing.append((code, name))

    return missing


_teo_cleanup_registered = False


def register_teo_cleanup_listeners():
    """Регистрирует удаление файла ТЭО с диска при удалении мероприятия —
    срабатывает независимо от того, как мероприятие удаляется: явное
    удаление мероприятия, удаление всего плана (каскад Plan.events,
    cascade="all, delete-orphan" — ORM удаляет каждый Event по отдельности,
    так что этот mapper-хук отрабатывает и тут), или удаление через
    админ-панель (cm_admin тоже делает db.session.delete(obj)). Централизует
    очистку файлов в одном месте вместо дублирования в каждом роуте.

    Mapper-события SQLAlchemy глобальны (не привязаны к конкретному Flask
    app), поэтому регистрация защищена от повторного вызова — иначе при
    повторном create_app() (например, в тестах) обработчик дублировался бы
    при каждом вызове."""
    global _teo_cleanup_registered
    if _teo_cleanup_registered:
        return
    _teo_cleanup_registered = True

    @sa_event.listens_for(Event, 'after_delete')
    def _delete_teo_file_on_event_delete(mapper, connection, target):
        if not target.teo_filename:
            return
        try:
            folder = current_app.config['TEO_UPLOAD_FOLDER']
            _remove_file(folder, target.teo_filename)
        except Exception as e:
            # Нет активного app-контекста или иная непредвиденная ошибка —
            # не должно ломать удаление самой записи в БД.
            try:
                current_app.logger.warning(f'Не удалось удалить файл ТЭО при удалении мероприятия {target.id}: {e}')
            except Exception:
                pass
