# Klarvido - logika obliczen i powiazania danych

> Status: dokument roboczy przygotowany na podstawie `Finalny mockup.html`.
> Opisuje obecne zachowanie mockupu, a nie jeszcze docelowa specyfikacje ksiegowa.

## Jak czytac ten dokument

- **Liczone** - wartosc wynika z danych i wzoru w mockupie.
- **Demo** - wartosc jest wpisana na stale i nie pochodzi z integracji.
- **Zalozenie** - uproszczenie przyjete na potrzeby symulacji.
- **Do decyzji** - miejsce, w ktorym przed wdrozeniem produkcyjnym trzeba uzgodnic jedna definicje.

Kwoty zapisane w podstawowych tablicach mockupu sa podane w tysiacach zlotych. Na potrzeby tabel i faktur sa mnozone przez 1 000.

## Ogolna mapa powiazan

```text
Dane miesieczne firmy
  -> KPI na pulpicie
  -> wykres przychodow, kosztow, podatku i dochodu
  -> analiza firmy na tle rynku
  -> scenariusze finansowe

Trendy klientow
  -> faktury sprzedazowe
  -> obroty klientow
  -> udzial klienta w przychodach
  -> koncentracja przychodow i ryzyko utraty klienta

Trendy dostawcow
  -> faktury zakupowe
  -> koszty dostawcow i kategorii
  -> udzial dostawcy w kosztach
  -> wykrywanie wzrostow, nowych kosztow i anomalii

Faktury sprzedazowe i zakupowe
  -> lista faktur i filtry
  -> wykres trendu w analizie
  -> liczba faktur klienta lub dostawcy
  -> eksport CSV
```

## Dane bazowe mockupu

Mockup zawiera szesc miesiecy danych: styczen-czerwiec.

| Miesiac | Przychod | Koszty | Podatek | Dochod po podatku |
| --- | ---: | ---: | ---: | ---: |
| Styczen | 195 000 zl | 92 000 zl | 20 000 zl | 83 000 zl |
| Luty | 205 000 zl | 96 000 zl | 21 000 zl | 88 000 zl |
| Marzec | 204 000 zl | 94 000 zl | 21 000 zl | 89 000 zl |
| Kwiecien | 207 000 zl | 101 000 zl | 20 000 zl | 86 000 zl |
| Maj | 203 000 zl | 108 000 zl | 18 000 zl | 77 000 zl |
| Czerwiec | 202 000 zl | 123 500 zl | 17 000 zl | 61 500 zl |
| **Razem** | **1 216 000 zl** | **614 500 zl** | **117 000 zl** | **484 500 zl** |

Podstawowa zaleznosc jest nastepujaca:

```text
dochod po podatku = przychod - koszty - podatek
```

Przyklad dla czerwca:

```text
202 000 - 123 500 - 17 000 = 61 500 zl
```

Obecnie tablica dochodu jest wpisana osobno, chociaz jej wartosci wynikaja z powyzszego wzoru. W wersji produkcyjnej dochod powinien byc wyliczany, aby nie mogl rozjechac sie z pozostala trojka danych.

## Wybor okresu

Wybrany okres steruje wiekszoscia KPI, rankingow i wykresow.

| Wybor | Okres biezacy | Okres porownawczy |
| --- | --- | --- |
| Biezacy miesiac | ostatni dostepny miesiac | miesiac poprzedni |
| Poprzedni miesiac | miesiac przed ostatnim | jeszcze jeden miesiac wstecz |
| Ostatni kwartal | ostatnie 3 miesiace | poprzednie 3 miesiace, jesli istnieja |
| Wlasny miesiac | wskazany miesiac | miesiac bezposrednio go poprzedzajacy |
| Polrocze / rok | wszystkie dostepne miesiace | brak porownania przy obecnych 6 miesiacach danych |

Dla okresow wielomiesiecznych wartosci pieniezne sa sumowane. Procentowa zmiana jest liczona tak:

```text
zmiana procentowa = (wartosc biezaca - wartosc poprzednia)
                     / wartosc bezwzgledna poprzednia * 100%
```

Gdy nie istnieje okres porownawczy albo poprzednia wartosc wynosi zero, zmiana nie jest liczona.

## Glowne KPI

### Przychod

**Liczone:** suma przychodow w wybranym okresie.

Wzrost przychodu jest interpretowany jako zjawisko korzystne, a spadek jako niekorzystne.

### Koszty

**Liczone:** suma kosztow w wybranym okresie.

Wzrost kosztow jest interpretowany jako zjawisko niekorzystne, a spadek jako korzystne. Jest to odwrotna interpretacja niz dla przychodu i dochodu.

### Podatek

**Liczone na pulpicie:** suma wartosci z tablicy podatku dla wybranego okresu.

Spadek podatku jest oznaczany jako korzystny, a wzrost jako niekorzystny. To jedynie prezentacja zmiany obciazenia, a nie ocena zgodnosci podatkowej.

### Dochod po podatku

**Liczone:**

```text
dochod = przychod - koszty - podatek
```

### Marza netto na pulpicie

**Liczone:**

```text
marza netto = dochod po podatku / przychod * 100%
```

Dla czerwca:

```text
61 500 / 202 000 * 100% = 30,4%
```

Zmiana marzy jest pokazywana w punktach procentowych, a nie jako procentowa zmiana samej marzy:

```text
zmiana marzy = marza biezaca - marza poprzednia
```

## Wykresy

### Wykres na pulpicie

Wykres pokazuje cztery serie:

- przychod,
- koszty,
- szacowany podatek,
- szacowany dochod po podatku.

Wysokosc slupkow jest liczona wzgledem najwyzszej wartosci widocznego okresu. Oznacza to, ze skala moze zmienic sie po zmianie zakresu dat. Pod wykresem znajduje sie tabela z dokladnymi kwotami i marza.

Male wykresy przy KPI uzywaja danych z biezacego okresu, a jesli istnieje porownanie, rowniez z okresu poprzedniego. Przy zaledwie dwoch punktach mockup dodaje posrednie punkty, aby linia wygladala naturalniej. Te dodatkowe punkty sa tylko efektem wizualnym i nie sa nowymi danymi finansowymi.

### Trend w analizie

Ten wykres jest budowany z wygenerowanych faktur, a nie bezposrednio z glownych tablic miesiecznych.

- Faktury sprzedazowe zwiekszaja linie przychodu.
- Faktury zakupowe zwiekszaja linie kosztow.
- Dla jednego miesiaca faktury sa grupowane w okolo cztery tygodniowe przedzialy.
- Dla dluzszego zakresu kazdy miesiac jest dzielony na dwie polowy.
- Gorna granica osi jest zaokraglana w gore do najblizszych 50 000 zl.

Linie sa wygladzane. Wypelnienie pod linia przychodu jest elementem prezentacji, bez dodatkowego znaczenia rachunkowego.

### Trend klienta lub dostawcy

Profil klienta i dostawcy korzysta z ich miesiecznej tablicy `trend`. Gorna granica osi jest zaokraglana w gore do najblizszych 10 000 zl.

## Faktury

Faktury w mockupie sa generowane deterministycznie. Te same dane wejsciowe zawsze tworza taki sam zestaw faktur.

### Faktury sprzedazowe

Dla kazdego klienta i miesiaca:

1. Miesieczny obrot klienta jest pobierany z jego trendu i mnozony przez 1 000.
2. Kwota jest dzielona na 1-3 faktury.
3. Podzial zachowuje laczna miesieczna kwote netto.
4. VAT wynosi 23% kwoty netto.
5. Kwota brutto to netto plus VAT.
6. Kategoria to zawsze `Sprzedaz wyrobow gotowych`.

### Faktury zakupowe

Dla kazdego dostawcy i miesiaca stosowana jest taka sama zasada podzialu jego kosztu na 1-3 faktury. Kategoria wynika z przypisania dostawcy do rodzaju kosztu.

