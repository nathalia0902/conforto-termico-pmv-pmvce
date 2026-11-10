import argparse
import json
import math
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
from zoneinfo import ZoneInfo
from pythermalcomfort.models import pmv_ppd_iso, pmv_e
from pythermalcomfort.environment import v_relative
from pythermalcomfort.clothing import clo_dynamic_iso


def calcular(ta, rh, te, met, clo, v, e=None):
    valores = [ta, rh, te, met, clo, v]
    if not all(math.isfinite(x) for x in valores):
        raise ValueError('Todos os dados devem ser números finitos.')
    if not (0 <= rh <= 100 and met > 0 and clo > 0 and v >= 0):
        raise ValueError('Confira umidade (0–100), met/clo positivos e velocidade não negativa.')
    if e is not None and not (math.isfinite(e) and 0 < e <= 1):
        raise ValueError('Coeficiente de expectativa deve estar entre 0 e 1, excluindo 0.')
    vr = float(v_relative(v=v, met=met))
    cd = float(clo_dynamic_iso(clo=clo, met=met, v=v))
    entradas = dict(tdb=ta, tr=te, vr=vr, rh=rh, met=met, clo=cd)
    base = pmv_ppd_iso(**entradas)
    if not all(math.isfinite(float(x)) for x in [base.pmv, base.ppd]):
        raise ValueError('Entradas/resultado fora dos limites do modelo. Não gravado; revise os dados e o método.')
    r = dict(temperatura_ar=ta, umidade=rh, temperatura_externa=te,
             temperatura_radiante_assumida=te, met=met, clo=clo,
             clo_dinamico=cd, velocidade_ar=v, velocidade_relativa=vr,
             pmv=float(base.pmv), ppd=float(base.ppd))
    if e is not None:
        epmv = float(pmv_e(**entradas, e_coefficient=e).e_pmv)
        if not math.isfinite(epmv):
            raise ValueError('ePMV fora dos limites do modelo. Não gravado.')
        r.update(epmv=epmv, coeficiente_expectativa=e)
    return r


def numero(rotulo):
    return float(input(rotulo).strip().replace(',', '.'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gravar', action='store_true')
    args = ap.parse_args()
    zona = input('Zona (R1 a R6): ').strip().upper()
    if zona not in [f'R{i}' for i in range(1, 7)]:
        raise ValueError('Zona inválida.')
    dt = datetime.strptime(input('Data/hora local dos dados (AAAA-MM-DD HH:MM): ').strip(),
                           '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('America/Fortaleza'))
    met = numero('Met do questionário ou perfil da zona: ')
    clo = numero('Clo do questionário ou perfil da zona: ')
    ta = numero('Temperatura interna medida (°C): ')
    rh = numero('Umidade interna medida (%): ')
    te = numero('Temperatura externa no mesmo período (°C): ')
    v = numero('Velocidade do ar (m/s; 0 para hipótese do professor): ')
    e_txt = input('Coeficiente e justificado (ENTER para somente PMV/PPD): ').strip()
    e = float(e_txt.replace(',', '.')) if e_txt else None
    origem = input('Origem dos dados (ex.: sensores; exemplo_didatico): ').strip()
    perfil = input('Met/clo contemporâneos ou perfil histórico? Descreva: ').strip()
    if not origem or not perfil:
        raise ValueError('Informe a origem e a identificação do perfil.')
    r = calcular(ta, rh, te, met, clo, v, e)
    print(json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False))
    print('Hipótese: Tr = temperatura externa. ePMV, se presente, é exploratório para sala climatizada.')
    if args.gravar:
        if origem.lower() in ('exemplo_didatico', 'exemplo'):
            raise ValueError('Exemplo didático não deve ser gravado no banco do projeto.')
        from influxdb_client import InfluxDBClient, Point, WritePrecision
        from influxdb_client.client.write_api import SYNCHRONOUS
        p = (Point('conforto_calculado').tag('zona', zona)
             .tag('metodo', 'pmv_iso_epmv_exploratorio' if e else 'pmv_iso')
             .tag('hipotese_tr', 'temperatura_externa')
             .tag('cenario_ar', str(v))
             .tag('cenario_e', str(e) if e is not None else 'ausente')
             .field('origem_dados', origem).field('perfil_met_clo', perfil)
             .field('versao_pythermalcomfort', '4.6.2'))
        for k, value in r.items():
            p.field(k, float(value))
        p.time(int(dt.timestamp() * 1000), WritePrecision.MS)
        with InfluxDBClient(url=os.environ.get('INFLUX_URL', 'http://localhost:8086'),
                            token=os.environ['INFLUX_TOKEN'],
                            org=os.environ.get('INFLUX_ORG', 'ufc_quixada')) as client:
            with client.write_api(write_options=SYNCHRONOUS) as writer:
                writer.write(bucket=os.environ.get('INFLUX_BUCKET', 'instrumentacao_2026'), record=p)
        print('Resultado gravado em conforto_calculado.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError) as exc:
        raise SystemExit(f'Não concluído: {exc}')
