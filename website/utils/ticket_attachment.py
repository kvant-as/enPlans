import os
import uuid

from flask import current_app
from sqlalchemy import event as sa_event

from common_models.models import PlanTicket
from common_models.timeutils import current_utc_time

ALLOWED_TICKET_ATTACHMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'}


def _ext(filename):
    return os.path.splitext(filename or '')[1].lower()


def validate_ticket_attachment(file_storage):
    """Проверяет расширение и размер файла, прикреплённого к сообщению
    (замечанию). Возвращает текст ошибки или None, если файл допустим."""
    if not file_storage or not file_storage.filename:
        return 'Файл не выбран'

    if _ext(file_storage.filename) not in ALLOWED_TICKET_ATTACHMENT_EXTENSIONS:
        return 'Недопустимый формат файла. Разрешены: .doc, .docx, .pdf, .xls, .xlsx, .jpg, .jpeg, .png'

    max_size = current_app.config.get('TICKET_ATTACHMENT_MAX_FILE_SIZE', 20 * 1024 * 1024)
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_size:
        return f'Файл слишком большой (максимум {max_size // (1024 * 1024)} МБ)'

    return None


def save_ticket_attachment(ticket, file_storage):
    """Сохраняет файл на диск и обновляет поля сообщения (ticket)."""
    error = validate_ticket_attachment(file_storage)
    if error:
        raise ValueError(error)

    folder = current_app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)

    ext = _ext(file_storage.filename)
    stored_name = f'{uuid.uuid4().hex}{ext}'
    file_storage.save(os.path.join(folder, stored_name))

    ticket.attachment_filename = stored_name
    ticket.attachment_original_name = file_storage.filename
    ticket.attachment_uploaded_at = current_utc_time()


def delete_ticket_attachment(ticket):
    """Удаляет прикреплённый файл сообщения (с диска и из БД)."""
    if not ticket.attachment_filename:
        return

    folder = current_app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER']
    _remove_file(folder, ticket.attachment_filename)

    ticket.attachment_filename = None
    ticket.attachment_original_name = None
    ticket.attachment_uploaded_at = None


def _remove_file(folder, filename):
    path = os.path.join(folder, filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as e:
        current_app.logger.warning(f'Не удалось удалить файл вложения сообщения {path}: {e}')


_ticket_attachment_cleanup_registered = False


def register_ticket_attachment_cleanup_listeners():
    """Регистрирует удаление файла вложения с диска при удалении самого
    сообщения (см. register_teo_cleanup_listeners в teo.py — тот же приём
    и те же причины защиты от повторной регистрации)."""
    global _ticket_attachment_cleanup_registered
    if _ticket_attachment_cleanup_registered:
        return
    _ticket_attachment_cleanup_registered = True

    @sa_event.listens_for(PlanTicket, 'after_delete')
    def _delete_attachment_on_ticket_delete(mapper, connection, target):
        if not target.attachment_filename:
            return
        try:
            folder = current_app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER']
            _remove_file(folder, target.attachment_filename)
        except Exception as e:
            try:
                current_app.logger.warning(f'Не удалось удалить файл вложения при удалении сообщения {target.id}: {e}')
            except Exception:
                pass
