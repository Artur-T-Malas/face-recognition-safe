#Podgląd z kamery w Qt5: ®https://gist.github.com/docPhil99/ca4da12c9d6f29b9cea137b617c7b8b1

from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QLineEdit, QPushButton, QHBoxLayout, \
    QMessageBox, QComboBox, QListWidget, QDialog, QDialogButtonBox, QListWidgetItem, QMainWindow, QInputDialog
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QThread
import cv2
import sys
import numpy as np
import os

#---===---M E T O D Y   O G Ó L N E---===---

def listaZPliku(sciezka):
    listaTemp = []
    plik = open(sciezka, "r")
    for line in plik:
        listaTemp.append(line.strip())
    plik.close()
    return listaTemp

def listaDoPliku(lista, sciezka):
    plik = open(sciezka, "wt")
    for x in range(len(lista)):
        print(lista[x], file=plik)
    plik.close()

#---===---K L A S Y---===---

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def run(self):
        #capture from web cam
        cap = cv2.VideoCapture(0)#, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        while True:
            ret, self.cv_img = cap.read()
            if ret:
                self.change_pixmap_signal.emit(self.cv_img)

    def zrobZdjecie(self, cv_img):
        print("Proboje zrobic zdjecie")

        nadawca2 = self.sender()
        #print("nadawca2 = self.sender()")
        try:

            if nadawca2.text() == "&Zrob zdjecie":
                zdjeciePlik = "opencv_frame.png"
                cv2.imwrite(zdjeciePlik, self.cv_img)
                print("Zrobiono zdjecie")
                # cv2.imwrite("Zdjecie.png", zdjecie)
                return self.cv_img

            else:
                pass

        except ValueError:
            QMessageBox.warning(self, "Blad", "Bledne dane", QMessageBox.Ok)


class Identyfikacja(QWidget):

    listaUzytkownikow = []
    uzytkownicyKatalogi = []
    parentDir = os.getcwd()
    trainingDirs = []
    sciezka = ""

    def __init__(self, parent = None):
        super().__init__(parent)

        self.numerNaLiscie = 0

        self.interfejs()


    def interfejs(self):

        #układ
        ukladT = QGridLayout()

        #etykiety
        etykietaImieNazwisko = QLabel("Imie i nazwisko", self)
        self.etykietaWybranyUzytkownik = QLabel("Brak", self)
        self.sciezkaDoZapisu = QLabel("Empty", self)

        #pola edycyjne
        self.imieNazwisko = QLineEdit()

        #przyciski
        dodajUzytkownikaBtn = QPushButton("&Dodaj uzytkownika", self)
        zrobZdjecieBtn = QPushButton("&Zrob zdjecie", self)
        pokazListeBtn = QPushButton("&Pokaz liste", self)
        zapiszZdjecieBtn = QPushButton("Z&apisz zdjecie", self)
        wybierzUzytkownikaDoZapisuZdjeciaBtn = QPushButton("&Wybierz uzytkownika do zapisu zdjecia", self)
        wybierzUzytkownikaDoZapisuZdjeciaBtn.clicked.connect(self.wybierzUzytkownika)
        wczytajPlikListyBtn = QPushButton("W&czytaj plik z lista", self)
        wczytajPlikListyBtn.clicked.connect(self.wczytajListe)


        #lista wyboru


        self.display_width = 1280
        self.display_height = 720
        # create the label that holds the image
        self.image_label = QLabel(self)
        self.image_label.resize(self.display_width, self.display_height)
        # create a text label
        self.textLabel = QLabel('Webcam')

        #przypisanie przycisków do poziomego układu
        ukladH = QHBoxLayout()
        ukladH.addWidget(wczytajPlikListyBtn)
        #ukladH.addWidget(zrobZdjecieBtn)
        ukladH.addWidget(dodajUzytkownikaBtn)
        ukladH.addWidget(pokazListeBtn)

        ukladH2 = QHBoxLayout()
        ukladH2.addWidget(wybierzUzytkownikaDoZapisuZdjeciaBtn)
        ukladH2.addWidget(self.etykietaWybranyUzytkownik)
        ukladH2.addWidget(self.sciezkaDoZapisu)
        ukladH2.addWidget(zrobZdjecieBtn)
        ukladH2.addWidget(zapiszZdjecieBtn)



        #przypisanie pozostałych elementów do głównego układu tabelarycznego
        ukladT.addWidget(etykietaImieNazwisko, 0, 0)
        ukladT.addWidget(self.imieNazwisko, 1, 0)
        ukladT.addWidget(self.image_label, 3, 0)
        ukladT.addLayout(ukladH, 2, 0, 1, 3)
        ukladT.addLayout(ukladH2, 4, 0, 1, 3)

        self.setLayout(ukladT)

        # create the video capture thread
        self.thread = VideoThread()
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.update_image)
        # start the thread
        self.thread.start()

        #działanie przycisków
        dodajUzytkownikaBtn.clicked.connect(self.dodajUzytkownika)
        zrobZdjecieBtn.clicked.connect(self.thread.zrobZdjecie)
        #pokazListeBtn.clicked.connect(self.dodajUzytkownika)
        #pokazListeBtn.clicked.connect(lambda: DialogListyUzytkownikow(self.listaUzytkownikow))
        pokazListeBtn.clicked.connect(self.pokazDialogLista)
        zapiszZdjecieBtn.clicked.connect(self.zapiszZdjecieUzytkownika)




        self.setGeometry(20, 30, 300, 100)
        self.setWindowTitle("Identyfikacja")
        self.show()

    def wczytajListe(self):
        self.listaUzytkownikow = listaZPliku('uzytkownicy.txt')
        print(self.listaUzytkownikow)
        self.aktualizacjaKatalogow()


    def dodajUzytkownika(self):

        nadawca = self.sender()

        try:
            uzytkownikTemp = (self.imieNazwisko.text())
            self.listaUzytkownikow = listaZPliku('uzytkownicy.txt')


            #nie działa
            #for i in range(len(self.listaUzytkownikow)):
            #    self.listaWyborUzytkownika.addItem(self.listaUzytkownikow[i])



            self.numerNaLiscie = len(self.listaUzytkownikow) #nowo dodany użytkownik otrzyma kolejny numer na liscie
            print("Odczytano liste uzytkownikow z pliku, jest: ", len(self.listaUzytkownikow)-1, " pozycji")

            if nadawca.text() == "&Dodaj uzytkownika":
                self.listaUzytkownikow.append(uzytkownikTemp)
                self.numerNaLiscie = self.numerNaLiscie + 1
                listaDoPliku(self.listaUzytkownikow, 'uzytkownicy.txt')
                print("Aktualizuje katalogi")
                self.aktualizacjaKatalogow()
            elif nadawca.text() == "&Pokaz liste":
                print(self.listaUzytkownikow)
            else:
                pass

        except ValueError:
            QMessageBox.warning(self, "Blad", "Bledne dane", QMessageBox.Ok)


    def zlaczDaneUzytkownika(self, nazwa, numer, katalog):
        tempLista = [nazwa, numer, katalog]
        return tempLista



