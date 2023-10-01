import numpy as np
from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QLineEdit, QPushButton, QHBoxLayout, \
    QMessageBox, QComboBox, QListWidget, QDialog, QDialogButtonBox, QListWidgetItem, QMainWindow, QInputDialog, \
    QVBoxLayout, QTableView, QCheckBox
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QThread
import cv2
import sys


class RobienieZdjecia(QWidget):

    def __init__(self, video_thread, funkcja_robienia_zdjec):
        super().__init__()

        print('__init__ RobienieZdjecia()')
        self.video_thread = video_thread

        self.podglad_kamery = QLabel(self)
        zrob_zdjecie_btn = QPushButton('&Zrób zdjęcie', self)
        zrob_zdjecie_btn.clicked.connect(funkcja_robienia_zdjec)

        self.szerokosc = 1280
        self.wysokosc = 720

        self.podglad_kamery.resize(self.szerokosc, self.wysokosc)

        video_thread.start()
        video_thread.change_pixmap_signal.connect(self.odswiezanie_obrazu)

        # Układy
        uklad = QHBoxLayout()

        uklad.addWidget(self.podglad_kamery)
        uklad.addWidget(zrob_zdjecie_btn)

        self.setLayout(uklad)
        self.setWindowTitle("Robienie zdjęcia")
        self.show()

    def closeEvent(self, QCloseEvent):
        self.video_thread.stop()

    @pyqtSlot(np.ndarray)
    def odswiezanie_obrazu(self, cv_img):
        qt_img = self.konwersja_cv_qt(cv_img)
        self.podglad_kamery.setPixmap(qt_img)

    def konwersja_cv_qt(self, cv_img):
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        zmiana_na_qt_format = QtGui.QImage(rgb_img.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = zmiana_na_qt_format.scaled(self.szerokosc, self.wysokosc, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)