Pierwsza czerwcowa faktura DrewnoPol ma celowo pusta kategorie. Sluzy do pokazania przypadku `Bez kategorii` i mozliwosci recznej korekty.

### Kwoty faktury

```text
VAT = netto * 23%
brutto = netto + VAT
```

VAT i brutto sa zaokraglane do dwoch miejsc po przecinku.

### Lista faktur

Liste mozna filtrowac wedlug:

- typu sprzedaz/zakup,
- kategorii,
- miesiaca,
- numeru faktury lub nazwy kontrahenta.

Sortowanie po dacie uzywa numerycznej postaci `RRRRMMDD`. Eksport CSV obejmuje aktualnie przefiltrowane i posortowane wiersze, a nie caly nieprzefiltrowany zbior.

## Klienci

Mockup ma 12 klientow z szescioma miesiecznymi wartosciami trendu. Suma czerwcowych trendow klientow wynosi 202 000 zl i odpowiada czerwcowemu przychodowi firmy.

### Obrot klienta

```text
obrot klienta = suma trendu klienta w wybranym okresie * 1 000
```

### Zmiana obrotu

```text
zmiana = (obrot biezacy - obrot poprzedni) / obrot poprzedni * 100%
```

Zmiana jest liczona tylko wtedy, gdy poprzedni obrot jest wiekszy od zera.

### Udzial w przychodzie

```text
udzial klienta = obrot klienta / obrot wszystkich klientow * 100%
```

### Status klienta

- zmiana dodatnia: `Rosnacy`,
- zmiana ujemna: `Wymaga uwagi`,
- brak zmiany: `Stabilny`,
- brak okresu porownawczego: `Brak porownania`.

### Koncentracja przychodow

Klienci sa sortowani wedlug obrotu w wybranym okresie.

```text
koncentracja TOP 3 = suma udzialow trzech najwiekszych klientow
```

Najwiekszy klient to klient z najwyzszym obrotem. Aktywny klient to taki, ktory ma obrot wiekszy od zera w wybranym okresie.

Rankingi wzrostow i spadkow sa tworzone z procentowej zmiany obrotu; mockup pokazuje po trzy pierwsze pozycje.

## Dostawcy

Dla dostawcow obowiazuja analogiczne wzory jak dla klientow, ale ich trend reprezentuje koszt zakupow.

### Koszt i udzial dostawcy

```text
koszt dostawcy = suma trendu dostawcy w wybranym okresie * 1 000
udzial dostawcy = koszt dostawcy / koszt wszystkich dostawcow * 100%
```

### Status dostawcy

Interpretacja jest odwrotna niz dla klienta:

- wzrost kosztu: `Wymaga uwagi`,
- spadek kosztu: `Tanieje`,
- brak zmiany: `Stabilny`,
- brak okresu porownawczego: `Brak porownania`.

Koncentracja TOP 3, najwiekszy dostawca i liczba aktywnych dostawcow sa liczone tak samo jak po stronie klientow.

### Wzrost kosztu materialow

Do materialow zaliczani sa dostawcy w kategorii `Materialy produkcyjne`. Mockup porownuje laczny koszt tych dostawcow w styczniu i czerwcu:

```text
wzrost materialow = (koszt czerwca - koszt stycznia) / koszt stycznia * 100%
```

W obecnych danych:

```text
styczen: 58 700 zl
czerwiec: 74 000 zl
wzrost: okolo 26,1%
```

## Struktura kosztow i anomalie

### Koszt wedlug kategorii

Struktura kosztow jest budowana z faktur zakupowych z wybranych miesiecy. Faktury sa grupowane po kategorii, a pusta kategoria trafia do `Bez kategorii`.

```text
udzial kategorii = suma netto kategorii / suma netto wszystkich zakupow * 100%
```

Klikniecie kategorii na wykresie lub w tabeli ustawia odpowiedni filtr na liscie faktur zakupowych.

### Nowy koszt cykliczny

