-- Limpieza de la base del cierre. Es idempotente: se puede ejecutar varias veces.
-- Corrige lo reparable; lo irreparable (estado invalido, sin empresa, fechas
-- ininterpretables, cruces) queda reportado en output/excepciones.csv.

-- Funcion auxiliar: normaliza FEC_AFI a YYYY-MM-DD o devuelve NULL si no es fecha real.
CREATE OR REPLACE FUNCTION pg_temp.fec_norm(t text) RETURNS text AS $$
BEGIN
    t := btrim(t);
    IF t ~ '^\d{4}-\d{2}-\d{2}$' THEN
        RETURN to_char(to_date(t, 'YYYY-MM-DD'), 'YYYY-MM-DD');
    ELSIF t ~ '^\d{2}/\d{2}/\d{4}$' THEN
        RETURN to_char(to_date(t, 'DD/MM/YYYY'), 'YYYY-MM-DD');
    ELSIF t ~ '^\d{8}$' THEN
        RETURN to_char(to_date(t, 'YYYYMMDD'), 'YYYY-MM-DD');
    END IF;
    RETURN NULL;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

BEGIN;

-- 1. Espacios sobrantes
UPDATE afi_mae SET nro_doc = btrim(nro_doc), est_afi = btrim(est_afi),
                   cod_emp = btrim(cod_emp), fec_afi = btrim(fec_afi);

-- 2. DUPLICADOS: conservar la primera aparicion (orden de carga)
DELETE FROM afi_mae a USING afi_mae b
WHERE a.nro_doc = b.nro_doc AND a.ctid > b.ctid;

-- 3. FECHAS: normalizar las que se pueden interpretar (las demas se reportan)
UPDATE afi_mae SET fec_afi = pg_temp.fec_norm(fec_afi)
WHERE pg_temp.fec_norm(fec_afi) IS NOT NULL
  AND pg_temp.fec_norm(fec_afi) <> fec_afi;

-- 4. BENEFICIARIOS HUERFANOS: sin afiliado no tienen a quien pertenecer
DELETE FROM afi_ben b
WHERE NOT EXISTS (SELECT 1 FROM afi_mae a WHERE a.nro_doc = b.nro_doc_afi);

COMMIT;
