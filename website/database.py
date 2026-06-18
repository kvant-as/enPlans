import datetime
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
    from .models import Organization
    return all([
        Organization.query.count() == 0,
    ])

def read_dbf(file_path, columns):
    data = []
    for record in DBF(file_path):
        row = {col: record[col] for col in columns}
        data.append(row)
    return data

def filling_database(db):
    if is_db_empty():
        from .models import User, Organization, Unit, Direction, Indicator, Ministry, Region, News
        from sqlalchemy.exc import IntegrityError
        current_app.logger.debug('Filling is in progress...')

        ### ORGANIZATION DATA ###
        website_path = os.path.dirname(os.path.abspath(__file__))

        Brest_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Брест.dbf')
        Vitebsk_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Витебск.dbf')
        Gomel_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Гомель.dbf')
        Grodno_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Гродно.dbf')
        Minsk_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Минск.dbf')
        MinskRegion_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Минск_область.dbf')
        Migilev_org_data_path = os.path.join(website_path, 'static/files/organizations', 'Могилев.dbf')

        columns_org = ['OKPO', 'NAME', 'MIN', 'UNP']

        Brest_org_data = read_dbf(Brest_org_data_path, columns_org)
        Vitebsk_org_data = read_dbf(Vitebsk_org_data_path, columns_org)
        Gomel_org_data = read_dbf(Gomel_org_data_path, columns_org)
        Grodno_org_data = read_dbf(Grodno_org_data_path, columns_org)
        Minsk_org_data = read_dbf(Minsk_org_data_path, columns_org)
        MinskRegion_org_data = read_dbf(MinskRegion_org_data_path, columns_org)
        Migilev_org_data = read_dbf(Migilev_org_data_path, columns_org)

        city_all_data = pd.concat([
            pd.DataFrame(Brest_org_data, columns=columns_org),
            pd.DataFrame(Vitebsk_org_data, columns=columns_org),
            pd.DataFrame(Gomel_org_data, columns=columns_org),
            pd.DataFrame(Grodno_org_data, columns=columns_org),
            pd.DataFrame(Minsk_org_data, columns=columns_org),
            pd.DataFrame(MinskRegion_org_data, columns=columns_org),
            pd.DataFrame(Migilev_org_data, columns=columns_org)
        ], ignore_index=True)

        MinskRegion_min_data_path = os.path.join(website_path, 'static/files/ministerstvo', 'MinskReg_min.dbf')
        columns_min = ['MIN', 'NAME']
        MinskRegion_min_data = read_dbf(MinskRegion_min_data_path, columns_min)

        min_all_data = pd.DataFrame(MinskRegion_min_data, columns=columns_min)

        ministries_dict = {}

        for _, row in min_all_data.drop_duplicates('MIN').iterrows():
            ministry = Ministry.query.filter_by(id=row['MIN']).first()

            if not ministry:
                ministry = Ministry(
                    id=row['MIN'],
                    name=row['NAME']
                )
                db.session.add(ministry)

            ministries_dict[row['MIN']] = ministry

        db.session.commit()

        for _, row in city_all_data.iterrows():
            organization_name = ' '.join(filter(None, [
                row['NAME']
            ]))

            existing_org = Organization.query.filter_by(okpo=row['OKPO']).first()

            if not existing_org:
                organization = Organization(
                    okpo=row['OKPO'],
                    name=organization_name,
                    ministry_id=row['MIN'],
                    ynp=row['UNP']
                )
                db.session.add(organization)

        try:
            db.session.commit()
            current_app.logger.debug("The data has been successfully added to the database")
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Data integrity error: {e}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"An error has occurred: {e}")

        dop_org_data = [
            ('Брестское областное управление', '100000001000'),
            ('Витебское областное управление', '200000002000'),
            ('Гомельское областное управление', '300000003000'),
            ('Гродненское областное управление', '400000004000'),
            ('Управление г. Минск', '500000005000'),
            ('Минское областное управление', '600000006000'),
            ('Могилевское областное управление', '700000007000'),
            ('Департамент по энергоэффективности', '800000008000'),
        ]

        for name, okpo in dop_org_data:
            dop_org = Organization(name=name, okpo=str(okpo))
            db.session.add(dop_org)
        db.session.commit()
        ### ----------- ###

        ### REGION DATA ###
        region_data = [
            ('Брестская область'),
            ('Витебская область'),
            ('Гомельская область'),
            ('Гродненская область'),
            ('г. Минск'),
            ('Минская область'),
            ('Могилевская область'),
        ]

        for name in region_data:
            new_region = Region(name=name)
            db.session.add(new_region)

        db.session.commit()
        ### ----------- ###

        ### USER DATA ###
        users_data = [
            ('', os.getenv('adminemail1'), os.getenv('adminname1'), os.getenv('adminsecondname1'), os.getenv('adminpatr1'), os.getenv('adminphone1'), True, False, 14),
            ('', os.getenv('adminemail2'), os.getenv('adminname2'), os.getenv('adminsecondname2'), os.getenv('adminpatr2'), os.getenv('adminphone2'), False, False, 6471),

            # ('', os.getenv('auditoremailBrest'), 'Иванов1', 'Иван', 'Иванович', '+11', False, True, 7940),
            # ('', os.getenv('auditoremailVitebsk'), 'Иванов2', 'Иван', 'Иванович', '+22', False, True, 7941),
            # ('', os.getenv('auditoremailGomel'), 'Иванов3', 'Иван', 'Иванович', '+33', False, True, 7942),
            # ('', os.getenv('auditoremailGrodno'), 'Иванов4', 'Иван', 'Иванович', '+44', False, True, 7943),
            # ('', os.getenv('auditoremailMinskobl'), 'Иванов5', 'Иван', 'Иванович', '+55', False, True, 7945),
            # ('', os.getenv('auditoremailMogilev'), 'Иванов6', 'Иван', 'Иванович', '+66', False, True, 7946),
            # ('', os.getenv('auditoremailMinsk'), 'Иванов7', 'Иван', 'Иванович', '+77', False, True, 7944),
            
            ('', os.getenv('testuser'), 'Иванов', 'Иван', 'Иванович', '+375173382562', False, False, 6443),
            ('', os.getenv('auditoremailNadzor'), 'Иванов', 'Иван', 'Иванович', '+375173385051', False, True, 7947),

            # ('', os.getenv('auditoremailBrestTEST'), 'Иванов1', 'Иван', 'Иванович', '+1', False, True, 7940),
            # ('', os.getenv('auditoremailVitebskTEST'), 'Иванов2', 'Иван', 'Иванович', '+2', False, True, 7941),
            # ('', os.getenv('auditoremailGomelTEST'), 'Иванов3', 'Иван', 'Иванович', '+3', False, True, 7942),
            # ('', os.getenv('auditoremailGrodnoTEST'), 'Иванов4', 'Иван', 'Иванович', '+4', False, True, 7943),
            # ('', os.getenv('auditoremailMinskoblTEST'), 'Иванов5', 'Иван', 'Иванович', '+5', False, True, 7945),
            # ('', os.getenv('auditoremailMogilevTEST'), 'Иванов6', 'Иван', 'Иванович', '+6', False, True, 7946),
            # ('', os.getenv('auditoremailMinskTEST'), 'Иванов7', 'Иван', 'Иванович', '+7', False, True, 7944),
            # ('', os.getenv('auditoremailNadzorTEST'), 'Иванов8', 'Иван', 'Иванович', '+8', False, True, 7947),
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
            ('Новый дизайн интерфейса', 
            'Представляем обновлённый дизайн личного кабинета и навигации. Интерфейс стал более удобным и интуитивно понятным.', 
            'design.png', 
            True, 
            TimeByMinsk(), 
            1),
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
    else:
        current_app.logger.debug('The database already contains the data!')