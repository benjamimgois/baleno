## ADDED Requirements

### Requirement: Persistir camadas nomeadas
O sistema SHALL persistir, no arquivo do mapa, as camadas nomeadas a que cada dispositivo pertence, restaurando-as ao recarregar o mapa.

#### Scenario: Camadas salvas e restauradas
- **WHEN** um dispositivo pertence a camadas nomeadas (ex.: "Rede-A" e "Rede-A-2") e o mapa é salvo
- **THEN** ao recarregar o mapa, o dispositivo volta a pertencer às mesmas camadas

#### Scenario: Arquivo antigo sem camadas
- **WHEN** um mapa persistido no formato anterior não possui o campo de camadas
- **THEN** o dispositivo é carregado sem camadas (e é tratado como visível por padrão), sem erro
