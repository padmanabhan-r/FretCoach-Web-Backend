-- Table: fretcoach.sessions

-- DROP TABLE IF EXISTS fretcoach.sessions;

CREATE TABLE IF NOT EXISTS fretcoach.sessions
(
    session_id character varying(255) COLLATE pg_catalog."default" NOT NULL,
    user_id character varying(255) COLLATE pg_catalog."default" NOT NULL,
    start_timestamp timestamp without time zone NOT NULL,
    end_timestamp timestamp without time zone,
    pitch_accuracy double precision,
    scale_conformity double precision,
    timing_stability double precision,
    scale_chosen character varying(100) COLLATE pg_catalog."default" NOT NULL,
    sensitivity double precision NOT NULL,
    strictness double precision NOT NULL,
    total_notes_played integer DEFAULT 0,
    correct_notes_played integer DEFAULT 0,
    bad_notes_played integer DEFAULT 0,
    total_inscale_notes integer,
    duration_seconds double precision,
    ambient_light_option boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    scale_type character varying(20) COLLATE pg_catalog."default" DEFAULT 'diatonic'::character varying,
    CONSTRAINT sessions_pkey PRIMARY KEY (session_id, user_id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS fretcoach.sessions
    OWNER to postgres;

ALTER TABLE IF EXISTS fretcoach.sessions
    ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE fretcoach.sessions FROM paddy;

GRANT INSERT, DELETE, SELECT, UPDATE ON TABLE fretcoach.sessions TO paddy;

GRANT ALL ON TABLE fretcoach.sessions TO postgres;

-- Index: idx_sessions_start_timestamp

CREATE INDEX IF NOT EXISTS idx_sessions_start_timestamp
    ON fretcoach.sessions USING btree
    (start_timestamp DESC NULLS FIRST)
    WITH (fillfactor=100, deduplicate_items=True)
    TABLESPACE pg_default;

-- Index: idx_sessions_user_id

CREATE INDEX IF NOT EXISTS idx_sessions_user_id
    ON fretcoach.sessions USING btree
    (user_id COLLATE pg_catalog."default" ASC NULLS LAST)
    WITH (fillfactor=100, deduplicate_items=True)
    TABLESPACE pg_default;
