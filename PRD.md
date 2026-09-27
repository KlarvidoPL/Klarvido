# Klarvido — Product Requirements Document (PRD)

**Wersja:** 0.2
**Status:** source of truth dla MVP / pilotażu
**Data:** 2026-09-26
**Produkt:** Klarvido
**Kategoria wewnętrzna:** AI CFO / system decyzji finansowych dla MŚP
**Dokument powiązany:** `CALCULATIONS.md` — referencyjny opis logiki i zachowania aktualnego mockupu

---

## 0. Fazy realizacji i obowiązujący stack

Ten PRD opisuje kierunek produktu oraz kryteria płatnego pilotażu. Nie wszystkie wymagania są zakresem pierwszej implementacji. Realizacja została podzielona na fazy:

| Faza                        | Cel                                     | Źródła danych                               | Rezultat                                                         |
| --------------------------- | --------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------- |
| 0. Reference prototype      | Potwierdzenie UX i zakresu informacji   | Dane wpisane w mockup                       | Interaktywny wzorzec wizualny i `CALCULATIONS.md`                |
| 1. Synthetic vertical slice | Produkcyjna architektura jednej decyzji | Backendowe fixtures przez `MockDataAdapter` | Pełna ścieżka od faktury do outcome                              |
| 2. Source adapters          | Zastąpienie danych demonstracyjnych     | KSeF, GUS/REGON i NBP                       | Te same obliczenia i UI na danych zewnętrznych                   |
| 3. Paid pilot               | Walidacja wartości u pierwszych firm    | Dane pilotażowe i niezbędne dane ręczne     | Spełnienie kryteriów z sekcji 31 dla uzgodnionych rodzin decyzji |
| 4. Expansion                | Poszerzenie produktu i kanału B2B2C     | Bank i dodatkowe źródła operacyjne          | Kolejne decyzje, outcome i portfolio firm                        |

### Zakres danych fazy 1

Faza 1 obejmuje wyłącznie dane, które posiada aktualny mockup: firmę i jej profil, faktury sprzedażowe i zakupowe, klientów, dostawców, kategorie kosztów, okresy, demonstracyjny kontekst GUS/NBP oraz wyniki obliczeń opisanych w `CALCULATIONS.md`.

Transakcje bankowe, kadry, magazyn, CRM, rzeczywiste wykorzystanie zespołu i inne dane operacyjne pozostają poza fazą 1. Architektura może przewidywać ich późniejsze adaptery, ale nie implementuje modeli i procesów bez bieżącego przypadku użycia.

### Decyzja techniczna repozytorium

Obowiązującym stackiem implementacyjnym jest istniejący React/Vite, Django/GraphQL, PostgreSQL, Celery i AWS CDK. Pierwotnie rozważany wariant Next.js, FastAPI i Terraform został odrzucony dla tego repozytorium i nie jest planem migracji. Szczegóły zawiera `ARCHITECTURE.md`.

---

## 1. Streszczenie produktu

Klarvido nie jest systemem księgowym, ERP, narzędziem do fakturowania ani kolejnym dashboardem finansowym. Produkt ma pełnić rolę **AI CFO dla MŚP**: zamieniać dane finansowe i operacyjne w konkretne decyzje biznesowe, prowadzić użytkownika do wykonania działania, a następnie mierzyć rezultat.

Najważniejsza zasada produktu:

> **Dashboard pokazuje liczby. Klarvido mówi, co zrobić dalej.**

Docelowy przepływ:

```text
dane
→ sygnał
→ diagnoza
→ prawdopodobna przyczyna
→ możliwe działania
→ wybór działania
→ wykonanie
→ dowód wykonania
→ rezultat
→ ponowna ocena
```

KSeF, dane bankowe, GUS, NBP i inne źródła są **warstwą danych**, a nie kategorią produktu. Użytkownik nie kupuje „analityki KSeF”. Kupuje spokój, kontrolę, pewność decyzji i oszczędność czasu.

---

## 2. Problem użytkownika

Właściciel małej lub średniej firmy zazwyczaj ma dostęp do danych, ale nie ma czasu, kompetencji ani osoby odpowiedzialnej za ich ciągłą interpretację.

Typowe problemy:

- dane są rozproszone między księgowością, KSeF, bankiem, arkuszami i systemami operacyjnymi,
- księgowość mówi, **co się wydarzyło i jak to rozliczyć**, ale nie zawsze mówi, **co zrobić dalej**,
- klasyczny dashboard wymaga samodzielnej interpretacji,
- konsultant lub fractional CFO działa okresowo, a nie stale,
- właściciel podejmuje decyzje na podstawie intuicji, opóźnionych raportów i pojedynczych sygnałów,
- wiele problemów jest widocznych dopiero po czasie, np. osłabienie ważnego klienta, wzrost kosztu obsługi, koncentracja dostawców albo powolna erozja marży.

Klarvido ma dostarczać wartość zanim użytkownik nauczy się nazywać ją „controllingiem”, „FP&A” czy „rachunkowością zarządczą”.

---

## 3. Grupy docelowe

### 3.1. Właściciel MŚP — użytkownik główny

Profil orientacyjny:

- 3–50 pracowników,
- brak wewnętrznego CFO,
- korzysta z biura rachunkowego lub księgowości,
- sam podejmuje większość decyzji finansowych i operacyjnych,
- oczekuje odpowiedzi prostym językiem,
- nie chce konfigurować narzędzia analitycznego ani budować własnych dashboardów.

Najważniejsze pytania użytkownika:

