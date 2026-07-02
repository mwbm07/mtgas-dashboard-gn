from __future__ import annotations

from pathlib import Path
from datetime import datetime
import base64
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# DASHBOARD MTGÁS - VENDAS DE GÁS NATURAL (GN)
# Versão adaptada para Streamlit Community Cloud
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo_mtgas.png"

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

MESES_ABREV = {
    "Janeiro": "JAN", "Fevereiro": "FEV", "Março": "MAR", "Abril": "ABR",
    "Maio": "MAI", "Junho": "JUN", "Julho": "JUL", "Agosto": "AGO",
    "Setembro": "SET", "Outubro": "OUT", "Novembro": "NOV", "Dezembro": "DEZ",
}

CLIENTE_CORES = {
    "MILAN": "#00823B",
    "MINEIRO": "#4F4F4F",
    "GRECA": "#57B947",
    "SANEAR MT": "#19A7CE",
    "SAN CRISTO": "#79B829",
    "EXCELÊNCIA RAÇÕES": "#8E44AD",
}

VERDE = "#006B35"
VERDE_CLARO = "#2EAD59"
CINZA_TEXTO = "#1F2933"
CINZA_BORDA = "#E3E8E4"
FUNDO = "#F5F8F6"
ANO_PADRAO = 2026


# =========================================================
# UTILITÁRIOS
# =========================================================

def parse_numero_br(valor) -> float:
    """Converte números em padrão brasileiro, aceitando vazio, ponto de milhar e vírgula decimal."""
    if pd.isna(valor):
        return 0.0
    texto = str(valor).strip()
    if texto.lower() in {"", "-", "nan", "none", "null"}:
        return 0.0
    texto = texto.replace("m³", "").replace("m3", "").replace("%", "").strip()
    texto = texto.replace(" ", "")

    # Padrão brasileiro: 1.234,56
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return 0.0


def fmt_numero_br(valor: float, casas: int = 2) -> str:
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_m3(valor: float) -> str:
    return f"{fmt_numero_br(valor)} m³"


def fmt_pct(valor: float) -> str:
    return f"{fmt_numero_br(valor, 2)}%"


def sinal_numero(valor: float, unidade: str = "") -> str:
    prefixo = "+" if valor >= 0 else ""
    if unidade == "m3":
        return f"{prefixo}{fmt_m3(valor)}"
    if unidade == "pct":
        return f"{prefixo}{fmt_pct(valor)}"
    return f"{prefixo}{fmt_numero_br(valor)}"


def mes_label(mes: str | None, ano: int = ANO_PADRAO) -> str:
    if not mes:
        return "N/A"
    return f"{mes.upper()}/{ano}"


def periodo_acumulado_label(mes_atual: str | None, ano: int = ANO_PADRAO) -> str:
    if not mes_atual:
        return f"JAN–DEZ/{ano}"
    return f"JAN–{MESES_ABREV.get(mes_atual, mes_atual[:3].upper())}/{ano}"


def logo_base64() -> str | None:
    if not LOGO_PATH.exists():
        return None
    try:
        return base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
    except Exception:
        return None


# =========================================================
# CARGA DOS DADOS
# =========================================================

