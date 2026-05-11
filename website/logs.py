import os
import sys
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
import traceback

class logs(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "file": record.filename,
            "line": record.lineno,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        return json.dumps(log_data, ensure_ascii=False)

class ExcludeInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelname != 'INFO'

def setup_logging(app):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "py-app.log")
    
    exclude_info = app.config.get('EXCLUDE_INFO_LOGS')
    
    json_formatter = logs()
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    
    if exclude_info:
        file_handler.addFilter(ExcludeInfoFilter())
        console_handler.addFilter(ExcludeInfoFilter())
        app.logger.debug("INFO logs are EXCLUDED")
    else:
        app.logger.debug("ALL logs are shown (including INFO)")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    loggers_to_silence = [
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.orm',
        'urllib3',
        'requests',
        'werkzeug'
    ]
    
    for logger_name in loggers_to_silence:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        logger.handlers.clear()

    app.logger.handlers.clear()
    app.logger.propagate = True

    app.logger.debug("=" * 60)
    app.logger.debug(f"Launch time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app.logger.debug(f"Exclude INFO logs: {exclude_info}")
    app.logger.debug(f"Debug mode: {app.config.get('DEBUG', False)}")
    app.logger.debug(f"Logs are recorded in: {log_file}")
    app.logger.debug("=" * 60)


def log_with_extra(logger, level, message, **extra_fields):
    if hasattr(logger, level.lower()):
        log_method = getattr(logger, level.lower())
        extra = {}
        extra.update(extra_fields)
        log_method(message, extra={'extra': extra})
    else:
        logger.info(message, extra={'extra': extra_fields})