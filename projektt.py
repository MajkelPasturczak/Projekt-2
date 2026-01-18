import sys
from dataclasses import dataclass
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPainterPath
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QPushButton, QSlider, QStackedWidget
)

# kolory - trochę losowo poukładane
BG = QColor(235, 235, 240)
PIPE_OFF = QColor(90, 90, 90)
PIPE_ON = QColor(0, 130, 240)
TANK_BORDER = QColor(20, 20, 20)
LIQ_COLD = QColor(40, 150, 255, 170)
LIQ_HOT = QColor(255, 100, 20, 170)

def clamp(x, min_val, max_val):
    return max(min_val, min(max_val, x))

# --------------------------------------------------

@dataclass
class Zbiornik:
    nazwa: str
    x: int
    y: int
    szer: int
    wys: int
    max_poj: float
    poziom: float = 0.0
    temp: float = 20.0

    def procent(self):
        if self.max_poj <= 0:
            return 0
        return clamp(self.poziom / self.max_poj, 0, 1)

    def zabierz(self, ile):
        ile = min(self.poziom, max(0, ile))
        self.poziom -= ile
        return ile

    def wlej(self, ile, temp_zrodla):
        wolne = self.max_poj - self.poziom
        ile = min(wolne, max(0, ile))
        if ile > 0 and (self.poziom + ile) > 0:
            nowa_temp = (self.poziom * self.temp + ile * temp_zrodla) / (self.poziom + ile)
            self.temp = nowa_temp
        self.poziom += ile
        return ile


class Pompa:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.wlaczona = False
        self.wydajnosc = 7.2  # l/s
        self.kat = 0

    def przeplyw(self):
        return self.wydajnosc if self.wlaczona else 0.0


class Grzalka:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.wlaczona = False
        self.moc = 0.68   # °C/s - przybliżenie

    def grzej(self, dt):
        return self.moc * dt if self.wlaczona else 0.0


class Rura:
    def __init__(self, punkty):
        self.punkty = punkty
        self.plynie = False


# --------------------------------------------------

class Instalacja:
    def __init__(self):
        self.t1 = Zbiornik("T1 - ZASILANIE",  60,  70, 110, 170, 200, 150)
        self.t2 = Zbiornik("T2 - PROCES",    320, 230, 130, 130, 150,  30)
        self.t3 = Zbiornik("T3 - GAŁĄŹ A",   640,  70, 100, 130, 100,   0)
        self.t4 = Zbiornik("T4 - GAŁĄŹ B",   640, 360, 100, 130, 100,   0)

        self.pompa = Pompa(250, 200)
        self.grzalka = Grzalka(345, 385)

        self.r1 = Rura([(115,240),(115,280),(220,280),(250,200),(320,200),(320,230)])
        self.r2 = Rura([(450,295),(520,295),(580,295)])
        self.r3 = Rura([(580,295),(580,120),(640,120)])
        self.r4 = Rura([(580,295),(580,420),(640,420)])

        self.sp_poz = 90
        self.sp_temp = 55
        self.udzial_A = 0.5

        self.czas = 0.0

    def ustaw_start(self, t1_start, poz_sp, temp_sp, proc_A):
        self.t1.poziom = clamp(t1_start, 0, self.t1.max_poj)
        self.sp_poz   = clamp(poz_sp, 20, self.t2.max_poj)
        self.sp_temp  = clamp(temp_sp, 20, 100)
        self.udzial_A = clamp(proc_A / 100.0, 0.0, 1.0)

    def krok(self, dt):
        self.czas += dt

        # pompa - histereza
        if self.t2.poziom < self.sp_poz - 9:
            self.pompa.wlaczona = True
        if self.t2.poziom > self.sp_poz + 9:
            self.pompa.wlaczona = False

        # grzałka
        if self.t2.temp < self.sp_temp - 1.2:
            self.grzalka.wlaczona = True
        if self.t2.temp > self.sp_temp + 1.2:
            self.grzalka.wlaczona = False

        # temperatura T2
        self.t2.temp += self.grzalka.grzej(dt)
        # stygnie do 20°C
        self.t2.temp += (20 - self.t2.temp) * 0.017 * dt

        # przepływ T1 → T2
        q = self.pompa.przeplyw() * dt
        pob = self.t1.zabierz(q)
        if pob > 0:
            self.t2.wlej(pob, self.t1.temp)
            self.r1.plynie = True
        else:
            self.r1.plynie = False

        # wypływ z T2
        wyp = 0.0
        if self.t2.poziom > 18:
            wyp = 4.8 * dt   # trochę arbitralnie

        zab = self.t2.zabierz(wyp)

        doA = zab * self.udzial_A
        doB = zab * (1 - self.udzial_A)

        self.t3.wlej(doA, self.t2.temp)
        self.t4.wlej(doB, self.t2.temp)

        self.r2.plynie = zab > 0
        self.r3.plynie = doA > 0
        self.r4.plynie = doB > 0

        # odpływ z T4
        self.t4.zabierz(2.3 * dt)


