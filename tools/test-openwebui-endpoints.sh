#!/usr/bin/env bash
set -uo pipefail

# ============================================================
# Open WebUI API Endpoint Tester
# ============================================================
# Uso:
#   chmod +x test-openwebui-endpoints.sh
#   ./test-openwebui-endpoints.sh \
#     --url http://localhost:8080 \
#     --api-key sk-xxx \
#     --model qwen3:8b \
#     --embedding-model nomic-embed-text \
#     --prompt "Spiegami Docker Compose"
#
# Variabili env supportate:
#   OPENWEBUI_URL
#   OPENWEBUI_API_KEY
#   OPENWEBUI_MODEL
#   OPENWEBUI_EMBEDDING_MODEL
#   OPENWEBUI_PROMPT
#   OPENWEBUI_TEST_OUTPUT
#   OPENWEBUI_TEST_TIMEOUT
# ============================================================

BASE_URL="${OPENWEBUI_URL:-http://localhost:8080}"
API_KEY="${OPENWEBUI_API_KEY:-}"
MODEL="${OPENWEBUI_MODEL:-qwen3:8b}"
EMBEDDING_MODEL="${OPENWEBUI_EMBEDDING_MODEL:-nomic-embed-text}"
PROMPT="${OPENWEBUI_PROMPT:-Rispondi solo con: ok}"
OUTPUT_FILE="${OPENWEBUI_TEST_OUTPUT:-openwebui-endpoint-test.jsonl}"
TIMEOUT="${OPENWEBUI_TEST_TIMEOUT:-120}"
VERBOSE=0

usage() {
  cat <<EOF
Uso:
  $0 [opzioni]

Opzioni:
  -u, --url URL                    URL base Open WebUI, es. http://localhost:8080
  -k, --api-key KEY                API key Open WebUI
  -m, --model MODEL                Nome modello chat/generate, es. qwen3:8b
  -e, --embedding-model MODEL      Nome modello embeddings, es. nomic-embed-text
  -p, --prompt PROMPT              Prompt da inviare
  -o, --output FILE                File report JSONL
  -t, --timeout SECONDS            Timeout curl
  -v, --verbose                    Mostra corpo risposta più lungo
  -h, --help                       Mostra help

Variabili env equivalenti:
  OPENWEBUI_URL
  OPENWEBUI_API_KEY
  OPENWEBUI_MODEL
  OPENWEBUI_EMBEDDING_MODEL
  OPENWEBUI_PROMPT
  OPENWEBUI_TEST_OUTPUT
  OPENWEBUI_TEST_TIMEOUT

Esempio:
  $0 \\
    --url http://localhost:8080 \\
    --api-key sk-xxx \\
    --model qwen3:8b \\
    --embedding-model nomic-embed-text \\
    --prompt "Rispondi solo con ok"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--url)
      BASE_URL="$2"
      shift 2
      ;;
    -k|--api-key)
      API_KEY="$2"
      shift 2
      ;;
    -m|--model)
      MODEL="$2"
      shift 2
      ;;
    -e|--embedding-model)
      EMBEDDING_MODEL="$2"
      shift 2
      ;;
    -p|--prompt)
      PROMPT="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argomento non riconosciuto: $1"
      usage
      exit 1
      ;;
  esac
done

BASE_URL="${BASE_URL%/}"

if ! command -v curl >/dev/null 2>&1; then
  echo "Errore: curl non trovato."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Errore: jq non trovato."
  echo "Installa jq, es:"
  echo "  sudo dnf install jq"
  echo "  sudo apt install jq"
  exit 1
fi

if [[ -z "$API_KEY" ]]; then
  echo "Errore: API key mancante."
  echo "Passala con --api-key oppure OPENWEBUI_API_KEY."
  echo ""
  echo "Per documentazione usa -h"
  exit 1
fi

: > "$OUTPUT_FILE"

