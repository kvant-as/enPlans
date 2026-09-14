import os
from flask import Blueprint, jsonify, request
import pandas as pd
from werkzeug.security import generate_password_hash

from common_models import current_utc_time
from website import csrf
from common_models.logs import get_logger

db_bp = Blueprint('db_bp', __name__, url_prefix='/database/')

logger = get_logger()

def fill_organizations(db):
    from ..models import Organization, Region
    
    def load_organizations_from_excel():
        base_path = os.path.join('website', 'static', 'files', 'spravochniki')
        
        files = {
            'regular': os.path.join(base_path, 'regulars.xlsx'),
            'coordinator': os.path.join(base_path, 'coordinators.xlsx'),
            'approver': os.path.join(base_path, 'approvers.xlsx')
        }
        
        existing_orgs = {}
        skipped_duplicates = 0
        created_count = 0
        updated_count = 0
        
        for org_type, file_path in files.items():
            try:
                if not os.path.exists(file_path):
                    logger.warning(f'No file: {file_path}')
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
                        org = existing_org_by_okpo
                        updated_count += 1
                        
                        if org_type == 'regular':
                            org.is_regular = True
                        elif org_type == 'coordinator':
                            org.is_coordinator = True
                        elif org_type == 'approver':
                            org.is_approver = True
                        
                        existing_orgs[ynp] = org
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
                        full_name=name,
                        ynp=ynp if ynp and ynp != 'nan' else None,
                        okpo=okpo if okpo and okpo != 'nan' else None,
                        is_active=True,
                        region_id=None,
                        is_regular=False,
                        is_coordinator=False,
                        is_approver=False,
                        is_region_management=False
                    )
                    
                    if org_type == 'regular':
                        org.is_regular = True
                    elif org_type == 'coordinator':
                        org.is_coordinator = True
                    elif org_type == 'approver':
                        org.is_approver = True
                    
                    db.session.add(org)
                    existing_orgs[ynp] = org
                    created_count += 1
                    
            except Exception as e:
                logger.error(f'Error with file {file_path}: {str(e)}')
                continue
        
        db.session.commit()
        logger.info(
            f'Организации: создано {created_count}, обновлено {updated_count}, '
            f'пропущено дубликатов {skipped_duplicates}'
        )
    
    def assign_regions_to_organizations():
        organizations = Organization.query.filter_by(region_id=None).all()
        
        assigned_count = 0
        deleted_count = 0
        skipped_count = 0
        
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
        logger.info(
            f'Регионы: назначено {assigned_count} организациям, '
            f'удалено {deleted_count} организаций без региона'
        )
    
    def assign_region_management_to_organizations():
        search_pattern = '%управление по надзору за рациональным использованием ТЭР%'
        
        organizations = Organization.query.filter(
            Organization.full_name.ilike(search_pattern),
            Organization.is_region_management == False
        ).all()
        
        assigned_count = 0
        
        for org in organizations:
            org.is_region_management = True
            assigned_count += 1
        
        db.session.commit()
        logger.info(
            f'Региональное управление: назначено {assigned_count} организациям'
        )
    
    logger.info('Начинаем загрузку организаций...')
    load_organizations_from_excel()
    assign_regions_to_organizations()
    assign_region_management_to_organizations()
    logger.info('Загрузка организаций завершена')


