import argparse
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import influxdb_client
from dotenv import load_dotenv
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 1. Configurações do banco de dados
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

URL = os.getenv("INFLUX_URL", "http://localhost:8086")
TOKEN = os.getenv("INFLUX_TOKEN")
ORG = os.getenv("INFLUX_ORG", "ufc_quixada")
BUCKET = os.getenv("INFLUX_BUCKET", "instrumentacao_2026")

# 2. Dados extraídos da Tabela 1 do Relatório (Zonas com respondentes/ocupação)
# Mapeando horários de referência: Manhã (10:00), Tarde 1 (13:30), Tarde 2 (15:30)
data_coleta = "2026-09-30" # Data base para os timestamps

schedules = [
    # Manhã (10h)
    {"zona": "R2", "hora": "10:00:00", "met": 1.05, "clo": 0.42, "ocupacao": 2},
    {"zona": "R5", "hora": "10:00:00", "met": 1.03, "clo": 0.44, "ocupacao": 4},
    {"zona": "R6", "hora": "10:00:00", "met": 1.05, "clo": 0.41, "ocupacao": 2},

    # Tarde 1 (13:30)
    {"zona": "R5", "hora": "13:30:00", "met": 1.04, "clo": 0.44, "ocupacao": 7},
    {"zona": "R6", "hora": "13:30:00", "met": 1.13, "clo": 0.51, "ocupacao": 4},

    # Tarde 2 (15:30)
    {"zona": "R1", "hora": "15:30:00", "met": 1.03, "clo": 0.62, "ocupacao": 6},
    {"zona": "R2", "hora": "15:30:00", "met": 1.03, "clo": 0.49, "ocupacao": 4},
    {"zona": "R5", "hora": "15:30:00", "met": 1.06, "clo": 0.43, "ocupacao": 10},
    {"zona": "R6", "hora": "15:30:00", "met": 1.00, "clo": 0.49, "ocupacao": 1}
]


# 3. Simulação ou injeção dos pontos no InfluxDB

parser = argparse.ArgumentParser(
    description="Processamento dos schedules extraídos do relatório."
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
    if not TOKEN:
        raise RuntimeError("INFLUX_TOKEN não foi definido no arquivo .env")

    print("Modo de gravação ativado.")
    client = influxdb_client.InfluxDBClient(
        url=URL, token=TOKEN, org=ORG
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
else:
    print("Modo de simulação: nenhum dado será gravado.")

try:
    for entrada in schedules:
        # Conversão para timestamp Unix em milissegundos
        dt_str = f"{data_coleta} {entrada['hora']}"
        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        dt_obj = dt_obj.replace(
            tzinfo=ZoneInfo("America/Fortaleza")
        )
        timestamp_ms = int(dt_obj.timestamp() * 1000)

        p = (
            Point("schedules_r1_r6")
            .tag("zona", entrada["zona"])
            .tag("origem", "relatorio")
            .field("met", float(entrada["met"]))
            .field("clo", float(entrada["clo"]))
            .field("ocupacao", int(entrada["ocupacao"]))
            .time(
                timestamp_ms,
                write_precision=influxdb_client.WritePrecision.MS
            )
        )

        if args.gravar:
            write_api.write(
                bucket=BUCKET,
                org=ORG,
                record=p
            )

finally:
    if write_api is not None:
        write_api.close()
    if client is not None:
        client.close()

if args.gravar:
    print(f"Sucesso! {len(schedules)} registros gravados no InfluxDB.")
else:
    print(f"Simulação concluída: {len(schedules)} registros preparados.")
    print("\nPrévia dos registros:")

    for entrada in schedules:
        print(
            f"Zona: {entrada['zona']} | "
            f"Data: {data_coleta} | "
            f"Hora: {entrada['hora']} | "
            f"MET: {entrada['met']} | "
            f"CLO: {entrada['clo']} | "
            f"Ocupação: {entrada['ocupacao']}"
        )
