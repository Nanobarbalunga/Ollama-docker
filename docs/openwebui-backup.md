# Backup di OpenWebUI

Lo script [script/openwebui-backup.py](../script/openwebui-backup.py) esegue un backup della directory persistente `/app/backend/data` del servizio `ollama-webui`.

Include SQLite (utenti, chat, impostazioni), upload, dati vettoriali locali ed eventuali cache presenti nel volume. **Non salva i modelli Ollama, ComfyUI, Automatic1111 o l'intero stack.** Per questi dati occorrono backup separati. Database PostgreSQL, database vettoriali remoti e storage esterni non sono coperti: le configurazioni remote riconosciute sono rifiutate prima dello stop.

## Requisiti

- Python 3.9+ su Linux, senza dipendenze Python aggiuntive.
- Docker Compose e accesso al daemon Docker con il proprio utente.
- Una sola istanza OpenWebUI avviata, con mount persistente su `/app/backend/data` e SQLite locale `webui.db` (oppure un percorso SQLite sotto la stessa directory).
- Destinazione già esistente e scrivibile, esterna ai mount del container; verificare che il disco sia effettivamente montato.
- Filesystem con supporto a `posix_fallocate`. ZIP usa Python; 7z richiede `7zz` oppure `7z` installato sull'host.
- Nessun altro processo o istanza deve scrivere nel volume durante il backup. Non avviare aggiornamenti in parallelo.

Il backup contiene dati personali, credenziali e chiavi eventualmente presenti in SQLite o nel `.env`. I file sono creati con permessi riservati; **non sono cifrati**. Segreti forniti tramite altri file, Docker secrets o variabili della shell vanno conservati separatamente.

## Uso rapido

Eseguire dalla root di `Ollama-docker`. I file predefiniti sono `docker-compose-ollama-nvidia.yaml` e `docker-compose.ssl.override.yaml`.

Creare la destinazione e verificare soltanto la stima:

```bash
mkdir -p "/mnt/backup/openwebui"
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -e
```

Backup con timestamp di avvio e ZIP bilanciato:

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t -a zip -p balanced
```

Backup senza seconda copia compressa:

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t
```

7z con compressione massima:

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t -a 7z -p max
```

Il nome predefinito è `openwebui`; con `-t` diventa `openwebui_YYYYMMDD_HHMMSS_microsecondi`, usando l'istante di avvio e l'ora locale dell'host. Nomi già esistenti non vengono sovrascritti.

## Parametri

| Breve | Lungo | Significato |
| --- | --- | --- |
| `-h` | `--help` | Guida con esempi; funziona senza Docker |
| `-P` | `--project-dir` | Root del progetto, default directory corrente |
| `-f` | `--file` | File Compose in ordine, ripetibile; sostituisce i default |
| `-s` | `--service` | Servizio, default `ollama-webui` |
| `-m` | `--margin-percent` | Margine TAR, default 20% |
| `-M` | `--min-free-gib` | Riserva libera in GiB, default 1 |
| `-a` | `--archive` | `none` (default), `zip`, `7z` |
| `-p` | `--preset` | `fast`, `balanced` (default), `max` |
| `-e` | `--estimate` | Solo stima; nessuno stop né preallocazione |
| `-t` | `--timestamp` | Aggiunge timestamp di avvio al nome |

Le iniziali duplicate usano maiuscole: `-P` per il progetto, `-p` per il preset; `-M` per la riserva, `-m` per il margine. Senza argomenti lo script rimanda a `-h` e termina con codice 2.

I preset corrispondono ai livelli 1, 5 e 9. ZIP usa Deflate, 7z usa LZMA2. Il preset massimo può richiedere più CPU, tempo e RAM, senza garantire risparmi su dati già compressi.

### CPU/AMD o assenza dell'override SSL

CPU senza override (il file CPU della repository si chiama `docker-compose.yml`):

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t -f docker-compose.yml
```

