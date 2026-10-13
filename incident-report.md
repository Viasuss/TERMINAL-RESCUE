# Informe de incidentes — Terminal Rescue

## Incidente 1
- **Síntoma:** El contenedor del servicio `cierre-worker` se encontraba caído en estado `Exited (1)` al iniciar el entorno con `docker compose ps`.
- **Diagnóstico:** Revisando los registros de ejecución mediante `docker compose logs cierre-worker` se evidenció que la variable de entorno `WORKER_INTERVAL_SECONDS` contenía el valor `30s`. La función `int()` de Python fallaba con `ValueError` al no poder parsear la cadena con el sufijo de unidad.
- **Comandos:** `docker compose ps`, `docker compose logs cierre-worker | grep -i CIE-1107`
- **Solución:** Se editó el archivo de configuración `.env` y la plantilla `.env.example`, modificando `WORKER_INTERVAL_SECONDS=30` como entero puro en segundos y reiniciando el servicio.
- **Evidencia:** evidence/01-worker.txt

## Incidente 2
- **Síntoma:** La API no lograba conectarse a la base de datos relacional y arrojaba errores de conexión al consultar información.
- **Diagnóstico:** Se comprobó mediante `docker compose logs cierre-api` que el hostname configurado era `cierre-database`. Sin embargo, en la red interna de Docker el servicio de PostgreSQL está nombrado como `cierre-db`.
- **Comandos:** `docker compose exec cierre-db psql -U cierre -d cierre -c "SELECT count(*) FROM afi_mae;"`
- **Solución:** Se corrigió la variable `DATABASE_HOST=cierre-db` en `.env` y `.env.example`, permitiendo la correcta resolución DNS en la red de contenedores.
- **Evidencia:** evidence/02-database.txt

## Incidente 3
- **Síntoma:** El script de cierre `scripts/cierre.sh` fallaba inmediatamente al ejecutarse y no leía los archivos del lote mensual.
- **Diagnóstico:** Inspeccionando con `find` y `sed` la ruta de entrada en `scripts/cierre.sh`, se observó que apuntaba a `/opt/cierre/entrada`, un directorio inexistente en el host. Además, intentaba mover destructivamente el archivo de entrada.
- **Comandos:** `find scripts/ -type f`, `chmod +x scripts/cierre.sh`
- **Solución:** Se corrigieron las rutas para leer directamente desde `data/` y generar en `output/` de forma no destructiva e idempotente mediante `scripts/cierre.py`.
- **Evidencia:** evidence/03-entrada.txt

## Incidente 4
- **Síntoma:** Los registros históricos del sistema registraban miles de mensajes de fallas y códigos de error heterogéneos sin consolidar.
- **Diagnóstico:** Se analizaron los archivos bajo `logs/` con comandos de filtrado y conteo `grep`, `sort`, `uniq` y `wc`, identificando que el código con mayor recurrencia era `CIE-4012` con un total de 1424 ocurrencias.
- **Comandos:** `grep -o "CIE-[0-9]\+" logs/*.log | sort | uniq -c | sort -nr | head -5`
- **Solución:** Se integró en el proceso de cierre la agregación automática de errores para generar `output/top_error.txt` con el código y número exacto de apariciones.
- **Evidencia:** evidence/04-top_error.txt

## Incidente 5
- **Síntoma:** Discrepancias graves en la calidad de los datos maestros con registros duplicados, empresas inexistentes y beneficiarios sin titular.
- **Diagnóstico:** Consultando la base de datos con `psql` y filtrando los CSVs con `awk`, se identificaron 20 documentos duplicados, 14 estados con códigos inválidos, 18 afiliados activos sin empresa y 15 beneficiarios huérfanos.
- **Comandos:** `docker compose exec cierre-db psql -U cierre -d cierre -c "SELECT est_afi, count(*) FROM afi_mae GROUP BY est_afi;"`
- **Solución:** Se programaron en `scripts/cierre.py` las reglas del diccionario para reportar cada anomalía en `output/excepciones.csv`, y se creó `scripts/limpieza.sql` (ejecutado por `scripts/cierre.sh` con `psql`) que en la base elimina los duplicados conservando el primer registro, borra los beneficiarios huérfanos y normaliza las fechas interpretables.
- **Evidencia:** evidence/05-calidad.txt

