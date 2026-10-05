# Faktury z KSeF

Moduł `apps.invoices` i biblioteka `@sb/webapp-invoices` udostępniają faktury sprzedażowe i zakupowe w istniejącym interfejsie Klarvido. Dane ekranów, eksportów i AI pochodzą z lokalnej bazy; wyłącznie synchronizacja kontaktuje się z KSeF.

## Uruchomienie lokalne

1. Zainstaluj zależności (`pnpm install`) i uruchom backend (`pnpm saas backend up`). Po zmianie zależności Pythona przebuduj obraz backendu zgodnie z lokalną konfiguracją Compose.
2. Zastosuj migracje: `pnpm saas backend migrate`.
3. Uruchom backend, Redis, worker Celery, Beat i MCP. Po aktualizacji kodu lub operacji MCP: `docker compose restart celery_default celery_beat mcp-server`.
4. Uruchom frontend: `pnpm saas webapp up`.
5. Wybierz organizację z polskim NIP-em. W jej ustawieniach bezpieczeństwa zapisz istniejący token KSeF z uprawnieniem `InvoiceRead`, dla środowiska ustawionego przez `KSEF_ENVIRONMENT`.
6. Otwórz „Faktury”, wybierz 12 miesięcy, 6 miesięcy lub własną datę i kliknij rozpoczęcie importu. Samo wejście na ekran nie uruchamia pobierania.

Pierwszy zakres dotyczy daty trwałego zapisania dokumentu w KSeF; filtry tabeli dotyczą daty wystawienia. Synchronizacja po pierwszym uruchomieniu jest planowana co dwie godziny (Beat sprawdza terminy co pięć minut). Usunięcie tokenu zatrzymuje nowe pobrania i zachowuje faktury. Zmiana NIP-u lub środowiska wymaga nowego zakresu.

## Uprawnienia i dane

- `invoices.view`: lista, szczegóły, kontekst AI.
- `invoices.categorize`: kategorie.
- `invoices.export`: cały przefiltrowany zbiór CSV i oryginalny XML.
- `invoices.sync`: pierwszy import, rozszerzenie historii i synchronizacja ręczna.

Owner otrzymuje wszystkie uprawnienia; Admin domyślnie pierwsze trzy. Obsługa tokenu pozostaje pod istniejącymi uprawnieniami `security.ksef.*`. Wszystkie operacje wymagają `tenantId` i weryfikacji po stronie backendu.

Kwoty przechowujemy jako Decimal, podsumowania oddzielnie według waluty. Obsługiwane są FA(2), FA(3), korekty i odniesienia do dokumentów jeszcze niepobranych. XML jest chronionym źródłem w bazie; błędne dokumenty zachowujemy do ponowienia. Numer KSeF jest unikalny w organizacji i środowisku. Ponowny import zachowuje kategorię użytkownika. Backup obejmuje faktury, pozycje i kategorie; nie obejmuje zadań ani sesji. Odtworzenie faktur resetuje punkty kontynuacji, aby synchronizacja mogła uzupełnić brakujące dokumenty.

## Zapytaj Klarvido

Lista z filtrami, zaznaczone faktury i szczegóły mogą zostać dodane jako usuwalny kontekst rozmowy. Przeglądarka przesyła identyfikatory lub filtry, a backend odczytuje uprawnione dane i podsumowania. Narzędzia MCP `get_invoices`, `get_invoice`, `get_invoice_summary` są tylko do odczytu. Rozmowa z tym kontekstem nie zmienia kategorii ani nie uruchamia synchronizacji. Treść dokumentów jest danymi, nie instrukcjami; token i oryginalny XML nie trafiają do kontekstu. Zmiana organizacji czyści rozmowę i załączniki.

## Weryfikacja

```sh
docker compose exec -T backend pytest apps/invoices/tests apps/ksef/tests apps/backup/tests/test_restore.py -q --no-cov
pnpm nx run webapp-invoices:test --watchAll=false
pnpm nx run webapp-ai-assistant:test --watchAll=false
pnpm nx run webapp:type-check
pnpm nx run webapp:build
```

Weryfikacja tej gałęzi: 114 testów backendu oraz testy modułu Faktur, kontekstu AI i dashboardu. Testy KSeF korzystają z kontrolowanych odpowiedzi i zaszyfrowanych paczek; odpowiedzi modelu AI są mockowane. Pełny test na usłudze KSeF wymaga zapisania tokenu w lokalnej organizacji — lokalna baza podczas implementacji nie zawierała żadnego tokenu. Nie wykonano testu żywego KSeF ani żywego modelu AI.

Po dodaniu tokenu sprawdź import obu kierunków, listę, szczegóły, XML/CSV, kategoryzację i rozmowę ze źródłami. Następnie uruchom ponowną synchronizację i potwierdź brak duplikatów oraz zachowanie kategorii. Dokumenty dostępne wyłącznie przez podmiot trzeci lub upoważniony są poza zakresem tego etapu.
