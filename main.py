import os
import re
import html
import json
import urllib.parse
from datetime import datetime, time
from zoneinfo import ZoneInfo

import feedparser
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

print("INICIANDO AGENTE VIRTUAL SAULO")

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não encontrado no arquivo .env")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")

if not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_CHAT_ID não encontrado no arquivo .env")

client = OpenAI(api_key=OPENAI_API_KEY)
FUSO = ZoneInfo("America/Sao_Paulo")
ARQUIVO_MEMORIA = "memoria_saulo.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

FONTES_FORTES = [
    "reuters",
    "bloomberg",
    "cnn",
    "cnn brasil",
    "valor",
    "valor econômico",
    "infomoney",
    "o globo",
    "oglobo",
    "estadão",
    "estadao",
    "neofeed",
    "exame",
    "forbes",
    "forbes brasil",
    "correio braziliense",
    "metrópoles",
    "metropoles",
    "gps",
    "abrasce",
    "techcrunch",
    "mit technology review",
    "business of fashion",
]

PALAVRAS_FRACAS = [
    "prefeitura",
    "câmara municipal",
    "camara municipal",
    "vereador",
    "edital",
    "licitação",
    "licitacao",
    "diário oficial",
    "diario oficial",
]

CATEGORIAS_BRIEF = [
    {
        "nome": "Macro Global",
        "queries": [
            "economia global mercados inflação juros fed bloomberg reuters",
            "mercados globais inflação eua juros reuters",
            "economia global bloomberg reuters cnn",
        ],
    },
    {
        "nome": "Brasil",
        "queries": [
            "economia brasil inflação juros fiscal cnn brasil infomoney valor",
            "brasil economia juros inflação valor infomoney",
            "economia brasil oglobo estadao cnn brasil",
        ],
    },
    {
        "nome": "Negócios",
        "queries": [
            "negócios empresas brasil investimentos valor exame neofeed",
            "empresas brasil expansão aquisições exame valor",
            "negócios brasil forbes exame neofeed",
        ],
    },
    {
        "nome": "Empreendedorismo",
        "queries": [
            "empreendedorismo brasil startups crescimento empresas exame forbes",
            "empreendedorismo inovação negócios brasil",
            "startups brasil expansão investimento",
        ],
    },
    {
        "nome": "IA",
        "queries": [
            "openai anthropic nvidia inteligência artificial empresas reuters techcrunch",
            "inteligência artificial negócios openai empresas",
            "ia empresas tecnologia reuters techcrunch",
        ],
    },
    {
        "nome": "Varejo & Consumo",
        "queries": [
            "varejo consumo brasil marcas vendas infomoney estadao",
            "consumo brasil varejo comportamento consumidor",
            "varejo físico brasil consumo",
        ],
    },
    {
        "nome": "Shopping Centers",
        "queries": [
            "shopping centers brasil abrasce varejo físico",
            "shopping center brasil fluxo ocupação varejo",
            "shoppings brasil varejo consumo",
        ],
    },
    {
        "nome": "Restaurantes & Bares",
        "queries": [
            "food service restaurantes bares hospitalidade brasil",
            "restaurantes bares brasil experiência consumo",
            "hospitalidade gastronomia brasil negócios",
        ],
    },
    {
        "nome": "Luxo & Joias",
        "queries": [
            "luxo joias joalheria marcas premium bloomberg forbes",
            "mercado de luxo joias consumo premium",
            "joalheria luxo marcas premium",
        ],
    },
    {
        "nome": "Brasília",
        "queries": [
            "brasília df negócios economia cidade metropoles gps correio braziliense",
            "brasília df economia negócios",
            "distrito federal negócios economia cidade",
        ],
    },
]

QUERIES_RESERVA = [
    "geopolítica mercados petróleo reuters bloomberg cnn",
    "consumo luxo marcas premium bloomberg forbes",
    "entretenimento negócios brasil",
    "tecnologia empresas big tech reuters cnn",
    "varejo físico brasil shopping consumo",
]

MAX_MATERIAS = 10


