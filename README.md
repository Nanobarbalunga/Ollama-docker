# Ollama Docker Compose Setup

## Getting Started

### Prerequisites
Assicurati di avere installato :

- Docker > 3.7

#### GPU Support (Optional)

Se vuoi usare la gpu per migliorare le prestazioni devi prima installare NVIDIA Container Toolkit:

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

Se vui usare la GPU
```bash
docker compose -f docker-compose-ollama-gpu.yaml up -d
```

else
```bash
docker compose up -d
```

Per aprire Ollama-webui [http://localhost:8080](http://localhost:8080) nel tuo browser.

### Model Installation

Per installare un modello da openWebUi andare su Impostazioni=>Modello=>Gestione e selezionare il modello desiderato.

## Stop and Cleanup

Per fermare e pulire le risorse utilizzate, eseguire:

```bash
docker compose down
```

## License

[GPL 2.0](LICENSE).
