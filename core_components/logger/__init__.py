import logging
from datetime import datetime
from pathlib import Path

def setup_logger(name='root', log_file=None):
    current_dir = Path.cwd()
    log_dir = Path('../logs') if current_dir.name == "notebooks" else Path('logs')
    
    if not log_dir.exists():
        log_dir.mkdir(parents=True)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    if log_file is None:
        log_file = log_dir / f'log_{datetime.now().strftime("%Y%m%d")}.log'

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    logger.handlers = []

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(log_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger