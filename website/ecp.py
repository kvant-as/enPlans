from cryptography import x509
from cryptography.hazmat.backends import default_backend
from website.models import current_utc_time

def check_certificate_expiry(cert_file):
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())

        return cert.not_valid_before <= current_utc_time() <= cert.not_valid_after
    except Exception:
        return False

def validate_certificate_for_sending(uploaded_file):
    if not uploaded_file or uploaded_file.filename == '':
        return False, 'Файл сертификата обязателен.'

    ALLOWED_EXTENSIONS = {'cer'}

    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    if not allowed_file(uploaded_file.filename):
        return False, f'Неверный формат файла. Разрешены только: {", ".join(ALLOWED_EXTENSIONS)}'

    try:
        uploaded_file.seek(0)
        if not check_certificate_expiry(uploaded_file):
            return False, 'Срок действия сертификата истёк.'
        uploaded_file.seek(0)
        return True, None

    except Exception as e:
        return False, f'Ошибка при проверке сертификата: {str(e)}'

# cer_path = 'certificatenon.cer'
# print(check_certificate_expiry(cer_path))