# Formato:
#   NAME|METHOD|PATH|BODY_TYPE|AUTH_MODE
#
# BODY_TYPE:
#   none
#   chat_completions
#   anthropic_messages
#   ollama_generate
#   ollama_chat
#   embeddings
#
# AUTH_MODE:
#   bearer
#   x-api-key

ENDPOINTS=(
  "Open WebUI - List models|GET|/api/models|none|bearer"
  "Open WebUI - Chat completions|POST|/api/chat/completions|chat_completions|bearer"

  "Open WebUI - Anthropic messages /api/message|POST|/api/message|anthropic_messages|x-api-key"
  "Open WebUI - Anthropic messages /api/v1/messages|POST|/api/v1/messages|anthropic_messages|x-api-key"

  "Open WebUI - Custom models export|GET|/api/v1/models/export|none|bearer"

  "Ollama Proxy - Tags|GET|/ollama/api/tags|none|bearer"
  "Ollama Proxy - Generate|POST|/ollama/api/generate|ollama_generate|bearer"
  "Ollama Proxy - Chat|POST|/ollama/api/chat|ollama_chat|bearer"
  "Ollama Proxy - Embeddings|POST|/ollama/api/embeddings|embeddings|bearer"

  "Legacy - /api/completions check|POST|/api/completions|ollama_generate|bearer"
)

make_body() {
  local body_type="$1"

  case "$body_type" in
    none)
      echo ""
      ;;

    chat_completions)
      jq -n \
        --arg model "$MODEL" \
        --arg prompt "$PROMPT" \
        '{
          model: $model,
          stream: false,
          messages: [
            {
              role: "user",
              content: $prompt
            }
          ]
        }'
      ;;

    anthropic_messages)
      jq -n \
        --arg model "$MODEL" \
        --arg prompt "$PROMPT" \
        '{
          model: $model,
          max_tokens: 1024,
          stream: false,
          messages: [
            {
              role: "user",
              content: $prompt
            }
          ]
        }'
      ;;

    ollama_generate)
      jq -n \
        --arg model "$MODEL" \
        --arg prompt "$PROMPT" \
        '{
          model: $model,
          prompt: $prompt,
          stream: false
        }'
      ;;

    ollama_chat)
      jq -n \
        --arg model "$MODEL" \
        --arg prompt "$PROMPT" \
        '{
          model: $model,
          stream: false,
          messages: [
            {
              role: "user",
              content: $prompt
            }
          ]
        }'
      ;;

    embeddings)
      jq -n \
        --arg model "$EMBEDDING_MODEL" \
        --arg prompt "$PROMPT" \
        '{
          model: $model,
          prompt: $prompt
        }'
      ;;

    *)
      echo ""
      ;;
  esac
}

status_label() {
  local code="$1"

  if [[ "$code" =~ ^2 ]]; then
    echo "SUCCESS"
  elif [[ "$code" == "000" ]]; then
    echo "CURL_ERROR"
  elif [[ "$code" =~ ^4 ]]; then
    echo "CLIENT_ERROR"
  elif [[ "$code" =~ ^5 ]]; then
    echo "SERVER_ERROR"
  else
    echo "UNKNOWN"
  fi
}