@st.cache_data(show_spinner=False)
def carregar_dados_manuais() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    mensal_path = DATA_DIR / "entradas_vendas_mensais.csv"
    diario_path = DATA_DIR / "entradas_vendas_diarias.csv"
    config_path = DATA_DIR / "configuracoes.csv"

    if not mensal_path.exists():
        st.error(f"Arquivo não encontrado: {mensal_path}")
        st.stop()
    if not diario_path.exists():
        st.error(f"Arquivo não encontrado: {diario_path}")
        st.stop()

    mensal_raw = pd.read_csv(mensal_path, sep=";", dtype=str, encoding="utf-8")
    mensal_raw.columns = [str(c).strip() for c in mensal_raw.columns]

    if "Cliente" not in mensal_raw.columns:
        st.error("O CSV mensal precisa ter a coluna 'Cliente'.")
        st.stop()

    mensal_raw["Cliente"] = mensal_raw["Cliente"].astype(str).str.strip().str.upper()

    for mes in MESES:
        if mes not in mensal_raw.columns:
            mensal_raw[mes] = ""
        mensal_raw[mes] = mensal_raw[mes].apply(parse_numero_br)

    mensal = mensal_raw.melt(
        id_vars="Cliente",
        value_vars=MESES,
        var_name="Mês",
        value_name="Volume_m3",
    )
    mensal["Mês_Ordem"] = mensal["Mês"].map({mes: i + 1 for i, mes in enumerate(MESES)})
    mensal["Mês_Abrev"] = mensal["Mês"].map(MESES_ABREV)
    mensal = mensal[mensal["Volume_m3"] > 0].copy()

    diario_raw = pd.read_csv(diario_path, sep=";", dtype=str, encoding="utf-8")
    diario_raw.columns = [str(c).strip() for c in diario_raw.columns]

    if "Data" not in diario_raw.columns or "Volume_m3" not in diario_raw.columns:
        st.error("O CSV diário precisa ter as colunas 'Data' e 'Volume_m3'.")
        st.stop()

    diario_raw["Data"] = pd.to_datetime(diario_raw["Data"], dayfirst=True, errors="coerce")
    diario_raw["Volume_m3"] = diario_raw["Volume_m3"].apply(parse_numero_br)
    diario = diario_raw.dropna(subset=["Data"]).sort_values("Data").copy()

    config = {}
    if config_path.exists():
        config_raw = pd.read_csv(config_path, sep=";", dtype=str, encoding="utf-8")
        config_raw.columns = [str(c).strip() for c in config_raw.columns]
        if {"Parametro", "Valor"}.issubset(config_raw.columns):
            config = dict(zip(config_raw["Parametro"], config_raw["Valor"]))

    return mensal, diario, config


def carregar_dados_api_scada() -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    """
    Ponto preparado para integração futura com SCADA/API/software interno.

    Quando a API estiver definida, substitua este return None pela chamada real.
    O retorno deve ser: mensal_df, diario_df, config_dict.
    """
    return None


# =========================================================
# PERÍODOS DINÂMICOS
# =========================================================

def obter_periodos_referencia(mensal: pd.DataFrame) -> tuple[str | None, str | None, int]:
    """
    Identifica automaticamente o último mês com volume lançado e o mês imediatamente anterior.
    Assim, ao preencher Junho no CSV, os cards mudam de MAIO para JUNHO automaticamente.
    """
    if mensal.empty:
        return None, None, ANO_PADRAO

    mensal_total = mensal.groupby(["Mês", "Mês_Ordem"], as_index=False)["Volume_m3"].sum()
    mensal_total = mensal_total[mensal_total["Volume_m3"] > 0].sort_values("Mês_Ordem")

    if mensal_total.empty:
        return None, None, ANO_PADRAO

    mes_atual = str(mensal_total.iloc[-1]["Mês"])
    mes_anterior = str(mensal_total.iloc[-2]["Mês"]) if len(mensal_total) >= 2 else None

    return mes_atual, mes_anterior, ANO_PADRAO


# =========================================================
# CSS / LAYOUT WIDESCREEN
# =========================================================

