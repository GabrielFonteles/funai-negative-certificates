"""
=============================================================================
SCRIPT 2b — REEXTRAÇÃO DE COORDENADAS COMPLETAS
=============================================================================

O que este script faz:
  - Lê o CSV já gerado pelo Script 2
  - Para cada linha, reenvia o PDF ao Claude pedindo APENAS as coordenadas
    completas (todos os vértices, exatamente como constam no documento)
  - Atualiza apenas a coluna "Coordenadas Geográficas" no CSV
  - Preserva todos os outros campos intactos
  - Salva o progresso após cada arquivo

IMPORTANTE:
  As coordenadas são transcritas fielmente como constam nos documentos
  originais — erros, inconsistências e imprecisões são preservados
  intencionalmente, pois constituem evidência histórica.

Como instalar:
  pip3 install anthropic

Como rodar (depois do Script 2):
  python3 02b_reextrair_coordenadas.py

=============================================================================
"""

import os
import csv
import json
import time
import base64
import anthropic
from pathlib import Path


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

PASTA_PDFS           = "com_certidao"
ARQUIVO_CSV_ENTRADA  = "certidoes_negativas_funai.csv"
ARQUIVO_CSV_SAIDA    = "certidoes_negativas_funai_v2.csv"
ARQUIVO_PROGRESSO    = "progresso_coordenadas.json"

CHAVE_API = ""  # Cole aqui: "sk-ant-..." ou use variável ANTHROPIC_API_KEY

MODELO           = "claude-sonnet-4-5"
PAUSA_ENTRE_PDFS = 3
MAX_TENTATIVAS   = 3
PAUSA_RETRY      = 30

# Nome exato da coluna de coordenadas no CSV
COLUNA_COORDENADAS = "Coordenadas Geográficas"
COLUNA_REFERENCIA  = "Referência (arquivo)"


# =============================================================================
# PROMPT DE COORDENADAS
# Foco exclusivo nas coordenadas — transcrição fiel, sem correções.
# =============================================================================

PROMPT_COORDENADAS = """
Analise este documento PDF, que é um processo administrativo da FUNAI
relativo a uma Certidão Negativa de presença ou aldeamento indígena.

Sua tarefa é extrair TODAS as coordenadas geográficas que definem os
limites da área pleiteada, exatamente como aparecem no documento.

REGRAS IMPORTANTES:
- Transcreva as coordenadas FIELMENTE como constam no documento original
- NÃO corrija erros, NÃO normalize formatos, NÃO interprete ambiguidades
- Se houver inconsistências ou coordenadas aparentemente erradas, transcreva
  assim mesmo — esses erros são evidência histórica importante
- Se as coordenadas aparecerem em uma tabela de vértices, liste TODOS os
  vértices com seus números e valores exatos
- Se aparecerem apenas os extremos (N, S, L, W), liste-os exatamente
- Se houver coordenadas UTM E geográficas, inclua ambas

Responda APENAS com um JSON no seguinte formato, sem texto adicional:

{
  "formato": "vertice" ou "extremos" ou "misto" ou "ausente",
  "sistema": "geografico" ou "UTM" ou "ambos",
  "datum": "datum geodésico se mencionado, ex: SAD69, WGS84, ou null",
  "total_vertices": número inteiro ou null,
  "coordenadas_raw": "transcrição fiel de TODAS as coordenadas, exatamente como aparecem no documento",
  "vertices": [
    {
      "id": "identificador do vértice como aparece no documento, ex: 1, P1, Marco 1",
      "lat_raw": "latitude exatamente como escrita no documento",
      "lon_raw": "longitude exatamente como escrita no documento",
      "lat_decimal": número decimal ou null,
      "lon_decimal": número decimal ou null
    }
  ]
}

Para converter para decimal (quando possível):
  - Sul e Oeste são negativos
  - Graus + minutos/60 + segundos/3600
  - Ex: 10°14'10"S = -10.2361
  - Ex: 49°36'40"W = -49.6111
  - Se não for possível converter com certeza, use null

Se não houver coordenadas no documento, retorne:
{
  "formato": "ausente",
  "sistema": null,
  "datum": null,
  "total_vertices": null,
  "coordenadas_raw": null,
  "vertices": []
}
"""


# =============================================================================
# FUNÇÕES
# =============================================================================

def pdf_para_base64(caminho_pdf: str) -> str:
    """Converte um PDF em Base64."""
    with open(caminho_pdf, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extrair_coordenadas_do_pdf(cliente, caminho_pdf: str) -> dict:
    """
    Envia um PDF ao Claude e retorna apenas as coordenadas.
    Tenta até MAX_TENTATIVAS vezes em caso de erro temporário.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            print(f"  → Enviando para o Claude (tentativa {tentativa}/{MAX_TENTATIVAS})...")
            pdf_b64 = pdf_para_base64(caminho_pdf)

            resposta = cliente.messages.create(
                model=MODELO,
                max_tokens=4000,  # Mais tokens para acomodar listas longas de vértices
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": PROMPT_COORDENADAS,
                            },
                        ],
                    }
                ],
            )

            texto = resposta.content[0].text.strip()

            if texto.startswith("```"):
                linhas = texto.split("\n")
                texto = "\n".join(linhas[1:-1]).strip()

            return json.loads(texto)

        except Exception as e:
            erro_str = str(e)
            if any(x in erro_str.lower() for x in ["rate", "overloaded", "529"]):
                if tentativa < MAX_TENTATIVAS:
                    print(f"  ⚠ API sobrecarregada. Aguardando {PAUSA_RETRY}s...")
                    time.sleep(PAUSA_RETRY)
                    continue
            raise

    raise Exception(f"Falhou após {MAX_TENTATIVAS} tentativas.")


def carregar_csv(caminho: str) -> tuple:
    """
    Lê o CSV e retorna:
      - lista de dicionários (uma por linha)
      - lista com os nomes das colunas (para preservar a ordem)
    """
    with open(caminho, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        colunas = reader.fieldnames
        linhas  = list(reader)
    return linhas, colunas


def salvar_csv(linhas: list, colunas: list, caminho: str):
    """Salva o CSV com as colunas na ordem original mais as novas."""
    # Adiciona as novas colunas de coordenadas se ainda não existirem
    novas_colunas = [
        "Coordenadas Formato",
        "Coordenadas Sistema",
        "Datum",
        "Total Vértices",
        "Coordenadas Raw",
        "Vértices JSON",
    ]
    todas_colunas = list(colunas)
    for col in novas_colunas:
        if col not in todas_colunas:
            todas_colunas.append(col)

    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=todas_colunas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)

    print(f"\n✓ CSV atualizado salvo em: {caminho}")


def carregar_progresso() -> set:
    """Retorna o set de arquivos já reprocessados."""
    if not Path(ARQUIVO_PROGRESSO).exists():
        return set()
    with open(ARQUIVO_PROGRESSO, "r", encoding="utf-8") as f:
        return set(json.load(f))


def salvar_progresso(ja_feitos: set):
    """Salva o progresso após cada arquivo."""
    with open(ARQUIVO_PROGRESSO, "w", encoding="utf-8") as f:
        json.dump(list(ja_feitos), f, ensure_ascii=False)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  REEXTRAÇÃO DE COORDENADAS — Script 2b")
    print("  (usando Anthropic Claude)")
    print("=" * 60)

    # Configura a API
    chave = CHAVE_API or os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise ValueError(
            "Chave de API não encontrada!\n"
            "Defina CHAVE_API no início do script ou execute:\n"
            "  export ANTHROPIC_API_KEY='sua-chave'"
        )
    cliente = anthropic.Anthropic(api_key=chave)

    # Carrega o CSV
    print(f"\nLendo CSV: {ARQUIVO_CSV_ENTRADA}...")
    if not Path(ARQUIVO_CSV_ENTRADA).exists():
        raise FileNotFoundError(f"Arquivo '{ARQUIVO_CSV_ENTRADA}' não encontrado.")
    linhas, colunas = carregar_csv(ARQUIVO_CSV_ENTRADA)
    print(f"  {len(linhas)} linha(s) encontrada(s).")

    # Carrega progresso anterior
    ja_feitos = carregar_progresso()
    if ja_feitos:
        print(f"  ℹ {len(ja_feitos)} arquivo(s) já reprocessado(s) — serão pulados.")

    # Cria índice das linhas por nome de arquivo para atualização rápida
    indice = {linha[COLUNA_REFERENCIA]: i for i, linha in enumerate(linhas)}

    # Filtra os que ainda precisam ser processados
    pendentes = [
        linha for linha in linhas
        if linha[COLUNA_REFERENCIA] not in ja_feitos
    ]
    print(f"  {len(pendentes)} arquivo(s) a processar.\n")

    if not pendentes:
        print("Todos já reprocessados! Gerando CSV final...")
        salvar_csv(linhas, colunas, ARQUIVO_CSV_SAIDA)
        return

    erros = []

    for i, linha in enumerate(pendentes, start=1):
        nome_arquivo = linha[COLUNA_REFERENCIA]
        caminho_pdf  = Path(PASTA_PDFS) / nome_arquivo

        print(f"[{i}/{len(pendentes)}] {nome_arquivo}")

        # Verifica se o PDF existe
        if not caminho_pdf.exists():
            print(f"  ⚠ PDF não encontrado em '{PASTA_PDFS}/' — pulando.\n")
            erros.append(nome_arquivo)
            continue

        try:
            coords = extrair_coordenadas_do_pdf(cliente, str(caminho_pdf))

            # Atualiza a linha no índice com os novos dados de coordenadas
            idx = indice[nome_arquivo]
            linhas[idx]["Coordenadas Formato"]  = coords.get("formato", "")
            linhas[idx]["Coordenadas Sistema"]   = coords.get("sistema", "")
            linhas[idx]["Datum"]                 = coords.get("datum", "")
            linhas[idx]["Total Vértices"]        = coords.get("total_vertices", "")
            linhas[idx]["Coordenadas Raw"]       = coords.get("coordenadas_raw", "")

            # Vértices salvos como JSON string para não quebrar o CSV
            vertices = coords.get("vertices", [])
            linhas[idx]["Vértices JSON"] = json.dumps(vertices, ensure_ascii=False)

            # Resumo no terminal
            fmt   = coords.get("formato", "—")
            total = coords.get("total_vertices", "—")
            print(f"  ✓ Concluído — formato: {fmt} | vértices: {total}\n")

            ja_feitos.add(nome_arquivo)

        except json.JSONDecodeError as e:
            print(f"  ✗ Erro ao interpretar JSON: {e}\n")
            erros.append(nome_arquivo)

        except Exception as e:
            print(f"  ✗ Erro: {e}\n")
            erros.append(nome_arquivo)

        # Salva progresso e CSV parcial após cada arquivo
        salvar_progresso(ja_feitos)
        salvar_csv(linhas, colunas, ARQUIVO_CSV_SAIDA)

        if i < len(pendentes):
            time.sleep(PAUSA_ENTRE_PDFS)

    # Resumo final
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Total de linhas no CSV:    {len(linhas)}")
    print(f"  Reprocessados com êxito:   {len(ja_feitos)}")
    print(f"  Erros:                     {len(erros)}")
    print(f"  Arquivo gerado:            {ARQUIVO_CSV_SAIDA}")
    print("=" * 60)
    if erros:
        print("\nArquivos com erro:")
        for e in erros:
            print(f"  - {e}")


if __name__ == "__main__":
    main()