def fill_users(db):
    from ..models import User
    
    users_data = [
        # ('', os.getenv('admin_email'), os.getenv('admin_name'), os.getenv('admin_secondname'), os.getenv('admin_patr'), os.getenv('admin_phone'), True, False, 54),
        ('', os.getenv('testuser_email_1'), os.getenv('testuser_name_1'), os.getenv('testuser_secondname_1'), os.getenv('testuser_patr_1'), os.getenv('testuser_phone_1'), False, False, 290),
        ('', os.getenv('testuser_email_2'), os.getenv('testuser_name_2'), os.getenv('testuser_secondname_2'), os.getenv('testuser_patr_2'), os.getenv('testuser_phone_2'), False, False, 290),
        ('', os.getenv('testuserdepart_email_1'), os.getenv('testuserdepart_name_1'), os.getenv('testuserdepart_secondname_1'), os.getenv('testuserdepart_patr_1'), os.getenv('testuserdepart_phone_1'), False, False, 290),
        ('', os.getenv('testuserdepart_email_2'), os.getenv('testuserdepart_name_2'), os.getenv('testuserdepart_secondname_2'), os.getenv('testuserdepart_patr_2'), os.getenv('testuserdepart_phone_2'), False, False, 290),
        ('', 'testauditorMinskobl@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 783),
        ('', 'testauditorGancevichi@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 728),
        ('', 'testauditorNesvig@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 792),
        ('', 'testauditorLidskoePivo@gmail.com', 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 411),
    ]

    for post, email, first_name, last_name, patronymic_name, telephone, is_admin, is_auditor, organization_id in users_data:
        if email == os.getenv('testuserdepart_email_1'):
            password = os.getenv('testuserdepart_pass_1')
        elif email == os.getenv('testuserdepart_email_2'):
            password = os.getenv('testuserdepart_pass_2')
        else:
            password = os.getenv('userpass')
        
        user = User(
            post=post,
            email=email,
            first_name=first_name,
            last_name=last_name,
            patronymic_name=patronymic_name,
            telephone=telephone,
            is_admin=is_admin,
            is_auditor=is_auditor,
            organization_id=organization_id,
            password=generate_password_hash(password)
        )
        db.session.add(user)
    db.session.commit()
    logger.info(f'Добавлено {len(users_data)} пользователей')


def fill_units(db):
    from ..models import Unit
    
    if Unit.query.count() > 0:
        logger.info('Единицы измерения уже заполнены')
        return
    
    unit_data = [
        (1, 'т у.т.'),
        (2, 'тонн'),
        (3, 'тыс. куб. м'),
        (4, 'т усл. влажн.'),
        (5, 'плотн. куб. м'),
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
        unit = Unit(id=id, name=name)
        db.session.add(unit)
    db.session.commit()
    logger.info(f'Добавлено {len(unit_data)} единиц измерения')


def fill_directions(db):
    from ..models import Direction
    
    if Direction.query.count() > 0:
        logger.info('Направления уже заполнены')
        return
    
    direction_data = [
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
        (9, '1099', 'Другие мероприятия по повышению эффективности работы котельных', True, False),
        (12, '1111', 'Децентрализация теплоснабжения с ликвидацией длинных и незагруженных паро- и теплотрасс', True, False),
        (12, '1112', 'Замена изношенных теплотрасс с внедрением эффективных трубопроводов (предварительно изолированных труб)', True, False),
        (8, '1113', 'Внедрение индивидуальных тепловых пунктов вместо центральных тепловых пунктов', True, False),
        (12, '1114', 'Модернизация тепловой изоляции паропроводов, системы отопления, горячего водоснабжения, запорной арматуры', True, False),
        (9, '1115', 'Установка теплоотражающих экранов за радиаторами отопления', True, False),
        (9, '1116', 'Модернизация теплоиспользующего оборудования', True, False),
        (9, '1199', 'Другие мероприятия по оптимизации теплоснабжения', True, False),
        (8, '1211', 'Замена насосного оборудования более энергоэффективным', True, False),
        (8, '1212', 'Замена насосного оборудования в котельных на энергосберегающее меньшей мощности', True, False),
        (8, '1213', 'Замена насосного оборудования в системах водопроводно-канализационного хозяйства на энергосберегающее', True, False),
        (8, '1214', 'Замена повысительных, центробежных насосов на энергосберегающие', True, False),
        (8, '1219', 'Другие мероприятия по замене насосного оборудования более энергоэффективным', True, False),
        (8, '1221', 'Внедрение энергоэффективного вентиляционного оборудования', True, False),
        (8, '1222', 'Децентрализация воздухоснабжения с установкой локальных компрессоров', True, False),
        (8, '1223', 'Децентрализация систем удаления отработанного воздуха с установкой локальных отсосов', True, False),
        (8, '1224', 'Децентрализация холодоснабжения с установкой локальных холодильных установок', True, False),
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
        (8, '1411', 'Внедрение в производство современного энергоэффективного оборудования с увеличением использования электрической энергии и с замещением углеводородного топлива', True, False),
        (8, '1413', 'Реконструкция (модернизация) энергоисточников с переводом на использование электронагрева', True, False),
        (9, '1419', 'Другие мероприятия, направленные на сокращение использования углеводородного топлива и увеличение использования электрической энергии', True, False),
        (9, '1421', 'Автоматизация и роботизация технологических процессов', True, False),
        (9, '1422', 'Внедрение автоматизированной системы управления потреблением энергоресурсов', True, False),
        (9, '1423', 'Мероприятия, направленные на снижение расхода электрической энергии на транспорт в электросетях', True, False),
        (8, '1424', 'Внедрение автоматических систем компенсации реактивной мощности', True, False),
        (8, '1425', 'Внедрение приборов автоматического регулирования в системах тепло-, газо-, и водоснабжения', True, False),
        (8, '1426', 'Внедрение частотно-регулируемых электроприводов на механизмах с переменной нагрузкой (сетевые теплофикационные насосные, канализационные насосные станции, системы водоснабжения, тягодутьевые механизмы котлов и другие)', True, False),
        (9, '1429', 'Другие мероприятия, направленные на автоматизацию процессов в системах энерго-, газо- и водоснабжения', True, False),
        (9, '1521', 'Внедрение автоматических систем управления освещением', True, False),
        (9, '1522', 'Внедрение секционного разделения освещения', True, False),
        (8, '1523', 'Внедрение энергоэффективных светильников уличного освещения', True, False),
        (8, '1524', 'Внедрение энергоэффективных ламп в светильниках уличного освещения', True, False),
        (8, '1525', 'Внедрение энергоэффективных светильников внутреннего освещения', True, False),
        (8, '1526', 'Внедрение энергоэффективных ламп в светильниках внутреннего освещения', True, False),
        (14, '1511', 'Термореновация ограждающих конструкций зданий, сооружений', True, False),
        (14, '1512', 'Термореновация ограждающих конструкций кровли, подвалов', True, False),
        (14, '1513', 'Применение энергоэффективных материалов при модернизации тепловой изоляции промышленных установок и оборудования (котлоагрегатов, холодильников, теплиц, трубопроводов и др.)', True, False),
        (8, '1514', 'Внедрение инфракрасных излучателей для локального обогрева рабочих мест и в технологических процессах', True, False),
        (14, '1515', 'Замена оконных блоков и входных групп на более энергоэффективные', True, False),
        (11, '1610', 'Ввод теплоэлектроцентралей, работающих на местных топливно-энергетических ресурсах  ', False, True),
        (8, '1621', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на топливной щепе', False, True),
        (8, '1622', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на древесных пеллетах (гранулах, брикетах) ', False, True),
        (8, '1623', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на отходах деревообработки, лесозаготовок, сельскохозяйственной деятельности ', False, True),
        (8, '1624', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на торфяном топливе ', False, True),
        (8, '1625', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на твердых коммунальных отходах, включая RDF-топливо', False, True),
        (8, '1626', 'Ввод новых котлов и другого топливоиспользующего оборудования, работающего на прочих местных топливно-энергетических ресурсах ', False, True),
        (8, '1631', 'Ввод энергогенерирующего и технологического оборудования, работающего с использованием отходов деревообработки и лесозаготовок ', False, True),
        (8, '1632', 'Ввод энергогенерирующего и технологического оборудования, работающего с использованием отходов сельскохозяйственной деятельности', False, True),
        (8, '1641', 'Реконструкция (модернизация) энергоисточников с переводом на использование топливной щепы', False, True),
        (8, '1642', 'Реконструкция (модернизация) энергоисточников с переводом на использование древесных пеллетов, гранул', False, True),
        (8, '1643', 'Реконструкция (модернизация) энергоисточников с переводом на использование отходов деревообработки, лесозаготовок, сельскохозяйственной деятельности', False, True),
        (8, '1644', 'Реконструкция (модернизация) энергоисточников с переводом на использование торфяного топлива', False, True),
        (8, '1645', 'Реконструкция (модернизация) энергоисточников с переводом на использование прочих местных топливно-энергетических ресурсов', False, True),
        (8, '1651', 'Внедрение мероприятий по увеличению использования энергии воды', True, True),
        (8, '1652', 'Внедрение мероприятий по увеличению использования энергии ветра', True, True),
        (8, '1653', 'Внедрение мероприятий по увеличению использования энергии солнца', True, True),
        (8, '1654', 'Внедрение мероприятий по увеличению использования геотермальных источников энергии', True, True),
        (8, '1655', 'Внедрение мероприятий по установке тепловых насосов, использующих энергию из окружающей среды', True, True),
        (8, '1656', 'Внедрение биогазовых установок', False, True),
        (9, '1699', 'Другие мероприятия по увеличению использования местных топливно-энергетических ресурсов', False, True),
        (8, '1710', 'Утилизация тепловых вторичных энергетических ресурсов', True, False),
        (8, '1721', 'Внедрение тепловых насосов компрессорного типа в системах теплоснабжения и холодоснабжения', True, False),
        (8, '1722', 'Установка абсорбционных бромисто-литиевых тепловых насосов в системах теплоснабжения и холодоснабжения', True, False),
        (8, '1810', 'Ввод энергогенерирующего и технологического оборудования, работающего с использованием вторичных энергетических ресурсов избыточного давления', True, False),
        (9, '1900', 'Прочие мероприятия по повышению эффективности использования топливно-энергетических ресурсов', True, False),
        
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
    logger.info(f'Добавлено {len(direction_data)} направлений')


def fill_indicators(db):
    from ..models import Indicator
    from website.utils.plans import to_decimal_3
    
    if Indicator.query.count() > 0:
        logger.info('Индикаторы уже заполнены')
        return
    
    # Коды строк соответствуют таблице "КОДЫ строк для enPlans" (были
    # изменены — см. миграцию c776c34b880a в common_models).
    indicator_data = [
        (1, '1101', 'Котельно-печное топливо (КПТ), израсходовано всего, в том числе:', 1.000, True, 1, 1, False, False),
        (3, '1090', 'газ природный', 1.150, False, 1, 2, False, False),
        (2, '1050', 'мазут топочный', 1.370, False, 1, 3, False, False),
        (2, '1040', 'топливо печное бытовое', 1.450, False, 1, 4, False, False),
        (2, '1660', 'кокс металлургический, коксик и коксовая мелочь', 0.990, False, 1, 5, False, False),
        (2, '1075', 'кокс нефтяной', 1.130, False, 1, 6, False, False),
        (2, '1160', 'уголь и продукты переработки угля', 0.814, False, 1, 7, False, False),
        (2, '1150', 'газы углеводородные сжиженные', 1.570, False, 1, 8, False, False),
        (2, '1060', 'газы углеводородные нефтепереработки', 1.500, False, 1, 9, False, False),
        (1, '1750', 'метано-водородная фракция производства полиэтилена', 1.000, False, 1, 10, False, False),
        (1, '1790', 'отработанные нефтепродукты', 1.000, False, 1, 11, False, False),
        (3, '1110', 'газ природный попутный', 1.300, False, 1, 12, True, False),
        (4, '1620', 'торф топливный фрезерный', 0.340, False, 1, 13, True, False),
        (4, '1630', 'торф топливный кусковой', 0.340, False, 1, 13, True, False),
        (4, '1640', 'брикеты и полубрикеты торфяные', 0.600, False, 1, 14, True, False),
        (1, '1794', 'использованные автопокрышки', 1.000, False, 1, 15, True, False),
        (1, '1745', 'биогаз', 1.000, False, 1, 16, False, True),
        (5, '1690', 'дрова', 0.228, False, 1, 17, False, True),
        (5, '1680', 'топливная щепа', 0.187, False, 1, 18, False, True),
        (1, '1742', 'древесные гранулы, пеллеты', 1.000, False, 1, 19, False, True),
        (1, '1744', 'древесные брикеты', 1.000, False, 1, 20, False, True),
        (1, '1785', 'RDF-топливо', 1.000, False, 1, 21, False, True),
        (1, '1730', 'отходы лесозаготовок и деревообработки', 1.000, False, 1, 22, False, True),
        (1, '1740', 'отходы сельскохозяйственной деятельности и прочие виды природного топлива', 1.000, False, 1, 23, False, True),
        (1, '1780', 'сульфатные и сульфитные щелока целлюлозно-бумажной промышленности', 1.000, False, 1, 24, False, True),
        (1, '1710', 'прочие отходы', 1.000, False, 1, 25, False, False),
        (1, '1700', 'прочие виды топлива', 1.000, False, 1, 26, False, False),
        (1, '1796', 'из него местные виды топлива и отходы', 1.000, True, 1.1, 3, False, False),
        (1, '1797', 'из них возобновляемые', 1.000, True, 1.2, 4, False, False),
        (6, '1105', 'Электроэнергия, израсходовано всего', 0.123, True, 2, 5, False, False),
        (6, '1405', 'Электроэнергия, выработанная собственными энергоисточниками, в том числе:', 0.123, True, 2, 6, False, False),
        (6, '1425', 'энергия воды, ветра, солнца, геотермальных источников', 0.123, True, 2, 7, False, False),
        (7, '1104', 'Теплоэнергия, израсходовано всего', 0.143, True, 3, 8, False, False),
        (7, '1404', 'Теплоэнергия, произведенная собственными энергоисточниками, в том числе:', 0.143, True, 3, 9, False, False),
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

    # Показатели, которые считаются автоматически (см. update_plan_indicators
    # в website/utils/plans.py) — их нельзя удалить/отредактировать вручную.
    computed_codes = {'260', '9900', '9999', '1101', '1797', '1796', '9915', '9916', '9917', '9910'}
    # Рост значения относительно отчёта — это хорошо (доля местных/
    # возобновляемых ТЭР). Для группы 1 берём is_local самой строки.
    higher_is_better_codes = {'1796', '1797', '9916', '9917', '1425', '1424'}
    # "Прочие" — требуют категории топлива и своего наименования,
    # можно добавить несколько.
    custom_codes = {'1710', '1700'}

    for IdUnit, CodeIndicator, NameIndicator, CoeffToTut, IsMandatory, Group, RowN, is_local, is_renewable in indicator_data:
        higher_is_better = True if CodeIndicator in higher_is_better_codes else (is_local if Group == 1 else None)
        indicator = Indicator(
            id_unit=IdUnit,
            code=CodeIndicator,
            name=NameIndicator,
            CoeffToTut=to_decimal_3(CoeffToTut),
            IsMandatory=IsMandatory,
            Group=Group,
            is_computed=CodeIndicator in computed_codes,
            higher_is_better=higher_is_better,
            is_custom=CodeIndicator in custom_codes,
            RowN=RowN,
            is_local=is_local,
            is_renewable=is_renewable
        )
        db.session.add(indicator)
    db.session.commit()
    logger.info(f'Добавлено {len(indicator_data)} индикаторов')


def fill_news(db):
    from ..models import News

    news_data = [
        ('Начало тестирования', 
         'EnPlans - инструмент для управления энергосбережением. Начинаем тестирование системы, которая автоматизирует создание планов мероприятий, контроль их исполнения и подготовку аналитики по энергоэффективности организаций. Перед началом работы ознакомьтесь с руководством пользователя в разделе Помощь.', 
         'update_v2.png', 
         True, 
         current_utc_time(), 
         1),
    ]

    for title, text, img_name, is_published, published_at, views_count in news_data:
        news = News(
            title=title,
            text=text,
            img_name=img_name,
            is_published=is_published,
            published_at=published_at,
            views_count=views_count,
            is_enplans=True
        )
        db.session.add(news)
    db.session.commit()
    logger.info(f'Добавлено {len(news_data)} новостей')


@db_bp.route('/fill-all-data', methods=['POST'])
@csrf.exempt
def fill_database_route():
    from flask import current_app
    from flask_login import current_user
    from website import db

    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'success': False, 'message': 'Требуются права администратора'}), 403

    try:
        # fill_users(db)
        fill_units(db)
        fill_directions(db)
        fill_indicators(db)
        fill_news(db)
        fill_organizations(db)

        return jsonify({
            'success': True,
            'message': 'База данных успешно заполнена'
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'Ошибка при заполнении базы данных: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@db_bp.route('/upload-statistics', methods=['POST'])
@csrf.exempt
def upload_statistics_route():
    """Загрузка статистики отдельным архивом (ZIP) из панели администратора.
    Каждый файл внутри должен соблюдать формат имени, который разбирает
    website.utils.stat_parse (окпо и год в имени, тип отчёта — по содержимому)."""
    from flask_login import current_user
    from website import db
    from website.utils.stat_import import import_stat_archive

    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'success': False, 'message': 'Требуются права администратора'}), 403

    archive = request.files.get('archive')
    if not archive or not archive.filename:
        return jsonify({'success': False, 'message': 'Не выбран архив'}), 400
    if not archive.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'message': 'Ожидается ZIP-архив'}), 400

    try:
        result = import_stat_archive(archive.stream, db, uploaded_by_id=current_user.id)
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f'Ошибка при импорте архива статистики: {str(e)}')
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

    imported, skipped, errors = result['imported'], result['skipped'], result['errors']
    logger.info(
        f'Импорт статистики из архива {archive.filename}: '
        f'{len(imported)} загружено, {len(skipped)} пропущено, {len(errors)} ошибок'
    )

    message = f'Загружено отчётов: {len(imported)}'
    if skipped:
        message += f', пропущено файлов: {len(skipped)}'
    if errors:
        message += f', ошибок: {len(errors)} — {"; ".join(errors[:3])}'
        if len(errors) > 3:
            message += '…'

    return jsonify({
        'success': not errors or bool(imported),
        'message': message,
        'imported': imported,
        'skipped': skipped,
        'errors': errors,
    }), 200


@db_bp.route('/test-route', methods=['GET', 'POST'])
@csrf.exempt
def test_route():
    logger.info(f'test route')
    return jsonify({
        'success': True,
        'message': 'Succes test'
    }), 200