- Czy tracę ważnego klienta?
- Który koszt wymaga reakcji?
- Czy jestem zbyt zależny od jednego dostawcy?
- Czy mogę zatrudnić kolejną osobę?
- Czy powinienem zmienić ceny?
- Dlaczego robię więcej, a zostaje mi mniej?
- Co powinienem zrobić w tym tygodniu?

### 3.2. Biuro rachunkowe — kanał B2B2C

Biuro rachunkowe korzysta z Klarvido jako warstwy doradczej dla portfela klientów.

Potrzeby:

- szybkie rozpoznanie klientów wymagających uwagi,
- możliwość świadczenia doradztwa premium bez budowania własnego działu controllingu,
- oddzielenie danych poszczególnych klientów,
- historia decyzji i rezultatów,
- potencjalnie widok portfolio w kolejnych fazach produktu.

---

## 4. Pozycjonowanie i zasady produktowe

### 4.1. Pozycjonowanie

Najbardziej precyzyjna definicja:

> **Klarvido automatycznie wykrywa sytuację wymagającą decyzji i otwiera właściwy zestaw analiz, rekomendacji oraz działań.**

Komunikacja do użytkownika może być prostsza:

> **Klarvido pilnuje Twojej firmy i mówi Ci, kiedy warto zareagować.**

### 4.2. Zasady

1. **Decision-first.** Ekran zaczyna się od sytuacji i działania, nie od KPI.
2. **Action-first.** Informacja bez możliwego działania ma niższy priorytet.
3. **Jedno źródło prawdy.** Wskaźniki pochodne nie mogą być wpisywane statycznie w kilku miejscach.
4. **Explainability by default.** Każda istotna liczba i decyzja musi prowadzić do źródeł, wzoru i ograniczeń.
5. **Data readiness before diagnosis.** System najpierw ocenia, czy ma prawo wykonać analizę.
6. **LLM nie jest kalkulatorem ani źródłem prawdy.** Obliczenia wykonuje deterministyczna warstwa danych i Decision Engine.
7. **Nie udajemy wiedzy.** Brak danych ma skutkować ograniczeniem lub pytaniem, a nie halucynacją.
8. **Rezultat jest częścią produktu.** Rekomendacja nie kończy procesu; Outcome Engine wraca do niej później.
9. **KSeF jest niewidoczną infrastrukturą.** Nie sprzedajemy produktu jako „narzędzia KSeF”.
10. **Minimalna konfiguracja przez użytkownika.** Klarvido bierze na siebie odpowiedzialność za wybór analiz i priorytetów.

---

## 5. Cele MVP

MVP ma udowodnić, że Klarvido potrafi przeprowadzić pełny pionowy przebieg jednej decyzji, a nie tylko pokazać poprawne dane.

### 5.1. Główne pytanie MVP

> Czy na podstawie KSeF, minimalnych danych operacyjnych i kontekstu gospodarczego system potrafi regularnie wskazać właścicielowi trafne działanie, doprowadzić do wykonania i później zweryfikować efekt?

### 5.2. Pętla MVP

```text
onboarding
→ Company Economic Profile
→ weryfikacja profilu na danych
→ konfiguracja rachunkowości zarządczej
→ ingest i walidacja danych
→ wykrycie sygnału
→ diagnoza
→ wygenerowanie kandydatów działań
→ Data Readiness + Safety Gates
→ ranking
→ rekomendacja
→ działanie
→ evidence
→ outcome
```

### 5.3. Pierwszy archetyp pilotażowy

**Usługa B2B oparta na ludziach**, np.:

- agencja,
- software house,
- biuro rachunkowe,
- firma konsultingowa,
- firma techniczna/projektowa.

Powód: duża część sprzedaży jest widoczna w fakturach, a jednocześnie można testować klientów, projekty, koszty podwykonawców, zatrudnienie i zdolność operacyjną.

### 5.4. Archetyp kontrastowy

Działalność wolumenowo-materiałowa, np. catering lub lekka produkcja, wykorzystywana do testów jakości modelu i elastyczności konfiguracji.

---

## 6. Zakres MVP — Must / Should / Later

### 6.1. MUST

- onboarding i Company Economic Profile,
- integracja KSeF / import danych fakturowych,
- canonical data model,
- Data Quality Engine + Data Readiness Gate,
- klienci i dostawcy,
- faktury, filtrowanie, wyszukiwanie i CSV,
- podstawowe KPI i trendy zdefiniowane w `CALCULATIONS.md`,
- kontekst GUS / REGON / NBP,
- 3 głębokie rodziny decyzji,
- Decision Workspace,
- Recommendation Protocol / Decision Contract,
- zadania i status wykonania,
- Outcome Engine,
- audit trail i wyjaśnienie źródeł,
- symulacje: cena/wolumen, zatrudnienie, utrata klienta,
- historia decyzji,
- rozmowa z asystentem w kontekście danych i aktualnego Decision Workspace.

### 6.2. SHOULD

- dodatkowe sygnały KSeF-native: koncentracja klientów, koncentracja dostawców, nowy koszt cykliczny, nietypowy koszt, kandydat do renegocjacji,
- aktywne pytania uzupełniające o brakujące dane,
- scoring jakości danych,
- adaptacyjne baseline’y zamiast wyłącznie sztywnych progów,
- biblioteka Decision Components współdzielona między widokami.

### 6.3. LATER / poza MVP

- pełny bankowy cash flow i rzeczywiste DSO,
- pełne ERP / magazyn / CRM,
- automatyzacja podatkowa jako system rozliczeniowy,
- Knowledge Graph / GraphRAG w produkcji,
- contextual bandits / reinforcement learning,
- własny feature store,
- autonomiczne agenty wykonujące niekontrolowane działania,
- fine-tuning własnego LLM,
- pełny konfigurowalny dashboard builder,
- aplikacja mobilna jako osobny natywny produkt.

