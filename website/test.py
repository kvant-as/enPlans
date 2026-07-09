from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone, timedelta

def get_current_utc():
    return datetime.now(timezone.utc)

def get_attribute_value(attributes):
    return attributes[0].value if attributes else None

def get_certificate_owner_info(cert_file):
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        subject = cert.subject
        
        owner_info = {
            'common_name': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)),
            'given_name': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.GIVEN_NAME)),
            'surname': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.SURNAME)),
            'organization': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)),
            'organizational_unit': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.ORGANIZATIONAL_UNIT_NAME)),
            'email': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.EMAIL_ADDRESS)),
            'country': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.COUNTRY_NAME)),
            'state': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.STATE_OR_PROVINCE_NAME)),
            'locality': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.LOCALITY_NAME)),
            'street': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.STREET_ADDRESS)),
            'postal_code': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.POSTAL_CODE)),
            'title': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.TITLE)),
            'serial_number': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)),
            'user_id': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.USER_ID)),
            'dn_qualifier': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.DN_QUALIFIER)),
            'full_subject': str(subject)
        }
        
        return owner_info
        
    except Exception as e:
        return {'error': str(e)}

def get_certificate_validity(cert_file):
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        not_valid_before = cert.not_valid_before_utc
        not_valid_after = cert.not_valid_after_utc
        now_utc = get_current_utc()
        
        validity_info = {
            'not_valid_before': not_valid_before,
            'not_valid_after': not_valid_after,
            'not_valid_before_local': not_valid_before.astimezone(timezone(timedelta(hours=3))),
            'not_valid_after_local': not_valid_after.astimezone(timezone(timedelta(hours=3))),
            'is_valid': not_valid_before <= now_utc <= not_valid_after,
            'days_until_expiry': (not_valid_after - now_utc).days if not_valid_after > now_utc else 0,
            'days_since_issue': (now_utc - not_valid_before).days
        }
        
        return validity_info
        
    except Exception as e:
        return {'error': str(e)}

def get_certificate_fingerprint(cert_file):
    from cryptography.hazmat.primitives import hashes
    
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        fingerprint_sha1 = cert.fingerprint(hashes.SHA1())
        fingerprint_sha256 = cert.fingerprint(hashes.SHA256())
        
        fingerprint_info = {
            'sha1': ':'.join(f'{b:02x}' for b in fingerprint_sha1),
            'sha256': ':'.join(f'{b:02x}' for b in fingerprint_sha256),
            'serial_number': hex(cert.serial_number),
            'version': cert.version.value
        }
        
        return fingerprint_info
        
    except Exception as e:
        return {'error': str(e)}

def get_certificate_issuer_info(cert_file):
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        issuer = cert.issuer
        
        issuer_info = {
            'common_name': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)),
            'organization': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)),
            'country': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.COUNTRY_NAME)),
            'organizational_unit': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.ORGANIZATIONAL_UNIT_NAME)),
            'full_issuer': str(issuer)
        }
        
        return issuer_info
        
    except Exception as e:
        return {'error': str(e)}

def get_all_certificate_data(cert_file):
    try:
        cert_data = cert_file.read()
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        subject = cert.subject
        issuer = cert.issuer
        now_utc = get_current_utc()
        not_valid_before = cert.not_valid_before_utc
        not_valid_after = cert.not_valid_after_utc
        
        from cryptography.hazmat.primitives import hashes
        fingerprint_sha1 = cert.fingerprint(hashes.SHA1())
        fingerprint_sha256 = cert.fingerprint(hashes.SHA256())
        
        all_data = {
            'owner': {
                'common_name': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)),
                'given_name': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.GIVEN_NAME)),
                'surname': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.SURNAME)),
                'organization': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)),
                'organizational_unit': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.ORGANIZATIONAL_UNIT_NAME)),
                'email': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.EMAIL_ADDRESS)),
                'country': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.COUNTRY_NAME)),
                'state': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.STATE_OR_PROVINCE_NAME)),
                'locality': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.LOCALITY_NAME)),
                'title': get_attribute_value(subject.get_attributes_for_oid(x509.NameOID.TITLE)),
                'full_subject': str(subject)
            },
            'issuer': {
                'common_name': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)),
                'organization': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)),
                'country': get_attribute_value(issuer.get_attributes_for_oid(x509.NameOID.COUNTRY_NAME)),
                'full_issuer': str(issuer)
            },
            'validity': {
                'not_valid_before': not_valid_before,
                'not_valid_after': not_valid_after,
                'not_valid_before_local': not_valid_before.astimezone(timezone(timedelta(hours=3))),
                'not_valid_after_local': not_valid_after.astimezone(timezone(timedelta(hours=3))),
                'is_valid': not_valid_before <= now_utc <= not_valid_after,
                'days_until_expiry': (not_valid_after - now_utc).days if not_valid_after > now_utc else 0,
                'days_since_issue': (now_utc - not_valid_before).days
            },
            'fingerprint': {
                'sha1': ':'.join(f'{b:02x}' for b in fingerprint_sha1),
                'sha256': ':'.join(f'{b:02x}' for b in fingerprint_sha256),
                'serial_number': hex(cert.serial_number),
                'version': cert.version.value
            }
        }
        
        return all_data
        
    except Exception as e:
        return {'error': str(e)}

try:
    with open('certificate.cer', 'rb') as f:
        data = get_all_certificate_data(f)
        
        if 'error' in data:
            print(f"Ошибка: {data['error']}")
        else:
            print("=" * 60)
            print("ДАННЫЕ ВЛАДЕЛЬЦА СЕРТИФИКАТА")
            print("=" * 60)
            
            if data['owner']['surname']:
                print(f"Фамилия: {data['owner']['surname']}")
            if data['owner']['given_name']:
                print(f"Имя: {data['owner']['given_name']}")
            if data['owner']['common_name']:
                print(f"Полное имя (CN): {data['owner']['common_name']}")
            if data['owner']['organization']:
                print(f"Организация: {data['owner']['organization']}")
            if data['owner']['title']:
                print(f"Должность: {data['owner']['title']}")
            if data['owner']['email']:
                print(f"Email: {data['owner']['email']}")
            if data['owner']['country']:
                print(f"Страна: {data['owner']['country']}")
            if data['owner']['state']:
                print(f"Регион: {data['owner']['state']}")
            if data['owner']['locality']:
                print(f"Населенный пункт: {data['owner']['locality']}")
            
            print("\n" + "=" * 60)
            print("ИНФОРМАЦИЯ О СРОКЕ ДЕЙСТВИЯ")
            print("=" * 60)
            print(f"Действителен до: {data['validity']['not_valid_after_local'].strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"Осталось дней: {data['validity']['days_until_expiry']}")
            print(f"Статус: {'Действителен' if data['validity']['is_valid'] else 'Недействителен'}")
            
            print("\n" + "=" * 60)
            print("ТЕХНИЧЕСКИЕ ДАННЫЕ")
            print("=" * 60)
            print(f"Серийный номер: {data['fingerprint']['serial_number']}")
            print(f"Отпечаток SHA256: {data['fingerprint']['sha256']}")
            print(f"Версия: v{data['fingerprint']['version']}")
            
except FileNotFoundError:
    print("Файл 'certificate.cer' не найден")
except Exception as e:
    print(f"Ошибка: {e}")