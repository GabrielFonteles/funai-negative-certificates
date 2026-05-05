"""
=============================================================================
SCRIPT 1 — TRIAGEM DE PROCESSOS FUNAI (versão Anthropic Claude)
=============================================================================

O que este script faz:
  - Lê cada PDF da pasta 'processos/'
  - Pergunta ao Claude: "este processo tem certidão negativa?"
  - Move o PDF para a pasta correta:
      com_certidao/  → processos onde a certidão foi emitida
      sem_certidao/  → processos arquivados sem certidão
  - Gera um relatório JSON com o resultado de cada arquivo
  - Retry automático se a API retornar erro temporário
  - Pula arquivos já processados em execuções anteriores

Como instalar:
  pip3 install anthropic

Como rodar:
  python3 01_triagem_certidoes.py

=============================================================================
"""

import os
import json
import time
import shutil
import base64
import anthropic
from pathlib import Path


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

PASTA_ENTRADA     = "processos"
PASTA_COM_CERT    = "com_certidao"
PASTA_SEM_CERT    = "sem_certidao"
ARQUIVO_RELATORIO = "relatorio_triagem.json"

CHAVE_API = ""  # Cole aqui: "sk-ant-..." ou use variável ANTHROPIC_API_KEY

MODELO = "claude-sonnet-4-5"
PAUSA_ENTRE_PDFS = 2   # Segundos entre chamadas
MAX_TENTATIVAS   = 3   # Quantas vezes tentar antes de registrar como erro
PAUSA_RETRY      = 30  # Segundos de espera entre tentativas


# =============================================================================
# PROMPT DE TRIAGEM
# =============================================================================

PROMPT_TRIAGEM = """
Analise este documento PDF, que é um processo administrativo da FUNAI
(Fundação Nacional do Índio) relativo a pedido de Certidão Negativa de
presença ou aldeamento indígena.

Responda APENAS com um JSON no seguinte formato, sem nenhum texto adicional:

{
  "tem_certidao": true ou false,
  "numero_processo": "número do processo se encontrado, ou null",
  "requerente": "nome do requerente se encontrado, ou null"
}

Critério para "tem_certidao":
- true:  o processo contém uma Certidão Negativa efetivamente emitida
         (documento formal com número, data e assinatura da FUNAI
         declarando ausência de aldeamento indígena na área)
- false: o processo foi arquivado sem emitir certidão, ou o pedido foi
         negado, ou a certidão ainda não havia sido emitida
"""


# =============================================================================
# FUNÇÕES
# =============================================================================

