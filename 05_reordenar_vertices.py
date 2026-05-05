"""
=============================================================================
SCRIPT 5 — REORDENAÇÃO DE VÉRTICES E CORREÇÃO DE POLÍGONOS
=============================================================================

O que este script faz:
  - Lê o CSV v4
  - Para cada polígono, reordena os vértices no sentido horário
    usando o algoritmo de convex hull
  - Corrige o efeito "gravata borboleta" causado por vértices fora de ordem
  - Regenera o GeoJSON com os polígonos corrigidos
  - Salva o CSV v5 com os vértices reordenados

Por que convex hull?
  O convex hull calcula o envoltório convexo dos pontos — ou seja,
  a menor forma convexa que contém todos os vértices. Para áreas rurais
  com 4 a 8 vértices, isso produz o polígono correto na grande maioria
  dos casos, sem precisar de API ou intervenção manual.

Como rodar (sem dependências extras — usa apenas bibliotecas padrão):
  python3 05_reordenar_vertices.py

=============================================================================
"""

import csv
import json
import math
from pathlib import Path


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ARQUIVO_CSV_ENTRADA = "certidoes_negativas_funai_v4.csv"
ARQUIVO_CSV_SAIDA   = "certidoes_negativas_funai_v5.csv"
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
COLUNA_VERTICES_CONVERTIDOS = "Vértices Convertidos"
COLUNA_DATUM_ASSUMIDO       = "Datum Assumido"
COLUNA_STATUS               = "Status Certidão"
COLUNA_OBS_COORDS           = "Observação Coordenadas"


# =============================================================================
# ALGORITMO DE REORDENAÇÃO
# =============================================================================

def calcular_centroide(pontos: list) -> tuple:
    """
    Calcula o centróide (ponto central) de uma lista de pontos.
    O centróide é a média das coordenadas — o "centro de gravidade" do polígono.
    """
    lon_media = sum(p[0] for p in pontos) / len(pontos)
    lat_media = sum(p[1] for p in pontos) / len(pontos)
    return lon_media, lat_media


def angulo_em_relacao_ao_centro(ponto: tuple, centro: tuple) -> float:
    """
    Calcula o ângulo de um ponto em relação ao centro do polígono.
    Usado para ordenar os vértices no sentido horário.

    math.atan2 retorna o ângulo em radianos entre -π e π.
    Negamos o resultado para inverter de anti-horário para horário.
    """
    dx = ponto[0] - centro[0]
    dy = ponto[1] - centro[1]
    return -math.atan2(dy, dx)  # negativo = sentido horário


def reordenar_horario(vertices: list) -> list:
    """
    Reordena uma lista de vértices no sentido horário.

    Algoritmo:
    1. Calcula o centróide dos pontos
    2. Calcula o ângulo de cada ponto em relação ao centróide
    3. Ordena os pontos por ângulo (sentido horário)

    Isso corrige o efeito "gravata borboleta" sem precisar
    conhecer a ordem original dos vértices.
    """
    # Extrai apenas os pontos com coordenadas WGS84 válidas
    validos = [
        v for v in vertices
        if v.get("lon_wgs84") is not None and v.get("lat_wgs84") is not None
    ]

    if len(validos) < 3:
        return vertices  # Não é possível formar polígono — retorna como está

    # Monta lista de (lon, lat) para o cálculo
    pontos = [(v["lon_wgs84"], v["lat_wgs84"]) for v in validos]

    # Calcula o centróide
    centro = calcular_centroide(pontos)

    # Ordena os vértices por ângulo em relação ao centróide
    validos_ordenados = sorted(
        validos,
        key=lambda v: angulo_em_relacao_ao_centro(
            (v["lon_wgs84"], v["lat_wgs84"]), centro
        )
    )

    return validos_ordenados


