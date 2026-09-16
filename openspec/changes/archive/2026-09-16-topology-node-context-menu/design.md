# Design: topology-node-context-menu

## Context

Motivação e escopo na proposta (`proposal.md`) e comportamento nas specs (`specs/node-context-actions/spec.md`).

Estado atual relevante:

- `NodeItem.contextMenuEvent` (`cetuslib/topology/gui/view.py:280`) constrói um menu mínimo com só "Remover" e emite `remove_requested`.
- `GroupNodeItem` não tem menu de contexto.
- `TopologyTab(self.config)` (`cetuslib/main.py:468`) não conhece o main window — não consegue invocar os métodos dos módulos (SSH, IP Scanner, SNMP, Transfer).
- Módulos são invocáveis por "pré-preenchimento + chamada pública":
  - SSH/Telnet: `connect_ssh()` (`main.py:13099`) lê `ssh_host`, `ssh_port`, `ssh_username`, `ssh_password`, `ssh_current_protocol`; já pede senha via dialog quando vazia (`main.py:13170`). Padrão de perfil: `load_ssh_profile_from_tree` (`main.py:12504`).
  - IP Scanner: `_start_scan()` (`main.py:8949`) lê `scan_network_input` (CIDR/IP/range), `scan_mask_combo`, `scan_current_method`, `scan_ports_input` (obrigatórias em TCP/UDP, `main.py:8972`).
  - SNMP: `execute_snmp_query()` (`main.py:5217`) lê `snmp_host_input`, OID (walk usa default `.1.3.6.1.2.1`), `snmp_current_type`, community (histórico via `get_vuln_community_history`/`add_vuln_community`).
  - Transfer: `_ft_client_connect()` (`main.py:11428`) lê `_ft_host_input`, `_ft_port_input`, `_ft_user_input`, `_ft_pass_input`; protocolo via `_ft_set_protocol` (`main.py:11040`, portas default SSH=22/FTP=21/TFTP=69/SMB=445). TFTP não exige auth.
- `switch_tab(index)` (`main.py:480`) navega entre páginas (2=ipscan, 4=snmp, 7=tftp/transfer).

## Goals / Non-Goals

**Goals:**
- Menu rico em nós e grupos, invocando módulos existentes sem duplicar lógica.
- Resolução de credenciais: perfil salvo por IP → fallback pré-preenchimento.
- Invocação direta onde o host basta (Telnet, ICMP, SNMP walk); pré-preenchimento onde precisa de credenciais (SSH, Transfer).
- Isolar o dispatcher num helper novo para não inchar `main.py`.

**Non-Goals:**
- Não alterar o comportamento interno dos módulos existentes.
- Não criar novo armazenamento de credenciais.
- Não suportar scan multi-IP a partir de grupo (só o IP do pai).
- Não adicionar ações novas aos módulos (apenas invocação das existentes).

## Decisions

### D1: Sinais em vez de menu no item gráfico
`NodeItem`/`GroupNodeItem` param de construir menu; `contextMenuEvent` emite `context_menu_requested(device_or_group, screen_pos)` (e mantém `remove_requested` apenas como caminho interno). `TopologyScene` re-emite; `TopologyView` re-emite; `TopologyTab` conecta. Alternativa: construir o menu no próprio item — descartada: item gráfico não conhece o main window nem credenciais.

### D2: Back-reference do main window no TopologyTab
`TopologyTab(self.config)` → `TopologyTab(self.config, main_window=self)` (`main.py:468`). O tab guarda `self._main = main_window` e delega. Alternativa: signals pelo `SerialTerminalGUI` — descartada: acoplar `main.py` ao `cetuslib.topology` via signals duplica fiação.

### D3: Helper novo `cetuslib/topology/actions.py`
Classe `TopologyActions` com métodos estáticos/por instância:
- `show_node_menu(main_window, device, pos)` — constrói `QMenu` com Ping (primeira ação), submenus Access/Scan/SNMP/Transfer/Remover.
- `show_group_menu(main_window, group, pos)` — idem para grupo (IP do pai).
- Helpers internos: `_resolve_profile(main_window, ip)` → perfil SSH salvo cujo host == ip; `_invoke_ping`, `_invoke_ssh(main_window, device)`, `_invoke_scan(main_window, device, method)`, `_invoke_traceroute(main_window, device, method)`, `_invoke_snmp(main_window, device, qtype)`, `_invoke_transfer(main_window, device, proto)`.
`main.py` só ganha um delegador fino (`show_topology_node_menu`) que chama o helper. Alternativa: métodos no `SerialTerminalGUI` — descartada: infla o arquivo de 14k linhas.

