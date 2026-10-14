# Uso de inteligencia artificial

## Uso 1
- Herramienta: Claude 3.7 Sonnet y Gemini
- Para qué se usó: Diagnosticar la causa raíz del fallo en la API y el error de conexión con la base de datos
- Prompt principal (resumido): "Analizar error de conexión en docker-compose y TypeError en app.py al consultar afiliados"
- Qué produjo: Identificó que DATABASE_HOST debía apuntar al nombre de servicio docker cierre-db y sugirió usar un filtro de campos nulos en app.py
- Qué modificó o corrigió el equipo: El equipo verificó los nombres reales de los servicios en docker-compose.yml y refactorizó app.py usando filter(None, ...) para evitar caídas con valores nulos

## Uso 2
- Herramienta: Claude 3.7 Sonnet y Gemini
- Para qué se usó: Formulación de las reglas de deduplicación y cruce de datos del diccionario de datos
- Prompt principal (resumido): "Cómo procesar duplicados en AFI_MAE, normalizar fechas y cruzar con extracto de Caja Oriente según las reglas del diccionario"
- Qué produjo: Un bosquejo de script para clasificar excepciones DUPLICADO, FECHA_INVALIDA y CRUCE_NO_COINCIDE
- Qué modificó o corrigió el equipo: El equipo ajustó la normalización de identificadores con ceros a la izquierda y validó contra las huellas criptográficas del validador oficial

## Uso 3
- Herramienta: Claude 3.7 Sonnet y Gemini
- Para qué se usó: Diseño de pipeline idempotente para scripts/cierre.sh y generación de top_error.txt
- Prompt principal (resumido): "Cómo estructurar el script de cierre para que sea repetible, no mueva archivos de entrada y extraiga el error más frecuente de logs"
- Qué produjo: Propuesta para consolidar logs de worker y api con expresiones regulares y escribir totales en formato clave-valor
- Qué modificó o corrigió el equipo: El equipo implementó la agregación de todos los logs en scripts/cierre.py asegurando que run.sh pueda ejecutarse múltiples veces sin modificar los CSVs de origen