def carregar_memoria() -> dict:
    if not os.path.exists(ARQUIVO_MEMORIA):
        memoria_inicial = {
            "usuario": {
                "nome": "Saulo",
                "perfil": (
                    "Empresário brasileiro, estratégico, disciplinado, orientado a crescimento, "
                    "marca, experiência, gestão e legado."
                ),
                "cidade_base": "Brasília",
                "signo": "Capricórnio",
            },
            "coralli": {
                "descricao": (
                    "Joalheria familiar em expansão, foco em gestão profissional, experiência de compra, "
                    "mix de produtos, posicionamento e crescimento sustentável."
                )
            },
            "mane": {
                "descricao": (
                    "Plataforma de gastronomia, entretenimento e experiência, com foco em curadoria, "
                    "operação, ambiente, marketing, eventos e crescimento consistente."
                )
            },
            "discussoes_recentes": [
                "Construção do Agente Virtual Saulo",
                "Morning Brief das 06h",
                "Curadoria de notícias",
                "Eficiência e qualidade executiva",
            ],
        }
        salvar_memoria(memoria_inicial)
        return memoria_inicial

    with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_memoria(memoria: dict) -> None:
    with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


MEMORIA = carregar_memoria()


def contexto_sistema_base() -> str:
    discussoes = MEMORIA.get("discussoes_recentes", [])
    discussoes_texto = "; ".join(discussoes[-10:]) if discussoes else "Nenhuma"

    return f"""
Você é o Agente Virtual Saulo.

Atue como assistente executivo e conselheiro estratégico de um grande empresário.

Contexto do usuário:
- Nome: {MEMORIA["usuario"]["nome"]}
- Cidade base: {MEMORIA["usuario"]["cidade_base"]}
- Signo: {MEMORIA["usuario"]["signo"]}
- Perfil: {MEMORIA["usuario"]["perfil"]}

Contexto Coralli:
{MEMORIA["coralli"]["descricao"]}

Contexto Mané:
{MEMORIA["mane"]["descricao"]}

Discussões recentes:
{discussoes_texto}

Diretrizes:
- responda em português do Brasil
- seja sofisticado, executivo, objetivo e útil
- não seja genérico
- quando fizer insight, seja cirúrgico
- não force relação com Coralli e Mané se o noticiário não justificar
""".strip()


def limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def fonte_forte(nome_fonte: str) -> bool:
    nome_fonte = (nome_fonte or "").lower()
    return any(f in nome_fonte for f in FONTES_FORTES)


def materia_fraca(titulo: str, descricao: str, fonte: str) -> bool:
    base = f"{titulo} {descricao} {fonte}".lower()

    if any(p in base for p in PALAVRAS_FRACAS):
        return True

    if len((titulo or "").strip()) < 25:
        return True

    return False


def buscar_feed_google_news(query: str, limite: int = 8):
    query_codificada = urllib.parse.quote_plus(f"{query} when:1d")
    url = (
        "https://news.google.com/rss/search"
        f"?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    feed = feedparser.parse(url)
    return feed.entries[:limite]


def extrair_descricao_artigo(url: str) -> str:
    try:
        resposta = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, "html.parser")

        metas = [
            ("property", "og:description"),
            ("name", "description"),
            ("name", "twitter:description"),
        ]

        for attr, valor in metas:
            tag = soup.find("meta", attrs={attr: valor})
            if tag and tag.get("content"):
                texto = limpar_texto(tag["content"])
                if len(texto) >= 80:
                    return texto[:320]

        paragrafos = []
        for p in soup.find_all("p"):
            texto = limpar_texto(p.get_text(" ", strip=True))
            if len(texto) >= 90:
                paragrafos.append(texto)
            if len(paragrafos) >= 2:
                break

        if paragrafos:
            return " ".join(paragrafos)[:320]

        return ""
    except Exception:
        return ""