---

## 7. Główne podróże użytkownika

### 7.1. Pierwsze uruchomienie

1. Użytkownik zakłada konto i firmę.
2. REGON/GUS uzupełnia możliwe dane identyfikacyjne.
3. Użytkownik odpowiada na maksymalnie 6 pytań podstawowych i 1–3 zależne od modelu.
4. Powstaje wstępny Company Economic Profile.
5. Użytkownik podłącza KSeF lub importuje dane testowe.
6. System wykonuje ocenę jakości danych.
7. System pokazuje, jakie analizy są dostępne, ograniczone lub zablokowane.
8. Po przetworzeniu danych użytkownik otrzymuje pierwszą wartościową decyzję.

### 7.2. Codzienne/tygodniowe użycie

1. Użytkownik wchodzi do widoku **Dzisiaj**.
2. Widzi maksymalnie kilka spraw wymagających uwagi.
3. Otwiera Decision Workspace.
4. Widzi: co się zmieniło, dlaczego to ważne, dowody, ograniczenia, rekomendację i możliwe działania.
5. Wybiera działanie albo odpowiada na pytanie uzupełniające.
6. Działanie trafia do zadań / historii decyzji.
7. Outcome Engine wraca po określonym czasie i ocenia efekt.

### 7.3. Eksploracja danych

Użytkownik może zejść głębiej do klientów, dostawców, faktur, trendów i wzorów, ale eksploracja nie jest domyślnym sposobem korzystania z produktu.

---

## 8. Architektura informacji i nawigacja

### 8.1. Dzisiaj

- aktywne decyzje,
- maksymalnie kilka priorytetów,
- status firmy w prostym języku,
- brak ściany KPI jako pierwszego elementu.

### 8.2. Wymaga decyzji

Lista aktywnych problemów i szans z:

- priorytetem,
- terminem,
- confidence,
- statusem wykonania,
- oczekiwanym efektem,
- ograniczeniami danych.

### 8.3. Firma

Gotowy przegląd:

- sprzedaż,
- koszty,
- klienci,
- dostawcy,
- struktura kosztów,
- podstawowe KPI,
- kontekst gospodarczy,
- jakość danych.

### 8.4. Laboratorium decyzji

Symulacje i scenariusze:

- zmiana ceny i wolumenu,
- zatrudnienie pracownika,
- utrata klienta,
- nowy koszt stały,
- zmiana dostawcy,
- inne scenariusze dodawane później.

### 8.5. Historia decyzji

```text
co wykryto
→ co zalecono
→ co użytkownik zrobił
→ jaki był rezultat
```

### 8.6. Dane i źródła

Widok techniczny:

- KSeF,
- dane operacyjne,
- GUS / REGON / NBP,
- pokrycie danych,
- kompletność,
- świeżość,
- źródła wyliczeń,
- wersje reguł.

---

## 9. Onboarding i Company Economic Profile

Klarvido nie pyta użytkownika „jaki masz model biznesowy?”. System buduje **profil ekonomiczny firmy**.

### 9.1. Sześć modeli przychodowych

1. Abonament / stała obsługa.
2. Projekt / kontrakt.
3. Produkt / transakcja.
4. Czas lub zdolność operacyjna.
5. Wolumen / użycie.
6. Prowizja / wynik.

Firma może mieć maksymalnie dwa główne modele z orientacyjnymi udziałami.

### 9.2. Minimalne wymiary profilu

```yaml
revenue_streams:
  - model
  - estimated_share
  - confidence

customer_type:
  - B2B
  - B2C
  - mixed

economic_object:
  - customer_contract_month
  - project
  - order
  - hour
  - operating_unit
  - successful_outcome

cost_drivers:
  primary:
  secondary:

growth_constraint:
  primary:

pricing_mechanism:
cash_timing:
data_coverage:
missing_information:
```

### 9.3. Logika profilu

Najważniejsze połączenie:

```text
model przychodowy
× mechanizm kosztowy
× ograniczenie wzrostu
× rytm gotówkowy
```

### 9.4. Business Model Verification Engine

Onboarding tworzy hipotezę, a dane ją potwierdzają lub podważają.

Dla każdego elementu profilu system przechowuje:

- `SUPPORT`,
- `CONTRADICTION`,
- `UNKNOWN`.

Brak danych nie jest dowodem przeciwko modelowi.

---

## 10. Źródła danych

### 10.1. KSeF

Główne automatyczne źródło w MVP:

- faktury sprzedażowe,
- faktury zakupowe,
- kontrahenci,
- daty i wartości,
- waluta,
- korekty i zaliczki,
- pozycje, ilości, jednostki i ceny — jeżeli dostępne,
- terminy płatności — jeżeli uzupełnione.

KSeF nie jest wystarczający do potwierdzenia rzeczywistej daty zapłaty, salda bankowego ani pełnej sprzedaży B2C.

### 10.2. Dane operacyjne podawane przez firmę

Uniwersalnie:

- liczba pracowników,
- miesięczny koszt wynagrodzeń,
- koszty stałe niewidoczne w fakturach,
- większe planowane wydatki,
- orientacyjna sprzedaż B2C poza KSeF,
- liczba zamówień / klientów / jednostek operacyjnych, jeśli wpływa to na decyzje.

Zasada: nie tworzymy długiej ankiety księgowej. System pyta tylko o dane, które zmieniają rekomendację.

### 10.3. GUS / REGON

