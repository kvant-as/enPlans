import os
from dotenv import load_dotenv

from flask import Flask, flash, render_template, session, request, g, redirect, url_for
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_babel import format_date, format_datetime
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman

from website.logs import setup_logging

from .database import create_database

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

db = SQLAlchemy()
socketio = SocketIO()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_url_path='/static')
    from itsdangerous import URLSafeSerializer, BadSignature
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

        EXCLUDE_INFO_LOGS=os.getenv('EXCLUDE_INFO_LOGS'),

        AI_API_URL=os.getenv('AI_API_URL'),
        AI_X_API_KEY=os.getenv('AI_X_API_KEY'),
        
        LOG_LEVEL='DEBUG'
    )

    db.init_app(app)
    socketio.init_app(app)
    babel.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    
    setup_logging(app)
    
    Talisman(app, 
            force_https=False,
            content_security_policy=None)

    login_manager.init_app(app)
    login_manager.login_message = "Пожалуйста, авторизуйтесь для доступа к этой странице"
    login_manager.login_view = "auth.login"

    from .routes.views import views
    from .routes.auth import auth
    from .routes.chat_bp import chat_bp
    from .routes.plan_bp import plan_bp
    from .routes.api_bp import api_bp
    from .routes.audit_bp import audit_bp
    from .routes.stat_bp import bp as stat_bp
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(plan_bp, url_prefix='/plans/plan')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(audit_bp, url_prefix='/')
    app.register_blueprint(stat_bp, url_prefix='/stat-reports')
    
    with app.app_context():
        from .routes.admin import AdminSetup
        admin_setup = AdminSetup(app, db)
        admin_setup.setup()
        
    with app.app_context():
        db.create_all()
        create_database(app, db)
    
    app.jinja_env.globals['format_date'] = format_date
    
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
            
    @app.template_filter('ru_date')
    def ru_date(date):
        months = {
            1: 'Января', 2: 'Февраля', 3: 'Марта',
            4: 'Апреля', 5: 'Мая', 6: 'Июня',
            7: 'Июля', 8: 'Августа', 9: 'Сентября',
            10: 'Октября', 11: 'Ноября', 12: 'Декабря'
        }
        return f"{date.day} {months[date.month]} {date.year}"
            
    return app