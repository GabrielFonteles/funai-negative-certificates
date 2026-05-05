"""
=============================================================================
SCRIPT 2 — EXTRAÇÃO DE DADOS DAS CERTIDÕES NEGATIVAS (versão Anthropic Claude)
=============================================================================

O que este script faz:
  - Lê cada PDF da pasta 'com_certidao/' (gerada pelo Script 1)
  - Envia ao Claude para extrair todos os campos definidos
  - Salva os resultados em um arquivo CSV
  - Retry automático se a API retornar erro temporário
  - Pula arquivos já extraídos em execuções anteriores

Como instalar:
  pip3 install anthropic

Como rodar (depois do Script 1):
  python3 02_extrator_certidoes.py

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

PASTA_PDFS        = "com_certidao"
ARQUIVO_SAIDA     = "certidoes_negativas_funai.csv"
ARQUIVO_PROGRESSO = "progresso_extracao.json"

CHAVE_API = ""  # Cole aqui: "sk-ant-..." ou use variável ANTHROPIC_API_KEY

MODELO           = "claude-sonnet-4-5"
PAUSA_ENTRE_PDFS = 3
MAX_TENTATIVAS   = 3
PAUSA_RETRY      = 30


# =============================================================================
# PROMPT DE EXTRAÇÃO COMPLETA
# =============================================================================

PROMPT_EXTRACAO = """
Você é um especialista em análise de processos administrativos da FUNAI
(Fundação Nacional do Índio) relativos a Certidões Negativas de presença
ou aldeamento indígena, emitidas entre 1968 e meados dos anos 1980.

Analise o documento PDF fornecido e extraia as informações abaixo em
formato JSON. Se um campo não for encontrado, use null.

CAMPOS A EXTRAIR:

- numero_processo: número do processo (ex: "FUNAI/BSB/0532/86")
- empresa_requerente: nome da empresa, fazenda ou pessoa que fez o requerimento
- data_requerimento: data do requerimento inicial (formato DD/MM/AAAA)
- origem_funai: delegacia ou regional da FUNAI que recebeu o pedido
    (ex: "2ªDR/Belém", "Sede/BSB")
- tem_certidao: "Sim" se há Certidão Negativa emitida; "Não" caso contrário
- nome_responsavel: nome do responsável legal pela empresa ou propriedade
- numero_certidao: número da certidão negativa emitida (ex: "0013")
- data_certidao: data de emissão da certidão (formato DD/MM/AAAA)
- signatario: nome completo de quem assinou a certidão negativa
- cargo_signatario: cargo de quem assinou (ex: "Diretor da DPI", "Presidente da FUNAI")
- uf_empresa: sigla do estado onde está sediada a empresa ou o requerente (ex: "SP")
- uf_area: sigla do estado onde se localiza a área pleiteada
- municipio: município onde se localiza a área pleiteada
- area_ha: tamanho da área em hectares — apenas número (ex: 4882.1322)
- coordenadas: coordenadas geográficas encontradas no processo.
    Se houver tabela de vértices, indique quantos pontos e os dois primeiros.
    Se houver apenas extremos (N, S, L, W), liste-os.
    Ex: "31 vértices; P1: 0°04'30\"N 51°27'03\"W; P2: 0°04'12\"N 51°26'49\"W"
- tem_mapas: "Sim" se há mapas ou plantas; "Não" caso contrário
- total_mapas: número inteiro de mapas/plantas encontrados
- tem_deferimento: "Sim" se há documento interno de aprovação/deferimento; "Não" caso contrário
- quem_assina_deferimento: nome de quem assina o despacho de deferimento interno
- departamento: setor/departamento da FUNAI responsável (ex: "DPI", "DF", "DIDD")
- consultados: pessoas, departamentos ou órgãos consultados durante a instrução
    (separados por ponto e vírgula)
- povos_tis: povos indígenas ou terras indígenas mencionados no processo
    (separados por ponto e vírgula). Se nenhum, use null.
- observacoes: observações relevantes não capturadas nos outros campos
- referencia: deixe em branco — será preenchido automaticamente pelo script

IMPORTANTE:
- Responda APENAS com o JSON, sem nenhum texto antes ou depois
- Não use blocos de código markdown (sem ```)
- Use aspas duplas para strings
- Números decimais com ponto, não vírgula (ex: 4882.13)
"""


# =============================================================================
# DEFINIÇÃO DAS COLUNAS
# Cada tupla: (chave no JSON, nome da coluna no CSV)
# =============================================================================

COLUNAS = [
    ("numero_processo",         "Nº do Processo"),
    ("empresa_requerente",      "Empresa / Requerente"),
    ("data_requerimento",       "Data do Requerimento"),
    ("origem_funai",            "Origem (FUNAI)"),
    ("tem_certidao",            "Tem Certidão Negativa?"),
    ("nome_responsavel",        "Nome do Responsável"),
    ("numero_certidao",         "Nº da Certidão"),
    ("data_certidao",           "Data da Certidão"),
    ("signatario",              "Nome do Signatário"),
    ("cargo_signatario",        "Cargo do Signatário"),
    ("uf_empresa",              "UF Empresa"),
    ("uf_area",                 "UF da Área"),
    ("municipio",               "Município"),
    ("area_ha",                 "Tamanho da Área (ha)"),
    ("coordenadas",             "Coordenadas Geográficas"),
    ("tem_mapas",               "Tem Mapas?"),
    ("total_mapas",             "Total de Mapas"),
    ("tem_deferimento",         "Tem Doc. de Deferimento?"),
    ("quem_assina_deferimento", "Quem Assina o Deferimento"),
    ("departamento",            "Departamento"),
    ("consultados",             "Quem Foi Consultado?"),
    ("povos_tis",               "Povos ou TIs Mencionados"),
    ("observacoes",             "Observações"),
    ("referencia",              "Referência (arquivo)"),
]


# =============================================================================
# FUNÇÕES
# =============================================================================

def pdf_para_base64(caminho_pdf: str) -> str:
    """Converte um PDF em Base64 para enviar à API da Anthropic."""
    with open(caminho_pdf, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extrair_dados_do_pdf(cliente, caminho_pdf: str) -> dict:
    """
    Envia um PDF ao Claude e retorna os dados extraídos.
    Tenta até MAX_TENTATIVAS vezes em caso de erro temporário.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            print(f"  → Enviando para o Claude (tentativa {tentativa}/{MAX_TENTATIVAS})...")
            pdf_b64 = pdf_para_base64(caminho_pdf)

            resposta = cliente.messages.create(
                model=MODELO,
                max_tokens=2000,
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
                                "text": PROMPT_EXTRACAO,
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

            dados = json.loads(texto)
            dados["referencia"] = Path(caminho_pdf).name
            return dados

        except Exception as e:
            erro_str = str(e)
            if any(x in erro_str.lower() for x in ["rate", "overloaded", "529"]):
                if tentativa < MAX_TENTATIVAS:
                    print(f"  ⚠ API sobrecarregada. Aguardando {PAUSA_RETRY}s...")
                    time.sleep(PAUSA_RETRY)
                    continue
            raise

    raise Exception(f"Falhou após {MAX_TENTATIVAS} tentativas.")


def carregar_progresso() -> tuple:
    """
    Carrega resultados de uma execução anterior (se existir).
    Retorna a lista de resultados já extraídos e um set com os arquivos já feitos.
    """
    if not Path(ARQUIVO_PROGRESSO).exists():
        return [], set()

    with open(ARQUIVO_PROGRESSO, "r", encoding="utf-8") as f:
        resultados = json.load(f)

    ja_feitos = {r["referencia"] for r in resultados if r.get("referencia")}

    if ja_feitos:
        print(f"  ℹ {len(ja_feitos)} arquivo(s) já extraído(s) — serão pulados.")

    return resultados, ja_feitos


def salvar_progresso(resultados: list):
    """Salva o progresso em JSON após cada arquivo."""
    with open(ARQUIVO_PROGRESSO, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)


def salvar_csv(resultados: list, caminho_saida: str):
    """
    Salva todos os dados extraídos em um arquivo CSV.

    Usa encoding UTF-8 BOM para garantir que acentos e caracteres
    especiais apareçam corretamente ao abrir no Excel ou Numbers.
    """
    cabecalhos = [nome for _, nome in COLUNAS]

    with open(caminho_saida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cabecalhos)
        writer.writeheader()

        for registro in resultados:
            linha = {}
            for chave, nome_col in COLUNAS:
                valor = registro.get(chave)
                linha[nome_col] = "" if valor is None else valor
            writer.writerow(linha)

    print(f"\n✓ CSV salvo em: {caminho_saida}")


def listar_pdfs(pasta: str) -> list:
    """Lista todos os PDFs de uma pasta."""
    caminho = Path(pasta)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Pasta '{pasta}' não encontrada.\n"
            f"Execute o Script 1 primeiro para gerar esta pasta."
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
    print("  EXTRAÇÃO DE DADOS — CERTIDÕES NEGATIVAS FUNAI")
    print("  Script 2 de 2  (usando Anthropic Claude)")
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

    # Carrega progresso anterior
    print(f"\nVerificando progresso anterior...")
    resultados, ja_feitos = carregar_progresso()

    # Lista os PDFs e filtra os já processados
    print(f"\nBuscando PDFs em '{PASTA_PDFS}'...")
    todos_pdfs = listar_pdfs(PASTA_PDFS)
    pdfs = [p for p in todos_pdfs if p.name not in ja_feitos]
    print(f"  {len(todos_pdfs)} arquivo(s) encontrado(s) — {len(pdfs)} a processar.\n")

    if not pdfs:
        print("Todos os arquivos já foram extraídos! Gerando CSV...")
        salvar_csv(resultados, ARQUIVO_SAIDA)
        return

    erros = []

    for i, caminho_pdf in enumerate(pdfs, start=1):
        nome = caminho_pdf.name
        print(f"[{i}/{len(pdfs)}] Processando: {nome}")

        try:
            dados = extrair_dados_do_pdf(cliente, str(caminho_pdf))
            resultados.append(dados)
            print(f"  ✓ Concluído")
            print(f"    Processo:  {dados.get('numero_processo', '—')}")
            print(f"    Certidão:  {dados.get('numero_certidao', '—')}")
            print(f"    Município: {dados.get('municipio', '—')} / {dados.get('uf_area', '—')}\n")

        except json.JSONDecodeError as e:
            print(f"  ✗ Erro ao interpretar JSON: {e}\n")
            erros.append(nome)
            resultados.append({"referencia": nome, "observacoes": f"Erro JSON: {e}"})

        except Exception as e:
            print(f"  ✗ Erro: {e}\n")
            erros.append(nome)
            resultados.append({"referencia": nome, "observacoes": f"Erro: {e}"})

        # Salva progresso após cada arquivo
        salvar_progresso(resultados)

        if i < len(pdfs):
            time.sleep(PAUSA_ENTRE_PDFS)

    # Gera o CSV final
    print("Gerando CSV...")
    salvar_csv(resultados, ARQUIVO_SAIDA)

    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Total de PDFs:         {len(todos_pdfs)}")
    print(f"  Extraídos com êxito:   {len(resultados) - len(erros)}")
    print(f"  Erros:                 {len(erros)}")
    print(f"  Arquivo gerado:        {ARQUIVO_SAIDA}")
    print("=" * 60)


if __name__ == "__main__":
    main()