Koszt jest uznawany za nowy cykliczny, gdy lacznie spelnia warunki:

1. Dostawca nie mial dodatniego kosztu w styczniu.
2. Jego pierwszy miesiac z kosztem znajduje sie w wybranym okresie.
3. Kategoria to subskrypcja, najem, media albo usluga telekomunikacyjna.

Kwota nowego kosztu to koszt dostawcy w pierwszym dodatnim miesiacu. W aktualnych danych ten warunek spelnia CloudArch Backup w czerwcu.

### Nietypowy koszt

Mockup stosuje dwie reguly:

1. Dla istniejacego dostawcy koszt w wybranym miesiacu przekracza 150% sredniej z pozostalych dodatnich miesiecy.
2. Dla nowego dostawcy jego pierwsza faktura przekracza 10 000 zl.

Porownanie odbywa sie miesiac do miesiaca nawet wtedy, gdy uzytkownik wybral szerszy okres. Zapobiega to uznaniu sumy kilku zwyklych miesiecy za pojedyncza anomalie.

W pierwszej regule analizowana jest laczna miesieczna wartosc dostawcy, a nie kazda pojedyncza faktura.

## Analiza firmy na tle rynku

Analiza firmy zawsze korzysta z pelnego zakresu styczen-czerwiec. Nie zmienia sie razem z filtrem okresu na pulpicie.

### Dynamika sprzedazy firmy

```text
dynamika sprzedazy = (przychod czerwca - przychod stycznia)
                      / przychod stycznia * 100%
```

Dla obecnych danych wynosi okolo 3,6%.

### Marza firmy w analizie

```text
marza = (suma przychodow - suma kosztow - suma podatku)
         / suma przychodow * 100%
```

Dla calego okresu wynosi okolo 39,8%.

### Benchmarki rynkowe

**Demo:** wartosci rynkowe sa wpisane na stale i nie sa jeszcze pobierane z GUS, NBP ani innego zrodla:

- wzrost cen materialow: 7,2%,
- dynamika sprzedazy mebli: 4,8%,
- srednia marza branzy: okolo 21%,
- kurs EUR/PLN: w jednym miejscu 4,27, a w danych makro 4,31.

Porownanie firmy z rynkiem jest roznica w punktach procentowych:

```text
roznica = wynik firmy - benchmark
```

Dla kosztu materialow nizszy wynik jest lepszy. Dla sprzedazy i marzy wyzszy wynik jest lepszy.

Dlugosc paskow porownawczych jest normalizowana do najwiekszej bezwzglednej roznicy sposrod trzech metryk. Jest to jedynie skala wizualna.

## Szczegolowe zestawienie i podatek

W tej czesci mockup stosuje odrebny model podatkowy:

- miesieczny ZUS: 3 000 zl,
- stawka podatku: 19%,
- `dochod` oznacza przychod minus koszty, jeszcze przed podatkiem.

Dla kazdego miesiaca:

```text
dochod przed podatkiem = przychod - koszty
podstawa podatku = dochod przed podatkiem - ZUS
```

Nastepnie wartosci sa kumulowane od stycznia:

```text
podatek narastajaco = max(0, podstawa narastajaco) * 19%
```

Kwota podatku narastajaco jest zaokraglana do pelnych zlotych. Wiersz pokazuje kwote zaplacona do poprzedniego miesiaca oraz pozostala kwote do zaplaty. Po jej naliczeniu staje sie ona czescia sumy zaplaconej w kolejnym miesiacu.

Filtr miesiaca ukrywa niewybrane wiersze, ale nie przelicza narastania od zera. Najpierw liczone jest cale zestawienie styczen-czerwiec, a dopiero potem wybierane sa widoczne miesiace.

## Symulacje

Symulacje uzywaja czerwca jako miesiaca bazowego:

```text
przychod bazowy = 202 000 zl
koszt bazowy = 123 500 zl
marza bazowa brutto = (przychod - koszt) / przychod = okolo 38,9%
```

