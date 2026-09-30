"""Проверка сертификата ЭЦП при отправке плана на согласование.

По аналогии с ErespondentN (website/ecp.py), где проверяется только срок
действия сертификата, — здесь дополнительно сверяем УНП организации,
записанный в самом сертификате, с УНП организации, которой принадлежит
план. Такой сверки раньше не было вообще ни в одном из приложений —
сертификат в enPlans до сих пор проверялся только по расширению файла на
клиенте (.cer), сервер его содержимое не читал.
"""
import re
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend


def _load_certificate(cert_bytes):
    try:
        return x509.load_pem_x509_certificate(cert_bytes, default_backend())
    except ValueError:
        return x509.load_der_x509_certificate(cert_bytes, default_backend())


def _to_naive_utc(dt):
    """Сертификаты X.509 оперируют временем в UTC; приводим к "наивному"
    UTC, чтобы сравнивать без путаницы с локальным временем приложения
    (common_models.current_utc_time на самом деле возвращает MSK — здесь
    сознательно его не используем)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _extract_unp_candidates(cert):
    """УНП в белорусских сертификатах ЭЦП встречается в Subject в разных
    полях в зависимости от удостоверяющего центра (serialNumber, O, CN и
    т.п.). Вместо привязки к конкретному OID ищем все 9-значные
    последовательности цифр в текстовом представлении Subject — УНП всегда
    ровно 9 цифр (см. common_models.validate_ynp)."""
    subject_text = cert.subject.rfc4514_string()
    return set(re.findall(r'\d{9}', subject_text))


def verify_certificate(file_storage, expected_unp=None):
    """Возвращает (True, None) при успехе либо (False, текст_ошибки для
    пользователя). ``file_storage`` — werkzeug FileStorage из request.files;
    поток перематывается обратно в начало после чтения, чтобы вызывающий
    код при необходимости мог сохранить файл повторно."""
    try:
        cert_bytes = file_storage.read()
    except Exception:
        return False, 'Не удалось прочитать файл сертификата.'
    finally:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass

    if not cert_bytes:
        return False, 'Файл сертификата пуст.'

    try:
        cert = _load_certificate(cert_bytes)
    except Exception:
        return False, 'Не удалось разобрать файл — убедитесь, что это корректный файл сертификата (.cer).'

    now = datetime.utcnow()
    try:
        not_before = _to_naive_utc(getattr(cert, 'not_valid_before_utc', None) or cert.not_valid_before)
        not_after = _to_naive_utc(getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after)
    except Exception:
        return False, 'Не удалось прочитать срок действия сертификата.'

    if now < not_before:
        return False, 'Срок действия сертификата ещё не наступил.'
    if now > not_after:
        return False, 'Срок действия сертификата истёк.'

    if expected_unp:
        found = _extract_unp_candidates(cert)
        if expected_unp not in found:
            return False, f'Сертификат не принадлежит организации плана (УНП {expected_unp} не найден в сертификате).'

    return True, None
