import os
import time
import threading
from datetime import datetime

import requests
import schedule
import yfinance as yf

OZ_TO_GRAM = 31.1035

def pegar_dolar():
    try:
        hist = yf.Ticker("USDBRL=X").history(period="5d")
        return float(hist["Close"].iloc[-1])
    except:
        return None


def pegar_metal_em_real_por_grama(simbolo):
    try:
        dolar = pegar_dolar()
        if dolar is None:
            return None, None

        hist = yf.Ticker(simbolo).history(period="5d")
        if hist.empty or len(hist) < 2:
            return None, None

        atual_usd_oz = float(hist["Close"].iloc[-1])
        anterior_usd_oz = float(hist["Close"].iloc[-2])

        atual_brl_g = (atual_usd_oz / OZ_TO_GRAM) * dolar
        anterior_brl_g = (anterior_usd_oz / OZ_TO_GRAM) * dolar

        variacao = ((atual_brl_g - anterior_brl_g) / anterior_brl_g) * 100

        return atual_brl_g, variacao

    except:
        return None, None


def formatar_metal(nome, simbolo, emoji):
    preco, variacao = pegar_metal_em_real_por_grama(simbolo)

    if preco is None:
        return f"{emoji} {nome}: n/d\n   n/d"

    seta = "▲" if variacao > 0 else "▼"
    sinal = "+" if variacao > 0 else ""

    return f"{emoji} {nome}: R$ {preco:,.2f}/g\n   {seta} {sinal}{variacao:.2f}%"

# =========================================================
# CONFIGURAÇÕES
# =========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
CHAT_ID_PADRAO = os.getenv("TELEGRAM_CHAT_ID", "")  # opcional para envio automático

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ULTIMO_UPDATE_ID = None


# =========================================================
# FUNÇÕES BÁSICAS TELEGRAM
# =========================================================
def enviar_mensagem(chat_id: str, texto: str) -> None:
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resposta = requests.post(url, json=payload, timeout=30)
        resposta.raise_for_status()
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")


def obter_updates():
    global ULTIMO_UPDATE_ID

    url = f"{API_URL}/getUpdates"
    params = {"timeout": 30}

    if ULTIMO_UPDATE_ID is not None:
        params["offset"] = ULTIMO_UPDATE_ID + 1

    try:
        resposta = requests.get(url, params=params, timeout=35)
        resposta.raise_for_status()
        dados = resposta.json()

        if not dados.get("ok"):
            return []

        return dados.get("result", [])
    except Exception as e:
        print(f"Erro ao obter updates: {e}")
        return []


# =========================================================
# INDICADORES DE MERCADO
# =========================================================
def pegar_preco_variacao(simbolo: str):
    """
    Retorna:
    - preço atual
    - variação percentual diária
    - moeda sugerida de exibição
    """
    try:
        hist = yf.Ticker(simbolo).history(period="5d", interval="1d", auto_adjust=False)

        if hist.empty:
            return None, None

        fechamentos = hist["Close"].dropna()

        if len(fechamentos) < 2:
            return None, None

        preco_atual = float(fechamentos.iloc[-1])
        preco_anterior = float(fechamentos.iloc[-2])

        if preco_anterior == 0:
            return preco_atual, 0.0

        variacao = ((preco_atual - preco_anterior) / preco_anterior) * 100
        return preco_atual, variacao

    except Exception as e:
        print(f"Erro ao buscar {simbolo}: {e}")
        return None, None


def formatar_linha_ativo(nome: str, simbolo: str, emoji: str, prefixo_moeda: str):
    preco, variacao = pegar_preco_variacao(simbolo)

    if preco is None:
        return f"{emoji} {nome}: n/d\n   n/d"

    seta = "▲" if variacao > 0 else "▼" if variacao < 0 else "•"
    sinal = "+" if variacao > 0 else ""

    return f"{emoji} {nome}: {prefixo_moeda} {preco:,.4f}\n   {seta} {sinal}{variacao:.2f}%"


def montar_bloco_indicadores():
    linhas = [
        "INDICADORES DE MERCADO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
formatar_linha_ativo("Dólar", "USDBRL=X", "💵", "R$"),

formatar_linha_ativo("Euro", "EURBRL=X", "💶", "R$"),

formatar_metal("Ouro", "GC=F", "🥇"),

formatar_metal("Prata", "SI=F", "🥈"),

    ]
    return "\n".join(linhas)