def pdf_para_base64(caminho_pdf: str) -> str:
    """Converte um PDF em Base64 para enviar à API da Anthropic."""
    with open(caminho_pdf, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def classificar_pdf(cliente, caminho_pdf: str) -> dict:
    """
    Envia um PDF ao Claude e recebe a classificação.
    Tenta até MAX_TENTATIVAS vezes em caso de erro temporário.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            print(f"  → Enviando para o Claude (tentativa {tentativa}/{MAX_TENTATIVAS})...")
            pdf_b64 = pdf_para_base64(caminho_pdf)

            resposta = cliente.messages.create(
                model=MODELO,
                max_tokens=300,
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
                                "text": PROMPT_TRIAGEM,
                            },
                        ],
                    }
                ],
            )

            texto = resposta.content[0].text.strip()

            # Remove blocos markdown se presentes
            if texto.startswith("```"):
                linhas = texto.split("\n")
                texto = "\n".join(linhas[1:-1]).strip()

            return json.loads(texto)

        except Exception as e:
            erro_str = str(e)
            # Se for erro de sobrecarga ou rate limit, espera e tenta de novo
            if any(x in erro_str.lower() for x in ["rate", "overloaded", "529", "529"]):
                if tentativa < MAX_TENTATIVAS:
                    print(f"  ⚠ API sobrecarregada. Aguardando {PAUSA_RETRY}s...")
                    time.sleep(PAUSA_RETRY)
                    continue
            raise

    raise Exception(f"Falhou após {MAX_TENTATIVAS} tentativas.")


def carregar_relatorio_existente() -> tuple:
    """
    Carrega o relatório de uma execução anterior (se existir).
    Retorna a lista de registros já processados e um set com os nomes
    dos arquivos já tratados com sucesso — para não reprocessar.
    """
    if not Path(ARQUIVO_RELATORIO).exists():
        return [], set()

    with open(ARQUIVO_RELATORIO, "r", encoding="utf-8") as f:
        relatorio = json.load(f)

    # Só pula arquivos que foram processados sem erro
    ja_processados = {
        r["arquivo"] for r in relatorio if r.get("erro") is None
    }

    if ja_processados:
        print(f"  ℹ {len(ja_processados)} arquivo(s) já processado(s) — serão pulados.")

    return relatorio, ja_processados


def salvar_relatorio(relatorio: list):
    """Salva o relatório JSON. É chamado após cada arquivo para não perder progresso."""
    with open(ARQUIVO_RELATORIO, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)


def criar_pastas():
    """Cria as pastas de destino se não existirem."""
    Path(PASTA_COM_CERT).mkdir(exist_ok=True)
    Path(PASTA_SEM_CERT).mkdir(exist_ok=True)


def mover_pdf(caminho_origem: Path, tem_certidao: bool) -> Path:
    """Move o PDF para a pasta correta."""
    pasta_destino = PASTA_COM_CERT if tem_certidao else PASTA_SEM_CERT
    destino = Path(pasta_destino) / caminho_origem.name

    if destino.exists():
        print(f"  ⚠ Arquivo já existe em '{pasta_destino}/', pulando movimentação.")
        return destino

    shutil.move(str(caminho_origem), str(destino))
    return destino


def listar_pdfs(pasta: str) -> list:
    """Lista todos os PDFs de uma pasta, em ordem alfabética."""
    caminho = Path(pasta)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Pasta '{pasta}' não encontrada.\n"
            f"Crie a pasta e coloque os PDFs dentro dela."
        )
    pdfs = sorted(caminho.glob("*.pdf")) + sorted(caminho.glob("*.PDF"))
    pdfs = list(dict.fromkeys(pdfs))
    if not pdfs:
        raise FileNotFoundError(f"Nenhum PDF encontrado em '{pasta}'.")
    return pdfs


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  TRIAGEM DE PROCESSOS FUNAI — Script 1 de 2")
    print("  (usando Anthropic Claude)")
    print("=" * 60)

    # Configura a API
    chave = CHAVE_API or os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise ValueError(
            "Chave de API não encontrada!\n"
            "Opção 1: defina CHAVE_API no início do script.\n"
            "Opção 2: execute: export ANTHROPIC_API_KEY='sua-chave'"
        )
    cliente = anthropic.Anthropic(api_key=chave)

    # Cria as pastas de destino
    criar_pastas()
    print(f"\nPastas de destino prontas:")
    print(f"  → Com certidão:  '{PASTA_COM_CERT}/'")
    print(f"  → Sem certidão:  '{PASTA_SEM_CERT}/'")

    # Carrega progresso anterior se houver
    print(f"\nVerificando progresso anterior...")
    relatorio, ja_processados = carregar_relatorio_existente()

    # Lista os PDFs e filtra os já processados
    print(f"\nBuscando PDFs em '{PASTA_ENTRADA}'...")
    todos_pdfs = listar_pdfs(PASTA_ENTRADA)
    pdfs = [p for p in todos_pdfs if p.name not in ja_processados]
    print(f"  {len(todos_pdfs)} arquivo(s) encontrado(s) — {len(pdfs)} a processar.\n")

    if not pdfs:
        print("Todos os arquivos já foram processados!")
        return

    # Contadores — já inclui o que foi processado anteriormente
    contagem_com  = sum(1 for r in relatorio if r.get("tem_certidao") is True)
    contagem_sem  = sum(1 for r in relatorio if r.get("tem_certidao") is False)
    contagem_erro = 0

    for i, caminho_pdf in enumerate(pdfs, start=1):
        nome = caminho_pdf.name
        print(f"[{i}/{len(pdfs)}] {nome}")

        try:
            resultado  = classificar_pdf(cliente, str(caminho_pdf))
            tem_cert   = resultado.get("tem_certidao", False)
            num_proc   = resultado.get("numero_processo", "")
            requerente = resultado.get("requerente", "")

            destino      = mover_pdf(caminho_pdf, tem_cert)
            icone        = "✓" if tem_cert else "–"
            destino_nome = PASTA_COM_CERT if tem_cert else PASTA_SEM_CERT

            print(f"  {icone} {'COM certidão' if tem_cert else 'SEM certidão'}")
            print(f"    Processo:   {num_proc or 'não identificado'}")
            print(f"    Requerente: {requerente or 'não identificado'}")
            print(f"    Movido →    {destino_nome}/\n")

            if tem_cert:
                contagem_com += 1
            else:
                contagem_sem += 1

            relatorio.append({
                "arquivo": nome,
                "tem_certidao": tem_cert,
                "numero_processo": num_proc,
                "requerente": requerente,
                "destino": str(destino),
                "erro": None,
            })

        except json.JSONDecodeError as e:
            print(f"  ✗ Erro ao interpretar resposta JSON: {e}\n")
            contagem_erro += 1
            relatorio.append({
                "arquivo": nome,
                "tem_certidao": None,
                "numero_processo": None,
                "requerente": None,
                "destino": None,
                "erro": f"JSON inválido: {e}",
            })

        except Exception as e:
            print(f"  ✗ Erro: {e}\n")
            contagem_erro += 1
            relatorio.append({
                "arquivo": nome,
                "tem_certidao": None,
                "numero_processo": None,
                "requerente": None,
                "destino": None,
                "erro": str(e),
            })

        # Salva após cada arquivo — não perde progresso se interromper
        salvar_relatorio(relatorio)

        if i < len(pdfs):
            time.sleep(PAUSA_ENTRE_PDFS)

    # Resumo final
    print("\n" + "=" * 60)
    print("  RESUMO DA TRIAGEM")
    print("=" * 60)
    print(f"  Total de PDFs:          {len(todos_pdfs)}")
    print(f"  Com certidão negativa:  {contagem_com}  →  '{PASTA_COM_CERT}/'")
    print(f"  Sem certidão:           {contagem_sem}  →  '{PASTA_SEM_CERT}/'")
    print(f"  Erros:                  {contagem_erro}  (veja '{ARQUIVO_RELATORIO}')")
    print("=" * 60)
    print(f"\nPróximo passo: rode o Script 2 na pasta '{PASTA_COM_CERT}/'")


if __name__ == "__main__":
    main()