Ta marza nie uwzglednia podatku, dlatego nie jest tym samym co czerwcowa marza 30,4% na pulpicie.

### Zmiana ceny i wolumenu

```text
nowy przychod = przychod bazowy * (1 + zmiana ceny) * udzial wolumenu
nowy koszt = koszt bazowy * udzial wolumenu
nowa marza = (nowy przychod - nowy koszt) / nowy przychod * 100%
```

Wynik pokazuje roznice przychodu w zlotych i roznice marzy w punktach procentowych.

**Zalozenie:** wszystkie koszty sa zmienne i skaluja sie dokladnie razem z wolumenem. Zmiana ceny nie zmienia kosztu jednostkowego. Jest to symulacja wrazliwosci, a nie prognoza.

### Zatrudnienie pracownika

Mockup oblicza minimalna dodatkowa sprzedaz potrzebna do pokrycia miesiecznego kosztu pracownika:

```text
wymagana sprzedaz = miesieczny koszt pracownika / marza bazowa brutto
```

Wynik jest zaokraglany do pelnych zlotych. To prog rentownosci kosztu, a nie rekomendacja kadrowa.

### Utrata klienta

Punktem wyjscia jest czerwcowy przychod wybranego klienta i jego udzial w przychodzie firmy.

```text
koszt przypisany klientowi = koszt bazowy * udzial klienta
utracony przychod = przychod klienta * procent utraty
utracony koszt = koszt przypisany klientowi * procent utraty
utracony zysk brutto = utracony przychod - utracony koszt
```

**Zalozenie:** wszystkie koszty przypisane klientowi sa zmienne i proporcjonalne do jego udzialu w sprzedazy.

Poziom koncentracji klienta:

- co najmniej 15%: wysoki,
- od 8% do ponizej 15%: umiarkowany,
- ponizej 8%: niski.

Odpowiedzi asystenta widoczne w mockupie sa tekstami demonstracyjnymi. Nie wszystkie sa dynamicznie polaczone z suwakami scenariusza.

## Decyzje i zadania

Wiekszosc wykrytych decyzji ma statyczna tresc demonstracyjna. Czesc liczb jest zgodna z danymi zrodlowymi, ale nie sa one obecnie generowane przez jeden wspolny silnik regul.

Przyklady:

- MebloDom spada z 62 000 do 31 000 zl, czyli o 50%.
- MebloKlik rosnie z 9 600 do 15 000 zl, czyli o okolo 56,3%.
- Decyzja materialowa porownuje 92 000 z 113 000 zl i opisuje wzrost o 22,8%.
- Zmiana numeru rachunku na fakturze jest wylacznie przykladem; numer rachunku nie wystepuje w obecnym modelu faktury.

Priorytet decyzji jest mapowany na temperature zadania:

- blokujacy lub wysoki -> `gorace`,
- sredni -> `cieple`,
- niski -> `zimne`.

Pierwsza sugerowana akcja aktywnej decyzji jest dodawana automatycznie. Kolejne wymagaja akceptacji. Termin zadania to data utworzenia plus liczba dni przypisana do sugestii.

Decyzje sa sortowane najpierw wedlug priorytetu malejaco, a nastepnie wedlug daty utworzenia rosnaco. Zamknieta decyzja jest automatycznie archiwizowana po pieciu dniach.

## Gotowosc i jakosc danych

**Demo:** ekran gotowosci danych pokazuje miedzy innymi:

- 18 miesiecy danych KSeF,
- 1 284 faktury,
- 47 klientow,
- 68 dostawcow,
- pozycje faktur uzupelnione w 87%,
- ilosci i jednostki w 63%,
- terminy platnosci w 42%.

Te liczby nie wynikaja z aktualnego modelu mockupu. Model obliczeniowy zawiera szesc miesiecy, 12 klientow, 11 dostawcow i osobno wygenerowana liczbe faktur.

Oceny gotowosci sa opisowe:

