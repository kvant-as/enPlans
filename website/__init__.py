import os
from datetime import timedelta
from importlib.resources import files
from dotenv import load_dotenv

from flask import Flask, flash, render_template, session, request, g, redirect, url_for, jsonify
from flask_babel import Babel
from flask_socketio import SocketIO
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_babel import format_date
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman

from common_models import db, current_utc_time
from common_models.logs import setup_logging

load_dotenv()

LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'be': 'Беларуский'
}

def get_locale():
    if 'language' in session and session['language'] in LANGUAGES:
        return session['language']
    user = getattr(g, 'user', None)
    if user and hasattr(user, 'locale') and user.locale in LANGUAGES:
        return user.locale

    return request.accept_languages.best_match(LANGUAGES)

def get_timezone():
    user = getattr(g, 'user', None)
    if user is not None and hasattr(user, 'timezone'):
        return user.timezone
    return None

babel = Babel(
    locale_selector=get_locale,
    timezone_selector=get_timezone
)

socketio = SocketIO()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_url_path='/static')
    from itsdangerous import URLSafeSerializer
    s = URLSafeSerializer(os.getenv('SECRET_KEY'))
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_DATABASE_URI=f"postgresql://{os.getenv('postrgeuser')}:{os.getenv('postrgepass')}@localhost:5432/{os.getenv('postrgedbname')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        BABEL_TRANSLATION_DIRECTORIES='translations',
        LANGUAGES=LANGUAGES,
        SESSION_SQLALCHEMY=db,
        SESSION_PERMANENT=True,
        SESSION_TYPE='sqlalchemy',
        FLASK_ADMIN_SWATCH='cosmo',
        BABEL_DEFAULT_LOCALE='ru',
        SEND_FILE_MAX_AGE_DEFAULT=0,
        SESSION_COOKIE_NAME=os.getenv('SESSION_COOKIE_NAME'),
        APP_NAME=os.getenv('APP_NAME', 'enplans'),
        AI_API_URL=os.getenv('AI_API_URL'),
        AI_X_API_KEY=os.getenv('AI_X_API_KEY'),
        LOG_LEVEL=os.getenv('LOG_LEVEL', 'DEBUG'),
        LOG_JSON=os.getenv('LOG_JSON'),
        LOG_STATIC_REQUESTS=os.getenv('LOG_STATIC_REQUESTS'),
        LOG_TO_FILE=os.getenv('LOG_TO_FILE'),
        LOG_DIR=os.getenv('LOG_DIR', 'logs'),
        LOG_FILE=os.getenv('LOG_FILE', 'enplans.json'),
        # common_models.sessions
        SESSION_TOKEN_COOKIE='session_token',
        SESSION_TOKEN_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes'),
        SESSION_LOGIN_ENDPOINT='auth.login',
        SESSION_LOGOUT_ENDPOINT='auth.logout',
        SESSION_TIMEOUT_PRIVILEGED=timedelta(hours=9),
        SESSION_TIMEOUT_DEFAULT=timedelta(minutes=60),
        # роли, дающие длинное окно; is_admin/is_auditor/is_approver/is_reader
        SESSION_PRIVILEGED_ATTRS=('is_admin', 'is_auditor', 'is_approver', 'is_reader'),
        # main.py запускает приложение с debug=True (как и erespondentN) — без
        # этого флага enforce_idle_timeout() молча пропускает проверку простоя
        # в debug-режиме (см. common_models.sessions._enforcing), и пользователь
        # никогда не разлогинивается по истечении сессии.
        SESSION_ENFORCE_IN_DEBUG=True,
        # Файлы ТЭО и вложения к сообщениям (замечаниям) в чате согласования
        # плана лежат в одной общей папке (ATTACHMENTS_UPLOAD_FOLDER —
        # переопределяется в .env, например на боевом сервере — на
        # реальный постоянный диск/раздел), а внутри неё — отдельные
        # подпапки по назначению файла (teo/tickets). НЕ называем её
        # UPLOAD_FOLDER — этот ключ уже занят в export.py (временная папка
        # архивов экспорта, другое назначение).
        #
        # По умолчанию папка лежит ЗА ПРЕДЕЛАМИ кода приложения — на
        # уровень выше папки enPlans (а не в enPlans/instance), чтобы
        # загруженные файлы переживали переразвёртывание/переустановку
        # самого приложения и не терялись вместе с кодом.
        ATTACHMENTS_UPLOAD_FOLDER=os.getenv(
            'ATTACHMENTS_UPLOAD_FOLDER',
            os.path.join(os.path.dirname(os.path.dirname(app.instance_path)), 'uploads')
        ),
        TEO_MAX_FILE_SIZE=int(os.getenv('TEO_MAX_FILE_SIZE', 20 * 1024 * 1024)),
        # Если диск, на котором лежит ATTACHMENTS_UPLOAD_FOLDER, заполнен на
        # этот процент и более — загрузка новых файлов ТЭО блокируется с
        # понятным сообщением (см. website/utils/teo.py:check_disk_space).
        TEO_DISK_USAGE_LIMIT_PERCENT=float(os.getenv('TEO_DISK_USAGE_LIMIT_PERCENT', 80)),
        TICKET_ATTACHMENT_MAX_FILE_SIZE=int(os.getenv('TICKET_ATTACHMENT_MAX_FILE_SIZE', 20 * 1024 * 1024)),
        # ЕГР (egr.gov.by) — обновление данных организации по УНП
        # (utils/egr.py). EGR_API_KEY — если ЕГР выдал ключ доступа
        # (заголовок Authorization по спецификации API), иначе пусто.
        EGR_API_BASE=os.getenv('EGR_API_BASE', 'https://egr.gov.by/api/v2/egr'),
        EGR_API_KEY=os.getenv('EGR_API_KEY'),
        EGR_TIMEOUT=float(os.getenv('EGR_TIMEOUT', 15)),
        # Сверка организации с ЕГР перед «Подписать и отправить» — короткий
        # таймаут, чтобы недоступный ЕГР не задерживал подпись.
        EGR_CHECK_ON_SEND=os.getenv('EGR_CHECK_ON_SEND', 'true').lower() in ('1', 'true', 'yes'),
        EGR_SEND_TIMEOUT=float(os.getenv('EGR_SEND_TIMEOUT', 5)),
    )
    app.config['TEO_UPLOAD_FOLDER'] = os.path.join(app.config['ATTACHMENTS_UPLOAD_FOLDER'], 'teo')
    app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER'] = os.path.join(app.config['ATTACHMENTS_UPLOAD_FOLDER'], 'tickets')

    os.makedirs(app.config['TEO_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER'], exist_ok=True)

    from website.utils.teo import register_teo_cleanup_listeners
    register_teo_cleanup_listeners()

    from website.utils.ticket_attachment import register_ticket_attachment_cleanup_listeners
    register_ticket_attachment_cleanup_listeners()

    db.init_app(app)
    socketio.init_app(app)
    babel.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db,
                     directory=str(files('common_models') / 'migrations'),
                     render_as_batch=True)
    csrf.init_app(app)
    
    setup_logging(app)
    
    Talisman(app, 
            force_https=False,
            content_security_policy=None)

    login_manager.init_app(app)
    login_manager.login_message = "Пожалуйста, авторизуйтесь для доступа к этой странице"
    login_manager.login_view = "auth.login"

    from common_models.sessions import enforce_idle_timeout
    enforce_idle_timeout(app)

    from .routes.views import views
    from .routes.auth import auth
    from .routes.chat_bp import chat_bp
    from .routes.plan_bp import plan_bp
    from .routes.api_bp import api_bp
    from .routes.audit_bp import audit_bp
    from .routes.stat_bp import bp as stat_bp
    from .routes.db_bp import db_bp
    from .routes.admin_support import admin_support_bp
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(plan_bp, url_prefix='/plans/plan')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(audit_bp, url_prefix='/')
    app.register_blueprint(stat_bp, url_prefix='/stat-reports')
    app.register_blueprint(db_bp, url_prefix='/database')
    app.register_blueprint(admin_support_bp, url_prefix='/admin/support-chats')
    from .routes.admin_org import admin_org_bp
    app.register_blueprint(admin_org_bp, url_prefix='/admin/org-by-unp')

    common_templates = str(files('common_models') / 'templates')

    app.jinja_loader.searchpath = [
        os.path.join(app.root_path, 'templates'),
        common_templates
    ]
    
    from .admin import init_admin
    init_admin(app)

    from common_models.assets import init_assets
    init_assets(app)

    from common_models.forms_ui import init_forms_ui
    init_forms_ui(app)

    # schema is managed by Alembic (common_models/migrations); run `flask db upgrade`

    app.jinja_env.globals['format_date'] = format_date
    app.jinja_env.globals['current_utc_time'] = current_utc_time

    from website.utils.plans import get_plan_versions
    app.jinja_env.globals['get_plan_versions'] = get_plan_versions
    
    @app.context_processor
    def inject_get_locale():
        return dict(get_locale=get_locale)
    
    @app.context_processor
    def utility_processor():
        def generate_plan_token(plan_id):
            return s.dumps(plan_id)
        return dict(generate_plan_token=generate_plan_token)

    @app.route('/static/<path:filename>')
    def custom_static(filename):
        from flask import send_from_directory
        return send_from_directory(app.static_folder, filename)
    
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.remove('X-Frame-Options')
        return response
    
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html', hide_header=True), 404
    
    @app.before_request
    def check_admin_access():
        if request.path.startswith('/admin/'):
            if not current_user.is_authenticated:
                flash('Необходимо авторизоваться для доступа к админ-панели', 'error')
                return redirect(url_for('auth.login'))
            
            is_admin = False
            if hasattr(current_user, 'is_admin'):
                is_admin = getattr(current_user, 'is_admin', False)
            
            if not is_admin:
                flash('Недостаточно прав для доступа к админ-панели', 'error')
                return redirect(url_for('views.begin_page'))
            
    # Организация не действующая по ЕГР (ликвидирована / в ликвидации /
    # банкротство, utils/egr.py::INACTIVE_KINDS) — её сотрудникам доступен
    # только просмотр: любой изменяющий запрос (не GET/HEAD/OPTIONS)
    # отклоняется. Исключения — то, без чего человек застрял бы: вход/выход
    # и пароль, служебные запросы сессии, отметка уведомлений, обращение в
    # поддержку, экспорт (это просмотр) и «Обновить из ЕГР» — если
    # организацию восстановили, руководитель снимет блокировку сам.
    # Администраторов не касается.
    EGR_BLOCK_ALLOWED_ENDPOINTS = {
        'auth.logout', 'auth.login', 'auth.forgot_password', 'auth.reset_password',
        'views.egr_refresh_organization', 'views.start_export',
        'api_bp.mark_all_notifications_read', 'api_bp.mark_notification_read',
    }
    EGR_BLOCK_ALLOWED_PREFIXES = ('/_session', '/_forms', '/api/chat', '/static')

    @app.before_request
    def block_inactive_organization():
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        if not current_user.is_authenticated or getattr(current_user, 'is_admin', False):
            return None
        if request.endpoint in EGR_BLOCK_ALLOWED_ENDPOINTS or request.path.startswith(EGR_BLOCK_ALLOWED_PREFIXES):
            return None
        from website.utils.egr import org_is_inactive, inactive_notice
        org = current_user.organization
        if not org_is_inactive(org):
            return None

        message = inactive_notice(org)
        app.logger.info(f'EGR block: user {current_user.id} org {org.id} ({org.egr_status_kind}) -> {request.endpoint}')
        wants_json = (
            request.is_json
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in (request.headers.get('Accept') or '')
        )
        if wants_json:
            return jsonify({'success': False, 'error': message}), 403
        flash(message, 'error')
        return redirect(request.referrer or url_for('views.profile'))

    @app.context_processor
    def inject_inactive_org_notice():
        """Плашка в base.html для сотрудников недействующей организации."""
        try:
            if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
                from website.utils.egr import org_is_inactive, inactive_notice
                org = current_user.organization
                if org_is_inactive(org):
                    return {'inactive_org_notice': inactive_notice(org)}
        except Exception:
            pass
        return {'inactive_org_notice': None}

    @app.template_filter('ru_date')
    def ru_date(date):
        months = {
            1: 'Января', 2: 'Февраля', 3: 'Марта',
            4: 'Апреля', 5: 'Мая', 6: 'Июня',
            7: 'Июля', 8: 'Августа', 9: 'Сентября',
            10: 'Октября', 11: 'Ноября', 12: 'Декабря'
        }
        return f"{date.day} {months[date.month]} {date.year}"
    
    @app.template_filter('nl2br')
    def nl2br(text):
        """Текст новости (News.text) — обычная многострочная текстовая
        область в админке (admin.py: F("text", ..., type="text")), не
        HTML-редактор, поэтому переносы строк там — обычные \\n. Раньше
        шаблон news_id.html выводил его через |safe как есть — браузер
        схлопывает \\n в пробел, и вся новость превращалась в один сплошной
        абзац без разбивки.

        CSS для статьи (news.css :: .text_spectrum p / p:first-child)
        рассчитан именно на отдельные <p> — без них пропадают отступы
        между абзацами и увеличенный первый абзац-лид. Поэтому пустая
        строка (два подряд \\n) трактуется как разделитель абзацев, а
        одиночный \\n внутри абзаца — просто как <br>. Текст экранируется,
        HTML-тегами он быть не должен.
        """
        from markupsafe import Markup, escape
        import re
        if not text:
            return ''
        paragraphs = re.split(r'\n\s*\n', str(text).strip())
        html_parts = []
        for para in paragraphs:
            if not para.strip():
                continue
            escaped = '<br>\n'.join(str(escape(line)) for line in para.splitlines())
            html_parts.append(f'<p>{escaped}</p>')
        return Markup('\n'.join(html_parts))

    @app.template_filter('comma_decimal')
    def comma_decimal(value):
        if value is None:
            return ""
        try:
            return str(value).replace('.', ',')
        except (ValueError, TypeError):
            return str(value).replace('.', ',')
            
    return app