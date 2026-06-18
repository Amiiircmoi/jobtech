-- ════════════════════════════════════════════════════════════════════════
-- jobtech — Data Warehouse : schéma en étoile (PostgreSQL)
-- ════════════════════════════════════════════════════════════════════════
-- 5 dimensions + 1 table de faits. Idempotent (CREATE TABLE IF NOT EXISTS).
-- Clés naturelles UNIQUE → permettent un chargement par UPSERT (ON CONFLICT).
-- Contraintes d'intégrité (NOT NULL, FK, UNIQUE, CHECK) garanties au niveau SGBD.
-- ════════════════════════════════════════════════════════════════════════

-- ── Dimension temps ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS d_date (
    date_key  DATE      PRIMARY KEY,
    day       SMALLINT  NOT NULL,
    month     SMALLINT  NOT NULL,
    quarter   SMALLINT  NOT NULL,
    year      SMALLINT  NOT NULL,
    day_week  SMALLINT  NOT NULL
);

-- ── Dimension pays ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS d_country (
    id_country    SERIAL  PRIMARY KEY,
    iso2          CHAR(2) NOT NULL UNIQUE,
    country_name  TEXT    NOT NULL,
    region        TEXT,
    monnaie_iso3  CHAR(3)
);

-- ── Dimension entreprise ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS d_company (
    id_company      SERIAL PRIMARY KEY,
    company_name    TEXT   NOT NULL UNIQUE,
    workforce_size  TEXT,
    sector          TEXT
);

-- ── Dimension compétence ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS d_skill (
    id_skill     SERIAL PRIMARY KEY,
    tech_label   TEXT   NOT NULL UNIQUE,
    skill_group  TEXT
);

-- ── Dimension source ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS d_source (
    id_source    SERIAL PRIMARY KEY,
    source_name  TEXT   NOT NULL UNIQUE
);

-- ── Table de faits : offres d'emploi agrégées (grain = date×pays×skill×source×entreprise) ──
CREATE TABLE IF NOT EXISTS fact_job (
    id_fact     BIGSERIAL    PRIMARY KEY,
    date_key    DATE         NOT NULL REFERENCES d_date(date_key),
    id_country  INTEGER      NOT NULL REFERENCES d_country(id_country),
    id_company  INTEGER      NOT NULL REFERENCES d_company(id_company),
    id_skill    INTEGER      NOT NULL REFERENCES d_skill(id_skill),
    id_source   INTEGER      NOT NULL REFERENCES d_source(id_source),
    avg_salary  NUMERIC(12,2),
    min_salary  NUMERIC(12,2),
    max_salary  NUMERIC(12,2),
    job_count   INTEGER      NOT NULL DEFAULT 0,
    CONSTRAINT uq_fact_grain
        UNIQUE (date_key, id_country, id_company, id_skill, id_source),
    CONSTRAINT ck_salary_order
        CHECK (min_salary IS NULL OR max_salary IS NULL OR min_salary <= max_salary),
    CONSTRAINT ck_job_count_positive
        CHECK (job_count >= 0)
);

-- ── Index pour l'accès rapide analytique ────────────────────────────────
CREATE INDEX IF NOT EXISTS ix_fact_date    ON fact_job (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_country ON fact_job (id_country);
CREATE INDEX IF NOT EXISTS ix_fact_skill   ON fact_job (id_skill);
CREATE INDEX IF NOT EXISTS ix_fact_source  ON fact_job (id_source);
