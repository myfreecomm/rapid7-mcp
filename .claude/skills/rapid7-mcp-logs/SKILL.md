---
name: rapid7-mcp-logs
description: Sobe o servidor local do rapid7-mcp e faz buscas de log no InsightIDR (Rapid7) via MCP. Use sempre que precisar consultar logs de um pedido/integração via Rapid7, quando o MCP rapid7-mcp der ConnectionRefused ou erro 500, ou quando for necessário descobrir o ID de um log set (ex: handler PluggTo, KORP, Estee Lauder, etc). Cobre subir o servidor, reconectar o MCP, resolver nome→UUID de log, montar query_logs corretamente e paginar resultados assíncronos.
---

# rapid7-mcp: subir servidor + buscar logs

## Contexto

O MCP `rapid7-mcp` **não é um serviço always-on** — é um servidor HTTP local
(FastAPI/uvicorn) que precisa ser iniciado manualmente antes de cada sessão.
O `.claude.json` já tem o servidor registrado como:

```json
"rapid7-mcp": { "type": "http", "url": "http://localhost:9000/mcp" }
```

Repo local: `D:\Repos\rapid7-mcp`. É um **fork da Nexaas**
(`github.com/myfreecomm/rapid7-mcp`, remote `origin`) do projeto original
`SecuritahGuy/rapid7-mcp` (remote `upstream`) — fizemos o fork porque não
temos permissão de push no upstream e precisávamos commitar correções
próprias. Ao mexer no código deste repo, commite/push no `origin`
(myfreecomm), nunca tente dar push no `upstream`.

Credenciais já configuradas em `D:\Repos\rapid7-mcp\.env` (`IDR_REGION=eu`,
`IDR_API_KEY=...`, `DEMO_MODE=false`) — não mexer, já funcionam.

**Produto usado de fato: InsightIDR (log search).** InsightVM (sites/assets)
e Metasploit Pro não estão configurados/usados — não perca tempo tentando
essas tools se aparecer erro de conexão nelas, é esperado.

## 1. Verificar se o servidor já está no ar

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9000/mcp --max-time 3
```

Se der erro de conexão (não retornar `406`), o servidor não está rodando —
vá para o passo 2. Se as tools `mcp__rapid7-mcp__*` já aparecerem disponíveis
na sessão, pule direto para o passo 3.

## 2. Subir o servidor

```bash
cd "D:/Repos/rapid7-mcp" && uv run uvicorn rapid7_mcp.main:app --port 9000
```

Rodar em **background** (`run_in_background: true` no Bash tool, ou em um
terminal separado) — é um processo de vida longa, não retorna.

Depois de subir, **a sessão atual não reconecta sozinha** se o MCP já tinha
tentado conectar e falhado no início da sessão. Peça para o usuário rodar
`/mcp` para reconectar, ou avise que é necessário. Depois disso as tools
`mcp__rapid7-mcp__*` ficam disponíveis via `ToolSearch`.

Se precisar reiniciar (depois de uma correção de código, por exemplo): mate o
processo antigo (`taskkill //PID <pid> //F`) e suba de novo com o mesmo
comando — **não há hot-reload**. Como é um processo local compartilhado por
qualquer sessão de Claude Code na máquina, reiniciar derruba na hora quem
mais estiver com uma chamada em andamento.

## 3. Descobrir o log set certo (nome → UUID)

`query_logs` exige o **UUID** do log, não o nome amigável do console Rapid7
(ex: `prod-handler-pluggto` não funciona, tem que ser o UUID). Use a tool
`list_logs` (endpoint `GET /idr/logs/catalog`, parâmetro opcional
`name_contains`) para resolver:

```
list_logs(name_contains="pluggto")
```

IDs de logs de produção já confirmados (ambiente `Connection-PROD-Commerce`):

| Nome amigável           | UUID                                   |
| ----------------------- | -------------------------------------- |
| `prod-handler-pluggto`  | `31b52aa8-a512-4425-acb7-f4f3e61a7c13` |
| `prod-receiver-pluggto` | `405c40ef-0b8d-49e2-bc70-0d887f3705e4` |

Para qualquer outra integração (KORP, Estee Lauder, VTEX, etc.), rode
`list_logs` com o `name_contains` correspondente em vez de assumir um ID.

## 4. Buscar logs (`query_logs`)

Parâmetros:

- `query` (obrigatório) — LEQL. Busca de texto cru: `where(<termo>)`, ex.
  `where(6a6ff8f13289ce1e02e01fc4)` para achar um order ID/hash em qualquer
  linha de log.
- `logs` (obrigatório) — lista de UUIDs (vindos do `list_logs`). Sem isso a
  API do Rapid7 recusa a query.