# =========================================================
# INSIGHT ESTRATÉGICO
# =========================================================
def gerar_insight_estrategico():
    hoje = datetime.now().strftime("%d/%m/%Y")

    return "\n".join([
        "INSIGHT ESTRATÉGICO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📌 {hoje}",
        "",
        "Crescer não é apenas vender mais; é fortalecer a estrutura para suportar o próximo salto.",
        "Toda operação que acelera sem clareza de processo acaba trocando faturamento por desgaste.",
        "",
        "Hoje, olhe para um ponto simples:",
        "qual gargalo operacional, comercial ou financeiro está limitando o resultado do negócio mais do que a falta de vendas?",
        "",
        "Quem encontra o verdadeiro gargalo primeiro, cresce com mais margem, mais controle e menos ruído."
    ])


# =========================================================
# MENSAGEM DE CAPRICÓRNIO
# =========================================================
def gerar_mensagem_capricornio():
    return "\n".join([
        "CAPRICÓRNIO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "♑ Hoje é um dia de consistência, disciplina e construção silenciosa.",
        "O que parece pequeno agora pode se tornar muito relevante se for repetido com excelência.",
        "",
        "Evite dispersão.",
        "Seu diferencial hoje estará em concluir bem o que realmente importa.",
        "",
        "Mensagem do dia:",
        "quem domina a rotina domina o resultado."
    ])


# =========================================================
# BRIEFING COMPLETO
# =========================================================
def montar_briefing():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    cabecalho = "\n".join([
        "SAULO MORNING BRIEF",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕒 Atualizado em: {agora}",
        ""
    ])

    bloco_indicadores = montar_bloco_indicadores()
    bloco_insight = gerar_insight_estrategico()
    bloco_capricornio = gerar_mensagem_capricornio()

    return "\n\n".join([
        cabecalho,
        bloco_indicadores,
        bloco_insight,
        bloco_capricornio
    ])


# =========================================================
# COMANDOS
# =========================================================
def responder_comando(texto: str):
    texto_limpo = (texto or "").strip().lower()

    if texto_limpo in ["/start", "start"]:
        return (
            "Bem-vindo ao Agente Virtual Saulo.\n\n"
            "Comandos disponíveis:\n"
            "/briefing - envia o briefing completo\n"
            "/indicadores - envia apenas os indicadores\n"
            "/insight - envia apenas o insight estratégico\n"
            "/capricornio - envia apenas a mensagem de Capricórnio"
        )

    if texto_limpo in ["/briefing", "briefing"]:
        return montar_briefing()

    if texto_limpo in ["/indicadores", "indicadores"]:
        return montar_bloco_indicadores()

    if texto_limpo in ["/insight", "insight"]:
        return gerar_insight_estrategico()

    if texto_limpo in ["/capricornio", "capricornio"]:
        return gerar_mensagem_capricornio()

    return (
        "Comando não reconhecido.\n\n"
        "Use:\n"
        "/briefing\n"
        "/indicadores\n"
        "/insight\n"
        "/capricornio"
    )


def processar_updates():
    updates = obter_updates()

    global ULTIMO_UPDATE_ID

    for update in updates:
        ULTIMO_UPDATE_ID = update["update_id"]

        message = update.get("message", {})
        chat = message.get("chat", {})
        texto = message.get("text", "")
        chat_id = chat.get("id")

        if not chat_id:
            continue

        resposta = responder_comando(texto)
        enviar_mensagem(str(chat_id), resposta)


# =========================================================
# AGENDAMENTO
# =========================================================
def enviar_briefing_automatico():
    if not CHAT_ID_PADRAO:
        print("CHAT_ID_PADRAO não configurado. Briefing automático ignorado.")
        return

    print("Enviando Morning Brief automático...")
    texto = montar_briefing()
    enviar_mensagem(CHAT_ID_PADRAO, texto)


def loop_agendamento():
    schedule.every().day.at("06:00").do(enviar_briefing_automatico)
    print("Morning Brief agendado para 06:00.")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"Erro no agendamento: {e}")
        time.sleep(30)


# =========================================================
# LOOP PRINCIPAL
# =========================================================
def main():
    print("INICIANDO AGENTE VIRTUAL SAULO")
    print("Agente Virtual Saulo rodando...")

    thread_schedule = threading.Thread(target=loop_agendamento, daemon=True)
    thread_schedule.start()

    while True:
        try:
            processar_updates()
            time.sleep(2)
        except KeyboardInterrupt:
            print("Encerrando bot...")
            break
        except Exception as e:
            print(f"Erro no loop principal: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()