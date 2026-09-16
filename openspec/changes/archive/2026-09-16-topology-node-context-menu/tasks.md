# Tasks: topology-node-context-menu

## 1. Fiação de sinais no view

- [x] 1.1 `NodeItem.contextMenuEvent` passa a emitir `context_menu_requested(device, screen_pos)` (e mantém `remove_requested` internamente); `TopologyScene` e `TopologyView` re-emitem o novo sinal. Verificar com `python3 -m py_compile cetuslib/topology/gui/view.py`
- [x] 1.2 `GroupNodeItem` ganha `context_menu_requested(group, screen_pos)` emitido no `contextMenuEvent`; `TopologyScene` re-emite. Verificar com py_compile

## 2. Back-reference do main window

- [x] 2.1 `TopologyTab.__init__` aceita `main_window=None` e guarda `self._main`. `main.py:468` passa `main_window=self`. Verificar instanciando `TopologyTab(config, main_window=...)` sem erro

## 3. Helper `cetuslib/topology/actions.py`

- [x] 3.1 Criar `TopologyActions` com `show_node_menu(main_window, device, pos)` e `show_group_menu(main_window, group, pos)` construindo `QMenu` dark com submenus Access/Scan/SNMP/Transfer/Remover (estilo de `_show_settings_menu`). Verificar abrindo menu headless (offscreen) sobre nó e grupo
- [x] 3.2 `_resolve_profile(main_window, ip)`: busca em `config.get_ssh_profiles()` um perfil com `host == ip`. Verificar com perfil fake
- [x] 3.3 `_invoke_ssh(main_window, device)`: perfil → `connect_ssh()`; sem perfil → `switch_tab(0)` + prefill host + `connect_ssh()`. Verificar que `ssh_host`/`ssh_current_protocol` são setados
- [x] 3.4 `_invoke_scan(main_window, device, method)`: prefill `scan_network_input`=IP, preset `DEFAULT_SCAN_PORTS` em TCP/UDP, `scan_current_method`, `_start_scan()`. Verificar que o scan dispara com alvo único
- [x] 3.5 `_invoke_snmp(main_window, device, qtype)`: prefill host, community do histórico (ou `public`), tipo, OID default para walk; `execute_snmp_query()` para walk, navegação para get/getnext. Verificar walk executando com host preenchido
- [x] 3.6 `_invoke_transfer(main_window, device, proto)`: perfil → prefill user/pass + `_ft_client_connect()`; sem perfil → `switch_tab(7)` + prefill host/port/protocolo; TFTP direto. Verificar prefill de `_ft_host_input`/`_ft_protocol`
- [x] 3.7 Disabled: device sem IP → submenus de rede `setEnabled(False)`. Verificar com device manual sem IP

## 4. Integração e validação

- [x] 4.1 `TopologyTab` conecta os sinais `context_menu_requested` de nós e grupos ao helper. Verificar com teste headless simulando evento de contexto
- [x] 4.2 "Remover" continua funcional no novo menu. Verificar removendo nó via menu
- [x] 4.3 Regressão: `python3 -m py_compile cetuslib/topology/gui/view.py cetuslib/topology/tab.py cetuslib/topology/actions.py` e regenerar `dist/cetus` via `python3 scripts/bundle-monolith.py`
- [x] 4.4 Teste manual: nó descoberto → Access>SSH abre terminal; Scan>ICMP varre o IP; SNMP>Walk roda; grupo → Scan varre IP do pai; nó sem IP → menus cinza