# --------------------------------------------------

class WidokInstalacji(QWidget):
    def __init__(self, inst):
        super().__init__()
        self.inst = inst
        self.setMinimumSize(840, 640)

    def kolor_cieczy(self, t):
        f = clamp((t - 20) / 80, 0, 1)
        r = int(LIQ_COLD.red() + (LIQ_HOT.red() - LIQ_COLD.red()) * f)
        g = int(LIQ_COLD.green() + (LIQ_HOT.green() - LIQ_COLD.green()) * f)
        b = int(LIQ_COLD.blue() + (LIQ_HOT.blue() - LIQ_COLD.blue()) * f)
        return QColor(r, g, b, 185)

    def rysuj_rure(self, painter, rura):
        if not rura.punkty:
            return
        path = QPainterPath()
        path.moveTo(rura.punkty[0][0], rura.punkty[0][1])
        for x,y in rura.punkty[1:]:
            path.lineTo(x, y)

        pen = QPen(PIPE_ON if rura.plynie else PIPE_OFF, 7)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

    def rysuj_zbiornik(self, p, z):
        p.setPen(QPen(TANK_BORDER, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRect(z.x, z.y, int(z.szer), int(z.wys))


        h = z.wys * z.procent()
        p.setPen(Qt.NoPen)
        p.setBrush(self.kolor_cieczy(z.temp))
        p.drawRect(z.x + 4, int(z.y + z.wys - h), int(z.szer - 8), int(h))

        p.setPen(Qt.black)
        p.drawText(z.x, z.y - 5, z.nazwa)
        p.drawText(z.x + 8, z.y + 25, f"{z.poziom:.0f} L")
        p.drawText(z.x + 8, z.y + 45, f"{z.temp:.1f} °C")

    def rysuj_pompe(self, p):
        pom = self.inst.pompa
        p.setBrush(QColor(210,210,210))
        p.drawEllipse(pom.x-16, pom.y-16, 32, 32)

        if pom.wlaczona:
            pom.kat = (pom.kat + 22) % 360

        p.save()
        p.translate(pom.x, pom.y)
        p.rotate(pom.kat)
        p.setPen(QPen(Qt.black, 3))
        p.drawLine(-11,0,11,0)
        p.drawLine(0,-11,0,11)
        p.restore()

        col = Qt.darkGreen if pom.wlaczona else Qt.red
        p.setPen(col)
        p.drawText(pom.x-25, pom.y+35, "POMPA " + ("ON" if pom.wlaczona else "OFF"))

    def rysuj_grzalke(self, p):
        g = self.inst.grzalka
        col = Qt.red if g.wlaczona else Qt.gray
        p.setPen(QPen(col, 4))

        x, y = g.x, g.y
        for i in range(4):
            p.drawLine(x, y + i*10, x+14, y + i*10 - 6)
            p.drawLine(x+14, y + i*10 - 6, x, y + i*10 + 4)

        p.setPen(Qt.black)
        p.drawText(x+22, y+18, "GRZ")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), BG)

        for r in [self.inst.r1, self.inst.r2, self.inst.r3, self.inst.r4]:
            self.rysuj_rure(painter, r)

        for zb in [self.inst.t1, self.inst.t2, self.inst.t3, self.inst.t4]:
            self.rysuj_zbiornik(painter, zb)

        self.rysuj_pompe(painter)
        self.rysuj_grzalke(painter)

        painter.setPen(QColor(50,50,50))
        txt = f"czas = {self.inst.czas:.1f} s   |  SP: {self.inst.sp_poz} L   {self.inst.sp_temp} °C   |  A = {self.inst.udzial_A*100:.0f}%"
        painter.drawText(20, self.height() - 15, txt)


