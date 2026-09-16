# Proposal: topology-node-context-menu

## Why

O mapa de topologia mostra devices descobertos/desenhados, mas para agir sobre eles o usuário precisa sair da aba Topology e navegar até o módulo certo (SSH, IP Scanner, SNMP, Transferência), preencher o host manualmente e clicar. Isso quebra o fluxo de trabalho: o mapa já conhece o IP e o papel do device. O usuário quer clicar com o botão direito num elemento do mapa e invocar qualquer módulo do Cetus em um clique, com o host já apontado.

## What Changes

- **Menu de contexto rico em nós**: botão direito em um `NodeItem` abre um menu com a ação `Ping` (primeira opção), submenus que invocam módulos existentes do Cetus — `Access` (SSH/Telnet), `Scan` (TCP/UDP), `Traceroute` (ICMP/TCP/UDP), `SNMP` (Walk/Get/GetNext) e `Transfer` (SSH/SMB/FTP/TFTP) — além do "Remover" já existente.
- **Menu de contexto em grupos**: `GroupNodeItem` também ganha menu, com ações que operam sobre um único IP (o do device pai do grupo).
- **Resolução de credenciais**: para SSH/Telnet/Transfer, tentar primeiro um perfil salvo cujo host corresponda ao IP do device; sem perfil, cair de volta para pré-preenchimento do módulo (usuário completa credenciais).
- **Invocações diretas quando possível**: Ping, Telnet e SNMP walk executam imediatamente com o host preenchido; SSH/Transfer usam o fluxo de conexão existente (que já pede senha quando ausente).
- **Ações de rede desabilitadas para devices sem IP**: objetos manuais da paleta sem IP ficam com submenus de rede cinza; só "Remover" (e edição) permanece ativo.

## Capabilities

### New Capabilities

- `node-context-actions`: Ações de contexto sobre elementos do mapa de topologia — menu de botão direito em nós e grupos que invocam os módulos Access, Scan, SNMP e Transfer do Cetus com o host pré-preenchido, com resolução de credenciais via perfis salvos e fallback para pré-preenchimento.

### Modified Capabilities

Nenhum. Módulos existentes não mudam de comportamento; o menu apenas dispara seus fluxos públicos com campos pré-preenchidos.

## Impact

- **Código modificado**:
  - `cetuslib/topology/gui/view.py` — `NodeItem.contextMenuEvent` e `GroupNodeItem` passam a emitir sinais em vez de construir o menu; `TopologyScene`/`TopologyView` re-emitem para o `TopologyTab`.
  - `cetuslib/topology/tab.py` — recebe back-reference ao main window (`main_window=`), conecta os novos sinais e delega para o helper.
  - `cetuslib/main.py` — `TopologyTab(self.config)` vira `TopologyTab(self.config, main_window=self)` e ganha um delegador fino para o helper.
- **Código novo**: `cetuslib/topology/actions.py` (helper `TopologyActions`) — dispatcher do menu, presets de portas, resolução de perfil. Mantém `main.py` sem inchar.
- **Config**: nenhuma mudança de schema; usa `get_ssh_profiles()` e histórico de communities existentes.
- **Dependências**: nenhuma nova.
- **Empacotamento**: `dist/cetus` regenerado via `scripts/bundle-monolith.py`.

## Open Questions

Nenhuma. Escopo fechado nas decisões de design (perfil → fallback, invocação direta onde possível, scan de grupo = IP único do pai, helper novo).