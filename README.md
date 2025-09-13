Este projeto integra **Azure DevOps** com um contador automático de horas de trabalho, ajudando times a manterem as tarefas sempre atualizadas sem precisar editar manualmente os campos de **Remaining Work** e **Completed Work**.
CRIADOR:Lucas Lopes Freitas Moura
---

⏱️ Remaining Hours ADO

Ferramenta para automatizar contagem de horas e atualização de Work Items no Azure DevOps, usando Azure Functions em Python rodando localmente via Docker.

✨ Funcionalidades
🔗 Associação automática

Detecta AB#<id> em branches e commits.

Atualiza automaticamente:

Estado do Work Item para Active / In Progress / Doing.

Campos Remaining Work e Completed Work.

⏱️ Contagem de horas

Timer executa a cada 5 minutos (configurável).

Acumula minutos → converte em horas → aplica:

Incrementa CompletedWork.

Reduz RemainingWork.

🕹️ Comandos manuais

Connect → conecta Work Items ao contador.

Focus → deixa apenas 1 Work Item ativo.

Pause / Resume → pausa ou retoma a contagem.

🔌 Integração com Azure DevOps

Webhooks suportados: git.push e git.refUpdateCreated (criação de branch).

🌐 Interface Web opcional

Campo de IDs de tarefas.

Botões: Connect, Focus, Pause e Resume.

Logs em tempo real.

🧰 Stack técnica

Azure Functions (Python v2)

Azure Table Storage (emulado com Azurite)

Docker Compose

API do Azure DevOps (REST 7.1)
Configuração

Clone o repositório.

Copie o arquivo de exemplo:

cp .env.example .env


Edite .env com suas credenciais:

ADO_ORG=seu-org
ADO_PROJECT=seu-projeto
ADO_PAT=seu-personal-access-token  # escopos: Work Items RW + Code Read
DEFAULT_ESTIMATE_HOURS=6.0
HOURS_PER_PUSH=0.5

▶️ Subir containers
docker compose up -d

🔗 Endpoints locais

POST /connect

POST /pause

POST /resume

POST /focus

POST /devops-webhook

🧪 Exemplos de uso
# Conectar WIs
curl -X POST http://localhost:7071/api/connect \
  -H "Content-Type: application/json" \
  -d '{"wi_ids":["12345","67890"]}'

# Pausar
curl -X POST http://localhost:7071/api/pause \
  -H "Content-Type: application/json" \
  -d '{"wi_ids":["12345"]}'

# Retomar
curl -X POST http://localhost:7071/api/resume \
  -H "Content-Type: application/json" \
  -d '{"wi_ids":["12345"]}'

# Focus
curl -X POST http://localhost:7071/api/focus \
  -H "Content-Type: application/json" \
  -d '{"wi_id":"12345"}'