# DODAC ZAPISYWANIE ZDJECIA DO KATALOGU UZYTKOWNIKA - zrobione
    def zapiszZdjecieUzytkownika(self):
        print("------------------------------------------------------------------------")
        nadawca3 = self.sender()
        print("Weszliśmy w funkcje zapiszZdjecieUzytkownika")

        try:
            print("Weszliśmy w try")
            #sciezka = self.uzytkownicyKatalogi[-1][2]

            for uzytkownikNumer in range(len(self.listaUzytkownikow)):
                if self.listaUzytkownikow[uzytkownikNumer] == self.wybranyUzykownik:
                    self.sciezka = self.trainingDirs[uzytkownikNumer]
                    self.sciezkaDoZapisu.setText(self.sciezka)

            print("Katalog do zapisania zdjecia: ", self.sciezka)
            zdjecie = self.thread.cv_img
            if nadawca3.text() == "Z&apisz zdjecie":
                os.chdir(self.sciezka)
                cv2.imwrite("1.jpg", zdjecie)
            else:
                pass

        except ValueError:
            QMessageBox.warning(self, "Blad", "Bledne dane", QMessageBox.Ok)


    def aktualizacjaKatalogow(self): #dodanie katalogu dla nowo dodanych osób

    #USUNĄĆ TWORZENIE NOWYCH POWTARZAJĄCYCH SIĘ ELEMENTÓW NA LIŚCIE

        tempTrainingDirs = []

        print("Sprawdzamy katalogi")
        tempTrainingDirsForFiltering = os.listdir(os.path.join(os.getcwd(), "test")) #Sprawdzamy jakie katalogi już mamy stworzone
        for i in range(len(tempTrainingDirsForFiltering)):
            print("-----------------------------------------------------")
            if tempTrainingDirsForFiltering[i] != ".DS_Store":  #Odrzucamy plik systemowy z MacBook'a
                tempTrainingDirs.append(tempTrainingDirsForFiltering[i]) #Pozostałe katalogi dodajemy do tymczasowej listy
                #print("Katalog ", tempTrainingDirsForFiltering[i], " jest dobry")
            else:
                print("Katalog ", tempTrainingDirsForFiltering[i], " NIE jest dobry")

        tempTrainingDirs.sort() #Sortujemy katalogi aby ich indexy odpowiadały indexom z trwałej listy użytkowników (uzytkownicy.txt)
        print("Aktualna zawartosc listy tempTrainingDirs to: ", tempTrainingDirs)

        self.trainingDirs = [] #Na wszelki przypadek zerujemy tablicę katalogów
        for n in range(len(tempTrainingDirs)):
            self.trainingDirs.append(os.path.join(self.parentDir, 'test', tempTrainingDirs[n]))

        for x in range(len(self.listaUzytkownikow)):
            """tutaj zmieniamy z \ na / w Macu"""
            tempDirName = "test" + "/s" + str(x)
            print("Dla uzytkownika :", self.listaUzytkownikow[x], " katalog to: ", tempDirName)


            if os.path.exists(tempDirName):
                #sprawić aby indeks [x] zawsze odpowiadał numerowi katalogu s[x]!!!
                print("Katalog ", self.trainingDirs[x], " już istnieje!")
            else:
                print("tempDirName: ", tempDirName)
                print("self.parentDir: ", self.parentDir)
                print("os.path.join: ", os.path.join(self.parentDir, tempDirName))
                for n in range(len(self.trainingDirs)): #Czemu self.trainingDirs ma wiele więcej powtarzających się elementów?!
                    print("index: ", n)
                    print("self.trainingDirs[n]", self.trainingDirs[n])
                self.trainingDirs.append(os.path.join(self.parentDir, tempDirName))
                print(self.trainingDirs[x])
                try:
                    os.makedirs(self.trainingDirs[x])
                except FileExistsError:
                    pass
                print("Stworzono katalog", self.trainingDirs[x])
            #print(self.uzytkownicyKatalogi[2*x])
            #if self.uzytkownicyKatalogi[2*x] != self.trainingDirs[x]:
            #    self.uzytkownicyKatalogi.append(self.zlaczDaneUzytkownika(self.listaUzytkownikow[x], x, self.trainingDirs[x]))

            listaDoPliku(self.uzytkownicyKatalogi, "uzytkownicyKatalogi.txt")

        for y in range(len(self.uzytkownicyKatalogi)):
            print(self.uzytkownicyKatalogi[y])


    def pokazDialogLista(self):
        self.wybierzUzytkownika()
        print("w funkcji pokazDialogLista")
        dlg = DialogListyUzytkownikow(self)
        dlg.exec()


    def wybierzUzytkownika(self):
        listaWyboru = self.listaUzytkownikow
        self.wybranyUzykownik, self.wybranoUzytkownika = QInputDialog.getItem(self, "Wybierz uzytkownika", "Uzytkownik: ", listaWyboru, 0, False)

        if self.wybranoUzytkownika:
            self.etykietaWybranyUzytkownik.setText(self.wybranyUzykownik)
            self.etykietaWybranyUzytkownik.adjustSize()

            for uzytkownikNumer in range(len(self.listaUzytkownikow)):
                if self.listaUzytkownikow[uzytkownikNumer] == self.wybranyUzykownik:
                    self.sciezka = self.trainingDirs[uzytkownikNumer]
                    self.sciezkaDoZapisu.setText(self.sciezka)

    def koniec(self):

        self.close()

    def closeEvent(self, event):

        odp = QMessageBox.question(self, 'Komunikat', "Wyjsc z programu?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if odp == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.image_label.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.display_width, self.display_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)


class DialogListyUzytkownikow(QDialog): #do poprawy, nie działa
    def __init__(self, parent=None):
        super().__init__()

        self.setWindowTitle("Lista uzytkownikow")
        etykieta = QLabel(self)
        etykieta.setText("Lista uzytkownikow")

        listWidget = QListWidget(self)
        for i in range(len(okno.listaUzytkownikow)):
            tempItem = QListWidgetItem(okno.listaUzytkownikow[i])
            listWidget.addItem(tempItem)
        self.show()









# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    #import sys


    app = QApplication(sys.argv)
    okno = Identyfikacja()
    sys.exit(app.exec_())





# See PyCharm help at https://www.jetbrains.com/help/pycharm/
