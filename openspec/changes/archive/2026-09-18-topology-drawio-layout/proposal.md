# Proposal

## Why

A aba de topologia atual mantém a descoberta e ações de visualização divididas de forma pouco prática, consumindo espaço útil vertical e dificultando o fluxo natural de modelagem de rede. Inspirando-se no padrão consagrado pelo Draw.io, mover a barra lateral para a esquerda com seções retráteis (Accordion: Objetos, Camadas e Descoberta) e unificar as ferramentas de edição no topo (Salvar, Exportar, Undo/Redo, Link, Zoom e Busca rápida) otimiza o espaço da tela e torna a experiência de uso mais fluida, limpa e profissional.

## What Changes

- **Barra lateral à esquerda com seções retráteis (Accordion)**:
  - **Seção 1: Objetos**: Paleta com ícones de dispositivos arrastáveis no topo imediato para facilitar a modelagem manual.
  - **Seção 2: Camadas**: Árvore hierárquica estilo GIMP com visibilidade por olho (`👁`), contadores de nós e menu de contexto (*Solo*, *Fit*, *Remover*).
  - **Seção 3: Descoberta (Discovery)**: Formulário recolhível contendo rede CIDR, nome da camada, popover SNMP, botão *Discover*, progresso e status.
- **Barra superior operacional estilo Draw.io**:
  - Ações rápidas: `[☷ Painel]` (abrir/fechar sidebar), `[💾 Salvar]`, `[📷 Exportar PNG]`.
  - Histórico de edição: `[↶ Desfazer]` (Ctrl+Z) e `[↷ Refazer]` (Ctrl+Y).
  - Ferramenta de conexão: `[⚡ Criar Link]`.
  - Controles de zoom: `[-]`, `[ 100% ]` (reset), `[+]`, `[⛶ Fit]`.
  - Seletor de layout: dropdown direto `[ Layout: Tree ▾ ]`.
  - **Busca rápida de dispositivos / IP**: Campo de busca com destaque visual em tempo real no canvas e centralização/zoom suave ao pressionar Enter.
- **Sistema de Undo / Redo (`QUndoStack`)**:
  - Histórico para movimentação de nós no canvas, inserção de nós manuais e criação/remoção de links.

## Capabilities

### New Capabilities
- `topology-drawio-layout`: Layout Studio estilo Draw.io com barra lateral accordion à esquerda (Objetos, Camadas e Descoberta), barra superior de ações operacionais rápidas, suporte a Undo/Redo e busca rápida com foco no nó.

### Modified Capabilities
<!-- Nenhuma especificação anterior teve seus requisitos alterados. -->

## Impact

- `balenolib/topology/tab.py`: Reorganização do layout principal (sidebar accordion à esquerda, topbar de ações e busca rápida).
- `balenolib/topology/gui/view.py`: Suporte a busca de dispositivos com halo de destaque e centralização com zoom (`focus_device`), integração com `QUndoStack`.
- `balenolib/topology/gui/accordion.py`: Novo componente `AccordionWidget` / `CollapsibleSection` para a barra lateral.
- `balenolib/topology/undo.py`: Comandos de histórico para mover nós, adicionar nós e conectar links.
- `scripts/bundle-monolith.py`: Inclusão dos novos módulos no empacotamento monólito.
