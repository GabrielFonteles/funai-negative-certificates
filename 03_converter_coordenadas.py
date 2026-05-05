"""
=============================================================================
SCRIPT 3 — CONVERSÃO DE COORDENADAS E EXPORTAÇÃO GEOJSON
=============================================================================

O que este script faz:
  - Lê o CSV v2 gerado pelo Script 2b
  - Converte as coordenadas de SAD69 para WGS84 (localmente, sem API)
  - Adiciona a coluna "Vértices Convertidos" ao CSV — gerando o CSV v3
  - Exporta um arquivo .geojson pronto para abrir no QGIS

Convenção de datum adotada:
  - SAD69 explícito     → converte para WGS84
  - WGr (notação)       → trata como SAD69, converte para WGS84
  - Sem datum           → assume SAD69, converte para WGS84
  - Incerteza registrada na coluna "Datum Assumido"

Como instalar:
  pip3 install pyproj

Como rodar (depois do Script 2b):
  python3 03_converter_coordenadas.py

=============================================================================
"""

import csv
import json
from pathlib import Path
from pyproj import Transformer


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

ARQUIVO_CSV_ENTRADA = "certidoes_negativas_funai_v2.csv"
ARQUIVO_CSV_SAIDA   = "certidoes_negativas_funai_v3.csv"
ARQUIVO_GEOJSON     = "certidoes_negativas_funai.geojson"

# Colunas relevantes
COLUNA_REFERENCIA   = "Referência (arquivo)"
COLUNA_PROCESSO     = "Nº do Processo"
COLUNA_EMPRESA      = "Empresa / Requerente"
COLUNA_MUNICIPIO    = "Município"
COLUNA_UF           = "UF da Área"
COLUNA_AREA_HA      = "Tamanho da Área (ha)"
COLUNA_DATUM        = "Datum"
COLUNA_FORMATO      = "Coordenadas Formato"
COLUNA_VERTICES     = "Vértices JSON"
COLUNA_COORDS_RAW   = "Coordenadas Raw"
COLUNA_CONVERTIDOS  = "Vértices Convertidos"
COLUNA_DATUM_ASSUMIDO = "Datum Assumido"


# =============================================================================
# CONVERSÃO DE DATUM
# =============================================================================

# Cria os transformadores de projeção
# SAD69 → WGS84
transformador_sad69 = Transformer.from_crs(
    "EPSG:4618",   # SAD69 geográfico
    "EPSG:4326",   # WGS84
    always_xy=True # sempre (longitude, latitude) — evita confusão de ordem
)

# SIRGAS2000 → WGS84 (praticamente idêntico, mas para ser preciso)
transformador_sirgas = Transformer.from_crs(
    "EPSG:4674",   # SIRGAS2000
    "EPSG:4326",   # WGS84
    always_xy=True
)


def determinar_datum(datum_raw: str) -> tuple:
    """
    Determina qual datum usar com base no campo Datum do CSV.

    Retorna:
        (transformador, datum_assumido, certeza)
        certeza: "explícito" ou "assumido"
    """
    if not datum_raw or datum_raw.strip() == "" or datum_raw.lower() == "null":
        # Sem datum especificado — assume SAD69 (padrão brasileiro da época)
        return transformador_sad69, "SAD69 (assumido — não especificado no documento)", "assumido"

    datum_upper = datum_raw.upper().strip()

    if "SAD69" in datum_upper or "SAD 69" in datum_upper:
        return transformador_sad69, "SAD69", "explícito"

    if "WGR" in datum_upper or "WG" in datum_upper:
        # WGr é notação de "West Greenwich", não um datum — trata como SAD69
        return transformador_sad69, "SAD69 (assumido — documento usa notação WGr)", "assumido"

    if "SIRGAS" in datum_upper:
        return transformador_sirgas, "SIRGAS2000", "explícito"

    if "WGS" in datum_upper or "WGS84" in datum_upper:
        # Já está em WGS84 — não precisa converter
        return None, "WGS84 (já no sistema de destino)", "explícito"

    if "CORREGO" in datum_upper or "CÓRREGO" in datum_upper or "ALEGRE" in datum_upper:
        # Córrego Alegre — diferença pequena do SAD69, usamos SAD69 como aproximação
        return transformador_sad69, "SAD69 (aproximação — documento usa Córrego Alegre)", "assumido"

    # Datum desconhecido — assume SAD69
    return transformador_sad69, f"SAD69 (assumido — datum '{datum_raw}' não reconhecido)", "assumido"


