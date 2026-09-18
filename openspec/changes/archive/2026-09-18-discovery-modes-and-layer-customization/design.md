# Design

## Context

A ferramenta de topologia do Baleno possui atualmente uma barra lateral retrátil dividida em Objetos, Camadas e Descoberta.
- Na Descoberta, a varredura (`TopologyDiscoveryWorker`) executa obrigatoriamente um escaneamento ICMP seguido de coletas SNMP (IF-MIB e LLDP) concorrentes.
- As camadas geradas são atribuídas aos dispositivos em `device.layers` (com derivações como `<nome>` para sementes e `<nome>-<N>` para saltos LLDP).
- No canvas (`view.py`), cada `NodeItem` desenha um cartão com o ícone do dispositivo dentro de um círculo de fundo escuro com borda cinza neutra.
- As ações de botão direito sobre nós são centralizadas em `TopologyActions._show_menu` (`actions.py`), mas não oferecem edição rápida de atributos do nó (papel e camada).
- O mapa é persistido em JSON (versão 3) por `persistence.py`.

## Goals / Non-Goals

**Goals:**
- Adicionar opção de modo de descoberta no painel lateral: **Básico (ICMP)** e **Profundo (ICMP + LLDP)**.
- Desabilitar ou sinalizar campos de credenciais SNMP quando o modo Básico estiver selecionado.
- Permitir escolher e alterar a cor de qualquer camada (no formulário de descoberta e via menu de contexto da árvore de camadas).
- Exibir anel de destaque com a cor da camada ao redor do círculo do ícone do dispositivo em `NodeItem.paint`.
- Propagar automaticamente a cor da camada principal para subcamadas geradas por saltos LLDP (`<nome>-<N>`).
- Persistir `layer_colors` no JSON do mapa de forma retrocompatível.
- Disponibilizar submenus no clique direito do nó: `Device Type` (todos os `DeviceRole`) e `Layer` (mover para camada existente ou nova camada).

**Non-Goals:**
- Tentar adivinhar fabricante ou modelo via ICMP puro no modo básico (dispositivos entram com papel padrão `Host` e podem ser reclassificados manualmente).
- Substituir o modelo de grafo ou a arquitetura do `LayerTreeWidget`.

## Decisions

### Decisão 1: Parâmetro `mode` no `TopologyDiscoveryWorker`
O construtor do `TopologyDiscoveryWorker` receberá `mode: str = 'deep'` (`'deep'` ou `'basic'`).
- Quando `mode == 'basic'`:
  - Executa `expand_networks()` e `PingScanner.scan_sync()`.
  - Para cada IP responsivo em `reachable`, instancia diretamente um `Device(id=ip, ip=ip, status='up', latency_ms=rtt, role=DeviceRole.HOST)`.
  - Pula a execução do pool de threads SNMP/LLDP (`_collect_ip`).
  - Constrói o grafo com `TopologyEngine().build(devices)` e emite `finished`.
- Quando `mode == 'deep'`:
  - Executa o fluxo completo existente (ICMP + SNMP + LLDP + expansão).

### Decisão 2: Modelo de cores de camada e persistência
Adicionar ao `TopologyGraph` um dicionário `layer_colors: dict[str, str] = field(default_factory=dict)`:
- Mapeia o nome da camada para uma string hexadecimal (ex.: `'LAN-Corporativa': '#3B82F6'`).
- Em `save_map()` e `load_map()` (`persistence.py`), o dicionário é serializado/desserializado sob a chave `'layer_colors'`. Arquivos JSON legados sem a chave recebem `{}` transparentemente.
- Subcamadas geradas por saltos (ex.: `LAN-Corporativa-2`) herdam a cor da camada semente `LAN-Corporativa` caso não possuam cor individual definida.

### Decisão 3: Seletor de cor no painel de Descoberta e na Árvore de Camadas
- No formulário de descoberta (`tab.py`):
  - Botão de pré-visualização de cor (`QPushButton` estilizado com swatch) ao lado do campo de nome da camada.
  - Ao clicar, exibe um menu popup com 8 cores elegantes pré-configuradas (*Azul #3B82F6, Esmeralda #10B981, Roxo #8B5CF6, Âmbar #F59E0B, Vermelho #EF4444, Ciano #06B6D4, Laranja #F97316, Grafite #6B7280*) e opção "Custom Color..." abrindo o `QColorDialog`.
- Na árvore de camadas (`LayerTreeWidget`):
  - Exibição de marcador colorido `●` na coluna de nome da camada.
  - Ação de contexto `🎨 Set Layer Color...` que abre o diálogo de seleção de cor e emite sinal de alteração.

### Decisão 4: Referência visual no ícone do dispositivo (`NodeItem`)
Em `NodeItem.paint`:
- Obtém a cor da camada associada ao nó (da primeira camada em `device.layers` ou da camada do grupo).
- No desenho do círculo do ícone (`icon_center, 22, 22`), se houver cor definida para a camada, substitui a borda neutra `QColor(30, 35, 42)` por `QPen(QColor(layer_color), 2.5)`.
- Isso garante identificação imediata e elegante da camada sem poluir o ícone central nem as informações de texto.

### Decisão 5: Submenus `Device Type` e `Layer` no Menu de Contexto do Nó
Em `TopologyActions._show_menu`:
- **Submenu `Device Type`**:
  - Lista todos os membros de `DeviceRole`: `Router`, `Switch`, `Core`, `Access`, `Firewall`, `Server`, `AP`, `Camera`, `Host`, `Phone`, `Cloud`, `Internet`.
  - Exibe ícone do tipo e marcação de verificação (`✓`) no papel atual do dispositivo.
  - Ao clicar: atualiza `device.role`, dispara atualização no `NodeItem` (que redesenha ícone e rótulo de tipo) e salva o mapa.
- **Submenu `Layer`**:
  - Lista todas as camadas conhecidas no grafo com marcação na camada atual.
  - Ação no topo/final: `+ Move to New Layer...` abrindo diálogo para definir nome e cor.
  - Ao selecionar uma camada: remove a camada anterior de `device.layers`, adiciona a nova camada, atualiza a árvore de camadas e os indicadores visuais do nó, e salva o mapa.

## Risks / Trade-offs

- **[Risk] Dispositivo sem SNMP no modo básico**: Usuário não terá informações detalhadas de portas físicas (IF-MIB) nem enlaces automáticos.
  - *Mitigation*: O modo é explicitamente rotulado como "Básico (ICMP)", ideal para inventário e alcance. Links manuais continuam suportados através da ferramenta "Create Link".
- **[Risk] Dispositivo pertencente a múltiplas camadas**: Qual cor exibir no anel do ícone?
  - *Mitigation*: Prioriza a cor da camada semente (hop 1 / nome base sem sufixo numérico); se houver mais de uma camada independente, usa a cor da primeira camada ordenada alfabeticamente.
