# Webhook Delivery System

Niezawodny system do przyjmowania, kolejkowaania i dostarczania webhooków z wbudowanym mechanizmem ponowień (retry) oraz deduplikacją.

## 🛠 Wymagania
- **Docker** & **Docker Compose**
- **Python 3.x** (opcjonalnie, do prac developerskich)

## ⚙️ Konfiguracja

### Plik .env
Przed uruchomieniem należy przygotować plik ze zmiennymi środowiskowymi:
1. Przejdź do katalogu `src/`.
2. Utwórz plik `.env` na podstawie `env_template`.
3. Skopiuj zawartość szablonu i uzupełnij dane (hasła, dane dostępowe).

> **Uwaga:** Jeśli uruchamiasz aplikację wewnątrz Dockera, możesz pozostawić domyślne wartości z szablonu – kontenery są skonfigurowane tak, aby współpracować ze sobą bez dodatkowych zmian.

### Zaawansowana konfiguracja (`config.py`)
W pliku `config.py` (lub poprzez zmienne środowiskowe) możesz zarządzać kluczowymi parametrami systemu:

| Zmienna | Opis |
| :--- | :--- |
| `WORKER_ENABLED` | Włącza lub wyłącza proces workera. |
| `WORKER_CONCURRENCY` | Liczba webhooków przetwarzanych równolegle (liczba workerów). |
| `WORKER_RETRY_MAX` | Maksymalna liczba prób dostarczenia pojedynczego webhooka. |
| `WORKER_RETRY_DELAY` | Opóźnienie między kolejnymi próbami (w sekundach). |
| `DEDUPLICATION_WINDOW_SECONDS` | Czas (w sekundach), w którym identyczne webhooki są ignorowane. |


## Architektura

System składa się z kilku głównych elementów:

| Komponent | Odpowiedzialność |
| :--- | :--- |
| `API` | Przyjmuje żądania HTTP, waliduje dane wejściowe i zapisuje webhooki do bazy. |
| `MySQL` | Przechowuje webhooki, historię prób dostarczenia oraz wpisy deduplikacji. |
| `Worker` | Przetwarza webhooki w tle, wysyła żądania HTTP i obsługuje ponowienia. |
| `Deduplication` | Zapobiega wielokrotnemu przetwarzaniu identycznych webhooków w krótkim czasie. |

### Przepływ działania

1. Klient wysyła żądanie `POST /webhooks` z adresem docelowym oraz payloadem.
2. API waliduje dane i sprawdza, czy webhook nie jest duplikatem.
3. Jeśli webhook jest poprawny i nie jest duplikatem, zostaje zapisany w bazie ze statusem `PENDING`.
4. Worker pobiera oczekujące webhooki do przetworzenia.
5. Worker wysyła żądanie HTTP na wskazany URL.
6. Wynik próby zostaje zapisany w historii.
7. Jeśli dostarczenie się nie powiedzie, worker ponawia próbę zgodnie z konfiguracją `WORKER_RETRY_MAX` i `WORKER_RETRY_DELAY`.
8. Po udanym dostarczeniu webhook otrzymuje status `DELIVERED`.
9. Po przekroczeniu liczby prób webhook otrzymuje status `FAILED`.

### Kolejkowanie i worker

Webhooki nie są dostarczane bezpośrednio w trakcie obsługi requestu HTTP.  
API tylko przyjmuje zgłoszenie i zapisuje je do bazy, a właściwe dostarczenie wykonuje worker działający w tle.

Dzięki temu:
- odpowiedź API jest szybka,
- zadania w trakcie przetwarzania serwisu nie są tracone,
- po restarcie worker może kontynuować pracę,
- historia prób dostarczenia pozostaje zachowana.






## 🚀 Uruchomienie aplikacji

Aby zbudować i uruchomić cały system, wykonaj komendę:

```bash
docker compose up --build