- dane identyfikacyjne przedsiębiorstwa,
- branża / PKD jako kontekst,
- lokalizacja,
- inflacja,
- PPI,
- dynamika wynagrodzeń,
- bezrobocie regionalne,
- wybrane dane branżowe.

### 10.4. NBP

- kursy walut,
- stopy procentowe,
- kontekst finansowania.

### 10.5. Dane bankowe

Nie są wymagane dla pierwszego vertical slice’u. Po integracji odblokują:

- faktyczne daty wpływów i wypływów,
- saldo,
- rzeczywisty cash flow,
- DSO / payment behavior,
- mocniejsze dowody Outcome Engine.

---

## 11. Canonical Data Model i jedno źródło prawdy

Docelowy przepływ danych:

```text
faktury i korekty
→ pozycje dokumentów
→ normalizacja i kategorie
→ canonical facts
→ agregaty okresowe
→ metrics / features / signals
→ Decision Engine
→ Decision Package
→ Outcome Engine
```

Zasada produkcyjna: nie przechowujemy statycznie wartości pochodnych takich jak `share`, `change`, `status` i `value`, jeżeli mogą zostać wyliczone ze źródeł.

Każdy wynik analityczny musi umożliwiać pokazanie:

- okresu,
- dokumentów źródłowych,
- zastosowanego wzoru,
- wersji wzoru / reguły,
- daty przeliczenia,
- statusu: fakt / estymacja / symulacja,
- jednostki,
- jakości danych.

---

## 12. Data Quality Engine i Data Readiness Gate

### 12.1. Dwie warstwy walidacji

**Data validation** sprawdza techniczną poprawność danych.
**Data Readiness** sprawdza, czy dane są wystarczające do konkretnej analizy.

Przykładowe pola:

```text
ksef_revenue_coverage
b2b_revenue_coverage
b2c_revenue_coverage
line_item_completeness
quantity_completeness
unit_price_completeness
buyer_identification_completeness
payment_field_completeness
history_length
freshness
```

### 12.2. Status analizy

Każda analiza ma stan:

- `READY`,
- `LIMITED`,
- `BLOCKED`.

Przykład:

- koncentracja klientów: READY przy wysokiej identyfikacji nabywców,
- price/volume: LIMITED lub BLOCKED przy niskiej kompletności ilości,
- cash flow: BLOCKED bez danych bankowych,
- pełna rentowność klienta: LIMITED bez danych o pracy i kosztach przypisanych.

### 12.3. Wymóg bezpieczeństwa

Decision Engine **nie może** wydać mocniejszej diagnozy niż pozwala jakość danych.

---

## 13. Warstwa obliczeń — wymagania z CALCULATIONS.md

`CALCULATIONS.md` pozostaje referencją dla szczegółowych wzorów i zachowania aktualnego mockupu. PRD definiuje docelowe wymagania produktowe i miejsca, w których mockup jest wyłącznie demonstracją.

### 13.1. Wybór okresu

System obsługuje co najmniej:

- bieżący miesiąc,
- poprzedni miesiąc,
- ostatni kwartał,
- własny miesiąc / zakres,
- półrocze / rok po uzyskaniu odpowiedniej historii.

Dla okresów wielomiesięcznych wartości pieniężne są sumowane. Zmiana procentowa:

```text
zmiana = (wartość bieżąca - wartość poprzednia)
         / |wartość poprzednia| * 100%
```

Jeżeli brak okresu porównawczego lub poprzednia wartość wynosi zero, zmiana nie jest liczona.

### 13.2. KPI

Minimum:

- przychód,
- koszty,
- wynik przed podatkiem,
- wynik netto — tylko jeśli istnieje wiarygodne źródło podatku,
- marża brutto,
- marża netto — jeżeli dostępny jest wynik netto.

### 13.3. Decyzja terminologiczna PRD

W produkcji nie używamy jednego słowa `dochód` dla dwóch definicji.

- `wynik przed podatkiem = przychód - koszty`,
- `wynik netto = przychód - koszty - podatek`,
- `marża brutto = wynik przed podatkiem / przychód`,
- `marża netto = wynik netto / przychód`.

Zmiana marży jest pokazywana w **punktach procentowych**.

### 13.4. Podatek

Klarvido nie jest programem podatkowym.

Wymaganie produkcyjne:

- podatek może być pokazany tylko jako wartość pochodząca z wiarygodnego źródła lub jawna estymacja,
- uproszczony model `19% po ZUS` z mockupu pozostaje demonstracją i nie stanowi docelowego silnika podatkowego,
- każda estymacja podatku musi być jednoznacznie oznaczona.

### 13.5. Klienci

Wymagane obliczenia:

```text
obrót klienta = suma wartości klienta w okresie
udział klienta = obrót klienta / obrót wszystkich klientów * 100%
koncentracja TOP 3 = suma udziałów 3 największych klientów
```

Dodatkowo:

- ranking wzrostów,
- ranking spadków,
- aktywni klienci,
- rytm fakturowania,
- ostatnia aktywność,
- trend wartości i częstotliwości.

### 13.6. Dostawcy

Analogicznie:

```text
koszt dostawcy = suma kosztu w okresie
udział dostawcy = koszt dostawcy / koszt wszystkich dostawców * 100%
```

Wzrost kosztu nie jest automatycznie „zły”; status musi być interpretowany w kontekście wolumenu, modelu kosztowego i rynku.

### 13.7. Struktura kosztów

```text
udział kategorii = suma netto kategorii / suma netto zakupów * 100%
```

Kliknięcie kategorii powinno prowadzić do dokumentów źródłowych.

