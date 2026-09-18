## Context

Hoje a aba Topology mantém **um único** grafo/cena/monitor e **um único** arquivo de mapa. Iniciar uma descoberta limpa a cena (`start_discovery` → `clear_scene()`) e, ao terminar, `load()` **substitui** tudo. Além disso, o `TrafficMonitor` antigo não é parado antes do `clear_scene()`, e o `_stop_monitor()` descarta a referência após `wait(3000)` mesmo se a thread continuar rodando — causando *"QThread: Destroyed while thread is still running"* e o fechamento do app.

O modelo-alvo é o de **camadas de editor de imagens**: cada descoberta nomeada gera camadas (`Rede-A`, `Rede-A-2`, …), que podem ser exibidas/ocultadas individualmente, num único mapa acumulado.

O `Device` já possui `layer` (int, profundidade de salto) e já existe um filtro de visibilidade numérico (`set_visible_levels`). A mudança troca o eixo numérico global por **camadas nomeadas por descoberta**.

## Goals / Non-Goals

**Goals:**
- Acumular múltiplas descobertas num único mapa, sem substituir e sem crash.
- Nomear cada descoberta e gerar camadas `<nome>` (sementes) e `<nome>-<N>` (vizinhos LLDP, profundidade real).
- Fundir dispositivos com o mesmo `chassis_id` (um nó, links somados), com pertinência a **múltiplas** camadas.
- Painel de camadas para exibir/ocultar redes por contexto.
- Posicionar cada descoberta à direita da região já ocupada, preservando a sub-hierarquia.
- Persistir camadas e associações no arquivo do mapa.

**Non-Goals:**
- Monitorar apenas a região/aba ativa (adiado).
- Controle manual da posição de cada região (adiado; automático à direita).
- Colisão de IP/hostname entre redes (não ocorre no cenário do usuário; `chassis_id` é a identidade).

## Decisions

### D1 — Camada nomeada deriva do nome da descoberta + profundidade
Cada descoberta recebe um nome (campo no formulário). O dispositivo é associado à camada `nome` (semente, hop 1) ou `nome-<N>` (vizinho LLDP no salto N). Sufixo numérico, profundidade real preservada.

- **Alternativa**: sufixo descritivo (`Rede-A · vizinhos`). **Rejeitada** — o usuário confirmou sufixo numérico.

### D2 — `Device.layers: set[str]` (pertinência múltipla)
O dispositivo guarda o conjunto de nomes de camada a que pertence. Um roteador de borda descoberto pelo backbone e pela rede pertence a ambas. A profundidade está codificada no sufixo do nome.

- **Alternativa**: `layer` único (int). **Rejeitada** — não representa o mesmo dispositivo em descobertas com profundidades diferentes.
- O `layer` (int) atual é mantido como **profundidade primária** (da primeira descoberta) para badge/escala, ou derivado do nome com menor salto.

### D3 — Merge/dedup por `chassis_id`
No merge, um dispositivo com `chassis_id` já presente funde (mantém um nó, soma links e camadas). Dispositivos sem `chassis_id` (órfãos ICMP) usam `ip` como chave, já que não há colisão de IP no cenário do usuário.

### D4 — Posicionamento à direita, por região de descoberta
Cada descoberta ocupa uma "região". Ao terminar, calcula o bounding box atual e posiciona os novos dispositivos à direita (offset = largura atual + margem), preservando a sub-hierarquia (sementes acima, vizinhos abaixo) dentro da região. Dispositivos compartilhados ficam na região da descoberta primária; os links cruzam regiões (mostrando a conexão backbone↔rede).

### D5 — Ciclo de vida do monitor (fix do crash)
Antes de mesclar, `_stop_monitor()` para o monitor antigo **e garante a finalização** (espera sem descartar thread em execução). O novo monitor cobre todos os dispositivos do grafo mesclado.

### D6 — Painel de camadas estilo GIMP e ações contextuais
O controle de camadas adota o padrão de editor de imagens (GIMP):
- **Árvore hierárquica**: Descobertas e suas subcamadas (`backbone`, `backbone-2`, `backbone-3`) são agrupadas sob uma pasta pai raiz correspondente ao prefixo da rede.
- **Visibilidade por ícone de olho (`👁`)**: Permite ligar/desligar a visualização em cascata para todo o grupo ou granularmente por subcamada (profundidade LLDP).
- **Contador de nós**: Cada camada e grupo exibe o número de dispositivos pertencentes.
- **Menu de contexto (botão direito)**: Ações avançadas como *Solo* (isolar a camada ocultando todas as demais), *Enquadrar no mapa (Fit Layer)* (pan e zoom para os limites da camada), *Exibir/Ocultar grupo*, e *Remover camada*.

### D7 — Persistência
`Device.to_dict`/`from_dict` passam a serializar `layers`. O formato v3 do mapa ganha o campo por dispositivo; leitura antiga (sem o campo) é tolerada (camada vazia → visível por padrão).

### D8 — Reestruturação da UI: Layout "Studio / CAD" (Opção A)
A barra Ribbon (que fragmentava os controles em 4 abas e consumia ~110px de altura) é substituída por um layout Studio/CAD limpo e moderno:
- **Barra superior compacta de linha única (~38px)**: Contém os campos de descoberta (`Networks`, `Layer`), botão `Discover`, barra de progresso, status e seletores de ação rápida (`Layout`, `Save Map`, `Export PNG`).
- **Popover de configurações SNMP**: As opções de versão SNMP (v1/v2c/v3), comunidade com histórico e credenciais v3 são movidas para um popover acionado por `[ ⚙ SNMP: v2c ▾ ]`, despoluindo a barra principal.
- **Painel lateral retrátil (Sidebar)**: Acoplado à direita do canvas (com toggle `[<]` / `[>]`), divido em duas seções:
  1. *Camadas (Layers)*: Árvore hierárquica estilo GIMP.
  2. *Paleta de Objetos*: Ícones arrastáveis (roteador, switch, etc.) imediatamente acessíveis sem precisar trocar de aba.
- **Controles flutuantes sobre o Canvas**: Botões de `Zoom In`, `Zoom Out`, `Fit In View` e a ferramenta de conexão manual (`Link Tool`) passam a flutuar no canvas como um mini-dock elegante.

## Risks / Trade-offs

- **[Nó em múltiplas camadas]** ocultar uma camada pode esconder um nó ainda usado por outra camada visível → Mitigação: visibilidade = OR das camadas (nó some só se TODAS as suas camadas estiverem ocultas).
- **[Regiões crescem para a direita]** mapas com muitas redes ficam largos → Mitigação: aceitável (o usuário pediu automático à direita); o painel de camadas reduz a poluição visual.
- **[Migração do arquivo v2→v3]** mapas antigos sem `layers` → Mitigação: leitura tolerante, camada vazia tratada como visível.
- **[Monitor cobrindo tudo]** carga SNMP multiplica → Mitigação: aceito por ora (monitorar região ativa é non-goal futuro).

## Open Questions

- Nenhuma pendente no escopo — os três pontos (pertinência múltipla, profundidade real, sufixo numérico) foram decididos com o usuário.
