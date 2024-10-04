import os
import logging
from datetime import datetime

def setup_logger(name='root', log_file=None):
    log_dir = '../logs' if os.path.basename(os.getcwd())=="notebooks" else 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    if log_file is None:
        log_file = f'{log_dir}/app_{datetime.now().strftime("%Y%m%d")}.log'

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