### 13.8. Nowy koszt cykliczny

System wykrywa powtarzalność i pierwszy moment pojawienia się kosztu. Sztywna lista kategorii z mockupu może być baseline’em, ale docelowo wykrycie wykorzystuje również podobieństwo dostawcy, opisu i rytmu faktur.

### 13.9. Nietypowy koszt

Reguła demonstracyjna z mockupu:

- istniejący dostawca: miesiąc >150% średniej pozostałych dodatnich miesięcy,
- nowy dostawca: pierwsza faktura >10 000 zł.

W produkcji jest to baseline porównawczy. Docelowo próg ma uwzględniać normalny rytm firmy, sezonowość i skalę działalności.

### 13.10. Benchmarki i makro

Porównanie firmy z rynkiem jest kontekstem diagnozy, nie osobnym produktem.

System musi odróżniać:

```text
zmianę typową dla rynku
vs
zmianę specyficzną dla firmy
vs
brak wystarczających danych
```

Dane demonstracyjne z mockupu nie mogą być użyte produkcyjnie.

### 13.11. Wykresy

Wykresy służą jako dowód i wyjaśnienie, a nie główny bohater produktu.

Wymagania:

- dokładne wartości zawsze dostępne w tabeli / tooltipie,
- wizualne wygładzanie nie może tworzyć fikcyjnych danych,
- punkty pośrednie generowane dla wyglądu nie mogą być użyte w analizie,
- zakres i skala osi muszą być opisane,
- wszystkie dane wykresu muszą pochodzić z canonical aggregates.

---

## 14. Management Accounting Configuration Engine

Business Model Verification Engine odpowiada: **jak firma zarabia?**
Management Accounting Configuration Engine odpowiada: **co w tej firmie należy mierzyć?**

### 14.1. Wspólny rdzeń

System konfiguruje:

- obiekt marży,
- koszt bezpośredni,
- koszt zdolności,
- koszt wspólny,
- główny driver kosztu,
- główne ograniczenie wzrostu,
- główny rytm przychodów i kosztów.

### 14.2. Wielopoziomowa marża

Docelowy model:

```text
Przychód
- bezpośredni koszt zmienny
= Marża I

Marża I
- koszty przypisane klientowi / projektowi / transakcji
= Marża II

Marża II
- koszt wykorzystanej zdolności operacyjnej
= Marża III

Suma Marży III
- koszty wspólnej infrastruktury
= wynik operacyjny
```

W MVP stosujemy tylko poziomy, dla których mamy wystarczające dane.

---

## 15. Decision Engine

### 15.1. Architektura logiczna

Rekomendowany model to **hybrydowy Next Best Action Engine**:

```text
Canonical Data
→ Feature & Signal Layer
→ Candidate Generator
→ Data Readiness Gate
→ Safety Gate
→ Transparentny Ranker
→ Decision Package
→ Constrained LLM
```

### 15.2. Odpowiedzialności

Decision Engine:

- liczy i interpretuje sygnały,
- generuje kandydatów działań,
- odrzuca działania niedopuszczalne,
- ocenia wpływ, pilność, pewność i wykonalność,
- wybiera działanie do pokazania.

LLM:

- tłumaczy wynik,
- upraszcza język,
- zadaje pytanie uzupełniające,
- tworzy draft działania,
- odpowiada w kontekście zaakceptowanych danych i reguł.

LLM nie powinien samodzielnie:

- liczyć KPI,
- ustalać faktów finansowych,
- tworzyć nowych reguł bezpieczeństwa,
- wymyślać dowolnych rekomendacji spoza katalogu działań.

---

## 16. Główne rodziny decyzji MVP

### 16.1. Klient słabnie / przestaje kupować

Sygnały:

- spadek wartości sprzedaży,
- spadek częstotliwości,
- wydłużony czas od ostatniej faktury,
- zanik dodatkowych projektów / pozycji,
- znaczący udział klienta w przychodzie.

Dopuszczalne interpretacje:

- relacja słabnie,
- wzorzec odbiega od normalnego rytmu,
- brak wystarczających danych.

Zakazane twierdzenia bez dodatkowego dowodu:

- klient na pewno odchodzi,
- klient wybrał konkurencję.

Możliwe działania:

- kontakt,
- przygotowanie rozmowy / oferty odnowienia,
- obserwacja bez działania,
- zabezpieczenie koncentracji przychodów.

### 16.2. Koszt obsługi / materiałów / podwykonawców rośnie szybciej niż przychód

Sygnały:

- wzrost kategorii kosztowej,
- wzrost dostawcy,
- spadek marży,
- stabilny przychód przy rosnącym koszcie,
- benchmark rynkowy wolniejszy od wzrostu kosztu firmy.

Możliwe działania:

- sprawdzenie pozycji o największym wzroście,
- renegocjacja dostawcy,
- zmiana zakresu usługi,
- korekta ceny,
- zmiana dostawcy,
- obserwacja.

### 16.3. Zatrudnić, wykorzystać obecną zdolność czy zmienić ceny

Wymaga danych operacyjnych.

Sygnały:

- wykorzystanie zespołu,
- backlog / popyt,
- marża na godzinę lub jednostkę,
- koszt nowej osoby,
- oczekiwana dodatkowa sprzedaż,
- ograniczenie wzrostu.

System nie może wydać rekomendacji kadrowej tylko na podstawie prostego progu `koszt / marża`. Symulacja z `CALCULATIONS.md` jest narzędziem pomocniczym, nie samą decyzją.

---

## 17. Dodatkowe sygnały i decyzje wspierające

MVP powinno technicznie obsługiwać także:

- koncentrację klientów,
- koncentrację dostawców,
- rosnącego klienta,
- nowy koszt cykliczny,
- nietypowy koszt,
- kandydata do renegocjacji,
- spadek całkowitej sprzedaży,
- odchylenie od sezonowości,
- zmianę ceny jednostkowej przy wystarczających danych,
- ryzyko walutowe przy ekspozycji na walutę.

Nie wszystkie muszą mieć w pierwszym pilotażu pełny Outcome Engine i kompletny workflow egzekucji.

---

## 18. Recommendation Protocol / Decision Contract

Rekomendacja jest wykonywalnym obiektem, a nie tekstem.

Minimalny kontrakt:

```yaml
decision_family:
applicable_business_models:
economic_question:

required_data:
optional_data:

data_readiness:
  minimum_history:
  minimum_completeness:

signals:
allowed_diagnoses:
forbidden_claims:

action_candidates:
safety_constraints:

ranking:
  impact:
  urgency:
  confidence:
  effort:
  reversibility:

selected_action:
priority:
timeframe:

implementation_evidence:
  A:
  B:
  C:
  D:

outcome_evidence:
  A:
  B:
  C:
  D:

evaluation_window:
success_metric:
limitations:
calculation_version:
```

Ten sam kontrakt jest używany przez:

- Decision Engine,
- UI,
- LLM,
- Outcome Engine,
- testy automatyczne,
- audit trail.

---

## 19. Outcome Engine

### 19.1. Cel

System ma oceniać nie tylko, czy użytkownik kliknął „wykonano”, ale czy świat rzeczywiście się zmienił.

### 19.2. Poziomy dowodów

**A — twardy dowód w danych**
Np. pojawiła się nowa faktura, zmienił się udział klienta, koszt spadł.

**B — dowód pośredni**
Zmiana jest zgodna z działaniem, ale nie dowodzi przyczynowości.

**C — dowód systemowy**
Działanie wykonane z Klarvido lub przez integrację, np. wysłanie wiadomości.

**D — deklaracja użytkownika**
Najniższa jakość; nie może samodzielnie zasilać modelu jako mocny dowód.

### 19.3. Dwa oddzielne confidence

- **Implementation Confidence** — czy działanie rzeczywiście zostało wdrożone.
- **Outcome Confidence** — na ile zmiana może wynikać z rekomendacji.

### 19.4. Evaluation Recipe

Każda decyzja określa:

- baseline,
- metrykę sukcesu,
- okno pomiaru,
- warunek sukcesu,
- częściowy sukces,
- porażkę,
- czynniki zakłócające.

---

## 20. Decision Workspace i komponenty UI

### 20.1. Trzy poziomy doświadczenia

**Poziom 1 — Gotowa decyzja**
Krótki komunikat i działanie.

**Poziom 2 — Widok decyzyjny**
Co się zmieniło, dlaczego, możliwa przyczyna, dowody, ograniczenia, rekomendacja, działania, sposób pomiaru.

**Poziom 3 — Pokaż analizę**
Dane źródłowe, wykresy, filtry, wzory, scenariusze i drill-down.

### 20.2. Decision Components

Komponent może mieć typ:

- recommendation,
- diagnosis,
- evidence,
- metric,
- chart,
- table,
- question,
- scenario,
- action,
- outcome,
- limitation.

Backend zwraca definicję widoku, a frontend składa ją z kontrolowanej biblioteki komponentów.

---

## 21. Funkcje z aktualnego mockupu wymagane w produkcie

### 21.1. Pulpit / Company Overview

- wybór okresu,
- przychód,
- koszty,
- wynik,
- marże,
- porównanie do poprzedniego okresu,
- wykres trendu,
- tabela dokładnych wartości.

Pulpit pozostaje warstwą drugą względem decision-first home.

### 21.2. Faktury

- sprzedaż / zakup,
- filtrowanie po kategorii i miesiącu,
- wyszukiwanie po numerze i kontrahencie,
- sortowanie po dacie,
- CSV aktualnego widoku,
- drill-down z KPI i kategorii do faktur.

### 21.3. Klienci

- obrót,
- udział,
- zmiana,
- trend,
- liczba dokumentów,
- koncentracja TOP 3,
- ranking wzrostów i spadków,
- profil klienta.

### 21.4. Dostawcy

- koszt,
- udział,
- trend,
- koncentracja TOP 3,
- ranking zmian,
- profil dostawcy,
- powiązane kategorie kosztów.

### 21.5. Struktura kosztów

- kategorie,
- udział procentowy,
- możliwość przejścia do dokumentów,
- wykrycie nowego kosztu cyklicznego,
- wykrycie kosztu nietypowego.

### 21.6. Benchmarking

- porównanie wybranych wskaźników firmy do odpowiedniego kontekstu rynkowego,
- wyłącznie wtedy, gdy istnieje poprawne mapowanie i aktualne źródło,
- benchmark nie może być prezentowany jako „średnia branży”, jeśli źródło nie uzasadnia takiego poziomu szczegółowości.

---

## 22. Symulacje

### 22.1. Cena i wolumen

Baseline z aktualnego mockupu:

```text
nowy przychód = przychód bazowy * (1 + zmiana ceny) * udział wolumenu
nowy koszt = koszt bazowy * udział wolumenu
nowa marża = (nowy przychód - nowy koszt) / nowy przychód
```

W produkcie użytkownik musi widzieć założenie, że koszty skalują się razem z wolumenem.

### 22.2. Zatrudnienie

Baseline:

```text
minimalna dodatkowa sprzedaż = miesięczny koszt pracownika / marża bazowa brutto
```

