"""
=============================================================================
SCRIPT 6 — CRUZAMENTO POR POVO / TERRA INDÍGENA
=============================================================================

O que este script faz:
  - Lê a tabela de reportagens e o CSV das certidões
  - Cruza APENAS pelo campo Povo / Terra Indígena
  - Só inclui na tabela final os povos/TIs que aparecem em AMBAS as tabelas
  - Usa fuzzy matching para lidar com variações de grafia
  - Gera uma tabela limpa e objetiva

Colunas da tabela de saída:
  - Povo/TI
  - Número do Processo (certidão)
  - Data da Certidão
  - Título da Reportagem
  - Data da Reportagem
  - Observações (certidão)
  - Evento Mencionado (reportagem)
  - Link da Reportagem

100% local — sem API, sem tokens.

Como instalar:
  pip3 install rapidfuzz

Como rodar:
  python3 06_cruzamento_povos.py

=============================================================================
"""

import csv
import re
from pathlib import Path
from rapidfuzz import fuzz, process


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ARQUIVO_REPORTAGENS = "reportagens_certidoes_negativas.csv"
ARQUIVO_CERTIDOES   = "certidoes_negativas_funai_v5.csv"
ARQUIVO_SAIDA       = "cruzamento_por_povos.csv"

# Score mínimo de similaridade (0-100)
# 85 = rigoroso, pega só casos bem parecidos
# Reduzir para 75 se estiver perdendo casos óbvios
SCORE_MINIMO = 85


# =============================================================================
# COLUNAS
# =============================================================================

# Reportagens
COL_REP_TITULO   = "Título do texto"
COL_REP_DATA     = "Data da publicação"
COL_REP_POVOS    = "Povo ou terra indígena mencionado"
COL_REP_EVENTO   = "Se houver, evento mencionado (violência, crimes, etc)"
COL_REP_LINK     = "Link da notícia"

# Certidões
COL_CERT_PROCESSO = "Nº do Processo"
COL_CERT_DATA     = "Data da Certidão"
COL_CERT_POVOS    = "Povos ou TIs Mencionados"
COL_CERT_OBS      = "Observações"


# =============================================================================
# FUNÇÕES
# =============================================================================

def limpar(texto: str) -> str:
    """Normaliza texto para comparação: minúsculas, sem espaços extras."""
    if not texto:
        return ""
    return re.sub(r'\s+', ' ', texto.lower().strip())


def separar(texto: str) -> list:
    """
    Separa múltiplos itens de uma string.
    Separadores aceitos: ponto e vírgula, vírgula, quebra de linha.
    Remove itens vazios ou muito curtos (menos de 3 caracteres).
    """
    if not texto:
        return []
    itens = re.split(r'[;,\n]', texto)
    return [limpar(i) for i in itens if len(limpar(i)) >= 3]