def aplicar_css() -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #F5F8F6 !important;
        }

        header[data-testid="stHeader"] {
            display: none !important;
        }

        section[data-testid="stSidebar"] {
            display: none !important;
        }

        footer, #MainMenu {
            visibility: hidden !important;
        }

        .block-container {
            max-width: 1920px !important;
            padding-top: 1.55rem !important;
            padding-bottom: 0.55rem !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.55rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.65rem !important;
        }

        .top-header {
            display: grid;
            grid-template-columns: 295px 1fr 285px;
            align-items: center;
            gap: 0.8rem;
            min-height: 82px;
            margin-bottom: 0.35rem;
        }

        .logo-box {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-height: 74px;
        }

        .logo-box img {
            max-width: 275px;
            max-height: 62px;
            object-fit: contain;
        }

        .titulo-box {
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 76px;
        }

        .titulo-principal {
            font-size: 2.45rem;
            font-weight: 900;
            color: #001B32;
            line-height: 1.04;
            margin: 0 !important;
            padding: 0 !important;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }

        .data-box {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            justify-content: center;
            min-height: 74px;
        }

        .data-ano {
            font-size: 2rem;
            font-weight: 900;
            color: #1F2933;
            line-height: 1;
            margin-bottom: 0.25rem;
        }

        .data-atualizacao {
            background: #ffffff;
            border: 1px solid #d9e6dd;
            border-radius: 10px;
            padding: 0.50rem 0.85rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            font-size: 0.68rem;
            text-align: center;
            min-width: 195px;
            font-weight: 800;
        }

        .kpi-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 0.70rem 0.80rem;
            min-height: 96px;
            border: 1px solid #dfe8e2;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            display: flex;
            align-items: center;
            gap: 0.65rem;
        }

        .kpi-icon {
            min-width: 42px;
            height: 42px;
            border-radius: 50%;
            background: #006B35;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.22rem;
            font-weight: 900;
        }

        .kpi-content {
            width: 100%;
        }

        .kpi-label {
            font-size: 0.58rem;
            font-weight: 900;
            color: #111111;
            text-transform: uppercase;
            line-height: 1.15;
            margin-bottom: 0.18rem;
        }

        .kpi-value {
            font-size: 1.38rem;
            font-weight: 900;
            color: #006B35;
            line-height: 1.08;
            margin: 0;
        }

        .kpi-sub {
            font-size: 0.60rem;
            color: #222222;
            font-weight: 600;
            margin-top: 0.20rem;
            line-height: 1.12;
        }

        .section-title {
            background: #ffffff;
            border-radius: 10px;
            padding: 0.50rem 0.60rem;
            text-align: center;
            font-weight: 900;
            color: #001B32;
            border: 1px solid #dfe8e2;
            box-shadow: 0 1px 6px rgba(0,0,0,0.06);
            margin-bottom: 0.40rem;
            font-size: 0.82rem;
            text-transform: uppercase;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 10px !important;
            overflow: hidden !important;
            border: 1px solid #dfe8e2 !important;
            box-shadow: 0 1px 6px rgba(0,0,0,0.05);
            background: #ffffff;
        }

        table, .dataframe {
            font-size: 0.68rem !important;
        }

        div[data-testid="stPlotlyChart"] {
            background: #ffffff;
            border-radius: 10px;
            border: 1px solid #dfe8e2;
            box-shadow: 0 1px 6px rgba(0,0,0,0.05);
            padding: 0.20rem;
        }

        .footer-card {
            background: #ffffff;
            border: 1px solid #dfe8e2;
            border-radius: 12px;
            padding: 0.60rem 0.75rem;
            min-height: 55px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.05);
        }

        .footer-title {
            font-size: 0.64rem;
            font-weight: 900;
            color: #003B1F;
            text-transform: uppercase;
            margin-bottom: 0.12rem;
        }

        .footer-text {
            font-size: 0.58rem;
            color: #222222;
            line-height: 1.15;
        }

        @media screen and (min-width: 1600px) {
            .block-container {
                max-width: 1900px !important;
                padding-top: 1.45rem !important;
                padding-left: 1.20rem !important;
                padding-right: 1.20rem !important;
            }
            .titulo-principal { font-size: 2.65rem; }
            .kpi-value { font-size: 1.50rem; }
        }

        @media screen and (max-width: 1400px) {
            .block-container {
                padding-top: 1.85rem !important;
                padding-left: 1.00rem !important;
                padding-right: 1.00rem !important;
            }
            .top-header {
                grid-template-columns: 245px 1fr 245px;
                min-height: 82px;
            }
            .logo-box img { max-width: 230px; }
            .titulo-principal { font-size: 2.00rem; }
            .data-ano { font-size: 1.65rem; }
            .data-atualizacao { min-width: 175px; font-size: 0.62rem; }
            .kpi-value { font-size: 1.20rem; }
            .kpi-label { font-size: 0.54rem; }
            .kpi-sub { font-size: 0.56rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# COMPONENTES VISUAIS
# =========================================================

def kpi_card(icone: str, label: str, valor: str, nota: str = "") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon">{icone}</div>
            <div class="kpi-content">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{valor}</div>
                <div class="kpi-sub">{nota}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def titulo_secao(texto: str) -> None:
    st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)


# =========================================================
# GRÁFICOS
# =========================================================

def criar_fig_linha(df_mensal_total: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_mensal_total["Mês"],
            y=df_mensal_total["Volume_m3"],
            mode="lines+markers+text",
            line=dict(color=VERDE, width=3),
            marker=dict(size=8, color=VERDE, line=dict(color="white", width=2)),
            fill="tozeroy",
            fillcolor="rgba(0, 107, 53, 0.10)",
            text=[fmt_numero_br(v) for v in df_mensal_total["Volume_m3"]],
            textposition="top center",
            hovertemplate="%{x}<br>%{y:,.2f} m³<extra></extra>",
        )
    )
    fig.update_layout(
        height=220,
        margin=dict(l=25, r=15, t=10, b=25),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#111827", size=11),
        xaxis=dict(showgrid=False, categoryorder="array", categoryarray=MESES),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", rangemode="tozero"),
    )
    return fig


