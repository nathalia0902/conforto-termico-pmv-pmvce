# Complemento de conforto — Grupo 1

Copie os arquivos para a pasta do projeto existente. Não substitua os scripts de ingestão.

1. Crie/ative um ambiente: `python3 -m venv .venv` e `source .venv/bin/activate` (Linux).
2. Instale: `python -m pip install -r requirements-conforto.txt`.
3. Execute: `python calcular_conforto.py`.
4. Informe zona, data/hora em Fortaleza, met, clo, temperatura interna, umidade, temperatura externa, velocidade e, opcionalmente, coeficiente e.
5. Sem coeficiente e, somente PMV/PPD. Não invente e: justifique com o professor/literatura. O ePMV de Fanger/Toftum foi proposto para ambientes não climatizados; nesta sala seu uso é exploratório.
6. Para gravar, configure INFLUX_TOKEN (obrigatório), INFLUX_URL, INFLUX_ORG e INFLUX_BUCKET e execute `python calcular_conforto.py --gravar`.

O script usa a API nativa do InfluxDB, measurement conforto_calculado e timestamp Unix em milissegundos. Não testa conexão nem grava sem --gravar. Não altere históricos antigos para forçar coincidência temporal.

Entradas: temperatura/umidade devem ser medidas da zona e período estudados; met/clo podem ser individuais ou um perfil representativo explicitamente identificado. Se usar médias, o índice descreve o perfil médio, não a média dos índices individuais. Não compare uma resposta de setembro com uma condição ambiental de novembro como se fossem simultâneas.

Hipóteses do exercício: temperatura radiante média igual à temperatura externa e velocidade ambiente inicialmente zero. Temperatura radiante depende das superfícies ao redor do ocupante: igualá-la ao ar externo é simplificação, não medição. O jato do split pode alterar a velocidade junto aos ocupantes; avaliar com anemômetro ou comparar cenários explícitos. A velocidade de saída do aparelho não representa automaticamente a velocidade na carteira.

A biblioteca corrige velocidade relativa e isolamento dinâmico. O ePMV usa a correção metabólica interna da biblioteca e o fator e; não é apenas multiplicar o PMV inicial por e. PPD retornado pertence ao PMV convencional, não ao ePMV.

Teste didático (não são dados coletados): ta=25, umidade=55, externa=30, met=1.05, clo=0.42, v=0, e=0.7. O e=0.7 serve apenas para testar, não é uma escolha metodológica para o projeto.

Remova `.field("temperatura", 0.0)`, `.field("umidade", 0.0)` e `.field("epmv", 0.0)` das futuras ingestões do script antigo. Dados inexistentes não devem ser tratados como zero. Não apague dados do banco sem verificar o que já foi preenchido.

Integração automática posterior: consultar sensores e schedules no InfluxDB, associar por zona e janela temporal declarada, chamar calcular(...), e gravar em conforto_calculado. Faltam os nomes reais dos measurements/campos dos sensores para implementar essa associação sem adivinhações.

Arquivos recebidos do Grupo 2: relatórios EnergyPlus/OpenStudio e arquivo climático EPW de Quixeramobim; não foi identificada exportação da rede real. A data de execução do EnergyPlus não é data de coleta dos sensores.

Fontes:
- https://pythermalcomfort.readthedocs.io/en/stable/_modules/pythermalcomfort/models/pmv_e.html
- https://cbe-berkeley.gitbook.io/fans-guidebook/full-guidebook/elevated-air-speed-and-thermal-comfort
- https://cbe-berkeley.gitbook.io/thermal-comfort-tool/documentation/pmv
