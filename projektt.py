import sys
from dataclasses import dataclass
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPainterPath
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QPushButton, QSlider, QStackedWidget
)

# ==========================================
# KONFIGURACJA
# ==========================================
ODSWIEZANIE_MS = 50   # 20 FPS
TLO = QColor(245, 245, 245)
RURA_OFF = QColor(120, 120, 120)
RURA_ON = QColor(0, 120, 255)
OBRYS_ZBIORNIKA = QColor(40, 40, 40)
CIECZ_ZIMNA = QColor(0, 160, 255, 200)
CIECZ_GORACA = QColor(255, 80, 0, 200)


def ogranicz(x, a, b):
    return max(a, min(b, x))


# ==========================================
# ELEMENTY PROCESU (OOP)
# ==========================================

@dataclass
class Zbiornik:
    """Zbiornik z cieczą (poziom + temperatura)."""
    nazwa: str
    x: int
    y: int
    szer: int
    wys: int
    pojemnosc_maks: float
    poziom: float
    temperatura: float = 20.0

    def procent_wypelnienia(self) -> float:
        if self.pojemnosc_maks <= 0:
            return 0.0
        return ogranicz(self.poziom / self.pojemnosc_maks, 0.0, 1.0)

    def pobierz(self, ilosc: float) -> float:
        """Zabiera ciecz ze zbiornika."""
        a = min(self.poziom, max(0.0, ilosc))
        self.poziom -= a
        return a

    def dodaj(self, ilosc: float, temp_we: float) -> float:
        """Dodaje ciecz do zbiornika (z mieszaniem temperatury)."""
        wolne = self.pojemnosc_maks - self.poziom
        a = min(wolne, max(0.0, ilosc))
        if self.poziom + a > 0:
            self.temperatura = (self.poziom * self.temperatura + a * temp_we) / (self.poziom + a)
        self.poziom += a
        return a


class Pompa:
    """Pompa ON/OFF. Animacja wirnika jest tylko wizualna."""
    def __init__(self, x: int, y: int, wydajnosc_lps: float):
        self.x, self.y = x, y
        self.wydajnosc_lps = wydajnosc_lps
        self.wlaczona = False
        self.kat = 0  # do animacji

    def przeplyw(self) -> float:
        return self.wydajnosc_lps if self.wlaczona else 0.0


class Grzalka:
    """Grzałka ON/OFF (podnosi temperaturę zbiornika)."""
    def __init__(self, x: int, y: int, moc_c_na_s: float):
        self.x, self.y = x, y
        self.moc_c_na_s = moc_c_na_s
        self.wlaczona = False

    def grzanie(self, dt: float) -> float:
        return self.moc_c_na_s * dt if self.wlaczona else 0.0


class Rura:
    """Rura jako lista punktów: rysuje zakręty 90° i rozgałęzienia."""
    def __init__(self, punkty: list[tuple[int, int]]):
        self.punkty = punkty
        self.plynie = False


# ==========================================
# INSTALACJA (LOGIKA PROCESU + AUTOMATYKA)
# ==========================================

