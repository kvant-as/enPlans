"""Проверка сертификата ЭЦП — пока используется только в демо-модалке
"Проверка ЭЦП" на шаге отправки плана (см. static/js/ecp-mock-modal.js,
способ "Сертификат ЭЦП"). Способ "Аппаратный ключ" остаётся чисто
визуальным макетом — сюда не стучится.

Реальной привязки к аккаунту/плану (как раньше делала полноценная
верификация аккаунта — см. историю, она была убрана целиком) больше нет:
это разовая проверка файла на лету, ничего не сохраняется в БД.
"""
import logging
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


def _load_certificate(cert_bytes):
    try:
        return x509.load_pem_x509_certificate(cert_bytes, default_backend())
    except ValueError:
        return x509.load_der_x509_certificate(cert_bytes, default_backend())


def _to_naive_utc(dt):
    """Сертификаты X.509 оперируют временем в UTC; приводим к "наивному"
    UTC, чтобы сравнивать без путаницы с локальным временем приложения."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _log_certificate_debug(cert):
    """Выводит в лог (уровень DEBUG) всё, что удалось достать из
    сертификата — по просьбе отладки проверки ЭЦП: срок действия и
    остальные доступные поля."""
    try:
        not_before = _to_naive_utc(getattr(cert, 'not_valid_before_utc', None) or cert.not_valid_before)
        not_after = _to_naive_utc(getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after)
    except Exception:
        not_before = not_after = None

    try:
        subject = cert.subject.rfc4514_string()
    except Exception:
        subject = None

    try:
        issuer = cert.issuer.rfc4514_string()
    except Exception:
        issuer = None

    try:
        serial = cert.serial_number
    except Exception:
        serial = None

    try:
        sig_algo = cert.signature_algorithm_oid._name
    except Exception:
        sig_algo = None

    try:
        version = cert.version.name
    except Exception:
        version = None

    try:
        fingerprint = cert.fingerprint(cert.signature_hash_algorithm).hex() if cert.signature_hash_algorithm else None
    except Exception:
        fingerprint = None

    # logger.debug(
    #     'ЭЦП-сертификат: subject=%s, issuer=%s, serial=%s, version=%s, '
    #     'signature_algorithm=%s, not_before=%s, not_after=%s, fingerprint=%s',
    #     subject, issuer, serial, version, sig_algo, not_before, not_after, fingerprint,
    # )


def verify_certificate(file_storage):
    """Возвращает (True, None) при успехе либо (False, текст_ошибки для
    пользователя). ``file_storage`` — werkzeug FileStorage из request.files;
    поток перематывается обратно в начало после чтения. Параллельно пишет
    в лог (DEBUG) всё, что смогла прочитать из сертификата."""
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

    _log_certificate_debug(cert)

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

    return True, None
