"""Baixa documentos REAIS de bancos publicos para calibrar o AIDA Documents.

Fontes (testadas em 19/10/2026):
- NapierOne (Edinburgh Napier University, licenca aberta com atribuicao): 100 (tiny)
  ou ~1.000 (small) arquivos reais por formato, coletados ate 2021-2022, em ingles.
  Bucket publico S3 "napierone.com" (eu-north-1). So os subconjuntos normais: os
  NOMAGIC (cabecalho apagado) e PASSWORD (com senha) nao servem para o AIDA.
- PNCP (Portal Nacional de Contratacoes Publicas, dado publico): editais, termos de
  referencia, atas e contratos de orgaos de todo o Brasil, em PDF e DOCX, de 2023 em
  diante. Documento real brasileiro e recente, de milhares de emissores diferentes.
  Um documento por orgao, para variar o programa gerador.
- SAFEDOCS / CC-MAIN-2021-31-PDF-UNTRUNCATED (Digital Corpora, termos do Common Crawl):
  8,4 milhoes de PDFs da web coletados em jul/ago de 2021, antes do ChatGPT, com o
  dominio de cada um (146 mil de sites .br, de 12 mil dominios). Os ZIPs tem 1,3 GB com
  1.000 PDFs cada; aqui so o indice e os PDFs escolhidos sao baixados (leitura por faixas).
  Um PDF por dominio.
- Querido Diario (Open Knowledge Brasil, dado publico): diarios oficiais de centenas
  de municipios brasileiros, de 2010 ate hoje, em PDF. Cada prefeitura publica pelo
  seu proprio sistema, muitos com assinatura ICP-Brasil. Um diario por emissor (o
  diario de uma associacao de municipios conta como um emissor so).
- Essay-BR estendido (UFPI, MIT): 6.577 redacoes ENEM de dez/2015 a ago/2021, em
  portugues, gravadas como .txt. ATENCAO: o texto traz as correcoes do avaliador
  misturadas ("ex presidente ex-presidente"); nao e o texto puro do aluno.

Os arquivos sao gravados como vieram (nada e regravado, para nao criar marcas de
edicao), cada um com uma linha em <saida>/origem.csv (fonte, licenca, formato).

Uso (na pasta AIDA.ON):
    python -m aida_documents.baixar_amostras napierone --formatos PDF DOCX DOC TXT --tamanho tiny --saida ../reais_publicos
    python -m aida_documents.baixar_amostras essaybr --quantidade 200 --saida ../reais_publicos
    python -m aida_documents.baixar_amostras safedocs --quantidade 100 --dominio br --saida ../reais_publicos
    python -m aida_documents.baixar_amostras pncp --quantidade 100 --inicio 20261001 --fim 20261010 --saida ../reais_publicos
    python -m aida_documents.baixar_amostras queridodiario --quantidade 100 --inicio 2026-10-01 --fim 2026-10-10 --saida ../reais_publicos
"""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import io
import random
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

NAPIERONE = "https://s3.eu-north-1.amazonaws.com/napierone.com/NapierOne/Data/{fmt}/{fmt}-{tamanho}.zip"
ESSAYBR = "https://raw.githubusercontent.com/lplnufpi/essay-br/master/extended-corpus/extended_essay-br.csv"
PNCP_CONSULTA = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
PNCP_ARQUIVOS = "https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
# Pregao eletronico, dispensa, concorrencia eletronica e inexigibilidade: os mais comuns.
PNCP_MODALIDADES = (6, 8, 4, 9)
PNCP_EXTENSOES = {".pdf", ".docx", ".doc", ".txt"}
PNCP_MAX_BYTES = 20 * 1024 * 1024  # mesmo limite da rota /documento/analisar
LICENCA_PNCP = "Dado público (Lei 14.133/2021, art. 174)"
SAFEDOCS = "https://digitalcorpora.s3.amazonaws.com/corpora/files/CC-MAIN-2021-31-PDF-UNTRUNCATED"
LICENCA_SAFEDOCS = "Termos do Common Crawl e da Digital Corpora (pesquisa)"
QUERIDO_DIARIO = "https://api.queridodiario.org.br/gazettes"
LICENCA_QUERIDO_DIARIO = "Dado público (diário oficial); coleta Querido Diário / Open Knowledge Brasil"
LICENCA_NAPIERONE = "Edinburgh Napier University License (livre, com atribuição)"
LICENCA_ESSAYBR = "MIT (LPLN-UFPI)"
_DADO_NAPIERONE = re.compile(r"^\d{4}-[a-z0-9]+\.[a-z0-9]+$")  # 0001-doc.doc; ignora a ficha DOC.pdf


_AGENTE = {"User-Agent": "AIDA-Documents/1.0 (pesquisa academica)"}  # a API do Querido Diario barra o agente padrao do Python


def _baixar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_AGENTE), timeout=600) as resposta:
        return resposta.read()


def _json(url):
    return json.loads(_baixar(url).decode("utf-8"))


def _nome_anexo(url):
    """Nome do arquivo (Content-Disposition) e tamanho, sem baixar o conteudo."""
    req = urllib.request.Request(url, method="HEAD", headers=_AGENTE)
    with urllib.request.urlopen(req, timeout=60) as resposta:
        disp = resposta.headers.get("Content-Disposition", "")
        tamanho = int(resposta.headers.get("Content-Length") or 0)
    achado = re.search(r'filename="?([^";]+)', disp)
    return (achado.group(1) if achado else ""), tamanho


class _ArquivoRemoto(io.RawIOBase):
    """Arquivo HTTP lido por faixas (Range): o zipfile baixa so o indice e os membros pedidos."""

    def __init__(self, url):
        super().__init__()
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as resposta:
            self.tamanho = int(resposta.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, deslocamento, origem=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.tamanho}[origem]
        self.pos = base + deslocamento
        return self.pos

    def readinto(self, buffer):
        if self.pos >= self.tamanho:
            return 0
        fim = min(self.pos + len(buffer), self.tamanho) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{fim}"})
        with urllib.request.urlopen(req, timeout=300) as resposta:
            dados = resposta.read()
        buffer[:len(dados)] = dados
        self.pos += len(dados)
        return len(dados)


def _zip_safedocs(nome_pdf):
    """0001234.pdf -> zipfiles/0000-0999/0001.zip (1.000 PDFs por zip, 1.000 zips por pasta)."""
    numero_zip = int(Path(nome_pdf).stem) // 1000
    pasta = numero_zip // 1000 * 1000
    return f"{SAFEDOCS}/zipfiles/{pasta:04d}-{pasta + 999:04d}/{numero_zip:04d}.zip"


def _registrar(saida, linhas):
    arquivo = Path(saida) / "origem.csv"
    novo = not arquivo.exists()
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["arquivo", "rotulo", "formato", "fonte", "licenca", "detalhe"], delimiter=";")
        if novo:
            escritor.writeheader()
        escritor.writerows(linhas)


def napierone(formatos, tamanho, saida, avisar=print):
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    for fmt in formatos:
        pacote = f"{fmt}-{tamanho}.zip"
        avisar(f"baixando {pacote}...")
        z = zipfile.ZipFile(io.BytesIO(_baixar(NAPIERONE.format(fmt=fmt, tamanho=tamanho))))
        linhas = []
        for info in z.infolist():
            nome = Path(info.filename).name  # descarta pastas do zip: nada sai de <saida>/reais
            if info.is_dir() or not _DADO_NAPIERONE.match(nome):
                continue
            final = f"napierone-{nome}"
            (destino / final).write_bytes(z.read(info))
            linhas.append({"arquivo": final, "rotulo": "REAL", "formato": fmt.lower(),
                           "fonte": f"NapierOne {pacote}", "licenca": LICENCA_NAPIERONE, "detalhe": ""})
        _registrar(saida, linhas)
        avisar(f"  {len(linhas)} arquivos em {destino}")


def essaybr(quantidade, saida, avisar=print):
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    avisar("baixando Essay-BR...")
    csv.field_size_limit(10**8)
    redacoes = list(csv.DictReader(io.StringIO(_baixar(ESSAYBR).decode("utf-8"))))
    linhas = []
    for i, r in enumerate(redacoes[:quantidade], 1):
        try:  # o campo vem como lista Python de paragrafos
            paragrafos = ast.literal_eval(r["essay"])
        except (ValueError, SyntaxError):
            paragrafos = [r["essay"]]
        texto = "\n\n".join(p.strip() for p in paragrafos if p.strip())
        if r.get("title"):
            texto = r["title"].strip() + "\n\n" + texto
        final = f"essaybr-{i:04d}.txt"
        (destino / final).write_text(texto + "\n", encoding="utf-8")
        linhas.append({"arquivo": final, "rotulo": "REAL", "formato": "txt", "fonte": "Essay-BR estendido",
                       "licenca": LICENCA_ESSAYBR, "detalhe": f"tema {r.get('prompt')}, nota {r.get('score')}"})
    _registrar(saida, linhas)
    avisar(f"  {len(linhas)} redações em {destino}")


def pncp(quantidade, inicio, fim, saida, max_por_formato=None, pausa=0.2, avisar=print):
    """Um documento por orgao, alternando modalidades, ate juntar `quantidade`."""
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    max_por_formato = max_por_formato or quantidade
    por_formato, orgaos, linhas = {}, set(), []
    pagina = 1
    while len(linhas) < quantidade:
        achou_algo = False
        for modalidade in PNCP_MODALIDADES:
            consulta = PNCP_CONSULTA + "?" + urllib.parse.urlencode({
                "dataInicial": inicio, "dataFinal": fim, "codigoModalidadeContratacao": modalidade,
                "pagina": pagina, "tamanhoPagina": 50})
            try:
                compras = _json(consulta).get("data") or []
            except Exception as exc:  # pagina fora do fim ou instabilidade: segue com as outras
                avisar(f"  consulta falhou ({modalidade}, p. {pagina}): {exc}")
                continue
            achou_algo = achou_algo or bool(compras)
            for compra in compras:
                if len(linhas) >= quantidade:
                    break
                orgao = compra["orgaoEntidade"]
                if orgao["cnpj"] in orgaos:
                    continue
                try:
                    arquivos = _json(PNCP_ARQUIVOS.format(cnpj=orgao["cnpj"], ano=compra["anoCompra"], seq=compra["sequencialCompra"]))
                    for arq in arquivos:
                        nome, tamanho = _nome_anexo(arq["url"])
                        ext = Path(nome).suffix.lower()
                        if ext not in PNCP_EXTENSOES or tamanho > PNCP_MAX_BYTES or por_formato.get(ext, 0) >= max_por_formato:
                            continue
                        controle = compra["numeroControlePNCP"].replace("/", "-")
                        final = f"pncp-{controle}-{arq['sequencialDocumento']}{ext}"
                        (destino / final).write_bytes(_baixar(arq["url"]))
                        unidade = compra.get("unidadeOrgao") or {}
                        linha = {"arquivo": final, "rotulo": "REAL", "formato": ext[1:], "fonte": "PNCP",
                                 "licenca": LICENCA_PNCP,
                                 "detalhe": f"{orgao['razaoSocial']} ({unidade.get('municipioNome', '')}/{unidade.get('ufSigla', '')}); "
                                            f"{arq.get('tipoDocumentoNome', '')}: {arq.get('titulo', '')}; {arq.get('dataPublicacaoPncp', '')[:10]}"}
                        _registrar(saida, [linha])  # a cada arquivo: um lote interrompido nao perde a origem
                        linhas.append(linha)
                        por_formato[ext] = por_formato.get(ext, 0) + 1
                        orgaos.add(orgao["cnpj"])
                        avisar(f"  [{len(linhas)}/{quantidade}] {final}")
                        break
                except Exception as exc:  # documento fora do ar nao para o lote
                    avisar(f"  {compra.get('numeroControlePNCP')}: {exc}")
                time.sleep(pausa)
        if not achou_algo:
            break
        pagina += 1
    avisar(f"  {len(linhas)} documentos do PNCP em {destino} ({por_formato})")


def _emissor_diario(url):
    """Pasta do PDF no Querido Diario: o municipio, ou a associacao que publica por varios."""
    return urllib.parse.urlparse(url).path.strip("/").split("/")[0]


def querido_diario(quantidade, inicio, fim, saida, pausa=0.2, avisar=print):
    """Um diario oficial por emissor, publicado entre `inicio` e `fim` (AAAA-MM-DD)."""
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    emissores, linhas, deslocamento = set(), [], 0
    while len(linhas) < quantidade:
        consulta = QUERIDO_DIARIO + "?" + urllib.parse.urlencode({
            "published_since": inicio, "published_until": fim, "size": 100, "offset": deslocamento})
        diarios = _json(consulta).get("gazettes") or []
        if not diarios:
            break
        deslocamento += len(diarios)
        for diario in diarios:
            if len(linhas) >= quantidade:
                break
            url = diario.get("url") or ""
            emissor = _emissor_diario(url)
            if not url.lower().endswith(".pdf") or emissor in emissores:
                continue
            try:
                _, tamanho = _nome_anexo(url)
                if tamanho > PNCP_MAX_BYTES:
                    continue
                final = f"qd-{emissor}-{diario['date']}-{Path(url).stem[:12]}.pdf"
                (destino / final).write_bytes(_baixar(url))
                linha = {"arquivo": final, "rotulo": "REAL", "formato": "pdf", "fonte": "Querido Diário",
                         "licenca": LICENCA_QUERIDO_DIARIO,
                         "detalhe": f"{diario.get('territory_name', '')}/{diario.get('state_code', '')}; "
                                    f"edição {diario.get('edition') or '-'}; {diario['date']}"}
                _registrar(saida, [linha])
                linhas.append(linha)
                emissores.add(emissor)
                avisar(f"  [{len(linhas)}/{quantidade}] {final}")
            except Exception as exc:  # diario fora do ar nao para o lote
                avisar(f"  {url}: {exc}")
            time.sleep(pausa)
    avisar(f"  {len(linhas)} diários oficiais em {destino}")


def _hosts_safedocs(dominio, cache, avisar):
    """(arquivo, host) dos PDFs de um dominio de topo; lido uma vez (248 MB) e guardado em cache."""
    if cache.exists():
        with open(cache, encoding="utf-8") as f:
            return [(l["file_name"], l["host"]) for l in csv.DictReader(f)]
    avisar("lendo os metadados de dominio do SAFEDOCS (248 MB, uma vez só)...")
    achados = []
    with urllib.request.urlopen(f"{SAFEDOCS}/metadata/cc-hosts-20230303.csv.gz", timeout=600) as resposta:
        for linha in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=resposta), encoding="utf-8-sig")):
            if linha["tld"] == dominio:
                achados.append((linha["file_name"], linha["host"]))
    with open(cache, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["file_name", "host"])
        escritor.writerows(achados)
    return achados