def criar_fig_barras(mensal: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for cliente in sorted(mensal["Cliente"].unique()):
        dados = mensal[mensal["Cliente"] == cliente].sort_values("Mês_Ordem")
        fig.add_trace(
            go.Bar(
                x=dados["Mês"],
                y=dados["Volume_m3"],
                name=cliente,
                marker_color=CLIENTE_CORES.get(cliente, VERDE_CLARO),
                text=[fmt_numero_br(v) for v in dados["Volume_m3"]],
                textposition="outside",
                hovertemplate=f"{cliente}<br>%{{x}}<br>%{{y:,.2f}} m³<extra></extra>",
            )
        )
    fig.update_layout(
        height=250,
        barmode="group",
        margin=dict(l=25, r=15, t=10, b=55),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#111827", size=10),
        legend=dict(orientation="h", y=-0.20, x=0.02),
        xaxis=dict(showgrid=False, categoryorder="array", categoryarray=MESES),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", rangemode="tozero"),
    )
    return fig


def criar_fig_donut(ranking: pd.DataFrame, total: float) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=ranking["Cliente"],
            values=ranking["Volume_m3"],
            hole=0.55,
            marker=dict(colors=[CLIENTE_CORES.get(c, VERDE_CLARO) for c in ranking["Cliente"]]),
            textinfo="percent",
            textfont=dict(color="white", size=12),
            hovertemplate="%{label}<br>%{value:,.2f} m³<br>%{percent}<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>TOTAL</b><br>{fmt_m3(total)}",
        showarrow=False,
        font=dict(size=10, color="#111827"),
    )
    fig.update_layout(
        height=250,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        font=dict(color="#111827", size=10),
        legend=dict(orientation="v", y=0.5, x=1.02),
    )
    return fig


