# Terminal Rescue — Equipo FESC

## Descripción

Terminal Rescue es una solución de rescate, diagnóstico y estabilización técnica del sistema legacy de procesamiento de afiliados para una Caja de Compensación Familiar. Resuelve las fallas críticas de conectividad entre microservicios, caídas en contenedores de conciliación, errores 500 en endpoints de consulta de afiliados y desajustes en el proceso de cierre mensual de operaciones, garantizando que el área de Subsidios reciba información exacta, deduplicada y auditada de forma repetible y confiable.

## Integrantes

- Johan sebastian viasus cardoso
- Wilmer dubuath mantilla rincon

## Requisitos

- Sistema operativo Linux, macOS o Windows con WSL2 / entorno POSIX.
- Docker versión 24+ y Docker Compose v2+.
- Python versión 3.8 o superior.
- Utilidades estándar de terminal: bash, curl, jq, psql, grep, awk, sed, sort, uniq, wc, find, chmod.

## Instalación y ejecución

Para levantar el entorno completo y ejecutar el cierre desde una copia limpia, siga los comandos en orden:
1. Copie el archivo de variables de entorno: `cp .env.example .env`.
2. Levante los servicios en segundo plano con reconstrucción de imágenes: `docker compose up -d --build`.
3. Verifique que los contenedores estén saludables: `docker compose ps`.
4. Ejecute el proceso de cierre mensual de afiliados: `./run.sh` (genera `output/` y limpia la base).

## Configuración

Las variables de entorno requeridas en el archivo `.env.example` y `.env` son:

- `POSTGRES_DB`: Nombre de la base de datos principal de PostgreSQL (ejemplo: `cierre`).
- `POSTGRES_USER`: Usuario administrador para la base de datos relacional (ejemplo: `cierre`).
- `POSTGRES_PASSWORD`: Contraseña para autenticación en la base de datos (ejemplo: `cambia_esta_clave`).
- `DATABASE_HOST`: Host de conexión de red para la base de datos, correspondiente al servicio Docker (ejemplo: `cierre-db`).
- `DATABASE_PORT`: Puerto TCP interno del motor PostgreSQL (ejemplo: `5432`).
- `DATABASE_NAME`: Base de datos a la que conectan la API y el worker (ejemplo: `cierre`).
- `DATABASE_USER`: Usuario de aplicación para conexiones de base de datos (ejemplo: `cierre`).
- `DATABASE_PASSWORD`: Credencial de conexión para la aplicación (ejemplo: `cambia_esta_clave`).
- `API_PORT`: Puerto expuesto en el host para el servicio de consulta HTTP (ejemplo: `8081`).
- `WORKER_INTERVAL_SECONDS`: Intervalo periódico en segundos para la conciliación del worker (ejemplo: `30`).

## Arquitectura

El sistema se compone de tres servicios orquestados en red mediante Docker Compose:

1. `cierre-db`: Motor de base de datos PostgreSQL 16 Alpine que almacena los maestros operativos (`afi_mae`, `empresa`, `afi_ben`, `aportes`).
2. `cierre-api`: Servicio web desarrollado en Python (puerto 8081) que expone endpoints REST para que el área de Subsidios consulte el estado de los afiliados en tiempo real conectándose a `cierre-db`.
3. `cierre-worker`: Proceso en segundo plano que concilia periódicamente cada 30 segundos la integridad del número total de registros y documentos distintos contra `cierre-db`.

La comunicación entre contenedores se realiza a través de la red bridge interna usando resolución DNS de Docker por nombre de servicio.

## Uso

### Consulta de Afiliados vía API REST
Realice peticiones HTTP GET al endpoint `/afiliados/{documento}` (ruta parametrizada `/afiliados/{x}`):
```bash
curl -i http://localhost:8081/afiliados/1098765432
```
Respuesta esperada (HTTP 200):
```json
{
  "documento": "1098765432",
  "nombre": "JUAN CARLOS PEREZ GOMEZ",
  "estado": "ACTIVO",
  "empresa": "EMPRESA ABC"
}
```
Si el afiliado no existe en el sistema, la API responde con código `404 Not Found`.

### Ejecución del Cierre Mensual
La ejecución de `./run.sh` procesa los insumos y genera de manera determinista los cuatro archivos obligatorios en el directorio `output/`:
- `output/afiliados_activos.csv`: Contiene el listado de afiliados activos con empresa válida, beneficiarios y último aporte.
- `output/excepciones.csv`: Registra las excepciones detectadas (`DUPLICADO`, `SIN_EMPRESA`, `BENEFICIARIO_HUERFANO`, `CODIGO_INVALIDO`, `FECHA_INVALIDA`, `CRUCE_NO_COINCIDE`).
- `output/totales.txt`: Archivo en formato clave-valor con los totales de `total_afiliados`, `activos`, `inactivos` y `excepciones`.
- `output/top_error.txt`: Consolidado del código de error más frecuente en los registros (`codigo_error` y `ocurrencias`).

## Pruebas

Para comprobar que todo el entorno funciona correctamente y cumple las reglas del reto, ejecute las pruebas con los comandos:
- Validación rápida de servicios y reglas: `./validator check --quick`.
- Verificación de entregables y rúbrica: `./validator entregables`.
- Comprobación manual de repetibilidad del cierre: `./run.sh && ./run.sh`.
El resultado esperado es la aprobación del 100% de las pruebas y la coincidencia exacta de los totales con la hoja de control.

## Documentación

Los documentos complementarios y auditorías del reto se encuentran enlazados en el repositorio:
- [Informe de incidentes](file:///c:/Users/Johan%20Viasus/Downloads/fesc-tecnico/incident-report.md)
- [Evidencias de terminal](file:///c:/Users/Johan%20Viasus/Downloads/fesc-tecnico/evidence/)
- [Registro de uso de IA](file:///c:/Users/Johan%20Viasus/Downloads/fesc-tecnico/AI_USAGE.md)

## Qué resolvimos

Se reparó el entorno Docker corrigiendo el formato de tiempo en el worker y el nombre de host de la base de datos. En la API se resolvió la concatenación defectuosa de nombres para campos nulos y el manejo de estados atípicos. En el proceso de cierre mensual se eliminaron dependencias a rutas absolutas inexistentes y se implementó una arquitectura en Python idempotente que aplica deduplicación, validación de fechas, cruce con Caja Oriente y generación precisa de los archivos exigidos.

## Limitaciones y pendientes

El sistema depende de insumos en archivos planos CSV heredados; queda pendiente implementar colas de mensajes y migración a una base de datos relacional nativa en producción.