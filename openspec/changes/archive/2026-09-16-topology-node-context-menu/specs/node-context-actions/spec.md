# node-context-actions

## Purpose

Permitir que o usuário invoque, em um clique, qualquer módulo do Cetus (Access, Scan, SNMP, Transfer) a partir do menu de contexto de um elemento do mapa de topologia, com o host pré-preenchido e credenciais resolvidas automaticamente quando possível.

## ADDED Requirements

### Requirement: Menu de contexto em nós
O sistema SHALL exibir, ao clicar com o botão direito em um `NodeItem` do mapa, um menu de contexto com a ação `Ping`, os submenus `Access`, `Scan`, `Traceroute`, `SNMP` e `Transfer` e a ação `Remover`.

#### Scenario: Menu aparece no nó
- **WHEN** o usuário clica com o botão direito em um nó do mapa
- **THEN** um menu de contexto é exibido com a ação Ping, os submenus Access, Scan, Traceroute, SNMP, Transfer e a ação Remover

### Requirement: Ação Ping
A primeira opção do menu de contexto SHALL ser `Ping`, que dispara um ping para o IP do device no terminal padrão do sistema.

#### Scenario: Ping no terminal do sistema
- **WHEN** o usuário clica em `Ping` em um device com IP
- **THEN** o terminal padrão do sistema abre executando `ping <ip>`

#### Scenario: Ping sem IP
- **WHEN** o device não possui IP
- **THEN** a opção `Ping` é exibida desabilitada

### Requirement: Ações Access (SSH/Telnet)
O submenu `Access` SHALL oferecer `SSH` e `Telnet`, que abrem o terminal do Cetus conectado ao IP do device.

#### Scenario: SSH via perfil salvo
- **WHEN** o usuário clica em `Access > SSH` em um device cujo IP corresponde a um perfil SSH salvo
- **THEN** o terminal do Cetus abre e conecta usando as credenciais do perfil

#### Scenario: SSH sem perfil salvo
- **WHEN** o usuário clica em `Access > SSH` em um device sem perfil salvo correspondente
- **THEN** o Cetus navega para o módulo SSH com o host pré-preenchido e o fluxo de conexão existente pede a senha

#### Scenario: Telnet direto
- **WHEN** o usuário clica em `Access > Telnet` em um device com IP
- **THEN** o terminal do Cetus abre e conecta via Telnet ao IP do device

#### Scenario: Nó sem IP
- **WHEN** o device não possui IP (objeto manual da paleta)
- **THEN** os submenus de rede (Access, Scan, SNMP, Transfer) são exibidos desabilitados

### Requirement: Ações Scan (TCP/UDP)
O submenu `Scan` SHALL oferecer `TCP` e `UDP`, que invocam o IP Scanner do Cetus com o IP do device como alvo.

#### Scenario: Scan TCP/UDP com portas padrão
- **WHEN** o usuário clica em `Scan > TCP` ou `Scan > UDP`
- **THEN** o IP Scanner inicia um scan usando o preset padrão de portas (`22,23,80,443,3389,8080,8443` + `161`)

### Requirement: Ações Traceroute (ICMP/TCP/UDP)
O submenu `Traceroute` SHALL oferecer `ICMP`, `TCP` e `UDP`, que invocam o módulo de traceroute do Cetus com o IP do device como alvo.

#### Scenario: Traceroute direto
- **WHEN** o usuário clica em `Traceroute > ICMP`, `TCP` ou `UDP` em um device com IP
- **THEN** o módulo de traceroute inicia o traçado do IP do device usando o método selecionado

### Requirement: Ações SNMP
O submenu `SNMP` SHALL oferecer `Walk`, `Get` e `GetNext`, que invocam o módulo SNMP com o host pré-preenchido.

#### Scenario: Walk direto
- **WHEN** o usuário clica em `SNMP > Walk` em um device com IP
- **THEN** o módulo SNMP executa um walk do MIB-2 no IP do device usando a community do histórico (ou `public`)

#### Scenario: Get com OID
- **WHEN** o usuário clica em `SNMP > Get`
- **THEN** o módulo SNMP navega com o host pré-preenchido, permitindo ao usuário informar o OID antes de executar

### Requirement: Ações Transfer (SSH/SMB/FTP/TFTP)
O submenu `Transfer` SHALL oferecer `SSH`, `SMB`, `FTP` e `TFTP`, que abrem o módulo de transferência de arquivos com o host pré-preenchido.

#### Scenario: Transfer via perfil
- **WHEN** o usuário clica em `Transfer > SSH` e existe perfil SSH salvo para o IP
- **THEN** o módulo de transferência pré-preenche host e usuário com os dados do perfil

#### Scenario: Transfer sem perfil
- **WHEN** o usuário clica em `Transfer > SSH` sem perfil correspondente
- **THEN** o módulo de transferência navega com o host pré-preenchido para o usuário completar credenciais

### Requirement: Menu de contexto em grupos
O sistema SHALL exibir, ao clicar com o botão direito em um `GroupNodeItem`, um menu de contexto com as mesmas ações, operando sobre o IP do device pai do grupo (ping e scan de um único IP).

#### Scenario: Ping do IP do grupo
- **WHEN** o usuário clica em `Ping` no menu de um grupo
- **THEN** o terminal padrão do sistema abre executando `ping <ip>` do device pai do grupo

### Requirement: Ação Remover preservada
O menu de contexto SHALL manter a ação `Remover` para nós.

#### Scenario: Remover continua disponível
- **WHEN** o usuário clica com o botão direito em um nó e seleciona `Remover`
- **THEN** o nó é removido do mapa como hoje, com salvamento automático