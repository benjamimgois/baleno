# Spec Delta

## ADDED Requirements

### Requirement: Modos de descoberta básico e profundo
O sistema SHALL disponibilizar no formulário de descoberta a seleção entre modo Profundo (ICMP + LLDP) e modo Básico (apenas ICMP), adaptando a interface e o fluxo de coleta de acordo com a opção escolhida.

#### Scenario: Execução em modo básico (apenas ICMP)
- **WHEN** o usuário seleciona o modo Básico (ICMP) e inicia a descoberta
- **THEN** o sistema realiza apenas a sondagem de alcance ICMP, cadastra todos os endereços IP responsivos como nós com papel padrão `Host` na camada informada e conclui a varredura sem realizar consultas SNMP ou busca de vizinhos LLDP

#### Scenario: Execução em modo profundo (ICMP + LLDP)
- **WHEN** o usuário seleciona o modo Profundo (ICMP + LLDP) e inicia a descoberta
- **THEN** o sistema executa a varredura completa de alcance ICMP, consultas SNMP MIB-2 e IF-MIB, e expansão de vizinhos LLDP para descoberta de enlaces e hierarquia de saltos

#### Scenario: Desabilitação de controles SNMP no modo básico
- **WHEN** o usuário seleciona o modo Básico de descoberta
- **THEN** os controles de configuração de credenciais SNMP tornam-se desabilitados na interface com indicação visual de que não são necessários

### Requirement: Personalização e persistência de cores de camadas
O sistema SHALL permitir associar uma cor a cada camada de rede, persistindo as cores no arquivo de mapa e exibindo identificadores coloridos na árvore de camadas.

#### Scenario: Seleção de cor durante a criação da camada
- **WHEN** o usuário configura uma descoberta informando nome de camada
- **THEN** o sistema permite selecionar uma cor para a camada a partir de uma paleta predefinida ou diálogo seletor de cor personalizada

#### Scenario: Herança de cor por subcamadas de saltos LLDP
- **WHEN** uma descoberta profunda cria subcamadas por profundidade de salto (ex.: `Rede-A-2`)
- **THEN** as subcamadas herdam automaticamente a cor atribuída à camada principal do grupo

#### Scenario: Alteração de cor via menu de contexto da árvore de camadas
- **WHEN** o usuário clica com o botão direito sobre uma camada ou grupo na árvore de camadas e seleciona "Set Layer Color"
- **THEN** um diálogo seletor de cor é exibido e a nova cor é aplicada imediatamente à camada, atualizando a árvore e os nós correspondentes no canvas

#### Scenario: Persistência de cores no mapa
- **WHEN** o mapa é salvo em disco
- **THEN** o dicionário de cores de camadas é persistido sob a chave `layer_colors` no JSON e restaurado na reinicialização

### Requirement: Indicador visual da cor da camada nos dispositivos
O sistema SHALL exibir no canvas uma referência visual da cor da camada no ícone de cada dispositivo pertencente a ela.

#### Scenario: Renderização de anel de cor ao redor do ícone
- **WHEN** um dispositivo pertence a uma camada que possui cor definida
- **THEN** o círculo do ícone do dispositivo no canvas é renderizado com um anel de destaque com a cor da camada
