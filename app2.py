import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt

st.set_page_config(page_title="Indicadores Econômicos", layout="wide")

# Entrada do usuário
st.title("📊 Indicadores Econômicos do Brasil")
entrada = st.text_input("Digite a quantidade de meses (ex: 12,24, 36...) ou uma data de início no formato americano 'feb/24':", "12")
opcoes_validas = [12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
hoje = datetime.today()

# Processamento da entrada
try:
    entrada = entrada.strip().lower()
    if entrada.isdigit() and int(entrada) in opcoes_validas:
        historico_meses = int(entrada)
        data_inicio = hoje - relativedelta(months=historico_meses + 1)
    else:
        data_inicio = datetime.strptime(entrada, '%b/%y')
        historico_meses = (hoje.year - data_inicio.year) * 12 + hoje.month - data_inicio.month
        if historico_meses < 1:
            st.warning("⚠️ Data de início inválida ou no futuro.")
            st.stop()
except Exception:
    st.warning("⚠️ Entrada inválida. Use um número (ex: 24) ou mês no formato 'jun/24'.")
    st.stop()

# Séries do Bacen
series = {
    'IGPM': 189,
    'INCC': 192,
    'IPCA': 433,
    'CDI': 4391,
    'POUP': 196
}
data_inicial = '01/01/2010'
data_final = hoje.strftime('%d/%m/%Y')

def consulta_bc(codigo_serie, data_inicial, data_final):
    url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados?formato=json&dataInicial={data_inicial}&dataFinal={data_final}'
    resposta = requests.get(url)
    if resposta.status_code != 200:
        return pd.Series(dtype=float)
    dados = resposta.json()
    if not dados:
        return pd.Series(dtype=float)
    df = pd.DataFrame(dados)
    df['data'] = pd.to_datetime(df['data'], dayfirst=True)
    df['valor'] = pd.to_numeric(df['valor'].str.replace(',', '.'), errors='coerce')
    return df.set_index('data')['valor']

# Coleta Bacen
df_indices = pd.DataFrame()
for nome, codigo in series.items():
    serie = consulta_bc(codigo, data_inicial, data_final)
    if not serie.empty:
        df_indices[nome] = serie

# Agregação mensal
indices_media = ['IGPM', 'INCC', 'IPCA']
indices_soma = ['CDI', 'POUP']
aggs = {col: 'mean' if col in indices_media else 'sum' for col in df_indices.columns}
df_mensal = df_indices.resample('ME').agg(aggs)

# Yahoo Finance
inicio = data_inicio.strftime('%Y-%m-%d')
fim = hoje.strftime('%Y-%m-%d')
ibov = yf.download("^BVSP", start=inicio, end=fim, interval="1d", progress=False, auto_adjust=False)
usdbrl = yf.download("USDBRL=X", start=inicio, end=fim, interval="1d", progress=False, auto_adjust=False)
ibov.index = pd.to_datetime(ibov.index)
usdbrl.index = pd.to_datetime(usdbrl.index)
ibov_mensal = ibov['Close'].resample('ME').last()
usd_mensal = usdbrl['Close'].resample('ME').last()
mes_atual = hoje.strftime('%Y-%m')
ibov_mensal = ibov_mensal[ibov_mensal.index.strftime('%Y-%m') < mes_atual]
usd_mensal = usd_mensal[usd_mensal.index.strftime('%Y-%m') < mes_atual]

df_mensal['DOLAR'] = usd_mensal
df_mensal['IBOV MES'] = ibov_mensal
df_mensal = df_mensal.dropna().tail(historico_meses)

# Acumulados
df_acumulado = df_mensal.copy()
for col in ['IGPM', 'INCC', 'IPCA', 'CDI', 'POUP']:
    if col in df_acumulado.columns:
        df_acumulado[f'{col}-A'] = ((1 + df_acumulado[col] / 100).cumprod() - 1) * 100
if 'IBOV MES' in df_acumulado.columns:
    base_ibov = df_acumulado['IBOV MES'].iloc[0]
    df_acumulado['IBOV MES-A'] = (df_acumulado['IBOV MES'] / base_ibov - 1) * 100
if 'DOLAR' in df_acumulado.columns:
    base_dolar = df_acumulado['DOLAR'].iloc[0]
    df_acumulado['DOLAR-A'] = (df_acumulado['DOLAR'] / base_dolar - 1) * 100

# Reorganizar colunas
colunas_ordenadas = []
for col in ['IGPM', 'INCC', 'IPCA', 'CDI', 'POUP', 'DOLAR', 'IBOV MES']:
    if col in df_acumulado.columns:
        colunas_ordenadas.append(col)
        col_acum = f'{col}-A'
        if col_acum in df_acumulado.columns:
            colunas_ordenadas.append(col_acum)
df_acumulado = df_acumulado[colunas_ordenadas]
df_acumulado.index = df_acumulado.index.to_series().dt.strftime('%b/%y').str.lower()
df_acumulado.index.name = 'Data'

# Exibir tabela
st.subheader("📋 Tabela Consolidada")
st.dataframe(df_acumulado.style.format({col: '{:,.2f}' for col in df_acumulado.columns}, na_rep='-'))

# Gráfico de barras
cols_acumulados = [col for col in df_acumulado.columns if col.endswith('-A')]
df_barras = df_acumulado[cols_acumulados].copy()
valores_finais = df_barras.iloc[-1].sort_values()

st.subheader("📈 Indicadores Acumulados")
fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(valores_finais.index, valores_finais.values, color='skyblue')
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, height + 0.5, f'{height:.2f}%',
            ha='center', va='bottom', fontsize=10)
ax.set_title(f"Indicadores Acumulados dos Últimos {historico_meses} meses", fontsize=14)
ax.set_ylabel("Acumulado (%)")
ax.set_xticks(range(len(valores_finais.index)))
ax.set_xticklabels(valores_finais.index, rotation=45)
ax.grid(axis='y', linestyle='--', alpha=0.5)
ax.set_ylim(valores_finais.min() - 4, valores_finais.max() + 6)
st.pyplot(fig)
