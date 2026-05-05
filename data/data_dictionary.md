# Data Dictionary

This repository contains two datasets. The raw certificate data cannot be shared publicly due to a usage agreement with FUNAI restricting it to academic research. A data dictionary is provided below to allow other researchers to understand the dataset structure and replicate the study by submitting a similar request to FUNAI.

---

## Dataset 1: FUNAI Negative Certificates (`certidoes_negativas`)

**Source:** FUNAI (Fundação Nacional dos Povos Indígenas), obtained via direct email request  
**Coverage:** 1968–1990  
**Records:** 78 certificates  
**Availability:** Restricted. Raw data cannot be shared publicly (personal data, usage agreement).  
A synthetic sample with 5 fictitious rows is available at `data/certidoes_sample_synthetic.csv`.

| Column | Type | Description |
|--------|------|-------------|
| Nº do Processo | string | Internal FUNAI process number |
| Empresa / Requerente | string | Name of the company or individual requesting the certificate |
| Data do Requerimento | string | Date the request was submitted (DD/MM/YYYY) |
| Origem (FUNAI) | string | FUNAI regional office or department that processed the request |
| Tem Certidão Negativa? | string | Whether a negative certificate was issued (Sim/Não) |
| Nome do Responsável | string | Name of the FUNAI official responsible for the process |
| Nº da Certidão | string | Certificate identification number |
| Data da Certidão | string | Date the certificate was issued (DD/MM/YYYY) |
| Nome do Signatário | string | Name of the FUNAI official who signed the certificate |
| Cargo do Signatário | string | Title or position of the signatory |
| UF Empresa | string | Brazilian state where the requesting company or individual was registered |
| UF da Área | string | Brazilian state where the certified area is located |
| Município | string | Municipality where the certified area is located |
| Tamanho da Área (ha) | float | Size of the certified area in hectares |
| Coordenadas Geográficas | string | Geographic coordinates as found in the original document |
| Tem Mapas? | string | Whether the original document includes maps (Sim/Não) |
| Total de Mapas | integer | Number of maps included in the original document |
| Tem Doc. de Deferimento? | string | Whether an approval document is present (Sim/Não) |
| Quem Assina o Deferimento | string | Name of the official who signed the approval document |
| Departamento | string | FUNAI department(s) consulted before issuing the certificate |
| Quem Foi Consultado? | string | Individuals or departments consulted during the process |
| Povos ou TIs Mencionados | string | Indigenous peoples or territories mentioned in the document (pipe-separated list) |
| Observações | string | Researcher notes and annotations |
| Referência (arquivo) | string | File reference in the FUNAI archive |
| Coordenadas Formato | string | Format of the geographic coordinates (e.g., UTM, geographic) |
| Coordenadas Sistema | string | Coordinate system used (e.g., SAD69, WGS84) |
| Datum | string | Geodetic datum as specified in the original document |
| Total Vértices | float | Number of vertices defining the area boundary |
| Coordenadas Raw | string | Raw coordinate string as extracted from the document |
| Vértices JSON | string | Area boundary vertices in JSON format |
| Datum Assumido | string | Datum assumed by the researcher when not specified in the document |
| Vértices Convertidos | string | Vertices converted to WGS84 for GIS analysis |
| Status Certidão | string | Processing status of the certificate in this dataset |
| Observação Coordenadas | string | Researcher notes on coordinate extraction and conversion |

---

## Dataset 2: Press Reports (`reportagens_certidoes_negativas.csv`)

**Source:** Public sources, primarily the Hemeroteca Indígena digital archive  
**Coverage:** 1972–2009  
**Records:** 105 press reports  
**Availability:** Public. Full dataset available in this repository.

| Column | Type | Description |
|--------|------|-------------|
| Carimbo de data/hora | string | Timestamp of data entry |
| Nome do Jornal ou Revista | string | Name of the newspaper or magazine |
| Estado da federação da publicação | string | Brazilian state where the publication is based |
| Título do texto | string | Title of the article or report |
| Data da publicação | string | Publication date (DD/MM/YYYY) |
| Nome do autor do texto | string | Author of the article |
| Povo ou terra indígena mencionado | string | Indigenous people or territory mentioned in the report |
| Nomes de empresas, fazendas ou indivíduos mencionados | string | Names of companies, farms or individuals mentioned |
| Entrevista algum indígena? | string | Whether any indigenous person was interviewed (Sim/Não) |
| Qual o nome do indígena entrevistado? | string | Name of the indigenous person interviewed, if any |
| Há não-indígena entrevistado? | string | Whether any non-indigenous person was interviewed (Sim/Não) |
| Nome do não-indígena entrevistado | string | Name of the non-indigenous person interviewed, if any |
| Cargo ou profissão do não-indígena entrevistado | string | Title or profession of the non-indigenous interviewee |
| Se houver, evento mencionado (violência, crimes, etc) | string | Type of event reported, if any (violence, land conflict, crime, etc.) |
| Link da notícia | string | URL to the original article |

---

## Methodological Note on Data Access

The certificate dataset was obtained by submitting a direct email request to FUNAI. Researchers interested in replicating this study may contact FUNAI directly at [www.funai.gov.br](https://www.funai.gov.br) or submit a formal request via the Lei de Acesso à Informação (LAI) at [www.gov.br/acessoainformacao](https://www.gov.br/acessoainformacao).

Note that the 78 certificates analyzed here represent a partial corpus — FUNAI estimates approximately 1,400 negative certificates were issued during this period. The selective nature of institutional archive access is itself analytically relevant to this research.