## Incidente 6
- **Síntoma:** Las consultas al endpoint `GET /afiliados/{documento}` retornaban error HTTP 500 para afiliados existentes con nombres secundarios nulos.
- **Diagnóstico:** Al revisar el traceback con `docker compose logs cierre-api`, se detectó que `app.py` concatenaba directamente `nom1 + " " + nom2 + " " + ape1 + " " + ape2`. Cuando `nom2` o `ape2` eran `None`, Python arrojaba `TypeError`.
- **Comandos:** `docker compose logs cierre-api | grep -i CIE-5003`, `curl -i http://localhost:8081/afiliados/1098765432`
- **Solución:** Se refactorizó la lógica en `app.py` utilizando `filter(None, [...])` y `join` para omitir campos nulos o vacíos, y se implementó un fallback seguro ante estados no estándar.
- **Evidencia:** evidence/06-api.txt

## Incidente 7
- **Síntoma:** El proceso de cierre no interpretaba fechas de afiliación con formatos alternativos o descartaba registros silenciosamente.
- **Diagnóstico:** Se procesaron con `awk` y `sed` las fechas en `AFI_MAE.csv`, encontrando formatos `DD/MM/YYYY`, `YYYYMMDD` y 12 fechas no parseables o inexistentes como `2025-02-30` o `SIN FECHA`.
- **Comandos:** `awk -F',' '{print $9}' data/AFI_MAE.csv | grep -v "^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}$" | head -10`
- **Solución:** Se implementó normalización automática para fechas válidas en formatos alternativos y reporte obligatorio como `FECHA_INVALIDA` en `output/excepciones.csv` para las fechas ilegítimas.
- **Evidencia:** evidence/07-fechas.txt

## Incidente 8
- **Síntoma:** El archivo de cruce remitido por Caja Oriente utilizaba una estructura, separadores y nomenclatura incompatibles con el maestro local.
- **Diagnóstico:** Con `grep` y `wc -l` sobre `data/extracto_caja_oriente.csv` se constató el uso de delimitador `;`, documentos con ceros a la izquierda y estados `VIGENTE` y `RETIRADO`.
- **Comandos:** `grep ";" data/extracto_caja_oriente.csv | wc -l`, `sort data/extracto_caja_oriente.csv | head -5`
- **Solución:** Se adaptó el parser para normalizar los números de documento eliminando ceros a la izquierda y validar la equivalencia de estados, reportando las 25 discrepancias en `output/excepciones.csv` bajo el tipo `CRUCE_NO_COINCIDE`.
- **Evidencia:** evidence/08-cruce.txt

## Incidente 9
- **Síntoma:** Los totales de afiliados y estados generados por el script heredado no cuadraban con los valores auditados de la hoja de control.
- **Diagnóstico:** El script original contaba líneas totales de archivo con `wc -l` en vez de documentos únicos, e ignoraba la exclusión de afiliados sin empresa válida y estados anómalos.
- **Comandos:** `wc -l control/hoja_control.csv`, `cat control/hoja_control.csv`
- **Solución:** Se computaron los totales exactos aplicando las reglas de negocio (1500 afiliados únicos, 1194 activos, 274 inactivos y 104 excepciones), generando el archivo `output/totales.txt`.
- **Evidencia:** evidence/09-totales.txt

## Incidente 10
- **Síntoma:** El proceso de cierre fallaba sistemáticamente a partir de la segunda ejecución consecutiva.
- **Diagnóstico:** El script original ejecutaba `mkdir output` sin bandera de existencia y realizaba un `mv` de los datos de entrada a una carpeta de procesados, dejando el sistema sin insumos para corridas posteriores.
- **Comandos:** `find output/ -type f | wc -l`, `chmod +x run.sh`
- **Solución:** Se aseguró la idempotencia del pipeline creando directorios con `mkdir -p`, leyendo los insumos en modo solo lectura y garantizando que múltiples corridas de `./run.sh` produzcan resultados idénticos sin pérdida de datos.
- **Evidencia:** evidence/10-repetibilidad.txt