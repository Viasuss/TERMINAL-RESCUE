#!/usr/bin/env python3
"""Script de cierre mensual de afiliados (Terminal Rescue).

Procesa los archivos en data/ y logs/ para generar los entregables en output/:
- output/afiliados_activos.csv
- output/excepciones.csv
- output/totales.txt
- output/top_error.txt
"""

import csv
import glob
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def parse_fec(raw):
    """Normaliza o valida fechas FEC_AFI. Formatos válidos: YYYY-MM-DD, DD/MM/YYYY, YYYYMMDD."""
    raw = (raw or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        try:
            d = datetime.strptime(raw, "%Y-%m-%d")
            return d.strftime("%Y-%m-%d")
        except ValueError:
            return None
    elif re.match(r"^\d{2}/\d{2}/\d{4}$", raw):
        try:
            d = datetime.strptime(raw, "%d/%m/%Y")
            return d.strftime("%Y-%m-%d")
        except ValueError:
            return None
    elif re.match(r"^\d{8}$", raw):
        try:
            d = datetime.strptime(raw, "%Y%m%d")
            return d.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Cargar Maestros
    empresa_path = os.path.join(DATA_DIR, "EMPRESA.csv")
    empresas = {}
    with open(empresa_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            empresas[row["COD_EMP"].strip()] = row["NOM_EMP"].strip()

    afi_mae_path = os.path.join(DATA_DIR, "AFI_MAE.csv")
    with open(afi_mae_path, encoding="utf-8") as f:
        afi_mae_rows = list(csv.DictReader(f))

    afi_ben_path = os.path.join(DATA_DIR, "AFI_BEN.csv")
    with open(afi_ben_path, encoding="utf-8") as f:
        afi_ben_rows = list(csv.DictReader(f))

    aportes_path = os.path.join(DATA_DIR, "APORTES.csv")
    with open(aportes_path, encoding="utf-8") as f:
        aportes_rows = list(csv.DictReader(f))

    extracto_path = os.path.join(DATA_DIR, "extracto_caja_oriente.csv")
    with open(extracto_path, encoding="utf-8") as f:
        extracto_rows = list(csv.DictReader(f, delimiter=";"))

    # Estructuras para excepciones
    excepciones = []  # Lista de tuplas: (documento, tipo, detalle)

    # 2. Regla 1: Universo y DUPLICADO
    seen_docs = set()
    unique_afi = []
    for r in afi_mae_rows:
        doc = r["NRO_DOC"].strip()
        if doc in seen_docs:
            excepciones.append((doc, "DUPLICADO", f"Documento {doc} duplicado en AFI_MAE"))
        else:
            seen_docs.add(doc)
            unique_afi.append(r)

    total_afiliados = len(unique_afi)

    # 3. Reglas de Validación sobre Afiliados Únicos
    # Regla 2: Estado y CODIGO_INVALIDO
    # Regla 3: Empresa y SIN_EMPRESA
    # Regla 5: Fechas y FECHA_INVALIDA
    activos_validos = []
    inactivos_count = 0

    for r in unique_afi:
        doc = r["NRO_DOC"].strip()
        est = r["EST_AFI"].strip()
        cod_emp = r["COD_EMP"].strip()
        fec_raw = r["FEC_AFI"].strip()

        # Validación de fecha
        fec_norm = parse_fec(fec_raw)
        if fec_norm is None:
            excepciones.append((doc, "FECHA_INVALIDA", f"Fecha inválida '{fec_raw}' para documento {doc}"))

        # Validación de estado
        if est not in ("A", "I"):
            excepciones.append((doc, "CODIGO_INVALIDO", f"Código de estado inválido '{est}' para documento {doc}"))
        elif est == "I":
            inactivos_count += 1
        elif est == "A":
            if not cod_emp or cod_emp not in empresas:
                excepciones.append((doc, "SIN_EMPRESA", f"Afiliado activo con COD_EMP '{cod_emp}' no encontrado en EMPRESA"))
            else:
                activos_validos.append(r)

    # 4. Regla 4: Beneficiarios y BENEFICIARIO_HUERFANO
    all_afi_docs = {r["NRO_DOC"].strip() for r in afi_mae_rows}
    ben_counts = defaultdict(int)

    for b in afi_ben_rows:
        doc_afi = b["NRO_DOC_AFI"].strip()
        doc_ben = b["NRO_DOC_BEN"].strip()
        if doc_afi not in all_afi_docs:
            excepciones.append((doc_ben, "BENEFICIARIO_HUERFANO", f"Beneficiario {doc_ben} depende de afiliado {doc_afi} inexistente"))
        else:
            ben_counts[doc_afi] += 1

    # 5. Aportes: mayor PERIODO pagado
    max_aporte = {}
    for ap in aportes_rows:
        doc = ap["NRO_DOC"].strip()
        periodo = ap["PERIODO"].strip()
        if doc not in max_aporte or periodo > max_aporte[doc]:
            max_aporte[doc] = periodo

    # 6. Regla 6: Cruce Caja Oriente y CRUCE_NO_COINCIDE
    unique_afi_by_doc = {r["NRO_DOC"].strip(): r for r in unique_afi}
    for row in extracto_rows:
        raw_id = row["id_afiliado"].strip()
        doc = raw_id.lstrip("0")
        situacion = row["situacion"].strip().upper()

        if doc not in unique_afi_by_doc:
            excepciones.append((doc, "CRUCE_NO_COINCIDE", f"Afiliado {doc} del extracto no existe en AFI_MAE"))
        else:
            est_local = unique_afi_by_doc[doc]["EST_AFI"].strip().upper()
            equiv = {"VIGENTE": "A", "RETIRADO": "I"}.get(situacion)
            if equiv != est_local:
                excepciones.append((doc, "CRUCE_NO_COINCIDE", f"Situación {situacion} no coincide con estado local {est_local}"))

    # 7. Generar output/afiliados_activos.csv
    # Formato: documento,nombre,estado,cod_empresa,empresa,beneficiarios,ultimo_aporte
    activos_csv_path = os.path.join(OUTPUT_DIR, "afiliados_activos.csv")
    with open(activos_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["documento", "nombre", "estado", "cod_empresa", "empresa", "beneficiarios", "ultimo_aporte"])
        for r in activos_validos:
            doc = r["NRO_DOC"].strip()
            nom_parts = [r.get(f).strip() for f in ["NOM1", "NOM2", "APE1", "APE2"] if r.get(f) and r.get(f).strip()]
            nombre = " ".join(nom_parts)
            cod_emp = r["COD_EMP"].strip()
            nom_emp = empresas.get(cod_emp, "")
            num_ben = ben_counts.get(doc, 0)
            ult_apo = max_aporte.get(doc, "")
            writer.writerow([doc, nombre, "ACTIVO", cod_emp, nom_emp, num_ben, ult_apo])

    # 8. Generar output/excepciones.csv
    # Formato: documento,tipo,detalle
    excepciones_csv_path = os.path.join(OUTPUT_DIR, "excepciones.csv")
    with open(excepciones_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["documento", "tipo", "detalle"])
        for doc, tipo, detalle in excepciones:
            writer.writerow([doc, tipo, detalle])

    # 9. Generar output/totales.txt
    # clave=valor: total_afiliados, activos, inactivos, excepciones
    totales_path = os.path.join(OUTPUT_DIR, "totales.txt")
    with open(totales_path, "w", encoding="utf-8") as f:
        f.write(f"total_afiliados={total_afiliados}\n")
        f.write(f"activos={len(activos_validos)}\n")
        f.write(f"inactivos={inactivos_count}\n")
        f.write(f"excepciones={len(excepciones)}\n")

    # 10. Generar output/top_error.txt
    # Contar errores CIE-#### en los logs
    error_counter = Counter()
    for log_file in glob.glob(os.path.join(LOGS_DIR, "*.log")):
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                codes = re.findall(r"CIE-\d+", line)
                error_counter.update(codes)

    top_code, top_count = error_counter.most_common(1)[0] if error_counter else ("NINGUNO", 0)
    top_error_path = os.path.join(OUTPUT_DIR, "top_error.txt")
    with open(top_error_path, "w", encoding="utf-8") as f:
        f.write(f"codigo_error={top_code}\n")
        f.write(f"ocurrencias={top_count}\n")

    print(f"Cierre finalizado exitosamente.")
    print(f"total_afiliados={total_afiliados}, activos={len(activos_validos)}, inactivos={inactivos_count}, excepciones={len(excepciones)}")
    print(f"top_error: codigo_error={top_code}, ocurrencias={top_count}")


if __name__ == "__main__":
    main()