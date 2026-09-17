# Design: add-manual-link

## Context

`PortLink` (models.py:162) já modela tudo o que um link manual precisa: `source_id/target_id`, `source_port/target_port`, `override_status`, `override_speed`. "AUTO" já é o estado nativo (`None`): `refresh_state()` e `link_speed()` (view.py:556-576) usam os valores SNMP quando não há override, e `speed_color(0)` devolve cinza quando não há velocidade conhecida. Links paralelos usam offsets simétricos (view.py:748-762), mas a lógica está **duplicada e divergente** em `set_graph_from_persisted` (view.py:1019-1029, ainda com o offset antigo baseado em `lag`).

O spec `topology-link-override` já cobre o contrato Auto/up/down/velocidade; esta change é aditiva e não altera nenhum requisito existente.

## Goals / Non-Goals

**Goals:**
- Entrar/sair de um modo de criação de link a partir de um ícone "Link" fixo na paleta Objects.
- Selecionar source (1º clique, amarelo) e target (2º clique), com preview e cancelamento (Esc/vazio/mesmo objeto).
- Diálogo de portas (listas de interface + entrada livre) e velocidade (AUTO default).
- Criar/persistir o `PortLink` + `EdgeItem`, rejeitando duplicatas e self-loop.
- Suportar grupo ↔ dispositivo.

**Non-Goals:**
- "Tipo de link" (LAG/lógico) — fora de escopo; só velocidade (decisão do usuário).
- Link grupo ↔ grupo.
- Detecção automática de portas (o operador escolhe/digita).

## Decisions

### 1. Sem mudança no modelo

`PortLink` permanece como está. Velocidade escolhida manualmente vira `override_speed` (mesmo mecanismo do menu de contexto existente); AUTO = `None`. Porta digitada livre vira `source_port`/`target_port` (string), `source_ifindex=0`.

- **Alternativa considerada**: adicionar campo `link_type`. Rejeitada — o usuário confirmou que só precisa de velocidade.

### 2. Estado de modo de link na cena

`TopologyScene` ganha `_link_mode: bool` e `_link_source: NodeItem | GroupNodeItem | None`, expostos por `set_link_mode(on)`. O `TopologyView` (ou a aba) liga o ícone ao modo.

- `NodeItem` e `GroupNodeItem` ganham um `mousePressEvent` que, quando `scene._link_mode` está ativo, **emite** o clique ao invés de selecionar normalmente (evita que o clique de criação mude a seleção Qt padrão).
- Destaque amarelo: novo flag `_link_highlight` nas duas classes, desenhado como anel amarelo forte no `paint` (cor distinta do azul `ACCENT` de seleção).

### 3. Preview

Enquanto há source, um `QGraphicsPathItem` tracejado temporário é atualizado no `mouseMoveEvent` da cena/view, do centro do source até o cursor. Removido ao concluir/cancelar.

### 4. Diálogo `LinkCreationDialog` (em detail.py)

- Duas colunas: interfaces do source (esq) e do target (dir), como listas (`QListWidget`) ordenadas por `index`, rotuladas `iface.name` (+ `descr`).
- Se um lado tem `device.interfaces` vazio: substitui a lista por um `QLineEdit` de porta livre.
- Combobox de velocidade: `Auto`, `10 Mbps`, `100 Mbps`, `1 Gbps`, `10 Gbps` (mesmos valores do menu de contexto). `Auto` = `override_speed=None`.
- O diálogo devolve as escolhas; a cena cria o link.

### 5. Criação do link e offset

Novo `TopologyScene.add_manual_link(source_dev_id, source_port, target_dev_id, target_port, speed)`:
- Checa duplicata: `PortLink.key()` (models.py:177) — se já existe link com a mesma chave, retorna erro (mensagem exibida pelo caller).
- Checa self-loop (`source_dev_id == target_dev_id`).
- Cria `PortLink`, anexa em `self.graph.links`, cria `EdgeItem`, recalcula offsets do par.
- Extrai helper `_pair_offsets(pair_nodes)` compartilhado por `set_graph`, `set_graph_from_persisted` e `add_manual_link`, corrigindo a divergência atual.
- Chama `_schedule_save()`.

### 6. Grupo ↔ dispositivo

Um grupo colapsado não tem id de device próprio nem interfaces. Ao linkar um grupo, resolve para `GroupNodeItem.parent_id` (o dispositivo nível-1 dono do cluster); o lado do grupo usa **porta livre** (sem lista de interfaces).

- **Risco**: semanticamente o link "grupo→device" é uma aproximação (o grupo representa N filhos). Documentado como limitação; representa a conectividade do pai do cluster.

## Risks / Trade-offs

- **[Interceptar cliques]** → risco de conflitar com seleção/arrasto normal; mitigação: `mousePressEvent` custom só desvia quando `_link_mode` ativo.
- **[Device manual sem interface]** → AUTO resulta em link cinza (sem status real); mitigação: comportamento explícito e já existente.
- **[Offset duplicado]** → corrigido ao extrair helper único, removendo a inconsistência atual.
- **[Semântica de grupo]** → link usa o device pai do cluster; documentado.
- **[Self-loop/duplicata]** → bloqueado por `key()` + checagem de id, com mensagem.

## Open Questions

Nenhuma bloqueante — todas as ambiguidades foram decididas com o usuário.
