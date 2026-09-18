# Proposal

## Why

Ao realizar uma nova descoberta de rede logo após a montagem da topologia, o Baleno fecha repentinamente com `RuntimeError: wrapped C/C++ object of type TopologyDiscoveryWorker has been deleted`. Isso ocorre porque o término da primeira descoberta invoca `deleteLater()` no worker, destruindo o objeto C++ no Qt, mas a referência `self._worker` em `TopologyTab` é mantida em memória, causando falha fatal ao chamar `self._worker.isRunning()` na descoberta seguinte ou no `shutdown()`.

## What Changes

- Redefinir explicitamente `self._worker = None` nos callbacks de término (`_on_finished`) e de falha (`_on_failed`) em `TopologyTab`.
- Adicionar proteção defensiva em `start_discovery()` e `shutdown()` para tratar possíveis exceções de runtime caso o objeto C++ subjacente tenha sido destruído antes da verificação de `isRunning()`.
- Garantir que o botão de descoberta e o estado da interface permaneçam consistentes entre sucessivas execuções de descoberta sem crashes.

## Capabilities

### New Capabilities

- `topology-discovery-lifecycle`: Garante o gerenciamento robusto do ciclo de vida do worker de descoberta de topologia, assegurando que sucessivas descobertas e o encerramento da aplicação ocorram sem referências a objetos C++ destruídos.

### Modified Capabilities

<!-- Nenhuma especificação existente teve seus requisitos de comportamento alterados. -->

## Impact

- `balenolib/topology/tab.py`: Métodos `start_discovery`, `_on_finished`, `_on_failed` e `shutdown` atualizados para limpar `self._worker = None` e proteger chamadas `.isRunning()`.
- Sem quebras de compatibilidade com modelos de dados, configurações ou APIs externas.
