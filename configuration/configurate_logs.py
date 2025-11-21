import logging
from logging.handlers import TimedRotatingFileHandler
import os
import glob
import datetime

LOG_DIR = "log"

def setup_logger():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"logs_{today}.txt")

    cutoff = datetime.datetime.now() - datetime.timedelta(days=5)
    for file_path in glob.glob(os.path.join(LOG_DIR, "logs_*.txt")):
        file_date_str = os.path.basename(file_path).replace("logs_", "").replace(".txt", "")
        try:
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(file_path)
        except:
            pass

    logger = logging.getLogger("SystemLogger")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger