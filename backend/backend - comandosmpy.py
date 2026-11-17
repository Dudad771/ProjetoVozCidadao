# VOZ CIDADÃO - BACKEND (Flask + MySQL)

# histórico de buscas nem localização. Tudo é processado só durante a requisição.

import math
import os
import re
import unicodedata
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector import pooling
from werkzeug.exceptions import HTTPException

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from zoneinfo import ZoneInfo
    FUSO = ZoneInfo("America/Recife")
except Exception:  # sem tzdata (Windows) vai usa a hora da máquina
    FUSO = None


# CONEXÃO COM O MYSQL (pool criado na primeira consulta)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="voz_cidadao",
            pool_size=5,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "vozcidadao"),
            charset="utf8mb4",
        )
    return _pool


def consultar(sql, params=None):
    """Executa um SELECT parametrizado e devolve lista de dicionários."""
    conn = _get_pool().get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        linhas = cur.fetchall()
        cur.close()
        return linhas
    finally:
        conn.close()  # devolve ao pool


# CONSTANTES E UTILITÁRIOS

TIPOS = {"HOSPITAL": "Hospital", "UPA": "UPA", "UBS": "UBS",
         "POLICLINICA": "Policlínica", "CAPS": "CAPS"}
DIAS = ["SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO"]  # weekday() 0..6
AVISO_EMERGENCIA = "Em caso de emergência, ligue 192 (SAMU)."


def _agora():
    return datetime.now(FUSO) if FUSO else datetime.now()


def distancia_m(a, b):
    """Distância em metros entre (lat, lon) – Haversine."""
    r = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def formatar_dist(m):
    return f"{round(m)} m" if m < 1000 else f"{m / 1000:.1f} km".replace(".", ",")


