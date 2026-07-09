import os
from dbfread import DBF
from flask import current_app
import pandas as pd
from werkzeug.security import generate_password_hash

from website.time import TimeByMinsk

def create_database(app, db):
    with app.app_context():
        # db.reflect()
        # db.drop_all()
        db.create_all()
        filling_database(db)


def is_db_empty():
    from .models import User
    return all([
        User.query.count() == 0,
    ])


def read_dbf(file_path, columns):
    data = []
    for record in DBF(file_path):
        row = {col: record[col] for col in columns}
        data.append(row)
    return data


def import_stat_files(db):
    from .models import StatPlan
    from website.utils.stat_import import save_parsed_report, find_organization_by_okpo, OrganizationNotFoundError
    from website.utils.stat_parse import parse_stat_file, extract_okpo_from_filename
    
    stats_dir = os.path.join('website', 'static', 'files', 'stats')
    
    if not os.path.exists(stats_dir):
        current_app.logger.warning(f'Папка со статистикой не найдена: {stats_dir}')
        return
    
    existing_reports = StatPlan.query.count()
    if existing_reports > 0:
        current_app.logger.info(f'В БД уже есть {existing_reports} отчётов. Пропускаем импорт статистики.')
        return
    
    stat_files = []
    for filename in os.listdir(stats_dir):
        if filename.lower().endswith(('.xlsx', '.xls')) and not filename.startswith('~$'):
            file_path = os.path.join(stats_dir, filename)
            stat_files.append((file_path, filename))
    
    if not stat_files:
        current_app.logger.warning('Нет файлов статистики для импорта')
        return
    
    current_app.logger.info(f'Найдено {len(stat_files)} файлов статистики для импорта')
    
    imported_count = 0
    error_count = 0
    
    for file_path, filename in stat_files:
        try:
            current_app.logger.info(f'Импорт файла: {filename}')
            
            parsed = parse_stat_file(file_path, filename)
            
            okpo = extract_okpo_from_filename(filename)
            org = find_organization_by_okpo(okpo)
            
            if org is None:
                current_app.logger.warning(
                    f'Организация с ОКПО "{okpo}" не найдена. '
                    f'Файл: {filename}'
                )
                error_count += 1
                continue

            report = save_parsed_report(
                parsed=parsed,
                organization_id=org.id,
                db=db,
                uploaded_by_id=None,
                replace=True
            )
            
            imported_count += 1
            current_app.logger.info(
                f'Успешно импортирован отчёт {parsed.type} для организации {org.name}'
            )
            
        except OrganizationNotFoundError as e:
            current_app.logger.warning(f'Ошибка: {str(e)}. Файл: {filename}')
            error_count += 1
            db.session.rollback()
        except Exception as e:
            current_app.logger.error(f'Ошибка при импорте файла {filename}: {str(e)}')
            error_count += 1
            db.session.rollback()
    
    current_app.logger.info(
        f'Импорт статистики завершён: импортировано {imported_count} отчётов, '
        f'ошибок: {error_count}'
    )

