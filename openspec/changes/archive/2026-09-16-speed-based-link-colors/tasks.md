## 1. Cor por velocidade no EdgeItem

- [x] 1.1 Adicionar `speed_color(mbps)` e a cor laranja na paleta de `view.py`. Verificar com `python3 -m py_compile cetuslib/topology/gui/view.py`.
- [x] 1.2 Adicionar `EdgeItem.link_speed()` = `min` das duas interfaces (0 se nenhuma resolve). Verificar que retorna o menor valor quando as pontas divergem.
- [x] 1.3 Ajustar `EdgeItem._pen()`: down → vermelho sólido; senão `speed_color(link_speed())` tracejado animado. Verificar com o demo que cores mudam por velocidade.

## 2. Re-verificação de velocidade a cada minuto

- [x] 2.1 Adicionar `LldpCollector.poll_speed()` (ifHighSpeed + fallback ifSpeed). Verificar com `py_compile`.
- [x] 2.2 Em `TrafficMonitor`, re-verificar velocidade no mesmo bloco de 60s e emitir `speed_updated`. Verificar que o sinal só dispara após o intervalo.
- [x] 2.3 Adicionar `TopologyView.update_speeds()` aplicando `speed_mbps` + `refresh_state()`. Conectar `speed_updated` na tab. Verificar que a cor muda ao alterar a velocidade.

## 3. Legenda

- [x] 3.1 Adicionar legenda compacta (cores de velocidade + down + tracejado) ao `TopologyView`. Verificar visualmente no demo.

## 4. Integração e validação

- [x] 4.1 Atualizar o demo com interfaces de velocidades distintas (10G/1G/100M) e verificar as três cores + cinza desconhecido.
- [x] 4.2 Rodar `python3 -m py_compile` em `view.py`, `monitor.py`, `collector.py`, `models.py`, `tab.py`, `demo.py` e `openspec validate speed-based-link-colors`.