def selecionar_melhor_materia(queries: list[str]) -> dict | None:
    melhores = []

    for query in queries:
        entradas = buscar_feed_google_news(query, limite=8)

        for entry in entradas:
            titulo = getattr(entry, "title", "Sem título")
            link = getattr(entry, "link", "")
            fonte = ""

            if hasattr(entry, "source") and isinstance(entry.source, dict):
                fonte = entry.source.get("title", "")

            if not link:
                continue

            descricao = extrair_descricao_artigo(link)

            if not descricao:
                summary = getattr(entry, "summary", "")
                descricao = limpar_texto(
                    BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)
                )[:320]

            if not descricao:
                continue

            if materia_fraca(titulo, descricao, fonte):
                continue

            score = 0

            if fonte_forte(fonte):
                score += 4

            if len(descricao) >= 120:
                score += 2

            texto_total = f"{titulo} {descricao}".lower()

            if "brasil" in texto_total:
                score += 1

            if (
                "economia" in texto_total
                or "negócio" in texto_total
                or "mercado" in texto_total
                or "empresa" in texto_total
            ):
                score += 1

            melhores.append(
                {
                    "titulo": titulo,
                    "link": link,
                    "fonte": fonte or "Fonte não informada",
                    "descricao": descricao,
                    "score": score,
                }
            )

        if melhores:
            break

    if not melhores:
        return None

    melhores.sort(key=lambda x: x["score"], reverse=True)
    melhor = melhores[0]
    melhor.pop("score", None)
    return melhor


def resumir_descricao_executiva(titulo: str, descricao: str) -> str:
    prompt = f"""
Resuma a reportagem abaixo em 2 frases curtas, em português do Brasil, no estilo de briefing executivo.
Objetivo: deixar o leitor bem informado sem precisar abrir o link.
Não invente fatos. Seja claro e sofisticado.

Título:
{titulo}

Descrição:
{descricao}
"""

    try:
        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        return resposta.output_text.strip()[:320]
    except Exception:
        return descricao[:220]


def obter_cotacao_yahoo(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period="5d")

        if hist.empty:
            return None, None

        atual = float(hist["Close"].iloc[-1])
        anterior = float(hist["Close"].iloc[-2]) if len(hist) > 1 else atual
        variacao_pct = ((atual / anterior) - 1) * 100 if anterior else 0

        return atual, variacao_pct
    except Exception:
        return None, None


def formatar_variacao_pct(valor):
    if valor is None:
        return "n/d"

    seta = "▲" if valor >= 0 else "▼"
    return f"{seta} {valor:+.2f}%"


def montar_bloco_cotacoes() -> str:
    usd, usd_var = obter_cotacao_yahoo("USDBRL=X")
    eur, eur_var = obter_cotacao_yahoo("EURBRL=X")
    gold_usd_oz, gold_var = obter_cotacao_yahoo("GC=F")
    silver_usd_oz, silver_var = obter_cotacao_yahoo("SI=F")

    oz_para_grama = 31.1034768

    gold_brl_g = None
    silver_brl_g = None

    if usd is not None and gold_usd_oz is not None:
        gold_brl_g = (gold_usd_oz * usd) / oz_para_grama

    if usd is not None and silver_usd_oz is not None:
        silver_brl_g = (silver_usd_oz * usd) / oz_para_grama

    linhas = [
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>INDICADORES DE MERCADO</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💵 <b>Dólar:</b> R$ {usd:.4f}" if usd is not None else "💵 <b>Dólar:</b> n/d",
        f"   {formatar_variacao_pct(usd_var)}",
        "",
        f"💶 <b>Euro:</b> R$ {eur:.4f}" if eur is not None else "💶 <b>Euro:</b> n/d",
        f"   {formatar_variacao_pct(eur_var)}",
        "",
        f"🥇 <b>Ouro:</b> R$ {gold_brl_g:.2f}/g" if gold_brl_g is not None else "🥇 <b>Ouro:</b> n/d",
        f"   {formatar_variacao_pct(gold_var)}",
        "",
        f"🥈 <b>Prata:</b> R$ {silver_brl_g:.2f}/g" if silver_brl_g is not None else "🥈 <b>Prata:</b> n/d",
        f"   {formatar_variacao_pct(silver_var)}",
    ]

    return "\n".join(linhas)