def filling_database(db):
    if is_db_empty():
        from .models import User, Organization, Unit, Direction, Indicator, Region, News
        current_app.logger.debug('Filling is in progress...')


        ### REGION DATA ###
        region_data = [
            (1, 'Брестская область'),
            (2, 'Витебская область'),
            (3, 'Гомельская область'),
            (4, 'Гродненская область'),
            (5, 'г. Минск'),
            (6, 'Минская область'),
            (7, 'Могилевская область'),
        ]

        for number, name in region_data:
            new_region = Region(number=number, name=name)
            db.session.add(new_region)

        db.session.commit()
        ### ----------- ###

        ### ORGANIZATION DATA ###
        def load_organizations_from_excel():
            base_path = os.path.join('website', 'static', 'files', 'spravochniki')
            
            files = {
                'regular': os.path.join(base_path, 'regulars.xlsx'),
                'coordinator': os.path.join(base_path, 'coordinators.xlsx'),
                'approver': os.path.join(base_path, 'approvers.xlsx')
            }
            
            existing_orgs = {}
            skipped_duplicates = 0
            
            for org_type, file_path in files.items():
                try:
                    if not os.path.exists(file_path):
                        current_app.logger.warning(f'No file: {file_path}')
                        continue
                    
                    df = pd.read_excel(file_path, header=3)
                    df.columns = ['num', 'ynp', 'okpo', 'name']
                    df = df.dropna(subset=['ynp', 'name'])
                    df['ynp'] = df['ynp'].astype(str).str.strip()
                    
                    if 'okpo' in df.columns:
                        df['okpo'] = df['okpo'].apply(lambda x: str(int(x)) if pd.notna(x) and x != '' else '')
                    
                    for _, row in df.iterrows():
                        ynp = str(row['ynp']).strip()
                        name = str(row['name']).strip()
                        okpo = str(row['okpo']).strip() if pd.notna(row['okpo']) and str(row['okpo']).strip() != '' else ''
                        
                        if not okpo or okpo == '' or okpo == 'nan':
                            skipped_duplicates += 1
                            continue
                        
                        existing_org_by_okpo = Organization.query.filter_by(okpo=okpo).first()
                        if existing_org_by_okpo:
                            if ynp in existing_orgs:
                                org = existing_orgs[ynp]
                            else:
                                org = existing_org_by_okpo
                                existing_orgs[ynp] = org
                            
                            if org_type == 'regular':
                                org.is_regular = True
                            elif org_type == 'coordinator':
                                org.is_coordinator = True
                            elif org_type == 'approver':
                                org.is_approver = True
                            skipped_duplicates += 1
                            continue
                        
                        if ynp in existing_orgs:
                            org = existing_orgs[ynp]
                            if org_type == 'regular':
                                org.is_regular = True
                            elif org_type == 'coordinator':
                                org.is_coordinator = True
                            elif org_type == 'approver':
                                org.is_approver = True
                            continue
                        
                        org = Organization(
                            name=name,
                            ynp=ynp if ynp and ynp != 'nan' else None,
                            okpo=okpo if okpo and okpo != 'nan' else None,
                            is_active=True,
                            region_id=None
                        )
                        
                        if org_type == 'regular':
                            org.is_regular = True
                            org.is_coordinator = False
                            org.is_approver = False
                        elif org_type == 'coordinator':
                            org.is_regular = False
                            org.is_coordinator = True
                            org.is_approver = False
                        elif org_type == 'approver':
                            org.is_regular = False
                            org.is_coordinator = False
                            org.is_approver = True
                        
                        db.session.add(org)
                        existing_orgs[ynp] = org
                        
                except Exception as e:
                    current_app.logger.error(f'Error with file {file_path}: {str(e)}')
                    continue
            
            db.session.commit()
            current_app.logger.info(f'Uploaded by {len(existing_orgs)} unique organizations, missing duplicates: {skipped_duplicates}')
        
        def assign_regions_to_organizations():
            try:
                organizations = Organization.query.filter_by(region_id=None).all()
                
                assigned_count = 0
                skipped_count = 0
                deleted_count = 0
                
                for org in organizations:
                    if not org.okpo or org.okpo == '' or org.okpo == 'nan':
                        db.session.delete(org)
                        deleted_count += 1
                        continue
                    
                    okpo_str = str(org.okpo).strip()
                    
                    if len(okpo_str) < 4:
                        db.session.delete(org)
                        deleted_count += 1
                        continue
                    
                    try:
                        region_number = int(okpo_str[-4])
                    except ValueError:
                        db.session.delete(org)
                        deleted_count += 1
                        continue
                    
                    region = Region.query.filter_by(number=region_number).first()
                    if region:
                        org.region_id = region.id
                        assigned_count += 1
                    else:
                        db.session.delete(org)
                        deleted_count += 1
                
                db.session.commit()
                current_app.logger.info(f'Regions assigned to {assigned_count} organizations, deleted {deleted_count}')
            except Exception as e:
                current_app.logger.error(f'Error in assigning regions: {str(e)}')
                db.session.rollback()

        def assign_region_management_to_organizations():
            try:
                search_pattern = '%управление по надзору за рациональным использованием топливно-энергетических ресурсов%'
                
                organizations = Organization.query.filter(
                    Organization.name.ilike(search_pattern),
                    Organization.is_region_management == False
                ).all()
                
                assigned_count = 0
                
                for org in organizations:
                    org.is_region_management = True
                    assigned_count += 1
                
                db.session.commit()
                current_app.logger.info(f'Region management assigned to {assigned_count} organizations')
                
                return {
                    'success': True,
                    'assigned': assigned_count
                }
                
            except Exception as e:
                current_app.logger.error(f'Error in assign_region_management: {str(e)}')
                db.session.rollback()
                return {
                    'success': False,
                    'error': str(e)
                }

        def org_migration():
            try:
                load_organizations_from_excel()
                assign_regions_to_organizations()
                assign_region_management_to_organizations()
                current_app.logger.info('The migration of organizations has been successfully completed')
            except Exception as e:
                current_app.logger.error(f'Migration error: {str(e)}')
                db.session.rollback()
                
        ### ----------- ###
        
        org_migration()

        ### USER DATA ###
        users_data = [
            ('', os.getenv('adminemail1'), os.getenv('adminname1'), os.getenv('adminsecondname1'), os.getenv('adminpatr1'), os.getenv('adminphone1'), True, False, 54),
            ('', os.getenv('adminemail2'), os.getenv('adminname2'), os.getenv('adminsecondname2'), os.getenv('adminpatr2'), os.getenv('adminphone2'), False, False, 290),

            ('', os.getenv('testuser'), 'Иванов', 'Иван', 'Иванович', '+375173382562', False, False, 413),
            ('', os.getenv('auditoremailNadzor'), 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 124),

            ('', 'testrespondent@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, False, 290),
            
            ('', 'testauditorMinskobl@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 783),
            ('', 'testauditorGancevichi@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 728),
            ('', 'testauditorNesvig@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 792),
            ('', 'testauditorLidskoePivo@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 411),
        ]

        for post, email, first_name, last_name, patronymic_name, phone, is_admin, is_auditor, organization_id in users_data:
            if email == os.getenv('testuser'):
                password = os.getenv('testuserpass')
            elif email == os.getenv('auditoremailNadzor'):
                password = os.getenv('auditoremailNadzorpass')
            else:
                password = os.getenv('userpass')
            
            user = User(
                post=post,
                email=email,
                first_name=first_name,
                last_name=last_name,
                patronymic_name=patronymic_name,
                phone=phone,
                is_admin=is_admin,
                is_auditor=is_auditor,
                organization_id=organization_id,
                password=generate_password_hash(password)
            )
            db.session.add(user)
        db.session.commit()
        ### ----------- ###

        ### Unit DATA ###
        unit_data = [
            (1, 'т.у.т.'),
            (2, 'тонн'),
            (3, 'тыс. куб. м'),
            (4, 'т. усл. влажн.'),
            (5, 'пл. куб. м'),
            (6, 'тыс. кВт · ч'),
            (7, 'Гкал'),
            (8, 'шт.'),
            (9, 'ед.'),
            (10, 'киловатт'),
            (11, 'Гкал/ч'),
            (12, 'пог.м'),
            (13, 'кв. м'),
            (14, 'м2'),
            (15, 'Мвт'),
            (16, '%')
        ]
        for id, name in unit_data:
            unit = Unit(
                id = id,
                name=name
            )
            db.session.add(unit)
        db.session.commit()
        ### ----------- ###

        ### Direction DATA ###
        direction_data = [
            # КОТЕЛЬНЫЕ И ПЕЧИ (1011-1021 - экономия)
            (10, '1011', 'Ввод в эксплуатацию электрогенерирующего оборудования на основе паро- и газотурбинных, парогазовых, турбодетандерных и газопоршневых установок', True, False),
            (11, '1012', 'Передача тепловых нагрузок от ведомственных котельных на теплоэлектроцентрали', True, False),
            (8, '1013', 'Замена неэкономичных котлов и печей с низким коэффициентом полезного действия на более эффективные', True, False),
            (8, '1014', 'Замена газогорелочных устройств на энергоэффективные', True, False),
            (8, '1015', 'Внедрение устройств предотвращения накипеобразования на поверхностях нагрева котлов и другого оборудования (магнитно-импульсные и другие)', True, False),
            (8, '1016', 'Перевод котлов с жидких видов топлива на газ', True, False),
            (8, '1017', 'Внедрение котлов малой мощности вместо незагруженных котлов большой мощности', True, False),
            (8, '1018', 'Внедрение автоматизации процессов горения топлива в котлоагрегатах и другом топливоиспользующем оборудовании', True, False),
            (9, '1019', 'Использование возврата конденсата для нужд котельных', True, False),
            (8, '1020', 'Перевод паровых котлов в водогрейный режим', True, False),
            (8, '1021', 'Реконструкция (модернизация) энергоисточников с переводом в автоматический режим работы', True, False),

            # ТЕПЛОСНАБЖЕНИЕ (1111-1199 - экономия)
            (12, '1111', 'Децентрализация теплоснабжения с ликвидацией длинных и незагруженных паро- и теплотрасс', True, False),
            (12, '1112', 'Замена изношенных теплотрасс с внедрением эффективных трубопроводов (предварительно изолированных труб)', True, False),
            (8, '1113', 'Внедрение индивидуальных тепловых пунктов вместо центральных тепловых пунктов', True, False),
            (12, '1114', 'Модернизация тепловой изоляции паропроводов, системы отопления, горячего водоснабжения, запорной арматуры', True, False),
            (8, '1115', 'Установка теплоотражающих экранов за радиаторами отопления', True, False),
            (9, '1116', 'Модернизация теплоиспользующего оборудования', True, False),
            (9, '1199', 'Другие мероприятия по оптимизации теплоснабжения', True, False),

            # НАСОСЫ, ВЕНТИЛЯЦИЯ, КОМПРЕССОРЫ (1211-1224 - экономия)
            (8, '1211', 'Замена насосного оборудования более энергоэффективным', True, False),
            (8, '1212', 'Замена насосного оборудования в котельных на энергосберегающее меньшей мощности', True, False),
            (8, '1213', 'Замена насосного оборудования в системах водопроводно-канализационного хозяйства на энергосберегающее', True, False),
            (8, '1214', 'Замена повысительных, центробежных насосов на энергосберегающие', True, False),
            (9, '1219', 'Другие мероприятия по замене насосного оборудования более энергоэффективным', True, False),
            (8, '1221', 'Внедрение энергоэффективного вентиляционного оборудования', True, False),
            (8, '1222', 'Децентрализация воздухоснабжения с установкой локальных компрессоров', True, False),
            (8, '1223', 'Децентрализация систем удаления отработанного воздуха с установкой локальных отсосов', True, False),
            (8, '1224', 'Децентрализация холодоснабжения с установкой локальных холодильных установок', True, False),

            # ПРОИЗВОДСТВЕННЫЕ ТЕХНОЛОГИИ И ОБОРУДОВАНИЕ (1311-1340 - экономия)
            (9, '1311', 'Внедрение в производство современных энергоэффективных технологий', True, False),
            (9, '1312', 'Внедрение в производство современных энергоэффективных процессов', True, False),
            (9, '1313', 'Повышение энергоэффективности действующих технологий', True, False),
            (9, '1314', 'Повышение энергоэффективности действующих процессов', True, False),
            (9, '1315', 'Повышение энергоэффективности технологического оборудования', True, False),
            (9, '1316', 'Внедрение в производство современного энергоэффективного оборудования', True, False),
            (9, '1317', 'Внедрение в производство современных энергоэффективных материалов', True, False),
            (8, '1321', 'Замена морально устаревших теплообменников на более эффективные', True, False),
            (14, '1322', 'Модернизация изоляции теплообменников', True, False),
            (8, '1330', 'Внедрение энергоэффективных компрессоров', True, False),
            (8, '1340', 'Замена нагревательного оборудования в пищеблоках, прачечных на энергоэффективное', True, False),

            # ЗАМЕЩЕНИЕ УГЛЕВОДОРОДОВ ЭЛЕКТРОЭНЕРГИЕЙ (1411-1419 - экономия)
            (8, '1411', 'Внедрение в производство современного энергоэффективного оборудования с увеличением использования электрической энергии и с замещением углеводородного топлива', True, False),
            (8, '1413', 'Реконструкция (модернизация) энергоисточников с переводом на использование электронагрева', True, False),
            (9, '1419', 'Другие мероприятия, направленные на сокращение использования углеводородного топлива и увеличение использования электрической энергии', True, False),

            # АВТОМАТИЗАЦИЯ И УПРАВЛЕНИЕ (1421-1429 - экономия)
            (9, '1421', 'Автоматизация и роботизация технологических процессов', True, False),
            (9, '1422', 'Внедрение автоматизированной системы управления потреблением энергоресурсов', True, False),
            (9, '1423', 'Мероприятия, направленные на снижение расхода электрической энергии на транспорт в электросетях', True, False),
            (8, '1424', 'Внедрение автоматических систем компенсации реактивной мощности', True, False),
            (8, '1425', 'Внедрение приборов автоматического регулирования в системах тепло-, газо-, и водоснабжения', True, False),
            (8, '1426', 'Внедрение частотно-регулируемых электроприводов на механизмах с переменной нагрузкой (сетевые теплофикационные насосные, канализационные насосные станции, системы водоснабжения, тягодутьевые механизмы котлов и другие)', True, False),
            (9, '1429', 'Другие мероприятия, направленные на автоматизацию процессов в системах энерго-, газо- и водоснабжения', True, False),

            # ОСВЕЩЕНИЕ (1521-1526 - экономия)
            (9, '1521', 'Внедрение автоматических систем управления освещением', True, False),
            (9, '1522', 'Внедрение секционного разделения освещения', True, False),
            (8, '1523', 'Внедрение энергоэффективных светильников уличного освещения', True, False),
            (8, '1524', 'Внедрение энергоэффективных ламп в светильниках уличного освещения', True, False),
            (8, '1525', 'Внедрение энергоэффективных светильников внутреннего освещения', True, False),
            (8, '1526', 'Внедрение энергоэффективных ламп в светильниках внутреннего освещения', True, False),

            # ТЕРМОМОДЕРНИЗАЦИЯ ЗДАНИЙ (1511-1515 - экономия)
            (14, '1511', 'Термореновация ограждающих конструкций зданий, сооружений', True, False),
            (14, '1512', 'Термореновация ограждающих конструкций кровли, подвалов', True, False),
            (14, '1513', 'Применение энергоэффективных материалов при модернизации тепловой изоляции промышленных установок и оборудования (котлоагрегатов, холодильников, теплиц, трубопроводов и др.)', True, False),
            (8, '1514', 'Внедрение инфракрасных излучателей для локального обогрева рабочих мест и в технологических процессах', True, False),
            (14, '1515', 'Замена оконных блоков и входных групп на более энергоэффективные', True, False),

            # МЕСТНЫЕ ТОПЛИВНО-ЭНЕРГЕТИЧЕСКИЕ РЕСУРСЫ (МТЭР) - ВВОД НОВЫХ ИСТОЧНИКОВ (1621-1627 - увеличение)
            (8, '1621', 'Ввод нового энергоисточника, работающего на топливной щепе', False, True),
            (8, '1622', 'Ввод нового энергоисточника, работающего на древесных пеллетах, гранулах', False, True),
            (8, '1623', 'Ввод нового энергоисточника, работающего на отходах деревообработки, лесозаготовок, сельскохозяйственной деятельности', False, True),
            (8, '1624', 'Ввод нового энергоисточника, работающего на торфяном топливе', False, True),
            (8, '1625', 'Ввод нового энергоисточника, работающего на твердых коммунальных отходах, включая RDF-топливо', False, True),
            (8, '1626', 'Ввод нового энергоисточника, работающего на прочих местных топливно-энергетических ресурсах', False, True),
            (8, '1627', 'Ввод нового энергоисточника, работающего на древесных брикетах', False, True),

            # МТЭР - РЕКОНСТРУКЦИЯ С ПЕРЕВОДОМ (1641-1646 - увеличение)
            (8, '1641', 'Реконструкция (модернизация) энергоисточников с переводом на использование топливной щепы', False, True),
            (8, '1642', 'Реконструкция (модернизация) энергоисточников с переводом на использование древесных пеллетов, гранул', False, True),
            (8, '1643', 'Реконструкция (модернизация) энергоисточников с переводом на использование отходов деревообработки, лесозаготовок, сельскохозяйственной деятельности', False, True),
            (8, '1644', 'Реконструкция (модернизация) энергоисточников с переводом на использование торфяного топлива', False, True),
            (8, '1645', 'Реконструкция (модернизация) энергоисточников с переводом на использование прочих местных топливно-энергетических ресурсов', False, True),
            (8, '1646', 'Реконструкция (модернизация) энергоисточников с переводом на использование древесных брикетов', False, True),

            # ВОЗОБНОВЛЯЕМЫЕ ИСТОЧНИКИ ЭНЕРГИИ (ВИЭ) 1651-1655 - и туда, и туда
            (8, '1651', 'Внедрение мероприятий по увеличению использования энергии воды', True, True),
            (8, '1652', 'Внедрение мероприятий по увеличению использования энергии ветра', True, True),
            (8, '1653', 'Внедрение мероприятий по увеличению использования энергии солнца', True, True),
            (8, '1654', 'Внедрение мероприятий по увеличению использования геотермальных источников энергии', True, True),
            (8, '1655', 'Внедрение мероприятий по установке тепловых насосов, использующих энергию из окружающей среды', True, True),
            
            # 1656 - увеличение
            (8, '1656', 'Внедрение биогазовых установок', False, True),
            
            # 1699 - увеличение
            (9, '1699', 'Другие мероприятия по увеличению использования местных топливно-энергетических ресурсов', False, True),

            # ВТОРИЧНЫЕ ЭНЕРГЕТИЧЕСКИЕ РЕСУРСЫ (ВЭР) 1710-1810 - экономия
            (8, '1710', 'Утилизация тепловых вторичных энергетических ресурсов', True, False),
            (8, '1721', 'Внедрение тепловых насосов компрессорного типа в системах теплоснабжения и холодоснабжения', True, False),
            (8, '1722', 'Установка абсорбционных бромисто-литиевых тепловых насосов в системах теплоснабжения и холодоснабжения', True, False),
            (8, '1810', 'Ввод энергогенерирующего и технологического оборудования, работающего с использованием вторичных энергетических ресурсов избыточного давления', True, False),

            # ПРОЧИЕ (1900 - экономия)
            (9, '1900', 'Прочие мероприятия по повышению эффективности использования топливно-энергетических ресурсов', True, False),
            
            # ПРОЧИЕ
            (None, '0001', 'Январь-Март', True, False),
            (None, '0002', 'Январь-Июнь', True, False),
            (None, '0003', 'Январь-Сентябрь', True, False),
            (None, '0004', 'Январь-Декабрь', True, False),
            
            (None, '0001', 'Январь-Март', False, True),
            (None, '0002', 'Январь-Июнь', False, True),
            (None, '0003', 'Январь-Сентябрь', False, True),
            (None, '0004', 'Январь-Декабрь', False, True)
        ]

        for id_unit, code, name, is_econom, is_increase in direction_data:
            direction = Direction(
                id_unit=id_unit,
                code=code,
                name=name,
                is_econom=is_econom,
                is_increase=is_increase
            )
            db.session.add(direction)
        db.session.commit()
        # ### ----------- ###

        ### Indicator DATA ###
        indicator_data = [
            (1, '1000', 'Котельно-печное топливо израсходовано всего, в том числе', 1.000, True, 1, 1, False, False),
            
            (3, '2000', 'газ природный', 1.150, False, 1, 2, False, False),
            (2, '2001', 'мазут топочный', 1.370, False, 1, 3, False, False),
            (2, '2002', 'топливо печное бытовое', 1.450, False, 1, 4, False, False),
            (2, '2003', 'кокс металлургический, коксик и коксовая мелочь', 0.990, False, 1, 5, False, False),
            (2, '2004', 'кокс нефтяной', 1.130, False, 1, 6, False, False),
            (2, '2005', 'уголь и продукты переработки угля', 0.814, False, 1, 7, False, False),
            (2, '2006', 'газы углеводородные сжиженные', 1.570, False, 1, 8, False, False),
            (2, '2007', 'газы углеводородные нефтепереработки', 1.500, False, 1, 9, False, False),
            (1, '2008', 'метано-водородная фракция производства полиэтилена', 1.000, False, 1, 10, False, False),
            (1, '2009', 'отработанные нефтепродукты', 1.000, False, 1, 11, False, False),
            (3, '2010', 'газ природный попутный', 1.300, False, 1, 12, True, False),  # is_local = True
            (4, '2011', 'торф топливный фрезерный и кусковой', 0.340, False, 1, 13, True, False),  # is_local = True
            (4, '2012', 'брикеты и полубрикеты торфяные', 0.600, False, 1, 14, True, False),  # is_local = True
            (1, '2013', 'использованные автопокрышки', 1.000, False, 1, 15, True, False),  # is_local = True
            (1, '2014', 'биогаз', 1.000, False, 1, 16, False, True),  # is_renewable = True
            (5, '2015', 'дрова', 0.228, False, 1, 17, False, True),  # is_renewable = True
            (5, '2016', 'топливная щепа', 0.187, False, 1, 18, False, True),  # is_renewable = True
            (1, '2017', 'древесные гранулы, пеллеты', 1.000, False, 1, 19, False, True),  # is_renewable = True
            (1, '2018', 'древесные брикеты', 1.000, False, 1, 20, False, True),  # is_renewable = True
            (1, '2019', 'RDF-топливо', 1.000, False, 1, 21, False, True),  # is_renewable = True
            (1, '2020', 'отходы лесозаготовок и деревообработки', 1.000, False, 1, 22, False, True),  # is_renewable = True
            (1, '2021', 'отходы сельскохозяйственной деятельности и прочие виды природного топлива', 1.000, False, 1, 23, False, True),  # is_renewable = True
            (1, '2022', 'сульфатные и сульфитные щелока целлюлозно-бумажной промышленности', 1.000, False, 1, 24, False, True),  # is_renewable = True
                     
            (1, '2023', 'прочие отходы', 1.000, False, 1, 25, False, False),
            (1, '2024', 'прочие виды топлива', 1.000, False, 1, 26, False, False),
            
            (1, '1796', 'из него местные виды топлива и отходы', 1.000, True, 1.1, 3, False, False),
            (1, '1797', 'из них возобновляемые', 1.000, True, 1.2, 4, False, False),
            
            (6, '1105', 'Электроэнергия израсходовано всего', 0.123, True, 2, 5, False, False),
            (6, '1405', 'Электроэнергия, выработанная собственными энергоисточниками, в том числе', 0.123, True, 2, 6, False, False),
            (6, '1425', 'энергия воды, ветра, солнца, геотермальных источников', 0.123, True, 2, 7, False, False),
            (7, '1104', 'Теплоэнергия израсходовано всего', 0.143, True, 3, 8, False, False),
            (7, '1404', 'Теплоэнергия, произведенная собственными энергоисточниками, в том числе', 0.143, True, 3, 9, False, False),
            (7, '1424', 'энергия воды, ветра, солнца, геотермальных источников', 0.143, True, 3, 10, False, False),
            (1, '260', 'Суммарное потребление ТЭР', 1.000, True, 4, 11, False, False),
            
            (1, '9999', 'Годовая экономия ТЭР от энергосберегающих мероприятий всего', 1.000, True, 5, 12, False, False),
            (1, '9900', 'Ожидаемая экономия ТЭР от внедрения мероприятий в текущем году', 1.000, True, 5, 13, False, False),
            (1, '9910', 'Экономия ТЭР от мероприятий предыдущего года внедрения, в том числе:', 1.000, True, 5, 14, False, False),
            (1, '9911', 'январь-март', 1.000, True, 5, 15, False, False),
            (1, '9912', 'январь-июнь', 1.000, True, 5, 16, False, False),
            (1, '9913', 'январь-сентябрь', 1.000, True, 5, 17, False, False),
            (1, '9914', 'январь-декабрь', 1.000, True, 5, 18, False, False),
            (16, '9915', 'Целевой показатель энергосбережения', 1.000, True, 6, 19, False, False),
            (16, '9916', 'Целевой показатель по доле местных ТЭР в КПТ', 1.000, True, 7, 20, False, False),
            (16, '9917', 'Целевой показатель по доле возобновляемых источников энергии в КПТ', 1.000, True, 8, 21, False, False)
        ]
        from website.utils.plans import to_decimal_3
        for IdUnit, CodeIndicator, NameIndicator, CoeffToTut, IsMandatory, Group, RowN, is_local, is_renewable in indicator_data:
            indicator = Indicator(
                id_unit=IdUnit,
                code=CodeIndicator,
                name=NameIndicator,
                CoeffToTut=to_decimal_3(CoeffToTut),
                IsMandatory=IsMandatory,
                Group=Group,
                RowN=RowN,
                is_local=is_local,
                is_renewable=is_renewable
            )
            db.session.add(indicator)
        db.session.commit()
        
        news_data = [
            ('Формирование планов мероприятий по энергосбережению', 
            'Автоматизированный комплекс для создания и представления для согласования планов мероприятий по энергосбережению организаций. Система позволяет формировать планы, отслеживать их выполнение и получать аналитические отчеты по энергоэффективности.', 
            'update_v2.png', 
            True, 
            TimeByMinsk(), 
            1),
            # ('Новый дизайн интерфейса', 
            # 'Представляем обновлённый дизайн личного кабинета и навигации. Интерфейс стал более удобным и интуитивно понятным.', 
            # 'design.png', 
            # True, 
            # TimeByMinsk(), 
            # 1),
        ]

        for title, content, image_url, is_published, published_at, views_count in news_data:
            news = News(
                title=title,
                content=content,
                image_url=image_url,
                is_published=is_published,
                published_at=published_at,
                views_count=views_count
            )
            db.session.add(news)
        db.session.commit()
        
        current_app.logger.debug('The filling is finished!')
        
        try:
            import_stat_files(db)
        except Exception as e:
            current_app.logger.error(f'Ошибка при импорте статистических файлов: {str(e)}')
        
    else:
        current_app.logger.debug('The database already contains the data!')