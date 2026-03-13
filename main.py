import os
import time
import threading
from datetime import datetime

import requests
import schedule
import yfinance as yf


# =========================================================
# CONFIGURAÇÕES
# =========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
CHAT_ID_PADRAO = os.getenv("TELEGRAM_CHAT_ID", "")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
ULTIMO_UPDATE_ID = None

OZ_TO_GRAM = 31.1035


# =========================================================
# TELEGRAM
# =========================================================
def enviar_mensagem(chat_id: str, texto: str) -> None:
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": True,
    }

    try:
        resposta = requests.post(url, json=payload, timeout=30)
        resposta.raise_for_status()
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")


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
# MERCADO
# =========================================================
def pegar_hist(simbolo: str, dias: str = "5d"):
    try:
        hist = yf.Ticker(simbolo).history(period=dias, interval="1d", auto_adjust=False)
        if hist.empty:
            return None
        return hist["Close"].dropna()
    except Exception as e:
        print(f"Erro ao buscar histórico de {simbolo}: {e}")
        return None


def pegar_preco_variacao(simbolo: str):
    try:
        fechamentos = pegar_hist(simbolo)

        if fechamentos is None or len(fechamentos) < 2:
            return None, None

        atual = float(fechamentos.iloc[-1])
        anterior = float(fechamentos.iloc[-2])

        if anterior == 0:
            return atual, 0.0

        variacao = ((atual - anterior) / anterior) * 100
        return atual, variacao
    except Exception as e:
        print(f"Erro ao calcular preço/variação de {simbolo}: {e}")
        return None, None


def pegar_dolar_brl():
    preco, _ = pegar_preco_variacao("USDBRL=X")
    return preco


def pegar_metal_em_real_por_grama(simbolo: str):
    """
    Converte metal de USD/onça troy para BRL/grama.
    """
    try:
        dolar = pegar_dolar_brl()
        fechamentos = pegar_hist(simbolo)

        if dolar is None or fechamentos is None or len(fechamentos) < 2:
            return None, None

        atual_usd_oz = float(fechamentos.iloc[-1])
        anterior_usd_oz = float(fechamentos.iloc[-2])

        atual_brl_g = (atual_usd_oz / OZ_TO_GRAM) * dolar
        anterior_brl_g = (anterior_usd_oz / OZ_TO_GRAM) * dolar

        if anterior_brl_g == 0:
            return atual_brl_g, 0.0

        variacao = ((atual_brl_g - anterior_brl_g) / anterior_brl_g) * 100
        return atual_brl_g, variacao
    except Exception as e:
        print(f"Erro ao converter metal {simbolo} para R$/g: {e}")
        return None, None


# =========================================================
# FORMATAÇÃO
# =========================================================
def formatar_numero_brl(valor: float, casas: int = 4) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_variacao(variacao: float) -> str:
    if variacao is None:
        return "n/d"

    if variacao > 0:
        return f"▲ +{variacao:.2f}%"
    if variacao < 0:
        return f"▼ {variacao:.2f}%"
    return "• 0.00%"


def formatar_linha_ativo(nome: str, simbolo: str, emoji: str, prefixo_moeda: str):
    preco, variacao = pegar_preco_variacao(simbolo)

    if preco is None:
        return f"{emoji} {nome}: n/d\n   n/d"

    return (
        f"{emoji} {nome}: {prefixo_moeda} {formatar_numero_brl(preco, 4)}\n"
        f"   {formatar_variacao(variacao)}"
    )


def formatar_metal(nome: str, simbolo: str, emoji: str):
    preco, variacao = pegar_metal_em_real_por_grama(simbolo)

    if preco is None:
        return f"{emoji} {nome}: n/d\n   n/d"

    return (
        f"{emoji} {nome}: R$ {formatar_numero_brl(preco, 2)}/g\n"
        f"   {formatar_variacao(variacao)}"
    )


def formatar_metal_teor(nome: str, preco_24k_g: float, teor: float, emoji: str):
    if preco_24k_g is None:
        return f"{emoji} {nome}: n/d"

    preco = preco_24k_g * teor
    return f"{emoji} {nome}: R$ {formatar_numero_brl(preco, 2)}/g"


# =========================================================
# BLOCOS DA MENSAGEM
# =========================================================
def montar_bloco_indicadores():
    ouro_24k_preco, ouro_24k_variacao = pegar_metal_em_real_por_grama("GC=F")
    prata_pura_preco, prata_pura_variacao = pegar_metal_em_real_por_grama("SI=F")

    linhas = [
        "INDICADORES DE MERCADO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        formatar_linha_ativo("Dólar", "USDBRL=X", "💵", "R$"),
        "",
        formatar_linha_ativo("Euro", "EURBRL=X", "💶", "R$"),
        "",
        (
            f"🥇 Ouro: R$ {formatar_numero_brl(ouro_24k_preco, 2)}/g\n"
            f"   {formatar_variacao(ouro_24k_variacao)}"
            if ouro_24k_preco is not None
            else "🥇 Ouro: n/d\n   n/d"
        ),
        "",
        (
            f"🥈 Prata: R$ {formatar_numero_brl(prata_pura_preco, 2)}/g\n"
            f"   {formatar_variacao(prata_pura_variacao)}"
            if prata_pura_preco is not None
            else "🥈 Prata: n/d\n   n/d"
        ),
        "",
        "METAIS PARA JOALHERIA",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        formatar_metal_teor("Ouro 24k", ouro_24k_preco, 1.0, "🟡"),
        formatar_metal_teor("Ouro 18k", ouro_24k_preco, 0.75, "🟠"),
        formatar_metal_teor("Prata 925", prata_pura_preco, 0.925, "⚪"),
    ]

    return "\n".join(linhas)


def gerar_insight_estrategico():
    return "\n".join([
        "INSIGHT ESTRATÉGICO",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "Em cenário de pressão macroeconômica e maior seletividade do consumo,",
        "o crescimento saudável passa menos por vender a qualquer custo e mais por proteger margem, giro e eficiência.",
        "",
        "Para negócios como varejo e operação multiunidade, a grande vantagem competitiva não está só na expansão,",
        "mas na capacidade de transformar processo em previsibilidade.",
        "",
        "PERGUNTA DO DIA:",
        "qual gargalo hoje está travando mais resultado: estoque, equipe, conversão, despesas ou capital de giro?",
        "",
        "AÇÃO PRÁTICA:",
        "escolha 1 alavanca operacional para melhorar ainda esta semana e acompanhe o impacto no caixa e na margem."
    ])


def gerar_mensagem_capricornio():
    return "\n".join([
        "CAPRICÓRNIO DO DIA",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "Capricórnio, hoje sua determinação será seu maior trunfo para avançar nos objetivos profissionais.",
        "Mantenha o foco nas prioridades e evite distrações para garantir resultados sólidos.",
        "",
        "Lembre-se:",
        "disciplina e paciência são a base do seu sucesso duradouro."
    ])


def montar_briefing():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    cabecalho = "\n".join([
        "SAULO MORNING BRIEF",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕒 Atualizado em: {agora}",
    ])

    return "\n\n".join([
        cabecalho,
        montar_bloco_indicadores(),
        gerar_insight_estrategico(),
        gerar_mensagem_capricornio(),
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
    global ULTIMO_UPDATE_ID

    updates = obter_updates()

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
    enviar_mensagem(CHAT_ID_PADRAO, montar_briefing())


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
# MAIN
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