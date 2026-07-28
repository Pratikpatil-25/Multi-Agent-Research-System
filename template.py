import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]:%(message)s:')

backend = "server"
frontend = "client"

list = {
    f"src/{backend}/__init__.py",
    f"src/{backend}/components/__init__.py",
    f"src/{backend}/constants/__init__.py",
    f"src/{backend}/utils/__init__.py",
    f"src/{backend}/utils/common.py",
    f"src/{backend}/logger/__init__.py",
    f"src/{backend}/middlewares/__init__.py",
    f"src/{backend}/routes/__init__.py",
    f"src/{backend}/main.py",
    f"src/{frontend}/components/__init__.py",
    f"src/{frontend}/utils/__init__.py",
    f"src/{frontend}/app.py",
    f"src/{frontend}/config.py",
    "params.yaml",
    "requirements.txt",
}

for filepath in list:
    filepath = Path(filepath)

    filedir, filename = os.path.split(filepath)

    if filedir !="":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory; {filedir} for the file: {filename}")

    if (not os.path.exists(filepath)) or (os.path.getsize(filepath) == 0):
        with open(filepath, "w") as f:
            logging.info(f"Creating empty file: {filepath}")


    else:
        logging.info(f"{filename} is already exists")