def safedocs(quantidade, saida, dominio="br", semente=0, avisar=print):
    """Um PDF por dominio, sorteado; baixa por faixas so os PDFs escolhidos."""
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    pdfs = _hosts_safedocs(dominio, Path(saida) / f".safedocs-{dominio}.csv", avisar)
    random.Random(semente).shuffle(pdfs)
    escolhidos, hosts = [], set()
    for nome, host in pdfs:
        if host not in hosts and not (destino / f"safedocs-{nome}").exists():
            hosts.add(host)
            escolhidos.append((nome, host))
        if len(escolhidos) >= quantidade:
            break
    por_zip = {}
    for nome, host in escolhidos:
        por_zip.setdefault(_zip_safedocs(nome), []).append((nome, host))
    gravados = 0
    for url, itens in sorted(por_zip.items()):
        try:
            pacote = zipfile.ZipFile(io.BufferedReader(_ArquivoRemoto(url), buffer_size=1 << 20))
            membros = {Path(n).name: n for n in pacote.namelist()}
            for nome, host in itens:
                info = pacote.getinfo(membros[nome])
                if info.file_size > PNCP_MAX_BYTES:
                    continue
                final = f"safedocs-{nome}"
                (destino / final).write_bytes(pacote.read(info))
                _registrar(saida, [{"arquivo": final, "rotulo": "REAL", "formato": "pdf", "fonte": "SAFEDOCS 2021",
                                    "licenca": LICENCA_SAFEDOCS, "detalhe": f"{host}; {url.rsplit('/', 2)[-2]}/{url.rsplit('/', 1)[-1]}"}])
                gravados += 1
                avisar(f"  [{gravados}/{len(escolhidos)}] {final} ({host})")
        except Exception as exc:  # zip ou membro com problema nao para o lote
            avisar(f"  {url}: {exc}")
    avisar(f"  {gravados} PDFs do SAFEDOCS ({dominio}) em {destino}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="fonte", required=True)
    n1 = sub.add_parser("napierone")
    n1.add_argument("--formatos", nargs="+", default=["PDF", "DOCX", "DOC", "TXT"], choices=["PDF", "DOCX", "DOC", "TXT"])
    n1.add_argument("--tamanho", default="tiny", choices=["tiny", "small"], help="tiny ~100, small ~1.000 por formato")
    n1.add_argument("--saida", default="reais_publicos")
    eb = sub.add_parser("essaybr")
    eb.add_argument("--quantidade", type=int, default=200)
    eb.add_argument("--saida", default="reais_publicos")
    sd = sub.add_parser("safedocs")
    sd.add_argument("--quantidade", type=int, default=100)
    sd.add_argument("--dominio", default="br", help="domínio de topo: br, pt, com...")
    sd.add_argument("--semente", type=int, default=0, help="mude para sortear outros PDFs")
    sd.add_argument("--saida", default="reais_publicos")
    pn = sub.add_parser("pncp")
    pn.add_argument("--quantidade", type=int, default=100)
    pn.add_argument("--inicio", required=True, help="AAAAMMDD")
    pn.add_argument("--fim", required=True, help="AAAAMMDD")
    pn.add_argument("--max-por-formato", type=int, help="ex.: 50 para no máximo 50 PDFs e 50 DOCX")
    pn.add_argument("--saida", default="reais_publicos")
    qd = sub.add_parser("queridodiario")
    qd.add_argument("--quantidade", type=int, default=100)
    qd.add_argument("--inicio", required=True, help="AAAA-MM-DD")
    qd.add_argument("--fim", required=True, help="AAAA-MM-DD")
    qd.add_argument("--saida", default="reais_publicos")
    args = parser.parse_args(argv)
    if args.fonte == "napierone":
        napierone(args.formatos, args.tamanho, args.saida)
    elif args.fonte == "safedocs":
        safedocs(args.quantidade, args.saida, args.dominio, args.semente, avisar=lambda m: print(m, flush=True))
    elif args.fonte == "queridodiario":
        querido_diario(args.quantidade, args.inicio, args.fim, args.saida, avisar=lambda m: print(m, flush=True))
    elif args.fonte == "pncp":
        pncp(args.quantidade, args.inicio, args.fim, args.saida, args.max_por_formato,
             avisar=lambda m: print(m, flush=True))  # progresso aparece mesmo com a saida redirecionada
    else:
        essaybr(args.quantidade, args.saida)


if __name__ == "__main__":
    main()