def criar_fig_diaria(diario: pd.DataFrame) -> go.Figure:
    ultimos = diario.tail(30)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ultimos["Data"],
            y=ultimos["Volume_m3"],
            mode="lines+markers",
            line=dict(color=VERDE, width=2.5),
            marker=dict(size=6, color=VERDE),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f} m³<extra></extra>",
        )
    )
    if not ultimos.empty:
        ultimo = ultimos.iloc[-1]
        fig.add_annotation(
            x=ultimo["Data"],
            y=ultimo["Volume_m3"],
            text=fmt_numero_br(ultimo["Volume_m3"]),
            showarrow=True,
            arrowhead=2,
            bgcolor=VERDE,
            font=dict(color="white", size=11),
        )
    fig.update_layout(
        height=250,
        margin=dict(l=25, r=15, t=10, b=30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#111827", size=10),
        xaxis=dict(showgrid=False, tickformat="%d/%m"),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", rangemode="tozero"),
    )
    return fig


# =========================================================
# TABELAS E INDICADORES
# =========================================================

def montar_tabelas(mensal: pd.DataFrame, mes_atual: str | None, mes_anterior: str | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ranking = mensal.groupby("Cliente", as_index=False)["Volume_m3"].sum().sort_values("Volume_m3", ascending=False)
    total = float(ranking["Volume_m3"].sum()) if not ranking.empty else 0.0
    ranking["Participação"] = ranking["Volume_m3"] / total if total else 0.0

    atual = mensal[mensal["Mês"] == mes_atual].groupby("Cliente")["Volume_m3"].sum() if mes_atual else pd.Series(dtype=float)
    anterior = mensal[mensal["Mês"] == mes_anterior].groupby("Cliente")["Volume_m3"].sum() if mes_anterior else pd.Series(dtype=float)

    comp = pd.DataFrame({"Cliente": ranking["Cliente"]})
    comp["Atual"] = comp["Cliente"].map(atual).fillna(0.0)
    comp["Anterior"] = comp["Cliente"].map(anterior).fillna(0.0)
    comp["Vs Anterior"] = comp["Atual"] - comp["Anterior"]
    comp["Var %"] = comp.apply(lambda r: (r["Vs Anterior"] / r["Anterior"] if r["Anterior"] else 0.0), axis=1)

    tabela_anual = mensal.pivot_table(index="Cliente", columns="Mês_Abrev", values="Volume_m3", aggfunc="sum", fill_value=0)
    cols = [MESES_ABREV[m] for m in MESES]
    for c in cols:
        if c not in tabela_anual.columns:
            tabela_anual[c] = 0.0
    tabela_anual = tabela_anual[cols]
    tabela_anual["TOTAL"] = tabela_anual.sum(axis=1)
    if not ranking.empty:
        tabela_anual = tabela_anual.loc[ranking["Cliente"]]

    return ranking, comp, tabela_anual


def dataframe_formatado_ranking(ranking: pd.DataFrame, comp: pd.DataFrame, mes_anterior: str | None) -> pd.DataFrame:
    df = ranking.copy().reset_index(drop=True)
    df.insert(0, "Pos.", [f"{i}º" for i in range(1, len(df) + 1)])
    df = df.merge(comp[["Cliente", "Vs Anterior", "Var %"]], on="Cliente", how="left")
    nome_col_vs = f"Vs {MESES_ABREV.get(mes_anterior, 'Ant.')} (m³)" if mes_anterior else "Vs mês anterior (m³)"
    nome_col_pct = f"Vs {MESES_ABREV.get(mes_anterior, 'Ant.')} (%)" if mes_anterior else "Vs mês anterior (%)"
    return pd.DataFrame({
        "Pos.": df["Pos."],
        "Cliente": df["Cliente"],
        "Volume (m³)": df["Volume_m3"].map(fmt_numero_br),
        "Participação": (df["Participação"] * 100).map(fmt_pct),
        nome_col_vs: df["Vs Anterior"].map(lambda x: sinal_numero(x)),
        nome_col_pct: (df["Var %"] * 100).map(lambda x: sinal_numero(x, "pct")),
    })


def dataframe_formatado_comp(comp: pd.DataFrame, mes_atual: str | None, mes_anterior: str | None) -> pd.DataFrame:
    nome_col = f"Vs {MESES_ABREV.get(mes_anterior, 'Ant.')} (m³)" if mes_anterior else "Vs mês anterior (m³)"
    df = comp[["Cliente", "Vs Anterior", "Var %"]].copy()
    return pd.DataFrame({
        "Cliente": df["Cliente"],
        nome_col: df["Vs Anterior"].map(lambda x: sinal_numero(x)),
        "Var. (%)": (df["Var %"] * 100).map(lambda x: sinal_numero(x, "pct")),
    })


def formatar_tabela_anual(tabela: pd.DataFrame) -> pd.DataFrame:
    saida = tabela.copy()
    for col in saida.columns:
        saida[col] = saida[col].map(lambda v: "-" if float(v) == 0 else fmt_numero_br(v))
    saida.insert(0, "Cliente", saida.index)
    return saida.reset_index(drop=True)


def calcular_totais(mensal: pd.DataFrame, mes_atual: str | None, mes_anterior: str | None) -> dict:
    mensal_total = mensal.groupby(["Mês", "Mês_Ordem"], as_index=False)["Volume_m3"].sum().sort_values("Mês_Ordem")
    vol_mes_atual = float(mensal_total.loc[mensal_total["Mês"] == mes_atual, "Volume_m3"].sum()) if mes_atual else 0.0
    vol_mes_anterior = float(mensal_total.loc[mensal_total["Mês"] == mes_anterior, "Volume_m3"].sum()) if mes_anterior else 0.0
    dif_mes = vol_mes_atual - vol_mes_anterior
    pct_mes = (dif_mes / vol_mes_anterior) if vol_mes_anterior else 0.0
    return {
        "mensal_total": mensal_total,
        "vol_mes_atual": vol_mes_atual,
        "vol_mes_anterior": vol_mes_anterior,
        "dif_mes": dif_mes,
        "pct_mes": pct_mes,
    }


# =========================================================
# APP PRINCIPAL
# =========================================================

def main() -> None:
    st.set_page_config(page_title="Vendas de Gás Natural - MTGÁS", layout="wide")
    aplicar_css()

    dados_api = carregar_dados_api_scada()
    if dados_api is None:
        mensal, diario, config = carregar_dados_manuais()
    else:
        mensal, diario, config = dados_api

    mes_atual, mes_anterior, ano = obter_periodos_referencia(mensal)
    periodo_acum = periodo_acumulado_label(mes_atual, ano)

    ranking, comp, tabela_anual = montar_tabelas(mensal, mes_atual, mes_anterior)
    totais = calcular_totais(mensal, mes_atual, mes_anterior)
    mensal_total = totais["mensal_total"]

    total_acumulado = float(ranking["Volume_m3"].sum()) if not ranking.empty else 0.0
    vol_mes_atual = totais["vol_mes_atual"]
    dif_mes = totais["dif_mes"]
    pct_mes = totais["pct_mes"]

    lider = ranking.iloc[0] if not ranking.empty else pd.Series({"Cliente": "N/A", "Participação": 0.0})
    meta_anual = parse_numero_br(config.get("Meta anual", "350000"))
    realizado_meta = total_acumulado / meta_anual if meta_anual else 0.0
    vendido_hoje = float(diario.iloc[-1]["Volume_m3"]) if not diario.empty else 0.0

    data_atualizacao = config.get("Data da atualização", "")
    hora_atualizacao = config.get("Hora da atualização", "")
    if not data_atualizacao and not diario.empty:
        data_atualizacao = diario.iloc[-1]["Data"].strftime("%d/%m/%Y")
    if not hora_atualizacao:
        hora_atualizacao = datetime.now().strftime("%H:%M:%S")

    # Cabeçalho SEM o período fixo "JANEIRO A MAIO DE 2026"
    logo64 = logo_base64()
    logo_html = f'<img src="data:image/png;base64,{logo64}">' if logo64 else '<b style="font-size:1.6rem;color:#006B35;">mtgás</b>'

    st.markdown(
        f"""
        <div class="top-header">
            <div class="logo-box">{logo_html}</div>
            <div class="titulo-box">
                <div class="titulo-principal">VENDAS DE GÁS NATURAL (GN)</div>
            </div>
            <div class="data-box">
                <div class="data-ano">{ano}</div>
                <div class="data-atualizacao">
                    ÚLTIMA ATUALIZAÇÃO<br>
                    <span style="color:#006B35; font-weight:900;">{data_atualizacao} {hora_atualizacao}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPIs dinâmicos
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        kpi_card("▣", "Total vendido hoje", fmt_m3(vendido_hoje), data_atualizacao)
    with k2:
        kpi_card("▥", "Total vendido no mês", fmt_m3(vol_mes_atual), mes_label(mes_atual, ano))
    with k3:
        kpi_card("↗", "Total acumulado no ano", fmt_m3(total_acumulado), periodo_acum)
    with k4:
        titulo_vs = f"Vs mês anterior ({mes_label(mes_anterior, ano)})" if mes_anterior else "Vs mês anterior"
        kpi_card("↑", titulo_vs, sinal_numero(dif_mes, "m3"), sinal_numero(pct_mes * 100, "pct"))
    with k5:
        kpi_card("🏆", "Cliente líder no ano", str(lider["Cliente"]), fmt_pct(float(lider["Participação"]) * 100) + " de participação")
    with k6:
        kpi_card("◎", "Meta anual", fmt_m3(meta_anual), f"Realizado: {fmt_pct(realizado_meta * 100)}")
        st.progress(min(max(realizado_meta, 0), 1))

    col_esq, col_centro, col_dir = st.columns([1.25, 1.85, 1.05])

    with col_esq:
        titulo_secao(f"Ranking acumulado ({periodo_acum})")
        st.dataframe(
            dataframe_formatado_ranking(ranking, comp, mes_anterior),
            hide_index=True,
            use_container_width=True,
            height=300,
        )

        titulo_secao(f"Comparativo – {mes_label(mes_atual, ano)} x {mes_label(mes_anterior, ano)}")
        st.dataframe(
            dataframe_formatado_comp(comp, mes_atual, mes_anterior),
            hide_index=True,
            use_container_width=True,
            height=270,
        )

    with col_centro:
        titulo_secao("Evolução das vendas – Total mensal (m³)")
        st.plotly_chart(criar_fig_linha(mensal_total), use_container_width=True, config={"displayModeBar": False})

        titulo_secao("Vendas por cliente – Evolução mensal (m³)")
        st.plotly_chart(criar_fig_barras(mensal), use_container_width=True, config={"displayModeBar": False})

        titulo_secao(f"Acumulado anual (m³) – {ano}")
        st.dataframe(formatar_tabela_anual(tabela_anual), hide_index=True, use_container_width=True, height=220)

    with col_dir:
        titulo_secao("Participação no total acumulado")
        st.plotly_chart(criar_fig_donut(ranking, total_acumulado), use_container_width=True, config={"displayModeBar": False})

        titulo_secao("Evolução diária – últimos 30 dias (m³)")
        st.plotly_chart(criar_fig_diaria(diario), use_container_width=True, config={"displayModeBar": False})

    f1, f2, f3, f4 = st.columns([1, 1, 1.6, 1.25])
    with f1:
        st.markdown('<div class="footer-card"><div class="footer-title">▣ Unidade de medida</div><div class="footer-text">Metros cúbicos (m³)</div></div>', unsafe_allow_html=True)
    with f2:
        st.markdown(f'<div class="footer-card"><div class="footer-title">▦ Fonte dos dados</div><div class="footer-text">{config.get("Fonte dos dados", "Sistema Comercial MTGÁS")}</div></div>', unsafe_allow_html=True)
    with f3:
        st.markdown('<div class="footer-card"><div class="footer-title">💡 Dica</div><div class="footer-text">Atualize os arquivos CSV na pasta <b>data</b>. O mês atual e o mês anterior serão identificados automaticamente.</div></div>', unsafe_allow_html=True)
    with f4:
        st.markdown('<div class="footer-card"><div class="footer-title">↻ Integração futura</div><div class="footer-text">Preparado para SCADA, API ou software interno.</div></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
