# Tasks

## 1. Ciclo de vida do TopologyDiscoveryWorker

- [x] 1.1 Redefinir `self._worker = None` nos métodos `_on_finished` e `_on_failed` de `TopologyTab` em `balenolib/topology/tab.py`
- [x] 1.2 Proteger verificação `self._worker.isRunning()` em `start_discovery()` com `try/except RuntimeError` para limpar referências órfãs
- [x] 1.3 Proteger verificação `self._worker.isRunning()` em `shutdown()` com `try/except RuntimeError` para evitar erros ao fechar a aplicação

## 2. Validação

- [x] 2.1 Validar integridade sintática executando `python3 -m py_compile balenolib/topology/tab.py`
- [x] 2.2 Testar descobertas sucessivas verificando que uma segunda descoberta inicia sem crash