AMD con SSL:

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t -f docker-compose-ollama-amd.yaml -f docker-compose.ssl.override.yaml
```

NVIDIA senza SSL:

```bash
python3 script/openwebui-backup.py "/mnt/backup/openwebui" -t -f docker-compose-ollama-nvidia.yaml
```

Da una directory diversa specificare anche `-P /percorso/Ollama-docker`. Conservare i file Compose e il nome progetto effettivamente usati dal proprio stack.

## Procedura e occupazione disco

1. Verifica il servizio avviato, il mount persistente, SQLite e i backend locali.
2. Stima dati e overhead TAR; controlla la riserva libera e lo spazio aggiuntivo per la compressione.
3. Prealloca realmente il TAR e copia `.env` e definizioni Compose nella cartella di backup.
4. Ferma **solo OpenWebUI** e copia l'intera directory dati tramite Docker. SQLite e gli eventuali file WAL/SHM vengono salvati insieme, con il servizio fermo.
5. Controlla la struttura TAR e l'header del database SQLite, quindi tenta il riavvio del servizio. Il controllo di container avviato non equivale a un test funzionale dell'applicazione.
6. Scrive manifest, checksum e indicatore di successo.
7. Se richiesto, comprime e verifica l'archivio dopo il riavvio di OpenWebUI.

Ollama, i modelli e gli altri container restano avviati. Caddy può mostrare un errore temporaneo mentre il backend è fermo.

Il controllo spazio non presume alcuna riduzione dovuta alla compressione. La cartella originale rimane **sempre**: per ZIP/7z occorre spazio per entrambe le copie. Per ridurre la preallocazione prudenziale si può usare, per esempio, `-m 5`; ciò non riduce i dati salvati. Se la copia supera la stima, il TAR viene esteso solo dopo un nuovo controllo dello spazio.

ZIP viene preallocato e verificato tramite CRC. Il programma 7-Zip gestisce direttamente l'allocazione del proprio file: lo script controlla lo spazio prima e durante, poi esegue `7z t`. Quote, scritture concorrenti, compressione e copy-on-write del filesystem possono comunque causare errori di spazio: i controlli non sono una garanzia assoluta.

## Output e verifica

La cartella completata contiene:

- `openwebui-data.tar`, con metadati dei file originali e directory dati completa;
- `configuration/`, con copie numerate dei file Compose del progetto e del `.env`;
- `manifest.json`, con immagine, image ID, versione se disponibile, percorso SQLite, dimensioni e hash;
- `SHA256SUMS`;
- `SUCCESS`.

L'archivio compresso aggiuntivo ha suffisso `.zip` o `.7z` ed è accompagnato dal file `.sha256`.

Dalla cartella del backup verificare:

```bash
sha256sum -c SHA256SUMS
```

Per l'archivio eseguire `sha256sum -c NOME_ARCHIVIO.zip.sha256` (o `.7z.sha256`) dalla directory che lo contiene.

Una cartella o un archivio `.partial` è incompleto. Se fallisce solo la compressione, la cartella originale già completata viene conservata. Non vengono eliminati backup precedenti. La verifica TAR/header/CRC/checksum **non sostituisce una prova di ripristino**, né certifica l'integrità logica di ogni database incluso.

## Errori e recupero

Lo script tenta di riavviare OpenWebUI anche se falliscono copia, verifica o stop parziale. Ctrl+C e SIGTERM attivano il recupero; SIGKILL e perdita di alimentazione no.

Se il recupero fallisce, controllare lo stato e riavviare dalla root del progetto con gli stessi Compose:

```bash
docker compose -f docker-compose-ollama-nvidia.yaml -f docker-compose.ssl.override.yaml start ollama-webui
docker compose -f docker-compose-ollama-nvidia.yaml -f docker-compose.ssl.override.yaml logs --tail 100 ollama-webui
```

Adattare i file per CPU/AMD. Prima di un ripristino fermare OpenWebUI, conservare l'attuale directory dati, usare l'immagine/versione annotata nel manifest e recuperare i file dal TAR preservando i metadati. Verificare prima su un'istanza separata: le migrazioni di un aggiornamento non vengono annullate cambiando soltanto immagine.

## Riferimenti

- [OpenWebUI: backup](https://docs.openwebui.com/tutorials/maintenance/backups/)
- [OpenWebUI: database SQLite ed esterni](https://docs.openwebui.com/tutorials/maintenance/database/)
- [OpenWebUI: aggiornamenti e migrazioni](https://docs.openwebui.com/getting-started/updating/)