class WidokAlarmow(QWidget):
    def __init__(self, inst):
        super().__init__()
        self.inst = inst
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("   ALARMY   "))
        self.tekst = QLabel("Sprawdzanie...")
        self.tekst.setStyleSheet("font-size: 15px; padding: 10px;")
        lay.addWidget(self.tekst)
        lay.addStretch()

    def odswiez(self):
        alarmy = []
        for z in [self.inst.t1, self.inst.t2, self.inst.t3, self.inst.t4]:
            if z.poziom < 10:
                alarmy.append(f"{z.nazwa} → NISKI POZIOM ({z.poziom:.0f} L)")
            if z.poziom > z.max_poj * 0.93:
                alarmy.append(f"{z.nazwa} → ZA DUŻO ({z.poziom:.0f} L)")

        if self.inst.t2.temp > self.inst.sp_temp + 8:
            alarmy.append(f"T2 → ZA GORĄCO ({self.inst.t2.temp:.1f} °C)")

        if not alarmy:
            self.tekst.setText("Wszystko OK ✅")
        else:
            self.tekst.setText("\n".join(alarmy))


# --------------------------------------------------

class Okno(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projekt - Instalacja")
        self.resize(1050, 720)

        self.inst = Instalacja()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # lewa strona - widoki
        self.stos = QStackedWidget()
        self.widok_glowny = WidokInstalacji(self.inst)
        self.widok_alarm = WidokAlarmow(self.inst)
        self.stos.addWidget(self.widok_glowny)
        self.stos.addWidget(self.widok_alarm)
        main_layout.addWidget(self.stos, 4)

        # prawa strona - sterowanie
        panel = QGroupBox("Ustawienia startowe")
        vbox = QVBoxLayout(panel)

        self.sl_t1 = QSlider(Qt.Horizontal)
        self.sl_t1.setRange(0, 200)
        self.sl_t1.setValue(150)
        self.lbl_t1 = QLabel(f"T1 start: {self.sl_t1.value()} L")

        self.sl_poz = QSlider(Qt.Horizontal)
        self.sl_poz.setRange(30, 150)
        self.sl_poz.setValue(90)
        self.lbl_poz = QLabel(f"SP poziom T2: {self.sl_poz.value()} L")

        self.sl_temp = QSlider(Qt.Horizontal)
        self.sl_temp.setRange(25, 90)
        self.sl_temp.setValue(55)
        self.lbl_temp = QLabel(f"SP temp T2: {self.sl_temp.value()} °C")

        self.sl_udzial = QSlider(Qt.Horizontal)
        self.sl_udzial.setRange(0, 100)
        self.sl_udzial.setValue(50)
        self.lbl_udzial = QLabel(f"Do gałęzi A: {self.sl_udzial.value()} %")

        for s in (self.sl_t1, self.sl_poz, self.sl_temp, self.sl_udzial):
            s.valueChanged.connect(self.odswiez_etykiety)

        vbox.addWidget(self.lbl_t1);   vbox.addWidget(self.sl_t1)
        vbox.addWidget(self.lbl_poz);  vbox.addWidget(self.sl_poz)
        vbox.addWidget(self.lbl_temp); vbox.addWidget(self.sl_temp)
        vbox.addWidget(self.lbl_udzial); vbox.addWidget(self.sl_udzial)

        btn = QPushButton("Zastosuj i zresetuj")
        btn.clicked.connect(self.resetuj)
        vbox.addWidget(btn)

        vbox.addSpacing(20)
        vbox.addWidget(QLabel("Widok:"))
        b1 = QPushButton("Instalacja")
        b2 = QPushButton("Alarmy")
        b1.clicked.connect(lambda: self.stos.setCurrentIndex(0))
        b2.clicked.connect(lambda: self.stos.setCurrentIndex(1))
        vbox.addWidget(b1)
        vbox.addWidget(b2)

        vbox.addStretch()
        main_layout.addWidget(panel, 1)

        self.odswiez_etykiety()

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    def odswiez_etykiety(self):
        self.lbl_t1.setText(f"T1 start: {self.sl_t1.value()} L")
        self.lbl_poz.setText(f"SP poziom T2: {self.sl_poz.value()} L")
        self.lbl_temp.setText(f"SP temp T2: {self.sl_temp.value()} °C")
        self.lbl_udzial.setText(f"Do gałęzi A: {self.sl_udzial.value()} %")

    def resetuj(self):
        self.inst = Instalacja()
        self.inst.ustaw_start(
            self.sl_t1.value(),
            self.sl_poz.value(),
            self.sl_temp.value(),
            self.sl_udzial.value()
        )
        self.widok_glowny.inst = self.inst
        self.widok_alarm.inst = self.inst

    def tick(self):
        dt = 0.050
        self.inst.krok(dt)

        wid = self.stos.currentWidget()
        if hasattr(wid, "odswiez"):
            wid.odswiez()
        else:
            wid.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Okno()
    win.show()
    sys.exit(app.exec_())
