import sys
import json
import logging
from datetime import datetime
import traceback

class WerkzeugFilter(logging.Filter):
    def filter(self, record):
        return not (record.name == 'werkzeug' and 'GET /static/' in record.getMessage())


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "file": record.filename,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info))
            }
        
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        log_line = f"{timestamp} | {color}{record.levelname:<8}{reset} | {record.name} | {record.filename}:{record.lineno} | {record.getMessage()}"
        
        if record.exc_info:
            log_line += f"\n{''.join(traceback.format_exception(*record.exc_info))}"
        
        return log_line


def setup_logging(app):
    log_level = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_static = app.config.get('LOG_STATIC_REQUESTS', False)
    
    numeric_level = getattr(logging, log_level)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    
    use_json = app.config.get('LOG_JSON', False)
    
    if use_json:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter())
    
    if not log_static:
        console_handler.addFilter(WerkzeugFilter())
    
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    app.logger.handlers.clear()
    app.logger.setLevel(numeric_level)
    app.logger.propagate = True
    
    app.logger.info("=" * 60)
    app.logger.info(f"Launch time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app.logger.info(f"Logging level: {log_level}")
    app.logger.info(f"JSON format: {use_json}")
    app.logger.info(f"Log static requests: {log_static}")
    app.logger.info("=" * 60)


def log_with_extra(logger, level, message, **extra_fields):
    log_method = getattr(logger, level.lower(), logger.info)
    extra = {'extra_data': extra_fields}
    log_method(message, extra=extra)