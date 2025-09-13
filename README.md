Este projeto integra **Azure DevOps** com um contador automático de horas de trabalho, ajudando times a manterem as tarefas sempre atualizadas sem precisar editar manualmente os campos de **Remaining Work** e **Completed Work**.
CRIADOR:Lucas Lopes Freitas Moura
---

Funcionalidades

Associação automática

Detecta AB#<id> em branches e commits.

Atualiza automaticamente:

Estado do Work Item para In Progress / Doing / Active.

Campos Remaining Work e Completed Work.

Contagem de horas

Timer soma tempo em intervalos configuráveis (default: 1h).

Incrementa CompletedWork e reduz RemainingWork.

Comandos manuais (API/UI)

Connect → conecta Work Items ao contador.

Focus → mantém apenas um Work Item ativo por vez.

Pause / Resume → pausa e retoma a contagem.

Integração com Azure DevOps

Webhooks de git.push e ref update (criação de branch).

Interface Web simples (opcional)

Campo de IDs de tarefas.

Botões: Connect, Focus, Pause, Resume.

Logs em tempo real das ações.

🚀 Como rodar localmente

Pré-requisitos

Docker Desktop
 (Windows/Mac) ou Docker Engine + Compose (Linux).

Passos

Clone o repositório.

Copie o arquivo de exemplo:

cp .env.example .env


Edite .env com suas credenciais:

ADO_ORG=seu-org
ADO_PROJECT=seu-projeto
ADO_PAT=seu-personal-access-token
DEFAULT_ESTIMATE_HOURS=6.0
HOURS_PER_PUSH=0.5


Suba os serviços:

docker compose up -d


Acesse os endpoints: http://localhost:7071/api

Exemplos

# Conectar um Work Item
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
