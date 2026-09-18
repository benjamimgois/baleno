# Design

## Context

No módulo `balenolib/topology/tab.py`, o início de uma descoberta de rede instancia `TopologyDiscoveryWorker` (um `QThread`) e conecta seu sinal `finished` tanto ao callback de visualização `_on_finished` quanto ao slot Qt `deleteLater`. Quando a descoberta termina, o Qt agenda a desalocação do objeto C++ subjacente. Contudo, o atributo Python `self._worker` permanece referenciando o invólucro (wrapper) do objeto já destruído. Qualquer chamada posterior a métodos C++ (como `self._worker.isRunning()`) levanta `RuntimeError: wrapped C/C++ object ... has been deleted`.

## Goals / Non-Goals

**Goals:**
- Garantir que `self._worker` seja redefinido para `None` assim que a execução do worker terminar (tanto no fluxo de sucesso quanto no de falha).
- Proteger chamadas a `self._worker.isRunning()` contra exceções de objetos já desalocados pelo Qt em `start_discovery()` e `shutdown()`.
- Manter o comportamento de concorrência: impedir que duas descobertas rodem simultaneamente se um worker realmente ainda estiver em execução.

**Non-Goals:**
- Não reescrever a engine de descoberta ou de coleta SNMP.
- Não alterar a lógica de merge de topologias ou de camadas.

## Decisions

### 1. Limpeza de referência em `_on_finished` e `_on_failed`
- **Decisão**: Atribuir `self._worker = None` dentro de `_on_finished` e `_on_failed`.
- **Racional**: Libera o ponteiro Python para o worker que terminou. Em chamadas subsequentes a `start_discovery()`, a checagem `if self._worker is not None` avaliará como `False`, permitindo a criação de um novo worker limpo.
- **Alternativa descartada**: Deixar a referência viva e confiar apenas no garbage collector sem `None`, o que ainda manteria o wrapper apontando para C++ deletado enquanto `self._worker` não fosse reatribuído.

### 2. Tratamento defensivo em `start_discovery()` e `shutdown()`
- **Decisão**: Envolver a verificação de execução do worker em um bloco defensivo:
  ```python
  if self._worker is not None:
      try:
          if self._worker.isRunning():
              return
      except RuntimeError:
          self._worker = None
  ```
- **Racional**: Protege de forma resiliente contra condições de corrida no loop de eventos do Qt onde o objeto C++ possa ser desalocado antes de uma checagem. Caso o objeto tenha sido deletado, a referência é imediatamente sanitizada para `None`.

## Risks / Trade-offs

- **[Risco]** Chamada concorrente a `start_discovery` enquanto o worker ainda está em execução.
  → **Mitigação**: O botão `discover_btn` já é desativado no início da descoberta (`setEnabled(False)`) e reativado somente ao final (`setEnabled(True)`). A verificação com `isRunning()` serve como segunda barreira defensiva.