Wynik jest progiem rentowności kosztu, **nie rekomendacją zatrudnienia**.

### 22.3. Utrata klienta

Baseline:

```text
koszt przypisany klientowi = koszt bazowy * udział klienta
utracony przychód = przychód klienta * procent utraty
utracony koszt = koszt przypisany klientowi * procent utraty
utracony zysk brutto = utracony przychód - utracony koszt
```

Wymagane jawne oznaczenie założenia o proporcjonalności kosztów.

### 22.4. Zasada dla wszystkich scenariuszy

Każdy wynik musi być oznaczony jako **symulacja**, a nie prognoza lub fakt.

---

## 23. Zadania i egzekucja

Aktywna decyzja może generować działania.

Minimalne wymagania:

- pierwsze rekomendowane działanie może zostać utworzone automatycznie jako sugestia,
- kolejne działania wymagają potwierdzenia,
- priorytet i termin wynikają z Decision Contract,
- zadanie może mieć status: `proposed`, `accepted`, `in_progress`, `done`, `cancelled`,
- zamknięta decyzja nie znika bez śladu — trafia do historii,
- autoarchiwizacja może być konfigurowana, ale nie może usuwać audytu.

Temperatura `gorące/ciepłe/zimne` z mockupu jest wyłącznie warstwą prezentacji; źródłem jest formalny priorytet.

---

## 24. Asystent Klarvido

Asystent działa na kontekście firmy i aktualnego widoku.

Powinien odpowiadać na pytania typu:

- „Dlaczego uważasz, że ten klient słabnie?”
- „Pokaż faktury, na których to widzisz.”
- „Co się stanie, jeśli podniosę cenę o 5%?”
- „Czego brakuje, żebyś mógł ocenić rentowność?”

Każda odpowiedź dotycząca danych firmy musi korzystać z przygotowanych faktów, metryk i Decision Package, a nie z pamięci LLM.

---

## 25. Transparentność i audyt

Każda decyzja musi posiadać audit trail:

```text
źródła
→ transformacje
→ metryki
→ sygnały
→ reguły / model
→ kandydaci działań
→ ranking
→ wybrana rekomendacja
→ tekst pokazany użytkownikowi
→ wykonanie
→ outcome
```

Użytkownik powinien móc wejść z decyzji do dokumentów źródłowych.

---

## 26. Wielofirmowość, role i bezpieczeństwo

### 26.1. Tenant model

```text
tenant_id = firma
user_id = osoba
role = owner / accountant / advisor / office_admin
```

Dane każdej firmy muszą być logicznie odseparowane.

### 26.2. Minimalne wymagania bezpieczeństwa

- szyfrowanie danych w tranzycie i spoczynku,
- brak współdzielonych tokenów KSeF między tenantami,
- secret management po stronie infrastruktury,
- audit log operacji administracyjnych,
- zasada najmniejszych uprawnień,
- możliwość odłączenia integracji,
- kontrola eksportu danych,
- MFA co najmniej dla administratorów i docelowo biur rachunkowych.

---

## 27. Architektura techniczna MVP

### 27.1. Założenie

**Modularny monolit**, nie mikroserwisy.

```text
React / Vite / TypeScript
↓
CloudFront / WAF
↓
Django / GraphQL / Python
↓
PostgreSQL + Celery + opcjonalne S3/SQS
↓
Decision Engine + Outcome Engine
↓
Ograniczona warstwa LLM
```

### 27.2. Stack

Frontend:

- TypeScript,
- React 19 + Vite,
- Apollo Client / GraphQL,
- Tailwind,
- współdzielone komponenty shadcn/ui z `webapp-core`,
- Recharts do wizualizacji,
- TanStack Table.

Backend:

- Python 3.11,
- Django 5,
- Graphene / GraphQL,
- Django ORM i migracje Django,
- Celery dla zadań asynchronicznych,
- pytest; Hypothesis może zostać dodany dla testów inwariantów finansowych.

Infra:

- ECS Fargate,
- PostgreSQL / RDS,
- CloudFront,
- S3, SQS i EventBridge tam, gdzie wymaga tego konkretny przepływ,
- istniejący system uwierzytelniania i tenantów,
- AWS CDK,
- GitHub Actions + AWS OIDC.

Observability:

- OpenTelemetry,
- Sentry,
- analityka produktu zgodna z metrykami z sekcji 30; PostHog pozostaje kandydatem, nie zależnością MVP.

### 27.3. Moduły backendu

Funkcje produktowe powstają w jednej aplikacji Django `apps/klarvido`, podzielonej wewnętrznie na canonical data, adaptery źródeł, obliczenia, jakość danych, profil ekonomiczny, decyzje, działania, outcome i audyt. To granice modułów wewnątrz modularnego monolitu, a nie osobne mikroserwisy lub wdrożenia. Szczegółowe granice zawiera `ARCHITECTURE.md`.

---

## 28. Testowanie

### 28.1. Testy jednostkowe

- wzory finansowe,
- okresy,
- agregacje,
- rankingi,
- statusy danych.

### 28.2. Property-based testing

Inwarianty przykładowe:

- przy niewystarczającym coverage system nie może wydać diagnozy całej sprzedaży,
- bez banku system nie może stwierdzić „klient nie zapłacił”,
- przy niskiej kompletności ilości price-volume jest blokowany,
- siła rekomendacji nie może przekraczać poziomu wsparcia diagnozy,
- udziały klientów po poprawnej agregacji muszą sumować się w przybliżeniu do 100%.

### 28.3. Dane syntetyczne