class Instalacja:
    """
    Proces działa automatycznie.
    Użytkownik podaje tylko parametry startowe, potem symulacja sama steruje pompą i grzałką.
    """
    def __init__(self):
        # 4 zbiorniki
        self.t1 = Zbiornik("T1 Zasilanie", 60, 70, 110, 170, 200, 160, 20)
        self.t2 = Zbiornik("T2 Proces",    320, 230, 130, 130, 150,  30, 25)
        self.t3 = Zbiornik("T3 Gałąź A",   640, 70,  100, 130, 100,   0, 20)
        self.t4 = Zbiornik("T4 Gałąź B",   640, 360, 100, 130, 100,   0, 20)

        # elementy dynamiczne
        self.pompa = Pompa(250, 200, wydajnosc_lps=7.0)     # T1 -> T2
        self.grzalka = Grzalka(345, 385, moc_c_na_s=0.65)   # grzanie T2

        # rury (90° + rozgałęzienie)
        self.rura_1 = Rura([(115, 240), (115, 280), (220, 280), (250, 200), (320, 200), (320, 230)])  # T1 -> T2
        self.rura_2 = Rura([(450, 295), (520, 295), (580, 295)])  # T2 -> węzeł
        self.rura_3 = Rura([(580, 295), (580, 120), (640, 120)])  # węzeł -> T3
        self.rura_4 = Rura([(580, 295), (580, 420), (640, 420)])  # węzeł -> T4

        # parametry zadane (ustawiane na starcie)
        self.sp_poziom_t2 = 90.0
        self.sp_temp_t2 = 55.0
        self.udzial_A = 0.50  # 0..1 (reszta idzie do B)

        self.czas_s = 0.0

    def ustaw_parametry_startowe(self, poziom_t1: float, sp_poziom_t2: float, sp_temp_t2: float, udzial_A_proc: float):
        self.t1.poziom = ogranicz(poziom_t1, 0, self.t1.pojemnosc_maks)
        self.sp_poziom_t2 = ogranicz(sp_poziom_t2, 0, self.t2.pojemnosc_maks)
        self.sp_temp_t2 = ogranicz(sp_temp_t2, 20, 100)
        self.udzial_A = ogranicz(udzial_A_proc / 100.0, 0.0, 1.0)

    def krok_symulacji(self, dt: float):
        """Jeden krok symulacji: automatyka + przepływy + temperatura."""
        self.czas_s += dt

        # --- AUTOMATYKA (ON/OFF z histerezą) ---
        # Pompa: utrzymuj poziom w T2 przy SP
        if self.t2.poziom < self.sp_poziom_t2 - 8:
            self.pompa.wlaczona = True
        elif self.t2.poziom > self.sp_poziom_t2 + 8:
            self.pompa.wlaczona = False

        # Grzałka: utrzymuj temperaturę w T2 przy SP
        if self.t2.temperatura < self.sp_temp_t2 - 1:
            self.grzalka.wlaczona = True
        elif self.t2.temperatura > self.sp_temp_t2 + 1:
            self.grzalka.wlaczona = False

        # --- TEMPERATURA T2 ---
        self.t2.temperatura += self.grzalka.grzanie(dt)
        # proste stygnięcie do 20°C
        self.t2.temperatura += (20 - self.t2.temperatura) * 0.02 * dt

        # --- PRZEPŁYW T1 -> T2 (pompa) ---
        q = self.pompa.przeplyw() * dt
        pobrane = self.t1.pobierz(q)
        if pobrane > 0:
            self.t2.dodaj(pobrane, self.t1.temperatura)
            self.rura_1.plynie = True
        else:
            self.rura_1.plynie = False

        # --- PRZEPŁYW T2 -> węzeł -> T3/T4 (rozgałęzienie) ---
        # automatyczny wypływ zależny od ilości w T2 (żeby "żyło")
        wyplyw = 0.0
        if self.t2.poziom > 20:
            wyplyw = min(self.t2.poziom, (4.5 + 2.0 * self.udzial_A) * dt)

        zabrane = self.t2.pobierz(wyplyw)
        a = zabrane * self.udzial_A
        b = zabrane * (1 - self.udzial_A)

        dodA = self.t3.dodaj(a, self.t2.temperatura)
        dodB = self.t4.dodaj(b, self.t2.temperatura)

        self.rura_2.plynie = (zabrane > 0)
        self.rura_3.plynie = (dodA > 0)
        self.rura_4.plynie = (dodB > 0)

        # --- ODPŁYW z T4 (symulacja zużycia) ---
        self.t4.pobierz(min(self.t4.poziom, 2.5 * dt))


# ==========================================
# EKRANY (WIDOKI)
# ==========================================

class Ekran(QWidget):
    def odswiez(self):
        pass