def encontrar_match(termo: str, candidatos: list, score_minimo: int):
    """
    Compara um termo com uma lista de candidatos usando fuzzy matching.
    Retorna (melhor_match, score) ou None se não houver match acima do mínimo.
    """
    if not termo or not candidatos:
        return None

    resultado = process.extractOne(
        termo,
        candidatos,
        scorer=fuzz.token_sort_ratio
    )

    if resultado and resultado[1] >= score_minimo:
        return resultado[0], resultado[1]

    return None


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  CRUZAMENTO POR POVO/TI — Script 6")
    print("  (fuzzy matching — 100% local, sem tokens)")
    print("=" * 60)

    # Verifica arquivos
    for arq in [ARQUIVO_REPORTAGENS, ARQUIVO_CERTIDOES]:
        if not Path(arq).exists():
            raise FileNotFoundError(
                f"Arquivo '{arq}' não encontrado.\n"
                f"Verifique se está na pasta correta."
            )

    # Carrega os dados
    print(f"\nCarregando dados...")
    with open(ARQUIVO_REPORTAGENS, "r", encoding="utf-8-sig") as f:
        reportagens = list(csv.DictReader(f))
    with open(ARQUIVO_CERTIDOES, "r", encoding="utf-8-sig") as f:
        certidoes = list(csv.DictReader(f))
    print(f"  {len(reportagens)} reportagens carregadas")
    print(f"  {len(certidoes)} certidões carregadas")

    # Extrai todos os povos/TIs das certidões (com referência à certidão)
    # Estrutura: [(povo_limpo, povo_original, certidao)]
    povos_certidoes = []
    for cert in certidoes:
        for povo in separar(cert.get(COL_CERT_POVOS, "")):
            if povo:
                povos_certidoes.append((povo, cert))

    # Lista de textos para o fuzzy matching
    textos_povos_cert = [p for p, _ in povos_certidoes]

    print(f"\n  {len(povos_certidoes)} entradas de povo/TI nas certidões")

    # Faz o cruzamento
    print(f"\nCruzando por Povo/TI (score mínimo: {SCORE_MINIMO})...\n")

    correspondencias = []
    ja_adicionados   = set()  # Evita duplicatas exatas

    for i, rep in enumerate(reportagens, start=1):
        povos_rep = separar(rep.get(COL_REP_POVOS, ""))

        for povo_rep in povos_rep:
            match = encontrar_match(povo_rep, textos_povos_cert, SCORE_MINIMO)

            if not match:
                continue

            povo_matched, score = match

            # Encontra a(s) certidão(ões) com esse povo
            for povo_cert, cert in povos_certidoes:
                if povo_cert != povo_matched:
                    continue

                # Chave única para evitar duplicatas
                chave = (
                    rep.get(COL_REP_TITULO, ""),
                    cert.get(COL_CERT_PROCESSO, ""),
                    povo_matched
                )
                if chave in ja_adicionados:
                    continue
                ja_adicionados.add(chave)

                correspondencias.append({
                    "Povo/TI":                    povo_matched.title(),
                    "Número do Processo":          cert.get(COL_CERT_PROCESSO, ""),
                    "Data da Certidão":            cert.get(COL_CERT_DATA, ""),
                    "Título da Reportagem":        rep.get(COL_REP_TITULO, ""),
                    "Data da Reportagem":          rep.get(COL_REP_DATA, ""),
                    "Observações (certidão)":      cert.get(COL_CERT_OBS, ""),
                    "Evento Mencionado (rep.)":    rep.get(COL_REP_EVENTO, ""),
                    "Link da Reportagem":          rep.get(COL_REP_LINK, ""),
                    "Score de Similaridade":       score,
                    "Termo na Reportagem":         povo_rep.title(),
                    "Termo na Certidão":           povo_matched.title(),
                })

                print(f"  ✓ [{int(score):3d}] {povo_rep:<25} ↔  {povo_matched}")

    # Ordena por povo e depois por score
    correspondencias.sort(key=lambda x: (x["Povo/TI"], -x["Score de Similaridade"]))

    # Salva o CSV
    if correspondencias:
        colunas = [
            "Povo/TI",
            "Número do Processo",
            "Data da Certidão",
            "Título da Reportagem",
            "Data da Reportagem",
            "Observações (certidão)",
            "Evento Mencionado (rep.)",
            "Link da Reportagem",
            "Score de Similaridade",
            "Termo na Reportagem",
            "Termo na Certidão",
        ]
        with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(correspondencias)
        print(f"\n✓ Tabela salva em: {ARQUIVO_SAIDA}")
    else:
        print("\n  Nenhuma correspondência encontrada.")
        print("  Tente reduzir o SCORE_MINIMO no início do script.")

    # Resumo
    povos_unicos = set(c["Povo/TI"] for c in correspondencias)
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Correspondências encontradas:  {len(correspondencias)}")
    print(f"  Povos/TIs únicos com match:    {len(povos_unicos)}")
    if povos_unicos:
        print(f"\n  Povos/TIs encontrados em ambas as tabelas:")
        for povo in sorted(povos_unicos):
            print(f"    - {povo}")
    print("=" * 60)


if __name__ == "__main__":
    main()