Decision Engine powinien być testowany również na sztucznie generowanych scenariuszach z oczekiwanym wynikiem, aby wykrywać false positives i false negatives przed wdrożeniem u klientów.

---

## 29. Wymagania niefunkcjonalne

### 29.1. Wydajność

- typowy widok aplikacji: odpowiedź API docelowo <2 s dla danych gotowych,
- cięższe przeliczenia asynchroniczne,
- przeliczenie po nowym imporcie nie może blokować UI,
- cache dla agregatów i Decision Packages.

### 29.2. Niezawodność

- przetwarzanie idempotentne,
- możliwość ponownego uruchomienia synchronizacji,
- stan błędu integracji widoczny użytkownikowi,
- brak częściowego „cichego” przeliczenia bez statusu.

### 29.3. Wyjaśnialność

Każda decyzja i ważna liczba musi mieć źródło, wzór i status jakości danych.

### 29.4. Dostępność

- klawiatura,
- poprawna hierarchia nagłówków,
- kontrast,
- semantyczne tabele,
- brak przekazywania znaczenia wyłącznie kolorem.

---

## 30. Metryki produktu

Klarvido nie powinno optymalizować DAU jako głównej miary.

Najważniejsze:

### 30.1. Time to First Value

Czas od podłączenia danych do pierwszej decyzji, którą użytkownik uznał za wartościową.

### 30.2. Activation

Odsetek firm, które w pierwszych 14 dniach:

- otrzymały co najmniej jedną sensowną decyzję,
- otworzyły ją lub wykonały działanie.

### 30.3. Action Rate

Odsetek rekomendacji prowadzących do zaakceptowanego działania.

### 30.4. Verified Value

Szacowany i zweryfikowany efekt finansowy decyzji wspieranych przez Klarvido.

### 30.5. Issues Detected Early

Liczba problemów wykrytych zanim użytkownik sam je zgłosił.

### 30.6. Retention

Retencja firm, również w okresach bez alarmów.

---

## 31. Kryteria akceptacji MVP

MVP jest gotowe do płatnego pilotażu, gdy:

1. Nowa firma może przejść onboarding i utworzyć Economic Profile.
2. Dane KSeF mogą zostać pobrane/importowane i przekształcone do canonical model.
3. Data Quality Engine potrafi zablokować analizę przy brakujących danych.
4. KPI, klienci, dostawcy, faktury i struktura kosztów korzystają z jednego źródła agregatów.
5. Co najmniej 3 rodziny decyzji mają pełny Decision Contract.
6. Decision Engine wybiera kandydatów i pokazuje uzasadnienie.
7. Każda decyzja pokazuje dowody, ograniczenia i poziom pewności.
8. Użytkownik może zaakceptować działanie i śledzić jego status.
9. Outcome Engine potrafi po czasie ocenić co najmniej jedną metrykę rezultatu.
10. Symulacje są jawnie oddzielone od faktów.
11. LLM nie wykonuje obliczeń będących źródłem prawdy.
12. Audit trail pozwala odtworzyć, skąd wzięła się decyzja.
13. Dane tenantów są izolowane.
14. Produkt ma telemetrykę aktywacji, Decision Opened, Action Accepted, Outcome Evaluated.

---

## 32. Rozbieżności mockupu — decyzje produkcyjne

Poniższe punkty z `CALCULATIONS.md` nie mogą pozostać niejednoznaczne w produkcji.

### 32.1. Dwie definicje marży

**Decyzja:** używamy jawnych nazw `marża brutto` i `marża netto`.

### 32.2. Dwa modele podatku

**Decyzja:** Klarvido nie tworzy własnego uproszczonego silnika podatkowego jako źródła prawdy. Podatek pochodzi z dedykowanego, zweryfikowanego źródła albo jest oznaczoną estymacją.

### 32.3. Dwa znaczenia „dochodu”

**Decyzja:** używamy `wynik przed podatkiem` i `wynik netto`.

### 32.4. Różne koszty czerwca

**Decyzja:** każdy ekran bazuje na tych samych canonical aggregates; wyłączenia są możliwe wyłącznie jako jawny baseline/scenariusz.

### 32.5. Statyczne pola i pola przeliczane

**Decyzja:** pochodne wyliczamy centralnie i wersjonujemy.

### 32.6. SysTech vs CloudArch Backup

**Decyzja:** produkcyjnym źródłem jest dynamiczny detektor; statyczne przykłady nie mogą sterować decyzją.

### 32.7. Dane rynkowe

**Decyzja:** brak hardcoded benchmarków w produkcji.

### 32.8. Faktury vs główne sumy

**Decyzja:** KPI i wykresy korzystają z jednego canonical source / agregatów z dokumentów.

---

## 33. Out of scope — czego Klarvido nie może udawać

Klarvido w MVP nie jest:

- programem księgowym,
- systemem składania deklaracji podatkowych,
- źródłem prawnie wiążącej porady podatkowej,
- ERP,
- CRM,
- systemem kadrowym,
- magazynem,
- automatycznym doradcą inwestycyjnym,
- autonomicznym systemem podejmującym decyzje za właściciela.

Klarvido wspiera decyzję; użytkownik zachowuje kontrolę nad wykonaniem.

---

## 34. Najważniejszy rezultat biznesowy MVP

Sukces nie polega na tym, że użytkownik otwiera dużo wykresów.

MVP ma doprowadzić do momentu:

> **„Klarvido znalazło coś, czego nie zauważyłem, podpowiedziało mi sensowne działanie i później pokazało, czy to zadziałało.”**

To jest właściwy test tezy „AI CFO dla MŚP”.
