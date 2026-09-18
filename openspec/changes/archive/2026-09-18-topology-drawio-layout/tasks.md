# Tasks

## 1. Componente Accordion e Barra Lateral à Esquerda

- [x] 1.1 Criar `AccordionWidget` e `CollapsibleSection` em `balenolib/topology/gui/accordion.py` e verificar renderização
- [x] 1.2 Mover a barra lateral para a esquerda do canvas da topologia em `tab.py` e verificar posicionamento
- [x] 1.3 Montar as seções do Accordion na ordem: Objetos (1º), Camadas (2º), Descoberta (3º)
- [x] 1.4 Integrar formulário de Descoberta dentro da seção 3 do Accordion (recolhida por padrão)

## 2. Barra Superior Operacional (Draw.io Style)

- [x] 2.1 Reestruturar a topbar em régua de ferramentas compacta (~36px) com botão toggle `[☷ Painel]`
- [x] 2.2 Adicionar botões de ação: Salvar, Exportar PNG e Criar Link (com atalho Esc para cancelar)
- [x] 2.3 Integrar controles de zoom na barra superior: Zoom In (+), Zoom Out (-), 100% (reset) e Zoom Fit (⛶)
- [x] 2.4 Integrar seletor de layout na barra superior

## 3. Busca Rápida de Dispositivos e Foco

- [x] 3.1 Adicionar campo de busca rápida com ícone de lupa na extremidade direita da barra superior
- [x] 3.2 Implementar método de filtro na `TopologyView` destacando visualmente os nós correspondentes a IP, hostname ou vendor
- [x] 3.3 Implementar método `focus_device` na `TopologyView` para centralizar a câmera com zoom confortável no nó ao pressionar Enter

## 4. Histórico de Edição (Undo / Redo)

- [x] 4.1 Criar módulo `balenolib/topology/undo.py` com `TopologyUndoStack` e comandos (`MoveNodeCommand`, `AddDeviceCommand`, `AddLinkCommand`)
- [x] 4.2 Conectar botões de Desfazer/Refazer na topbar aos atalhos `Ctrl+Z` e `Ctrl+Y` / `Ctrl+Shift+Z`
- [x] 4.3 Integrar registro de movimentação de nós e criação/exclusão manual no `TopologyView` com a pilha de undo

## 5. Empacotamento e Verificação

- [x] 5.1 Adicionar `accordion.py` e `undo.py` ao `MODULE_ORDER` em `scripts/bundle-monolith.py`
- [x] 5.2 Executar `python3 -m py_compile` em todos os módulos e gerar monólito em `dist/baleno`
- [x] 5.3 Testar: expansão e colapso das seções do accordion e execução de discovery a partir da sidebar
- [x] 5.4 Testar: botões de zoom, reset 100%, fit e toggle da barra lateral na esquerda
- [x] 5.5 Testar: busca rápida com filtro em tempo real e foco suave via tecla Enter
- [x] 5.6 Testar: desfazer e refazer movimentação de nó com Ctrl+Z e Ctrl+Y