truncate_text() {
  local max_len="$1"
  local input
  input="$(cat)"

  input="$(echo "$input" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')"

  if (( ${#input} > max_len )); then
    echo "${input:0:max_len}..."
  else
    echo "$input"
  fi
}

run_test() {
  local name="$1"
  local method="$2"
  local path="$3"
  local body_type="$4"
  local auth_mode="$5"

  local url="${BASE_URL}${path}"
  local body
  local response_file
  local curl_error_file
  local http_code
  local label
  local preview
  local curl_exit

  body="$(make_body "$body_type")"
  response_file="$(mktemp)"
  curl_error_file="$(mktemp)"

  local headers=(
    -H "Accept: application/json"
  )

  if [[ "$auth_mode" == "x-api-key" ]]; then
    headers+=(-H "x-api-key: ${API_KEY}")
  else
    headers+=(-H "Authorization: Bearer ${API_KEY}")
  fi

  if [[ "$method" == "POST" ]]; then
    headers+=(-H "Content-Type: application/json")
  fi

  if [[ "$method" == "GET" ]]; then
    http_code="$(
      curl -sS \
        --connect-timeout 10 \
        --max-time "$TIMEOUT" \
        -X GET \
        "${headers[@]}" \
        -o "$response_file" \
        -w "%{http_code}" \
        "$url" \
        2> "$curl_error_file"
    )"
    curl_exit=$?
  else
    http_code="$(
      curl -sS \
        --connect-timeout 10 \
        --max-time "$TIMEOUT" \
        -X POST \
        "${headers[@]}" \
        -d "$body" \
        -o "$response_file" \
        -w "%{http_code}" \
        "$url" \
        2> "$curl_error_file"
    )"
    curl_exit=$?
  fi

  if [[ $curl_exit -ne 0 ]]; then
    http_code="000"
  fi

  label="$(status_label "$http_code")"

  if [[ -s "$response_file" ]]; then
    if [[ "$VERBOSE" -eq 1 ]]; then
      preview="$(cat "$response_file" | truncate_text 500)"
    else
      preview="$(cat "$response_file" | truncate_text 180)"
    fi
  else
    preview="$(cat "$curl_error_file" | truncate_text 180)"
  fi

  jq -n \
    --arg name "$name" \
    --arg method "$method" \
    --arg url "$url" \
    --arg path "$path" \
    --arg body_type "$body_type" \
    --arg auth_mode "$auth_mode" \
    --arg status "$http_code" \
    --arg result "$label" \
    --arg preview "$preview" \
    --arg model "$MODEL" \
    --arg embedding_model "$EMBEDDING_MODEL" \
    '{
      name: $name,
      method: $method,
      url: $url,
      path: $path,
      body_type: $body_type,
      auth_mode: $auth_mode,
      http_status: $status,
      result: $result,
      model: $model,
      embedding_model: $embedding_model,
      preview: $preview
    }' >> "$OUTPUT_FILE"

  printf "%-42s %-6s %-5s %-14s %s\n" "$name" "$method" "$http_code" "$label" "$path"

  rm -f "$response_file" "$curl_error_file"
}

echo "============================================================"
echo "Open WebUI Endpoint Tester"
echo "============================================================"
echo "BASE_URL        : $BASE_URL"
echo "MODEL           : $MODEL"
echo "EMBEDDING_MODEL : $EMBEDDING_MODEL"
echo "PROMPT          : $PROMPT"
echo "OUTPUT          : $OUTPUT_FILE"
echo "TIMEOUT         : $TIMEOUT"
echo "============================================================"
echo

printf "%-42s %-6s %-5s %-14s %s\n" "NAME" "METHOD" "CODE" "RESULT" "PATH"
printf "%-42s %-6s %-5s %-14s %s\n" "----" "------" "----" "------" "----"

for item in "${ENDPOINTS[@]}"; do
  IFS='|' read -r name method path body_type auth_mode <<< "$item"
  run_test "$name" "$method" "$path" "$body_type" "$auth_mode"
done

echo
echo "============================================================"
echo "Riepilogo"
echo "============================================================"

success_count="$(jq -r 'select(.result=="SUCCESS") | .name' "$OUTPUT_FILE" | wc -l | tr -d ' ')"
error_count="$(jq -r 'select(.result!="SUCCESS") | .name' "$OUTPUT_FILE" | wc -l | tr -d ' ')"

echo "Successi: $success_count"
echo "Errori  : $error_count"
echo "Report  : $OUTPUT_FILE"

echo
echo "Endpoint falliti:"
jq -r 'select(.result!="SUCCESS") | "- [" + .http_status + "] " + .name + " -> " + .path + " | " + .preview' "$OUTPUT_FILE"

echo
echo "Endpoint riusciti:"
jq -r 'select(.result=="SUCCESS") | "- [" + .http_status + "] " + .name + " -> " + .path' "$OUTPUT_FILE"