class EkranInstalacji(Ekran):
    """Rysuje instalację: zbiorniki, rury, pompa, grzałka."""
    def __init__(self, instalacja: Instalacja):
        super().__init__()
        self.instalacja = instalacja
        self.setMinimumSize(820, 620)

    def _kolor_cieczy(self, temp: float) -> QColor:
        f = ogranicz((temp - 20) / 80.0, 0.0, 1.0)
        r = int(CIECZ_ZIMNA.red() + (CIECZ_GORACA.red() - CIECZ_ZIMNA.red()) * f)
        g = int(CIECZ_ZIMNA.green() + (CIECZ_GORACA.green() - CIECZ_ZIMNA.green()) * f)
        b = int(CIECZ_ZIMNA.blue() + (CIECZ_GORACA.blue() - CIECZ_ZIMNA.blue()) * f)
        return QColor(r, g, b, 200)

    def _rysuj_rure(self, p: QPainter, rura: Rura):
        pts = rura.punkty
        if not pts:
            return
        sciezka = QPainterPath()
        sciezka.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            sciezka.lineTo(x, y)

        pen = QPen(RURA_ON if rura.plynie else RURA_OFF, 7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(sciezka)

    def _rysuj_zbiornik(self, p: QPainter, z: Zbiornik):
        p.setPen(QPen(OBRYS_ZBIORNIKA, 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(z.x, z.y, z.szer, z.wys)
        p.drawRect(rect)

        # ciecz
        fill_h = z.wys * z.procent_wypelnienia()
        ciecz = QRectF(z.x + 2, z.y + z.wys - fill_h - 1, z.szer - 4, fill_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._kolor_cieczy(z.temperatura))
        p.drawRect(ciecz)

        # opisy
        p.setPen(Qt.GlobalColor.black)
        p.drawText(int(z.x), int(z.y - 10), z.nazwa)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{z.poziom:.0f} L\n{z.temperatura:.1f} °C")

    def _rysuj_pompe(self, p: QPainter):
        pompa = self.instalacja.pompa
        p.setPen(QPen(Qt.GlobalColor.black, 2))
        p.setBrush(QColor(220, 220, 220))
        p.drawEllipse(pompa.x - 16, pompa.y - 16, 32, 32)

        if pompa.wlaczona:
            pompa.kat = (pompa.kat + 20) % 360

        p.save()
        p.translate(pompa.x, pompa.y)
        p.rotate(pompa.kat)
        p.setPen(QPen(Qt.GlobalColor.black, 2))
        p.drawLine(-10, 0, 10, 0)
        p.drawLine(0, -10, 0, 10)
        p.restore()

        p.setPen(Qt.GlobalColor.darkGreen if pompa.wlaczona else Qt.GlobalColor.red)
        p.drawText(pompa.x - 18, pompa.y + 34, "ON" if pompa.wlaczona else "OFF")

    def _rysuj_grzalke(self, p: QPainter):
        g = self.instalacja.grzalka
        kolor = Qt.GlobalColor.red if g.wlaczona else Qt.GlobalColor.gray
        p.setPen(QPen(kolor, 3))

        sciezka = QPainterPath()
        sciezka.moveTo(g.x, g.y)
        for i in range(4):
            sciezka.lineTo(g.x + 10, g.y + i * 10 - 5)
            sciezka.lineTo(g.x, g.y + i * 10)
        p.drawPath(sciezka)

        p.setPen(Qt.GlobalColor.black)
        p.drawText(g.x + 18, g.y + 14, "GRZ")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), TLO)

        # rury (pod spodem)
        self._rysuj_rure(p, self.instalacja.rura_1)
        self._rysuj_rure(p, self.instalacja.rura_2)
        self._rysuj_rure(p, self.instalacja.rura_3)
        self._rysuj_rure(p, self.instalacja.rura_4)

        # zbiorniki
        self._rysuj_zbiornik(p, self.instalacja.t1)
        self._rysuj_zbiornik(p, self.instalacja.t2)
        self._rysuj_zbiornik(p, self.instalacja.t3)
        self._rysuj_zbiornik(p, self.instalacja.t4)

        # elementy dynamiczne
        self._rysuj_pompe(p)
        self._rysuj_grzalke(p)

        # pasek informacji
        p.setPen(QColor(60, 60, 60))
        p.drawText(
            20, self.height() - 20,
            f"t={self.instalacja.czas_s:0.1f}s | SP(T2)={self.instalacja.sp_poziom_t2:.0f}L / {self.instalacja.sp_temp_t2:.0f}°C | udzial_A={self.instalacja.udzial_A:.2f}"
        )

    def odswiez(self):
        self.update()


class EkranAlarmow(Ekran):
    """Drugi ekran: proste alarmy z progów."""
    def __init__(self, instalacja: Instalacja):
        super().__init__()
        self.instalacja = instalacja
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Alarmy (progi proste):"))
        self.lbl = QLabel()
        self.lbl.setStyleSheet("font-size: 14px;")
        lay.addWidget(self.lbl)
        lay.addStretch()

    def odswiez(self):
        i = self.instalacja
        alarmy = []

        for z in (i.t1, i.t2, i.t3, i.t4):
            if z.poziom < 10:
                alarmy.append(f"{z.nazwa}: NISKI POZIOM ({z.poziom:.0f} L)")
            if z.poziom > 0.95 * z.pojemnosc_maks:
                alarmy.append(f"{z.nazwa}: WYSOKI POZIOM ({z.poziom:.0f} L)")

        if i.t2.temperatura > i.sp_temp_t2 + 10:
            alarmy.append(f"{i.t2.nazwa}: WYSOKA TEMP ({i.t2.temperatura:.1f} °C)")

        self.lbl.setText("Brak alarmów ✅" if not alarmy else "<br>".join(alarmy))


# ==========================================
# OKNO GŁÓWNE
# ==========================================

class OknoGlowne(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projekt Informatyka - 2")
        self.resize(1000, 700)

        self.instalacja = Instalacja()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Ekrany po lewej
        self.stos = QStackedWidget()
        self.ekran_inst = EkranInstalacji(self.instalacja)
        self.ekran_al = EkranAlarmow(self.instalacja)
        self.stos.addWidget(self.ekran_inst)
        self.stos.addWidget(self.ekran_al)
        root.addWidget(self.stos, 3)

        # Panel po prawej (tylko parametry startowe)
        panel = QGroupBox("Panel (parametry startowe)")
        pv = QVBoxLayout(panel)

        self.lbl_t1 = QLabel()
        self.s_t1 = QSlider(Qt.Orientation.Horizontal)
        self.s_t1.setRange(0, int(self.instalacja.t1.pojemnosc_maks))
        self.s_t1.setValue(int(self.instalacja.t1.poziom))

        self.lbl_sp_poz = QLabel()
        self.s_sp_poz = QSlider(Qt.Orientation.Horizontal)
        self.s_sp_poz.setRange(0, int(self.instalacja.t2.pojemnosc_maks))
        self.s_sp_poz.setValue(int(self.instalacja.sp_poziom_t2))

        self.lbl_sp_temp = QLabel()
        self.s_sp_temp = QSlider(Qt.Orientation.Horizontal)
        self.s_sp_temp.setRange(20, 100)
        self.s_sp_temp.setValue(int(self.instalacja.sp_temp_t2))

        self.lbl_udzial = QLabel()
        self.s_udzial = QSlider(Qt.Orientation.Horizontal)
        self.s_udzial.setRange(0, 100)
        self.s_udzial.setValue(int(self.instalacja.udzial_A * 100))

        for s in (self.s_t1, self.s_sp_poz, self.s_sp_temp, self.s_udzial):
            s.valueChanged.connect(self._odswiez_opisy)

        pv.addWidget(self.lbl_t1); pv.addWidget(self.s_t1)
        pv.addWidget(self.lbl_sp_poz); pv.addWidget(self.s_sp_poz)
        pv.addWidget(self.lbl_sp_temp); pv.addWidget(self.s_sp_temp)
        pv.addWidget(self.lbl_udzial); pv.addWidget(self.s_udzial)

        self.btn_reset = QPushButton("Zastosuj + RESET instalacji")
        self.btn_reset.clicked.connect(self.zastosuj_i_reset)
        pv.addWidget(self.btn_reset)

        pv.addWidget(QLabel("Widoki:"))
        btn1 = QPushButton("Instalacja")
        btn2 = QPushButton("Alarmy")
        btn1.clicked.connect(lambda: self.stos.setCurrentIndex(0))
        btn2.clicked.connect(lambda: self.stos.setCurrentIndex(1))
        pv.addWidget(btn1)
        pv.addWidget(btn2)

        pv.addStretch()
        root.addWidget(panel, 1)

        self._odswiez_opisy()

        # Timer symulacji
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(ODSWIEZANIE_MS)

    def _odswiez_opisy(self):
        self.lbl_t1.setText(f"Start poziom T1 [L]: {self.s_t1.value()}")
        self.lbl_sp_poz.setText(f"SP poziom T2 [L]: {self.s_sp_poz.value()}")
        self.lbl_sp_temp.setText(f"SP temperatura T2 [°C]: {self.s_sp_temp.value()}")
        self.lbl_udzial.setText(f"Podział A→T3 [%]: {self.s_udzial.value()}")

    def zastosuj_i_reset(self):
        # najprostszy reset: tworzymy nową instalację i podmieniamy w ekranach
        self.instalacja = Instalacja()
        self.instalacja.ustaw_parametry_startowe(
            poziom_t1=float(self.s_t1.value()),
            sp_poziom_t2=float(self.s_sp_poz.value()),
            sp_temp_t2=float(self.s_sp_temp.value()),
            udzial_A_proc=float(self.s_udzial.value()),
        )
        self.ekran_inst.instalacja = self.instalacja
        self.ekran_al.instalacja = self.instalacja

    def tick(self):
        dt = ODSWIEZANIE_MS / 1000.0
        self.instalacja.krok_symulacji(dt)

        w = self.stos.currentWidget()
        if hasattr(w, "odswiez"):
            w.odswiez()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    okno = OknoGlowne()
    okno.show()
    sys.exit(app.exec())
