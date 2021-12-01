import sys
import logging
import threading

_notebook = sys.argv[-1].endswith('json')
_logging_levels = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'warning': logging.WARNING,
    'error': logging.ERROR,
}


_logger_handler: logging.Logger = None
_logger_lock = threading.Lock()

class LogFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.CRITICAL: "\033[38;5;196m", # bright/bold magenta
        logging.ERROR:    "\033[38;5;9m", # bright/bold red
        logging.WARNING:  "\033[38;5;11m", # bright/bold yellow
        logging.INFO:     "\033[38;5;111m", # white / light gray
        logging.DEBUG:    "\033[1;30m"  # bright/bold black / dark gray
    }

    RESET_CODE = "\033[0m"
    def __init__(self, color, *args, **kwargs):
        super(LogFormatter, self).__init__(*args, **kwargs)
        self.color = color

    def format(self, record, *args, **kwargs):
        if (self.color == True and record.levelno in self.COLOR_CODES):
            record.color_on  = self.COLOR_CODES[record.levelno]
            record.color_off = self.RESET_CODE
        else:
            record.color_on  = ""
            record.color_off = ""
        return super(LogFormatter, self).format(record, *args, **kwargs)


def setup_logging(config):
    logger = logging.getLogger(config['name'])
    logger.setLevel(_logging_levels[config.get('log_level', 'info')])

    console_log_output = sys.stdout if _notebook else sys.stderr        
    console_handler = logging.StreamHandler(console_log_output)
    console_handler.setLevel(config["console_log_level"].upper())
    console_formatter = LogFormatter(fmt=config["log_line_template"], color=config["console_log_color"], datefmt=config.get('datefmt', None))
    console_handler.setFormatter(console_formatter)
    if config.get('clear_handlers', False) and logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(console_handler)
    if config.get('quiet_loggers'):
        to_quiet = config['quiet_loggers']
        if isinstance(to_quiet, str): to_quiet = [to_quiet]
        for clr in to_quiet:
            clr_logger = logging.getLogger(clr)
            clr_logger.setLevel(logging.ERROR)

    logger.propagate = config.get('propagate', False)
    return logger


def setup_new_logger(name, log_level=None, quiet_loggers=None, clear_handlers=False, propagate=True):
    if not log_level: log_level = 'info'
    logger_config = {
        'name': name,
        'log_level': log_level,
        'console_log_output': "stdout", 
        'console_log_level': log_level,
        'console_log_color': True,
        'logfile_file': None,
        'logfile_log_level': "debug",
        'logfile_log_color': False,
        'log_line_template': f"%(asctime)s [{name}] %(color_on)s%(module)s.%(funcName)-20s%(color_off)s %(message)-2s",
        'clear_handlers': clear_handlers,
        'quiet_loggers': quiet_loggers,
        'propagate': propagate,
        'datefmt': "%Y-%m-%d %H:%M:%SZ"
    }
    return setup_logging(logger_config)

def get_logger(name: str = 'aws', log_level=None):
    global _logger_handler
    with _logger_lock:
        if not _logger_handler:
            _logger_handler = setup_new_logger(name=name, log_level=log_level)
        return _logger_handler