- `from_time` / `to_time` (opcionais) — epoch **milissegundos**. Se omitidos,
  o servidor aplica default de últimas 24h.

Exemplo:

```
query_logs(
  query: "where(6a6ff8f13289ce1e02e01fc4)",
  logs: ["31b52aa8-a512-4425-acb7-f4f3e61a7c13"],
  from_time: <epoch_ms>,
  to_time: <epoch_ms>
)
```

Para calcular epoch ms de "últimos N dias" em bash:

```bash
python3 -c "import time; t=int(time.time()*1000); print(t-N*24*3600*1000, t)"
```

### A busca é assíncrona — pode precisar continuar

`query_logs` inicia um job no Rapid7 e a primeira resposta costuma vir com
`progress` baixo (às vezes 0) e `events` vazio ou incompleto, mesmo havendo
resultados. Use `poll_log_query`, passando o `id` retornado por `query_logs`
(URL-encoded), para continuar acompanhando o mesmo job:

```
poll_log_query(query_id: "<id retornado por query_logs>")
```

Repita até `progress` chegar em `100`; cada chamada já retorna o conjunto
acumulado de eventos até aquele ponto, não só o incremento novo. Jobs
inativos por muito tempo expiram no lado do Rapid7 (erro "Cannot find
provided continue ID") — não fique esperando demais entre um poll e outro.

## 5. Tools que NÃO funcionam (não insista, não é bug seu)

| Tool                                                          | Sintoma                                 | Causa                                                                                                                          |
| ------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `list_investigations` / `get_investigation`                   | 403                                     | Licença de Insight IDR/UBA não habilita esse produto — problema de contrato com a Rapid7, não técnico                          |
| `list_indicators` (IOCs)                                      | 404                                     | Bug no repo: chama `GET /idr/v2/iocs`, endpoint que não existe na API real. Não corrigido — não adivinhamos o path certo ainda |
| `list_sites` / assets / scans (InsightVM)                     | Connection error (`getaddrinfo failed`) | `R7_CONSOLE_URL` não configurado — não usamos InsightVM                                                                        |
| `list_workspaces` / `list_sessions` / `get_loot` (Metasploit) | Connection error                        | `MSP_URL` não configurado — não usamos Metasploit Pro                                                                          |

## 6. Troubleshooting rápido

| Sintoma no MCP                                                                     | Causa real                                                                                                                                        | Onde olhar                                                                                                                                                                         |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ConnectionRefused` ao chamar qualquer tool                                        | Servidor local não está rodando                                                                                                                   | Passo 2                                                                                                                                                                            |
| Erro genérico "Status code: 500. Response: Internal Server Error" em qualquer tool | O wrapper MCP (`fastapi_mcp`) esconde o erro real — **sempre** reporta 500 genérico, seja qual for a causa de baixo (400, 403, 404, erro de rede) | Reproduza a chamada direto contra o servidor local com `curl` (`http://localhost:9000/<path>`) e leia o traceback no log do processo uvicorn — só assim aparece a causa verdadeira |
| `query_logs` retorna esse 500 genérico                                             | Faltou `logs`, ou a API rejeitou o payload                                                                                                        | Confira se está passando `logs` (UUID) — se sim, teste direto com `curl` no path `/idr/logs`                                                                                       |
| Nome amigável (ex: `prod-handler-pluggto`) não funciona em `logs`                  | `query_logs` exige UUID, não nome                                                                                                                 | Rode `list_logs` primeiro                                                                                                                                                          |
| `events` vazio mesmo sabendo que devia ter resultado                               | Job de busca ainda não terminou de processar (assíncrono)                                                                                         | Use `poll_log_query` com o `id` da resposta até `progress: 100`                                                                                                                    |

Técnica geral para depurar qualquer 500 do MCP: bata direto no endpoint REST
por trás da tool (`curl http://localhost:9000/<prefixo>/<path>`), sem passar
pelo protocolo MCP — o uvicorn loga o traceback completo no console, o que o
`fastapi_mcp` nunca repassa para o cliente MCP.

## Onde ficam as correções

Todas as correções descritas aqui (`query_logs` payload, `list_logs`,
`poll_log_query`) estão commitadas no fork `github.com/myfreecomm/rapid7-mcp`
(branch `main`) — não são mais patches locais soltos. Se precisar recriar o
ambiente do zero, é só clonar o fork (não o upstream `SecuritahGuy`) e
copiar/recriar o `.env`. Esta própria skill também vive versionada dentro do
repo, em `.claude/skills/rapid7-mcp-logs/SKILL.md`.
