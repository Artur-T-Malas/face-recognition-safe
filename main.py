import os
import shutil
import time

import sqlalchemy.orm
from sqlalchemy.exc import IntegrityError

from datetime import datetime as dt

from pathlib import Path

from sqlalchemy import select
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, UniqueConstraint, create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QLineEdit, QPushButton, QHBoxLayout, \
    QMessageBox, QComboBox, QListWidget, QDialog, QDialogButtonBox, QListWidgetItem, QMainWindow, QInputDialog, \
    QVBoxLayout, QTableView, QCheckBox
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QThread
from gpiozero import Servo
import cv2
import sys
import numpy as np
import hashlib
import wyrownanie_twarzy
import Robienie_zdjecia
from time import sleep


#serwomechanizmy = [Servo(2), Servo(3), Servo(4), Servo(17), Servo(27), Servo(22), Servo(10), Servo(9), Servo(11)]
serwomechanizmy = [Servo(14), Servo(15), Servo(18), Servo(23), Servo(24), Servo(25), Servo(8), Servo(7), Servo(1)]

skrytka_gdzie = ['1 od lewej i 1 od góry', '2 od lewej i 1 od góry', '3 od lewej i 1 od góry', '1 od lewej i 2 od góry',
 '2 od lewej i 2 od góry', '3 od lewej i 2 od góry', '1 od lewej i 3 od góry',
 '2 od lewej i 3 od góry', '3 od lewej i 3 od góry']


# Przestawienie serwomechanizmów w pozycję zablokowania skrytek
for s in serwomechanizmy:
    s.min()
    sleep(0.2)
    


def otworz_skrytke(skrytka):
    print(skrytka-1)
    serwomechanizmy[skrytka - 1].min()
    
def zamknij_skrytke(skrytka):
    print(skrytka-1)
    serwomechanizmy[skrytka - 1].max()
    

# tworzymy instancję klasy Engine do obsługi bazy
baza = create_engine('sqlite:///test.db')  # stworzenie Engine do podłączenia do bazy test.db (ścieżka lokalna)

# klasa bazowa
BazaModel = sqlalchemy.orm.declarative_base()

# zapamiętanie na czas działania aplikacji aktualnej lokalizacji katalogu głównego
katalog_glowny = os.getcwd()

lista_skrytek = list(range(1, 10))

log = os.path.join(os.getcwd(), 'log.txt')


class Osoba(BazaModel):
    __tablename__ = 'osoba'
    id = Column(Integer, primary_key=True)
    login = Column(String(50), nullable=False)
    imie_nazwisko = Column(String(200), nullable=False)
    hash = Column(String(50), default='')
    administrator = Column(Boolean, default=False)
    katalog = Column(String(400), default='')
    zdjecia = relationship('Zdjecie', backref='osoba')
    skrytka = Column(Integer, default=None)
    __table_args__ = (UniqueConstraint('login'),)


class Zdjecie(BazaModel):
    __tablename__ = 'zdjecie'
    id = Column(Integer, primary_key=True)
    numer = Column(Integer, nullable=False)
    sciezka = Column(String(500), nullable=False)
    osoba_id = Column(Integer, ForeignKey('osoba.id'), nullable=False)
 

# tworzymy tabele
BazaModel.metadata.create_all(baza)

# tworzymy sesję, która przechowuje obiekty i umożliwia "rozmowę" z bazą
BDSesja = sessionmaker(bind=baza)
sesja = BDSesja()


# testowe dodanie osoby do otwierania zarządzania bazą
def dodaj_test_admin():
    sesja = BDSesja()
    try:
        hash_admin = hashlib.sha256('123'.encode('utf-8')).hexdigest()
        sesja.add(Osoba(login='admin', imie_nazwisko='admin admin', hash=hash_admin, katalog='aby_nie_usunac', administrator=True))
        sesja.flush()
    except Exception as ex:
        pass
    else:
        sesja.commit()


dodaj_test_admin()


class Login(QDialog):

    def __init__(self, parent=None):
        super(Login, self).__init__(parent)

        inst_osoby = sesja.query(Osoba).all()
        self.uzytkownicy = []
        for osoba in inst_osoby:
            self.uzytkownicy.append(osoba.login)

        self.aktualny_uzytkownik_id = 0

        self.textName = QLineEdit(self)
        self.textName.setPlaceholderText('Login')
        self.textPass = QLineEdit(self)
        self.textPass.setPlaceholderText('Haslo')

        self.buttonLogin = QPushButton('Login', self)
        self.buttonLogin.clicked.connect(self.zaloguj)
        layout = QVBoxLayout(self)
        layout.addWidget(self.textName)
        layout.addWidget(self.textPass)
        layout.addWidget(self.buttonLogin)
        self.setWindowTitle('Login')
        self.show()

    def zaloguj(self):

        if self.textName.text() not in self.uzytkownicy:    # jeśli podany użytkownik nie znajduje się w bazie logowanie zostaje przerwane i zostaje wyświetlony dialog
            wyswietl_komunikat('Błąd logowania!', 'Błędny login lub hasło. Spróbuj ponownie.', QMessageBox.Warning)
            rejestracja_zdarzenia('Błąd logowania - Błędny login: {}'.format(self.textName.text()), 'n/d', log)
            self.reject()
            return

        logujacy_sie_uzytkownik = sesja.query(Osoba).filter(Osoba.login == self.textName.text()).one()  # pobieramy hasło dla użytkownika próbującego się zalogować
        hash = logujacy_sie_uzytkownik.hash

        hash_uzytkownika = hashlib.sha256(self.textPass.text().encode('utf-8')).hexdigest()
        # jeśli hasło jest błędne wyświetlony zostaje identyczny dialog aby nie informować czy "zgadło się" nazwę użytkownika
        if hash_uzytkownika != hash:
            wyswietl_komunikat('Błąd logowania!', 'Błędny login lub hasło. Spróbuj ponownie.', QMessageBox.Warning)
            rejestracja_zdarzenia('Błąd logowania - Błędne hasło'.format(self.textName.text()), logujacy_sie_uzytkownik.login, log)
            self.reject()
            return

        if logujacy_sie_uzytkownik.administrator is False:
            wyswietl_komunikat('Błąd logowania!', 'Brak uprawnień administratora.', QMessageBox.Warning)
            rejestracja_zdarzenia('Błąd logowania - Brak uprawnień administratora'.format(self.textName.text()), logujacy_sie_uzytkownik.login , log)
            self.reject()
            return

        rejestracja_zdarzenia('Zalogowano'.format(self.textName.text()),
                              logujacy_sie_uzytkownik.login, log)

        self.aktualny_uzytkownik_id = logujacy_sie_uzytkownik.id # przetrzymanie informacji o aktualnie zalogowanym użytkowniku

        self.accept()


