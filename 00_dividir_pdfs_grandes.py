"""
=============================================================================
SCRIPT 0 — DIVIDIR PDFs GRANDES (mais de 100 páginas)
=============================================================================

O que este script faz:
  - Verifica todos os PDFs da pasta 'processos/'
  - PDFs com mais de 100 páginas são divididos em partes de 80 páginas
  - O arquivo original é movido para 'processos/originais_grandes/'
  - As partes ficam na pasta 'processos/' com o sufixo _parte1, _parte2, etc.

Por que 80 páginas?
  O limite da API da Anthropic é 100 páginas. Usamos 80 como margem de segurança.

Como instalar:
  pip3 install pypdf

Como rodar (antes do Script 1):
  python3 00_dividir_pdfs_grandes.py

=============================================================================
"""

import shutil
from pathlib import Path
from pypdf import PdfReader, PdfWriter


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

PASTA_PROCESSOS  = "processos"
PASTA_ORIGINAIS  = "processos/originais_grandes"  # Guarda os PDFs originais
PAGINAS_POR_PART = 80                              # Páginas por parte
LIMITE_PAGINAS   = 100                             # Acima disso, divide


# =============================================================================
# FUNÇÕES
# =============================================================================

def dividir_pdf(caminho_pdf: Path, paginas_por_parte: int) -> list:
    """
    Divide um PDF em partes menores.

    Parâmetros:
        caminho_pdf: caminho para o PDF original
        paginas_por_parte: quantas páginas cada parte terá

    Retorna:
        lista com os caminhos das partes criadas
    """
    leitor = PdfReader(str(caminho_pdf))
    total  = len(leitor.pages)
    partes = []

    # Calcula quantas partes serão criadas
    num_partes = (total + paginas_por_parte - 1) // paginas_por_parte

    print(f"  → Dividindo em {num_partes} parte(s) de até {paginas_por_parte} páginas...")

    for i in range(num_partes):
        inicio = i * paginas_por_parte
        fim    = min(inicio + paginas_por_parte, total)

        # Cria um novo PDF com as páginas desta parte
        escritor = PdfWriter()
        for num_pag in range(inicio, fim):
            escritor.add_page(leitor.pages[num_pag])

        # Nome do arquivo da parte: nome_original_parte1.pdf
        nome_parte = f"{caminho_pdf.stem}_parte{i+1}.pdf"
        caminho_parte = caminho_pdf.parent / nome_parte

        with open(caminho_parte, "wb") as f:
            escritor.write(f)

        partes.append(caminho_parte)
        print(f"    ✓ {nome_parte}  ({fim - inicio} páginas, pág. {inicio+1}–{fim})")

    return partes


def main():
    print("=" * 60)
    print("  DIVISÃO DE PDFs GRANDES — Script 0 de 2")
    print("=" * 60)

    pasta = Path(PASTA_PROCESSOS)
    if not pasta.exists():
        raise FileNotFoundError(
            f"Pasta '{PASTA_PROCESSOS}' não encontrada.\n"
            f"Crie a pasta e coloque os PDFs dentro dela."
        )

    # Cria a pasta para guardar os originais grandes
    Path(PASTA_ORIGINAIS).mkdir(parents=True, exist_ok=True)

    # Lista todos os PDFs
    pdfs = sorted(pasta.glob("*.pdf")) + sorted(pasta.glob("*.PDF"))
    pdfs = list(dict.fromkeys(pdfs))

    if not pdfs:
        print("Nenhum PDF encontrado.")
        return

    print(f"\nVerificando {len(pdfs)} arquivo(s)...\n")

    grandes     = []
    contagem    = 0
    total_partes = 0

    for caminho_pdf in pdfs:
        try:
            leitor = PdfReader(str(caminho_pdf))
            n_pags = len(leitor.pages)
        except Exception as e:
            print(f"  ⚠ Não foi possível ler {caminho_pdf.name}: {e}")
            continue

        if n_pags <= LIMITE_PAGINAS:
            continue  # PDF pequeno — não precisa dividir

        grandes.append(caminho_pdf)
        print(f"[{len(grandes)}] {caminho_pdf.name}  ({n_pags} páginas)")

        # Divide o PDF
        partes = dividir_pdf(caminho_pdf, PAGINAS_POR_PART)
        total_partes += len(partes)
        contagem += 1

        # Move o original para a pasta de originais
        destino_original = Path(PASTA_ORIGINAIS) / caminho_pdf.name
        shutil.move(str(caminho_pdf), str(destino_original))
        print(f"    Original movido → {PASTA_ORIGINAIS}/\n")

    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    if contagem == 0:
        print("  Nenhum PDF com mais de 100 páginas encontrado.")
    else:
        print(f"  PDFs divididos:    {contagem}")
        print(f"  Partes criadas:    {total_partes}")
        print(f"  Originais em:      '{PASTA_ORIGINAIS}/'")
    print("=" * 60)
    print(f"\nPróximo passo: rode novamente o Script 1 (triagem).")
    print(f"Ele vai pular os arquivos já processados e tratar as novas partes.")


if __name__ == "__main__":
    main()