def verificar_cruzamento(vertices: list) -> bool:
    """
    Verifica se um polígono tem lados que se cruzam (gravata borboleta).
    Retorna True se houver cruzamento, False se o polígono for válido.

    Usa o algoritmo de interseção de segmentos de linha.
    """
    def segmentos_cruzam(p1, p2, p3, p4):
        """Verifica se o segmento p1-p2 cruza com p3-p4."""
        def produto_vetorial(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        d1 = produto_vetorial(p3, p4, p1)
        d2 = produto_vetorial(p3, p4, p2)
        d3 = produto_vetorial(p1, p2, p3)
        d4 = produto_vetorial(p1, p2, p4)

        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True
        return False

    validos = [
        (v["lon_wgs84"], v["lat_wgs84"]) for v in vertices
        if v.get("lon_wgs84") is not None and v.get("lat_wgs84") is not None
    ]

    n = len(validos)
    if n < 4:
        return False

    # Verifica cada par de segmentos não adjacentes
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # Segmentos adjacentes — pula
            p1 = validos[i]
            p2 = validos[(i + 1) % n]
            p3 = validos[j]
            p4 = validos[(j + 1) % n]
            if segmentos_cruzam(p1, p2, p3, p4):
                return True
    return False


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
    """Cria o GeoJSON completo."""
    features = []

    for linha in linhas:
        vertices_json = linha.get(COLUNA_VERTICES_CONVERTIDOS, "")
        try:
            vertices = json.loads(vertices_json) if vertices_json else []
        except json.JSONDecodeError:
            vertices = []

        geometria = vertices_para_geometria(vertices)

        properties = {
            "referencia":      linha.get(COLUNA_REFERENCIA, ""),
            "processo":        linha.get(COLUNA_PROCESSO, ""),
            "empresa":         linha.get(COLUNA_EMPRESA, ""),
            "municipio":       linha.get(COLUNA_MUNICIPIO, ""),
            "uf":              linha.get(COLUNA_UF, ""),
            "area_ha":         linha.get(COLUNA_AREA_HA, ""),
            "datum_original":  linha.get(COLUNA_DATUM, ""),
            "datum_assumido":  linha.get(COLUNA_DATUM_ASSUMIDO, ""),
            "formato":         linha.get(COLUNA_FORMATO, ""),
            "coords_raw":      linha.get(COLUNA_COORDS_RAW, ""),
            "status_certidao": linha.get(COLUNA_STATUS, ""),
            "obs_coordenadas": linha.get(COLUNA_OBS_COORDS, ""),
            "tem_geometria":   geometria is not None,
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
    """Salva o CSV."""
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)
    print(f"✓ CSV v5 salvo em: {caminho}")


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
    print("  REORDENAÇÃO DE VÉRTICES — Script 5")
    print("  (100% local, sem API, sem tokens)")
    print("=" * 60)

    # Carrega o CSV v4
    print(f"\nLendo: {ARQUIVO_CSV_ENTRADA}...")
    if not Path(ARQUIVO_CSV_ENTRADA).exists():
        raise FileNotFoundError(
            f"Arquivo '{ARQUIVO_CSV_ENTRADA}' não encontrado.\n"
            f"Execute o Script 4 primeiro."
        )
    linhas, colunas = carregar_csv(ARQUIVO_CSV_ENTRADA)
    print(f"  {len(linhas)} linha(s) encontrada(s).\n")

    # Contadores
    corrigidos    = 0
    ja_corretos   = 0
    sem_geometria = 0

    print("Verificando e corrigindo polígonos...\n")

    for i, linha in enumerate(linhas, start=1):
        referencia    = linha.get(COLUNA_REFERENCIA, f"linha {i}")
        vertices_json = linha.get(COLUNA_VERTICES_CONVERTIDOS, "")

        try:
            vertices = json.loads(vertices_json) if vertices_json else []
        except json.JSONDecodeError:
            vertices = []

        validos = [
            v for v in vertices
            if v.get("lon_wgs84") is not None and v.get("lat_wgs84") is not None
        ]

        if len(validos) < 3:
            sem_geometria += 1
            print(f"  [{i:02d}] {referencia[:50]:<50} → sem geometria suficiente")
            continue

        # Verifica se há cruzamento (gravata borboleta)
        tem_cruzamento = verificar_cruzamento(vertices)

        if tem_cruzamento:
            # Reordena no sentido horário
            vertices_corrigidos = reordenar_horario(vertices)
            linha[COLUNA_VERTICES_CONVERTIDOS] = json.dumps(
                vertices_corrigidos, ensure_ascii=False
            )
            corrigidos += 1
            print(f"  [{i:02d}] {referencia[:50]:<50} → ✓ corrigido")
        else:
            ja_corretos += 1
            print(f"  [{i:02d}] {referencia[:50]:<50} → ok")

    # Salva CSV v5
    print(f"\nSalvando CSV v5...")
    salvar_csv(linhas, colunas, ARQUIVO_CSV_SAIDA)

    # Regenera GeoJSON
    print(f"Regenerando GeoJSON...")
    geojson = criar_geojson(linhas)
    salvar_geojson(geojson, ARQUIVO_GEOJSON)

    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Total de certidões:        {len(linhas)}")
    print(f"  Polígonos corrigidos:      {corrigidos}")
    print(f"  Polígonos já corretos:     {ja_corretos}")
    print(f"  Sem geometria suficiente:  {sem_geometria}")
    print(f"  Arquivos gerados:")
    print(f"    {ARQUIVO_CSV_SAIDA}")
    print(f"    {ARQUIVO_GEOJSON}")
    print("=" * 60)
    print(f"\nNo QGIS: remova a camada atual e arraste o novo")
    print(f"'{ARQUIVO_GEOJSON}' para atualizar o mapa.")


if __name__ == "__main__":
    main()