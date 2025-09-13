Este projeto integra **Azure DevOps** com um contador automático de horas de trabalho, ajudando times a manterem as tarefas sempre atualizadas sem precisar editar manualmente os campos de **Remaining Work** e **Completed Work**.

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
 CRIADOR:Lucas Lopes Freitas Moura