algorytm_rozpoznawania_twarzy = cv2.face.LBPHFaceRecognizer_create()
# rozpoznawacz_twarzy = cv2.face.EigenFaceRecognizer_create()
# rozpoznawacz_twarzy = cv2.face.FisherFaceRecognizer_create()
subjects = []
subjects_loginy = []


def aktualizuj_loginy():
    for osoba in sesja.query(Osoba).all():
        subjects.append(osoba.imie_nazwisko)
        subjects_loginy.append(osoba.login)


class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cv_img = None
        self.ret = None
        self.kamera_potrzebna = False
        self.angle = 90
        self.scale_factor = 1.0

    def run(self):
        # capture from webcam
        self.kamera_potrzebna = True
        self.cap = cv2.VideoCapture(0) #, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        #time.sleep(0.5)
        

        try:
            while self.kamera_potrzebna:
                self.ret, self.cv_img = self.cap.read()
                (h, w) = self.cv_img.shape[:2]
                center = (w//2, h//2)
                M = cv2.getRotationMatrix2D(center, self.angle, self.scale_factor)
                self.rotated_img = cv2.warpAffine(self.cv_img, M, (w, h))
                if self.ret:
                    self.change_pixmap_signal.emit(self.rotated_img)
        except AttributeError:
            wyswietl_komunikat('Błąd kamery', 'Błąd kamery. Sprawdź podłączenie.', QMessageBox.Critical)
   
                

    def zrob_zdjecie(self):
        nadawca2 = self.sender()
        try:
            if nadawca2.text() == "&Zrob zdjecie":
                zdjecie_plik = "opencv_frame.png"
                (h, w) = self.cv_img.shape[:2]
                center = (w//2, h//2)
                M = cv2.getRotationMatrix2D(center, self.angle, self.scale_factor)
                self.rotated_img = cv2.warpAffine(self.cv_img, M, (w, h))
                cv2.imwrite(zdjecie_plik, self.rotated_img)
                return self.rotated_img
            else:
                pass
        except ValueError:
            QMessageBox.warning(self, "Blad", "Bledne dane", QMessageBox.Ok)

    def stop(self):
        self.kamera_potrzebna = False
        self.wait()
        self.cap.release()




# sekcja odpowiedzialna za wyświetlanie wideo z OpenCV
video_thread = VideoThread()


class Aplikacja(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Sejf wieloskrytkowy")

        self.setCentralWidget(InterfejsAplikacji())


class InterfejsAplikacji(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.zarzadzanie = None
        self.identyfikacja = None
        self.interfejs()

    def interfejs(self):
        # układy
        uklad_glowny = QVBoxLayout()
        uklad_poziomy = QHBoxLayout()

        # etykiety
        etykieta_wybierz_co_robic = QLabel("Wybierz co chcesz zrobić", self)

        # przyciski
        otworz_skrytke_btn = QPushButton("&Otwórz skrytkę", self)
        zarzadzaj_baza_osob_btn = QPushButton("&Zarządzaj bazą danych", self)

        # przypisanie przycisków do poziomego układu
        uklad_poziomy.addWidget(otworz_skrytke_btn)
        uklad_poziomy.addWidget(zarzadzaj_baza_osob_btn)

        # działanie przycisków
        otworz_skrytke_btn.clicked.connect(self.okno_identyfikacja)
        zarzadzaj_baza_osob_btn.clicked.connect(self.okno_zarzadzanie_baza)

        # przypisanie elementów do głównego układu
        uklad_glowny.addWidget(etykieta_wybierz_co_robic)
        uklad_glowny.addLayout(uklad_poziomy)

        # ustawienie układu głównego
        self.setLayout(uklad_glowny)
        self.setGeometry(20, 30, 300, 100)
        self.show()

    def okno_identyfikacja(self):
        self.identyfikacja = Identyfikacja()
        self.identyfikacja.show()

    def okno_zarzadzanie_baza(self):
        self.login = Login()
        self.login.show()

        if self.login.exec_() == QDialog.Accepted:
            self.zarzadzanie = ZarzadzanieBaza()
            self.zarzadzanie.aktualny_uzytkownik_id = self.login.aktualny_uzytkownik_id
            self.zarzadzanie.show()


class EdycjaUzytkownika(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.admin = False

        login_lbl = QLabel("Login", self)
        imie_nazwisko_lbl = QLabel("Imie i nazwisko", self)
        haslo_lbl = QLabel("Haslo", self)
        skrytka_lbl = QLabel("Skrytka", self)

        self.login_edt = QLineEdit(self)
        self.imie_nazwisko_edt = QLineEdit(self)
        self.haslo_edt = QLineEdit(self)
        self.haslo_edt.setEnabled(False)
        self.haslo_edt.setPlaceholderText('Hasło jest konieczne tylko dla kont z uprawnieniami administratora')

        self.czy_administrator = QCheckBox(self)
        self.czy_administrator.stateChanged.connect(self.ustaw_admin)
        self.czy_administrator.setText("Administrator")

        self.skrytka_combobox = QComboBox()
        for s in lista_skrytek:
            self.skrytka_combobox.addItem(str(s))

        self.btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)

        self.glowny_layout = QVBoxLayout()
        self.podglowny_layout = QHBoxLayout()
        self.lbl_layout = QVBoxLayout()
        self.edt_layout = QVBoxLayout()

        self.lbl_layout.addWidget(login_lbl)
        self.edt_layout.addWidget(self.login_edt)

        self.lbl_layout.addWidget(imie_nazwisko_lbl)
        self.edt_layout.addWidget(self.imie_nazwisko_edt)

        self.lbl_layout.addWidget(haslo_lbl)
        self.edt_layout.addWidget(self.haslo_edt)

        self.lbl_layout.addWidget(skrytka_lbl)
        self.edt_layout.addWidget(self.skrytka_combobox)

        self.podglowny_layout.addLayout(self.lbl_layout)
        self.podglowny_layout.addLayout(self.edt_layout)
        self.glowny_layout.addLayout(self.podglowny_layout)
        self.glowny_layout.addWidget(self.czy_administrator)
        self.glowny_layout.addWidget(self.btn_box)

        self.setLayout(self.glowny_layout)

        self.setWindowTitle('Dodaj/edytuj użytkownika')
        
        self.show()

    def ustaw_admin(self):
        if self.czy_administrator.isChecked():
            self.admin = True
            self.haslo_edt.setEnabled(True)
            self.haslo_edt.setPlaceholderText('')
        else:
            self.admin = False
            self.haslo_edt.setEnabled(False)
            self.haslo_edt.setPlaceholderText('Hasło jest konieczne tylko dla kont z uprawnieniami administratora')


class ZarzadzanieBaza(QWidget):
    def __init__(self):
        super().__init__()
        self.wybrany_uzytkownik_id = None
        self.zmodyfikowano_uzytkownika = None
        self.nowa_nazwa_uzytkownika = None
        self.usuniety_uzytkownik = None
        self.usuniety_uzytkownik = None
        self.czy_usunieto_uzytkownika = None
        self.czy_dodano_uzytkownika = None
        self.dodany_uzytkownik = None
        self.czy_wybrano_uzytkownika = None
        self.wybrany_uzytkownik = None
        self.wybrany_uzytkownik_login = None
        self.lista_osob_do_wyboru = None
        self.aktualny_uzytkownik_id = None

        uklad_przyciskow = QHBoxLayout()
        uklad_glowny = QVBoxLayout()
        uklad_edycji_uzytkownika = QVBoxLayout()
        uklad_aktualnego_uzytkownika = QGridLayout()

        self.aktualizuj_algorytm_btn = QPushButton('&Aktualizuj algorytm', self)
        self.aktualizuj_algorytm_btn.clicked.connect(self.ucz_sie)
        self.aktualizuj_algorytm_btn.setFixedWidth(300)
        self.aktualizuj_algorytm_btn.setFixedHeight(200)

        etykieta_wybrany_uzytkownik = QLabel(self)
        etykieta_wybrany_uzytkownik.setText('Użytkownik:')
        self.wybrany_uzytkownik_pole = QLineEdit(self)
        self.wybrany_uzytkownik_pole.setEnabled(False)

        etykieta_wybrany_uzytkownik_imie_nazwisko = QLabel(self)
        etykieta_wybrany_uzytkownik_imie_nazwisko.setText('Imie i nazwisko:')
        self.wybrany_uzytkownik_imie_nazwisko_pole = QLineEdit(self)
        self.wybrany_uzytkownik_imie_nazwisko_pole.setEnabled(False)

        etykieta_wybrany_uzytkownik_skrytka = QLabel(self)
        etykieta_wybrany_uzytkownik_skrytka.setText('Skrytka:')
        self.wybrany_uzytkownik_skrytka_pole = QLineEdit(self)
        self.wybrany_uzytkownik_skrytka_pole.setEnabled(False)

        etykieta_wybrany_uzytkownik_katalog = QLabel(self)
        etykieta_wybrany_uzytkownik_katalog.setText('Katalog:')
        self.wybrany_uzytkownik_katalog_pole = QLineEdit(self)
        self.wybrany_uzytkownik_katalog_pole.setEnabled(False)

        wybierz_uzytkownika_btn = QPushButton("&Wybierz użytkownika", self)
        wybierz_uzytkownika_btn.clicked.connect(self.wybierz_uzytkownika)
        wybierz_uzytkownika_btn.setFixedWidth(300)

        self.zrob_zdjecie_wybranego_uzytkownika_btn = QPushButton("Zrob &zdjęcie dla wybranego użytkownika")
        #self.zrob_zdjecie_wybranego_uzytkownika_btn.clicked.connect(self.zapisz_zdjecie)
        self.zrob_zdjecie_wybranego_uzytkownika_btn.clicked.connect(self.panel_robienia_zdjec)

        self.zrob_zdjecie_wybranego_uzytkownika_btn.setEnabled(False)

        self.modyfikuj_wybranego_uzytkownika_btn = QPushButton("&Modyfikuj użytkownika", self)
        self.modyfikuj_wybranego_uzytkownika_btn.clicked.connect(self.modyfikuj_uzytkownika)
        self.modyfikuj_wybranego_uzytkownika_btn.setEnabled(False)

        dodaj_uzytkownika_btn = QPushButton("&Dodaj użytkownika", self)
        dodaj_uzytkownika_btn.clicked.connect(self.dodaj_uzytkownika)
        dodaj_uzytkownika_btn.setFixedWidth(300)

        self.usun_uzytkownika_btn = QPushButton("&Usuń użytkownika", self)
        self.usun_uzytkownika_btn.clicked.connect(self.usun_uzytkownika)
        self.usun_uzytkownika_btn.setEnabled(False)

        # sekcja odpowiedzialna za wyświetlanie wideo z OpenCV
        #video_thread.start()
        #video_thread.change_pixmap_signal.connect(self.odswiezanie_obrazu)

        #self.display_width = 1280
        #self.display_height = 720
        #self.podglad_wideo = QLabel(self)  # etykieta będąca de-facto podglądem z kamery
        #self.podglad_wideo.resize(self.display_width, self.display_height)
        # koniec sekcji

        uklad_edycji_uzytkownika.addWidget(wybierz_uzytkownika_btn)

        uklad_aktualnego_uzytkownika.addWidget(etykieta_wybrany_uzytkownik, 0, 0)
        uklad_aktualnego_uzytkownika.addWidget(self.wybrany_uzytkownik_pole, 0, 1)
        uklad_aktualnego_uzytkownika.addWidget(etykieta_wybrany_uzytkownik_imie_nazwisko, 1, 0)
        uklad_aktualnego_uzytkownika.addWidget(self.wybrany_uzytkownik_imie_nazwisko_pole, 1, 1)
        uklad_aktualnego_uzytkownika.addWidget(etykieta_wybrany_uzytkownik_skrytka, 2, 0)
        uklad_aktualnego_uzytkownika.addWidget(self.wybrany_uzytkownik_skrytka_pole, 2, 1)
        uklad_aktualnego_uzytkownika.addWidget(etykieta_wybrany_uzytkownik_katalog, 3, 0)
        uklad_aktualnego_uzytkownika.addWidget(self.wybrany_uzytkownik_katalog_pole, 3, 1)

        uklad_edycji_uzytkownika.addLayout(uklad_aktualnego_uzytkownika)

        uklad_edycji_uzytkownika.addWidget(self.zrob_zdjecie_wybranego_uzytkownika_btn)
        uklad_edycji_uzytkownika.addWidget(self.modyfikuj_wybranego_uzytkownika_btn)
        uklad_edycji_uzytkownika.addWidget(self.usun_uzytkownika_btn)
        uklad_edycji_uzytkownika.setSpacing(10)

        uklad_przyciskow.addWidget(self.aktualizuj_algorytm_btn)
        uklad_przyciskow.addLayout(uklad_edycji_uzytkownika)
        uklad_przyciskow.addWidget(dodaj_uzytkownika_btn)
        uklad_przyciskow.addStretch()

        #uklad_glowny.addWidget(self.podglad_wideo)
        uklad_glowny.addLayout(uklad_przyciskow)

        self.setLayout(uklad_glowny)
        self.setWindowTitle('Zarządzanie bazą')

    def panel_robienia_zdjec(self):
        self.okno = Robienie_zdjecia.RobienieZdjecia(video_thread, self.zapisz_zdjecie)
        self.okno.show()

    # robienie zdjęcia i dodawanie go do folderu wybranego użytkownika
    def zapisz_zdjecie(self):

        osoba_do_zapisu = sesja.query(Osoba).filter(Osoba.id == self.wybrany_uzytkownik_id).one()

        zdjecie_do_zapisu = video_thread.rotated_img
        sciezka_do_zapisu = os.path.join(katalog_glowny, osoba_do_zapisu.katalog)

        # Sprawdzamy, czy katalog już istnieje
        if not os.path.exists(os.path.join(katalog_glowny, osoba_do_zapisu.katalog)):# jeśli katalog nie istnieje
            os.makedirs(os.path.join(katalog_glowny, osoba_do_zapisu.katalog))  # to go tworzymy

        # Sprawdzamy czy w katalogu znajdują się wgrane zdjęcia
        os.chdir(sciezka_do_zapisu)
        zdjecia_w_katalogu = os.listdir(os.getcwd())

        # Dla każdego zdjęcia sprawdzamy czy jest już w bazie danych
        numery = []
        i = 0
        for zdjecie in zdjecia_w_katalogu:
            numer = zdjecie.replace('.jpg', '')
            numery.append(numer)
            try:
                # Próbujemy wywołać select zdjęcia z katalogu w bazie danych
                # Jeśli zdjęcia nie ma w bazie danych zostanie zgłoszony wyjątek
                inst_zdjecie = sesja.query(Zdjecie).filter(Zdjecie.numer == numer).one()
            except sqlalchemy.exc.NoResultFound:
                # Skoro wyjątek został zgłoszony, to zdjęcie nie jest wpisanę w bazę i trzeba to zrobić
                sesja.add(Zdjecie(numer=numer, sciezka=osoba_do_zapisu.katalog, osoba_id=osoba_do_zapisu.id))
                sesja.commit()

        # Sprawdzamy, czy w bazie danych są wpisane jakiekolwiek zdjęcia
        inst_zdjecia = sesja.query(Zdjecie).filter(Zdjecie.osoba_id == osoba_do_zapisu.id).order_by(
            desc(Zdjecie.numer)).all()
        if not inst_zdjecia:
            numer = 1
        else:
            # Jeśli już jakieś zdjęcia są wpisane, to sprawdzamy czy nie są to puste nazwy bez plików
            zdjecia_do_sprawdzenia = sesja.query(Zdjecie).filter(Zdjecie.osoba_id == osoba_do_zapisu.id).all()
            for zdjecie_spr in zdjecia_do_sprawdzenia:
                sciezka_temp = os.path.join(katalog_glowny, zdjecie_spr.sciezka, str(zdjecie_spr.numer) + '.jpg')
                if not os.path.exists(sciezka_temp):
                    sesja.query(Zdjecie).filter(Zdjecie.id == zdjecie_spr.id).delete()  # jeśli plik już nie istnieje
                    # to usuwamy wpis z bazy danych
                    sesja.commit()

            #  jeśli są to szukamy pierwszego wolnego numeru
            x = 0
            numery = []
            for inst_zdjecie in inst_zdjecia:
                numery.append(inst_zdjecia[x].numer)
                x = x + 1
            numery.sort()
            y = 0
            while True:
                if y not in numery:
                    numer = y
                    break
                else:
                    y = y + 1

        # zapisanie zdjęcia jako pliku z pierwszym wolnym numerem i dodanie go do bazy danych
        plik_nazwa = str(numer) + '.jpg'

        zapisano = cv2.imwrite(plik_nazwa, zdjecie_do_zapisu)
        # Jeśli udało się zapisać plik to dodajemy jego ścieżkę i numer do bazy danych
        if zapisano:
            sesja.add(Zdjecie(numer=numer, sciezka=osoba_do_zapisu.katalog, osoba_id=osoba_do_zapisu.id))
            sesja.commit()
            inst_zdjecia = sesja.query(Zdjecie).filter(Zdjecie.osoba_id == osoba_do_zapisu.id).all()

    # dodawanie nowej osoby do bazy danych
    def dodaj_uzytkownika(self):
        # okno dialogowe pobierające tekst od użytkownika
        aktualizuj_loginy()
        dodawanie_uzytkownika = EdycjaUzytkownika(self)
        if dodawanie_uzytkownika.exec_() == QDialog.Accepted:
            dodany_login = dodawanie_uzytkownika.login_edt.text()
            dodany_uzytkownik = dodawanie_uzytkownika.imie_nazwisko_edt.text()
            hash = hashlib.sha256(dodawanie_uzytkownika.haslo_edt.text().encode('utf-8')).hexdigest()
            skrytka = dodawanie_uzytkownika.skrytka_combobox.currentText()
            czy_admin = dodawanie_uzytkownika.czy_administrator.isChecked()

            # Sprawdzenie, czy użytkownik o takim samym loginie już istnieje
            if dodany_login in subjects_loginy:
                wyswietl_komunikat('Błąd!', 'Nie można dodać użytkownika: {}. Login zajęty lub użytkownik już istnieje!'.format(dodany_login), QMessageBox.Warning)
                return

            sesja.add(Osoba(login=dodany_login, imie_nazwisko=dodany_uzytkownik, hash=hash, skrytka=skrytka, administrator=czy_admin))
            sesja.commit()

            # https://docs.sqlalchemy.org/en/20/changelog/migration_20.html#migration-20-query-usage

            try:
                inst_osoba = sesja.query(Osoba).filter(Osoba.login == dodany_login).one()
            except sqlalchemy.exc.NoResultFound:
                try:
                    with sesja:
                        inst_osoba = select(Osoba).filter_by(Osoba.login == dodany_login).one()
                except Exception as e:
                    print(e)
                    try:
                        inst_osoba = sesja.execute(select(Osoba).filter_by(login=dodany_login)).one()
                    except Exception as e:
                        print(e)

            wyswietl_komunikat('Dodano użytkownika', 'Dodano użytkownika {}'.format(inst_osoba.login), QMessageBox.Information)
            aktualny_uzytkownik = sesja.query(Osoba).filter(Osoba.id == self.aktualny_uzytkownik_id).one()
            rejestracja_zdarzenia('Edycja bazy - Dodano użytkownika {} {}'.format(inst_osoba.login, inst_osoba.imie_nazwisko), aktualny_uzytkownik.login, log)

            temp_katalog = os.path.join('test', 's' + str(inst_osoba.id))
            inst_osoba.katalog = temp_katalog
            sesja.commit()

            # Sprawdzamy, czy katalog już istnieje
            czy_istnieje = os.path.exists(inst_osoba.katalog)
            if not czy_istnieje:  # jeśli katalog nie istnieje
                os.makedirs(inst_osoba.katalog)  # to go tworzymy

    # usuwanie osoby z bazy danych
    def usun_uzytkownika(self):
        self.usuniety_uzytkownik = ''

        self.wczytaj_liste_z_bazy()

        # Dialog upewniający się o usunięciu użytkownika
        dlg = QDialog()
        dlg.setWindowTitle("Czy na pewno usunąć użytkownika?")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        dlg.buttonBox = QDialogButtonBox(QBtn)
        dlg.buttonBox.accepted.connect(dlg.accept)
        dlg.buttonBox.rejected.connect(dlg.reject)

        dlg.layout = QVBoxLayout()
        message = QLabel("Czy na pewno usunąć użytkownika {}?".format(self.wybrany_uzytkownik_login))
        dlg.layout.addWidget(message)
        dlg.layout.addWidget(dlg.buttonBox)
        dlg.setLayout(dlg.layout)

        if dlg.exec_():
            inst_osoba_do_usuniecia = sesja.query(Osoba).filter(Osoba.login == self.wybrany_uzytkownik_login).one()
            katalog_do_usuniecia = os.path.join(katalog_glowny, inst_osoba_do_usuniecia.katalog)
            try:
                if katalog_do_usuniecia != katalog_glowny or katalog_do_usuniecia != os.path.join(katalog_glowny, ''):
                    shutil.rmtree(katalog_do_usuniecia)
                else:
                    pass

            except PermissionError as e:
                wyswietl_komunikat('Błąd!', 'Nie udało się usunąć katalogu. Błąd {}'.format(e), QMessageBox.Warning)

            except FileNotFoundError:
                dlg = QDialog()
                dlg.setWindowTitle('Błąd!')
                message = QLabel('Katalog użytkownika nie istnieje. Czy usunąć sam wpis z bazy danych?')
                QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                dlg.buttonBox = QDialogButtonBox(QBtn)
                dlg.buttonBox.accepted.connect(dlg.accept)
                dlg.buttonBox.rejected.connect(dlg.reject)

                dlg.layout = QVBoxLayout()
                dlg.layout.addWidget(message)
                dlg.layout.addWidget(dlg.buttonBox)
                dlg.setLayout(dlg.layout)

                if dlg.exec_():
                    sesja.query(Osoba).filter(Osoba.login == self.wybrany_uzytkownik_login).delete()
                    sesja.commit()

                    wyswietl_komunikat('Usunięto użytkownika',
                                       'Usunięto użytkownika {}'.format(inst_osoba_do_usuniecia.login),
                                       QMessageBox.Information)

            except Exception:
                wyswietl_komunikat('Inny błąd', 'Wystąpił nieznany błąd', QMessageBox.Warning)
            else:
                sesja.query(Osoba).filter(Osoba.login == self.wybrany_uzytkownik_login).delete()
                sesja.commit()

                aktualizuj_loginy()
                self.wybrany_uzytkownik_pole.setPlaceholderText('')
                self.wybrany_uzytkownik_katalog_pole.setPlaceholderText('')
                wyswietl_komunikat('Usunięto użytkownika', 'Usunięto użytkownika {}'.format(inst_osoba_do_usuniecia.login), QMessageBox.Information)
                aktualny_uzytkownik = sesja.query(Osoba).filter(Osoba.id == self.aktualny_uzytkownik_id).one()
                rejestracja_zdarzenia(
                    'Edycja bazy - Usunięto użytkownika {} {}'.format(inst_osoba_do_usuniecia.login, inst_osoba_do_usuniecia.imie_nazwisko),
                    aktualny_uzytkownik.login, log)

    # wybór osoby do modyfikacji
    def wczytaj_liste_z_bazy(self):
        self.lista_osob_do_wyboru = ['']
        for temp_osoba in sesja.query(Osoba).all():
            self.lista_osob_do_wyboru.append(temp_osoba.login)

    def wybierz_uzytkownika(self):
        self.wczytaj_liste_z_bazy()
        self.wybrany_uzytkownik_login, self.czy_wybrano_uzytkownika = QInputDialog.getItem(self, "Wybierz uzytkownika",
                                                                                    "Uzytkownik: ",
                                                                                    self.lista_osob_do_wyboru, 0, False)

        if self.czy_wybrano_uzytkownika:
            temp_osoba = sesja.query(Osoba).filter(Osoba.login == self.wybrany_uzytkownik_login).one()
            self.wybrany_uzytkownik_id = temp_osoba.id

            self.wybrany_uzytkownik_pole.setPlaceholderText(temp_osoba.login)
            self.wybrany_uzytkownik_imie_nazwisko_pole.setPlaceholderText(temp_osoba.imie_nazwisko)
            self.wybrany_uzytkownik_skrytka_pole.setPlaceholderText(str(temp_osoba.skrytka))
            self.wybrany_uzytkownik_katalog_pole.setPlaceholderText(temp_osoba.katalog)

            #if not video_thread.ret:
            #    self.zrob_zdjecie_wybranego_uzytkownika_btn.setEnabled(False)
            #else:
            #    self.zrob_zdjecie_wybranego_uzytkownika_btn.setEnabled(True)

            self.zrob_zdjecie_wybranego_uzytkownika_btn.setEnabled(True)

            self.modyfikuj_wybranego_uzytkownika_btn.setEnabled(True)
            self.usun_uzytkownika_btn.setEnabled(True)

    def modyfikuj_uzytkownika(self):
        
        aktualizuj_loginy()
        edycja_uzytkownika = EdycjaUzytkownika(self)

        inst_wybrany_uzytkownik = sesja.query(Osoba).filter(Osoba.login == self.wybrany_uzytkownik_login).one()
        wybrany_uzytkownik_id = inst_wybrany_uzytkownik.id

        edycja_uzytkownika.login_edt.setText(inst_wybrany_uzytkownik.login)
        edycja_uzytkownika.imie_nazwisko_edt.setText(inst_wybrany_uzytkownik.imie_nazwisko)
        edycja_uzytkownika.haslo_edt.setText('')
        edycja_uzytkownika.czy_administrator.setChecked(inst_wybrany_uzytkownik.administrator)

        if wybrany_uzytkownik_id == self.aktualny_uzytkownik_id:
            edycja_uzytkownika.czy_administrator.setEnabled(False)
            edycja_uzytkownika.czy_administrator.setChecked(True)
            edycja_uzytkownika.czy_administrator.setText("Nie mozna usunac uprawnien administratora samemu/ej sobie!")

        if edycja_uzytkownika.exec_() == QDialog.Accepted:
            edytowany_uzytkownik_login = edycja_uzytkownika.login_edt.text()
            edytowany_uzytkownik = edycja_uzytkownika.imie_nazwisko_edt.text()
            hash = hashlib.sha256(edycja_uzytkownika.haslo_edt.text().encode('utf-8')).hexdigest()
            skrytka = edycja_uzytkownika.skrytka_combobox.currentText()
            czy_admin = edycja_uzytkownika.czy_administrator.isChecked()
            czy_edytowano_uzytkownika = True

            if czy_edytowano_uzytkownika:
                
                inst_edytowana_osoba = sesja.query(Osoba).filter(Osoba.id == self.wybrany_uzytkownik_id).one()
                inst_edytowana_osoba.login = edytowany_uzytkownik_login
                inst_edytowana_osoba.imie_nazwisko = edytowany_uzytkownik
                inst_edytowana_osoba.hash = hash
                inst_edytowana_osoba.skrytka = skrytka
                inst_edytowana_osoba.administrator = czy_admin
                sesja.commit()
                aktualny_uzytkownik = sesja.query(Osoba).filter(Osoba.id == self.aktualny_uzytkownik_id).one()
                aktualizuj_loginy()
                rejestracja_zdarzenia(
                    'Edycja bazy - Edycja użytkownika {} {}'.format(inst_edytowana_osoba.login,
                                                                      inst_edytowana_osoba.imie_nazwisko),
                    aktualny_uzytkownik.login, log)

    def ucz_sie(self):
        self.aktualizuj_algorytm_btn.setEnabled(False)
        os.chdir(katalog_glowny)

        twarze, podpisy = przygotuj_dane_algorytmu('test')  # przygotowanie danych do nauki modelu

        algorytm_rozpoznawania_twarzy.train(twarze, np.array(podpisy))  # przygotowanie modelu twarzy
        algorytm_rozpoznawania_twarzy.save(os.path.join(katalog_glowny, 'rozpoznawacz.yml'))  # zapisanie nauczonego modelu twarzy
        wyswietl_komunikat('Algorytm zaktualizowany', 'Algorytm został zaktualizowany.', QMessageBox.Information)
        self.aktualizuj_algorytm_btn.setEnabled(True)

    #@pyqtSlot(np.ndarray)
    #def odswiezanie_obrazu(self, cv_img):
    #    qt_img = self.konwersja_cv_qt(cv_img)
    #    self.podglad_wideo.setPixmap(qt_img)

    #def konwersja_cv_qt(self, cv_img):
    #    rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    #    h, w, ch = rgb_img.shape
    #    bytes_per_line = ch * w
    #    zmiana_na_qt_format = QtGui.QImage(rgb_img.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
    #    p = zmiana_na_qt_format.scaled(self.display_width, self.display_height, Qt.KeepAspectRatio)
    #    return QPixmap.fromImage(p)


#def rysuj_prostokat(img, rect):
#    x, y, w, h = rect
#    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)


#def rysuj_text(img, text, x, y):
#    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)


def przygotuj_dane_algorytmu(folder_ze_zdjeciami):
    dirs = os.listdir(folder_ze_zdjeciami)
    twarze = []
    podpisy = []

    for katalog in dirs:
        if not katalog.startswith('s'):
            continue
        podpis = int(katalog.replace('s', ''))
        sciezka_do_osoby = os.path.join(folder_ze_zdjeciami, katalog)
        pliki_zdjecia_osoby = os.listdir(sciezka_do_osoby)

        for plik_zdjecie in pliki_zdjecia_osoby:
            if plik_zdjecie.startswith('.'):
                continue
            sciezka_do_zdjecia = sciezka_do_osoby + '/' + plik_zdjecie
            zdjecie = cv2.imread(sciezka_do_zdjecia)

            # wyrównanie zdjecia przed rozpoznaniem twarzy i dodaniem jej do bazy rozpoznawacza
            wyrownane_zdjecie = wyrownanie_twarzy.wyrownaj_twarz(zdjecie)

            try:
                twarz, rect = wykrywanie_twarzy(wyrownane_zdjecie)
                if twarz is not None:
                    twarze.append(twarz)
                    podpisy.append(podpis)
            except cv2.error:
                pass

    return twarze, podpisy


def wykrywanie_twarzy(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    twarze = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    if len(twarze) == 0:
        return None, None

    x, y, w, h = twarze[0]
    gray = gray[y:y + h, x:x + w]  # focus na twarzy
    gray = cv2.resize(gray, (500, 500))
    return gray, twarze[0]


class Identyfikacja(QWidget):
    def __init__(self):
        super().__init__()
        self.rozpoznany_uzytkownik = None
        self.subjects = None
        self.skrytka_otwarta = False

        # sekcja odpowiedzialna za wyświetlanie wideo z OpenCV
        video_thread.start()
        video_thread.change_pixmap_signal.connect(self.odswiezanie_obrazu)

        self.display_width = 480
        self.display_height = 320
        self.podglad_wideo = QLabel(self)
        self.podglad_wideo.resize(self.display_width, self.display_height)

        # przyciski
        self.identyfikuj_btn = QPushButton("Identyfikuj", self)
        self.identyfikuj_btn.clicked.connect(self.zapisz_zdjecie_identyfikuj)
        self.zablokuj_skrytke_btn = QPushButton("Zablokuj skrytkę", self)
        self.zablokuj_skrytke_btn.setEnabled(False)
        self.zablokuj_skrytke_btn.clicked.connect(self.zablokuj_skrytke)

        # układy
        uklad_glowny = QHBoxLayout()
        uklad_przyciskow = QVBoxLayout()

        # dodawanie widgetów do układów
        uklad_glowny.addWidget(self.podglad_wideo)
        uklad_przyciskow.addWidget(self.identyfikuj_btn)
        uklad_przyciskow.addWidget(self.zablokuj_skrytke_btn)
        uklad_glowny.addLayout(uklad_przyciskow)

        # ustawienie układu głównego
        self.setLayout(uklad_glowny)

        self.setGeometry(400, 500, 300, 100)
        self.setWindowTitle("Identyfikacja")

    def closeEvent(self, QCloseEvent):
        try:
            video_thread.stop()
        except Exception:
            pass

    def zapisz_zdjecie_identyfikuj(self):

        self.identyfikuj_btn.setEnabled(False)

        zdjecie_do_zapisu = video_thread.rotated_img
        sciezka_do_zapisu = os.path.join(katalog_glowny, 'identyfikacja')

        os.chdir(sciezka_do_zapisu)
        try:
            cv2.imwrite("identyfikacja.jpg", zdjecie_do_zapisu)
        except cv2.error as e:
            wyswietl_komunikat('Błąd pobrania obrazu', 'Aplikacja nie mogła zapisać obrazu do identyfikacji. Spróbuj ponownie.', QMessageBox.Warning)

        self.rozpoznaj()

    def zablokuj_skrytke(self):
        # zablokuj skrytkę, która została otwarta dla danego użytkownika
        zamknij_skrytke(self.rozpoznany_uzytkownik.skrytka)
        rejestracja_zdarzenia('Zamknięto skrytkę {}'.format(self.rozpoznany_uzytkownik.skrytka), self.rozpoznany_uzytkownik.login, log)
        self.zablokuj_skrytke_btn.setEnabled(False)
        video_thread.start()
        self.podglad_wideo.setHidden(False)
        self.identyfikuj_btn.setEnabled(True)

    def rozpoznaj(self):
        algorytm_rozpoznawania_twarzy.read(os.path.join(katalog_glowny, 'rozpoznawacz.yml'))  # wczytanie modelu nauczonych twarzy

        test_img = cv2.imread(os.path.join(katalog_glowny, 'identyfikacja/identyfikacja.jpg'))
        img = test_img.copy()

        twarz, rect = wykrywanie_twarzy(img)

        if twarz is None:
            wyswietl_komunikat('Błąd!', 'Błąd! Nie wykryto twarzy. Spróbuj ponownie.', QMessageBox.Information)
            rejestracja_zdarzenia('Nieudane otwarcie skrytki', 'n/d', log)
            self.identyfikuj_btn.setEnabled(True)
            self.podglad_wideo.setHidden(False)
            video_thread.start()
        else:
            podpis, niepewnosc = algorytm_rozpoznawania_twarzy.predict(twarz)
            try:
                self.rozpoznany_uzytkownik = sesja.query(Osoba).filter(Osoba.katalog == os.path.join('test', 's{}'.format(podpis))).one()  # zamiast test przekazywać folder obejmujący jako argument przy wywołaniu funkcji
            except IndexError as e:
                print('IndexError {}'.format(e))
                self.identyfikuj_btn.setEnabled(True)

            except sqlalchemy.exc.NoResultFound as e:
                print('NoResultFound {}'.format(e))
                self.identyfikuj_btn.setEnabled(True)

            except Exception as e:
                print('Exception {}'.format(e))
                self.identyfikuj_btn.setEnabled(True)

            else:
                podpis_tekst = '{}, np: {}'.format(self.rozpoznany_uzytkownik.login, str(niepewnosc))

                if niepewnosc <= 40:
                    rejestracja_zdarzenia('Otwarto skrytkę {}'.format(self.rozpoznany_uzytkownik.skrytka),
                                          self.rozpoznany_uzytkownik.login, log)
                    wyswietl_komunikat('Otwieranie skrytki', 'Witaj {} - otworzy się skrytka {} ({})'.format(self.rozpoznany_uzytkownik.imie_nazwisko, self.rozpoznany_uzytkownik.skrytka, skrytka_gdzie[self.rozpoznany_uzytkownik.skrytka - 1]), QMessageBox.Information)
                    otworz_skrytke(self.rozpoznany_uzytkownik.skrytka)
                    self.zablokuj_skrytke_btn.setEnabled(True)
                    try:
                        video_thread.stop()
                    except Exception:
                        pass
                    self.podglad_wideo.setHidden(True)
                else:
                    wyswietl_komunikat('Błąd', 'Twarz nierozpoznana. Spróbuj ponownie.', QMessageBox.Warning)
                    rejestracja_zdarzenia('Nieudane otwarcie skrytki', self.rozpoznany_uzytkownik.login, log)
                    self.identyfikuj_btn.setEnabled(True)

            return img

    @pyqtSlot(np.ndarray)
    def odswiezanie_obrazu(self, cv_img):
        qt_img = self.konwersja_cv_qt(cv_img)
        self.podglad_wideo.setPixmap(qt_img)

    def konwersja_cv_qt(self, cv_img):
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        zmiana_na_qt_format = QtGui.QImage(rgb_img.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = zmiana_na_qt_format.scaled(self.display_width, self.display_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)


def wyswietl_komunikat(tytul_okna, tekst_komunikatu, ikona_komunikatu):
    dlg = QMessageBox()
    dlg.setWindowTitle(tytul_okna)
    dlg.setText(tekst_komunikatu)
    dlg.setStandardButtons(QMessageBox.Ok)
    dlg.setIcon(ikona_komunikatu)
    przyjeto = dlg.exec_()
    return przyjeto


def rejestracja_zdarzenia(zdarzenie, kto, plik):
    with open(plik, 'a') as p:
        p.write('Zdarzenie: {} Kto: {} Kiedy: {}\n'.format(zdarzenie, kto, dt.now().strftime('%Y-%m-%d %H:%M:%S')))


app = QApplication(sys.argv)
w = Aplikacja()
w.show()
app.exec()