def gerar_insight_estrategico(resumo_brief: str) -> str:
    prompt = f"""
{contexto_sistema_base()}

Com base neste Morning Brief:
{resumo_brief}

Crie um insight estratégico cirúrgico.
Estrutura obrigatória:
- Tendência
- Risco
- Oportunidade
- Ação prática

Regras:
- máximo de 8 linhas
- sem genericidade
- não force relação com Coralli ou Mané
- só conecte com Coralli ou Mané se houver aderência real ao noticiário
- linguagem de conselheiro de negócios sênior
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    return resposta.output_text.strip()


def gerar_capricornio_do_dia() -> str:
    prompt = """
Crie uma leitura curta para Capricórnio hoje.
Tom elegante, maduro, disciplinado e ambicioso.
Nada místico demais.
Máximo de 3 frases.
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    return resposta.output_text.strip()


def montar_partes_mensagem_dia() -> list[str]:
    hoje = datetime.now(FUSO).strftime("%d/%m/%Y")

    bloco_1 = [
        "☀️ <b>AGENTE VIRTUAL SAULO | MORNING BRIEF EXECUTIVO</b>",
        f"<b>{hoje}</b>",
        "",
        "Leitura de até 10 minutos para começar o dia com repertório, contexto e direção.",
        "",
    ]

    bloco_2 = []
    resumo_para_insight = []
    total_materias = 0
    links_usados = set()

    for categoria in CATEGORIAS_BRIEF:
        if total_materias >= MAX_MATERIAS:
            break

        materia = selecionar_melhor_materia(categoria["queries"])
        if not materia:
            continue

        if materia["link"] in links_usados:
            continue

        titulo = html.escape(materia["titulo"])
        link = html.escape(materia["link"])
        fonte = html.escape(materia["fonte"])
        resumo = html.escape(
            resumir_descricao_executiva(materia["titulo"], materia["descricao"])
        )

        bloco_2.extend([
            f"• <b>{html.escape(categoria['nome'])}</b>",
            f'  <a href="{link}">{titulo}</a>',
            f"  {resumo}",
            f"  <i>Fonte:</i> {fonte}",
            "",
        ])

        resumo_para_insight.append(
            f"{categoria['nome']}: {materia['titulo']} | {materia['descricao']}"
        )

        links_usados.add(materia["link"])
        total_materias += 1

    if total_materias < MAX_MATERIAS:
        for i, query in enumerate(QUERIES_RESERVA, start=1):
            if total_materias >= MAX_MATERIAS:
                break

            materia = selecionar_melhor_materia([query])
            if not materia:
                continue

            if materia["link"] in links_usados:
                continue

            nome_categoria = f"Radar Extra {i}"

            titulo = html.escape(materia["titulo"])
            link = html.escape(materia["link"])
            fonte = html.escape(materia["fonte"])
            resumo = html.escape(
                resumir_descricao_executiva(materia["titulo"], materia["descricao"])
            )

            bloco_2.extend([
                f"• <b>{nome_categoria}</b>",
                f'  <a href="{link}">{titulo}</a>',
                f"  {resumo}",
                f"  <i>Fonte:</i> {fonte}",
                "",
            ])

            resumo_para_insight.append(
                f"{nome_categoria}: {materia['titulo']} | {materia['descricao']}"
            )

            links_usados.add(materia["link"])
            total_materias += 1

    resumo_texto = "\n".join(resumo_para_insight)

    try:
        insight = html.escape(gerar_insight_estrategico(resumo_texto))
    except Exception:
        insight = (
            "Tendência: o noticiário sugere um ambiente em que disciplina de execução e leitura de contexto ganham peso. "
            "Risco: reagir ao ruído e perder foco. Oportunidade: usar repertório para fazer movimentos seletivos. "
            "Ação prática: decidir hoje uma frente para acelerar e uma para proteger."
        )

    try:
        capricornio = html.escape(gerar_capricornio_do_dia())
    except Exception:
        capricornio = (
            "Hoje favorece disciplina, consistência e decisões que reforcem sua construção de longo prazo."
        )

    bloco_3 = [
        "💡 <b>INSIGHT ESTRATÉGICO</b>",
        insight,
        "",
        "♑ <b>CAPRICÓRNIO DO DIA</b>",
        capricornio,
        "",
        montar_bloco_cotacoes(),
    ]

    return [
        "\n".join(bloco_1),
        "\n".join(bloco_2),
        "\n".join(bloco_3),
    ]


