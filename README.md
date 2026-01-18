## 1. Cel projektu

Celem projektu było rozszerzenie umiejętności programowania obiektowego
o stworzenie aplikacji wizualizującej uproszczony proces przemysłowy,
działającej na zasadzie systemu typu SCADA.

Aplikacja umożliwia obserwację poziomu cieczy, temperatury oraz przepływu
w instalacji technologicznej, bez ręcznego sterowania urządzeniami
w trakcie pracy procesu.

---

## 2. Zakres funkcjonalny

Projekt spełnia następujące wymagania:

- wizualizacja:
  - poziomu cieczy,
  - temperatury cieczy,
  - przepływu w rurociągach,
- ekran główny zawiera:
  - **4 zbiorniki**,
  - **rurociągi z zakrętami 90°**,
  - **rozgałęzienie przepływu**,
  - elementy dynamiczne: **pompa** i **grzałka**,
- proces przebiega **automatycznie**,
- użytkownik ustawia jedynie **parametry początkowe**,
- dostępne są **dwa ekrany**:
  - widok instalacji,
  - widok alarmów,
- zastosowano **architekturę obiektową**,
- wykorzystano bibliotekę graficzną **PyQt6**.

---

## 3. Opis procesu technologicznego

1. Zbiornik **T1** pełni rolę zbiornika zasilającego.
2. Pompa transportuje ciecz z T1 do zbiornika procesowego **T2**.
3. W zbiorniku **T2** realizowane jest:
   - utrzymywanie zadanego poziomu cieczy,
   - podgrzewanie cieczy do zadanej temperatury.
4. Ze zbiornika **T2** ciecz kierowana jest do węzła rozgałęziającego,
   gdzie strumień dzielony jest na dwie gałęzie:
   - **T3 (gałąź A)**,
   - **T4 (gałąź B)**.
5. Ze zbiornika **T4** realizowany jest odpływ (symulacja zużycia).

---

## 4. Automatyka i sterowanie

Sterowanie procesem odbywa się automatycznie:

- **Pompa**
  - włącza się, gdy poziom w T2 spadnie poniżej wartości zadanej,
  - wyłącza się po przekroczeniu górnej granicy (histereza).
- **Grzałka**
  - utrzymuje temperaturę cieczy w T2 na poziomie zadanym,
  - sterowanie typu ON/OFF z histerezą.

Użytkownik nie ma możliwości bezpośredniego sterowania pompą
ani grzałką podczas pracy procesu.

---

## 5. Struktura obiektowa projektu

Projekt został wykonany zgodnie z zasadami programowania obiektowego.

### Główne klasy:

- `Zbiornik` – reprezentuje zbiornik procesowy (poziom, temperatura),
- `Pompa` – element wykonawczy transportujący ciecz,
- `Grzalka` – element podgrzewający ciecz,
- `Rura` – wizualizacja połączeń technologicznych,
- `Instalacja` – logika procesu oraz automatyki,
- `EkranInstalacji` – wizualizacja instalacji technologicznej,
- `EkranAlarmow` – prezentacja stanów alarmowych,
- `OknoGlowne` – główne okno aplikacji.

---

## 6. Alarmy

Aplikacja sygnalizuje następujące stany alarmowe:

- niski poziom cieczy w zbiorniku,
- wysoki poziom cieczy,
- przekroczenie zadanej temperatury w zbiorniku T2.

Alarmy prezentowane są na osobnym ekranie.