def converter_vertice(lon: float, lat: float, transformador) -> tuple:
    """
    Converte um par lon/lat de SAD69 para WGS84.

    Retorna (lon_wgs84, lat_wgs84) ou (None, None) se falhar.
    """
    if transformador is None:
        # Já está em WGS84
        return lon, lat
    try:
        lon_wgs, lat_wgs = transformador.transform(lon, lat)
        return round(lon_wgs, 8), round(lat_wgs, 8)
    except Exception:
        return None, None


def converter_vertices(vertices_json: str, datum_raw: str) -> tuple:
    """
    Converte todos os vértices de um processo para WGS84.

    Retorna:
        (vertices_convertidos, datum_assumido)
        vertices_convertidos: lista de dicts com coordenadas WGS84
        datum_assumido: string descrevendo o datum usado
    """
    if not vertices_json or vertices_json.strip() in ("", "null", "[]"):
        return [], "sem coordenadas"

    try:
        vertices = json.loads(vertices_json)
    except json.JSONDecodeError:
        return [], "erro ao ler JSON"

    if not vertices:
        return [], "lista vazia"

    transformador, datum_assumido, _ = determinar_datum(datum_raw)

    vertices_convertidos = []
    for v in vertices:
        lat_dec = v.get("lat_decimal")
        lon_dec = v.get("lon_decimal")

        # Só converte se tiver valores decimais válidos
        if lat_dec is not None and lon_dec is not None:
            try:
                lat_f = float(lat_dec)
                lon_f = float(lon_dec)
                lon_wgs, lat_wgs = converter_vertice(lon_f, lat_f, transformador)
                vertices_convertidos.append({
                    "id":        v.get("id"),
                    "lat_raw":   v.get("lat_raw"),
                    "lon_raw":   v.get("lon_raw"),
                    "lat_sad69": lat_f,
                    "lon_sad69": lon_f,
                    "lat_wgs84": lat_wgs,
                    "lon_wgs84": lon_wgs,
                })
            except (TypeError, ValueError):
                vertices_convertidos.append({
                    "id":        v.get("id"),
                    "lat_raw":   v.get("lat_raw"),
                    "lon_raw":   v.get("lon_raw"),
                    "lat_sad69": None,
                    "lon_sad69": None,
                    "lat_wgs84": None,
                    "lon_wgs84": None,
                })
        else:
            # Sem decimal — mantém o registro mas sem conversão
            vertices_convertidos.append({
                "id":        v.get("id"),
                "lat_raw":   v.get("lat_raw"),
                "lon_raw":   v.get("lon_raw"),
                "lat_sad69": None,
                "lon_sad69": None,
                "lat_wgs84": None,
                "lon_wgs84": None,
            })

    return vertices_convertidos, datum_assumido


# =============================================================================
# GEOJSON
# =============================================================================

def vertices_para_geometria(vertices_convertidos: list, formato: str) -> dict:
    """
    Converte a lista de vértices em uma geometria GeoJSON.

    Se houver 3+ vértices com coordenadas válidas → Polygon
    Se houver 1-2 vértices válidos → MultiPoint (extremos)
    Se não houver vértices válidos → None
    """
    # Filtra apenas os vértices com coordenadas WGS84 válidas
    validos = [
        v for v in vertices_convertidos
        if v.get("lat_wgs84") is not None and v.get("lon_wgs84") is not None
    ]

    if not validos:
        return None

    # GeoJSON usa [longitude, latitude]
    pontos = [[v["lon_wgs84"], v["lat_wgs84"]] for v in validos]

    if len(pontos) >= 3:
        # Fecha o polígono repetindo o primeiro ponto no final
        if pontos[0] != pontos[-1]:
            pontos.append(pontos[0])
        return {
            "type": "Polygon",
            "coordinates": [pontos]
        }
    elif len(pontos) >= 1:
        return {
            "type": "MultiPoint",
            "coordinates": pontos
        }

    return None