### D4: Resolução de credenciais (perfil → fallback)
`_resolve_profile` busca em `main_window.config.get_ssh_profiles()` (JSON) um perfil com `host == device.ip`. Se achar:
- SSH/Telnet: preenche `ssh_host/port/username/password`, chama `connect_ssh()` (fluxo existente; senha ausente ainda pede dialog).
- Transfer SSH/SMB/FTP: preenche host/port/user/pass e chama `_ft_client_connect()`.
Sem perfil:
- SSH/Telnet: `switch_tab(0)` + preencher host + `connect_ssh()` (dialog de senha do próprio fluxo).
- Transfer SSH/FTP: `switch_tab(7)` + preencher host/port/protocolo, sem executar — usuário completa user/pass e clica CONNECT.
SMB/TFTP: o `FileConnectWorker` (`workers.py:1898`) só implementa modo cliente para SSH e FTP; SMB/TFTP são servidores. Logo o menu pré-preenche host + protocolo e navega, sem auto-conectar.

### D5: Invocação direta vs pré-preenchimento
- Direto (executa): `Ping` (abre `ping <ip>` no terminal nativo via `_launch_native_terminal`), Telnet (SSH se perfil com senha), `Traceroute > ICMP/TCP/UDP` (seta `traceroute_target_input` + `traceroute_current_method` + `_start_traceroute()`), `SNMP > Walk` (community do histórico ou `public`), Transfer SSH/FTP com perfil.
- Pré-preenchimento + navegar: SSH sem perfil, `SNMP > Get/GetNext` (precisa OID), Transfer SSH/FTP sem perfil, Transfer SMB/TFTP (modo cliente não implementado — `workers.py:1898`).
Motivo: Ping/Telnet/traceroute/walk só precisam do IP; os demais dependem de entrada do usuário.

### D6: Preset de portas para scan TCP/UDP
`DEFAULT_SCAN_PORTS = '22,23,80,443,3389,8080,8443,161'`. Ao invocar `Scan > TCP/UDP`, preencher `scan_ports_input` e `scan_network_input` com o IP, definir `scan_current_method`, chamar `_start_scan()`. Alternativa: prompt — descartada: usuário quer um clique.

### D7: Scan de grupo = IP único do pai
`show_group_menu` opera sobre `graph.devices[group.parent_id]`; `Scan` usa o IP desse device (scan de um único IP). Sem juntar membros.

### D8: Device sem IP
Se `device.ip` estiver vazio, a ação `Ping` e os submenus Access/Scan/SNMP/Transfer são adicionados desabilitados (`setEnabled(False)`); "Remover" permanece ativo.

### D9: Estilo do menu
Reusar o stylesheet dark dos menus existentes (padrão de `_show_settings_menu`, `main.py:499`) para consistência visual.

## Risks / Trade-offs

- [Ações invocam módulos com pré-preenchimento; o módulo pode exigir mais entrada] → não executar onde falta dado obrigatório (OID em Get, user/pass em transfer sem perfil); navegar para o módulo permite o usuário completar.
- [`connect_ssh` sem username falha] → Telnet não exige username; SSH sem perfil pré-preenche host e deixa o usuário digitar usuário antes de conectar? Decisão: pré-preenche host e usa o fluxo existente (que pede senha); username fica no campo. Risco baixo.
- [Escopo do menu de contexto cresce demais] → presets fixos (portas, OID default) evitam prompt; adições futuras são novos itens no helper.
- [Perfil salvo desatualizado (IP reutilizado)] → fallback natural: se `connect_ssh` falhar, o usuário é informado pelo fluxo existente; sem corrupção de dados.

## Migration Plan

- Aditivo: nenhum formato de arquivo muda; `NodeItem`/`GroupNodeItem` mantêm "Remover".
- Primeira execução: menu rico disponível imediatamente; nada a migrar.
- Rollback: reverter sinais para o menu mínimo antigo; módulos não são tocados.
- Deploy: regenerar `dist/cetus`.

## Open Questions

Nenhuma. Decisões fechadas: perfil → fallback (D4), direto vs prefill (D5), preset de portas (D6), grupo = IP único do pai (D7), devices sem IP desabilitados (D8), helper novo (D3).