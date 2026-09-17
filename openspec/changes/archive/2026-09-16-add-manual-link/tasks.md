## 1. Ícone "Link" e modo na cena

- [x] 1.1 Adicionar `LinkButton(QToolButton)` (toggle, ícone desenhado programaticamente) e inseri-lo como primeiro item da aba Objects em `tab.py`; verificar com `python3 -m py_compile cetuslib/topology/tab.py`
- [x] 1.2 Adicionar `TopologyScene.set_link_mode(on)` com `_link_mode`/`_link_source` e cursor de cruz no view quando ativo; verificar compilação de `cetuslib/topology/gui/view.py`
- [x] 1.3 Ligar o `LinkButton` ao modo (clicar alterna, Esc/vazio/mesmo objeto cancela); verificar manualmente via `python3 -m cetuslib.topology` que entrar/sair do modo funciona

## 2. Seleção de endpoints e destaque

- [x] 2.1 Adicionar `mousePressEvent` em `NodeItem` e `GroupNodeItem` que, em modo link, emite o clique (source ou target) em vez de selecionar; verificar compilação
- [x] 2.2 Adicionar destaque amarelo forte (`_link_highlight`) no `paint` de `NodeItem` e `GroupNodeItem`; verificar renderização na demo
- [x] 2.3 Desenhar linha tracejada de preview do source até o cursor (item temporário atualizado em `mouseMoveEvent`); verificar que some ao cancelar/concluir

## 3. Diálogo de configuração

- [x] 3.1 Criar `LinkCreationDialog` em `cetuslib/topology/gui/detail.py` com listas de interfaces esq/dir (ou `QLineEdit` livre quando sem interfaces) e combobox de velocidade com padrão Auto; verificar compilação
- [x] 3.2 Abrir o diálogo após o segundo clique e devolver portas + velocidade escolhidas; verificar manualmente com dois dispositivos

## 4. Criação, validação e persistência do link

- [x] 4.1 Adicionar `TopologyScene.add_manual_link(...)` criando `PortLink` + `EdgeItem`, com checagem de duplicata via `PortLink.key()` e self-loop; verificar compilação
- [x] 4.2 Extrair helper único de offset de links paralelos e usá-lo em `set_graph`, `set_graph_from_persisted` e `add_manual_link` (corrige divergência atual); verificar que links paralelos renderizam sem sobreposição
- [x] 4.3 Exibir mensagem de erro para link duplicado e chamar `_schedule_save()` ao criar link; verificar persistência recarregando o mapa

## 5. Grupo ↔ dispositivo e verificação final

- [x] 5.1 Suportar grupo como endpoint resolvendo para `GroupNodeItem.parent_id`, com porta livre no lado do grupo; verificar manualmente link grupo→dispositivo
- [x] 5.2 Rodar `python3 -m py_compile` em todos os arquivos alterados, regenerar `dist/cetus` com `python3 scripts/bundle-monolith.py` e validar com `openspec validate add-manual-link`
