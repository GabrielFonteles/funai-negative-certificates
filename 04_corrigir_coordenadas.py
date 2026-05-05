"""
=============================================================================
SCRIPT 4 — CORREÇÃO MANUAL DE COORDENADAS E ADIÇÃO DE CAMPOS DE STATUS
=============================================================================

O que este script faz:
  - Lê o CSV v3
  - Adiciona dois novos campos a TODOS os registros:
      status_certidao        → deferida, indeferida, ou vazio
      observacao_coordenadas → explica a origem das coordenadas quando necessário
  - Corrige as coordenadas do processo DC00014A0119990SOS_parte1.pdf,
    substituindo as coordenadas erradas (de outra certidão juntada aos autos)
    pelas coordenadas corretas lidas manualmente do documento
  - Regenera o GeoJSON com as correções

Como rodar:
  python3 04_corrigir_coordenadas.py

=============================================================================
"""

import csv
import json
from pathlib import Path


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ARQUIVO_CSV_ENTRADA = "certidoes_negativas_funai_v3.csv"
ARQUIVO_CSV_SAIDA   = "certidoes_negativas_funai_v4.csv"
ARQUIVO_GEOJSON     = "certidoes_negativas_funai.geojson"

COLUNA_REFERENCIA           = "Referência (arquivo)"
COLUNA_PROCESSO             = "Nº do Processo"
COLUNA_EMPRESA              = "Empresa / Requerente"
COLUNA_MUNICIPIO            = "Município"
COLUNA_UF                   = "UF da Área"
COLUNA_AREA_HA              = "Tamanho da Área (ha)"
COLUNA_DATUM                = "Datum"
COLUNA_FORMATO              = "Coordenadas Formato"
COLUNA_COORDS_RAW           = "Coordenadas Raw"
COLUNA_VERTICES_JSON        = "Vértices JSON"
COLUNA_VERTICES_CONVERTIDOS = "Vértices Convertidos"
COLUNA_DATUM_ASSUMIDO       = "Datum Assumido"
COLUNA_STATUS               = "Status Certidão"
COLUNA_OBS_COORDS           = "Observação Coordenadas"


# =============================================================================
# COORDENADAS CORRIGIDAS
# Lidas manualmente do documento original DC00014A0119990SOS
# Coordenadas pertencem a certidão de terceiro juntada aos autos como precedente
# Área localizada em Mato Grosso, próxima à Terra Indígena Sareré
# =============================================================================

ARQUIVO_CORRIGIR = "DC00014A0119990SOS_parte1.pdf"

VERTICES_CORRIGIDOS = [
    {
        "id": "A",
        "lat_raw": "14°44'56\"S",
        "lon_raw": "59°58'42\"W",
        "lat_sad69": -14.7489,
        "lon_sad69": -59.9783,
        "lat_wgs84": -14.7489,
        "lon_wgs84": -59.9783
    },
    {
        "id": "B",
        "lat_raw": "14°42'52\"S",
        "lon_raw": "59°40'03\"W",
        "lat_sad69": -14.7144,
        "lon_sad69": -59.6675,
        "lat_wgs84": -14.7144,
        "lon_wgs84": -59.6675
    },
    {
        "id": "C",
        "lat_raw": "14°46'58\"S",
        "lon_raw": "59°36'59\"W",
        "lat_sad69": -14.7828,
        "lon_sad69": -59.6164,
        "lat_wgs84": -14.7828,
        "lon_wgs84": -59.6164
    },
    {
        "id": "D",
        "lat_raw": "14°46'58\"S",
        "lon_raw": "59°39'03\"W",
        "lat_sad69": -14.7828,
        "lon_sad69": -59.6508,
        "lat_wgs84": -14.7828,
        "lon_wgs84": -59.6508
    },
    {
        "id": "E",
        "lat_raw": "14°51'40\"S",
        "lon_raw": "59°36'03\"W",
        "lat_sad69": -14.8611,
        "lon_sad69": -59.6008,
        "lat_wgs84": -14.8611,
        "lon_wgs84": -59.6008
    },
    {
        "id": "F",
        "lat_raw": "15°01'23\"S",
        "lon_raw": "59°30'58\"W",
        "lat_sad69": -15.0231,
        "lon_sad69": -59.5161,
        "lat_wgs84": -15.0231,
        "lon_wgs84": -59.5161
    },
    {
        "id": "G",
        "lat_raw": "14°51'00\"S",
        "lon_raw": "59°58'00\"W",
        "lat_sad69": -14.8500,
        "lon_sad69": -59.9667,
        "lat_wgs84": -14.8500,
        "lon_wgs84": -59.9667
    }
]

STATUS_CORRIGIDO = "Indeferida"

OBS_COORDS_CORRIGIDO = (
    "Coordenadas extraídas de certidão negativa de terceiro juntada aos autos "
    "como precedente — referente a área não identificada em MT. "
    "O processo principal (DC00014A0119990SOS) teve a certidão indeferida "
    "por incidir sobre a Terra Indígena Sareré. "
    "Coordenadas corrigidas manualmente a partir da leitura do documento original."
)


# =============================================================================
# GEOJSON
# =============================================================================

def vertices_para_geometria(vertices: list) -> dict:
    """Converte lista de vértices em geometria GeoJSON."""
    validos = [
        v for v in vertices
        if v.get("lat_wgs84") is not None and v.get("lon_wgs84") is not None
    ]

    if not validos:
        return None

    pontos = [[v["lon_wgs84"], v["lat_wgs84"]] for v in validos]

    if len(pontos) >= 3:
        if pontos[0] != pontos[-1]:
            pontos.append(pontos[0])
        return {"type": "Polygon", "coordinates": [pontos]}
    elif len(pontos) >= 1:
        return {"type": "MultiPoint", "coordinates": pontos}

    return None


