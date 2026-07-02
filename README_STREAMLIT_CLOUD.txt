DASHBOARD MTGÁS - VENDAS DE GÁS NATURAL (GN)
Versão adaptada para Streamlit Community Cloud

ESTRUTURA DO PROJETO

mtgas_streamlit_cloud/
├── app.py
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── assets/
│   └── logo_mtgas.png
└── data/
    ├── entradas_vendas_mensais.csv
    ├── entradas_vendas_diarias.csv
    └── configuracoes.csv

COMO PUBLICAR NO STREAMLIT COMMUNITY CLOUD

1. Crie um repositório no GitHub, por exemplo:
   mtgas-dashboard-gn

2. Envie todos os arquivos desta pasta para o repositório.
   O arquivo app.py deve ficar na raiz do repositório.

3. Acesse o Streamlit Community Cloud.

4. Clique em New app.

5. Selecione:
   Repository: mtgas-dashboard-gn
   Branch: main
   Main file path: app.py

6. Clique em Deploy.

COMO ATUALIZAR OS DADOS

Nesta versão gratuita/cloud, os dados são lidos dos arquivos CSV dentro da pasta data.
Para atualizar os dados, edite os CSVs no GitHub e salve o commit.
O Streamlit Cloud irá atualizar o app após o redeploy/atualização do repositório.

Arquivos principais:

1. data/entradas_vendas_mensais.csv
   Usado para os indicadores mensais, ranking, participação e acumulado anual.

2. data/entradas_vendas_diarias.csv
   Usado para total vendido hoje e evolução diária dos últimos 30 dias.

3. data/configuracoes.csv
   Usado para meta anual, fonte dos dados e data/hora de atualização.

ATENÇÃO SOBRE SCADA/API

O Streamlit Community Cloud não acessará diretamente sistemas internos da MTGÁS protegidos por firewall, salvo se houver uma API pública/segura disponível.
Para SCADA/API interna, o caminho recomendado é servidor interno, VPN ou proxy reverso corporativo com HTTPS e autenticação.

TESTE LOCAL

Para testar antes de publicar:

pip install -r requirements.txt
streamlit run app.py

