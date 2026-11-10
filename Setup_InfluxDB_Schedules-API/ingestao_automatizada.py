import argparse
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import influxdb_client
import pytz
from dotenv import load_dotenv
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

# --- 1. CONFIGURAÇÕES DO BANCO DE DADOS ---
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

URL = os.getenv("INFLUX_URL", "http://localhost:8086")
TOKEN = os.getenv("INFLUX_TOKEN")
ORG = os.getenv("INFLUX_ORG", "ufc_quixada")
BUCKET = os.getenv("INFLUX_BUCKET", "instrumentacao_2026")

if not TOKEN:
    raise RuntimeError("INFLUX_TOKEN não foi definido no arquivo .env")

# --- 2. MAPEAMENTO ASHRAE 55 ---
map_met = {
    'Sentado, estudando ou lendo': 1.0, 'Sentado, utilizando computador': 1.1,
    'Sentado, assistindo aula': 1.0, 'Sentado, conversando': 1.1,
    'Em pé, realizando atividade leve': 1.2, 'Sentado, escrevendo ou fazendo anotações': 1.0,
    'Sentado, conversando e usando o computador': 1.1
}

map_clo_sup = {
    'Regata': 0.08, 'Camiseta ou camisa de manga curta': 0.09, 'Camisa longa de manga curta': 0.09,
    'Camisa longa com manga curta': 0.09, 'camisa polo': 0.09, 'Camisa de manga longa': 0.15,
    'Camisa oversize': 0.10, 'Casaco ou moletom': 0.35
}

map_clo_inf = {
    'Short': 0.06, 'Bermuda': 0.11, 'Calça leve': 0.15,
    'Calça de tecido médio': 0.20, 'Calça tecido médio ': 0.20,
    'Calça de tecido pesado': 0.25, 'Calça jeans': 0.25
}

map_clo_add = {'Jaqueta': 0.36, 'Casaco ou moletom': 0.35, 'Não': 0.0}
map_clo_meias = {'Não': 0.0, 'Sim, meias curtas': 0.02, 'Sim, meias longas': 0.03}
map_clo_calcado = {'Sandália ou chinelo': 0.02, 'Tênis': 0.04, 'Sapato fechado': 0.04, 'Bota ': 0.10, 'Bota': 0.10}

# --- 3. PROCESSAMENTO DOS DADOS ---
# Usando o arquivo CSV que já está na sua pasta
CSV_PATH = ROOT_DIR / "Setup_InfluxDB_Schedules-API" / "Questionário de Percepção Térmica — Salas de Aula UFC Quixadá.csv"

df = pd.read_csv(CSV_PATH)

# Tratando a data para remover o 'GMT-3' e converter para formato temporal
df['Carimbo de data/hora'] = df['Carimbo de data/hora'].str.replace(' GMT-3', '')
df['Timestamp'] = pd.to_datetime(df['Carimbo de data/hora'], format='%Y/%m/%d %I:%M:%S %p')
df['Data'] = df['Timestamp'].dt.date
df['Hora'] = df['Timestamp'].dt.hour

# Mapeamento
df['Met_Calc'] = df['Qual atividade você realizou predominantemente nos últimos 30 minutos?'].map(map_met).fillna(1.0)
df['Clo_Calc'] = (
    df['Qual peça você utiliza na parte superior do corpo?'].map(map_clo_sup).fillna(0.09) +
    df['Qual peça você utiliza na parte inferior do corpo?'].map(map_clo_inf).fillna(0.15) +
    df['Você está utilizando alguma camada adicional sobre a peça principal da parte superior?'].map(map_clo_add).fillna(0.0) +
    df['Você está utilizando meias?'].map(map_clo_meias).fillna(0.0) +
    df['Qual tipo de calçado você está utilizando?'].map(map_clo_calcado).fillna(0.04)
)

col_zona = 'Em qual região da sala você está neste momento?'
df_grouped = df.groupby([col_zona, 'Data', 'Hora']).agg(
    met_medio=('Met_Calc', 'mean'),
    clo_medio=('Clo_Calc', 'mean'),
    ocupacao=('Carimbo de data/hora', 'count')
).reset_index()


# --- 4. SIMULAÇÃO OU INJEÇÃO NO INFLUXDB ---

parser = argparse.ArgumentParser(
    description="Processamento das respostas do questionário térmico."
)
parser.add_argument(
    "--gravar",
    action="store_true",
    help="Autoriza a gravação dos registros no InfluxDB."
)
args = parser.parse_args()

client = None
write_api = None

if args.gravar:
    print("Modo de gravação ativado.")
    client = influxdb_client.InfluxDBClient(
        url=URL, token=TOKEN, org=ORG
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
else:
    print("Modo de simulação: nenhum dado será gravado.")

try:
    for _, row in df_grouped.iterrows():
        # Fixando o fuso horário de Fortaleza
        dt_str = f"{row['Data']} {row['Hora']:02d}:00:00"
        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        dt_obj = pytz.timezone("America/Fortaleza").localize(dt_obj)
        timestamp_ms = int(dt_obj.timestamp() * 1000)

        zona = str(row[col_zona]).strip()

        p = (
            Point("schedules_r1_r6")
            .tag("zona", zona)
            .tag("origem", "questionario")
            .field("met", round(row["met_medio"], 2))
            .field("clo", round(row["clo_medio"], 2))
            .field("ocupacao", int(row["ocupacao"]))
            .time(
                timestamp_ms,
                write_precision=influxdb_client.WritePrecision.MS
            )
        )

        if args.gravar:
            write_api.write(bucket=BUCKET, org=ORG, record=p)

finally:
    if write_api is not None:
        write_api.close()
    if client is not None:
        client.close()

if args.gravar:
    print(f"Sucesso! {len(df_grouped)} registros gravados no InfluxDB.")
else:
    print(f"Simulação concluída: {len(df_grouped)} registros preparados.")
    print("\nPrévia dos registros:")
    print(
        df_grouped[
            [col_zona, "Data", "Hora", "met_medio", "clo_medio", "ocupacao"]
        ].to_string(index=False)
    )
