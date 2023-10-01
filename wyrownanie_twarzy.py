import cv2
import dlib
import numpy as np


# Load face detector and shape predictor models
face_detector = dlib.get_frontal_face_detector()
shape_predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")


def wyrownaj_twarz(zdj_wejsciowe):
    skala_szarosci = cv2.cvtColor(zdj_wejsciowe, cv2.COLOR_BGR2GRAY)        # konwersja obrazu na skalę szarości
    twarze = face_detector(skala_szarosci)                                  # detekcja twarzy w obrazie

    for twarz in twarze:                                                    # dla każdej znalezionej twarzy
        pkty_charakterystyczne = shape_predictor(skala_szarosci, twarz)     # znajdowanie charakterystycznych pktów twarzy
        pkty_charakterystyczne = np.array([[p.x, p.y] for p in pkty_charakterystyczne.parts()]) # konwersja pktów charakterystycznych twarzy na numpy array
        com = np.mean(pkty_charakterystyczne, axis = 0)                     # center of mass dla pktów charakterystycznych

        dy = pkty_charakterystyczne[33, 1] - pkty_charakterystyczne[8, 1]   # obliczenie kąta pomiędzy oczami a poziomem
        dx = pkty_charakterystyczne[33, 0] - pkty_charakterystyczne[8, 0]
        kat = np.degrees(np.arctan2(dy, dx)) + 90.0

        M = cv2.getRotationMatrix2D(tuple(com), kat, 1)                     # stworzenie macierzy obrotu

        wyrownany = cv2.warpAffine(zdj_wejsciowe, M, (zdj_wejsciowe.shape[1], zdj_wejsciowe.shape[0]), flags=cv2.INTER_CUBIC)   # wyrównanie obrazu

        return wyrownany