async def enviar_blocos(bot, chat_id: int, blocos: list[str]):
    for bloco in blocos:
        await bot.send_message(
            chat_id=chat_id,
            text=bloco,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá, Saulo! 👋\n\n"
        "Sou o Agente Virtual Saulo.\n\n"
        "Comandos ativos:\n"
        "/mensagemdodia\n"
        "/ideiascoralli\n"
        "/ideiasmane\n"
        "/ideiasnegocio\n\n"
        "Também envio automaticamente seu Morning Brief às 06:00."
    )


async def comando_mensagem_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Gerando seu Morning Brief...")
        partes = montar_partes_mensagem_dia()
        await enviar_blocos(context.bot, update.effective_chat.id, partes)
    except Exception as e:
        await update.message.reply_text(f"Erro ao gerar a mensagem do dia: {e}")


async def enviar_mensagem_dia_automaticamente(context: ContextTypes.DEFAULT_TYPE):
    try:
        partes = montar_partes_mensagem_dia()
        await enviar_blocos(context.bot, int(TELEGRAM_CHAT_ID), partes)
        print("Morning Brief enviado com sucesso.")
    except Exception as e:
        print(f"Erro no envio automático: {e}")


def gerar_resposta_usuario(texto_usuario: str) -> str:
    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": contexto_sistema_base()},
            {"role": "user", "content": texto_usuario},
        ],
    )
    return resposta.output_text.strip()


async def comando_ideias_coralli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = f"""
{contexto_sistema_base()}

Crie 5 ideias estratégicas para a Coralli.
Considere crescimento, vendas, experiência do cliente, branding, CRM, operação e posicionamento.
Seja prático e sofisticado.
"""
    resposta = client.responses.create(model="gpt-4.1-mini", input=prompt)
    await update.message.reply_text(resposta.output_text.strip()[:4000])


async def comando_ideias_mane(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = f"""
{contexto_sistema_base()}

Crie 5 ideias estratégicas para o Mané.
Considere gastronomia, entretenimento, experiência, ativações, operação e diferenciação.
Seja prático e sofisticado.
"""
    resposta = client.responses.create(model="gpt-4.1-mini", input=prompt)
    await update.message.reply_text(resposta.output_text.strip()[:4000])


async def comando_ideias_negocio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = f"""
{contexto_sistema_base()}

Crie 5 ideias de negócio para Saulo.
Priorize recorrência, diferenciação, marca, crescimento e geração de caixa.
"""
    resposta = client.responses.create(model="gpt-4.1-mini", input=prompt)
    await update.message.reply_text(resposta.output_text.strip()[:4000])


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    try:
        MEMORIA["discussoes_recentes"].append(texto)
        MEMORIA["discussoes_recentes"] = MEMORIA["discussoes_recentes"][-20:]
        salvar_memoria(MEMORIA)

        await update.message.chat.send_action(action=ChatAction.TYPING)
        resposta = gerar_resposta_usuario(texto)
        await update.message.reply_text(resposta[:4000])
    except Exception as e:
        await update.message.reply_text(f"Erro ao consultar a IA: {str(e)}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mensagemdodia", comando_mensagem_dia))
    app.add_handler(CommandHandler("ideiascoralli", comando_ideias_coralli))
    app.add_handler(CommandHandler("ideiasmane", comando_ideias_mane))
    app.add_handler(CommandHandler("ideiasnegocio", comando_ideias_negocio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app.job_queue.run_daily(
        callback=enviar_mensagem_dia_automaticamente,
        time=time(hour=6, minute=0, tzinfo=FUSO),
        name="morning_brief_6h",
    )

    print("Agente Virtual Saulo rodando...")
    print("Morning Brief agendado para 06:00.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()