# topology-drawio-layout Specification

## Purpose

Define a interface no padrão Studio/Draw.io para a aba de topologia, incluindo barra lateral retrátil à esquerda com seções accordion (Objetos, Camadas, Descoberta), barra superior de ações operacionais, histórico de Undo/Redo e ferramenta de busca rápida de dispositivos.

## Requirements

### Requirement: Barra lateral accordion à esquerda
O sistema SHALL posicionar a barra lateral à esquerda do canvas da topologia, estruturada em seções retráteis independentes (Accordion) para Objetos, Camadas e Descoberta.

#### Scenario: Alternar expansão de seção
- **WHEN** o usuário clica no cabeçalho de uma seção do accordion
- **THEN** a seção alterna entre expandida e colapsada, recolhendo ou exibindo seu conteúdo verticalmente

#### Scenario: Ocultar barra lateral
- **WHEN** o usuário aciona o botão de alternância do painel na barra superior
- **THEN** a barra lateral inteira é ocultada, expandindo o canvas para a largura total da janela

### Requirement: Seção de Objetos e Paleta
O sistema SHALL disponibilizar a paleta de dispositivos arrastáveis como a primeira seção da barra lateral.

#### Scenario: Arraste de equipamento
- **WHEN** o usuário arrasta um ícone de equipamento da seção de Objetos para o canvas
- **THEN** um novo nó correspondente à função selecionada é criado na coordenada onde o cursor foi solto

### Requirement: Seção de Descoberta retrátil
O sistema SHALL disponibilizar os controles de descoberta de rede dentro de uma seção colapsável da barra lateral, mantendo-a recolhida por padrão após uma varredura.

#### Scenario: Execução de descoberta a partir da barra lateral
- **WHEN** o usuário expande a seção de Descoberta, preenche os dados e clica em Iniciar Descoberta
- **THEN** o processo de varredura é executado atualizando o progresso e adicionando os dispositivos descobertos às camadas

### Requirement: Barra superior operacional
O sistema SHALL fornecer uma barra de ferramentas superior unificada contendo ações de arquivo (Salvar, PNG), conexão (Criar Link), navegação (Zoom +, Zoom -, 100%, Fit) e seletor de layout.

#### Scenario: Ajuste de zoom rápido
- **WHEN** o usuário clica no botão "100%" ou "Fit" na barra superior
- **THEN** o zoom da visão do mapa é imediatamente redefinido para a escala natural ou ajustado para enquadrar todos os elementos visíveis

#### Scenario: Alternância de modo de link manual
- **WHEN** o usuário clica no botão "Criar Link" na barra superior
- **THEN** o cursor muda para mira permitindo ligar dois dispositivos sequencialmente

### Requirement: Histórico de edição (Undo / Redo)
O sistema SHALL manter um histórico de ações no canvas suportando desfazer (Undo) e refazer (Redo) para movimentação de nós, adição de nós manuais e criação/exclusão de links.

#### Scenario: Desfazer movimentação de nó
- **WHEN** o usuário arrasta um nó para uma nova posição e aciona "Desfazer" (ou Ctrl+Z)
- **THEN** o nó retorna para a posição em que estava antes do movimento

#### Scenario: Refazer ação desfeita
- **WHEN** o usuário aciona "Refazer" (ou Ctrl+Y / Ctrl+Shift+Z) após um desfazer
- **THEN** a alteração é reaplicada na posição ou estado correspondente

### Requirement: Busca rápida de dispositivos e foco
O sistema SHALL incluir um campo de busca na barra superior que filtre dispositivos por IP, hostname, rótulo ou fabricante e permita centralizar a visualização.

#### Scenario: Destaque visual em tempo real
- **WHEN** o usuário digita um termo no campo de busca
- **THEN** os nós correspondentes recebem destaque visual no canvas

#### Scenario: Centralização com foco ao pressionar Enter
- **WHEN** o usuário pressiona a tecla Enter no campo de busca com um nó correspondente
- **THEN** a câmera do canvas é centralizada no dispositivo encontrado com ajuste confortável de zoom
