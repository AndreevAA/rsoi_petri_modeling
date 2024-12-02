from PyQt5.QtWidgets import *
import sys
from pathlib import Path
from app import App


# Устанавливаем корневой путь к директории, где находится текущий файл
root_path = Path(__file__).parent


if __name__ == '__main__':
    app = App(sys.argv, root_path)
    app.run()

