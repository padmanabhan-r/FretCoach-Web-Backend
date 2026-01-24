-- Table: fretcoach.ai_practice_plans

-- DROP TABLE IF EXISTS fretcoach.ai_practice_plans;

CREATE TABLE IF NOT EXISTS fretcoach.ai_practice_plans
(
    practice_id uuid NOT NULL,
    user_id character varying(255) COLLATE pg_catalog."default" NOT NULL,
    generated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    practice_plan text COLLATE pg_catalog."default" NOT NULL,
    executed_session_id character varying(255) COLLATE pg_catalog."default",
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ai_practice_plans_pkey PRIMARY KEY (practice_id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS fretcoach.ai_practice_plans
    OWNER to postgres;

ALTER TABLE IF EXISTS fretcoach.ai_practice_plans
    ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE fretcoach.ai_practice_plans FROM paddy;

GRANT INSERT, DELETE, SELECT, UPDATE ON TABLE fretcoach.ai_practice_plans TO paddy;

GRANT ALL ON TABLE fretcoach.ai_practice_plans TO postgres;

-- Index: idx_practice_plans_execution

CREATE INDEX IF NOT EXISTS idx_practice_plans_execution
    ON fretcoach.ai_practice_plans USING btree
    (executed_session_id COLLATE pg_catalog."default" ASC NULLS LAST)
    WITH (fillfactor=100, deduplicate_items=True)
    TABLESPACE pg_default;

-- Index: idx_practice_plans_user_time

CREATE INDEX IF NOT EXISTS idx_practice_plans_user_time
    ON fretcoach.ai_practice_plans USING btree
    (user_id COLLATE pg_catalog."default" ASC NULLS LAST, generated_at DESC NULLS FIRST)
    WITH (fillfactor=100, deduplicate_items=True)
    TABLESPACE pg_default;
