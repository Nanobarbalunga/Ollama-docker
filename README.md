# Ollama Docker Compose Setup

## Getting Started

### Prerequisites

Assicurati di avere installato :

- Docker > 3.7

#### GPU Support NVIDIA (Optional)

Se vuoi usare la gpu per migliorare le prestazioni devi prima installare NVIDIA Container Toolkit:

##### Su Debian

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure NVIDIA Container Toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Test GPU integration
docker run --gpus all nvidia/cuda:11.5.2-base-ubuntu20.04 nvidia-smi
```

##### Su Fedora

```bash
# Aggiungi il repository NVIDIA Container Toolkit
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo

# Aggiorna i metadati
sudo dnf makecache

# Installa il toolkit
sudo dnf install -y nvidia-container-toolkit

# Configura docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verifica se ha eseguito tutto
cat /etc/docker/daemon.json

# Test GPU integration
docker run --gpus all nvidia/cuda:11.5.2-base-ubuntu20.04 nvidia-smi
```

#### GPU Support AMD / ROCm (Optional)

Per usare una GPU AMD con Ollama in Docker devi usare un host Linux, oppure Docker Desktop con backend WSL2 che esponga i device Linux al container.

Prerequisiti:

- driver AMD / stack ROCm funzionante sull'host
- disponibilita' dei device `/dev/kfd` e `/dev/dri` nel runtime Docker

Nota: questa configurazione non e' pensata per Docker su Windows "puro" senza device Linux esposti al container.

### Configuration

1. Clone la repository:

    ```bash
    git clone https://github.com/Nanobarbalunga/ollama-docker
    ```

2. Cambia la directory:

    ```bash
    cd ollama-docker
    ```

## Usage

Per cominciare:

Se vuoi usare la GPU NVIDIA

```bash
docker compose -f docker-compose-ollama-nvidia.yaml up -d
```

Se vuoi usare la GPU AMD / ROCm

```bash
docker compose -f docker-compose-ollama-amd.yaml up -d
```

Se vuoi usare solo la CPU

```bash
docker compose up -d
```

Per aprire Ollama-webui [http://localhost:8080](http://localhost:8080) nel tuo browser.

### Generazione immagini: ComfyUI o Automatic1111

Entrambi i backend sono disabilitati di default e possono essere collegati a
Open WebUI. Scegline uno in base al tipo di utilizzo e alle risorse disponibili.

| Caratteristica | ComfyUI | Automatic1111 |
| --- | --- | --- |
| Approccio | Workflow visuale a nodi, molto flessibile | Interfaccia tradizionale a schede e parametri |
| Facilita' iniziale | Richiede di comprendere o importare un workflow | Generalmente piu' immediato per `txt2img` e `img2img` |
| Modelli e flussi complessi | Indicato per pipeline avanzate, riutilizzabili e modelli recenti | Indicato per flussi Stable Diffusion classici e il suo ampio ecosistema di estensioni |
| Uso della memoria | In genere gestisce meglio workflow complessi e sistemi con VRAM limitata | Puo' richiedere flag come `--medvram` o `--lowvram` su GPU piccole |
| Integrazione Open WebUI | Richiede un workflow API compatibile | Usa direttamente l'API `txt2img`/`img2img`, abilitata qui con `--api` |
| CPU | Supportata, ma molto lenta | Supportata con flag dedicati, ma non raccomandata |

Per entrambi e' fortemente consigliata una GPU NVIDIA. Come indicazione
generale, Stable Diffusion 1.5 puo' essere usato con circa 4-6 GB di VRAM,
mentre SDXL e workflow piu' complessi richiedono normalmente almeno 8-12 GB.
Il consumo effettivo dipende da modello, risoluzione, batch, precisione,
ControlNet e altri nodi o estensioni. Con sola CPU servono molta RAM, spazio su
disco per i modelli e tempi di generazione nettamente superiori.

Scegli **ComfyUI** se vuoi massimo controllo, workflow riproducibili o prevedi
di usare pipeline avanzate. Scegli **Automatic1111** se preferisci una UI
classica, una configurazione iniziale piu' semplice e workflow Stable Diffusion
tradizionali.

#### Abilitare ComfyUI

```dotenv
COMPOSE_PROFILES=images
OPEN_WEBUI_ENABLE_IMAGE_GENERATION=True
OPEN_WEBUI_IMAGE_GENERATION_ENGINE=comfyui
```

Open WebUI usa `http://comfyui:8188`; la UI locale e' disponibile su
[http://localhost:8188](http://localhost:8188).
Per proteggere l'interfaccia consulta
[Appendice B - Autenticazione web dei backend immagini](#appendice-b-autenticazione-backend-immagini).

#### Abilitare Automatic1111

```dotenv
COMPOSE_PROFILES=automatic1111
OPEN_WEBUI_ENABLE_IMAGE_GENERATION=True
OPEN_WEBUI_IMAGE_GENERATION_ENGINE=automatic1111
```

Open WebUI usa `http://automatic1111:7860`; la UI locale e' disponibile su
[http://localhost:7860](http://localhost:7860). Il flag `--api` e' gia'
presente nei valori predefiniti. Automatic1111 viene avviato esplicitamente
con:

```text
--listen --api --port 7860
```

Il bind predefinito `AUTOMATIC1111_HOST_BIND=0.0.0.0` rende l'interfaccia
raggiungibile anche dagli altri dispositivi della LAN:

```text
http://IP-DEL-SERVER:7860
```

Se il server ha un indirizzo LAN statico, puoi limitare l'ascolto a
quell'indirizzo:

```dotenv
AUTOMATIC1111_HOST_BIND=192.168.1.50
```

Poiche' `AUTOMATIC1111_WEB_ENABLE_AUTH=false` per default, non pubblicare la
porta `7860` direttamente su Internet. Limita l'accesso tramite firewall alla
rete locale oppure abilita un sistema di autenticazione.
La configurazione completa e' descritta in
[Appendice B - Autenticazione web dei backend immagini](#appendice-b-autenticazione-backend-immagini).

Dopo avere scelto il backend, avvia normalmente lo stack:

```bash
# CPU: anche il backend immagini usa la CPU
docker compose up -d

# NVIDIA: anche il backend immagini usa la GPU NVIDIA
docker compose -f docker-compose-ollama-nvidia.yaml up -d

# AMD/ROCm: Ollama usa ROCm, il backend immagini usa la CPU
docker compose -f docker-compose-ollama-amd.yaml up -d
```

I Compose dedicati possono essere usati anche separatamente:

```bash
docker compose -f docker-compose-comfyui.yaml --profile images up -d
docker compose -f docker-compose-comfyui-nvidia.yaml --profile images up -d
docker compose -f docker-compose-automatic1111.yaml --profile automatic1111 up -d
docker compose -f docker-compose-automatic1111-nvidia.yaml --profile automatic1111 up -d
```

Le immagini AI-Dock non includono checkpoint. Al primo avvio aggiungi almeno un
modello nella directory persistente `./comfyui` oppure `./automatic1111`, poi
seleziona il modello nelle impostazioni del backend e in **Admin Settings >
Images** di Open WebUI. ComfyUI puo' richiedere anche un workflow esportato nel
formato API.

Per disabilitare la generazione immagini:

```dotenv
COMPOSE_PROFILES=
OPEN_WEBUI_ENABLE_IMAGE_GENERATION=False
```

In alternativa puoi usare gli script gia' pronti nella root del progetto. Scegli quelli PowerShell se lavori da Windows/PowerShell, oppure quelli Bash se lavori da WSL2 o Linux.

| Ambiente | CPU | NVIDIA | AMD / ROCm | Stop CPU | Stop NVIDIA | Stop AMD / ROCm |
| --- | --- | --- | --- | --- | --- | --- |
| PowerShell | `.\start-default.ps1` | `.\start-nvidia.ps1` | `.\start-amd.ps1` | `.\stop-default.ps1` | `.\stop-nvidia.ps1` | `.\stop-amd.ps1` |
| WSL2 / Linux | `bash start-default.sh` | `bash start-nvidia.sh` | `bash start-amd.sh` | `bash stop-default.sh` | `bash stop-nvidia.sh` | `bash stop-amd.sh` |


### Use ollama from command line interface

Per entrare nella cli

```bash
docker exec -it ollama bash 
```

Per approfondire i comandi segui l'appendice :

- [Appendice A — Guida all'utilizzo della CLI di Ollama](#appendice-e-cli-ollama)


### Model Installation

Per installare un modello da openWebUi andare su Impostazioni=>Modello=>Gestione e selezionare il modello desiderato.

## Stop and Cleanup

Per fermare e pulire le risorse utilizzate, eseguire:

```bash
docker compose down
```

## Environment variables

I file `docker-compose*.yaml` leggono automaticamente un file `.env` nella root del progetto. Puoi partire dall'esempio:

```bash
cp .env.example .env
```

Poi modifica solo i valori che ti servono. Se una variabile non e' presente nel `.env`, Docker Compose usa il valore di default gia' definito nei file compose con la forma `${VAR:-default}`.

Esempi:

```bash
# CPU
docker compose up -d

# NVIDIA
docker compose -f docker-compose-ollama-nvidia.yaml up -d

# AMD / ROCm
docker compose -f docker-compose-ollama-amd.yaml up -d
```

### Env quick reference

| Variabile | Default | Profilo | Dettagli |
| --- | --- | --- | --- |
| `OLLAMA_CONTAINER_NAME` | `ollama` | Tutti | [Descrizione](#ollama_container_name) |
| `OPEN_WEBUI_CONTAINER_NAME` | `ollama-webui` | Tutti | [Descrizione](#open_webui_container_name) |
| `OLLAMA_PULL_POLICY` | `always` | Tutti | [Descrizione](#ollama_pull_policy) |
| `OLLAMA_CPU_RESTART_POLICY` | `always` | CPU | [Descrizione](#ollama_cpu_restart_policy) |
| `OLLAMA_GPU_RESTART_POLICY` | `unless-stopped` | NVIDIA, AMD | [Descrizione](#ollama_gpu_restart_policy) |
| `OPEN_WEBUI_RESTART_POLICY` | `unless-stopped` | Tutti | [Descrizione](#open_webui_restart_policy) |
| `OLLAMA_IMAGE` | `ollama/ollama:latest` | CPU | [Descrizione](#ollama_image) |
| `OPEN_WEBUI_CPU_IMAGE` | `ghcr.io/open-webui/open-webui:main` | CPU | [Descrizione](#open_webui_cpu_image) |
| `OLLAMA_NVIDIA_IMAGE` | `ollama/ollama:latest` | NVIDIA | [Descrizione](#ollama_nvidia_image) |
| `OLLAMA_AMD_IMAGE` | `ollama/ollama:rocm` | AMD | [Descrizione](#ollama_amd_image) |
| `OPEN_WEBUI_GPU_IMAGE` | `ghcr.io/open-webui/open-webui:latest` | NVIDIA, AMD | [Descrizione](#open_webui_gpu_image) |
| `OLLAMA_PORT` | `7869` | Tutti | [Descrizione](#ollama_port) |
| `OPEN_WEBUI_PORT` | `8080` | Tutti | [Descrizione](#open_webui_port) |
| `PROJECT_CODE_PATH` | `.` | CPU | [Descrizione](#project_code_path) |
| `OLLAMA_DATA_PATH` | `./ollama/ollama` | Tutti | [Descrizione](#ollama_data_path) |
| `OPEN_WEBUI_DATA_PATH` | `./ollama/ollama-webui` | Tutti | [Descrizione](#open_webui_data_path) |
| `OPEN_WEBUI_HOST_GATEWAY` | `host.docker.internal:host-gateway` | Tutti | [Descrizione](#open_webui_host_gateway) |
| `OLLAMA_HOST` | `0.0.0.0` | Tutti | [Descrizione](#ollama_host) |
| `OLLAMA_KEEP_ALIVE` | `15m` | Tutti | [Descrizione](#ollama_keep_alive) |
| `OLLAMA_OPTS` | `--offload cpu` | NVIDIA | [Descrizione](#ollama_opts) |
| `OLLAMA_MODELS` | `/root/.ollama/models` | Opzionale | [Descrizione](#ollama_models) |
| `OLLAMA_NUM_PARALLEL` | `1` | Opzionale | [Descrizione](#ollama_num_parallel) |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Opzionale | [Descrizione](#ollama_max_loaded_models) |
| `OLLAMA_LOAD_TIMEOUT` | `5m` | Opzionale | [Descrizione](#ollama_load_timeout) |
| `OLLAMA_MAX_QUEUE` | `512` | Opzionale | [Descrizione](#ollama_max_queue) |
| `OLLAMA_FLASH_ATTENTION` | `0` | Tutti | [Descrizione](#ollama_flash_attention) |
| `OLLAMA_KV_CACHE_TYPE` | `f16` | Tutti | [Descrizione](#ollama_kv_cache_type) |
| `OPEN_WEBUI_OLLAMA_BASE_URLS` | `http://host.docker.internal:7869` | Tutti | [Descrizione](#open_webui_ollama_base_urls) |
| `OPEN_WEBUI_ENV` | `dev` | Tutti | [Descrizione](#open_webui_env) |
| `OPEN_WEBUI_AUTH` | `False` | Tutti | [Descrizione](#open_webui_auth) |
| `OPEN_WEBUI_NAME` | `OpenWebUi` | Tutti | [Descrizione](#open_webui_name) |
| `OPEN_WEBUI_URL` | `http://localhost:8080` | Tutti | [Descrizione](#open_webui_url) |
| `OPEN_WEBUI_SECRET_KEY` | `t0p-s3cr3t` | Tutti | [Descrizione](#open_webui_secret_key) |
| `OPEN_WEBUI_ENABLE_OLLAMA_API` | `True` | Opzionale | [Descrizione](#open_webui_enable_ollama_api) |
| `OPEN_WEBUI_OLLAMA_BASE_URL` | `http://host.docker.internal:7869` | Opzionale | [Descrizione](#open_webui_ollama_base_url) |
| `OPEN_WEBUI_DEFAULT_MODELS` | vuoto | Opzionale | [Descrizione](#open_webui_default_models) |
| `OPEN_WEBUI_ENABLE_OPENAI_API` | `True` | Opzionale | [Descrizione](#open_webui_enable_openai_api) |
| `OPEN_WEBUI_OPENAI_API_BASE_URL` | `https://api.openai.com/v1` | Opzionale | [Descrizione](#open_webui_openai_api_base_url) |
| `OPEN_WEBUI_OPENAI_API_KEY` | vuoto | Opzionale | [Descrizione](#open_webui_openai_api_key) |
| `AUTOMATIC1111_WEB_ENABLE_AUTH` | `false` | Automatic1111 | [Descrizione](#automatic1111_web_enable_auth) |
| `AUTOMATIC1111_WEB_USER` | `user` | Automatic1111 | [Descrizione](#automatic1111_web_user) |
| `AUTOMATIC1111_WEB_PASSWORD` | `password` | Automatic1111 | [Descrizione](#automatic1111_web_password) |
| `AUTOMATIC1111_WEB_PASSWORD_HASH` | vuoto | Automatic1111 | [Descrizione](#automatic1111_web_password_hash) |
| `COMFYUI_WEB_ENABLE_AUTH` | `false` | ComfyUI | [Descrizione](#comfyui_web_enable_auth) |
| `COMFYUI_WEB_USER` | `user` | ComfyUI | [Descrizione](#comfyui_web_user) |
| `COMFYUI_WEB_PASSWORD` | `password` | ComfyUI | [Descrizione](#comfyui_web_password) |
| `COMFYUI_WEB_PASSWORD_HASH` | vuoto | ComfyUI | [Descrizione](#comfyui_web_password_hash) |
| `NVIDIA_VISIBLE_DEVICES` | `all` | NVIDIA | [Descrizione](#nvidia_visible_devices) |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | NVIDIA | [Descrizione](#nvidia_driver_capabilities) |
| `NVIDIA_GPU_COUNT` | `1` | NVIDIA | [Descrizione](#nvidia_gpu_count) |
| `NVIDIA_GPU_DEVICE_ID` | `0` | NVIDIA opzionale | [Descrizione](#nvidia_gpu_device_id) |
| `AMD_KFD_DEVICE` | `/dev/kfd` | AMD | [Descrizione](#amd_kfd_device) |
| `AMD_DRI_DEVICE` | `/dev/dri` | AMD | [Descrizione](#amd_dri_device) |
| `AMD_VIDEO_GROUP` | `video` | AMD | [Descrizione](#amd_video_group) |
| `AMD_RENDER_GROUP` | `render` | AMD | [Descrizione](#amd_render_group) |
| `AMD_HIP_VISIBLE_DEVICES` | `0` | AMD | [Descrizione](#amd_hip_visible_devices) |
| `AMD_ROCR_VISIBLE_DEVICES` | `0` | AMD | [Descrizione](#amd_rocr_visible_devices) |
| `AMD_HSA_OVERRIDE_GFX_VERSION` | `10.3.0` | AMD opzionale | [Descrizione](#amd_hsa_override_gfx_version) |

### Env details

#### `OLLAMA_CONTAINER_NAME`

Nome del container Ollama. Cambialo solo se hai piu' stack simili sullo stesso host o vuoi evitare conflitti con container gia' esistenti.

#### `OPEN_WEBUI_CONTAINER_NAME`

Nome del container Open WebUI. Utile quando vuoi avviare piu' istanze separate o rendere i nomi container piu' espliciti.

#### `OLLAMA_PULL_POLICY`

Controlla quando Docker deve scaricare l'immagine Ollama. `always` mantiene l'immagine aggiornata a ogni avvio; usa valori piu' conservativi se vuoi evitare aggiornamenti automatici.

#### `OLLAMA_CPU_RESTART_POLICY`

Policy di restart per Ollama nel compose CPU. Il default `always` replica il comportamento attuale del file principale.

#### `OLLAMA_GPU_RESTART_POLICY`

Policy di restart per Ollama nei compose NVIDIA e AMD. `unless-stopped` riavvia il servizio salvo stop manuale.

#### `OPEN_WEBUI_RESTART_POLICY`

Policy di restart per Open WebUI. In genere `unless-stopped` e' adatto per un servizio locale persistente.

#### `OLLAMA_IMAGE`

Immagine usata dal profilo CPU. Usa `ollama/ollama:latest` per la versione standard senza configurazioni GPU dedicate.

#### `OPEN_WEBUI_CPU_IMAGE`

Immagine Open WebUI usata dal compose CPU. Il default resta `ghcr.io/open-webui/open-webui:main`, come nel file originale.

#### `OLLAMA_NVIDIA_IMAGE`

Immagine Ollama usata con GPU NVIDIA. La gestione della GPU arriva dal runtime NVIDIA e dalla sezione `deploy.resources.reservations.devices`.

#### `OLLAMA_AMD_IMAGE`

Immagine Ollama per AMD/ROCm. Deve usare un tag ROCm, per esempio `ollama/ollama:rocm`, per avere il supporto AMD corretto.

#### `OPEN_WEBUI_GPU_IMAGE`

Immagine Open WebUI usata dai profili GPU. Il default e' `latest`, come nei compose NVIDIA e AMD originali.

#### `OLLAMA_PORT`

Porta esposta sull'host per l'API Ollama. Il container resta sulla porta `11434`; il default espone `7869:11434`.

#### `OPEN_WEBUI_PORT`

Porta esposta sull'host per l'interfaccia web. Il container resta sulla porta `8080`; il default espone `8080:8080`.

#### `PROJECT_CODE_PATH`

Path montato in `/code` nel compose CPU. Di solito puoi lasciarlo a `.`, oppure rimuovere/ignorare il mount se non ti serve dentro al container.

#### `OLLAMA_DATA_PATH`

Cartella locale dove Ollama salva modelli e dati persistenti. Cambiala se vuoi spostare i modelli su un disco piu' grande.

#### `OPEN_WEBUI_DATA_PATH`

Cartella locale dove Open WebUI salva database, impostazioni e dati applicativi. Va mantenuta persistente per non perdere configurazioni e utenti.

#### `OPEN_WEBUI_HOST_GATEWAY`

Entry `extra_hosts` che permette a Open WebUI di raggiungere servizi esposti dall'host tramite `host.docker.internal`.

#### `OLLAMA_HOST`

Indirizzo su cui Ollama ascolta dentro il container. `0.0.0.0` permette l'accesso dagli altri container e dal port mapping Docker.

#### `OLLAMA_KEEP_ALIVE`

Tempo per cui un modello resta caricato dopo l'ultima richiesta. Aumentalo per risposte successive piu' rapide; riducilo per liberare RAM/VRAM prima.

#### `OLLAMA_OPTS`

Opzioni aggiuntive per Ollama nel profilo NVIDIA. Lascia il default se vuoi mantenere il comportamento attuale; modificalo solo se sai quale flag Ollama vuoi passare.

#### `OLLAMA_MODELS`

Path interno in cui Ollama cerca i modelli. Usalo se cambi la destinazione del volume o vuoi separare i modelli da altri dati.

#### `OLLAMA_NUM_PARALLEL`

Numero di richieste parallele gestite per modello. Aumentarlo puo' migliorare throughput, ma richiede piu' memoria.

#### `OLLAMA_MAX_LOADED_MODELS`

Numero massimo di modelli tenuti caricati contemporaneamente. Utile su macchine con molta RAM/VRAM o con workflow multi-modello.

#### `OLLAMA_LOAD_TIMEOUT`

Tempo massimo concesso al caricamento di un modello. Aumentalo per modelli grandi su dischi lenti o sistemi con poca memoria.

#### `OLLAMA_MAX_QUEUE`

Numero massimo di richieste in coda. Utile per limitare il carico quando piu' client usano la stessa istanza.

#### `OLLAMA_FLASH_ATTENTION`

Abilita (`1`) o disabilita (`0`) Flash Attention. Ollama la usa
automaticamente quando backend e dispositivo la supportano; impostare `1` ne
forza l'attivazione. La quantizzazione della cache KV con `q8_0` o `q4_0`
richiede Flash Attention.

#### `OLLAMA_KV_CACHE_TYPE`

Imposta globalmente il tipo di quantizzazione della cache K/V per tutti i
modelli caricati da Ollama.

| Valore | Memoria indicativa | Precisione | Utilizzo consigliato |
| --- | --- | --- | --- |
| `f16` | 100% | Massima | Default; da preferire quando RAM o VRAM sono sufficienti |
| `q8_0` | Circa 50% di `f16` | Perdita molto piccola, normalmente non percepibile | Miglior compromesso quando si vuole ridurre la memoria |
| `q4_0` | Circa 25% di `f16` | Perdita piccola o media, piu' evidente con contesti lunghi | Sistemi con memoria molto limitata |

Per usare una cache quantizzata nel file `.env`:

```dotenv
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
```

L'impatto sulla qualita' dipende dal modello e dal task. I modelli con un alto
numero di gruppi GQA, per esempio Qwen2, possono perdere piu' precisione con la
quantizzazione. Dopo una modifica e' necessario ricreare o riavviare il
container Ollama.

#### `OPEN_WEBUI_OLLAMA_BASE_URLS`

Lista degli endpoint Ollama usati da Open WebUI, separati da punto e virgola. Nel setup locale punta a `http://host.docker.internal:7869`.

#### `OPEN_WEBUI_ENV`

Ambiente applicativo di Open WebUI. Il default `dev` replica la configurazione attuale del progetto.

#### `OPEN_WEBUI_AUTH`

Abilita o disabilita autenticazione in Open WebUI. `False` e' comodo in locale; per reti condivise o ambienti esposti usa autenticazione attiva.

#### `OPEN_WEBUI_NAME`

Nome mostrato nell'interfaccia Open WebUI. Cambialo se vuoi distinguere istanze diverse.

#### `OPEN_WEBUI_URL`

URL pubblico con cui raggiungi Open WebUI. E' importante se usi funzionalita' che generano link, OAuth o integrazioni esterne.

#### `OPEN_WEBUI_SECRET_KEY`

Chiave segreta usata da Open WebUI. Cambiala in qualunque ambiente non puramente locale e mantienila stabile tra i riavvii.

#### `OPEN_WEBUI_ENABLE_OLLAMA_API`

Abilita l'integrazione Ollama in Open WebUI. Disattivala solo se vuoi usare Open WebUI esclusivamente con altri provider.

#### `OPEN_WEBUI_OLLAMA_BASE_URL`

Endpoint Ollama singolo. Usa questa variabile se non ti serve la lista multipla `OPEN_WEBUI_OLLAMA_BASE_URLS`.

#### `OPEN_WEBUI_DEFAULT_MODELS`

Modelli predefiniti mostrati o selezionati in Open WebUI. Utile per standardizzare l'esperienza degli utenti.

#### `OPEN_WEBUI_ENABLE_OPENAI_API`

Abilita l'integrazione OpenAI-compatible in Open WebUI. Lasciala attiva se usi provider compatibili con API OpenAI.

#### `OPEN_WEBUI_OPENAI_API_BASE_URL`

Base URL per API OpenAI-compatible. Cambiala per usare proxy, gateway locali o provider alternativi.

#### `OPEN_WEBUI_OPENAI_API_KEY`

Chiave API per OpenAI o provider compatibili. Non committare mai un `.env` reale contenente questa chiave.

#### `AUTOMATIC1111_WEB_ENABLE_AUTH`

Abilita (`true`) o disabilita (`false`) l'autenticazione HTTP Basic fornita da
AI-Dock davanti all'interfaccia Automatic1111. Il default e' `false`; abilitala
quando la porta `7860` e' accessibile da una rete condivisa. Vedi
[Appendice B.1](#b1-automatic1111).

#### `AUTOMATIC1111_WEB_USER`

Nome utente richiesto per accedere all'interfaccia web Automatic1111 quando
l'autenticazione e' attiva. Il valore predefinito `user` deve essere sostituito
prima di esporre il servizio.

#### `AUTOMATIC1111_WEB_PASSWORD`

Password in chiaro per l'autenticazione web Automatic1111. Il default
`password` non e' sicuro: inserisci la password reale esclusivamente nel file
`.env` e non versionarla.

#### `AUTOMATIC1111_WEB_PASSWORD_HASH`

Hash bcrypt alternativo alla password in chiaro. Quando lo utilizzi, lascia
`AUTOMATIC1111_WEB_PASSWORD` vuota e racchiudi l'hash tra apici singoli nel
file `.env`, affinche' Docker Compose non interpreti i caratteri `$`.

#### `COMFYUI_WEB_ENABLE_AUTH`

Abilita (`true`) o disabilita (`false`) l'autenticazione HTTP Basic AI-Dock
per ComfyUI. Puo' impedire a Open WebUI di raggiungere direttamente l'API:
per questa integrazione e' normalmente preferibile lasciarla disabilitata e
limitare l'esposizione della porta. Vedi [Appendice B.2](#b2-comfyui).

#### `COMFYUI_WEB_USER`

Nome utente richiesto per accedere all'interfaccia web ComfyUI quando
l'autenticazione e' abilitata. Sostituisci il valore predefinito `user` negli
ambienti condivisi.

#### `COMFYUI_WEB_PASSWORD`

Password in chiaro usata dall'autenticazione web ComfyUI. Non usare il default
`password` in una rete condivisa e conserva il valore reale solamente nel file
`.env`.

#### `COMFYUI_WEB_PASSWORD_HASH`

Hash bcrypt utilizzabile al posto di `COMFYUI_WEB_PASSWORD`. Lascia vuota la
password in chiaro e racchiudi l'hash tra apici singoli nel `.env` per
preservare letteralmente i caratteri `$`.

#### `NVIDIA_VISIBLE_DEVICES`

Seleziona quali GPU NVIDIA rendere visibili al container. `all` espone tutte; usa un ID specifico per limitare il container a una GPU.

#### `NVIDIA_DRIVER_CAPABILITIES`

Capacita' driver NVIDIA richieste dal container. `compute,utility` e' adatto per inferenza e strumenti come `nvidia-smi`.

#### `NVIDIA_GPU_COUNT`

Numero di GPU richieste a Docker Compose per il servizio Ollama. Aumentalo solo se l'host ha piu' GPU disponibili e vuoi assegnarle al container.

#### `NVIDIA_GPU_DEVICE_ID`

ID di una GPU NVIDIA specifica. Nel compose e' commentato perche' in genere si usa `count`; abilitalo quando vuoi pinning esplicito su una GPU.

#### `AMD_KFD_DEVICE`

Device ROCm `/dev/kfd` esposto al container. E' necessario per usare GPU AMD con ROCm.

#### `AMD_DRI_DEVICE`

Device DRI esposto al container, normalmente `/dev/dri`. Serve a rendere disponibili le GPU/render node AMD.

#### `AMD_VIDEO_GROUP`

Gruppo Linux aggiunto al container per accedere ai device video. Di solito e' `video`.

#### `AMD_RENDER_GROUP`

Gruppo Linux aggiunto al container per accedere ai render node. Di solito e' `render`.

#### `AMD_HIP_VISIBLE_DEVICES`

Seleziona quali GPU HIP rendere visibili. Usa `0` per la prima GPU, oppure cambia valore su host multi-GPU.

#### `AMD_ROCR_VISIBLE_DEVICES`

Seleziona quali GPU ROCr rendere visibili. In genere deve restare coerente con `AMD_HIP_VISIBLE_DEVICES`.

#### `AMD_HSA_OVERRIDE_GFX_VERSION`

Override dell'architettura GPU ROCm. Usalo solo per GPU AMD che ne hanno bisogno e dopo aver verificato il valore corretto per il tuo hardware.

---

# Installazione di un modello da Ollama (es. qwen2.5-coder:1.5b)

Per installare un modello specifico con Ollama, puoi eseguire i seguenti passaggi:

1. **Scarica il Modello**:
   Assicurati di avere accesso al modello desiderato. Può essere disponibile su repository pubblici o da fornitori autorizzati.

2. **Carica il Modello**:
   Utilizza lo script Ollama per caricare il modello sul tuo sistema. Questo in genere implica la copia del file di modello nella directory corretta (`OLLAMA_MODELS`).

3. **Configura il Modello**:
   Modifica eventuali configurazioni specifiche per il modello, come il suo nome o versione.

4. **Avvia Ollama**:
   Esegui l'immagine Docker e assicurati che il modello sia caricato correttamente. Puoi controllare lo stato del caricamento nel log del container.

5. **Verifica la Configurazione**:
   Verifica che il modello sia accessibile e funzioni correttamente attraverso l'API di Ollama o l'interfaccia web di Open WebUI.

| Modello | Caso d'uso |
|:-------|:---|
| qwen2.5-coder:1.5b | Autocomplete e sviluppo codice |
| qwen2.5:3b | Chat base |
| qwen2.5:7b | Chat con contesti maggiori |
| qwen3.5:4b | Chat recente e moderno |

### Configurazione di contine.dev come estensione di VS Code

1. **Installazione dell'estensione**:
   Apri Visual Studio Code, vai a "Extensions" (Estensioni) dalla scheda lato sinistro o usa il shortcut `Ctrl+Shift+X`. Cerca "contine.dev" e installa l'estensione.

2. **Configurazione locale**:
  Nella configurazione di contine.dev:

  ```js
  {
   "models": [
      {
         "title": "Qwen Coder Chat",
         "provider": "ollama",
         "model": "qwen2.5-coder:7b",
         "apiBase": "http://localhost:7869"
      },
      {
         "title": "Qwen3 Coder Chat",
         "provider": "ollama",
         "model": "qwen3.5:4b-q4_K_M",
         "apiBase": "http://localhost:7869"
      }
   ],
   "tabAutocompleteModel": {
      "title": "Qwen Coder Autocomplete",
      "provider": "ollama",
      "model": "qwen2.5-coder:1.5b",
      "apiBase": "http://localhost:7869"
   },
   "embeddingsProvider": {
      "provider": "ollama",
      "model": "nomic-embed-text",
      "apiBase": "http://localhost:7869"
   },
   "contextProviders": [
      {
         "name": "code",
         "params": {}
      },
      {
         "name": "docs",
         "params": {}
      },
      {
         "name": "diff",
         "params": {}
      },
      {
         "name": "terminal",
         "params": {}
      },
      {
         "name": "problems",
         "params": {}
      }
   ],
   "slashCommands": [
      {
         "name": "share",
         "description": "Export the current chat session to markdown"
      },
      {
         "name": "cmd",
         "description": "Generate a shell command"
      },
      {
         "name": "commit",
         "description": "Generate a git commit message"
      }
   ]
   }
  ```

<a id="appendice-e-cli-ollama"></a>

## Appendice A - Guida all'utilizzo della CLI di Ollama (Comandi Ollama)

Lista dei comandi principali di ollama cli
Prima di iniziare assicurarsi che docker compose sia up e quindi entrare dentro il container ollama per eseguire i comandi

### Entrare dentro il container

```bash
docker exec -it ollama bash 
```

## A.1 Comandi CLI principali

### Avviare Ollama

```bash
ollama serve
```

Avvia il server locale Ollama. È il processo che espone le API HTTP.
Di base, una volta avviato il docker compose up il servizio ollama sará giá avviato...
Quindi non serve fare 'ollama serve'


---

### Scaricare un modello

```bash
ollama pull qwen2.5-coder:7b
```

Scarica il modello nel registro locale di Ollama.

Esempi:

```bash
ollama pull llama3.2
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

---

### Eseguire un modello in chat interattiva

```bash
ollama run qwen2.5-coder:7b
```

Apre una sessione interattiva da terminale.

Puoi anche passare direttamente il prompt:

```bash
ollama run qwen2.5-coder:7b "Spiegami Docker in 5 righe"
```

---

### Input multilinea

Nella chat interattiva puoi inserire testo multilinea usando triple virgolette:

```text
>>> """Spiegami questo codice:
... def hello():
...     print('ciao')
... """
```

---

### Elencare i modelli installati

```bash
ollama list
```

oppure:

```bash
ollama ls
```

Mostra i modelli presenti localmente.

---

### Mostrare i modelli caricati in memoria

```bash
ollama ps
```

Utile per capire quali modelli sono attualmente attivi e stanno usando RAM/VRAM.

---

### Fermare un modello caricato

```bash
ollama stop qwen2.5-coder:7b
```

Libera le risorse usate da quel modello.

---

### Mostrare informazioni su un modello

```bash
ollama show qwen2.5-coder:7b
```

Può mostrare informazioni su:

- famiglia del modello;
- template;
- parametri;
- licenza;
- capabilities;
- quantizzazione.

---

### Copiare o creare alias di un modello

```bash
ollama cp qwen2.5-coder:7b my-qwen-coder
```

Utile se vuoi usare un nome più comodo o compatibile con strumenti esterni.

Esempio:

```bash
ollama cp llama3.2 gpt-3.5-turbo
```

Questo non trasforma Llama in GPT, crea solo un alias locale.

---

### Rimuovere un modello

```bash
ollama rm qwen2.5-coder:7b
```

Elimina il modello dal disco locale.

---

### Creare un modello personalizzato con Modelfile

Crea un file chiamato `Modelfile`:

```text
FROM qwen2.5-coder:7b
SYSTEM """
Sei un assistente tecnico specializzato in Python, Laravel, Vue, Docker e AI.
Rispondi sempre in italiano.
"""
PARAMETER temperature 0.3
PARAMETER num_ctx 8192
```

Poi crea il modello:

```bash
ollama create qwen2.5-coder-it-8k -f Modelfile
```

Eseguilo:

```bash
ollama run qwen2.5-coder-it-8k
```

Usalo da Python:

```python
MODEL = "qwen2.5-coder-it-8k"
```

Questo è il modo consigliato per fissare parametri come `num_ctx` quando usi Ollama tramite API OpenAI-compatible.

---

### Generare embedding da CLI

Con un modello embedding:

```bash
ollama pull nomic-embed-text
ollama run nomic-embed-text "Laravel usa Eloquent ORM"
```

L'output è un vettore numerico. Per applicazioni reali conviene usare `/api/embed` o `/v1/embeddings` da codice.

---

### Usare un modello multimodale da CLI

Con un modello vision compatibile puoi passare un'immagine nel prompt:

```bash
ollama run gemma4 "Cosa vedi in questa immagine? /percorso/immagine.png"
```

Il supporto dipende dal modello installato.

---

### Login e logout Ollama

```bash
ollama signin
ollama signout
```

Servono per funzionalità legate all'account/registry Ollama. Per usare Ollama locale con modelli pubblici già disponibili spesso non ti servono.

---

## E.4 Comandi rapidi di diagnostica

```bash
# Versione Ollama
ollama -v

# Modelli installati
ollama list

# Modelli attivi in memoria
ollama ps

# API server vivo
curl http://localhost:11434/api/tags

# API OpenAI-compatible viva
curl http://localhost:11434/v1/models
```

Se usi la repo Docker con porta host `7869`, sostituisci:

```text
http://localhost:11434
```

con:

```text
http://localhost:7869
```

---

## E.5 Tabella riassuntiva CLI

| Comando | Scopo |
|---|---|
| `ollama serve` | avvia il server Ollama |
| `ollama run <model>` | esegue un modello in chat |
| `ollama pull <model>` | scarica un modello |
| `ollama list` / `ollama ls` | elenca modelli installati |
| `ollama ps` | mostra modelli caricati |
| `ollama stop <model>` | ferma un modello caricato |
| `ollama show <model>` | mostra dettagli modello |
| `ollama cp <source> <dest>` | crea alias/copia modello |
| `ollama rm <model>` | elimina modello locale |
| `ollama create <name> -f Modelfile` | crea modello personalizzato |
| `ollama signin` | login account Ollama |
| `ollama signout` | logout account Ollama |

---

<a id="appendice-b-autenticazione-backend-immagini"></a>

## Appendice B - Configurazione autenticazione web

Le immagini AI-Dock possono proteggere le interfacce di Automatic1111 e
ComfyUI con autenticazione HTTP Basic. Nel progetto l'autenticazione e'
opzionale e disabilitata per default, per non interrompere il collegamento con
Open WebUI.

Non usare in produzione le credenziali predefinite `user` / `password`.
Inserisci le credenziali reali esclusivamente nel file `.env`, che non deve
essere versionato.

### B.1 Automatic1111

Per abilitare l'autenticazione dell'interfaccia web:

```dotenv
AUTOMATIC1111_WEB_ENABLE_AUTH=true
AUTOMATIC1111_WEB_USER=admin
AUTOMATIC1111_WEB_PASSWORD=sostituisci-con-una-password-lunga
AUTOMATIC1111_WEB_PASSWORD_HASH=
```

`AUTOMATIC1111_WEB_PASSWORD` contiene la password in chiaro. In alternativa,
AI-Dock accetta un hash bcrypt tramite `AUTOMATIC1111_WEB_PASSWORD_HASH`; in
quel caso lascia vuota la password in chiaro:

```dotenv
AUTOMATIC1111_WEB_ENABLE_AUTH=true
AUTOMATIC1111_WEB_USER=admin
AUTOMATIC1111_WEB_PASSWORD=
AUTOMATIC1111_WEB_PASSWORD_HASH='$2y$10$sostituisci-con-un-hash-bcrypt'
```

L'autenticazione web AI-Dock e l'autenticazione dell'API Automatic1111 sono
distinte. Se vuoi proteggere anche l'API usata da Open WebUI, aggiungi
`--api-auth utente:password` agli argomenti e configura le stesse credenziali
in Open WebUI:

```dotenv
AUTOMATIC1111_NVIDIA_ARGS=--listen --api --port 7860 --api-auth openwebui:password-api
OPEN_WEBUI_AUTOMATIC1111_API_AUTH=openwebui:password-api
```

Per CPU conserva anche i flag dedicati:

```dotenv
AUTOMATIC1111_CPU_ARGS=--listen --api --port 7860 --api-auth openwebui:password-api --use-cpu all --precision full --no-half --skip-torch-cuda-test
```

### B.2 ComfyUI

Per proteggere l'interfaccia ComfyUI:

```dotenv
COMFYUI_WEB_ENABLE_AUTH=true
COMFYUI_WEB_USER=admin
COMFYUI_WEB_PASSWORD=sostituisci-con-una-password-lunga
COMFYUI_WEB_PASSWORD_HASH=
```

E' possibile usare un hash bcrypt nello stesso modo:

```dotenv
COMFYUI_WEB_ENABLE_AUTH=true
COMFYUI_WEB_USER=admin
COMFYUI_WEB_PASSWORD=
COMFYUI_WEB_PASSWORD_HASH='$2y$10$sostituisci-con-un-hash-bcrypt'
```

Attenzione: l'autenticazione HTTP Basic di AI-Dock puo' impedire a Open WebUI
di raggiungere direttamente l'API ComfyUI. Se usi ComfyUI esclusivamente come
backend di Open WebUI, mantieni `COMFYUI_WEB_ENABLE_AUTH=false` e limita
l'esposizione della porta con `COMFYUI_HOST_BIND=127.0.0.1` oppure tramite
firewall. Abilita l'autenticazione web quando devi esporre direttamente
l'interfaccia, verificando successivamente la connessione da Open WebUI.

### B.3 Applicare le modifiche

Dopo aver cambiato le credenziali, ricrea il backend selezionato:

```bash
# Automatic1111 CPU
docker compose --profile automatic1111 up -d --force-recreate automatic1111

# Automatic1111 NVIDIA
docker compose -f docker-compose-ollama-nvidia.yaml \
  --profile automatic1111 up -d --force-recreate automatic1111

# ComfyUI CPU
docker compose --profile images up -d --force-recreate comfyui

# ComfyUI NVIDIA
docker compose -f docker-compose-ollama-nvidia.yaml \
  --profile images up -d --force-recreate comfyui
```

## License

[GPL 2.0](LICENSE).