def _hhmm(valor):
    """TIME do MySQL chega como timedelta -> 'HH:MM'. NULL -> None (00:00 é válido!)."""
    if valor is None:
        return None
    if isinstance(valor, timedelta):
        minutos = int(valor.total_seconds() // 60)
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    return str(valor)[:5]


def _min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def aberto_agora(u, agora=None):
    """True/False; None se não há horário cadastrado para hoje."""
    if u["atendimento_24h"]:
        return True
    agora = agora or _agora()
    hoje = DIAS[agora.weekday()]
    h = next((h for h in u["horarios"] if h["dia"] == hoje), None)
    if h is None:
        return None
    if h["fechado"] or h["abre"] is None or h["fecha"] is None:
        return False
    return _min(h["abre"]) <= agora.hour * 60 + agora.minute < _min(h["fecha"])


# UNIDADES E SERVIÇOS (MySQL)

def _consultar_unidades(id_unidade=None, tipo=None, id_servico=None, bairro=None, cidade=None):
    """Unidades públicas ativas + serviços + horários (3 consultas, sem N+1)."""
    sql = ("SELECT id_unidade, nome, tipo, endereco, bairro, cidade, uf, cep, telefone, "
           "latitude, longitude, atendimento_24h "
           "FROM unidades_saude WHERE ativa = TRUE AND unidade_publica = TRUE")
    params = []
    if id_unidade:
        sql += " AND id_unidade = %s"
        params.append(id_unidade)
    if tipo:
        sql += " AND tipo = %s"
        params.append(tipo)
    if id_servico:
        sql += (" AND id_unidade IN (SELECT id_unidade FROM unidade_servico"
                " WHERE id_servico = %s)")
        params.append(id_servico)
    if bairro:
        sql += " AND bairro LIKE %s"
        params.append(f"%{bairro}%")
    if cidade:
        sql += " AND cidade LIKE %s"
        params.append(f"%{cidade}%")

    linhas = consultar(sql, params)
    if not linhas:
        return []

    ids = [r["id_unidade"] for r in linhas]
    marcadores = ",".join(["%s"] * len(ids))  # só placeholders; valores vão parametrizados
    servs = consultar(
        "SELECT us.id_unidade, s.nome FROM unidade_servico us "
        "JOIN servicos s ON s.id_servico = us.id_servico "
        f"WHERE s.ativo = TRUE AND us.id_unidade IN ({marcadores}) ORDER BY s.nome", ids)
    hors = consultar(
        "SELECT id_unidade, dia_semana, hora_abertura, hora_fechamento, fechado, observacoes "
        f"FROM horarios_atendimento WHERE id_unidade IN ({marcadores})", ids)

    servs_por, hors_por = {}, {}
    for s in servs:
        servs_por.setdefault(s["id_unidade"], []).append(s["nome"])
    for h in hors:
        hors_por.setdefault(h["id_unidade"], []).append({
            "dia": h["dia_semana"], "abre": _hhmm(h["hora_abertura"]),
            "fecha": _hhmm(h["hora_fechamento"]), "fechado": bool(h["fechado"]),
            "observacoes": h["observacoes"]})

    unidades = []
    for r in linhas:
        horarios = sorted(hors_por.get(r["id_unidade"], []), key=lambda h: DIAS.index(h["dia"]))
        unidades.append({
            "id": r["id_unidade"], "nome": r["nome"],
            "tipo": r["tipo"], "tipo_nome": TIPOS.get(r["tipo"], r["tipo"]),
            "endereco": r["endereco"], "bairro": r["bairro"], "cidade": r["cidade"],
            "uf": r["uf"], "cep": r["cep"], "telefone": r["telefone"],
            "lat": float(r["latitude"]) if r["latitude"] is not None else None,
            "lon": float(r["longitude"]) if r["longitude"] is not None else None,
            "atendimento_24h": bool(r["atendimento_24h"]),
            "servicos": servs_por.get(r["id_unidade"], []),
            "horarios": horarios,
        })
    return unidades


def buscar_unidades(tipo=None, id_servico=None, bairro=None, cidade=None,
                    limite=3, localizacao=None):
    """Unidades filtradas; ordenadas por distância se houver localização, senão por nome."""
    lista = _consultar_unidades(tipo=tipo, id_servico=id_servico, bairro=bairro, cidade=cidade)
    for u in lista:
        u["aberto"] = aberto_agora(u)
        if localizacao and u["lat"] is not None and u["lon"] is not None:
            u["dist_m"] = distancia_m(localizacao, (u["lat"], u["lon"]))
            u["distancia"] = formatar_dist(u["dist_m"])
            u["minutos"] = max(1, round(u["dist_m"] / 80))  # ~80 m/min a pé
        else:
            u["dist_m"] = u["distancia"] = u["minutos"] = None
    lista.sort(key=lambda u: (u["dist_m"] is None, u["dist_m"] or 0, u["nome"]))
    return lista[:limite]


def obter_unidade(id_unidade):
    lista = _consultar_unidades(id_unidade=id_unidade)
    if not lista:
        return None
    lista[0]["aberto"] = aberto_agora(lista[0])
    return lista[0]


def listar_servicos():
    """Catálogo de serviços de saúde (serve de sugestões clicáveis no front)."""
    return [{"id": r["id_servico"], "nome": r["nome"], "descricao": r["descricao"]}
            for r in consultar("SELECT id_servico, nome, descricao FROM servicos "
                               "WHERE ativo = TRUE ORDER BY nome")]


# GUIAS PASSO A PASSO (gov.br, INSS, etc.)
# como o banco não tem tabela para isso, então continuam aqui no código....


_GUIAS = [
    ("vacina", "Carteira de vacinação digital",
     "carteira de vacinacao,cartao de vacina,comprovante de vacina,conecte sus",
     "https://conectesus-paciente.saude.gov.br/",
     "Abra o site do Conecte SUS (botão abaixo).|Toque em \"Entrar com gov.br\".|"
     "Faça login com seu CPF e senha do gov.br.|No menu, procure por \"Vacinação\" ou \"Carteira de vacinação\".|"
     "Toque em \"Baixar\" ou \"Compartilhar\" para salvar o comprovante."),
    ("cartao_sus", "Cartão Nacional de Saúde (Cartão SUS)",
     "cartao sus,cartao do sus,cns,numero do sus",
     "https://conectesus-paciente.saude.gov.br/",
     "Abra o Conecte SUS (botão abaixo).|Entre com sua conta gov.br.|"
     "No início, procure \"Meus dados\" ou \"Cartão Nacional de Saúde\".|Anote o número ou salve a imagem do cartão."),
    ("inss", "Meu INSS (aposentadoria, benefícios, perícia)",
     "inss,aposentadoria,meu inss,pericia,beneficio,auxilio doenca,extrato",
     "https://meu.inss.gov.br/",
     "Abra o Meu INSS (botão abaixo).|Toque em \"Entrar com gov.br\".|"
     "Use a caixa de busca e digite o que precisa (ex.: \"extrato\", \"agendar perícia\").|"
     "Escolha o serviço na lista e siga as telas até \"Confirmar\"."),
    ("cpf", "CPF – consulta e segunda via",
     "cpf,segunda via do cpf,regularizar cpf,situacao cadastral",
     "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/cpf",
     "Abra a página do CPF no site da Receita (botão abaixo).|Procure o serviço \"Consultar situação cadastral\" ou \"Segunda via\".|"
     "Informe o CPF e a data de nascimento.|Siga as instruções para consultar ou imprimir."),
    ("titulo", "Título de eleitor e local de votação",
     "titulo de eleitor,titulo eleitoral,local de votacao,onde votar,zona eleitoral",
     "https://www.tse.jus.br/servicos-eleitorais/titulo-e-local-de-votacao",
     "Abra o site do TSE (botão abaixo).|Escolha \"Consulta ao local de votação\" ou \"Título de eleitor\".|"
     "Informe nome, data de nascimento e nome da mãe (ou número do título).|Confira zona, seção e endereço."),
    ("cadunico", "CadÚnico / Bolsa Família",
     "bolsa familia,cadunico,cad unico,cadastro unico,auxilio brasil",
     "https://www.gov.br/mds/pt-br",
     "O cadastro é feito no CRAS do seu bairro: leve documento com foto, CPF e comprovante de endereço.|"
     "Para consultar benefícios, abra o site do Ministério (botão abaixo).|Procure \"Bolsa Família\" ou \"CadÚnico\" no menu.|"
     "Em caso de dúvida, ligue 156."),
    ("seguro", "Seguro-desemprego",
     "seguro desemprego,seguro-desemprego,fui demitido,demissao",
     "https://www.gov.br/trabalho-e-emprego/pt-br",
     "Abra o site do Ministério do Trabalho (botão abaixo).|Procure \"Seguro-Desemprego\" na busca da página.|"
     "Entre com gov.br e siga \"Solicitar\".|Tenha em mãos a carteira de trabalho e o termo de rescisão."),
    ("iptu", "IPTU e serviços da Prefeitura",
     "iptu,imposto predial,imposto da casa,taxa da prefeitura,segunda via iptu",
     "https://www.recife.pe.gov.br/",
     "Abra o portal da Prefeitura (botão abaixo).|Procure \"Serviços\" > \"IPTU\" (ou use a lupa de busca).|"
     "Informe a inscrição do imóvel ou o CPF.|Escolha \"Segunda via\" ou \"Consultar débitos\"."),
    ("govbr", "Conta gov.br (criar, recuperar senha, níveis)",
     "gov br,conta gov,senha gov,nivel prata,nivel ouro,login gov,esqueci a senha",
     "https://www.gov.br/pt-br",
     "Abra o gov.br (botão abaixo).|Toque em \"Entrar\" (canto superior direito).|"
     "Para recuperar a senha, toque em \"Esqueci minha senha\" e informe o CPF.|"
     "Para subir de nível, entre em \"Selos de confiabilidade\" no seu perfil."),
    ("ouvidoria", "Reclamações e solicitações à Prefeitura (156)",
     "reclamacao,buraco,iluminacao,lixo,ouvidoria,156,denuncia,poste apagado",
     "https://www.recife.pe.gov.br/",
     "Ligue 156 (Central de Atendimento da Prefeitura) ou abra o portal (botão abaixo).|"
     "Escolha o assunto (ex.: iluminação, limpeza urbana).|Informe o endereço e descreva o problema.|"
     "Guarde o número do protocolo para acompanhar."),
]

GUIAS = [
    {"chave": ch, "titulo": ti, "palavras": pa, "url": url, "passos": pas.split("|")}
    for ch, ti, pa, url, pas in _GUIAS
]


def listar_guias():
    return [dict(g) for g in GUIAS]


def obter_guia(chave):
    g = next((g for g in GUIAS if g["chave"] == chave), None)
    return dict(g) if g else None


# INTERPRETAÇÃO DA FALA / TEXTO

def normalizar(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " " + re.sub(r"[^a-z0-9 ]", " ", t) + " "


def _tem(texto_norm, palavra):
    p = normalizar(palavra).strip()
    return (f" {p} " in texto_norm) if len(p) <= 4 else (p in texto_norm)



PALAVRAS_TIPO = {
    "posto": "UBS", "ubs": "UBS", "upa": "UPA", "pronto atendimento": "UPA",
    "hospital": "HOSPITAL", "policlinica": "POLICLINICA", "clinica": "POLICLINICA",
    "caps": "CAPS", "saude mental": "CAPS",
}
# palavras que indicam "quero uma unidade" sem filtro
PALAVRAS_GENERICAS = ["unidade", "saude", "perto de mim", "mais proxima", "mais proximo",
                      "atendimento medico"]
# sinônimos por serviço (chave = nome do serviço normalizado, como está em `servicos.nome`)
SINONIMOS_SERVICO = {
    "vacinacao": ["vacina", "vacinar", "imunizacao"],
    "pediatria": ["pediatra", "pediatrico", "crianca", "infantil", "bebe"],
    "atendimento de urgencia": ["urgencia", "emergencia", "passando mal", "pronto socorro"],
    "clinica medica": ["clinico geral", "medico", "consulta", "doente"],
}


def interpretar(texto, servicos=None, guias=None):
    """Frase -> intenção: 'guia' (passo a passo), 'unidade' (busca no banco) ou 'desconhecido'."""
    servicos = servicos if servicos is not None else listar_servicos()
    guias = guias if guias is not None else GUIAS
    t = normalizar(texto)

    melhor_guia, pontos_guia = None, 0
    for g in guias:
        p = sum(1 for k in g["palavras"].split(",") if _tem(t, k))
        if p > pontos_guia:
            melhor_guia, pontos_guia = g["chave"], p

    pontos_un, filtro_tipo = 0, None
    for k, tp in PALAVRAS_TIPO.items():
        if _tem(t, k):
            pontos_un += 1
            filtro_tipo = filtro_tipo or tp
    if any(_tem(t, k) for k in PALAVRAS_GENERICAS):
        pontos_un += 1

    melhor_serv, hits_serv = None, 0
    for s in servicos:
        termos = [s["nome"]] + SINONIMOS_SERVICO.get(normalizar(s["nome"]).strip(), [])
        h = sum(1 for k in termos if _tem(t, k))
        if h > hits_serv:
            melhor_serv, hits_serv = s, h
    if melhor_serv:
        pontos_un += 1

    if pontos_guia and pontos_guia >= pontos_un:  
        return {"tipo": "guia", "chave": melhor_guia}
    if pontos_un:
        return {"tipo": "unidade", "filtro_tipo": filtro_tipo,
                "id_servico": melhor_serv["id"] if melhor_serv else None,
                "servico": melhor_serv["nome"] if melhor_serv else None}
    return {"tipo": "desconhecido"}


def processar_comando(texto, localizacao=None, bairro=None, cidade=None):
    """
    Recebe a frase e devolve:
      texto, intencao, mensagem
      unidades (tipo 'unidade') | guia (tipo 'guia')
      aviso    (orientação de emergência, quando fizer sentido)
    Nada daqui é gravado.
    """
    intencao = interpretar(texto)
    resposta = {"texto": texto, "intencao": intencao}

    if intencao["tipo"] == "unidade":
        unidades = buscar_unidades(intencao["filtro_tipo"], intencao["id_servico"],
                                   bairro, cidade, localizacao=localizacao)
        resposta["unidades"] = unidades
        if unidades:
            ordem = "mais próximas" if localizacao else "encontradas"
            resposta["mensagem"] = f"Unidades públicas {ordem}."
        else:
            resposta["mensagem"] = "Não encontrei unidade pública com esse critério."
        urgente = (intencao["servico"] and "urgencia" in normalizar(intencao["servico"])) \
            or intencao["filtro_tipo"] in ("UPA", "HOSPITAL")
        if urgente:
            resposta["aviso"] = AVISO_EMERGENCIA
    elif intencao["tipo"] == "guia":
        guia = obter_guia(intencao["chave"])
        resposta["guia"] = guia
        resposta["mensagem"] = f"Vamos mostrar o passo a passo: {guia['titulo']}."
    else:
        resposta["mensagem"] = "Não identifiquei o que você precisa. Tente falar de outro jeito."
    return resposta


# RECONHECIMENTO DE VOZ (opcional – microfone da máquina do servidor)

class ErroReconhecimento(Exception):
    """Falha ao captar/entender a voz; a mensagem pode ser mostrada ao usuário."""


def reconhecer_voz(timeout=8, limite_frase=12):
    """Escuta o microfone e devolve o texto. O áudio NÃO é salvo em arquivo."""
    if sr is None:
        raise ErroReconhecimento(
            "O reconhecimento de voz não está instalado (pip install SpeechRecognition pyaudio).")
    r = sr.Recognizer()
    try:
        with sr.Microphone() as fonte:
            r.adjust_for_ambient_noise(fonte, duration=0.5)
            audio = r.listen(fonte, timeout=timeout, phrase_time_limit=limite_frase)
        return r.recognize_google(audio, language="pt-BR")
    except sr.WaitTimeoutError:
        raise ErroReconhecimento("Não ouvi nenhuma voz. Tente de novo.")
    except sr.UnknownValueError:
        raise ErroReconhecimento("Não consegui entender. Fale mais devagar e perto do microfone.")
    except sr.RequestError:
        raise ErroReconhecimento("Sem conexão com o serviço de voz. Verifique a internet.")
    except Exception as ex:
        raise ErroReconhecimento(f"Microfone indisponível ({ex.__class__.__name__}).")


# API (Flask)

app = Flask(__name__)
CORS(app)
app.json.ensure_ascii = False


def _localizacao(dados):
    """(lat, lon) válidos ou None. Sem localização, o front pode mandar 'bairro'."""
    try:
        lat, lon = float(dados["lat"]), float(dados["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


@app.get("/api/servicos")
def api_servicos():
    return jsonify(listar_servicos())  # alguns exemplos: vacinação, pediatria, urgência...


@app.get("/api/guias")
def api_guias():
    return jsonify(listar_guias())


@app.get("/api/guias/<chave>")
def api_guia(chave):
    g = obter_guia(chave)
    return (jsonify(g), 200) if g else (jsonify({"erro": "Guia não encontrado."}), 404)


@app.get("/api/unidades/<int:id_unidade>")
def api_unidade(id_unidade):
    u = obter_unidade(id_unidade)
    return (jsonify(u), 200) if u else (jsonify({"erro": "Unidade não encontrada."}), 404)


@app.post("/api/unidades/buscar")
def api_buscar_unidades():
    d = request.get_json(silent=True) or {}
    tipo = (d.get("tipo") or "").upper() or None
    if tipo and tipo not in TIPOS:
        return jsonify({"erro": f"Tipo inválido. Use: {', '.join(TIPOS)}."}), 400
    try:
        id_servico = int(d["id_servico"]) if d.get("id_servico") else None
        limite = min(max(int(d.get("limite", 3)), 1), 20)
    except (TypeError, ValueError):
        return jsonify({"erro": "id_servico e limite devem ser números."}), 400
    unidades = buscar_unidades(tipo, id_servico, d.get("bairro"), d.get("cidade"),
                               limite, _localizacao(d))
    return jsonify(unidades)


@app.post("/api/comando")
def api_comando():
    d = request.get_json(silent=True) or {}
    texto = (d.get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "Envie o campo 'texto'."}), 400
    return jsonify(processar_comando(texto[:300], _localizacao(d), d.get("bairro"), d.get("cidade")))


@app.post("/api/voz")
def api_voz():
    """Escuta o microfone da máquina do servidor e já processa o comando."""
    d = request.get_json(silent=True) or {}
    try:
        texto = reconhecer_voz()
    except ErroReconhecimento as e:
        return jsonify({"erro": str(e)}), 422
    return jsonify(processar_comando(texto, _localizacao(d), d.get("bairro"), d.get("cidade")))


@app.errorhandler(Exception)
def erro_generico(e):
    if isinstance(e, HTTPException):  
        return jsonify({"erro": e.description}), e.code
    app.logger.exception(e)
    return jsonify({"erro": "Erro interno. Tente novamente."}), 500


if __name__ == "__main__":
    app.run(debug=True)