import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p',  # 2023-05-15 02:32:10 PM
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )