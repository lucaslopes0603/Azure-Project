Este projeto integra **Azure DevOps** com um contador automático de horas de trabalho, ajudando times a manterem as tarefas sempre atualizadas sem precisar editar manualmente os campos de **Remaining Work** e **Completed Work**.
CRIADOR:Lucas Lopes Freitas Moura
---

## 🚀 Funcionalidades

- **Associa branches e commits a Work Items** usando a convenção `AB#<id>`.
- **Atualiza automaticamente**:
  - Estado do Work Item para *In Progress / Doing / Active*.
  - Campos **Remaining Work** e **Completed Work**.
- **Contagem automática**:
  - Timer que soma horas a cada intervalo (default: 1h, configurável).
  - Incrementa `CompletedWork` e reduz `RemainingWork`.
- **Comandos manuais** via API/UI:
  - `Connect` → conecta Work Items ao contador.
  - `Focus` → mantém apenas um Work Item ativo por vez.
  - `Pause` / `Resume` → pausa e retoma a contagem.
- **Integração com Webhooks** do Azure DevOps (`git.push`, `ref update`).
- **Interface Web** simples (Cloudflare Pages):
  - Campo de IDs de tarefas.
  - Botões para Connect, Focus, Pause e Resume.
  - Logs em tempo real das ações.
 
  - 🚀 Como rodar localmente
🔧 Pré-requisitos

Docker Desktop
 (Windows/Mac) ou Docker Engine + Compose Plugin (Linux).

Clonar este repositório.

📂 Preparar variáveis de ambiente

Copie o arquivo de exemplo:

cp .env.example .env


Edite o arquivo .env e preencha:

ADO_ORG=seu-org
ADO_PROJECT=seu-projeto
ADO_PAT=seu-personal-access-token
DEFAULT_ESTIMATE_HOURS=6.0
HOURS_PER_PUSH=0.5


⚠️ O ADO_PAT precisa ter permissões de Work Items (Read/Write) e Code (Read) no Azure DevOps.

▶️ Subir os serviços

Na raiz do projeto:

docker compose up -d


Isso vai iniciar:

Azurite (emulador do Azure Storage)

Azure Functions Host rodando este projeto Python

🔗 Endpoints disponíveis

Funções: http://localhost:7071/api

POST /connect → iniciar tracking de work items

POST /pause → pausar tracking

POST /resume → retomar tracking

POST /focus → focar em um único work item

POST /devops-webhook → usado pelo Service Hook do Azure DevOps

🧪 Exemplos de uso
# Conectar um work item
curl -X POST http://localhost:7071/api/connect \
  -H "Content-Type: application/json" \
  -d '{"wi_ids":["12345"]}'

# Pausar
curl -X POST http://localhost:7071/api/pause \
  -H "Content-Type: application/json" \
  -d '{"wi_ids":["12345"]}'

# Focar em um único item
curl -X POST http://localhost:7071/api/focus \
  -H "Content-Type: application/json" \
  -d '{"wi_id":"12345"}'

