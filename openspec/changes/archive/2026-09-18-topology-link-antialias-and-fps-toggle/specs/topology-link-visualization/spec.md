# Spec Delta

## ADDED Requirements

### Requirement: Terminação arredondada nos segmentos tracejados de links ativos
O sistema SHALL estilizar a caneta de desenho (pen) das conexões ativas com estilo de terminação arredondado (RoundCap) para suavizar a transição entre traços animados e eliminar degraus serrilhados.

#### Scenario: Desenho de link ativo tracejado
- **WHEN** uma linha de conexão ativa é desenhada na cena
- **THEN** a caneta de desenho utiliza estilo de terminação RoundCap nos segmentos do padrão tracejado