- analiza koncentracji klientow: wysoka gotowosc,
- analiza cen: srednia gotowosc,
- rentownosc: dane czesciowe,
- przeplywy pieniezne: zablokowane bez danych bankowych.

## Znane rozbieznosci do rozstrzygniecia

### 1. Dwie definicje marzy

- Pulpit: marza po kosztach i podatku.
- Scenariusze: marza po kosztach, ale przed podatkiem.

**Do decyzji:** nazwac je jawnie `marza netto` i `marza brutto` albo ujednolicic definicje w calej aplikacji.

### 2. Dwa modele podatku

- Pulpit korzysta ze statycznej miesiecznej tablicy podatku.
- Szczegolowe zestawienie liczy 19% od podstawy pomniejszonej o ZUS, narastajaco.

**Do decyzji:** wskazac jeden system podatkowy i jedno zrodlo prawdy.

### 3. Dwa znaczenia slowa `dochod`

- Na pulpicie jest to przychod minus koszty minus podatek.
- W szczegolowym zestawieniu jest to przychod minus koszty, przed podatkiem.

**Do decyzji:** uzywac precyzyjnych nazw, np. `wynik przed podatkiem` i `wynik netto`.

### 4. Koszt czerwca 113 000 lub 123 500 zl

Decyzja o materialach podaje 113 000 zl, poniewaz opisuje dotychczasowa baze kosztowa bez nowej faktury CloudArch Backup. Glowny pulpit uwzglednia dodatkowe 10 500 zl i pokazuje 123 500 zl.

Ta roznica jest zamierzona w narracji mockupu, ale bez wyjasnienia moze wygladac jak blad.

### 5. Pola statyczne i wyniki przeliczane

Obiekty klientow i dostawcow maja wpisane na stale pola typu `value`, `share`, `change`, `status` i `invoices`, a jednoczesnie mockup potrafi przeliczac te wartosci dla wybranego zakresu.

**Rekomendacja:** w produkcji przechowywac dane zrodlowe, a wszystkie wskazniki pochodne liczyc w jednym miejscu.

### 6. Nowy koszt SysTech

Jedna statyczna decyzja opisuje SysTech jako nowy koszt cykliczny, ale jego trend zawiera 3 290 zl w kazdym miesiacu od stycznia. Dynamiczny detektor nowego kosztu wskazuje natomiast CloudArch Backup w czerwcu.

### 7. Dane rynkowe

Benchmarki i kursy walut sa demonstracyjne. Dodatkowo kurs EUR/PLN wystepuje jako 4,27 i 4,31 w roznych miejscach.

### 8. Faktury a glowne sumy

Glowne KPI pochodza z tablic miesiecznych, a czesc wykresow z faktur wygenerowanych na podstawie trendow klientow i dostawcow. Dane sa ulozone tak, aby sie zgadzaly, ale istnieja dwa techniczne zrodla tej samej informacji.

**Rekomendacja:** docelowo KPI, wykresy i rankingi powinny korzystac z jednego zestawu zaksiegowanych dokumentow lub z jednej warstwy agregatow utworzonej na ich podstawie.

## Proponowane jedno zrodlo prawdy w wersji produkcyjnej

Najprostszy spojny przeplyw wygladalby tak:

```text
faktury i korekty
  -> pozycje dokumentow i kategorie
  -> miesieczne agregaty klientow, dostawcow i podatkow
  -> KPI, wykresy, rankingi i reguly anomalii
  -> decyzje i zadania z zapisanym uzasadnieniem
```

Kazdy wynik analityczny powinien przechowywac lub umiec pokazac:

- okres, ktorego dotyczy,
- dokumenty zrodlowe,
- zastosowany wzor i wersje reguly,
- date ostatniego przeliczenia,
- informacje, czy wynik jest faktem, estymacja czy symulacja,
- jednostke: zl, procent albo punkt procentowy.

Takie podejscie pozwoli uzytkownikowi przejsc od liczby na pulpicie do faktur, z ktorych ta liczba powstala, i uniknie roznych definicji tego samego wskaznika na roznych ekranach.