def criar_geojson(linhas: list) -> dict:
    """
    Cria o dicionário GeoJSON completo com todas as certidões.
    Cada certidão é uma Feature com seus atributos como properties.
    """
    features = []

    for linha in linhas:
        vertices_json = linha.get(COLUNA_CONVERTIDOS, "")
        formato       = linha.get(COLUNA_FORMATO, "")

        # Tenta carregar os vértices convertidos
        try:
            vertices = json.loads(vertices_json) if vertices_json else []
        except json.JSONDecodeError:
            vertices = []

        geometria = vertices_para_geometria(vertices, formato)

        # Propriedades da feature — tudo que vai aparecer no QGIS ao clicar
        properties = {
            "referencia":      linha.get(COLUNA_REFERENCIA, ""),
            "processo":        linha.get(COLUNA_PROCESSO, ""),
            "empresa":         linha.get(COLUNA_EMPRESA, ""),
            "municipio":       linha.get(COLUNA_MUNICIPIO, ""),
            "uf":              linha.get(COLUNA_UF, ""),
            "area_ha":         linha.get(COLUNA_AREA_HA, ""),
            "datum_original":  linha.get(COLUNA_DATUM, ""),
            "datum_assumido":  linha.get(COLUNA_DATUM_ASSUMIDO, ""),
            "formato":         formato,
            "coords_raw":      linha.get(COLUNA_COORDS_RAW, ""),
            "tem_geometria":   geometria is not None,
        }

        feature = {
            "type": "Feature",
            "geometry": geometria,
            "properties": properties,
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


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
    """Salva o CSV v3 com as novas colunas de coordenadas convertidas."""
    novas = [COLUNA_DATUM_ASSUMIDO, COLUNA_CONVERTIDOS]
    todas = list(colunas)
    for col in novas:
        if col not in todas:
            todas.append(col)

    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=todas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)

    print(f"✓ CSV v3 salvo em: {caminho}")


def salvar_geojson(geojson: dict, caminho: str):
    """Salva o arquivo GeoJSON."""
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"✓ GeoJSON salvo em: {caminho}")


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  CONVERSÃO DE COORDENADAS — Script 3")
    print("  (100% local, sem API, sem tokens)")
    print("=" * 60)

    # Carrega o CSV v2
    print(f"\nLendo: {ARQUIVO_CSV_ENTRADA}...")
    if not Path(ARQUIVO_CSV_ENTRADA).exists():
        raise FileNotFoundError(
            f"Arquivo '{ARQUIVO_CSV_ENTRADA}' não encontrado.\n"
            f"Execute o Script 2b primeiro."
        )
    linhas, colunas = carregar_csv(ARQUIVO_CSV_ENTRADA)
    print(f"  {len(linhas)} linha(s) encontrada(s).\n")

    # Contadores
    com_poligono   = 0
    com_pontos     = 0
    sem_geometria  = 0
    assumidos      = 0

    print("Convertendo coordenadas...\n")

    for i, linha in enumerate(linhas, start=1):
        referencia = linha.get(COLUNA_REFERENCIA, f"linha {i}")
        datum_raw  = linha.get(COLUNA_DATUM, "")
        vertices_json = linha.get(COLUNA_VERTICES, "")

        # Converte os vértices
        vertices_convertidos, datum_assumido = converter_vertices(
            vertices_json, datum_raw
        )

        # Registra se o datum foi assumido
        if "assumido" in datum_assumido.lower():
            assumidos += 1

        # Determina o tipo de geometria resultante
        validos = [
            v for v in vertices_convertidos
            if v.get("lat_wgs84") is not None
        ]
        if len(validos) >= 3:
            com_poligono += 1
            tipo = "polígono"
        elif len(validos) >= 1:
            com_pontos += 1
            tipo = "pontos"
        else:
            sem_geometria += 1
            tipo = "sem geometria"

        # Atualiza a linha
        linha[COLUNA_CONVERTIDOS]   = json.dumps(vertices_convertidos, ensure_ascii=False)
        linha[COLUNA_DATUM_ASSUMIDO] = datum_assumido

        print(f"  [{i:02d}/{len(linhas)}] {referencia[:45]:<45} → {tipo}")

    # Salva o CSV v3
    print(f"\nSalvando CSV v3...")
    salvar_csv(linhas, colunas, ARQUIVO_CSV_SAIDA)

    # Gera e salva o GeoJSON
    print(f"Gerando GeoJSON...")
    geojson = criar_geojson(linhas)
    salvar_geojson(geojson, ARQUIVO_GEOJSON)

    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Total de certidões:        {len(linhas)}")
    print(f"  Com polígono completo:     {com_poligono}")
    print(f"  Com pontos (extremos):     {com_pontos}")
    print(f"  Sem geometria:             {sem_geometria}")
    print(f"  Datum assumido (SAD69):    {assumidos}")
    print("=" * 60)
    print(f"\n  Arquivos gerados:")
    print(f"    {ARQUIVO_CSV_SAIDA}")
    print(f"    {ARQUIVO_GEOJSON}")
    print(f"\nPróximo passo: abra o QGIS e importe '{ARQUIVO_GEOJSON}'")


if __name__ == "__main__":
    main()