def criar_geojson(linhas: list) -> dict:
    """Cria o GeoJSON completo a partir das linhas do CSV."""
    features = []

    for linha in linhas:
        vertices_json = linha.get(COLUNA_VERTICES_CONVERTIDOS, "")
        try:
            vertices = json.loads(vertices_json) if vertices_json else []
        except json.JSONDecodeError:
            vertices = []

        geometria = vertices_para_geometria(vertices)

        properties = {
            "referencia":           linha.get(COLUNA_REFERENCIA, ""),
            "processo":             linha.get(COLUNA_PROCESSO, ""),
            "empresa":              linha.get(COLUNA_EMPRESA, ""),
            "municipio":            linha.get(COLUNA_MUNICIPIO, ""),
            "uf":                   linha.get(COLUNA_UF, ""),
            "area_ha":              linha.get(COLUNA_AREA_HA, ""),
            "datum_original":       linha.get(COLUNA_DATUM, ""),
            "datum_assumido":       linha.get(COLUNA_DATUM_ASSUMIDO, ""),
            "formato":              linha.get(COLUNA_FORMATO, ""),
            "coords_raw":           linha.get(COLUNA_COORDS_RAW, ""),
            "status_certidao":      linha.get(COLUNA_STATUS, ""),
            "obs_coordenadas":      linha.get(COLUNA_OBS_COORDS, ""),
            "tem_geometria":        geometria is not None,
        }

        features.append({
            "type": "Feature",
            "geometry": geometria,
            "properties": properties,
        })

    return {"type": "FeatureCollection", "features": features}


# =============================================================================
# FUNÇÕES DE LEITURA E ESCRITA
# =============================================================================

def carregar_csv(caminho: str) -> tuple:
    """Lê o CSV e retorna linhas e colunas."""
    with open(caminho, "r", encoding="utf-8-sig") as f:
        reader  = csv.DictReader(f)
        colunas = list(reader.fieldnames)
        linhas  = list(reader)
    return linhas, colunas


def salvar_csv(linhas: list, colunas: list, caminho: str):
    """Salva o CSV com as colunas atualizadas."""
    novas = [COLUNA_STATUS, COLUNA_OBS_COORDS]
    todas = list(colunas)
    for col in novas:
        if col not in todas:
            todas.append(col)

    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=todas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)

    print(f"✓ CSV v4 salvo em: {caminho}")


def salvar_geojson(geojson: dict, caminho: str):
    """Salva o GeoJSON."""
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"✓ GeoJSON atualizado salvo em: {caminho}")


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  CORREÇÃO DE COORDENADAS — Script 4")
    print("=" * 60)

    # Carrega o CSV v3
    print(f"\nLendo: {ARQUIVO_CSV_ENTRADA}...")
    if not Path(ARQUIVO_CSV_ENTRADA).exists():
        raise FileNotFoundError(
            f"Arquivo '{ARQUIVO_CSV_ENTRADA}' não encontrado.\n"
            f"Execute o Script 3 primeiro."
        )
    linhas, colunas = carregar_csv(ARQUIVO_CSV_ENTRADA)
    print(f"  {len(linhas)} linha(s) encontrada(s).\n")

    # Inicializa os novos campos em branco para todos os registros
    for linha in linhas:
        if COLUNA_STATUS not in linha:
            linha[COLUNA_STATUS] = ""
        if COLUNA_OBS_COORDS not in linha:
            linha[COLUNA_OBS_COORDS] = ""

    # Aplica a correção no processo específico
    corrigido = False
    for linha in linhas:
        if linha[COLUNA_REFERENCIA] == ARQUIVO_CORRIGIR:
            print(f"Corrigindo: {ARQUIVO_CORRIGIR}")
            linha[COLUNA_VERTICES_CONVERTIDOS] = json.dumps(
                VERTICES_CORRIGIDOS, ensure_ascii=False
            )
            linha[COLUNA_STATUS]     = STATUS_CORRIGIDO
            linha[COLUNA_OBS_COORDS] = OBS_COORDS_CORRIGIDO
            corrigido = True
            print(f"  ✓ Coordenadas substituídas — 7 vértices em MT")
            print(f"  ✓ Status: {STATUS_CORRIGIDO}")
            print(f"  ✓ Observação registrada\n")
            break

    if not corrigido:
        print(f"  ⚠ Arquivo '{ARQUIVO_CORRIGIR}' não encontrado no CSV.")
        print(f"    Verifique o nome exato na coluna '{COLUNA_REFERENCIA}'.\n")

    # Salva o CSV v4
    print("Salvando CSV v4...")
    salvar_csv(linhas, colunas, ARQUIVO_CSV_SAIDA)

    # Regenera o GeoJSON
    print("Regenerando GeoJSON...")
    geojson = criar_geojson(linhas)
    salvar_geojson(geojson, ARQUIVO_GEOJSON)

    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Total de registros:     {len(linhas)}")
    print(f"  Processo corrigido:     {ARQUIVO_CORRIGIR}")
    print(f"  Novos campos adicionados:")
    print(f"    - '{COLUNA_STATUS}'")
    print(f"    - '{COLUNA_OBS_COORDS}'")
    print(f"  Arquivos gerados:")
    print(f"    {ARQUIVO_CSV_SAIDA}")
    print(f"    {ARQUIVO_GEOJSON}")
    print("=" * 60)
    print(f"\nNo QGIS: remova a camada atual e arraste o novo")
    print(f"'{ARQUIVO_GEOJSON}' para atualizar o mapa.")


if __name__ == "__main__":
    main()