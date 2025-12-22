--
-- PostgreSQL database dump
--

\restrict ymVRjRMnxvPc2JkPdeKpxCv6teZVHWQSbNlX6cQbabVIPbGzPOAHwQ7ZfBkphG9

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.0 (Debian 18.0-1.pgdg12+3)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA auth;


ALTER SCHEMA auth OWNER TO supabase_admin;

--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA extensions;


ALTER SCHEMA extensions OWNER TO postgres;

--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql;


ALTER SCHEMA graphql OWNER TO supabase_admin;

--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql_public;


ALTER SCHEMA graphql_public OWNER TO supabase_admin;

--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: pgbouncer
--

CREATE SCHEMA pgbouncer;


ALTER SCHEMA pgbouncer OWNER TO pgbouncer;

--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA realtime;


ALTER SCHEMA realtime OWNER TO supabase_admin;

--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA storage;


ALTER SCHEMA storage OWNER TO supabase_admin;

--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA vault;


ALTER SCHEMA vault OWNER TO supabase_admin;

--
-- Name: pg_graphql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_graphql WITH SCHEMA graphql;


--
-- Name: EXTENSION pg_graphql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_graphql IS 'pg_graphql: GraphQL support';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


ALTER TYPE auth.aal_level OWNER TO supabase_auth_admin;

--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


ALTER TYPE auth.code_challenge_method OWNER TO supabase_auth_admin;

--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


ALTER TYPE auth.factor_status OWNER TO supabase_auth_admin;

--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


ALTER TYPE auth.factor_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_authorization_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_authorization_status AS ENUM (
    'pending',
    'approved',
    'denied',
    'expired'
);


ALTER TYPE auth.oauth_authorization_status OWNER TO supabase_auth_admin;

--
-- Name: oauth_client_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_client_type AS ENUM (
    'public',
    'confidential'
);


ALTER TYPE auth.oauth_client_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


ALTER TYPE auth.oauth_registration_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_response_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_response_type AS ENUM (
    'code'
);


ALTER TYPE auth.oauth_response_type OWNER TO supabase_auth_admin;

--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


ALTER TYPE auth.one_time_token_type OWNER TO supabase_auth_admin;

--
-- Name: action; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


ALTER TYPE realtime.action OWNER TO supabase_admin;

--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in'
);


ALTER TYPE realtime.equality_op OWNER TO supabase_admin;

--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


ALTER TYPE realtime.user_defined_filter OWNER TO supabase_admin;

--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


ALTER TYPE realtime.wal_column OWNER TO supabase_admin;

--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


ALTER TYPE realtime.wal_rls OWNER TO supabase_admin;

--
-- Name: buckettype; Type: TYPE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TYPE storage.buckettype AS ENUM (
    'STANDARD',
    'ANALYTICS'
);


ALTER TYPE storage.buckettype OWNER TO supabase_storage_admin;

--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


ALTER FUNCTION auth.email() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;

--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_cron_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    func_is_graphql_resolve bool;
BEGIN
    func_is_graphql_resolve = (
        SELECT n.proname = 'resolve'
        FROM pg_event_trigger_ddl_commands() AS ev
        LEFT JOIN pg_catalog.pg_proc AS n
        ON ev.objid = n.oid
    );

    IF func_is_graphql_resolve
    THEN
        -- Update public wrapper to pass all arguments through to the pg_graphql resolve func
        DROP FUNCTION IF EXISTS graphql_public.graphql;
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language sql
        as $$
            select graphql.resolve(
                query := query,
                variables := coalesce(variables, '{}'),
                "operationName" := "operationName",
                extensions := extensions
            );
        $$;

        -- This hook executes when `graphql.resolve` is created. That is not necessarily the last
        -- function in the extension so we need to grant permissions on existing entities AND
        -- update default permissions to any others that are created after `graphql.resolve`
        grant usage on schema graphql to postgres, anon, authenticated, service_role;
        grant select on all tables in schema graphql to postgres, anon, authenticated, service_role;
        grant execute on all functions in schema graphql to postgres, anon, authenticated, service_role;
        grant all on all sequences in schema graphql to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on tables to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on functions to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on sequences to postgres, anon, authenticated, service_role;

        -- Allow postgres role to allow granting usage on graphql and graphql_public schemas to custom roles
        grant usage on schema graphql_public to postgres with grant option;
        grant usage on schema graphql to postgres with grant option;
    END IF;

END;
$_$;


ALTER FUNCTION extensions.grant_pg_graphql_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_roles
      WHERE rolname = 'supabase_functions_admin'
    )
    THEN
      CREATE USER supabase_functions_admin NOINHERIT CREATEROLE LOGIN NOREPLICATION;
    END IF;

    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    IF EXISTS (
      SELECT FROM pg_extension
      WHERE extname = 'pg_net'
      -- all versions in use on existing projects as of 2025-02-20
      -- version 0.12.0 onwards don't need these applied
      AND extversion IN ('0.2', '0.6', '0.7', '0.7.1', '0.8', '0.10.0', '0.11.0')
    ) THEN
      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

      REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

      GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
      GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    END IF;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_net_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_ddl_watch() OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_drop_watch() OWNER TO supabase_admin;

--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


ALTER FUNCTION extensions.set_graphql_placeholder() OWNER TO supabase_admin;

--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: supabase_admin
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $_$
begin
    raise debug 'PgBouncer auth request: %', p_usename;

    return query
    select 
        rolname::text, 
        case when rolvaliduntil < now() 
            then null 
            else rolpassword::text 
        end 
    from pg_authid 
    where rolname=$1 and rolcanlogin;
end;
$_$;


ALTER FUNCTION pgbouncer.get_auth(p_usename text) OWNER TO supabase_admin;

--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
-- Regclass of the table e.g. public.notes
entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

-- I, U, D, T: insert, update ...
action realtime.action = (
    case wal ->> 'action'
        when 'I' then 'INSERT'
        when 'U' then 'UPDATE'
        when 'D' then 'DELETE'
        else 'ERROR'
    end
);

-- Is row level security enabled for the table
is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

subscriptions realtime.subscription[] = array_agg(subs)
    from
        realtime.subscription subs
    where
        subs.entity = entity_;

-- Subscription vars
roles regrole[] = array_agg(distinct us.claims_role::text)
    from
        unnest(subscriptions) us;

working_role regrole;
claimed_role regrole;
claims jsonb;

subscription_id uuid;
subscription_has_access bool;
visible_to_subscription_ids uuid[] = '{}';

-- structured info for wal's columns
columns realtime.wal_column[];
-- previous identity values for update/delete
old_columns realtime.wal_column[];

error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

-- Primary jsonb output for record
output jsonb;

begin
perform set_config('role', null, true);

columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'columns') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

old_columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'identity') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

for working_role in select * from unnest(roles) loop

    -- Update `is_selectable` for columns and old_columns
    columns =
        array_agg(
            (
                c.name,
                c.type_name,
                c.type_oid,
                c.value,
                c.is_pkey,
                pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
            )::realtime.wal_column
        )
        from
            unnest(columns) c;

    old_columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(old_columns) c;

    if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            -- subscriptions is already filtered by entity
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 400: Bad Request, no primary key']
        )::realtime.wal_rls;

    -- The claims role does not have SELECT permission to the primary key of entity
    elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 401: Unauthorized']
        )::realtime.wal_rls;

    else
        output = jsonb_build_object(
            'schema', wal ->> 'schema',
            'table', wal ->> 'table',
            'type', action,
            'commit_timestamp', to_char(
                ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
            ),
            'columns', (
                select
                    jsonb_agg(
                        jsonb_build_object(
                            'name', pa.attname,
                            'type', pt.typname
                        )
                        order by pa.attnum asc
                    )
                from
                    pg_attribute pa
                    join pg_type pt
                        on pa.atttypid = pt.oid
                where
                    attrelid = entity_
                    and attnum > 0
                    and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
            )
        )
        -- Add "record" key for insert and update
        || case
            when action in ('INSERT', 'UPDATE') then
                jsonb_build_object(
                    'record',
                    (
                        select
                            jsonb_object_agg(
                                -- if unchanged toast, get column name and value from old record
                                coalesce((c).name, (oc).name),
                                case
                                    when (c).name is null then (oc).value
                                    else (c).value
                                end
                            )
                        from
                            unnest(columns) c
                            full outer join unnest(old_columns) oc
                                on (c).name = (oc).name
                        where
                            coalesce((c).is_selectable, (oc).is_selectable)
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                    )
                )
            else '{}'::jsonb
        end
        -- Add "old_record" key for update and delete
        || case
            when action = 'UPDATE' then
                jsonb_build_object(
                        'old_record',
                        (
                            select jsonb_object_agg((c).name, (c).value)
                            from unnest(old_columns) c
                            where
                                (c).is_selectable
                                and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                        )
                    )
            when action = 'DELETE' then
                jsonb_build_object(
                    'old_record',
                    (
                        select jsonb_object_agg((c).name, (c).value)
                        from unnest(old_columns) c
                        where
                            (c).is_selectable
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                    )
                )
            else '{}'::jsonb
        end;

        -- Create the prepared statement
        if is_rls_enabled and action <> 'DELETE' then
            if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                deallocate walrus_rls_stmt;
            end if;
            execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
        end if;

        visible_to_subscription_ids = '{}';

        for subscription_id, claims in (
                select
                    subs.subscription_id,
                    subs.claims
                from
                    unnest(subscriptions) subs
                where
                    subs.entity = entity_
                    and subs.claims_role = working_role
                    and (
                        realtime.is_visible_through_filters(columns, subs.filters)
                        or (
                          action = 'DELETE'
                          and realtime.is_visible_through_filters(old_columns, subs.filters)
                        )
                    )
        ) loop

            if not is_rls_enabled or action = 'DELETE' then
                visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
            else
                -- Check if RLS allows the role to see the record
                perform
                    -- Trim leading and trailing quotes from working_role because set_config
                    -- doesn't recognize the role as valid if they are included
                    set_config('role', trim(both '"' from working_role::text), true),
                    set_config('request.jwt.claims', claims::text, true);

                execute 'execute walrus_rls_stmt' into subscription_has_access;

                if subscription_has_access then
                    visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
                end if;
            end if;
        end loop;

        perform set_config('role', null, true);

        return next (
            output,
            is_rls_enabled,
            visible_to_subscription_ids,
            case
                when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                else '{}'
            end
        )::realtime.wal_rls;

    end if;
end loop;

perform set_config('role', null, true);
end;
$$;


ALTER FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


ALTER FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) OWNER TO supabase_admin;

--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


ALTER FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) OWNER TO supabase_admin;

--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    declare
      res jsonb;
    begin
      execute format('select to_jsonb(%L::'|| type_::text || ')', val)  into res;
      return res;
    end
    $$;


ALTER FUNCTION realtime."cast"(val text, type_ regtype) OWNER TO supabase_admin;

--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
      /*
      Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
      */
      declare
          op_symbol text = (
              case
                  when op = 'eq' then '='
                  when op = 'neq' then '!='
                  when op = 'lt' then '<'
                  when op = 'lte' then '<='
                  when op = 'gt' then '>'
                  when op = 'gte' then '>='
                  when op = 'in' then '= any'
                  else 'UNKNOWN OP'
              end
          );
          res boolean;
      begin
          execute format(
              'select %L::'|| type_::text || ' ' || op_symbol
              || ' ( %L::'
              || (
                  case
                      when op = 'in' then type_::text || '[]'
                      else type_::text end
              )
              || ')', val_1, val_2) into res;
          return res;
      end;
      $$;


ALTER FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) OWNER TO supabase_admin;

--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $_$
    /*
    Should the record be visible (true) or filtered out (false) after *filters* are applied
    */
        select
            -- Default to allowed when no filters present
            $2 is null -- no filters. this should not happen because subscriptions has a default
            or array_length($2, 1) is null -- array length of an empty array is null
            or bool_and(
                coalesce(
                    realtime.check_equality_op(
                        op:=f.op,
                        type_:=coalesce(
                            col.type_oid::regtype, -- null when wal2json version <= 2.4
                            col.type_name::regtype
                        ),
                        -- cast jsonb to text
                        val_1:=col.value #>> '{}',
                        val_2:=f.value
                    ),
                    false -- if null, filter does not match
                )
            )
        from
            unnest(filters) f
            join unnest(columns) col
                on f.column_name = col.name;
    $_$;


ALTER FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) OWNER TO supabase_admin;

--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS SETOF realtime.wal_rls
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
    AS $$
      with pub as (
        select
          concat_ws(
            ',',
            case when bool_or(pubinsert) then 'insert' else null end,
            case when bool_or(pubupdate) then 'update' else null end,
            case when bool_or(pubdelete) then 'delete' else null end
          ) as w2j_actions,
          coalesce(
            string_agg(
              realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
              ','
            ) filter (where ppt.tablename is not null and ppt.tablename not like '% %'),
            ''
          ) w2j_add_tables
        from
          pg_publication pp
          left join pg_publication_tables ppt
            on pp.pubname = ppt.pubname
        where
          pp.pubname = publication
        group by
          pp.pubname
        limit 1
      ),
      w2j as (
        select
          x.*, pub.w2j_add_tables
        from
          pub,
          pg_logical_slot_get_changes(
            slot_name, null, max_changes,
            'include-pk', 'true',
            'include-transaction', 'false',
            'include-timestamp', 'true',
            'include-type-oids', 'true',
            'format-version', '2',
            'actions', pub.w2j_actions,
            'add-tables', pub.w2j_add_tables
          ) x
      )
      select
        xyz.wal,
        xyz.is_rls_enabled,
        xyz.subscription_ids,
        xyz.errors
      from
        w2j,
        realtime.apply_rls(
          wal := w2j.data::jsonb,
          max_record_bytes := max_record_bytes
        ) xyz(wal, is_rls_enabled, subscription_ids, errors)
      where
        w2j.w2j_add_tables <> ''
        and xyz.subscription_ids[1] is not null
    $$;


ALTER FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
      select
        (
          select string_agg('' || ch,'')
          from unnest(string_to_array(nsp.nspname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
        )
        || '.'
        || (
          select string_agg('' || ch,'')
          from unnest(string_to_array(pc.relname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
          )
      from
        pg_class pc
        join pg_namespace nsp
          on pc.relnamespace = nsp.oid
      where
        pc.oid = entity
    $$;


ALTER FUNCTION realtime.quote_wal2json(entity regclass) OWNER TO supabase_admin;

--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  BEGIN
    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    -- Attempt to insert the message
    INSERT INTO realtime.messages (payload, event, topic, private, extension)
    VALUES (payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      -- Capture and notify the error
      RAISE WARNING 'ErrorSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


ALTER FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) OWNER TO supabase_admin;

--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    /*
    Validates that the user defined filters for a subscription:
    - refer to valid columns that the claimed role may access
    - values are coercable to the correct column type
    */
    declare
        col_names text[] = coalesce(
                array_agg(c.column_name order by c.ordinal_position),
                '{}'::text[]
            )
            from
                information_schema.columns c
            where
                format('%I.%I', c.table_schema, c.table_name)::regclass = new.entity
                and pg_catalog.has_column_privilege(
                    (new.claims ->> 'role'),
                    format('%I.%I', c.table_schema, c.table_name)::regclass,
                    c.column_name,
                    'SELECT'
                );
        filter realtime.user_defined_filter;
        col_type regtype;

        in_val jsonb;
    begin
        for filter in select * from unnest(new.filters) loop
            -- Filtered column is valid
            if not filter.column_name = any(col_names) then
                raise exception 'invalid column for filter %', filter.column_name;
            end if;

            -- Type is sanitized and safe for string interpolation
            col_type = (
                select atttypid::regtype
                from pg_catalog.pg_attribute
                where attrelid = new.entity
                      and attname = filter.column_name
            );
            if col_type is null then
                raise exception 'failed to lookup type for column %', filter.column_name;
            end if;

            -- Set maximum number of entries for in filter
            if filter.op = 'in'::realtime.equality_op then
                in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
                if coalesce(jsonb_array_length(in_val), 0) > 100 then
                    raise exception 'too many values for `in` filter. Maximum 100';
                end if;
            else
                -- raises an exception if value is not coercable to type
                perform realtime.cast(filter.value, col_type);
            end if;

        end loop;

        -- Apply consistent order to filters so the unique constraint on
        -- (subscription_id, entity, filters) can't be tricked by a different filter order
        new.filters = coalesce(
            array_agg(f order by f.column_name, f.op, f.value),
            '{}'
        ) from unnest(new.filters) f;

        return new;
    end;
    $$;


ALTER FUNCTION realtime.subscription_check_filters() OWNER TO supabase_admin;

--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


ALTER FUNCTION realtime.to_regrole(role_name text) OWNER TO supabase_admin;

--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


ALTER FUNCTION realtime.topic() OWNER TO supabase_realtime_admin;

--
-- Name: add_prefixes(text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.add_prefixes(_bucket_id text, _name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    prefixes text[];
BEGIN
    prefixes := "storage"."get_prefixes"("_name");

    IF array_length(prefixes, 1) > 0 THEN
        INSERT INTO storage.prefixes (name, bucket_id)
        SELECT UNNEST(prefixes) as name, "_bucket_id" ON CONFLICT DO NOTHING;
    END IF;
END;
$$;


ALTER FUNCTION storage.add_prefixes(_bucket_id text, _name text) OWNER TO supabase_storage_admin;

--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


ALTER FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) OWNER TO supabase_storage_admin;

--
-- Name: delete_leaf_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_leaf_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_rows_deleted integer;
BEGIN
    LOOP
        WITH candidates AS (
            SELECT DISTINCT
                t.bucket_id,
                unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        ),
        uniq AS (
             SELECT
                 bucket_id,
                 name,
                 storage.get_level(name) AS level
             FROM candidates
             WHERE name <> ''
             GROUP BY bucket_id, name
        ),
        leaf AS (
             SELECT
                 p.bucket_id,
                 p.name,
                 p.level
             FROM storage.prefixes AS p
                  JOIN uniq AS u
                       ON u.bucket_id = p.bucket_id
                           AND u.name = p.name
                           AND u.level = p.level
             WHERE NOT EXISTS (
                 SELECT 1
                 FROM storage.objects AS o
                 WHERE o.bucket_id = p.bucket_id
                   AND o.level = p.level + 1
                   AND o.name COLLATE "C" LIKE p.name || '/%'
             )
             AND NOT EXISTS (
                 SELECT 1
                 FROM storage.prefixes AS c
                 WHERE c.bucket_id = p.bucket_id
                   AND c.level = p.level + 1
                   AND c.name COLLATE "C" LIKE p.name || '/%'
             )
        )
        DELETE
        FROM storage.prefixes AS p
            USING leaf AS l
        WHERE p.bucket_id = l.bucket_id
          AND p.name = l.name
          AND p.level = l.level;

        GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;
        EXIT WHEN v_rows_deleted = 0;
    END LOOP;
END;
$$;


ALTER FUNCTION storage.delete_leaf_prefixes(bucket_ids text[], names text[]) OWNER TO supabase_storage_admin;

--
-- Name: delete_prefix(text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_prefix(_bucket_id text, _name text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Check if we can delete the prefix
    IF EXISTS(
        SELECT FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name") + 1
          AND "prefixes"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    )
    OR EXISTS(
        SELECT FROM "storage"."objects"
        WHERE "objects"."bucket_id" = "_bucket_id"
          AND "storage"."get_level"("objects"."name") = "storage"."get_level"("_name") + 1
          AND "objects"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    ) THEN
    -- There are sub-objects, skip deletion
    RETURN false;
    ELSE
        DELETE FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name")
          AND "prefixes"."name" = "_name";
        RETURN true;
    END IF;
END;
$$;


ALTER FUNCTION storage.delete_prefix(_bucket_id text, _name text) OWNER TO supabase_storage_admin;

--
-- Name: delete_prefix_hierarchy_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_prefix_hierarchy_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    prefix text;
BEGIN
    prefix := "storage"."get_prefix"(OLD."name");

    IF coalesce(prefix, '') != '' THEN
        PERFORM "storage"."delete_prefix"(OLD."bucket_id", prefix);
    END IF;

    RETURN OLD;
END;
$$;


ALTER FUNCTION storage.delete_prefix_hierarchy_trigger() OWNER TO supabase_storage_admin;

--
-- Name: enforce_bucket_name_length(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.enforce_bucket_name_length() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
    if length(new.name) > 100 then
        raise exception 'bucket name "%" is too long (% characters). Max is 100.', new.name, length(new.name);
    end if;
    return new;
end;
$$;


ALTER FUNCTION storage.enforce_bucket_name_length() OWNER TO supabase_storage_admin;

--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
    _filename text;
BEGIN
    SELECT string_to_array(name, '/') INTO _parts;
    SELECT _parts[array_length(_parts,1)] INTO _filename;
    RETURN reverse(split_part(reverse(_filename), '.', 1));
END
$$;


ALTER FUNCTION storage.extension(name text) OWNER TO supabase_storage_admin;

--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


ALTER FUNCTION storage.filename(name text) OWNER TO supabase_storage_admin;

--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Return everything except the last segment
    RETURN _parts[1 : array_length(_parts,1) - 1];
END
$$;


ALTER FUNCTION storage.foldername(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_level(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_level(name text) RETURNS integer
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
SELECT array_length(string_to_array("name", '/'), 1);
$$;


ALTER FUNCTION storage.get_level(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_prefix(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_prefix(name text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $_$
SELECT
    CASE WHEN strpos("name", '/') > 0 THEN
             regexp_replace("name", '[\/]{1}[^\/]+\/?$', '')
         ELSE
             ''
        END;
$_$;


ALTER FUNCTION storage.get_prefix(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_prefixes(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_prefixes(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
DECLARE
    parts text[];
    prefixes text[];
    prefix text;
BEGIN
    -- Split the name into parts by '/'
    parts := string_to_array("name", '/');
    prefixes := '{}';

    -- Construct the prefixes, stopping one level below the last part
    FOR i IN 1..array_length(parts, 1) - 1 LOOP
            prefix := array_to_string(parts[1:i], '/');
            prefixes := array_append(prefixes, prefix);
    END LOOP;

    RETURN prefixes;
END;
$$;


ALTER FUNCTION storage.get_prefixes(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::bigint) as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


ALTER FUNCTION storage.get_size_by_bucket() OWNER TO supabase_storage_admin;

--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


ALTER FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text) OWNER TO supabase_storage_admin;

--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(name COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                        substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1)))
                    ELSE
                        name
                END AS name, id, metadata, updated_at
            FROM
                storage.objects
            WHERE
                bucket_id = $5 AND
                name ILIKE $1 || ''%'' AND
                CASE
                    WHEN $6 != '''' THEN
                    name COLLATE "C" > $6
                ELSE true END
                AND CASE
                    WHEN $4 != '''' THEN
                        CASE
                            WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                                substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                name COLLATE "C" > $4
                            END
                    ELSE
                        true
                END
            ORDER BY
                name COLLATE "C" ASC) as e order by name COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_token, bucket_id, start_after;
END;
$_$;


ALTER FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text) OWNER TO supabase_storage_admin;

--
-- Name: lock_top_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.lock_top_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket text;
    v_top text;
BEGIN
    FOR v_bucket, v_top IN
        SELECT DISTINCT t.bucket_id,
            split_part(t.name, '/', 1) AS top
        FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        WHERE t.name <> ''
        ORDER BY 1, 2
        LOOP
            PERFORM pg_advisory_xact_lock(hashtextextended(v_bucket || '/' || v_top, 0));
        END LOOP;
END;
$$;


ALTER FUNCTION storage.lock_top_prefixes(bucket_ids text[], names text[]) OWNER TO supabase_storage_admin;

--
-- Name: objects_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.objects_delete_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: objects_insert_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_insert_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    NEW.level := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_insert_prefix_trigger() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    -- NEW - OLD (destinations to create prefixes for)
    v_add_bucket_ids text[];
    v_add_names      text[];

    -- OLD - NEW (sources to prune)
    v_src_bucket_ids text[];
    v_src_names      text[];
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RETURN NULL;
    END IF;

    -- 1) Compute NEW−OLD (added paths) and OLD−NEW (moved-away paths)
    WITH added AS (
        SELECT n.bucket_id, n.name
        FROM new_rows n
        WHERE n.name <> '' AND position('/' in n.name) > 0
        EXCEPT
        SELECT o.bucket_id, o.name FROM old_rows o WHERE o.name <> ''
    ),
    moved AS (
         SELECT o.bucket_id, o.name
         FROM old_rows o
         WHERE o.name <> ''
         EXCEPT
         SELECT n.bucket_id, n.name FROM new_rows n WHERE n.name <> ''
    )
    SELECT
        -- arrays for ADDED (dest) in stable order
        COALESCE( (SELECT array_agg(a.bucket_id ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        COALESCE( (SELECT array_agg(a.name      ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        -- arrays for MOVED (src) in stable order
        COALESCE( (SELECT array_agg(m.bucket_id ORDER BY m.bucket_id, m.name) FROM moved m), '{}' ),
        COALESCE( (SELECT array_agg(m.name      ORDER BY m.bucket_id, m.name) FROM moved m), '{}' )
    INTO v_add_bucket_ids, v_add_names, v_src_bucket_ids, v_src_names;

    -- Nothing to do?
    IF (array_length(v_add_bucket_ids, 1) IS NULL) AND (array_length(v_src_bucket_ids, 1) IS NULL) THEN
        RETURN NULL;
    END IF;

    -- 2) Take per-(bucket, top) locks: ALL prefixes in consistent global order to prevent deadlocks
    DECLARE
        v_all_bucket_ids text[];
        v_all_names text[];
    BEGIN
        -- Combine source and destination arrays for consistent lock ordering
        v_all_bucket_ids := COALESCE(v_src_bucket_ids, '{}') || COALESCE(v_add_bucket_ids, '{}');
        v_all_names := COALESCE(v_src_names, '{}') || COALESCE(v_add_names, '{}');

        -- Single lock call ensures consistent global ordering across all transactions
        IF array_length(v_all_bucket_ids, 1) IS NOT NULL THEN
            PERFORM storage.lock_top_prefixes(v_all_bucket_ids, v_all_names);
        END IF;
    END;

    -- 3) Create destination prefixes (NEW−OLD) BEFORE pruning sources
    IF array_length(v_add_bucket_ids, 1) IS NOT NULL THEN
        WITH candidates AS (
            SELECT DISTINCT t.bucket_id, unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(v_add_bucket_ids, v_add_names) AS t(bucket_id, name)
            WHERE name <> ''
        )
        INSERT INTO storage.prefixes (bucket_id, name)
        SELECT c.bucket_id, c.name
        FROM candidates c
        ON CONFLICT DO NOTHING;
    END IF;

    -- 4) Prune source prefixes bottom-up for OLD−NEW
    IF array_length(v_src_bucket_ids, 1) IS NOT NULL THEN
        -- re-entrancy guard so DELETE on prefixes won't recurse
        IF current_setting('storage.gc.prefixes', true) <> '1' THEN
            PERFORM set_config('storage.gc.prefixes', '1', true);
        END IF;

        PERFORM storage.delete_leaf_prefixes(v_src_bucket_ids, v_src_names);
    END IF;

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.objects_update_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_level_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_level_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Set the new level
        NEW."level" := "storage"."get_level"(NEW."name");
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_update_level_trigger() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    old_prefixes TEXT[];
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Retrieve old prefixes
        old_prefixes := "storage"."get_prefixes"(OLD."name");

        -- Remove old prefixes that are only used by this object
        WITH all_prefixes as (
            SELECT unnest(old_prefixes) as prefix
        ),
        can_delete_prefixes as (
             SELECT prefix
             FROM all_prefixes
             WHERE NOT EXISTS (
                 SELECT 1 FROM "storage"."objects"
                 WHERE "bucket_id" = OLD."bucket_id"
                   AND "name" <> OLD."name"
                   AND "name" LIKE (prefix || '%')
             )
         )
        DELETE FROM "storage"."prefixes" WHERE name IN (SELECT prefix FROM can_delete_prefixes);

        -- Add new prefixes
        PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    END IF;
    -- Set the new level
    NEW."level" := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_update_prefix_trigger() OWNER TO supabase_storage_admin;

--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


ALTER FUNCTION storage.operation() OWNER TO supabase_storage_admin;

--
-- Name: prefixes_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.prefixes_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.prefixes_delete_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: prefixes_insert_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.prefixes_insert_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.prefixes_insert_trigger() OWNER TO supabase_storage_admin;

--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
declare
    can_bypass_rls BOOLEAN;
begin
    SELECT rolbypassrls
    INTO can_bypass_rls
    FROM pg_roles
    WHERE rolname = coalesce(nullif(current_setting('role', true), 'none'), current_user);

    IF can_bypass_rls THEN
        RETURN QUERY SELECT * FROM storage.search_v1_optimised(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    ELSE
        RETURN QUERY SELECT * FROM storage.search_legacy_v1(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    END IF;
end;
$$;


ALTER FUNCTION storage.search(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_legacy_v1(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_legacy_v1(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select path_tokens[$1] as folder
           from storage.objects
             where objects.name ilike $2 || $3 || ''%''
               and bucket_id = $4
               and array_length(objects.path_tokens, 1) <> $1
           group by folder
           order by folder ' || v_sort_order || '
     )
     (select folder as "name",
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[$1] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where objects.name ilike $2 || $3 || ''%''
       and bucket_id = $4
       and array_length(objects.path_tokens, 1) = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


ALTER FUNCTION storage.search_legacy_v1(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_v1_optimised(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_v1_optimised(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select (string_to_array(name, ''/''))[level] as name
           from storage.prefixes
             where lower(prefixes.name) like lower($2 || $3) || ''%''
               and bucket_id = $4
               and level = $1
           order by name ' || v_sort_order || '
     )
     (select name,
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[level] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where lower(objects.name) like lower($2 || $3) || ''%''
       and bucket_id = $4
       and level = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


ALTER FUNCTION storage.search_v1_optimised(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_v2(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer DEFAULT 100, levels integer DEFAULT 1, start_after text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text, sort_column text DEFAULT 'name'::text, sort_column_after text DEFAULT ''::text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    sort_col text;
    sort_ord text;
    cursor_op text;
    cursor_expr text;
    sort_expr text;
BEGIN
    -- Validate sort_order
    sort_ord := lower(sort_order);
    IF sort_ord NOT IN ('asc', 'desc') THEN
        sort_ord := 'asc';
    END IF;

    -- Determine cursor comparison operator
    IF sort_ord = 'asc' THEN
        cursor_op := '>';
    ELSE
        cursor_op := '<';
    END IF;
    
    sort_col := lower(sort_column);
    -- Validate sort column  
    IF sort_col IN ('updated_at', 'created_at') THEN
        cursor_expr := format(
            '($5 = '''' OR ROW(date_trunc(''milliseconds'', %I), name COLLATE "C") %s ROW(COALESCE(NULLIF($6, '''')::timestamptz, ''epoch''::timestamptz), $5))',
            sort_col, cursor_op
        );
        sort_expr := format(
            'COALESCE(date_trunc(''milliseconds'', %I), ''epoch''::timestamptz) %s, name COLLATE "C" %s',
            sort_col, sort_ord, sort_ord
        );
    ELSE
        cursor_expr := format('($5 = '''' OR name COLLATE "C" %s $5)', cursor_op);
        sort_expr := format('name COLLATE "C" %s', sort_ord);
    END IF;

    RETURN QUERY EXECUTE format(
        $sql$
        SELECT * FROM (
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    NULL::uuid AS id,
                    updated_at,
                    created_at,
                    NULL::timestamptz AS last_accessed_at,
                    NULL::jsonb AS metadata
                FROM storage.prefixes
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
            UNION ALL
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    id,
                    updated_at,
                    created_at,
                    last_accessed_at,
                    metadata
                FROM storage.objects
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
        ) obj
        ORDER BY %s
        LIMIT $3
        $sql$,
        cursor_expr,    -- prefixes WHERE
        sort_expr,      -- prefixes ORDER BY
        cursor_expr,    -- objects WHERE
        sort_expr,      -- objects ORDER BY
        sort_expr       -- final ORDER BY
    )
    USING prefix, bucket_name, limits, levels, start_after, sort_column_after;
END;
$_$;


ALTER FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer, levels integer, start_after text, sort_order text, sort_column text, sort_column_after text) OWNER TO supabase_storage_admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


ALTER FUNCTION storage.update_updated_at_column() OWNER TO supabase_storage_admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE auth.audit_log_entries OWNER TO supabase_auth_admin;

--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text NOT NULL,
    code_challenge_method auth.code_challenge_method NOT NULL,
    code_challenge text NOT NULL,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone
);


ALTER TABLE auth.flow_state OWNER TO supabase_auth_admin;

--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.flow_state IS 'stores metadata for pkce logins';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE auth.identities OWNER TO supabase_auth_admin;

--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE auth.instances OWNER TO supabase_auth_admin;

--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


ALTER TABLE auth.mfa_amr_claims OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


ALTER TABLE auth.mfa_challenges OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid,
    last_webauthn_challenge_data jsonb
);


ALTER TABLE auth.mfa_factors OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: COLUMN mfa_factors.last_webauthn_challenge_data; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.mfa_factors.last_webauthn_challenge_data IS 'Stores the latest WebAuthn challenge data including attestation/assertion for customer verification';


--
-- Name: oauth_authorizations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_authorizations (
    id uuid NOT NULL,
    authorization_id text NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    redirect_uri text NOT NULL,
    scope text NOT NULL,
    state text,
    resource text,
    code_challenge text,
    code_challenge_method auth.code_challenge_method,
    response_type auth.oauth_response_type DEFAULT 'code'::auth.oauth_response_type NOT NULL,
    status auth.oauth_authorization_status DEFAULT 'pending'::auth.oauth_authorization_status NOT NULL,
    authorization_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:03:00'::interval) NOT NULL,
    approved_at timestamp with time zone,
    nonce text,
    CONSTRAINT oauth_authorizations_authorization_code_length CHECK ((char_length(authorization_code) <= 255)),
    CONSTRAINT oauth_authorizations_code_challenge_length CHECK ((char_length(code_challenge) <= 128)),
    CONSTRAINT oauth_authorizations_expires_at_future CHECK ((expires_at > created_at)),
    CONSTRAINT oauth_authorizations_nonce_length CHECK ((char_length(nonce) <= 255)),
    CONSTRAINT oauth_authorizations_redirect_uri_length CHECK ((char_length(redirect_uri) <= 2048)),
    CONSTRAINT oauth_authorizations_resource_length CHECK ((char_length(resource) <= 2048)),
    CONSTRAINT oauth_authorizations_scope_length CHECK ((char_length(scope) <= 4096)),
    CONSTRAINT oauth_authorizations_state_length CHECK ((char_length(state) <= 4096))
);


ALTER TABLE auth.oauth_authorizations OWNER TO supabase_auth_admin;

--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_secret_hash text,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    client_type auth.oauth_client_type DEFAULT 'confidential'::auth.oauth_client_type NOT NULL,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048))
);


ALTER TABLE auth.oauth_clients OWNER TO supabase_auth_admin;

--
-- Name: oauth_consents; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    client_id uuid NOT NULL,
    scopes text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT oauth_consents_revoked_after_granted CHECK (((revoked_at IS NULL) OR (revoked_at >= granted_at))),
    CONSTRAINT oauth_consents_scopes_length CHECK ((char_length(scopes) <= 2048)),
    CONSTRAINT oauth_consents_scopes_not_empty CHECK ((char_length(TRIM(BOTH FROM scopes)) > 0))
);


ALTER TABLE auth.oauth_consents OWNER TO supabase_auth_admin;

--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


ALTER TABLE auth.one_time_tokens OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


ALTER TABLE auth.refresh_tokens OWNER TO supabase_auth_admin;

--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: supabase_auth_admin
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE auth.refresh_tokens_id_seq OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: supabase_auth_admin
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


ALTER TABLE auth.saml_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


ALTER TABLE auth.saml_relay_states OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


ALTER TABLE auth.schema_migrations OWNER TO supabase_auth_admin;

--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text,
    oauth_client_id uuid,
    refresh_token_hmac_key text,
    refresh_token_counter bigint,
    scopes text,
    CONSTRAINT sessions_scopes_length CHECK ((char_length(scopes) <= 4096))
);


ALTER TABLE auth.sessions OWNER TO supabase_auth_admin;

--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: COLUMN sessions.refresh_token_hmac_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.refresh_token_hmac_key IS 'Holds a HMAC-SHA256 key used to sign refresh tokens for this session.';


--
-- Name: COLUMN sessions.refresh_token_counter; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.refresh_token_counter IS 'Holds the ID (counter) of the last issued refresh token.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


ALTER TABLE auth.sso_domains OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


ALTER TABLE auth.sso_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


ALTER TABLE auth.users OWNER TO supabase_auth_admin;

--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: child; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.child (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    grade integer NOT NULL,
    created_at timestamp without time zone,
    cumulative_points integer,
    include_in_stats boolean
);


ALTER TABLE public.child OWNER TO postgres;

--
-- Name: child_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.child_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.child_id_seq OWNER TO postgres;

--
-- Name: child_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.child_id_seq OWNED BY public.child.id;


--
-- Name: child_note; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.child_note (
    id integer NOT NULL,
    child_id integer NOT NULL,
    note text NOT NULL,
    created_by integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.child_note OWNER TO postgres;

--
-- Name: child_note_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.child_note_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.child_note_id_seq OWNER TO postgres;

--
-- Name: child_note_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.child_note_id_seq OWNED BY public.child_note.id;


--
-- Name: daily_points; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.daily_points (
    id integer NOT NULL,
    child_id integer NOT NULL,
    date date NOT NULL,
    korean_points integer,
    math_points integer,
    ssen_points integer,
    reading_points integer,
    piano_points integer,
    english_points integer,
    advanced_math_points integer,
    writing_points integer,
    manual_points integer,
    manual_history text,
    total_points integer,
    created_by integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.daily_points OWNER TO postgres;

--
-- Name: daily_points_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.daily_points_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_points_id_seq OWNER TO postgres;

--
-- Name: daily_points_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.daily_points_id_seq OWNED BY public.daily_points.id;


--
-- Name: learning_record; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.learning_record (
    id integer NOT NULL,
    child_id integer NOT NULL,
    date date NOT NULL,
    korean_problems_solved integer,
    korean_problems_correct integer,
    korean_score double precision,
    korean_last_page integer,
    math_problems_solved integer,
    math_problems_correct integer,
    math_score double precision,
    math_last_page integer,
    reading_completed boolean,
    reading_score double precision,
    total_score double precision,
    created_by integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.learning_record OWNER TO postgres;

--
-- Name: learning_record_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.learning_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.learning_record_id_seq OWNER TO postgres;

--
-- Name: learning_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.learning_record_id_seq OWNED BY public.learning_record.id;


--
-- Name: notification; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notification (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    message text NOT NULL,
    type character varying(30),
    priority integer,
    target_user_id integer,
    target_role character varying(30),
    child_id integer,
    is_read boolean,
    is_active boolean,
    auto_expire boolean,
    expire_date timestamp without time zone,
    created_at timestamp without time zone,
    created_by integer NOT NULL,
    read_at timestamp without time zone
);


ALTER TABLE public.notification OWNER TO postgres;

--
-- Name: notification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notification_id_seq OWNER TO postgres;

--
-- Name: notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notification_id_seq OWNED BY public.notification.id;


--
-- Name: points_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.points_history (
    id integer NOT NULL,
    child_id integer NOT NULL,
    date date NOT NULL,
    old_korean_points integer,
    old_math_points integer,
    old_ssen_points integer,
    old_reading_points integer,
    old_total_points integer,
    old_piano_points integer,
    old_english_points integer,
    old_advanced_math_points integer,
    old_writing_points integer,
    new_korean_points integer,
    new_math_points integer,
    new_ssen_points integer,
    new_reading_points integer,
    new_total_points integer,
    new_piano_points integer,
    new_english_points integer,
    new_advanced_math_points integer,
    new_writing_points integer,
    change_type character varying(20),
    changed_by integer NOT NULL,
    changed_at timestamp without time zone,
    change_reason character varying(200)
);


ALTER TABLE public.points_history OWNER TO postgres;

--
-- Name: points_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.points_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.points_history_id_seq OWNER TO postgres;

--
-- Name: points_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.points_history_id_seq OWNED BY public.points_history.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    username character varying(80),
    password_hash character varying(255),
    name character varying(100) NOT NULL,
    role character varying(50) NOT NULL,
    created_at timestamp without time zone,
    login_attempts integer,
    last_attempt timestamp without time zone,
    is_locked boolean,
    locked_until timestamp without time zone,
    email character varying(120),
    firebase_uid character varying(128)
);


ALTER TABLE public."user" OWNER TO postgres;

--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_id_seq OWNER TO postgres;

--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
)
PARTITION BY RANGE (inserted_at);


ALTER TABLE realtime.messages OWNER TO supabase_realtime_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE realtime.schema_migrations OWNER TO supabase_admin;

--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


ALTER TABLE realtime.subscription OWNER TO supabase_admin;

--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text,
    type storage.buckettype DEFAULT 'STANDARD'::storage.buckettype NOT NULL
);


ALTER TABLE storage.buckets OWNER TO supabase_storage_admin;

--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: buckets_analytics; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets_analytics (
    id text NOT NULL,
    type storage.buckettype DEFAULT 'ANALYTICS'::storage.buckettype NOT NULL,
    format text DEFAULT 'ICEBERG'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.buckets_analytics OWNER TO supabase_storage_admin;

--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE storage.migrations OWNER TO supabase_storage_admin;

--
-- Name: objects; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb,
    level integer
);


ALTER TABLE storage.objects OWNER TO supabase_storage_admin;

--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: prefixes; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.prefixes (
    bucket_id text NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    level integer GENERATED ALWAYS AS (storage.get_level(name)) STORED NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE storage.prefixes OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb
);


ALTER TABLE storage.s3_multipart_uploads OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.s3_multipart_uploads_parts OWNER TO supabase_storage_admin;

--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: child id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child ALTER COLUMN id SET DEFAULT nextval('public.child_id_seq'::regclass);


--
-- Name: child_note id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child_note ALTER COLUMN id SET DEFAULT nextval('public.child_note_id_seq'::regclass);


--
-- Name: daily_points id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_points ALTER COLUMN id SET DEFAULT nextval('public.daily_points_id_seq'::regclass);


--
-- Name: learning_record id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_record ALTER COLUMN id SET DEFAULT nextval('public.learning_record_id_seq'::regclass);


--
-- Name: notification id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification ALTER COLUMN id SET DEFAULT nextval('public.notification_id_seq'::regclass);


--
-- Name: points_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.points_history ALTER COLUMN id SET DEFAULT nextval('public.points_history_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.audit_log_entries (instance_id, id, payload, created_at, ip_address) FROM stdin;
\.


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.flow_state (id, user_id, auth_code, code_challenge_method, code_challenge, provider_type, provider_access_token, provider_refresh_token, created_at, updated_at, authentication_method, auth_code_issued_at) FROM stdin;
\.


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at, id) FROM stdin;
\.


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.instances (id, uuid, raw_base_config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_amr_claims (session_id, created_at, updated_at, authentication_method, id) FROM stdin;
\.


--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_challenges (id, factor_id, created_at, verified_at, ip_address, otp_code, web_authn_session_data) FROM stdin;
\.


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_factors (id, user_id, friendly_name, factor_type, status, created_at, updated_at, secret, phone, last_challenged_at, web_authn_credential, web_authn_aaguid, last_webauthn_challenge_data) FROM stdin;
\.


--
-- Data for Name: oauth_authorizations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_authorizations (id, authorization_id, client_id, user_id, redirect_uri, scope, state, resource, code_challenge, code_challenge_method, response_type, status, authorization_code, created_at, expires_at, approved_at, nonce) FROM stdin;
\.


--
-- Data for Name: oauth_clients; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_clients (id, client_secret_hash, registration_type, redirect_uris, grant_types, client_name, client_uri, logo_uri, created_at, updated_at, deleted_at, client_type) FROM stdin;
\.


--
-- Data for Name: oauth_consents; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_consents (id, user_id, client_id, scopes, granted_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.one_time_tokens (id, user_id, token_type, token_hash, relates_to, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.refresh_tokens (instance_id, id, token, user_id, revoked, created_at, updated_at, parent, session_id) FROM stdin;
\.


--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_providers (id, sso_provider_id, entity_id, metadata_xml, metadata_url, attribute_mapping, created_at, updated_at, name_id_format) FROM stdin;
\.


--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_relay_states (id, sso_provider_id, request_id, for_email, redirect_to, created_at, updated_at, flow_state_id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.schema_migrations (version) FROM stdin;
20171026211738
20171026211808
20171026211834
20180103212743
20180108183307
20180119214651
20180125194653
00
20210710035447
20210722035447
20210730183235
20210909172000
20210927181326
20211122151130
20211124214934
20211202183645
20220114185221
20220114185340
20220224000811
20220323170000
20220429102000
20220531120530
20220614074223
20220811173540
20221003041349
20221003041400
20221011041400
20221020193600
20221021073300
20221021082433
20221027105023
20221114143122
20221114143410
20221125140132
20221208132122
20221215195500
20221215195800
20221215195900
20230116124310
20230116124412
20230131181311
20230322519590
20230402418590
20230411005111
20230508135423
20230523124323
20230818113222
20230914180801
20231027141322
20231114161723
20231117164230
20240115144230
20240214120130
20240306115329
20240314092811
20240427152123
20240612123726
20240729123726
20240802193726
20240806073726
20241009103726
20250717082212
20250731150234
20250804100000
20250901200500
20250903112500
20250904133000
20250925093508
20251007112900
20251104100000
20251111201300
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sessions (id, user_id, created_at, updated_at, factor_id, aal, not_after, refreshed_at, user_agent, ip, tag, oauth_client_id, refresh_token_hmac_key, refresh_token_counter, scopes) FROM stdin;
\.


--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_domains (id, sso_provider_id, domain, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_providers (id, resource_id, created_at, updated_at, disabled) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, invited_at, confirmation_token, confirmation_sent_at, recovery_token, recovery_sent_at, email_change_token_new, email_change, email_change_sent_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at, phone, phone_confirmed_at, phone_change, phone_change_token, phone_change_sent_at, email_change_token_current, email_change_confirm_status, banned_until, reauthentication_token, reauthentication_sent_at, is_sso_user, deleted_at, is_anonymous) FROM stdin;
\.


--
-- Data for Name: child; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.child (id, name, grade, created_at, cumulative_points, include_in_stats) FROM stdin;
44	이쁜이	4	2025-09-30 05:32:36.84065	39200	t
37	예나비	3	2025-09-30 05:32:36.84065	8200	t
50	토끼야	4	2025-09-30 05:32:36.84165	35500	t
55	태이프	6	2025-09-30 05:32:36.842649	5800	t
41	하늘이	3	2025-09-30 05:32:36.84065	37100	t
52	빡빡이	5	2025-09-30 05:32:36.84165	26900	t
36	핸드폰	2	2025-09-30 05:32:36.839622	15600	t
58	감스트	6	2025-09-30 05:32:36.842649	1900	t
42	먹대장	3	2025-09-30 05:32:36.84065	11400	t
56	머스크	6	2025-09-30 05:32:36.842649	10000	t
34	탕수육	2	2025-09-30 05:32:36.839622	30500	t
39	여고생	3	2025-09-30 05:32:36.84065	13500	t
51	베트남	5	2025-09-30 05:32:36.84165	8700	t
49	우라늄	4	2025-09-30 05:32:36.84165	27900	t
46	누룽지	4	2025-09-30 05:32:36.84065	49100	t
45	말랑이	4	2025-09-30 05:32:36.84065	35300	t
35	쫄라맨	2	2025-09-30 05:32:36.839622	56300	t
47	최씨군	4	2025-09-30 05:32:36.84165	26000	t
32	양양이	1	2025-09-30 05:32:36.839622	73200	t
48	포차코	4	2025-09-30 05:32:36.84165	43100	t
54	우등생	5	2025-09-30 05:32:36.842649	32100	t
53	민수르	5	2025-09-30 05:32:36.84165	2900	t
59	두목찡	6	2025-09-30 05:32:36.842649	53400	t
33	도마뱀	1	2025-09-30 05:32:36.839622	56600	t
43	짜장면	3	2025-09-30 05:32:36.84065	57300	t
40	노진구	3	2025-09-30 05:32:36.84065	48800	t
57	나이키	6	2025-09-30 05:32:36.842649	15300	t
31	돌고래	1	2025-09-30 05:32:36.755614	73700	t
38	베이비	3	2025-09-30 05:32:36.84065	16000	t
\.


--
-- Data for Name: child_note; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.child_note (id, child_id, note, created_by, created_at, updated_at) FROM stdin;
4	53	10/10 쎈 10쪽 풀음	1	2025-10-10 03:54:15.069612	2025-10-10 03:54:15.069614
5	38	요즘 열심히 진도 나가고 있어서 조만간 친구들이랑 진도 비슷해질것 같습니다.	1	2025-10-14 08:18:35.283461	2025-10-14 08:18:35.283463
7	37	학습태도가 가장 좋은날이었습니다	6	2025-10-16 08:29:00.431288	2025-10-16 08:29:00.431291
9	38	요새 계속 늦게오고 학습 의지가 떨어집니다(공부할시간 길어야 30분)	1	2025-11-04 07:47:49.805014	2025-11-04 07:47:49.805016
\.


--
-- Data for Name: daily_points; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.daily_points (id, child_id, date, korean_points, math_points, ssen_points, reading_points, piano_points, english_points, advanced_math_points, writing_points, manual_points, manual_history, total_points, created_by, created_at, updated_at) FROM stdin;
726	59	2025-10-01	0	0	0	0	0	0	0	0	0	[]	35900	1	2025-10-02 06:38:53.947319	2025-10-02 06:38:53.94732
727	59	2025-10-02	100	0	100	200	0	0	300	0	0	[]	700	1	2025-10-02 06:39:19.806971	2025-10-02 06:39:19.806974
728	48	2025-10-01	0	0	0	0	0	0	0	0	0	[]	25800	1	2025-10-02 06:50:23.938282	2025-10-02 06:50:23.938282
729	48	2025-10-02	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-02 06:51:25.705535	2025-10-02 06:51:26.578012
730	49	2025-10-01	0	0	0	0	0	0	0	0	0	[]	15800	1	2025-10-02 06:53:06.023352	2025-10-02 06:53:06.023352
731	49	2025-10-02	200	200	100	0	0	0	0	0	0	[]	500	1	2025-10-02 06:53:29.4779	2025-10-02 06:53:29.477902
732	32	2025-10-01	0	0	0	0	0	0	0	0	0	[]	46500	1	2025-10-02 08:05:11.269923	2025-10-02 08:05:11.269923
733	32	2025-10-02	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-02 08:05:48.778165	2025-10-02 08:05:48.778169
734	43	2025-10-01	0	0	0	0	0	0	0	0	0	[]	33700	1	2025-10-02 08:14:36.394544	2025-10-02 08:14:36.394545
735	43	2025-10-02	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-02 08:15:05.101175	2025-10-02 08:15:06.40955
736	40	2025-10-01	0	0	0	0	0	0	0	0	0	[]	28300	1	2025-10-02 08:17:53.892522	2025-10-02 08:17:53.892522
737	40	2025-10-02	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-02 08:18:27.207657	2025-10-02 08:18:27.20766
738	50	2025-10-01	0	0	0	0	0	0	0	0	0	[]	22100	1	2025-10-02 08:21:58.591279	2025-10-02 08:21:58.591279
739	50	2025-10-02	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-02 08:22:29.684663	2025-10-02 08:22:29.684666
740	38	2025-10-01	0	0	0	0	0	0	0	0	0	[]	8800	1	2025-10-02 08:24:15.423646	2025-10-02 08:24:15.423646
741	38	2025-10-02	100	100	100	200	0	0	0	0	200	[{"id": 1, "subject": "추가포인트", "points": 200, "reason": "열심히 수학", "created_by": "dev_hoon", "created_at": "2025-10-02 08:25:06"}]	700	1	2025-10-02 08:24:39.692099	2025-10-02 08:25:06.268288
742	45	2025-10-01	0	0	0	0	0	0	0	0	0	[]	20100	1	2025-10-02 08:25:50.445782	2025-10-02 08:25:50.445782
743	45	2025-10-02	100	100	100	100	0	0	0	0	0	[]	400	1	2025-10-02 08:26:56.574527	2025-10-02 08:26:56.574529
744	54	2025-10-01	0	0	0	0	0	0	0	0	0	[]	18000	1	2025-10-02 08:32:11.394363	2025-10-02 08:32:11.394364
745	54	2025-10-02	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-02 08:32:52.222705	2025-10-02 08:32:52.222709
746	39	2025-10-01	0	0	0	0	0	0	0	0	0	[]	4600	1	2025-10-02 08:42:17.8013	2025-10-02 08:42:17.801301
747	39	2025-10-02	100	100	0	0	0	0	0	0	0	[]	200	1	2025-10-02 08:42:31.514056	2025-10-02 08:42:31.514058
748	46	2025-10-01	0	0	0	0	0	0	0	0	0	[]	30500	1	2025-10-02 08:44:29.356543	2025-10-02 08:44:29.356543
749	46	2025-10-02	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-02 08:45:00.615127	2025-10-02 08:45:00.615129
750	44	2025-10-01	0	0	0	0	0	0	0	0	0	[]	26700	1	2025-10-02 08:46:43.353092	2025-10-02 08:46:43.353092
751	44	2025-10-02	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-02 08:47:13.766061	2025-10-02 08:47:13.766066
752	47	2025-10-01	0	0	0	0	0	0	0	0	0	[]	15000	1	2025-10-02 08:50:21.26604	2025-10-02 08:50:21.26604
753	47	2025-10-02	100	100	100	100	0	0	0	0	0	[]	400	1	2025-10-02 08:50:55.477293	2025-10-02 08:50:55.477295
754	53	2025-10-09	0	0	0	0	0	0	0	0	0	[]	1600	1	2025-10-10 01:49:14.113923	2025-10-10 01:49:14.113923
756	35	2025-10-09	0	0	0	0	0	0	0	0	0	[]	37000	1	2025-10-10 03:26:40.981554	2025-10-10 03:26:40.981554
757	35	2025-10-10	100	200	100	200	0	0	0	100	0	[]	700	1	2025-10-10 03:27:14.36215	2025-10-10 03:27:14.362153
758	36	2025-10-09	0	0	0	0	0	0	0	0	0	[]	10700	1	2025-10-10 03:42:25.779816	2025-10-10 03:42:25.779816
759	36	2025-10-10	100	200	100	200	0	0	0	100	0	[]	700	1	2025-10-10 03:44:56.836349	2025-10-10 03:44:56.836352
760	58	2025-10-09	0	0	0	0	0	0	0	0	0	[]	1500	1	2025-10-10 03:47:44.57148	2025-10-10 03:47:44.571481
761	58	2025-10-10	100	0	100	200	0	0	0	0	0	[]	400	1	2025-10-10 03:48:08.808365	2025-10-10 03:48:08.808368
762	45	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 03:53:11.984857	2025-10-10 03:53:11.98486
779	31	2025-10-09	0	0	0	0	0	0	0	0	0	[]	44300	1	2025-10-10 08:28:14.598626	2025-10-10 08:28:14.598626
755	53	2025-10-10	200	100	100	200	0	0	0	0	700	[{"id": 1, "subject": "연필", "points": -300, "reason": "연필 구매", "created_by": "dev_hoon", "created_at": "2025-10-10 01:50:04"}, {"id": 2, "subject": "추가포인트", "points": 1000, "reason": "열심히 수학&쎈", "created_by": "dev_hoon", "created_at": "2025-10-10 05:00:21"}]	1300	1	2025-10-10 01:50:04.02363	2025-10-10 05:00:21.373584
763	33	2025-10-09	0	0	0	0	0	0	0	0	0	[]	36200	1	2025-10-10 05:07:48.55011	2025-10-10 05:07:48.550111
764	40	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 06:27:48.045936	2025-10-10 06:27:48.045939
765	51	2025-10-09	0	0	0	0	0	0	0	0	0	[]	7600	1	2025-10-10 06:59:55.457331	2025-10-10 06:59:55.457331
766	51	2025-10-10	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-10 07:00:34.661698	2025-10-10 07:00:34.661701
767	50	2025-10-10	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-10 07:05:57.807004	2025-10-10 07:05:57.807009
768	57	2025-10-09	0	0	0	0	0	0	0	0	0	[]	15000	1	2025-10-10 07:07:37.458042	2025-10-10 07:07:37.458043
769	57	2025-10-10	200	0	100	0	0	0	0	0	0	[]	300	1	2025-10-10 07:07:55.102244	2025-10-10 07:07:55.102247
770	37	2025-10-09	0	0	0	0	0	0	0	0	0	[]	4300	1	2025-10-10 07:26:25.034082	2025-10-10 07:26:25.034083
771	43	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 07:28:01.948819	2025-10-10 07:28:01.948824
772	52	2025-10-09	0	0	0	0	0	0	0	0	0	[]	25000	1	2025-10-10 07:35:08.791402	2025-10-10 07:35:08.791402
773	52	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 07:35:34.856221	2025-10-10 07:35:34.856224
774	41	2025-10-09	0	0	0	0	0	0	0	0	0	[]	26300	1	2025-10-10 07:43:52.002597	2025-10-10 07:43:52.002598
775	44	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 07:44:40.915676	2025-10-10 07:44:40.915679
776	54	2025-10-10	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-10 08:01:56.669067	2025-10-10 08:01:56.66907
777	38	2025-10-10	200	100	100	100	0	0	0	0	300	[{"id": 1, "subject": "추가포인트", "points": 300, "reason": "열심히 수학", "created_by": "dev_hoon", "created_at": "2025-10-10 08:13:14"}]	800	1	2025-10-10 08:12:43.548171	2025-10-10 08:13:14.274541
778	48	2025-10-10	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-10 08:16:09.833758	2025-10-10 08:16:09.833761
780	31	2025-10-10	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-10 08:28:43.582009	2025-10-10 08:28:43.582012
781	55	2025-10-09	0	0	0	0	0	0	0	0	0	[]	5800	1	2025-10-10 08:31:58.932114	2025-10-10 08:31:58.932114
782	56	2025-10-09	0	0	0	0	0	0	0	0	0	[]	9500	1	2025-10-10 08:32:22.876886	2025-10-10 08:32:22.876887
787	32	2025-10-13	200	200	100	200	100	0	0	100	0	[]	900	1	2025-10-13 07:03:43.80015	2025-10-13 07:03:43.800152
785	49	2025-10-13	200	200	100	200	0	0	0	0	0	[]	700	1	2025-10-13 06:19:23.553244	2025-10-13 06:19:23.553246
786	35	2025-10-13	200	200	100	200	100	0	0	100	0	[]	900	1	2025-10-13 06:55:01.121861	2025-10-13 06:55:01.121863
788	59	2025-10-13	200	0	100	200	100	0	0	0	0	[]	600	1	2025-10-13 07:46:44.215305	2025-10-13 07:46:44.215308
789	40	2025-10-13	100	100	100	200	100	0	0	0	-200	[{"id": 1, "subject": "테이프", "points": -200, "reason": "테이프 구매", "created_by": "dev_hoon", "created_at": "2025-10-13 08:13:36"}]	400	1	2025-10-13 08:13:36.08601	2025-10-13 08:14:03.36949
790	48	2025-10-13	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-13 08:15:00.096527	2025-10-13 08:15:00.096529
791	46	2025-10-13	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-13 08:16:00.416475	2025-10-13 08:16:00.416479
792	38	2025-10-13	200	100	100	100	100	0	0	0	0	[]	600	1	2025-10-13 08:28:14.497899	2025-10-13 08:28:14.497903
793	44	2025-10-13	200	100	100	200	100	0	0	0	0	[]	700	1	2025-10-13 08:32:09.467283	2025-10-13 08:32:09.467287
794	54	2025-10-13	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-13 08:32:55.823213	2025-10-13 08:32:55.823217
795	45	2025-10-13	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-13 08:52:08.574775	2025-10-13 08:52:08.574777
796	31	2025-10-14	200	200	100	200	0	100	0	100	0	[]	900	5	2025-10-14 06:53:57.643241	2025-10-14 06:53:57.643245
797	40	2025-10-14	100	200	100	200	0	100	0	0	-300	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선 구매", "created_by": "dev_hoon", "created_at": "2025-10-14 07:44:15"}]	400	1	2025-10-14 07:43:40.034139	2025-10-14 07:44:15.781487
798	35	2025-10-14	100	100	100	200	0	100	0	100	0	[]	700	5	2025-10-14 07:57:26.915781	2025-10-14 07:57:26.915785
799	46	2025-10-14	200	100	100	200	0	100	0	0	0	[]	700	6	2025-10-14 07:58:47.769944	2025-10-14 07:58:47.769948
800	32	2025-10-14	200	200	100	200	0	100	0	100	-300	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선구매", "created_by": "teacher", "created_at": "2025-10-14 08:02:53"}]	600	6	2025-10-14 08:02:53.089613	2025-10-14 08:03:48.760463
801	43	2025-10-14	100	100	100	200	0	100	0	0	0	[]	600	5	2025-10-14 08:04:01.159811	2025-10-14 08:04:01.159815
802	38	2025-10-14	200	100	100	100	0	100	0	0	0	[]	600	1	2025-10-14 08:08:19.021916	2025-10-14 08:08:19.02192
803	45	2025-10-14	200	100	100	200	0	100	0	0	-300	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선구매", "created_by": "teacher", "created_at": "2025-10-14 08:16:45"}]	400	6	2025-10-14 08:15:35.986756	2025-10-14 08:16:45.854489
804	47	2025-10-14	100	100	100	200	0	100	0	0	0	[]	600	6	2025-10-14 08:20:00.391421	2025-10-14 08:20:00.391425
805	58	2025-10-14	0	0	0	0	0	0	0	0	0	[]	0	6	2025-10-14 08:25:25.351622	2025-10-14 08:25:25.351626
808	59	2025-10-14	200	0	100	100	0	100	300	0	0	[]	800	5	2025-10-14 08:40:54.388822	2025-10-14 08:40:54.388826
809	33	2025-10-14	200	200	100	200	0	100	0	100	0	[]	900	1	2025-10-14 08:42:32.900668	2025-10-14 08:42:32.900672
810	48	2025-10-14	100	100	100	200	0	100	0	0	0	[]	600	5	2025-10-14 08:46:16.528241	2025-10-14 08:46:16.528246
811	37	2025-10-14	100	100	100	100	0	100	0	0	500	[{"id": 1, "subject": "10/10 포인트", "points": 500, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-14 08:52:21"}]	1000	5	2025-10-14 08:49:15.952554	2025-10-14 08:52:21.228466
813	40	2025-10-15	200	200	0	200	0	0	0	0	0	[]	600	1	2025-10-15 05:02:00.734366	2025-10-15 05:02:00.734369
814	35	2025-10-15	0	0	0	200	0	0	0	100	0	[]	300	5	2025-10-15 05:10:31.708239	2025-10-15 05:10:31.708243
829	49	2025-10-16	200	100	100	0	0	0	0	0	100	[{"id": 1, "subject": "추가학습", "points": 100, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-10-16 06:35:35"}]	500	6	2025-10-16 06:35:35.533853	2025-10-16 06:36:07.641251
812	31	2025-10-15	200	200	100	200	0	0	0	100	600	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선 구매", "created_by": "dev_hoon", "created_at": "2025-10-15 05:14:09"}, {"id": 2, "subject": "10/13 포인트", "points": 900, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-15 05:19:39"}]	1400	1	2025-10-15 04:54:38.821276	2025-10-15 05:19:39.647247
830	40	2025-10-16	100	100	100	200	0	0	0	0	0	[]	500	1	2025-10-16 06:45:35.802519	2025-10-16 06:45:35.802522
816	59	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	5	2025-10-15 05:47:22.639787	2025-10-15 05:47:22.639791
815	43	2025-10-15	100	100	0	200	0	0	0	0	400	[{"id": 1, "subject": "10/13 포인트", "points": 700, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-15 05:37:10"}, {"id": 2, "subject": "풍선", "points": -300, "reason": "풍선 구매", "created_by": "dev_hoon", "created_at": "2025-10-15 05:37:41"}]	800	1	2025-10-15 05:37:10.631784	2025-10-15 05:51:39.359893
817	52	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-15 07:37:36.339291	2025-10-15 07:37:36.339294
818	48	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	6	2025-10-15 07:48:00.138595	2025-10-15 07:48:00.138597
819	45	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	5	2025-10-15 07:53:18.123798	2025-10-15 07:53:18.123801
820	46	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	6	2025-10-15 07:56:37.035655	2025-10-15 07:56:37.035658
821	47	2025-10-15	100	100	0	0	0	0	0	0	0	[]	200	1	2025-10-15 07:57:51.045866	2025-10-15 07:57:51.045868
822	38	2025-10-15	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-15 08:02:30.436838	2025-10-15 08:02:30.43684
823	32	2025-10-15	200	0	0	200	0	0	0	0	-300	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선 구매", "created_by": "dev_hoon", "created_at": "2025-10-15 08:04:11"}]	100	1	2025-10-15 08:04:11.049673	2025-10-15 08:05:05.854469
824	44	2025-10-15	100	200	0	0	0	0	0	0	0	[]	300	5	2025-10-15 08:19:07.797335	2025-10-15 08:19:07.797339
831	46	2025-10-16	100	0	100	200	0	0	0	0	0	[]	400	5	2025-10-16 06:46:02.722769	2025-10-16 06:46:02.722771
832	48	2025-10-16	200	100	100	200	0	0	0	0	0	[]	600	6	2025-10-16 07:04:04.169433	2025-10-16 07:04:04.169437
833	36	2025-10-16	200	100	100	0	0	0	0	0	0	[]	400	5	2025-10-16 07:52:12.366469	2025-10-16 07:52:12.366472
825	54	2025-10-15	0	0	0	200	0	0	0	0	0	[]	200	5	2025-10-15 08:26:08.123213	2025-10-15 08:26:12.171768
826	39	2025-10-15	0	100	100	0	0	0	0	0	0	[]	200	6	2025-10-15 08:31:47.025905	2025-10-15 08:31:47.025908
827	37	2025-10-15	0	100	100	0	0	0	0	0	0	[]	200	6	2025-10-15 08:33:38.50694	2025-10-15 08:33:38.506942
828	34	2025-10-14	0	0	0	0	0	0	0	0	0	[]	22200	1	2025-10-15 08:54:03.354538	2025-10-15 08:54:03.354538
834	44	2025-10-16	200	100	100	0	0	0	0	0	100	[{"id": 1, "subject": "5-1 수학", "points": 100, "reason": "5-1 수학", "created_by": "sowo_1", "created_at": "2025-10-16 07:59:41"}]	500	5	2025-10-16 07:59:41.46198	2025-10-16 07:59:47.601861
837	54	2025-10-16	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-16 08:24:12.33272	2025-10-16 08:24:12.332724
838	33	2025-10-16	200	200	100	200	0	0	0	100	400	[{"id": 1, "subject": "10/15 포인트", "points": 400, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-16 08:28:38"}]	1200	1	2025-10-16 08:28:38.170029	2025-10-16 08:29:03.594013
835	45	2025-10-16	100	100	100	200	0	0	0	0	0	[{"id": 1, "subject": "10/15  포인트", "points": 400, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-10-16 08:12:27"}, {"id": 2, "subject": "10/15 포인트 (차감)", "points": -400, "reason": "포인트 중복 입력", "created_by": "dev_hoon", "created_at": "2025-10-16 08:19:28"}]	500	5	2025-10-16 08:09:43.444307	2025-10-16 08:19:28.70575
836	37	2025-10-16	200	100	100	0	0	0	0	0	500	[{"id": 1, "subject": "학습태도", "points": 500, "reason": "학습태도", "created_by": "teacher", "created_at": "2025-10-16 08:31:20"}]	900	6	2025-10-16 08:23:27.238537	2025-10-16 08:31:20.160191
839	43	2025-10-16	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-16 08:58:35.908353	2025-10-16 08:58:35.908356
840	59	2025-10-16	100	100	0	0	0	0	0	0	0	[]	200	5	2025-10-16 08:58:40.367348	2025-10-16 08:58:40.367351
841	51	2025-10-16	100	100	100	0	0	0	0	0	0	[]	300	1	2025-10-16 09:00:10.247485	2025-10-16 09:00:10.247487
842	31	2025-10-16	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-16 09:05:07.329594	2025-10-16 09:05:07.329596
843	32	2025-10-16	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-16 09:05:51.480917	2025-10-16 09:05:51.480921
844	40	2025-10-17	200	100	100	200	0	100	0	0	0	[]	700	1	2025-10-17 05:35:54.264993	2025-10-17 05:35:54.264997
845	43	2025-10-17	200	100	100	200	0	100	0	0	0	[]	700	5	2025-10-17 06:11:59.651328	2025-10-17 06:11:59.651332
846	59	2025-10-17	200	100	100	200	0	100	0	0	0	[]	700	1	2025-10-17 06:34:31.279298	2025-10-17 06:34:31.279301
847	49	2025-10-17	100	100	100	100	0	100	0	0	200	[{"id": 1, "subject": "추가학습", "points": 200, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-10-17 06:47:35"}]	700	6	2025-10-17 06:45:44.245607	2025-10-17 06:47:35.006353
848	32	2025-10-17	200	200	100	200	0	100	0	100	0	[]	900	6	2025-10-17 08:22:22.032569	2025-10-17 08:22:24.011387
887	31	2025-10-22	100	200	100	200	0	0	0	100	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트 1장", "created_by": "dev_hoon", "created_at": "2025-10-22 05:09:54"}]	600	1	2025-10-22 05:09:54.590313	2025-10-22 05:12:41.802219
850	31	2025-10-17	100	200	100	200	0	100	0	100	0	[]	800	1	2025-10-17 08:24:49.89361	2025-10-17 08:24:49.893612
849	46	2025-10-17	100	200	100	200	0	100	0	0	300	[{"id": 1, "subject": "풍선", "points": 300, "reason": "풍선구매", "created_by": "teacher", "created_at": "2025-10-17 08:27:30"}]	1000	6	2025-10-17 08:23:38.889802	2025-10-17 08:27:30.966294
851	38	2025-10-17	200	100	100	100	0	100	0	0	0	[]	600	1	2025-10-17 08:38:28.351657	2025-10-17 08:38:28.351661
852	47	2025-10-17	100	100	100	0	0	100	0	0	0	[]	400	1	2025-10-17 09:01:39.895243	2025-10-17 09:01:39.895247
853	36	2025-10-20	0	0	0	0	0	0	0	0	-200	[{"id": 1, "subject": "10/10 포인트 (차감)", "points": -200, "reason": "500포인트인데 700포인트로 잘못 입력", "created_by": "dev_hoon", "created_at": "2025-10-20 05:03:59"}]	-200	1	2025-10-20 05:03:59.228636	2025-10-20 05:03:59.228638
855	31	2025-10-20	200	200	100	200	100	0	0	100	0	[]	900	1	2025-10-20 05:32:16.947843	2025-10-20 05:32:16.947846
856	40	2025-10-20	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-20 05:52:24.342573	2025-10-20 05:52:24.342577
857	49	2025-10-20	200	100	100	0	0	0	0	0	500	[{"id": 1, "subject": "추가학습", "points": 500, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-10-20 06:33:46"}]	900	6	2025-10-20 06:29:29.046028	2025-10-20 06:33:46.394149
858	43	2025-10-20	100	200	100	200	100	0	0	0	0	[]	700	5	2025-10-20 06:42:48.581128	2025-10-20 06:42:48.581133
859	48	2025-10-20	100	100	100	200	100	0	0	0	-300	[{"id": 1, "subject": "풍선", "points": -300, "reason": "풍선구매", "created_by": "teacher", "created_at": "2025-10-20 07:06:26"}]	300	6	2025-10-20 07:05:10.687432	2025-10-20 07:06:26.435917
860	32	2025-10-20	200	200	100	200	100	0	0	100	0	[]	900	6	2025-10-20 07:32:25.658437	2025-10-20 07:32:25.658441
861	50	2025-10-20	200	0	0	0	100	0	0	0	0	[]	300	6	2025-10-20 08:02:32.637402	2025-10-20 08:02:34.420595
862	59	2025-10-20	200	100	100	200	100	0	0	0	0	[]	700	5	2025-10-20 08:03:34.157407	2025-10-20 08:03:34.157411
863	38	2025-10-20	200	100	100	0	100	0	0	0	0	[]	500	1	2025-10-20 08:24:08.696429	2025-10-20 08:24:08.696432
865	54	2025-10-20	200	200	100	200	100	0	0	0	0	[]	800	1	2025-10-20 08:34:28.044032	2025-10-20 08:34:28.044035
864	39	2025-10-20	200	100	100	0	100	0	0	0	0	[]	500	6	2025-10-20 08:34:24.064018	2025-10-20 08:34:50.604498
868	45	2025-10-20	100	100	100	200	100	0	0	0	0	[]	600	6	2025-10-20 08:38:49.114049	2025-10-20 08:38:49.114053
867	44	2025-10-20	200	0	100	0	100	0	0	0	600	[{"id": 1, "subject": "10/17 포인트 ", "points": 600, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-20 08:39:35"}]	1000	1	2025-10-20 08:38:40.99972	2025-10-20 08:39:35.040509
866	46	2025-10-20	200	100	100	200	100	0	0	0	-600	[{"id": 1, "subject": "포인트 정정", "points": -600, "reason": "풍선구매 1번과 잘못입력된 +300(풍선)", "created_by": "dev_hoon", "created_at": "2025-10-20 08:44:11"}]	100	6	2025-10-20 08:35:41.560825	2025-10-20 08:44:11.17793
869	36	2025-10-21	0	0	0	0	0	0	0	0	800	[{"id": 1, "subject": "포인트 정정", "points": 800, "reason": "포인트 정정", "created_by": "dev_hoon", "created_at": "2025-10-21 01:47:21"}]	800	1	2025-10-21 01:47:21.957093	2025-10-21 01:47:21.957096
870	31	2025-10-21	100	200	100	200	0	100	0	100	0	[]	800	1	2025-10-21 06:24:28.877792	2025-10-21 06:24:28.877795
872	45	2025-10-21	200	100	100	200	0	100	0	0	0	[]	700	5	2025-10-21 07:35:56.842927	2025-10-21 07:35:56.84293
874	46	2025-10-21	200	100	100	200	0	100	0	0	0	[]	700	6	2025-10-21 07:38:54.619842	2025-10-21 07:38:54.619845
875	32	2025-10-21	200	200	100	200	0	100	0	100	0	[]	900	1	2025-10-21 07:40:13.306981	2025-10-21 07:40:13.306985
876	43	2025-10-21	100	200	100	200	0	100	0	0	0	[]	700	1	2025-10-21 08:04:17.846933	2025-10-21 08:04:17.846936
877	50	2025-10-21	200	100	100	0	0	100	0	0	0	[]	500	6	2025-10-21 08:06:50.700402	2025-10-21 08:06:50.700406
871	40	2025-10-21	200	200	100	200	0	100	0	0	-100	[{"id": 1, "subject": "테이프", "points": -100, "reason": "테이프 구매", "created_by": "dev_hoon", "created_at": "2025-10-21 08:10:44"}]	700	1	2025-10-21 06:59:52.355449	2025-10-21 08:10:44.981586
878	42	2025-10-20	0	0	0	0	0	0	0	0	0	[]	5700	6	2025-10-21 08:23:58.51341	2025-10-21 08:23:58.513411
879	42	2025-10-21	200	0	100	0	0	0	0	0	0	[]	300	6	2025-10-21 08:24:50.702561	2025-10-21 08:24:52.442474
880	38	2025-10-21	100	100	0	0	0	100	0	0	0	[]	300	1	2025-10-21 08:27:41.810202	2025-10-21 08:27:41.810205
873	44	2025-10-21	200	0	0	0	0	100	0	0	0	[]	300	5	2025-10-21 07:37:24.108137	2025-10-21 08:28:10.73557
881	59	2025-10-21	100	100	100	100	0	100	0	0	0	[]	500	5	2025-10-21 08:27:57.345677	2025-10-21 08:33:39.136732
882	48	2025-10-21	200	100	100	100	0	100	0	0	0	[]	600	5	2025-10-21 08:44:50.448781	2025-10-21 08:44:50.448784
883	33	2025-10-21	100	100	100	100	0	100	0	100	0	[]	600	5	2025-10-21 08:45:37.367382	2025-10-21 08:45:37.367386
884	47	2025-10-21	100	100	100	0	0	100	0	0	0	[]	400	5	2025-10-21 08:46:33.482308	2025-10-21 08:46:33.482311
885	41	2025-10-21	100	100	100	100	0	0	0	0	0	[]	400	5	2025-10-21 08:46:59.894339	2025-10-21 08:47:01.443422
886	37	2025-10-21	200	100	0	0	0	100	0	0	200	[{"id": 1, "subject": "추가 학습", "points": 200, "reason": "추가 학습 (국어)", "created_by": "sowo_1", "created_at": "2025-10-21 08:49:59"}]	600	5	2025-10-21 08:49:01.238409	2025-10-21 08:49:59.302013
888	35	2025-10-22	0	0	0	200	0	0	0	100	800	[{"id": 1, "subject": "10/20 포인트", "points": 800, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-22 05:32:58"}]	1100	1	2025-10-22 05:32:58.639889	2025-10-22 05:33:22.265677
889	40	2025-10-22	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-22 05:37:05.47365	2025-10-22 05:37:06.043655
890	43	2025-10-22	0	100	0	200	0	0	0	0	0	[]	300	1	2025-10-22 07:02:39.708736	2025-10-22 07:02:39.70874
891	33	2025-10-22	200	0	0	200	0	0	0	0	0	[]	400	1	2025-10-22 07:24:46.358305	2025-10-22 07:24:46.358308
892	54	2025-10-22	100	0	0	200	0	0	0	0	0	[]	300	1	2025-10-22 07:42:59.979921	2025-10-22 07:42:59.979926
899	47	2025-10-22	100	100	0	100	0	0	0	0	0	[]	300	6	2025-10-22 08:08:03.571249	2025-10-22 08:08:03.571253
893	48	2025-10-22	100	100	0	200	0	0	0	0	-600	[{"id": 1, "subject": "연필", "points": -600, "reason": "연필 구매", "created_by": "teacher", "created_at": "2025-10-22 07:44:03"}]	-200	6	2025-10-22 07:43:02.618755	2025-10-22 07:44:03.895886
894	46	2025-10-22	100	200	0	200	0	0	0	0	0	[]	500	6	2025-10-22 07:45:34.868887	2025-10-22 07:45:34.868891
895	42	2025-10-22	100	100	100	200	0	0	0	0	0	[]	500	6	2025-10-22 07:46:14.124893	2025-10-22 07:46:14.124896
896	45	2025-10-22	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-22 07:47:24.008833	2025-10-22 07:47:24.008837
897	32	2025-10-22	200	0	0	200	0	0	0	100	0	[]	500	6	2025-10-22 07:58:43.326196	2025-10-22 07:58:43.326199
898	50	2025-10-22	100	0	100	200	0	0	0	0	0	[]	400	6	2025-10-22 08:02:46.621304	2025-10-22 08:02:46.621307
900	44	2025-10-22	100	100	0	0	0	0	0	0	0	[]	200	6	2025-10-22 08:10:50.153936	2025-10-22 08:10:50.153939
901	34	2025-10-22	0	100	0	200	0	0	0	100	0	[]	400	6	2025-10-22 08:20:02.363978	2025-10-22 08:20:02.363982
902	41	2025-10-22	200	100	100	200	0	0	0	0	600	[{"id": 1, "subject": "포인트 정정", "points": 600, "reason": "포인트 정정", "created_by": "dev_hoon", "created_at": "2025-10-22 08:23:30"}]	1200	1	2025-10-22 08:23:30.751925	2025-10-22 08:23:55.466407
903	37	2025-10-22	200	200	100	0	0	0	0	0	-1000	[{"id": 1, "subject": "수첩", "points": -1000, "reason": "수첩구매", "created_by": "teacher", "created_at": "2025-10-22 08:26:03"}]	-500	6	2025-10-22 08:26:03.668366	2025-10-22 08:32:04.788811
904	39	2025-10-22	0	100	100	0	0	0	0	0	0	[]	200	6	2025-10-22 08:33:49.514662	2025-10-22 08:33:49.514666
905	52	2025-10-22	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-22 08:37:17.847994	2025-10-22 08:37:17.847998
906	40	2025-10-23	200	200	100	200	0	0	0	0	0	[]	700	6	2025-10-23 05:24:15.12699	2025-10-23 05:24:15.126993
907	35	2025-10-23	100	100	100	200	0	0	0	100	0	[]	600	5	2025-10-23 06:27:45.827837	2025-10-23 06:27:45.827839
908	43	2025-10-23	200	200	100	200	0	0	0	0	0	[]	700	5	2025-10-23 06:29:06.080703	2025-10-23 06:29:06.080706
909	49	2025-10-23	200	200	100	0	0	0	0	0	300	[{"id": 1, "subject": "추가학습", "points": 300, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-10-23 06:48:33"}]	800	6	2025-10-23 06:47:27.077213	2025-10-23 06:48:33.48523
942	48	2025-10-27	100	200	100	200	100	0	0	0	-300	[{"id": 1, "subject": "프린트", "points": -300, "reason": "프린트 3개", "created_by": "sowo_1", "created_at": "2025-10-27 06:07:30"}]	400	5	2025-10-27 06:06:13.392299	2025-10-27 06:07:30.804341
910	42	2025-10-23	100	100	100	0	0	0	0	0	300	[{"id": 1, "subject": "학습태도", "points": 300, "reason": "학습태도", "created_by": "teacher", "created_at": "2025-10-23 06:51:03"}]	600	6	2025-10-23 06:49:53.421753	2025-10-23 06:51:03.962494
912	46	2025-10-23	100	0	100	200	0	0	0	0	-100	[{"id": 1, "subject": "이면지", "points": -100, "reason": "이면지", "created_by": "teacher", "created_at": "2025-10-23 07:43:39"}]	300	6	2025-10-23 07:43:39.773595	2025-10-23 07:44:07.07009
913	41	2025-10-23	100	100	100	200	0	0	0	0	0	[]	500	5	2025-10-23 07:45:19.239009	2025-10-23 07:45:19.239012
914	32	2025-10-23	100	200	100	200	0	0	0	100	0	[]	700	6	2025-10-23 07:48:49.887248	2025-10-23 07:48:49.88725
915	44	2025-10-23	200	0	0	0	0	0	0	0	0	[]	200	6	2025-10-23 07:51:52.967183	2025-10-23 07:51:52.967185
911	59	2025-10-23	100	100	100	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-10-23 08:01:18"}]	400	5	2025-10-23 07:43:23.884934	2025-10-23 08:01:18.857253
916	54	2025-10-23	200	200	0	200	0	0	0	0	0	[]	600	5	2025-10-23 08:21:44.933118	2025-10-23 08:21:44.93312
917	48	2025-10-23	200	100	100	200	0	0	0	0	0	[]	600	5	2025-10-23 08:24:05.40628	2025-10-23 08:24:05.406281
918	33	2025-10-23	200	200	100	200	0	0	0	100	0	[]	800	5	2025-10-23 08:26:25.573761	2025-10-23 08:26:26.344684
919	31	2025-10-23	100	200	100	200	0	0	0	100	0	[]	700	5	2025-10-23 08:27:09.860757	2025-10-23 08:27:09.860759
920	45	2025-10-23	200	100	100	200	0	0	0	0	-100	[{"id": 1, "subject": "종이", "points": -100, "reason": "종이", "created_by": "sowo_1", "created_at": "2025-10-23 08:30:26"}]	500	5	2025-10-23 08:29:18.240013	2025-10-23 08:30:26.537365
921	39	2025-10-23	200	100	100	0	0	0	0	0	0	[]	400	5	2025-10-23 08:32:31.855306	2025-10-23 08:32:31.85531
922	40	2025-10-24	100	200	100	200	0	0	0	0	0	[]	600	1	2025-10-24 05:33:18.662262	2025-10-24 05:33:18.662265
923	43	2025-10-24	200	200	100	200	0	0	0	0	0	[]	700	5	2025-10-24 06:03:52.116044	2025-10-24 06:03:52.116049
924	49	2025-10-24	100	200	100	200	0	0	0	0	0	[]	600	1	2025-10-24 06:22:54.917646	2025-10-24 06:22:54.91765
925	35	2025-10-24	200	200	100	200	0	0	0	100	0	[]	800	5	2025-10-24 06:27:59.519257	2025-10-24 06:27:59.519261
926	32	2025-10-24	200	200	100	200	0	0	0	100	0	[]	800	5	2025-10-24 06:38:38.720531	2025-10-24 06:38:38.720535
927	48	2025-10-24	100	100	100	200	0	0	0	0	0	[]	500	6	2025-10-24 06:41:38.124091	2025-10-24 06:41:38.124093
928	50	2025-10-24	200	100	100	200	0	0	0	0	0	[]	600	6	2025-10-24 06:49:06.56333	2025-10-24 06:49:07.312085
929	46	2025-10-24	200	200	100	200	0	0	0	0	0	[]	700	6	2025-10-24 07:06:52.682294	2025-10-24 07:06:52.682298
930	44	2025-10-24	200	100	100	0	0	0	0	0	100	[{"id": 1, "subject": "5학년 수학", "points": 100, "reason": "5학년 수학", "created_by": "sowo_1", "created_at": "2025-10-24 07:40:41"}]	500	5	2025-10-24 07:39:28.109733	2025-10-24 07:40:41.940608
931	36	2025-10-24	0	0	0	100	0	0	0	0	200	[{"id": 1, "subject": "10/22 포인트", "points": 200, "reason": "받 100, 독 100", "created_by": "sowo_1", "created_at": "2025-10-24 07:50:10"}]	300	5	2025-10-24 07:49:18.676144	2025-10-24 07:50:10.576759
932	31	2025-10-24	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-24 07:51:20.842762	2025-10-24 07:51:20.842766
933	42	2025-10-24	0	100	0	0	0	0	0	0	0	[]	100	6	2025-10-24 07:55:51.322674	2025-10-24 07:55:51.322678
943	43	2025-10-27	100	200	100	200	100	0	0	0	0	[]	700	1	2025-10-27 06:30:40.215758	2025-10-27 06:30:40.215762
934	38	2025-10-24	100	200	0	100	0	0	0	0	700	[{"id": 1, "subject": "10/23 포인트", "points": 700, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-24 08:00:27"}]	1100	1	2025-10-24 08:00:27.284977	2025-10-24 08:00:58.672509
935	54	2025-10-24	100	200	100	0	0	0	0	0	0	[]	400	1	2025-10-24 08:09:50.062223	2025-10-24 08:10:23.102488
936	33	2025-10-24	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-24 08:23:42.298095	2025-10-24 08:23:42.298098
937	47	2025-10-24	100	100	100	200	0	0	0	0	0	[]	500	6	2025-10-24 08:32:36.374735	2025-10-24 08:32:36.374737
938	45	2025-10-24	200	100	100	200	0	0	0	0	0	[]	600	5	2025-10-24 08:43:48.936949	2025-10-24 08:43:48.936954
939	31	2025-10-27	200	200	100	200	100	0	0	100	0	[]	900	1	2025-10-27 05:02:00.387502	2025-10-27 05:02:00.387504
940	40	2025-10-27	100	100	100	200	100	0	0	0	0	[]	600	1	2025-10-27 06:01:46.371679	2025-10-27 06:01:46.371683
941	49	2025-10-27	200	200	100	200	0	0	0	0	0	[]	700	5	2025-10-27 06:02:06.030202	2025-10-27 06:02:06.030204
944	45	2025-10-27	200	100	100	200	100	0	0	0	0	[]	700	1	2025-10-27 06:41:13.451848	2025-10-27 06:41:13.45185
945	47	2025-10-27	100	0	100	0	100	0	0	0	0	[]	300	6	2025-10-27 06:45:10.250878	2025-10-27 06:45:10.867045
946	59	2025-10-27	200	100	100	200	100	0	0	0	500	[{"id": 1, "subject": "10/24 포인트", "points": 500, "reason": "포인트 입력 누락", "created_by": "sowo_1", "created_at": "2025-10-27 06:50:19"}]	1200	5	2025-10-27 06:47:09.53877	2025-10-27 06:50:19.586505
947	42	2025-10-27	100	100	100	200	100	0	0	0	0	[]	600	6	2025-10-27 07:03:49.337296	2025-10-27 07:03:49.3373
948	46	2025-10-27	200	100	100	200	100	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-10-27 07:41:54"}]	500	6	2025-10-27 07:41:25.912644	2025-10-27 07:41:54.439223
949	50	2025-10-27	200	100	100	200	100	0	0	0	0	[]	700	1	2025-10-27 08:06:28.839693	2025-10-27 08:06:28.839697
950	44	2025-10-27	200	200	100	0	100	0	0	0	0	[]	600	1	2025-10-27 08:14:52.417326	2025-10-27 08:14:52.417348
951	41	2025-10-27	200	100	100	200	0	0	0	0	0	[]	600	5	2025-10-27 08:15:45.773122	2025-10-27 08:15:45.773127
952	33	2025-10-27	200	200	100	200	100	0	0	100	0	[]	900	1	2025-10-27 08:29:57.892197	2025-10-27 08:29:57.8922
953	39	2025-10-27	100	0	0	0	0	0	0	0	0	[]	100	5	2025-10-27 08:34:51.541661	2025-10-27 08:34:51.541665
955	31	2025-10-28	200	200	100	200	0	100	0	100	0	[]	900	1	2025-10-28 06:10:49.852338	2025-10-28 06:10:49.852342
954	36	2025-10-27	100	100	100	0	0	0	0	0	300	[{"id": 1, "subject": "추가학습", "points": 300, "reason": "추가학습", "created_by": "sowo_1", "created_at": "2025-10-27 08:53:52"}]	600	5	2025-10-27 08:51:44.91054	2025-10-27 08:54:13.731241
956	45	2025-10-28	200	100	100	200	0	100	0	0	0	[]	700	1	2025-10-28 06:46:44.574091	2025-10-28 06:46:44.574094
957	46	2025-10-28	200	100	100	200	0	100	0	0	0	[]	700	6	2025-10-28 07:51:59.442652	2025-10-28 07:51:59.442655
958	54	2025-10-28	100	100	100	0	0	100	0	0	0	[]	400	1	2025-10-28 07:52:56.307644	2025-10-28 07:52:56.307647
959	40	2025-10-28	100	200	100	100	0	100	0	0	0	[]	600	1	2025-10-28 07:53:40.398472	2025-10-28 07:53:40.398476
960	32	2025-10-28	200	200	100	200	0	100	0	100	700	[{"id": 1, "subject": "10/27 포인트", "points": 700, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-28 08:01:02"}]	1600	1	2025-10-28 08:01:02.081177	2025-10-28 08:02:02.206492
961	43	2025-10-28	100	200	100	200	0	100	0	0	0	[]	700	5	2025-10-28 08:03:49.185237	2025-10-28 08:03:49.185241
962	33	2025-10-28	200	200	100	200	0	100	0	100	0	[]	900	1	2025-10-28 08:07:33.055655	2025-10-28 08:07:33.055659
963	47	2025-10-28	200	100	100	200	0	100	0	0	0	[]	700	6	2025-10-28 08:12:23.018532	2025-10-28 08:12:23.018536
964	38	2025-10-28	100	0	100	200	0	100	0	0	0	[]	500	1	2025-10-28 08:24:40.214874	2025-10-28 08:24:40.214878
965	59	2025-10-28	200	100	100	0	0	100	0	0	0	[]	500	5	2025-10-28 08:42:06.069765	2025-10-28 08:42:06.069769
966	41	2025-10-28	100	100	100	200	0	100	0	0	0	[]	600	5	2025-10-28 08:54:43.776869	2025-10-28 08:54:43.776872
967	31	2025-10-29	200	0	0	200	0	0	0	100	0	[]	500	1	2025-10-29 04:28:05.051036	2025-10-29 04:28:05.05104
968	45	2025-10-29	0	0	0	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-10-29 05:54:37"}]	100	5	2025-10-29 05:53:49.261059	2025-10-29 05:54:38.000084
969	43	2025-10-29	0	0	0	200	0	0	0	0	0	[]	200	1	2025-10-29 06:23:49.381836	2025-10-29 06:23:49.381839
970	32	2025-10-29	0	0	0	200	0	0	0	0	0	[]	200	1	2025-10-29 07:34:53.062992	2025-10-29 07:34:53.062995
971	50	2025-10-29	0	0	0	200	0	0	0	0	0	[]	200	1	2025-10-29 07:40:06.03958	2025-10-29 07:40:06.039583
972	48	2025-10-29	0	0	0	200	0	0	0	0	700	[{"id": 1, "subject": "10/28 포인트 갱신", "points": 700, "reason": "포인트 입력 누락", "created_by": "sowo_1", "created_at": "2025-10-29 08:31:13"}]	900	5	2025-10-29 08:30:23.988808	2025-10-29 08:31:13.483248
973	43	2025-10-30	200	200	100	200	0	0	0	0	0	[]	700	1	2025-10-30 05:37:02.893627	2025-10-30 05:37:02.89363
1002	56	2025-11-03	200	100	100	0	100	0	0	0	0	[]	500	5	2025-11-03 06:43:30.275985	2025-11-03 06:43:30.275988
974	35	2025-10-30	200	200	100	200	0	0	0	100	1500	[{"id": 1, "subject": "10/27 포인트", "points": 700, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-30 06:22:31"}, {"id": 2, "subject": "10/28 포인트", "points": 800, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-30 06:23:05"}]	2300	1	2025-10-30 06:22:31.401816	2025-10-30 06:23:37.889984
975	48	2025-10-30	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-30 06:26:24.904068	2025-10-30 06:26:24.904071
976	44	2025-10-30	0	0	0	0	0	0	0	0	200	[{"id": 1, "subject": "10/29 포인트", "points": 200, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-10-30 06:28:03"}]	200	1	2025-10-30 06:28:03.69074	2025-10-30 06:28:03.690742
977	31	2025-10-30	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-30 06:32:03.222957	2025-10-30 06:32:03.222961
978	59	2025-10-30	100	200	100	200	0	0	0	0	0	[]	600	5	2025-10-30 06:34:12.046869	2025-10-30 06:34:12.046872
979	49	2025-10-30	100	200	100	0	0	0	0	0	0	[]	400	5	2025-10-30 06:39:20.170365	2025-10-30 06:39:20.170369
980	46	2025-10-30	200	0	100	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-10-30 06:42:08"}]	400	5	2025-10-30 06:40:41.901433	2025-10-30 06:42:08.878121
981	34	2025-10-30	100	200	100	200	0	0	0	100	0	[]	700	5	2025-10-30 06:50:48.127382	2025-10-30 06:50:48.127384
982	42	2025-10-30	100	100	100	0	0	0	0	0	0	[]	300	6	2025-10-30 06:52:09.674129	2025-10-30 06:52:09.674133
983	41	2025-10-30	200	100	100	200	0	0	0	0	0	[]	600	5	2025-10-30 06:54:12.432288	2025-10-30 06:54:12.432291
984	32	2025-10-30	200	200	100	200	0	0	0	100	0	[]	800	1	2025-10-30 06:57:08.823437	2025-10-30 06:57:08.823441
985	45	2025-10-30	200	100	100	200	0	0	0	0	0	[]	600	1	2025-10-30 07:01:40.505487	2025-10-30 07:01:40.505489
986	50	2025-10-30	100	200	100	200	0	0	0	0	0	[]	600	1	2025-10-30 07:33:55.745502	2025-10-30 07:33:55.745505
987	43	2025-10-31	100	0	0	200	0	100	0	0	0	[]	400	5	2025-10-31 06:05:47.924548	2025-10-31 06:05:47.924549
988	35	2025-10-31	100	0	0	200	0	100	0	100	0	[]	500	5	2025-10-31 06:31:46.055084	2025-10-31 06:31:46.055086
989	59	2025-10-31	200	100	0	200	0	100	0	0	0	[]	600	5	2025-10-31 06:57:18.398755	2025-10-31 06:57:18.398759
990	48	2025-10-31	100	200	0	200	0	0	0	0	0	[]	500	6	2025-10-31 07:32:40.126793	2025-10-31 07:32:40.126795
991	50	2025-10-31	200	200	100	200	0	100	0	0	0	[]	800	6	2025-10-31 07:46:08.53161	2025-10-31 07:46:08.531614
992	41	2025-10-31	100	100	0	200	0	100	0	0	0	[]	500	5	2025-10-31 07:56:55.146822	2025-10-31 07:57:27.63691
993	44	2025-10-31	200	100	100	0	0	100	0	0	400	[{"id": 1, "subject": "10/30 포인트", "points": 400, "reason": "포인트 입력 누락", "created_by": "sowo_1", "created_at": "2025-10-31 07:59:58"}]	900	5	2025-10-31 07:58:25.53479	2025-10-31 07:59:58.651327
994	34	2025-10-31	0	0	0	0	0	0	0	0	-300	[{"id": 1, "subject": "학습실출입", "points": -300, "reason": "학습실출입", "created_by": "teacher", "created_at": "2025-10-31 08:02:43"}]	-300	6	2025-10-31 08:02:43.290075	2025-10-31 08:02:43.290078
995	32	2025-10-31	200	200	100	200	0	100	0	100	0	[]	900	1	2025-10-31 08:05:32.623395	2025-10-31 08:05:32.623399
996	31	2025-10-31	200	100	0	200	0	100	0	0	0	[]	600	1	2025-10-31 08:07:18.459118	2025-10-31 08:07:18.459122
997	47	2025-10-31	100	100	0	200	0	0	0	0	0	[]	400	1	2025-10-31 08:22:01.443468	2025-10-31 08:22:01.44347
998	54	2025-10-31	0	0	0	200	0	100	0	0	0	[]	300	1	2025-10-31 08:26:55.594617	2025-10-31 08:26:55.59462
999	31	2025-11-03	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-03 05:36:36.414579	2025-11-03 05:36:36.414583
1000	40	2025-11-03	200	100	100	200	100	0	0	0	0	[]	700	1	2025-11-03 06:20:06.4774	2025-11-03 06:20:06.477403
1001	43	2025-11-03	200	200	100	200	100	0	0	0	0	[]	800	1	2025-11-03 06:39:10.113026	2025-11-03 06:39:10.113028
1003	48	2025-11-03	200	100	100	200	100	0	0	0	0	[]	700	6	2025-11-03 06:47:14.258733	2025-11-03 06:47:14.258736
1004	42	2025-11-03	200	100	100	200	100	0	0	0	0	[]	700	6	2025-11-03 07:06:08.92337	2025-11-03 07:06:08.923372
1005	59	2025-11-03	200	100	100	200	100	0	0	0	0	[]	700	5	2025-11-03 07:34:37.33967	2025-11-03 07:34:37.339672
1006	32	2025-11-03	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-03 07:48:24.691118	2025-11-03 07:48:24.69112
1007	50	2025-11-03	200	200	100	200	100	0	0	0	0	[]	800	1	2025-11-03 07:51:48.987038	2025-11-03 07:51:48.987043
1008	46	2025-11-03	200	100	100	200	100	0	0	0	300	[{"id": 1, "subject": "10월 31일", "points": 300, "reason": "10월 31일", "created_by": "teacher", "created_at": "2025-11-03 08:00:10"}]	1000	6	2025-11-03 08:00:10.802849	2025-11-03 08:00:54.47976
1009	41	2025-11-03	200	100	100	200	0	0	0	0	0	[]	600	5	2025-11-03 08:02:48.233891	2025-11-03 08:02:48.233893
1010	54	2025-11-03	100	100	100	200	100	0	0	0	0	[]	600	1	2025-11-03 08:24:48.774366	2025-11-03 08:24:48.774368
1012	34	2025-11-03	100	200	100	200	100	0	0	100	0	[]	800	5	2025-11-03 08:51:54.176142	2025-11-03 08:51:54.176145
1011	36	2025-11-03	100	100	100	200	0	0	0	100	100	[{"id": 1, "subject": "추가 학습", "points": 100, "reason": "추가 학습(쎈)", "created_by": "sowo_1", "created_at": "2025-11-03 08:38:21"}]	700	5	2025-11-03 08:37:14.891805	2025-11-03 09:02:07.275241
1013	45	2025-11-04	200	100	100	200	0	100	0	0	400	[{"id": 1, "subject": "10/30 포인트", "points": 400, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-11-04 06:45:55"}]	1100	1	2025-11-04 06:45:55.490409	2025-11-04 06:46:48.234848
1014	40	2025-11-04	100	100	100	200	0	100	0	0	0	[]	600	1	2025-11-04 06:53:25.569321	2025-11-04 06:53:25.569324
1015	34	2025-11-04	100	100	100	200	0	100	0	0	0	[]	600	5	2025-11-04 07:06:59.912821	2025-11-04 07:06:59.912823
1016	46	2025-11-04	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-04 07:28:31.667013	2025-11-04 07:28:31.667015
1017	43	2025-11-04	200	100	100	200	0	100	0	0	0	[]	700	1	2025-11-04 07:53:56.413335	2025-11-04 07:53:56.413339
1018	47	2025-11-04	200	100	100	100	0	100	0	0	0	[]	600	6	2025-11-04 07:56:38.221103	2025-11-04 07:56:38.221107
1019	31	2025-11-04	100	200	100	200	0	100	0	100	0	[]	800	1	2025-11-04 07:59:10.72064	2025-11-04 07:59:10.720642
1020	32	2025-11-04	200	200	100	200	0	100	0	100	0	[]	900	1	2025-11-04 08:00:21.08123	2025-11-04 08:00:21.081232
1065	31	2025-11-10	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-10 05:30:11.19356	2025-11-10 05:30:11.193562
1021	33	2025-11-04	100	200	100	200	0	100	0	100	1000	[{"id": 1, "subject": "10/29 포인트", "points": 200, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-11-04 08:07:22"}, {"id": 2, "subject": "11/3 포인트", "points": 800, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-11-04 08:07:53"}]	1800	1	2025-11-04 08:07:22.720804	2025-11-04 08:08:32.238942
1022	50	2025-11-04	100	100	100	200	0	100	0	0	0	[]	600	6	2025-11-04 08:09:00.362898	2025-11-04 08:09:00.3629
1023	59	2025-11-04	100	0	100	200	0	100	0	0	0	[]	500	5	2025-11-04 08:10:30.801788	2025-11-04 08:10:30.80179
1024	54	2025-11-04	100	100	100	200	0	100	0	0	0	[]	600	5	2025-11-04 08:42:36.200302	2025-11-04 08:42:36.200304
1025	41	2025-11-04	100	200	100	200	0	100	0	0	0	[]	700	5	2025-11-04 08:55:31.293504	2025-11-04 08:55:31.293508
1026	37	2025-11-04	0	0	0	0	0	100	0	0	0	[]	100	5	2025-11-04 08:57:41.984794	2025-11-04 08:57:41.984796
1027	31	2025-11-05	200	200	0	200	0	0	0	100	0	[]	700	5	2025-11-05 04:43:22.990525	2025-11-05 04:43:22.990527
1029	40	2025-11-05	100	100	0	0	0	0	0	0	0	[]	200	5	2025-11-05 05:24:57.181203	2025-11-05 05:24:57.181206
1030	43	2025-11-05	200	200	0	200	0	0	0	0	0	[]	600	5	2025-11-05 05:36:47.221905	2025-11-05 05:36:47.221907
1028	35	2025-11-05	200	100	0	200	0	0	0	100	0	[]	600	5	2025-11-05 05:15:22.839126	2025-11-05 05:43:11.718013
1031	32	2025-11-05	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-05 07:26:19.571233	2025-11-05 07:26:19.571235
1032	54	2025-11-05	200	200	0	200	0	0	0	0	0	[]	600	5	2025-11-05 07:27:21.168806	2025-11-05 07:27:21.168809
1033	50	2025-11-05	200	0	100	0	0	0	0	0	0	[]	300	6	2025-11-05 07:28:52.730773	2025-11-05 07:28:53.952916
1034	59	2025-11-05	100	200	0	200	0	0	0	0	0	[]	500	5	2025-11-05 07:46:02.204627	2025-11-05 07:46:02.204629
1035	46	2025-11-05	200	100	0	200	0	0	0	0	0	[]	500	5	2025-11-05 07:49:04.265333	2025-11-05 07:49:04.265337
1036	45	2025-11-05	200	200	0	200	0	0	0	0	0	[]	600	6	2025-11-05 07:50:14.176313	2025-11-05 07:50:14.176315
1037	48	2025-11-05	200	100	0	200	0	0	0	0	0	[]	500	6	2025-11-05 07:51:06.634045	2025-11-05 07:51:06.634047
1038	41	2025-11-05	100	100	0	200	0	0	0	0	0	[]	400	5	2025-11-05 08:04:40.839085	2025-11-05 08:04:40.839087
1039	33	2025-11-05	200	200	0	200	0	0	0	100	0	[]	700	5	2025-11-05 08:17:55.273521	2025-11-05 08:17:55.273524
1040	40	2025-11-06	200	200	100	200	0	0	0	0	0	[]	700	1	2025-11-06 05:38:29.480947	2025-11-06 05:38:29.480948
1041	43	2025-11-06	200	200	100	200	0	0	0	0	0	[]	700	1	2025-11-06 06:07:07.389256	2025-11-06 06:07:07.389257
1042	49	2025-11-06	200	100	100	0	0	0	0	0	0	[]	400	6	2025-11-06 06:38:33.483238	2025-11-06 06:38:33.48324
1043	48	2025-11-06	200	100	100	200	0	0	0	0	0	[]	600	6	2025-11-06 06:42:09.353205	2025-11-06 06:42:09.353209
1044	42	2025-11-06	100	100	100	0	0	0	0	0	0	[]	300	6	2025-11-06 06:44:13.247347	2025-11-06 06:44:13.247349
1045	41	2025-11-06	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-06 07:45:58.322836	2025-11-06 07:45:58.322838
1046	59	2025-11-06	200	100	100	200	0	0	0	0	0	[]	600	5	2025-11-06 07:47:36.668809	2025-11-06 07:47:36.668811
1047	32	2025-11-06	200	200	100	200	0	0	0	100	300	[{"id": 1, "subject": "11/5 포인트 추가", "points": 300, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-11-06 07:56:01"}]	1100	1	2025-11-06 07:56:01.933776	2025-11-06 07:56:23.413925
1048	31	2025-11-06	200	100	100	200	0	0	0	100	0	[]	700	1	2025-11-06 08:05:56.677816	2025-11-06 08:05:56.677817
1049	46	2025-11-06	200	0	100	200	0	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-06 08:13:00"}]	300	6	2025-11-06 08:13:00.175331	2025-11-06 08:13:26.178731
1050	33	2025-11-06	200	200	100	200	0	0	0	100	0	[]	800	1	2025-11-06 08:33:02.847947	2025-11-06 08:33:02.847949
1051	54	2025-11-06	200	100	100	200	0	0	0	0	0	[]	600	1	2025-11-06 08:43:00.928587	2025-11-06 08:43:00.928589
1052	51	2025-11-06	100	100	100	0	0	0	0	0	0	[]	300	1	2025-11-06 08:46:59.370388	2025-11-06 08:46:59.37039
1053	40	2025-11-07	100	100	100	200	0	100	0	0	0	[]	600	5	2025-11-07 06:11:27.461466	2025-11-07 06:11:27.461468
1054	49	2025-11-07	200	200	100	0	0	100	0	0	0	[]	600	6	2025-11-07 06:14:43.109938	2025-11-07 06:14:43.109943
1055	43	2025-11-07	200	200	100	200	0	100	0	0	0	[]	800	5	2025-11-07 06:15:40.054659	2025-11-07 06:15:40.054661
1056	59	2025-11-07	200	0	100	200	0	100	0	0	0	[]	600	5	2025-11-07 07:01:41.853831	2025-11-07 07:01:41.853833
1057	32	2025-11-07	200	200	100	200	0	100	0	100	0	[]	900	6	2025-11-07 08:00:00.818648	2025-11-07 08:00:00.81865
1058	47	2025-11-07	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-07 08:04:02.630969	2025-11-07 08:04:02.630972
1059	33	2025-11-07	200	200	100	200	0	100	0	100	0	[]	900	5	2025-11-07 08:09:03.012437	2025-11-07 08:09:03.01244
1060	46	2025-11-07	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-07 08:10:39.772715	2025-11-07 08:10:39.772717
1061	48	2025-11-07	100	100	100	200	0	100	0	0	-100	[{"id": 1, "subject": "이면지", "points": -100, "reason": "이면지", "created_by": "teacher", "created_at": "2025-11-07 08:21:34"}]	500	6	2025-11-07 08:20:23.615014	2025-11-07 08:21:34.543571
1062	45	2025-11-07	200	100	100	0	0	100	0	0	0	[]	500	5	2025-11-07 08:40:12.889644	2025-11-07 08:40:12.889646
1063	31	2025-11-07	200	200	100	200	0	100	0	100	0	[]	900	5	2025-11-07 08:44:41.399954	2025-11-07 08:44:41.399957
1064	35	2025-11-07	200	100	100	200	0	100	0	100	0	[]	800	5	2025-11-07 09:01:29.135331	2025-11-07 09:01:29.135334
1066	43	2025-11-10	200	200	100	200	100	0	0	0	0	[]	800	5	2025-11-10 06:26:56.211229	2025-11-10 06:26:57.151857
1067	45	2025-11-10	200	200	100	200	100	0	0	0	0	[]	800	1	2025-11-10 06:53:25.916506	2025-11-10 06:53:25.916509
1068	40	2025-11-10	100	100	100	200	100	0	0	0	0	[]	600	1	2025-11-10 06:54:39.521512	2025-11-10 06:54:39.521516
1069	49	2025-11-10	100	200	100	200	0	0	0	0	0	[]	600	1	2025-11-10 06:56:19.977029	2025-11-10 06:56:19.977033
1070	59	2025-11-10	200	0	100	200	100	0	0	0	0	[]	600	5	2025-11-10 07:43:37.822584	2025-11-10 07:43:37.822587
1071	32	2025-11-10	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-10 07:46:04.930321	2025-11-10 07:46:04.930325
1073	48	2025-11-10	200	100	100	200	100	0	0	0	0	[]	700	1	2025-11-10 07:50:42.173165	2025-11-10 07:50:42.173167
1074	35	2025-11-10	200	100	100	200	0	100	0	100	0	[]	800	5	2025-11-10 07:57:37.702845	2025-11-10 07:57:51.585327
1075	52	2025-11-10	200	200	100	200	100	0	0	0	-100	[{"id": 1, "subject": "종이 구매", "points": -100, "reason": "종이 구매 1장", "created_by": "dev_hoon", "created_at": "2025-11-10 07:58:17"}]	700	1	2025-11-10 07:57:48.983251	2025-11-10 07:58:17.920924
1077	46	2025-11-10	100	100	100	200	0	100	0	0	0	[]	600	5	2025-11-10 08:03:51.021877	2025-11-10 08:03:51.02188
1078	33	2025-11-10	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-10 08:10:26.568042	2025-11-10 08:10:26.568045
1079	39	2025-11-10	200	100	0	0	0	0	0	0	0	[]	300	1	2025-11-10 08:31:16.189159	2025-11-10 08:31:16.189163
1080	41	2025-11-10	200	200	100	200	100	0	0	0	0	[]	800	5	2025-11-10 08:32:26.217306	2025-11-10 08:32:26.217309
1081	34	2025-11-10	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-10 08:36:46.082672	2025-11-10 08:36:46.082675
1076	54	2025-11-10	200	100	100	200	100	0	0	0	0	[]	700	1	2025-11-10 08:00:30.861424	2025-11-10 08:50:33.706612
1135	40	2025-11-17	200	100	100	200	100	0	0	0	0	[]	700	1	2025-11-17 07:59:30.576111	2025-11-17 07:59:30.576115
1136	32	2025-11-17	100	200	100	200	100	0	0	100	0	[]	800	1	2025-11-17 08:10:41.529273	2025-11-17 08:10:41.529276
1137	47	2025-11-17	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-17 08:15:39.952771	2025-11-17 08:15:39.952775
1082	44	2025-11-10	200	200	100	0	100	0	0	0	0	[]	600	5	2025-11-10 08:53:45.890184	2025-11-10 08:53:45.890189
1126	47	2025-11-14	100	100	100	100	0	0	0	0	0	[]	400	6	2025-11-14 08:17:41.2977	2025-11-14 08:17:41.297705
1072	36	2025-11-10	100	100	100	0	100	0	0	100	-400	[{"id": 1, "subject": "연필 구매", "points": -600, "reason": "연필 2개 구매", "created_by": "dev_hoon", "created_at": "2025-11-10 07:48:33"}, {"id": 2, "subject": "추가 학습", "points": 200, "reason": "쎈", "created_by": "sowo_1", "created_at": "2025-11-10 08:54:48"}]	100	1	2025-11-10 07:48:33.052174	2025-11-10 08:57:55.295509
1083	31	2025-11-11	200	200	100	200	0	100	0	100	0	[]	900	5	2025-11-11 06:33:51.121544	2025-11-11 06:33:51.121548
1084	40	2025-11-11	200	100	100	200	0	100	0	0	0	[]	700	1	2025-11-11 06:57:03.791003	2025-11-11 06:57:03.791006
1085	35	2025-11-11	200	100	100	200	0	100	0	100	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-11 07:40:20"}]	700	5	2025-11-11 07:39:49.428702	2025-11-11 07:40:20.18514
1086	43	2025-11-11	200	200	100	200	0	100	0	0	0	[]	800	5	2025-11-11 07:41:28.149624	2025-11-11 07:41:28.149628
1087	46	2025-11-11	200	100	100	200	0	100	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-11 07:54:38"}]	500	5	2025-11-11 07:54:08.636039	2025-11-11 07:54:38.624707
1088	59	2025-11-11	100	0	100	200	0	100	0	0	0	[]	500	5	2025-11-11 07:55:34.476732	2025-11-11 07:55:34.476737
1089	50	2025-11-11	200	100	100	200	0	100	0	0	0	[]	700	1	2025-11-11 07:58:52.872274	2025-11-11 07:58:52.872278
1090	32	2025-11-11	200	200	100	200	0	100	0	100	-400	[{"id": 1, "subject": "프린트", "points": -400, "reason": "구매", "created_by": "dev_hoon", "created_at": "2025-11-11 08:04:29"}]	500	1	2025-11-11 08:03:56.39872	2025-11-11 08:04:29.564253
1091	54	2025-11-11	100	100	100	200	0	100	0	0	0	[]	600	1	2025-11-11 08:44:45.525008	2025-11-11 08:44:45.525011
1092	41	2025-11-11	100	200	100	100	0	100	0	0	0	[]	600	5	2025-11-11 08:59:49.41243	2025-11-11 08:59:49.412435
1093	31	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	1	2025-11-12 04:41:19.576031	2025-11-12 04:41:19.576035
1094	35	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-12 04:48:52.429546	2025-11-12 04:48:52.429549
1095	59	2025-11-12	0	0	0	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-12 06:38:14"}]	100	6	2025-11-12 06:22:11.605189	2025-11-12 06:38:14.590324
1115	37	2025-11-13	0	100	100	0	0	0	0	0	300	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-13 08:24:00"}, {"id": 2, "subject": "추가학습", "points": 500, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-13 08:26:21"}]	500	6	2025-11-13 08:24:00.910694	2025-11-13 08:26:21.746343
1096	32	2025-11-12	0	0	0	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-12 06:39:49"}]	100	6	2025-11-12 06:37:03.545802	2025-11-12 06:39:49.80935
1097	33	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	1	2025-11-12 07:35:04.408288	2025-11-12 07:35:04.408293
1098	41	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	1	2025-11-12 07:35:48.94359	2025-11-12 07:35:48.943594
1099	54	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-12 08:00:35.62547	2025-11-12 08:00:35.625474
1100	43	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-12 08:01:29.476841	2025-11-12 08:01:29.476846
1101	50	2025-11-12	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-12 08:02:53.227442	2025-11-12 08:02:53.227446
1102	39	2025-11-12	0	0	100	0	0	0	0	0	0	[]	100	5	2025-11-12 08:37:22.126489	2025-11-12 08:37:22.126492
1103	43	2025-11-13	200	200	100	200	0	0	0	0	-500	[{"id": 1, "subject": "지우개", "points": -500, "reason": "지우개 구매", "created_by": "sowo_1", "created_at": "2025-11-13 05:41:07"}]	200	5	2025-11-13 05:39:45.394903	2025-11-13 05:41:07.290986
1104	40	2025-11-13	200	100	100	200	0	0	0	0	0	[]	600	1	2025-11-13 06:22:33.508692	2025-11-13 06:22:33.508696
1105	49	2025-11-13	200	200	100	0	0	0	0	0	0	[]	500	6	2025-11-13 06:29:10.930664	2025-11-13 06:29:10.930667
1106	42	2025-11-13	100	0	100	0	0	0	0	0	0	[]	200	6	2025-11-13 06:37:06.233171	2025-11-13 06:37:06.233174
1107	48	2025-11-13	100	100	100	200	0	0	0	0	600	[{"id": 1, "subject": "11일포인트", "points": 600, "reason": "11일포인트", "created_by": "teacher", "created_at": "2025-11-13 06:39:21"}]	1100	6	2025-11-13 06:39:21.649343	2025-11-13 06:39:59.537788
1108	59	2025-11-13	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-13 07:03:30.423469	2025-11-13 07:03:30.423473
1109	32	2025-11-13	100	100	100	200	0	0	0	100	0	[]	600	1	2025-11-13 07:07:58.197165	2025-11-13 07:07:58.197168
1110	41	2025-11-13	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-13 07:08:57.052467	2025-11-13 07:08:57.052471
1111	44	2025-11-13	100	100	100	0	0	0	0	0	0	[]	300	5	2025-11-13 07:32:40.38907	2025-11-13 07:32:40.389073
1112	31	2025-11-13	200	200	100	200	0	0	0	100	0	[]	800	1	2025-11-13 07:57:34.703267	2025-11-13 07:57:34.70327
1113	46	2025-11-13	100	100	100	200	0	0	0	0	0	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-13 08:00:52"}, {"id": 2, "subject": "추가학습", "points": 200, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-13 08:01:19"}]	500	6	2025-11-13 07:59:26.152791	2025-11-13 08:01:19.404339
1114	54	2025-11-13	200	100	100	200	0	0	0	0	0	[]	600	1	2025-11-13 08:12:57.008145	2025-11-13 08:12:57.008149
1117	33	2025-11-13	200	100	100	200	0	0	0	100	0	[]	700	1	2025-11-13 08:29:29.848447	2025-11-13 08:29:29.84845
1116	39	2025-11-13	0	100	100	0	0	0	0	0	300	[{"id": 1, "subject": "추가학습", "points": 300, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-13 08:29:30"}]	500	6	2025-11-13 08:28:59.642771	2025-11-13 08:29:30.509599
1118	40	2025-11-14	200	200	100	200	0	0	0	0	0	[]	700	1	2025-11-14 05:27:32.245746	2025-11-14 05:27:32.245749
1119	49	2025-11-14	200	100	100	200	0	0	0	0	0	[]	600	6	2025-11-14 06:12:47.731018	2025-11-14 06:12:47.731021
1120	35	2025-11-14	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-14 06:59:11.899222	2025-11-14 06:59:11.899225
1121	32	2025-11-14	200	200	100	200	0	0	0	100	0	[]	800	1	2025-11-14 07:04:22.185652	2025-11-14 07:04:22.185655
1122	31	2025-11-14	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-14 07:48:07.352784	2025-11-14 07:48:07.352787
1123	50	2025-11-14	100	100	100	200	0	0	0	0	0	[]	500	6	2025-11-14 07:57:39.315407	2025-11-14 07:57:39.315411
1124	33	2025-11-14	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-14 08:04:16.043577	2025-11-14 08:04:16.043579
1125	42	2025-11-14	0	200	0	0	0	0	0	0	0	[]	200	6	2025-11-14 08:07:33.130929	2025-11-14 08:07:33.130933
1127	54	2025-11-14	200	200	100	200	0	0	0	0	0	[]	700	5	2025-11-14 08:20:56.588823	2025-11-14 08:20:56.588827
1128	46	2025-11-14	100	100	100	200	0	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-14 08:30:43"}]	300	5	2025-11-14 08:29:47.260447	2025-11-14 08:30:43.375009
1129	31	2025-11-17	200	200	100	200	100	0	0	100	0	[]	900	1	2025-11-17 05:38:23.321431	2025-11-17 05:38:23.321434
1130	49	2025-11-17	200	100	100	200	0	0	0	0	200	[{"id": 1, "subject": "추가학습", "points": 200, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-17 05:52:08"}]	800	6	2025-11-17 05:51:21.211113	2025-11-17 05:52:08.012607
1131	43	2025-11-17	200	200	100	200	100	0	0	0	0	[]	800	5	2025-11-17 06:31:42.494899	2025-11-17 06:31:42.494902
1132	42	2025-11-17	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-17 06:48:05.625777	2025-11-17 06:48:05.625781
1133	45	2025-11-17	200	100	100	200	100	0	0	0	0	[]	700	6	2025-11-17 07:34:02.229983	2025-11-17 07:34:02.229984
1134	54	2025-11-17	200	100	100	200	100	0	0	0	0	[]	700	1	2025-11-17 07:57:34.584209	2025-11-17 07:57:34.584212
1138	35	2025-11-17	200	100	100	200	100	0	0	100	0	[]	800	5	2025-11-17 08:35:51.502975	2025-11-17 08:35:51.502979
1139	36	2025-11-17	100	100	100	0	100	0	0	0	300	[{"id": 1, "subject": "11/13 포인트", "points": 300, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-17 08:55:33"}]	700	5	2025-11-17 08:54:27.894552	2025-11-17 08:55:33.870985
1140	31	2025-11-18	200	100	100	200	0	100	0	100	0	[]	800	1	2025-11-18 06:24:22.627407	2025-11-18 06:24:22.62741
1142	59	2025-11-18	200	0	100	200	0	100	0	0	0	[]	600	5	2025-11-18 07:02:48.320807	2025-11-18 07:02:48.32081
1143	32	2025-11-18	100	200	100	200	0	100	0	100	0	[]	800	1	2025-11-18 07:43:11.905602	2025-11-18 07:43:11.905607
1144	43	2025-11-18	200	200	100	200	0	100	0	0	0	[]	800	5	2025-11-18 07:43:27.704088	2025-11-18 07:43:27.704091
1141	40	2025-11-18	200	100	100	200	0	100	0	0	-900	[{"id": 1, "subject": "연필", "points": -900, "reason": "연필 3개 구매", "created_by": "dev_hoon", "created_at": "2025-11-18 06:29:24"}]	-200	1	2025-11-18 06:29:24.545912	2025-11-18 07:49:26.692253
1146	50	2025-11-18	100	100	100	200	0	100	0	0	0	[]	600	6	2025-11-18 07:58:42.896503	2025-11-18 07:58:42.896506
1147	46	2025-11-18	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-18 07:59:39.133256	2025-11-18 07:59:39.133258
1180	48	2025-11-21	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-21 07:41:19.39505	2025-11-21 07:41:21.81403
1145	44	2025-11-18	100	100	100	0	0	100	0	0	500	[{"id": 1, "subject": "추가학습", "points": 500, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-18 08:22:03"}]	900	1	2025-11-18 07:43:59.510458	2025-11-18 08:22:03.74302
1148	48	2025-11-18	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-18 08:26:31.93259	2025-11-18 08:26:31.932594
1149	38	2025-11-18	100	0	0	0	0	100	0	0	0	[]	200	1	2025-11-18 08:29:02.054199	2025-11-18 08:29:02.054201
1150	47	2025-11-18	100	100	100	200	0	100	0	0	0	[]	600	6	2025-11-18 08:31:09.469745	2025-11-18 08:31:09.469747
1152	54	2025-11-18	200	100	100	200	0	100	0	0	0	[]	700	5	2025-11-18 08:51:57.002642	2025-11-18 08:51:57.002645
1151	33	2025-11-18	200	200	100	200	0	100	0	100	700	[{"id": 1, "subject": "11/17 포인트", "points": 700, "reason": "포인트 입력 누락", "created_by": "dev_hoon", "created_at": "2025-11-18 08:51:16"}]	1600	1	2025-11-18 08:51:16.652683	2025-11-18 08:52:09.5708
1153	31	2025-11-19	200	200	100	200	0	0	0	100	0	[]	800	1	2025-11-19 04:46:29.16917	2025-11-19 04:46:29.169174
1154	40	2025-11-19	200	100	100	200	0	0	0	0	0	[]	600	1	2025-11-19 05:36:30.134746	2025-11-19 05:36:30.134749
1181	46	2025-11-21	100	100	100	200	0	100	0	0	0	[]	600	6	2025-11-21 07:42:46.843336	2025-11-21 07:42:46.843338
1156	35	2025-11-19	200	200	100	200	0	0	0	100	900	[{"id": 1, "subject": "11/18 포인트", "points": 900, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-19 05:52:53"}]	1700	5	2025-11-19 05:52:19.535781	2025-11-19 05:52:53.256835
1157	43	2025-11-19	200	200	100	200	0	0	0	0	0	[]	700	5	2025-11-19 05:55:06.467427	2025-11-19 05:55:07.346059
1158	32	2025-11-19	0	0	0	200	0	0	0	0	0	[]	200	5	2025-11-19 07:36:26.160304	2025-11-19 07:36:26.160306
1159	48	2025-11-19	200	200	100	200	0	0	0	0	0	[]	700	6	2025-11-19 07:42:30.701564	2025-11-19 07:42:40.716275
1160	33	2025-11-19	200	100	100	200	0	0	0	100	0	[]	700	1	2025-11-19 07:42:55.398238	2025-11-19 07:42:55.398242
1161	42	2025-11-19	100	100	100	0	0	0	0	0	0	[]	300	6	2025-11-19 07:52:57.367516	2025-11-19 07:52:57.36752
1162	36	2025-11-19	100	0	0	0	0	0	0	0	0	[]	100	5	2025-11-19 07:56:41.746886	2025-11-19 07:56:41.746889
1163	41	2025-11-19	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-19 08:15:55.660191	2025-11-19 08:15:55.660194
1164	46	2025-11-19	200	100	100	200	0	0	0	0	0	[]	600	6	2025-11-19 08:28:53.42558	2025-11-19 08:28:53.425584
1165	47	2025-11-19	100	100	100	200	0	0	0	0	0	[]	500	6	2025-11-19 08:29:38.480767	2025-11-19 08:29:38.48077
1166	44	2025-11-19	200	200	100	0	0	0	0	0	500	[{"id": 1, "subject": "추가학습", "points": 500, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-19 08:37:24"}]	1000	6	2025-11-19 08:36:12.501463	2025-11-19 08:37:24.607061
1167	39	2025-11-19	100	0	100	0	0	0	0	0	0	[]	200	6	2025-11-19 08:38:18.556572	2025-11-19 08:38:18.556574
1155	59	2025-11-19	200	0	100	200	0	0	0	0	0	[]	500	5	2025-11-19 05:51:42.105935	2025-11-19 08:52:27.232329
1168	40	2025-11-20	200	100	100	200	0	0	0	0	0	[]	600	1	2025-11-20 06:00:08.467352	2025-11-20 06:00:08.467356
1169	42	2025-11-20	100	100	100	0	0	0	0	0	100	[{"id": 1, "subject": "추가학습", "points": 100, "reason": "추가학습", "created_by": "teacher", "created_at": "2025-11-20 06:39:27"}]	400	6	2025-11-20 06:38:35.133926	2025-11-20 06:39:27.797283
1170	35	2025-11-20	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-20 07:34:56.49182	2025-11-20 07:34:56.491824
1171	41	2025-11-20	200	100	100	200	0	0	0	0	0	[]	600	5	2025-11-20 07:54:19.340889	2025-11-20 07:54:19.340891
1172	47	2025-11-20	100	100	100	200	0	0	0	0	0	[]	500	6	2025-11-20 08:06:23.824785	2025-11-20 08:06:23.824789
1173	33	2025-11-20	200	100	100	200	0	0	0	100	0	[]	700	5	2025-11-20 08:22:05.47168	2025-11-20 08:22:05.471683
1174	40	2025-11-21	200	100	100	200	0	100	0	0	0	[]	700	1	2025-11-21 05:47:31.017764	2025-11-21 05:47:31.017768
1175	59	2025-11-21	200	0	100	200	0	100	0	0	0	[]	600	5	2025-11-21 06:21:16.838105	2025-11-21 06:21:16.838108
1176	43	2025-11-21	200	200	100	200	0	100	0	0	0	[]	800	5	2025-11-21 06:55:47.736924	2025-11-21 06:55:47.736927
1177	35	2025-11-21	100	100	100	200	0	100	0	100	0	[]	700	5	2025-11-21 07:01:26.543695	2025-11-21 07:01:26.543699
1178	44	2025-11-21	0	0	0	0	0	100	0	0	0	[]	100	5	2025-11-21 07:36:46.40511	2025-11-21 07:36:46.405112
1179	50	2025-11-21	200	100	100	200	0	100	0	0	0	[]	700	6	2025-11-21 07:39:55.883711	2025-11-21 07:39:56.625082
1182	32	2025-11-21	200	200	100	200	0	100	0	0	400	[{"id": 1, "subject": "추가포인트", "points": 400, "reason": "어제 날짜 + 국어 더 풀음", "created_by": "dev_hoon", "created_at": "2025-11-21 08:04:43"}]	1200	1	2025-11-21 08:03:58.595659	2025-11-21 08:04:43.728125
1183	31	2025-11-21	200	200	100	200	0	100	0	100	400	[{"id": 1, "subject": "추가포인트", "points": 400, "reason": "어제 날짜 + 국어 더 풀음", "created_by": "dev_hoon", "created_at": "2025-11-21 08:26:23"}]	1300	1	2025-11-21 08:24:45.068864	2025-11-21 08:26:23.555336
1184	31	2025-11-24	100	200	100	200	100	0	0	100	0	[]	800	5	2025-11-24 06:02:31.544591	2025-11-24 06:02:31.544595
1185	43	2025-11-24	200	200	100	200	100	0	0	0	0	[]	800	5	2025-11-24 06:16:33.571954	2025-11-24 06:16:33.571958
1186	42	2025-11-24	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-24 06:33:37.94515	2025-11-24 06:33:37.945152
1187	49	2025-11-24	200	100	100	100	0	0	0	0	0	[]	500	6	2025-11-24 06:41:10.511439	2025-11-24 06:41:10.511442
1188	40	2025-11-24	200	200	100	200	100	0	0	0	0	[]	800	5	2025-11-24 06:42:37.850828	2025-11-24 06:42:37.85083
1189	46	2025-11-24	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-24 06:48:32.736123	2025-11-24 06:48:32.736124
1190	45	2025-11-24	100	200	100	200	100	0	0	0	0	[]	700	6	2025-11-24 06:49:26.535823	2025-11-24 06:49:26.535826
1191	59	2025-11-24	200	0	100	200	100	0	0	0	0	[]	600	5	2025-11-24 07:42:46.869533	2025-11-24 07:42:46.869536
1192	48	2025-11-24	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-24 07:44:28.403122	2025-11-24 07:44:28.403124
1193	32	2025-11-24	200	200	100	200	100	0	0	100	0	[]	900	6	2025-11-24 07:52:42.518896	2025-11-24 07:52:42.518899
1194	47	2025-11-24	100	100	100	200	100	0	0	0	0	[]	600	6	2025-11-24 07:59:08.524227	2025-11-24 07:59:10.734498
1195	33	2025-11-24	200	200	100	200	100	0	0	100	0	[]	900	6	2025-11-24 08:21:24.547261	2025-11-24 08:21:24.547265
1196	50	2025-11-24	100	200	100	200	100	0	0	0	0	[]	700	6	2025-11-24 08:25:23.813604	2025-11-24 08:25:23.813607
1197	37	2025-11-24	200	200	100	0	100	0	0	0	0	[]	600	6	2025-11-24 08:29:34.504053	2025-11-24 08:29:34.504055
1198	54	2025-11-24	100	100	100	200	100	0	0	0	0	[]	600	5	2025-11-24 08:31:13.124916	2025-11-24 08:31:13.124918
1199	44	2025-11-24	100	100	100	0	100	0	0	0	100	[{"id": 1, "subject": "11/21 포인트", "points": 100, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-24 08:35:27"}]	500	5	2025-11-24 08:34:20.77826	2025-11-24 08:35:27.784961
1200	39	2025-11-24	200	0	100	0	100	0	0	0	5000	[{"id": 1, "subject": "미기입포인트", "points": 5000, "reason": "수첩교환미기입", "created_by": "teacher", "created_at": "2025-11-24 08:35:22"}]	5400	6	2025-11-24 08:35:22.196232	2025-11-24 08:35:47.499019
1233	39	2025-11-26	200	200	100	0	0	0	0	0	0	[]	500	6	2025-11-26 08:39:05.773251	2025-11-26 08:39:05.773255
1234	40	2025-11-27	100	200	100	200	0	0	0	0	0	[]	600	5	2025-11-27 05:37:35.328567	2025-11-27 05:37:35.328569
1201	34	2025-11-24	200	200	100	100	100	0	0	100	2600	[{"id": 1, "subject": "11/18 포인트", "points": 900, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-24 08:54:21"}, {"id": 2, "subject": "11/19 포인트 ", "points": 800, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-24 08:55:00"}, {"id": 3, "subject": "11/21 포인트", "points": 900, "reason": "포인트 누락", "created_by": "sowo_1", "created_at": "2025-11-24 08:55:51"}]	3400	5	2025-11-24 08:54:21.747787	2025-11-24 08:56:54.772641
1202	49	2025-11-25	200	100	100	0	0	0	0	0	0	[]	400	6	2025-11-25 05:35:30.245623	2025-11-25 05:35:30.245625
1203	35	2025-11-25	200	0	0	200	0	0	0	100	0	[]	500	6	2025-11-25 05:41:06.372751	2025-11-25 05:41:06.372753
1204	31	2025-11-25	200	0	0	200	0	0	0	100	0	[]	500	6	2025-11-25 05:41:40.726173	2025-11-25 05:41:40.726177
1205	45	2025-11-25	200	0	0	200	0	0	0	0	0	[]	400	6	2025-11-25 06:20:36.273781	2025-11-25 06:20:36.273785
1206	46	2025-11-25	200	100	0	200	0	0	0	0	0	[]	500	6	2025-11-25 06:21:09.646048	2025-11-25 06:21:09.646052
1207	40	2025-11-25	100	0	100	200	0	0	0	0	0	[]	400	6	2025-11-25 06:21:43.56481	2025-11-25 06:21:43.564813
1208	43	2025-11-25	100	0	0	200	0	0	0	0	0	[]	300	6	2025-11-25 06:22:20.4715	2025-11-25 06:22:20.471504
1209	50	2025-11-25	200	100	100	200	0	0	0	0	500	[{"id": 1, "subject": "도우미", "points": 500, "reason": "도우미", "created_by": "teacher", "created_at": "2025-11-25 07:23:40"}]	1100	6	2025-11-25 07:22:38.649333	2025-11-25 07:23:40.261084
1210	47	2025-11-25	200	0	0	200	0	0	0	0	0	[]	400	6	2025-11-25 07:29:22.222937	2025-11-25 07:29:22.222939
1211	32	2025-11-25	200	100	100	200	0	0	0	100	0	[]	700	6	2025-11-25 07:32:37.071234	2025-11-25 07:32:37.071238
1212	54	2025-11-25	100	0	100	200	0	0	0	0	0	[]	400	6	2025-11-25 08:00:01.07168	2025-11-25 08:00:01.071682
1213	44	2025-11-25	100	100	0	0	0	0	0	0	0	[]	200	6	2025-11-25 08:04:40.366258	2025-11-25 08:04:40.36626
1214	38	2025-11-25	200	100	100	100	0	0	0	0	0	[]	500	6	2025-11-25 08:14:28.974284	2025-11-25 08:14:28.974287
1215	59	2025-11-25	200	0	100	200	0	0	0	0	0	[]	500	6	2025-11-25 08:17:53.732699	2025-11-25 08:17:53.732701
1216	37	2025-11-25	200	100	100	100	0	0	0	0	0	[]	500	6	2025-11-25 08:20:41.476932	2025-11-25 08:20:41.476934
1217	48	2025-11-25	200	0	0	200	0	0	0	0	0	[]	400	6	2025-11-25 08:26:15.501888	2025-11-25 08:26:15.501892
1218	31	2025-11-26	200	0	0	200	0	0	0	100	0	[]	500	6	2025-11-26 04:54:04.381458	2025-11-26 04:54:04.381461
1219	35	2025-11-26	100	100	0	200	0	0	0	100	0	[]	500	5	2025-11-26 05:37:03.450527	2025-11-26 05:37:03.45053
1220	40	2025-11-26	100	0	100	200	0	0	0	0	0	[]	400	5	2025-11-26 05:38:55.031961	2025-11-26 05:38:55.031965
1221	50	2025-11-26	200	200	100	200	0	0	0	0	0	[]	700	6	2025-11-26 05:52:30.169846	2025-11-26 05:52:30.169848
1222	33	2025-11-26	200	100	100	200	0	0	0	100	0	[]	700	5	2025-11-26 07:28:58.944272	2025-11-26 07:28:58.944275
1224	32	2025-11-26	100	100	100	200	0	0	0	100	0	[]	600	6	2025-11-26 07:38:47.969194	2025-11-26 07:38:47.969198
1223	43	2025-11-26	200	200	100	200	0	0	0	0	-100	[{"id": 1, "subject": "포인트 오류", "points": -100, "reason": "포인트 오류", "created_by": "sowo_1", "created_at": "2025-11-26 07:40:06"}]	600	6	2025-11-26 07:33:32.953402	2025-11-26 07:40:06.631924
1225	46	2025-11-26	100	100	100	200	0	0	0	0	0	[]	500	6	2025-11-26 07:56:21.826456	2025-11-26 07:56:21.826458
1226	45	2025-11-26	200	200	100	200	0	0	0	0	0	[]	700	6	2025-11-26 07:57:01.57462	2025-11-26 07:57:01.574622
1227	59	2025-11-26	200	0	100	200	0	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-26 07:58:24"}]	300	5	2025-11-26 07:57:43.540259	2025-11-26 07:58:24.869706
1228	48	2025-11-26	200	200	100	200	0	0	0	0	0	[]	700	6	2025-11-26 08:04:21.096056	2025-11-26 08:04:21.09606
1229	44	2025-11-26	200	100	100	0	0	0	0	0	200	[{"id": 1, "subject": "5학년 수학", "points": 200, "reason": "5학년 수학", "created_by": "sowo_1", "created_at": "2025-11-26 08:23:33"}]	600	5	2025-11-26 08:22:52.728604	2025-11-26 08:23:33.360881
1230	52	2025-11-26	0	0	0	0	0	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-26 08:24:17"}]	-200	5	2025-11-26 08:24:17.356998	2025-11-26 08:24:17.357
1231	54	2025-11-26	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-26 08:25:40.641921	2025-11-26 08:25:40.641926
1232	34	2025-11-26	200	200	100	0	0	0	0	0	500	[{"id": 1, "subject": "추가 포인트", "points": 500, "reason": "추가 포인트 (쎈)", "created_by": "sowo_1", "created_at": "2025-11-26 08:35:35"}]	1000	5	2025-11-26 08:34:52.797548	2025-11-26 08:35:35.853672
1243	31	2025-11-27	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-27 08:03:42.566721	2025-11-27 08:03:42.566725
1237	43	2025-11-27	200	100	100	200	0	0	0	0	0	[]	600	5	2025-11-27 06:08:34.512596	2025-11-27 06:08:34.512598
1238	50	2025-11-27	200	100	100	200	0	0	0	0	0	[]	600	6	2025-11-27 06:18:00.552452	2025-11-27 06:18:00.552455
1239	48	2025-11-27	200	100	100	200	0	0	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-27 06:58:03"}]	400	6	2025-11-27 06:55:50.081091	2025-11-27 06:58:03.206724
1240	45	2025-11-27	200	100	100	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-27 07:03:06"}]	500	6	2025-11-27 07:01:52.305624	2025-11-27 07:03:06.1603
1236	59	2025-11-27	200	0	100	200	0	0	0	0	-100	[{"id": 1, "subject": "프린트", "points": -100, "reason": "프린트", "created_by": "sowo_1", "created_at": "2025-11-27 07:03:26"}]	400	5	2025-11-27 06:04:56.793238	2025-11-27 07:03:26.472922
1241	46	2025-11-27	200	100	100	200	0	0	0	0	0	[]	600	6	2025-11-27 07:04:47.89636	2025-11-27 07:04:47.896363
1242	32	2025-11-27	200	100	100	200	0	0	0	100	0	[]	700	6	2025-11-27 07:37:11.28657	2025-11-27 07:37:11.286574
1235	36	2025-11-27	100	0	0	0	0	0	0	0	600	[{"id": 1, "subject": "24일", "points": 300, "reason": "미기입포인트", "created_by": "teacher", "created_at": "2025-11-27 05:47:04"}, {"id": 2, "subject": "25일", "points": 300, "reason": "미기입포인트", "created_by": "teacher", "created_at": "2025-11-27 05:47:47"}]	700	6	2025-11-27 05:47:04.902279	2025-11-27 07:51:02.292849
1244	44	2025-11-27	200	100	100	0	0	0	0	0	200	[{"id": 1, "subject": "5학년 수학", "points": 200, "reason": "수학", "created_by": "sowo_1", "created_at": "2025-11-27 08:07:35"}]	600	5	2025-11-27 08:06:22.771224	2025-11-27 08:07:35.974021
1245	38	2025-11-27	200	200	0	0	0	0	0	0	0	[]	400	6	2025-11-27 08:13:00.79434	2025-11-27 08:13:00.794344
1246	33	2025-11-27	200	200	100	200	0	0	0	100	0	[]	800	5	2025-11-27 08:23:20.846717	2025-11-27 08:23:20.846719
1247	39	2025-11-27	0	0	100	0	0	0	0	0	0	[]	100	6	2025-11-27 08:37:50.657363	2025-11-27 08:37:50.657365
1248	41	2025-11-27	100	100	100	200	0	0	0	0	0	[]	500	5	2025-11-27 08:43:34.196018	2025-11-27 08:43:34.196021
1249	59	2025-11-28	100	0	100	200	0	100	0	0	0	[]	500	5	2025-11-28 06:09:02.741028	2025-11-28 06:09:02.741031
1250	40	2025-11-28	100	200	100	200	0	100	0	0	0	[]	700	5	2025-11-28 06:35:09.792655	2025-11-28 06:35:09.792659
1251	43	2025-11-28	200	200	100	200	0	100	0	0	0	[]	800	5	2025-11-28 06:37:43.804185	2025-11-28 06:37:43.804187
1252	35	2025-11-28	200	100	100	200	0	100	0	100	0	[]	800	6	2025-11-28 06:52:08.329271	2025-11-28 06:52:08.329273
1253	48	2025-11-28	100	100	100	200	0	100	0	0	-300	[{"id": 1, "subject": "프린트", "points": -300, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-28 07:04:22"}]	300	6	2025-11-28 07:03:22.840582	2025-11-28 07:04:22.708917
1254	46	2025-11-28	200	100	100	200	0	100	0	0	-200	[{"id": 1, "subject": "프린트", "points": -200, "reason": "프린트", "created_by": "teacher", "created_at": "2025-11-28 07:07:13"}]	500	6	2025-11-28 07:05:56.440692	2025-11-28 07:07:13.097758
1255	49	2025-11-28	200	200	100	0	0	100	0	0	600	[{"id": 1, "subject": "추가학습", "points": 600, "reason": "추가", "created_by": "teacher", "created_at": "2025-11-28 07:41:03"}]	1200	6	2025-11-28 07:39:54.841608	2025-11-28 07:41:03.716528
1256	44	2025-11-28	200	200	100	0	0	100	0	0	500	[{"id": 1, "subject": "추가학습", "points": 500, "reason": "추가", "created_by": "teacher", "created_at": "2025-11-28 07:49:22"}]	1100	6	2025-11-28 07:48:26.526852	2025-11-28 07:49:22.901738
1257	31	2025-11-28	200	200	100	200	0	100	0	100	0	[]	900	6	2025-11-28 07:58:19.006297	2025-11-28 07:58:19.006299
1258	32	2025-11-28	100	200	100	200	0	100	0	100	0	[]	800	6	2025-11-28 07:59:28.190046	2025-11-28 07:59:28.190048
1259	47	2025-11-28	100	100	100	200	0	100	0	0	0	[]	600	6	2025-11-28 08:25:01.214259	2025-11-28 08:25:01.214262
1260	31	2025-12-01	200	200	100	200	100	0	0	100	0	[]	900	1	2025-12-01 05:50:14.717332	2025-12-01 05:50:14.717334
1261	43	2025-12-01	200	200	100	200	100	0	0	0	0	[]	800	1	2025-12-01 06:04:09.581893	2025-12-01 06:04:09.581897
1262	40	2025-12-01	100	100	100	200	100	0	0	0	0	[]	600	1	2025-12-01 06:05:46.306446	2025-12-01 06:05:46.306448
1263	50	2025-12-01	100	200	100	200	100	0	0	0	0	[]	700	6	2025-12-01 06:35:10.774878	2025-12-01 06:35:10.77488
1264	49	2025-12-01	200	100	100	200	0	0	0	0	0	[]	600	6	2025-12-01 06:43:51.585312	2025-12-01 06:43:51.585315
1265	32	2025-12-01	200	200	100	200	100	0	0	100	0	[]	900	1	2025-12-01 07:01:22.585105	2025-12-01 07:01:22.585108
1266	48	2025-12-01	200	100	100	200	100	0	0	0	0	[]	700	6	2025-12-01 07:42:00.022781	2025-12-01 07:42:01.654852
1267	46	2025-12-01	200	100	100	200	100	0	0	0	0	[]	700	6	2025-12-01 07:43:53.032772	2025-12-01 07:43:53.032774
1268	47	2025-12-01	200	100	100	200	100	0	0	0	0	[]	700	6	2025-12-01 07:49:43.722032	2025-12-01 07:49:43.722034
1270	35	2025-12-01	200	100	100	200	100	0	0	100	0	[]	800	6	2025-12-01 07:56:20.197837	2025-12-01 07:56:20.197838
1271	45	2025-12-01	200	100	100	200	100	0	0	0	0	[]	700	1	2025-12-01 08:00:17.484897	2025-12-01 08:00:17.484902
1272	41	2025-12-01	100	100	100	200	0	0	0	0	0	[]	500	1	2025-12-01 08:17:19.318957	2025-12-01 08:17:19.318959
1273	33	2025-12-01	100	200	100	200	100	0	0	100	0	[]	800	1	2025-12-01 08:26:38.49128	2025-12-01 08:26:38.491284
1274	59	2025-12-01	200	0	100	200	100	0	0	0	0	[]	600	1	2025-12-01 08:33:40.791815	2025-12-01 08:33:40.791817
1269	36	2025-12-01	100	100	100	0	0	0	0	0	-300	[{"id": 1, "subject": "연필 ", "points": -300, "reason": "연필", "created_by": "teacher", "created_at": "2025-12-01 07:51:31"}]	0	6	2025-12-01 07:51:31.599163	2025-12-01 08:50:15.540578
1275	34	2025-12-01	200	100	100	200	100	0	0	100	0	[]	800	1	2025-12-01 09:02:31.759459	2025-12-01 09:02:31.759461
1276	39	2025-12-02	100	100	0	0	0	0	0	0	0	[]	200	6	2025-12-02 04:51:02.855455	2025-12-02 04:51:02.855458
1277	49	2025-12-02	0	100	0	0	0	0	0	0	0	[]	100	6	2025-12-02 05:40:15.591925	2025-12-02 05:40:15.591926
1278	31	2025-12-02	200	200	100	200	0	100	0	100	0	[]	900	1	2025-12-02 05:48:49.916216	2025-12-02 05:48:49.916218
1279	40	2025-12-02	100	200	100	200	0	100	0	0	0	[]	700	1	2025-12-02 06:25:47.18113	2025-12-02 06:25:47.181134
1280	43	2025-12-02	200	200	100	200	0	100	0	0	0	[]	800	5	2025-12-02 06:25:56.767546	2025-12-02 06:25:56.767548
1281	46	2025-12-02	200	100	100	200	0	100	0	0	0	[]	700	5	2025-12-02 06:44:37.199606	2025-12-02 06:44:37.19961
1282	45	2025-12-02	200	100	100	200	0	100	0	0	0	[]	700	1	2025-12-02 06:45:23.126533	2025-12-02 06:45:23.126534
1283	35	2025-12-02	200	200	100	200	0	100	0	100	0	[]	900	5	2025-12-02 06:57:59.653748	2025-12-02 06:57:59.65375
1284	47	2025-12-02	100	100	100	200	0	100	0	0	0	[]	600	6	2025-12-02 07:52:37.859283	2025-12-02 07:52:37.859285
1285	32	2025-12-02	200	100	100	200	0	100	0	100	0	[]	800	1	2025-12-02 07:59:25.624121	2025-12-02 07:59:25.624124
1286	48	2025-12-02	200	200	100	0	0	100	0	0	0	[]	600	1	2025-12-02 08:48:27.327962	2025-12-02 08:48:27.327963
1287	54	2025-12-02	100	100	100	200	0	100	0	0	0	[]	600	1	2025-12-02 08:52:04.374305	2025-12-02 08:52:04.37431
1288	59	2025-12-02	200	0	100	0	0	100	0	0	0	[]	400	5	2025-12-02 08:53:50.615107	2025-12-02 08:54:12.423816
1289	33	2025-12-02	200	200	100	200	0	100	0	100	0	[]	900	1	2025-12-02 08:54:53.829808	2025-12-02 08:54:53.82981
1290	43	2025-12-03	200	100	0	200	0	0	0	0	0	[]	500	5	2025-12-03 05:11:54.955316	2025-12-03 05:11:54.955318
1291	40	2025-12-03	200	100	0	200	0	0	0	0	0	[]	500	5	2025-12-03 05:12:18.869482	2025-12-03 05:12:18.869486
1292	31	2025-12-03	200	100	0	200	0	0	0	0	0	[]	500	5	2025-12-03 05:12:47.912172	2025-12-03 05:12:47.912175
\.


--
-- Data for Name: learning_record; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.learning_record (id, child_id, date, korean_problems_solved, korean_problems_correct, korean_score, korean_last_page, math_problems_solved, math_problems_correct, math_score, math_last_page, reading_completed, reading_score, total_score, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: notification; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notification (id, title, message, type, priority, target_user_id, target_role, child_id, is_read, is_active, auto_expire, expire_date, created_at, created_by, read_at) FROM stdin;
1	📝 감스트 특이사항 추가	dev_hoon님이 감스트 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	58	f	t	t	2025-10-03 08:22:35.633889	2025-09-30 08:22:35.639816	1	\N
2	📝 노진구 특이사항 추가	dev_hoon님이 노진구 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	40	f	t	t	2025-10-03 08:40:55.818627	2025-09-30 08:40:55.82096	1	\N
6	📝 누룽지 특이사항 추가	dev_hoon님이 누룽지 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	46	f	t	t	2025-10-05 02:34:18.475867	2025-10-02 02:34:18.477403	1	\N
7	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_04-55-09.json, 2025-10-02_04-55-09.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 04:55:09.160339	2025-10-02 04:55:09.162044	1	\N
33	🗑️ 노진구 특이사항 삭제	dev_hoon님이 노진구 아동의 특이사항을 삭제했습니다.	warning	2	\N	\N	40	f	t	t	2025-10-13 03:54:29.223977	2025-10-10 03:54:29.224616	1	\N
4	월간 백업 실패	월간 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	t	t	t	2025-10-07 23:00:59.600238	2025-09-30 23:00:59.601042	1	2025-10-02 05:04:07.338626
3	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	t	t	t	2025-10-07 22:00:59.137529	2025-09-30 22:00:59.139594	1	2025-10-02 05:04:09.59569
8	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_06-39-20.json, 2025-10-02_06-39-20.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 06:39:20.090938	2025-10-02 06:39:20.091546	1	\N
9	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_06-51-25.json, 2025-10-02_06-51-25.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 06:51:25.99167	2025-10-02 06:51:25.992133	1	\N
10	실시간 백업 완료	실시간 백업 완료 - update: 2025-10-02_06-51-26.json, 2025-10-02_06-51-26.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 06:51:26.822122	2025-10-02 06:51:26.822776	1	\N
11	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_06-53-29.json, 2025-10-02_06-53-29.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 06:53:29.767077	2025-10-02 06:53:29.767576	1	\N
12	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-05-49.json, 2025-10-02_08-05-49.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:05:49.06823	2025-10-02 08:05:49.06876	1	\N
13	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-15-05.json, 2025-10-02_08-15-05.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:15:05.396151	2025-10-02 08:15:05.396738	1	\N
14	실시간 백업 완료	실시간 백업 완료 - update: 2025-10-02_08-15-06.json, 2025-10-02_08-15-06.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:15:06.662997	2025-10-02 08:15:06.663774	1	\N
15	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-18-27.json, 2025-10-02_08-18-27.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:18:27.499199	2025-10-02 08:18:27.499669	1	\N
16	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-22-29.json, 2025-10-02_08-22-29.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:22:29.95919	2025-10-02 08:22:29.959771	1	\N
17	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-24-39.json, 2025-10-02_08-24-39.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:24:39.9665	2025-10-02 08:24:39.966933	1	\N
18	실시간 백업 완료	실시간 백업 완료 - manual_update: 2025-10-02_08-25-06.json, 2025-10-02_08-25-06.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:25:06.567187	2025-10-02 08:25:06.567675	1	\N
19	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-26-56.json, 2025-10-02_08-26-56.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:26:56.863752	2025-10-02 08:26:56.864486	1	\N
20	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-32-52.json, 2025-10-02_08-32-52.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:32:52.503807	2025-10-02 08:32:52.504225	1	\N
21	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-42-31.json, 2025-10-02_08-42-31.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:42:31.810708	2025-10-02 08:42:31.811292	1	\N
22	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-45-00.json, 2025-10-02_08-45-00.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:45:00.910572	2025-10-02 08:45:00.911076	1	\N
23	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-47-14.json, 2025-10-02_08-47-14.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:47:14.199158	2025-10-02 08:47:14.199659	1	\N
24	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-02_08-50-55.json, 2025-10-02_08-50-55.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-09 08:50:55.781274	2025-10-02 08:50:55.781947	1	\N
25	🗑️ 누룽지 특이사항 삭제	dev_hoon님이 누룽지 아동의 특이사항을 삭제했습니다.	warning	2	\N	\N	46	f	t	t	2025-10-07 13:56:05.832282	2025-10-04 13:56:05.832783	1	\N
26	실시간 백업 완료	실시간 백업 완료 - manual_update: 2025-10-10_01-50-04.json, 2025-10-10_01-50-04.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 01:50:04.359812	2025-10-10 01:50:04.360285	1	\N
27	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-10_03-27-14.json, 2025-10-10_03-27-14.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 03:27:14.652744	2025-10-10 03:27:14.653175	1	\N
28	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-10_03-44-57.json, 2025-10-10_03-44-57.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 03:44:57.151664	2025-10-10 03:44:57.152272	1	\N
29	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-10_03-48-09.json, 2025-10-10_03-48-09.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 03:48:09.114956	2025-10-10 03:48:09.11566	1	\N
31	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-10_03-53-12.json, 2025-10-10_03-53-12.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 03:53:12.325093	2025-10-10 03:53:12.325757	1	\N
32	📝 민수르 특이사항 추가	dev_hoon님이 민수르 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	53	f	t	t	2025-10-13 03:54:15.230141	2025-10-10 03:54:15.230701	1	\N
37	실시간 백업 완료	실시간 백업 완료 - create: 2025-10-10_07-00-34.json, 2025-10-10_07-00-34.xlsx	backup_success	2	\N	개발자	\N	f	t	t	2025-10-17 07:00:35.001069	2025-10-10 07:00:35.0018	1	\N
52	📝 베이비 특이사항 추가	dev_hoon님이 베이비 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	38	f	t	t	2025-10-17 08:18:35.416703	2025-10-14 08:18:35.417906	1	\N
53	📝 베이비 특이사항 추가	teacher님이 베이비 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	38	f	t	t	2025-10-17 08:32:37.32804	2025-10-14 08:32:37.328697	6	\N
54	🗑️ 베이비 특이사항 삭제	teacher님이 베이비 아동의 특이사항을 삭제했습니다.	warning	2	\N	\N	38	f	t	t	2025-10-17 08:32:51.348683	2025-10-14 08:32:51.349341	6	\N
72	수동 백업 실패	데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-03 06:22:09.856237	2025-10-27 06:22:09.856913	1	\N
73	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-03 22:00:13.053225	2025-10-27 22:00:13.053822	1	\N
57	수동 백업 실패	데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-23 04:14:04.322201	2025-10-16 04:14:04.322925	1	\N
74	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-04 22:00:13.92806	2025-10-28 22:00:13.928612	1	\N
58	📝 예나비 특이사항 추가	teacher님이 예나비 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	37	f	t	t	2025-10-19 08:29:00.559283	2025-10-16 08:29:00.559836	6	\N
59	📝 핸드폰 특이사항 추가	dev_hoon님이 핸드폰 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	36	f	t	t	2025-10-19 08:51:32.62619	2025-10-16 08:51:32.627638	1	\N
60	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-23 22:00:03.011649	2025-10-16 22:00:03.012297	1	\N
61	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-24 22:00:03.785206	2025-10-17 22:00:03.785812	1	\N
62	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-25 22:00:04.617498	2025-10-18 22:00:04.618038	1	\N
63	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-26 22:00:05.412797	2025-10-19 22:00:05.414091	1	\N
64	🗑️ 핸드폰 특이사항 삭제	dev_hoon님이 핸드폰 아동의 특이사항을 삭제했습니다.	warning	2	\N	\N	36	f	t	t	2025-10-23 05:04:22.769791	2025-10-20 05:04:22.770446	1	\N
65	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-27 22:00:06.322892	2025-10-20 22:00:06.323476	1	\N
66	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-28 22:00:07.354558	2025-10-21 22:00:07.355276	1	\N
67	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-29 22:00:08.214609	2025-10-22 22:00:08.21509	1	\N
68	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-30 22:00:09.037056	2025-10-23 22:00:09.037761	1	\N
69	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-10-31 22:00:09.924593	2025-10-24 22:00:09.925128	1	\N
70	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-01 22:00:10.838477	2025-10-25 22:00:10.838976	1	\N
71	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-02 22:00:11.91264	2025-10-26 22:00:11.91333	1	\N
75	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-05 22:00:14.936718	2025-10-29 22:00:14.937255	1	\N
76	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-06 22:00:15.752366	2025-10-30 22:00:15.752935	1	\N
77	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-07 22:00:16.628543	2025-10-31 22:00:16.62905	1	\N
78	월간 백업 실패	월간 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-07 23:00:17.418468	2025-10-31 23:00:17.418941	1	\N
79	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-08 22:00:18.408728	2025-11-01 22:00:18.409227	1	\N
80	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-09 22:00:19.322486	2025-11-02 22:00:19.323105	1	\N
81	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-10 22:00:20.147917	2025-11-03 22:00:20.148437	1	\N
82	📝 베이비 특이사항 추가	dev_hoon님이 베이비 아동의 특이사항을 추가했습니다.	warning	2	\N	\N	38	f	t	t	2025-11-07 07:47:49.942136	2025-11-04 07:47:49.94269	1	\N
83	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-11 22:00:21.122787	2025-11-04 22:00:21.123312	1	\N
84	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-12 22:00:22.049116	2025-11-05 22:00:22.049906	1	\N
85	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-13 22:00:23.251815	2025-11-06 22:00:23.252559	1	\N
86	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-14 22:00:24.204286	2025-11-07 22:00:24.204928	1	\N
87	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-15 22:00:34.811893	2025-11-08 22:00:34.815129	1	\N
88	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-16 22:00:35.809104	2025-11-09 22:00:35.809793	1	\N
89	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-17 22:00:37.081268	2025-11-10 22:00:37.08209	1	\N
90	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-18 22:00:38.078559	2025-11-11 22:00:38.079184	1	\N
91	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-19 22:00:39.152902	2025-11-12 22:00:39.153624	1	\N
92	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-20 22:00:40.373587	2025-11-13 22:00:40.374154	1	\N
93	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-21 22:00:41.403539	2025-11-14 22:00:41.404178	1	\N
94	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-22 22:00:42.490062	2025-11-15 22:00:42.490861	1	\N
95	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-23 22:00:43.5922	2025-11-16 22:00:43.592809	1	\N
96	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-24 22:00:44.56699	2025-11-17 22:00:44.567602	1	\N
97	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-25 22:00:45.807585	2025-11-18 22:00:45.808347	1	\N
98	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-26 22:00:46.979962	2025-11-19 22:00:46.980608	1	\N
99	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-27 22:00:48.095274	2025-11-20 22:00:48.095895	1	\N
100	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-28 22:00:49.480843	2025-11-21 22:00:49.481484	1	\N
101	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-29 22:00:50.517435	2025-11-22 22:00:50.518105	1	\N
102	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-11-30 22:00:51.683124	2025-11-23 22:00:51.683681	1	\N
103	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-01 22:00:52.820354	2025-11-24 22:00:52.821055	1	\N
104	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-02 22:00:53.994813	2025-11-25 22:00:53.995362	1	\N
105	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-03 22:00:55.080095	2025-11-26 22:00:55.080666	1	\N
106	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-04 22:00:56.372271	2025-11-27 22:00:56.372832	1	\N
107	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-05 22:00:57.496773	2025-11-28 22:00:57.497326	1	\N
108	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-06 22:00:58.7802	2025-11-29 22:00:58.780852	1	\N
109	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-07 22:01:00.01487	2025-11-30 22:01:00.015586	1	\N
110	월간 백업 실패	월간 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-07 23:00:01.174469	2025-11-30 23:00:01.175144	1	\N
111	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-08 22:00:02.283415	2025-12-01 22:00:02.28395	1	\N
112	일일 백업 실패	일일 데이터베이스 백업 생성 실패: 데이터베이스 파일을 찾을 수 없습니다	backup_failed	4	\N	개발자	\N	f	t	t	2025-12-09 22:00:03.573046	2025-12-02 22:00:03.573754	1	\N
\.


--
-- Data for Name: points_history; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.points_history (id, child_id, date, old_korean_points, old_math_points, old_ssen_points, old_reading_points, old_total_points, old_piano_points, old_english_points, old_advanced_math_points, old_writing_points, new_korean_points, new_math_points, new_ssen_points, new_reading_points, new_total_points, new_piano_points, new_english_points, new_advanced_math_points, new_writing_points, change_type, changed_by, changed_at, change_reason) FROM stdin;
2	59	2025-10-02	0	0	0	0	0	0	0	0	0	100	0	100	200	700	0	0	300	0	create	1	2025-10-02 06:39:19.828811	웹 UI를 통한 포인트 신규 입력
3	48	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-02 06:51:25.727769	웹 UI를 통한 포인트 신규 입력
4	49	2025-10-02	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	1	2025-10-02 06:53:29.501661	웹 UI를 통한 포인트 신규 입력
5	32	2025-10-02	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-02 08:05:48.80131	웹 UI를 통한 포인트 신규 입력
6	43	2025-10-02	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-02 08:15:05.123744	웹 UI를 통한 포인트 신규 입력
7	40	2025-10-02	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-02 08:18:27.231109	웹 UI를 통한 포인트 신규 입력
8	50	2025-10-02	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-02 08:22:29.705598	웹 UI를 통한 포인트 신규 입력
9	38	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-02 08:24:39.713439	웹 UI를 통한 포인트 신규 입력
10	38	2025-10-02	0	0	0	0	500	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-10-02 08:25:06.290391	수동 추가: 추가포인트 (열심히 수학)
11	45	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	100	100	400	0	0	0	0	create	1	2025-10-02 08:26:56.596219	웹 UI를 통한 포인트 신규 입력
12	54	2025-10-02	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-02 08:32:52.244201	웹 UI를 통한 포인트 신규 입력
13	39	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	1	2025-10-02 08:42:31.536438	웹 UI를 통한 포인트 신규 입력
14	46	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-02 08:45:00.63744	웹 UI를 통한 포인트 신규 입력
15	44	2025-10-02	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-02 08:47:13.793033	웹 UI를 통한 포인트 신규 입력
16	47	2025-10-02	0	0	0	0	0	0	0	0	0	100	100	100	100	400	0	0	0	0	create	1	2025-10-02 08:50:55.500508	웹 UI를 통한 포인트 신규 입력
17	53	2025-10-10	0	0	0	0	0	0	0	0	0	0	0	0	0	-300	0	0	0	0	차감	1	2025-10-10 01:50:04.046253	수동 차감: 연필 (연필 구매)
18	35	2025-10-10	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	0	0	100	create	1	2025-10-10 03:27:14.38371	웹 UI를 통한 포인트 신규 입력
19	36	2025-10-10	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	0	0	100	create	1	2025-10-10 03:44:56.8582	웹 UI를 통한 포인트 신규 입력
20	58	2025-10-10	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	1	2025-10-10 03:48:08.830995	웹 UI를 통한 포인트 신규 입력
21	45	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 03:53:12.00793	웹 UI를 통한 포인트 신규 입력
22	53	2025-10-10	0	0	0	0	-300	0	0	0	0	200	100	100	200	300	0	0	0	0	update	1	2025-10-10 04:59:29.091973	웹 UI를 통한 포인트 수정
23	53	2025-10-10	0	0	0	0	300	0	0	0	0	0	0	0	0	1300	0	0	0	0	추가	1	2025-10-10 05:00:21.394995	수동 추가: 추가포인트 (열심히 수학&쎈)
24	40	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 06:27:48.092998	웹 UI를 통한 포인트 신규 입력
25	51	2025-10-10	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-10 07:00:34.684859	웹 UI를 통한 포인트 신규 입력
26	50	2025-10-10	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-10 07:05:57.83879	웹 UI를 통한 포인트 신규 입력
27	57	2025-10-10	0	0	0	0	0	0	0	0	0	200	0	100	0	300	0	0	0	0	create	1	2025-10-10 07:07:55.124407	웹 UI를 통한 포인트 신규 입력
28	43	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 07:28:01.970047	웹 UI를 통한 포인트 신규 입력
29	52	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 07:35:34.877853	웹 UI를 통한 포인트 신규 입력
30	44	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 07:44:40.961206	웹 UI를 통한 포인트 신규 입력
31	54	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-10 08:01:56.692851	웹 UI를 통한 포인트 신규 입력
32	38	2025-10-10	0	0	0	0	0	0	0	0	0	200	100	100	100	500	0	0	0	0	create	1	2025-10-10 08:12:43.575804	웹 UI를 통한 포인트 신규 입력
33	38	2025-10-10	0	0	0	0	500	0	0	0	0	0	0	0	0	800	0	0	0	0	추가	1	2025-10-10 08:13:14.295106	수동 추가: 추가포인트 (열심히 수학)
34	48	2025-10-10	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-10 08:16:09.856549	웹 UI를 통한 포인트 신규 입력
35	31	2025-10-10	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-10 08:28:43.60338	웹 UI를 통한 포인트 신규 입력
43	49	2025-10-13	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	1	2025-10-13 06:19:23.596021	웹 UI를 통한 포인트 신규 입력
44	35	2025-10-13	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-10-13 06:55:01.16177	웹 UI를 통한 포인트 신규 입력
45	32	2025-10-13	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-10-13 07:03:43.826363	웹 UI를 통한 포인트 신규 입력
46	59	2025-10-13	0	0	0	0	0	0	0	0	0	200	0	100	200	600	100	0	0	0	create	1	2025-10-13 07:46:44.248089	웹 UI를 통한 포인트 신규 입력
47	40	2025-10-13	0	0	0	0	0	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	1	2025-10-13 08:13:36.124986	수동 차감: 테이프 (테이프 구매)
48	40	2025-10-13	0	0	0	0	-200	0	0	0	0	100	100	100	200	400	100	0	0	0	update	1	2025-10-13 08:14:03.392206	웹 UI를 통한 포인트 수정
49	48	2025-10-13	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-13 08:15:00.117963	웹 UI를 통한 포인트 신규 입력
50	46	2025-10-13	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-13 08:16:00.445744	웹 UI를 통한 포인트 신규 입력
51	38	2025-10-13	0	0	0	0	0	0	0	0	0	200	100	100	100	600	100	0	0	0	create	1	2025-10-13 08:28:14.537407	웹 UI를 통한 포인트 신규 입력
52	44	2025-10-13	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-10-13 08:32:09.489001	웹 UI를 통한 포인트 신규 입력
53	54	2025-10-13	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-13 08:32:55.85074	웹 UI를 통한 포인트 신규 입력
54	45	2025-10-13	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-13 08:52:08.604611	웹 UI를 통한 포인트 신규 입력
55	31	2025-10-14	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	5	2025-10-14 06:53:57.700629	웹 UI를 통한 포인트 신규 입력
56	40	2025-10-14	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	1	2025-10-14 07:43:40.076963	웹 UI를 통한 포인트 신규 입력
57	40	2025-10-14	0	0	0	0	700	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	1	2025-10-14 07:44:15.802472	수동 차감: 풍선 (풍선 구매)
58	35	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	200	700	0	100	0	100	create	5	2025-10-14 07:57:26.949753	웹 UI를 통한 포인트 신규 입력
59	46	2025-10-14	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-10-14 07:58:47.793833	웹 UI를 통한 포인트 신규 입력
60	32	2025-10-14	0	0	0	0	0	0	0	0	0	0	0	0	0	-300	0	0	0	0	차감	6	2025-10-14 08:02:53.12192	수동 차감: 풍선 (풍선구매)
61	32	2025-10-14	0	0	0	0	-300	0	0	0	0	200	200	100	200	600	0	100	0	100	update	6	2025-10-14 08:03:48.784885	웹 UI를 통한 포인트 수정
62	43	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-10-14 08:04:01.182586	웹 UI를 통한 포인트 신규 입력
63	38	2025-10-14	0	0	0	0	0	0	0	0	0	200	100	100	100	600	0	100	0	0	create	1	2025-10-14 08:08:19.045862	웹 UI를 통한 포인트 신규 입력
64	45	2025-10-14	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-10-14 08:15:36.015855	웹 UI를 통한 포인트 신규 입력
65	45	2025-10-14	0	0	0	0	700	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	6	2025-10-14 08:16:45.878733	수동 차감: 풍선 (풍선구매)
66	47	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-10-14 08:20:00.413091	웹 UI를 통한 포인트 신규 입력
67	58	2025-10-14	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	create	6	2025-10-14 08:25:25.374026	웹 UI를 통한 포인트 신규 입력
68	42	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	0	400	0	100	0	0	create	6	2025-10-14 08:28:57.062866	웹 UI를 통한 포인트 신규 입력
69	59	2025-10-14	0	0	0	0	0	0	0	0	0	200	0	100	100	800	0	100	300	0	create	5	2025-10-14 08:40:54.413859	웹 UI를 통한 포인트 신규 입력
70	33	2025-10-14	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-10-14 08:42:32.933239	웹 UI를 통한 포인트 신규 입력
71	48	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-10-14 08:46:16.550831	웹 UI를 통한 포인트 신규 입력
72	37	2025-10-14	0	0	0	0	0	0	0	0	0	100	100	100	100	500	0	100	0	0	create	5	2025-10-14 08:49:15.976096	웹 UI를 통한 포인트 신규 입력
73	37	2025-10-14	0	0	0	0	500	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	1	2025-10-14 08:52:21.24945	수동 추가: 10/10 포인트 (포인트 입력 누락)
74	31	2025-10-15	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-15 04:54:38.872122	웹 UI를 통한 포인트 신규 입력
75	40	2025-10-15	0	0	0	0	0	0	0	0	0	200	200	0	200	600	0	0	0	0	create	1	2025-10-15 05:02:00.764396	웹 UI를 통한 포인트 신규 입력
76	35	2025-10-15	0	0	0	0	0	0	0	0	0	0	0	0	200	300	0	0	0	100	create	5	2025-10-15 05:10:31.732697	웹 UI를 통한 포인트 신규 입력
77	31	2025-10-15	0	0	0	0	800	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	1	2025-10-15 05:14:09.236714	수동 차감: 풍선 (풍선 구매)
78	31	2025-10-15	0	0	0	0	500	0	0	0	0	0	0	0	0	1400	0	0	0	0	추가	1	2025-10-15 05:19:39.669733	수동 추가: 10/13 포인트 (포인트 입력 누락)
79	43	2025-10-15	0	0	0	0	0	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-10-15 05:37:10.665785	수동 추가: 10/13 포인트 (포인트 입력 누락)
80	43	2025-10-15	0	0	0	0	700	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	1	2025-10-15 05:37:41.764564	수동 차감: 풍선 (풍선 구매)
81	59	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	5	2025-10-15 05:47:22.667154	웹 UI를 통한 포인트 신규 입력
82	43	2025-10-15	0	0	0	0	400	0	0	0	0	100	100	0	200	800	0	0	0	0	update	1	2025-10-15 05:51:39.386146	웹 UI를 통한 포인트 수정
83	52	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-15 07:37:36.383458	웹 UI를 통한 포인트 신규 입력
84	48	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	6	2025-10-15 07:48:00.171433	웹 UI를 통한 포인트 신규 입력
85	45	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	5	2025-10-15 07:53:18.149348	웹 UI를 통한 포인트 신규 입력
86	46	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	6	2025-10-15 07:56:37.05737	웹 UI를 통한 포인트 신규 입력
87	47	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	1	2025-10-15 07:57:51.068938	웹 UI를 통한 포인트 신규 입력
88	38	2025-10-15	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-15 08:02:30.460375	웹 UI를 통한 포인트 신규 입력
89	32	2025-10-15	0	0	0	0	0	0	0	0	0	0	0	0	0	-300	0	0	0	0	차감	1	2025-10-15 08:04:11.087986	수동 차감: 풍선 (풍선 구매)
90	32	2025-10-15	0	0	0	0	-300	0	0	0	0	200	0	0	200	100	0	0	0	0	update	1	2025-10-15 08:05:05.878681	웹 UI를 통한 포인트 수정
91	44	2025-10-15	0	0	0	0	0	0	0	0	0	100	200	0	0	300	0	0	0	0	create	5	2025-10-15 08:19:07.829112	웹 UI를 통한 포인트 신규 입력
92	54	2025-10-15	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-10-15 08:26:08.146526	웹 UI를 통한 포인트 신규 입력
93	39	2025-10-15	0	0	0	0	0	0	0	0	0	0	100	100	0	200	0	0	0	0	create	6	2025-10-15 08:31:47.049541	웹 UI를 통한 포인트 신규 입력
94	37	2025-10-15	0	0	0	0	0	0	0	0	0	0	100	100	0	200	0	0	0	0	create	6	2025-10-15 08:33:38.530554	웹 UI를 통한 포인트 신규 입력
95	49	2025-10-16	0	0	0	0	0	0	0	0	0	0	0	0	0	100	0	0	0	0	추가	6	2025-10-16 06:35:35.57705	수동 추가: 추가학습 (추가학습)
96	49	2025-10-16	0	0	0	0	100	0	0	0	0	200	100	100	0	500	0	0	0	0	update	6	2025-10-16 06:36:07.665203	웹 UI를 통한 포인트 수정
97	40	2025-10-16	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-10-16 06:45:35.836144	웹 UI를 통한 포인트 신규 입력
98	46	2025-10-16	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	5	2025-10-16 06:46:02.743711	웹 UI를 통한 포인트 신규 입력
99	48	2025-10-16	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-10-16 07:04:04.193718	웹 UI를 통한 포인트 신규 입력
100	36	2025-10-16	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	5	2025-10-16 07:52:12.405786	웹 UI를 통한 포인트 신규 입력
101	44	2025-10-16	0	0	0	0	0	0	0	0	0	0	0	0	0	100	0	0	0	0	추가	5	2025-10-16 07:59:41.486257	수동 추가: 5-1 수학 (5-1 수학)
102	44	2025-10-16	0	0	0	0	100	0	0	0	0	200	100	100	0	500	0	0	0	0	update	5	2025-10-16 07:59:47.624745	웹 UI를 통한 포인트 수정
103	45	2025-10-16	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-10-16 08:09:43.478671	웹 UI를 통한 포인트 신규 입력
104	45	2025-10-16	100	100	100	200	500	0	0	0	0	100	100	0	200	400	0	0	0	0	update	5	2025-10-16 08:10:05.127951	웹 UI를 통한 포인트 수정
105	45	2025-10-16	100	100	0	200	400	0	0	0	0	100	100	100	200	500	0	0	0	0	update	5	2025-10-16 08:10:30.270454	웹 UI를 통한 포인트 수정
106	45	2025-10-16	0	0	0	0	500	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	5	2025-10-16 08:12:27.376468	수동 추가: 10/15  포인트 (포인트 누락)
107	45	2025-10-16	0	0	0	0	900	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	1	2025-10-16 08:19:28.732917	수동 차감: 10/15 포인트 (차감) (포인트 중복 입력)
108	37	2025-10-16	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	6	2025-10-16 08:23:27.273742	웹 UI를 통한 포인트 신규 입력
109	54	2025-10-16	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-16 08:24:12.356918	웹 UI를 통한 포인트 신규 입력
110	33	2025-10-16	0	0	0	0	0	0	0	0	0	0	0	0	0	400	0	0	0	0	추가	1	2025-10-16 08:28:38.191666	수동 추가: 10/15 포인트 (포인트 입력 누락)
111	33	2025-10-16	0	0	0	0	400	0	0	0	0	200	200	100	200	1200	0	0	0	100	update	1	2025-10-16 08:29:03.617505	웹 UI를 통한 포인트 수정
112	37	2025-10-16	0	0	0	0	400	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	6	2025-10-16 08:31:20.182042	수동 추가: 학습태도 (학습태도)
113	43	2025-10-16	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-16 08:58:35.940626	웹 UI를 통한 포인트 신규 입력
114	59	2025-10-16	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	5	2025-10-16 08:58:40.389333	웹 UI를 통한 포인트 신규 입력
115	51	2025-10-16	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	1	2025-10-16 09:00:10.271123	웹 UI를 통한 포인트 신규 입력
116	31	2025-10-16	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-16 09:05:07.357048	웹 UI를 통한 포인트 신규 입력
117	32	2025-10-16	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-16 09:05:51.502135	웹 UI를 통한 포인트 신규 입력
118	40	2025-10-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-10-17 05:35:54.313818	웹 UI를 통한 포인트 신규 입력
119	43	2025-10-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-10-17 06:11:59.694644	웹 UI를 통한 포인트 신규 입력
120	59	2025-10-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-10-17 06:34:31.321746	웹 UI를 통한 포인트 신규 입력
121	49	2025-10-17	0	0	0	0	0	0	0	0	0	100	100	100	100	500	0	100	0	0	create	6	2025-10-17 06:45:44.2773	웹 UI를 통한 포인트 신규 입력
122	49	2025-10-17	0	0	0	0	500	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	6	2025-10-17 06:47:35.028039	수동 추가: 추가학습 (추가학습)
123	32	2025-10-17	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	6	2025-10-17 08:22:22.082739	웹 UI를 통한 포인트 신규 입력
124	46	2025-10-17	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	6	2025-10-17 08:23:38.911303	웹 UI를 통한 포인트 신규 입력
125	31	2025-10-17	0	0	0	0	0	0	0	0	0	100	200	100	200	800	0	100	0	100	create	1	2025-10-17 08:24:49.922874	웹 UI를 통한 포인트 신규 입력
126	46	2025-10-17	0	0	0	0	700	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	6	2025-10-17 08:27:30.987467	수동 추가: 풍선 (풍선구매)
127	38	2025-10-17	0	0	0	0	0	0	0	0	0	200	100	100	100	600	0	100	0	0	create	1	2025-10-17 08:38:28.375045	웹 UI를 통한 포인트 신규 입력
128	47	2025-10-17	0	0	0	0	0	0	0	0	0	100	100	100	0	400	0	100	0	0	create	1	2025-10-17 09:01:39.963347	웹 UI를 통한 포인트 신규 입력
129	36	2025-10-20	0	0	0	0	0	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	1	2025-10-20 05:03:59.275343	수동 차감: 10/10 포인트 (차감) (500포인트인데 700포인트로 잘못 입력)
131	31	2025-10-20	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-10-20 05:32:16.985464	웹 UI를 통한 포인트 신규 입력
132	40	2025-10-20	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-20 05:52:24.385054	웹 UI를 통한 포인트 신규 입력
133	49	2025-10-20	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	6	2025-10-20 06:29:29.076249	웹 UI를 통한 포인트 신규 입력
134	49	2025-10-20	0	0	0	0	400	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	6	2025-10-20 06:33:46.431092	수동 추가: 추가학습 (추가학습)
135	43	2025-10-20	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	5	2025-10-20 06:42:48.614332	웹 UI를 통한 포인트 신규 입력
136	48	2025-10-20	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-10-20 07:05:10.721126	웹 UI를 통한 포인트 신규 입력
137	48	2025-10-20	0	0	0	0	600	0	0	0	0	0	0	0	0	300	0	0	0	0	차감	6	2025-10-20 07:06:26.457618	수동 차감: 풍선 (풍선구매)
138	32	2025-10-20	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	6	2025-10-20 07:32:25.689668	웹 UI를 통한 포인트 신규 입력
139	50	2025-10-20	0	0	0	0	0	0	0	0	0	200	0	0	0	300	100	0	0	0	create	6	2025-10-20 08:02:32.714208	웹 UI를 통한 포인트 신규 입력
140	59	2025-10-20	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	5	2025-10-20 08:03:34.179007	웹 UI를 통한 포인트 신규 입력
141	38	2025-10-20	0	0	0	0	0	0	0	0	0	200	100	100	0	500	100	0	0	0	create	1	2025-10-20 08:24:08.723795	웹 UI를 통한 포인트 신규 입력
142	39	2025-10-20	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	6	2025-10-20 08:34:24.095261	웹 UI를 통한 포인트 신규 입력
143	54	2025-10-20	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-10-20 08:34:28.066505	웹 UI를 통한 포인트 신규 입력
144	39	2025-10-20	200	100	100	0	400	0	0	0	0	200	100	100	0	500	100	0	0	0	update	6	2025-10-20 08:34:50.627127	웹 UI를 통한 포인트 수정
145	46	2025-10-20	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-10-20 08:35:41.584446	웹 UI를 통한 포인트 신규 입력
146	44	2025-10-20	0	0	0	0	0	0	0	0	0	200	0	100	0	400	100	0	0	0	create	1	2025-10-20 08:38:41.022757	웹 UI를 통한 포인트 신규 입력
147	45	2025-10-20	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-10-20 08:38:49.137443	웹 UI를 통한 포인트 신규 입력
148	44	2025-10-20	0	0	0	0	400	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	1	2025-10-20 08:39:35.069205	수동 추가: 10/17 포인트  (포인트 입력 누락)
149	46	2025-10-20	0	0	0	0	700	0	0	0	0	0	0	0	0	100	0	0	0	0	차감	1	2025-10-20 08:44:11.200287	수동 차감: 포인트 정정 (풍선구매 1번과 잘못입력된 +300(풍선))
150	36	2025-10-21	0	0	0	0	0	0	0	0	0	0	0	0	0	800	0	0	0	0	추가	1	2025-10-21 01:47:22.006017	수동 추가: 포인트 정정 (포인트 정정)
151	31	2025-10-21	0	0	0	0	0	0	0	0	0	100	200	100	200	800	0	100	0	100	create	1	2025-10-21 06:24:28.919502	웹 UI를 통한 포인트 신규 입력
152	40	2025-10-21	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	1	2025-10-21 06:59:52.405091	웹 UI를 통한 포인트 신규 입력
153	45	2025-10-21	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-10-21 07:35:56.886701	웹 UI를 통한 포인트 신규 입력
154	44	2025-10-21	0	0	0	0	0	0	0	0	0	0	0	0	0	100	0	100	0	0	create	5	2025-10-21 07:37:24.130595	웹 UI를 통한 포인트 신규 입력
155	46	2025-10-21	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-10-21 07:38:54.642539	웹 UI를 통한 포인트 신규 입력
156	32	2025-10-21	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-10-21 07:40:13.328975	웹 UI를 통한 포인트 신규 입력
157	43	2025-10-21	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	1	2025-10-21 08:04:17.920925	웹 UI를 통한 포인트 신규 입력
158	50	2025-10-21	0	0	0	0	0	0	0	0	0	200	100	100	0	500	0	100	0	0	create	6	2025-10-21 08:06:50.723149	웹 UI를 통한 포인트 신규 입력
159	40	2025-10-21	0	0	0	0	800	0	0	0	0	0	0	0	0	700	0	0	0	0	차감	1	2025-10-21 08:10:45.005896	수동 차감: 테이프 (테이프 구매)
160	42	2025-10-21	0	0	0	0	0	0	0	0	0	200	0	100	0	300	0	0	0	0	create	6	2025-10-21 08:24:50.725029	웹 UI를 통한 포인트 신규 입력
161	38	2025-10-21	0	0	0	0	0	0	0	0	0	100	100	0	0	300	0	100	0	0	create	1	2025-10-21 08:27:41.832473	웹 UI를 통한 포인트 신규 입력
162	59	2025-10-21	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-10-21 08:27:57.366971	웹 UI를 통한 포인트 신규 입력
163	44	2025-10-21	0	0	0	0	100	0	100	0	0	200	0	0	0	300	0	100	0	0	update	6	2025-10-21 08:28:10.758419	웹 UI를 통한 포인트 수정
164	59	2025-10-21	100	100	100	200	600	0	100	0	0	100	100	100	100	500	0	100	0	0	update	5	2025-10-21 08:33:39.161252	웹 UI를 통한 포인트 수정
165	48	2025-10-21	0	0	0	0	0	0	0	0	0	200	100	100	100	600	0	100	0	0	create	5	2025-10-21 08:44:50.482299	웹 UI를 통한 포인트 신규 입력
166	33	2025-10-21	0	0	0	0	0	0	0	0	0	100	100	100	100	600	0	100	0	100	create	5	2025-10-21 08:45:37.388736	웹 UI를 통한 포인트 신규 입력
167	47	2025-10-21	0	0	0	0	0	0	0	0	0	100	100	100	0	400	0	100	0	0	create	5	2025-10-21 08:46:33.506731	웹 UI를 통한 포인트 신규 입력
168	41	2025-10-21	0	0	0	0	0	0	0	0	0	100	100	100	100	400	0	0	0	0	create	5	2025-10-21 08:46:59.915773	웹 UI를 통한 포인트 신규 입력
169	37	2025-10-21	0	0	0	0	0	0	0	0	0	200	100	0	0	400	0	100	0	0	create	5	2025-10-21 08:49:01.260147	웹 UI를 통한 포인트 신규 입력
170	37	2025-10-21	0	0	0	0	400	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	5	2025-10-21 08:49:59.323655	수동 추가: 추가 학습 (추가 학습 (국어))
171	31	2025-10-22	0	0	0	0	0	0	0	0	0	0	0	0	0	-100	0	0	0	0	차감	1	2025-10-22 05:09:54.637533	수동 차감: 프린트 (프린트 1장)
172	31	2025-10-22	0	0	0	0	-100	0	0	0	0	100	200	100	200	600	0	0	0	100	update	1	2025-10-22 05:12:41.825631	웹 UI를 통한 포인트 수정
173	35	2025-10-22	0	0	0	0	0	0	0	0	0	0	0	0	0	800	0	0	0	0	추가	1	2025-10-22 05:32:58.677945	수동 추가: 10/20 포인트 (포인트 입력 누락)
174	35	2025-10-22	0	0	0	0	800	0	0	0	0	0	0	0	200	1100	0	0	0	100	update	1	2025-10-22 05:33:22.290256	웹 UI를 통한 포인트 수정
175	40	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-22 05:37:05.514066	웹 UI를 통한 포인트 신규 입력
176	43	2025-10-22	0	0	0	0	0	0	0	0	0	0	100	0	200	300	0	0	0	0	create	1	2025-10-22 07:02:39.752637	웹 UI를 통한 포인트 신규 입력
177	33	2025-10-22	0	0	0	0	0	0	0	0	0	200	0	0	200	400	0	0	0	0	create	1	2025-10-22 07:24:46.413322	웹 UI를 통한 포인트 신규 입력
178	54	2025-10-22	0	0	0	0	0	0	0	0	0	100	0	0	200	300	0	0	0	0	create	1	2025-10-22 07:43:00.017053	웹 UI를 통한 포인트 신규 입력
179	48	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	6	2025-10-22 07:43:02.64414	웹 UI를 통한 포인트 신규 입력
180	48	2025-10-22	0	0	0	0	400	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	6	2025-10-22 07:44:03.917698	수동 차감: 연필 (연필 구매)
181	46	2025-10-22	0	0	0	0	0	0	0	0	0	100	200	0	200	500	0	0	0	0	create	6	2025-10-22 07:45:34.922721	웹 UI를 통한 포인트 신규 입력
182	42	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-10-22 07:46:14.14894	웹 UI를 통한 포인트 신규 입력
183	45	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-22 07:47:24.030514	웹 UI를 통한 포인트 신규 입력
184	32	2025-10-22	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	6	2025-10-22 07:58:43.35852	웹 UI를 통한 포인트 신규 입력
185	50	2025-10-22	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	6	2025-10-22 08:02:46.65709	웹 UI를 통한 포인트 신규 입력
186	47	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	100	300	0	0	0	0	create	6	2025-10-22 08:08:03.597968	웹 UI를 통한 포인트 신규 입력
187	44	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	6	2025-10-22 08:10:50.174594	웹 UI를 통한 포인트 신규 입력
188	34	2025-10-22	0	0	0	0	0	0	0	0	0	0	100	0	200	400	0	0	0	100	create	6	2025-10-22 08:20:02.391029	웹 UI를 통한 포인트 신규 입력
189	41	2025-10-22	0	0	0	0	0	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	1	2025-10-22 08:23:30.787994	수동 추가: 포인트 정정 (포인트 정정)
190	41	2025-10-22	0	0	0	0	600	0	0	0	0	200	100	100	200	1200	0	0	0	0	update	1	2025-10-22 08:23:55.489682	웹 UI를 통한 포인트 수정
191	37	2025-10-22	0	0	0	0	0	0	0	0	0	0	0	0	0	-1000	0	0	0	0	차감	6	2025-10-22 08:26:03.689779	수동 차감: 수첩 (수첩구매)
192	37	2025-10-22	0	0	0	0	-1000	0	0	0	0	200	200	100	0	-500	0	0	0	0	update	6	2025-10-22 08:32:04.821724	웹 UI를 통한 포인트 수정
193	39	2025-10-22	0	0	0	0	0	0	0	0	0	0	100	100	0	200	0	0	0	0	create	6	2025-10-22 08:33:49.537976	웹 UI를 통한 포인트 신규 입력
194	52	2025-10-22	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-22 08:37:17.870058	웹 UI를 통한 포인트 신규 입력
195	40	2025-10-23	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-10-23 05:24:15.178551	웹 UI를 통한 포인트 신규 입력
196	35	2025-10-23	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	0	0	100	create	5	2025-10-23 06:27:45.871045	웹 UI를 통한 포인트 신규 입력
197	43	2025-10-23	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-10-23 06:29:06.103499	웹 UI를 통한 포인트 신규 입력
198	49	2025-10-23	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	6	2025-10-23 06:47:27.111941	웹 UI를 통한 포인트 신규 입력
199	49	2025-10-23	0	0	0	0	500	0	0	0	0	0	0	0	0	800	0	0	0	0	추가	6	2025-10-23 06:48:33.506842	수동 추가: 추가학습 (추가학습)
200	42	2025-10-23	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	6	2025-10-23 06:49:53.444019	웹 UI를 통한 포인트 신규 입력
201	42	2025-10-23	0	0	0	0	300	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	6	2025-10-23 06:51:03.983918	수동 추가: 학습태도 (학습태도)
202	59	2025-10-23	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-10-23 07:43:23.922843	웹 UI를 통한 포인트 신규 입력
203	46	2025-10-23	0	0	0	0	0	0	0	0	0	0	0	0	0	-100	0	0	0	0	차감	6	2025-10-23 07:43:39.794313	수동 차감: 이면지 (이면지)
204	46	2025-10-23	0	0	0	0	-100	0	0	0	0	100	0	100	200	300	0	0	0	0	update	6	2025-10-23 07:44:07.092533	웹 UI를 통한 포인트 수정
205	41	2025-10-23	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-10-23 07:45:19.259975	웹 UI를 통한 포인트 신규 입력
206	32	2025-10-23	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	0	0	100	create	6	2025-10-23 07:48:49.910316	웹 UI를 통한 포인트 신규 입력
207	44	2025-10-23	0	0	0	0	0	0	0	0	0	200	0	0	0	200	0	0	0	0	create	6	2025-10-23 07:51:52.99081	웹 UI를 통한 포인트 신규 입력
208	59	2025-10-23	0	0	0	0	500	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	5	2025-10-23 08:01:18.883469	수동 차감: 프린트 (프린트)
209	54	2025-10-23	0	0	0	0	0	0	0	0	0	200	200	0	200	600	0	0	0	0	create	5	2025-10-23 08:21:44.960887	웹 UI를 통한 포인트 신규 입력
210	48	2025-10-23	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-10-23 08:24:05.427351	웹 UI를 통한 포인트 신규 입력
211	33	2025-10-23	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-10-23 08:26:25.604741	웹 UI를 통한 포인트 신규 입력
212	31	2025-10-23	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	0	0	100	create	5	2025-10-23 08:27:09.883369	웹 UI를 통한 포인트 신규 입력
213	45	2025-10-23	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-10-23 08:29:18.260679	웹 UI를 통한 포인트 신규 입력
214	45	2025-10-23	0	0	0	0	600	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	5	2025-10-23 08:30:26.559242	수동 차감: 종이 (종이)
215	39	2025-10-23	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	5	2025-10-23 08:32:31.87884	웹 UI를 통한 포인트 신규 입력
216	40	2025-10-24	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	1	2025-10-24 05:33:18.703548	웹 UI를 통한 포인트 신규 입력
217	43	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-10-24 06:03:52.165875	웹 UI를 통한 포인트 신규 입력
218	49	2025-10-24	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	1	2025-10-24 06:22:54.951875	웹 UI를 통한 포인트 신규 입력
219	35	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-10-24 06:27:59.551889	웹 UI를 통한 포인트 신규 입력
220	32	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-10-24 06:38:38.75563	웹 UI를 통한 포인트 신규 입력
221	48	2025-10-24	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-10-24 06:41:38.155306	웹 UI를 통한 포인트 신규 입력
222	50	2025-10-24	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-10-24 06:49:06.596527	웹 UI를 통한 포인트 신규 입력
223	46	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-10-24 07:06:52.707444	웹 UI를 통한 포인트 신규 입력
224	44	2025-10-24	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	5	2025-10-24 07:39:28.151907	웹 UI를 통한 포인트 신규 입력
225	44	2025-10-24	0	0	0	0	400	0	0	0	0	0	0	0	0	500	0	0	0	0	추가	5	2025-10-24 07:40:41.961407	수동 추가: 5학년 수학 (5학년 수학)
226	36	2025-10-24	0	0	0	0	0	0	0	0	0	0	0	0	100	100	0	0	0	0	create	5	2025-10-24 07:49:18.699256	웹 UI를 통한 포인트 신규 입력
227	36	2025-10-24	0	0	0	0	100	0	0	0	0	0	0	0	0	300	0	0	0	0	추가	5	2025-10-24 07:50:10.598353	수동 추가: 10/22 포인트 (받 100, 독 100)
228	31	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-24 07:51:20.864576	웹 UI를 통한 포인트 신규 입력
229	42	2025-10-24	0	0	0	0	0	0	0	0	0	0	100	0	0	100	0	0	0	0	create	6	2025-10-24 07:55:51.348451	웹 UI를 통한 포인트 신규 입력
230	38	2025-10-24	0	0	0	0	0	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-10-24 08:00:27.308769	수동 추가: 10/23 포인트 (포인트 입력 누락)
231	38	2025-10-24	0	0	0	0	700	0	0	0	0	200	200	0	100	1200	0	0	0	0	update	1	2025-10-24 08:00:45.641245	웹 UI를 통한 포인트 수정
232	38	2025-10-24	200	200	0	100	1200	0	0	0	0	100	200	0	100	1100	0	0	0	0	update	1	2025-10-24 08:00:58.695072	웹 UI를 통한 포인트 수정
233	54	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	1	2025-10-24 08:09:50.090747	웹 UI를 통한 포인트 신규 입력
234	54	2025-10-24	200	200	100	0	500	0	0	0	0	100	200	100	0	400	0	0	0	0	update	1	2025-10-24 08:10:23.124459	웹 UI를 통한 포인트 수정
235	33	2025-10-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-24 08:23:42.329506	웹 UI를 통한 포인트 신규 입력
236	47	2025-10-24	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-10-24 08:32:36.420968	웹 UI를 통한 포인트 신규 입력
237	45	2025-10-24	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-10-24 08:43:48.961287	웹 UI를 통한 포인트 신규 입력
238	31	2025-10-27	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-10-27 05:02:00.427716	웹 UI를 통한 포인트 신규 입력
239	40	2025-10-27	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-10-27 06:01:46.40881	웹 UI를 통한 포인트 신규 입력
240	49	2025-10-27	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-10-27 06:02:06.051006	웹 UI를 통한 포인트 신규 입력
241	48	2025-10-27	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	5	2025-10-27 06:06:13.416791	웹 UI를 통한 포인트 신규 입력
242	48	2025-10-27	0	0	0	0	700	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	5	2025-10-27 06:07:30.825807	수동 차감: 프린트 (프린트 3개)
243	43	2025-10-27	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	1	2025-10-27 06:30:40.24196	웹 UI를 통한 포인트 신규 입력
244	45	2025-10-27	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-10-27 06:41:13.480875	웹 UI를 통한 포인트 신규 입력
245	47	2025-10-27	0	0	0	0	0	0	0	0	0	100	0	100	0	300	100	0	0	0	create	6	2025-10-27 06:45:10.281197	웹 UI를 통한 포인트 신규 입력
246	59	2025-10-27	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	5	2025-10-27 06:47:09.561777	웹 UI를 통한 포인트 신규 입력
247	59	2025-10-27	0	0	0	0	700	0	0	0	0	0	0	0	0	1200	0	0	0	0	추가	5	2025-10-27 06:50:19.608995	수동 추가: 10/24 포인트 (포인트 입력 누락)
248	42	2025-10-27	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-10-27 07:03:49.362828	웹 UI를 통한 포인트 신규 입력
249	46	2025-10-27	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-10-27 07:41:25.946645	웹 UI를 통한 포인트 신규 입력
250	46	2025-10-27	0	0	0	0	700	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	6	2025-10-27 07:41:54.463997	수동 차감: 프린트 (프린트)
251	50	2025-10-27	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-10-27 08:06:28.87402	웹 UI를 통한 포인트 신규 입력
252	44	2025-10-27	0	0	0	0	0	0	0	0	0	200	200	100	0	600	100	0	0	0	create	1	2025-10-27 08:14:52.439252	웹 UI를 통한 포인트 신규 입력
253	41	2025-10-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-10-27 08:15:45.793769	웹 UI를 통한 포인트 신규 입력
254	33	2025-10-27	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-10-27 08:29:57.923144	웹 UI를 통한 포인트 신규 입력
255	39	2025-10-27	0	0	0	0	0	0	0	0	0	100	0	0	0	100	0	0	0	0	create	5	2025-10-27 08:34:51.569457	웹 UI를 통한 포인트 신규 입력
256	36	2025-10-27	0	0	0	0	0	0	0	0	0	100	100	100	100	400	0	0	0	0	create	5	2025-10-27 08:51:44.944779	웹 UI를 통한 포인트 신규 입력
257	36	2025-10-27	0	0	0	0	400	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	5	2025-10-27 08:53:52.940143	수동 추가: 추가학습 (추가학습)
258	36	2025-10-27	100	100	100	100	700	0	0	0	0	100	100	100	0	600	0	0	0	0	update	5	2025-10-27 08:54:13.753709	웹 UI를 통한 포인트 수정
259	31	2025-10-28	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-10-28 06:10:49.901271	웹 UI를 통한 포인트 신규 입력
260	45	2025-10-28	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-10-28 06:46:44.626875	웹 UI를 통한 포인트 신규 입력
261	46	2025-10-28	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-10-28 07:51:59.487986	웹 UI를 통한 포인트 신규 입력
262	54	2025-10-28	0	0	0	0	0	0	0	0	0	100	100	100	0	400	0	100	0	0	create	1	2025-10-28 07:52:56.352468	웹 UI를 통한 포인트 신규 입력
263	40	2025-10-28	0	0	0	0	0	0	0	0	0	100	200	100	100	600	0	100	0	0	create	1	2025-10-28 07:53:40.423616	웹 UI를 통한 포인트 신규 입력
264	32	2025-10-28	0	0	0	0	0	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-10-28 08:01:02.106348	수동 추가: 10/27 포인트 (포인트 입력 누락)
265	32	2025-10-28	0	0	0	0	700	0	0	0	0	200	200	100	200	1600	0	100	0	100	update	1	2025-10-28 08:02:02.228054	웹 UI를 통한 포인트 수정
266	43	2025-10-28	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	5	2025-10-28 08:03:49.215251	웹 UI를 통한 포인트 신규 입력
267	33	2025-10-28	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-10-28 08:07:33.078559	웹 UI를 통한 포인트 신규 입력
268	47	2025-10-28	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-10-28 08:12:23.041502	웹 UI를 통한 포인트 신규 입력
269	38	2025-10-28	0	0	0	0	0	0	0	0	0	100	0	100	200	500	0	100	0	0	create	1	2025-10-28 08:24:40.247027	웹 UI를 통한 포인트 신규 입력
270	59	2025-10-28	0	0	0	0	0	0	0	0	0	200	100	100	0	500	0	100	0	0	create	5	2025-10-28 08:42:06.09903	웹 UI를 통한 포인트 신규 입력
271	41	2025-10-28	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-10-28 08:54:43.818831	웹 UI를 통한 포인트 신규 입력
272	31	2025-10-29	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	1	2025-10-29 04:28:05.095728	웹 UI를 통한 포인트 신규 입력
273	45	2025-10-29	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-10-29 05:53:49.30705	웹 UI를 통한 포인트 신규 입력
274	45	2025-10-29	0	0	0	0	200	0	0	0	0	0	0	0	0	100	0	0	0	0	차감	5	2025-10-29 05:54:38.034325	수동 차감: 프린트 (프린트)
275	43	2025-10-29	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-10-29 06:23:49.415553	웹 UI를 통한 포인트 신규 입력
276	32	2025-10-29	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-10-29 07:34:53.105149	웹 UI를 통한 포인트 신규 입력
277	50	2025-10-29	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-10-29 07:40:06.064269	웹 UI를 통한 포인트 신규 입력
278	48	2025-10-29	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-10-29 08:30:24.031506	웹 UI를 통한 포인트 신규 입력
279	48	2025-10-29	0	0	0	0	200	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	5	2025-10-29 08:31:13.50356	수동 추가: 10/28 포인트 갱신 (포인트 입력 누락)
280	43	2025-10-30	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	1	2025-10-30 05:37:02.932804	웹 UI를 통한 포인트 신규 입력
281	35	2025-10-30	0	0	0	0	0	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-10-30 06:22:31.44281	수동 추가: 10/27 포인트 (포인트 입력 누락)
282	35	2025-10-30	0	0	0	0	700	0	0	0	0	0	0	0	0	1500	0	0	0	0	추가	1	2025-10-30 06:23:05.171257	수동 추가: 10/28 포인트 (포인트 입력 누락)
283	35	2025-10-30	0	0	0	0	1500	0	0	0	0	200	200	100	200	2300	0	0	0	100	update	1	2025-10-30 06:23:37.913083	웹 UI를 통한 포인트 수정
284	48	2025-10-30	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-30 06:26:24.927394	웹 UI를 통한 포인트 신규 입력
285	44	2025-10-30	0	0	0	0	0	0	0	0	0	0	0	0	0	200	0	0	0	0	추가	1	2025-10-30 06:28:03.712464	수동 추가: 10/29 포인트 (포인트 입력 누락)
286	31	2025-10-30	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-30 06:32:03.246585	웹 UI를 통한 포인트 신규 입력
287	59	2025-10-30	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	5	2025-10-30 06:34:12.070321	웹 UI를 통한 포인트 신규 입력
288	49	2025-10-30	0	0	0	0	0	0	0	0	0	100	200	100	0	400	0	0	0	0	create	5	2025-10-30 06:39:20.194054	웹 UI를 통한 포인트 신규 입력
289	46	2025-10-30	0	0	0	0	0	0	0	0	0	200	0	100	200	500	0	0	0	0	create	5	2025-10-30 06:40:41.92339	웹 UI를 통한 포인트 신규 입력
290	46	2025-10-30	0	0	0	0	500	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	5	2025-10-30 06:42:08.899369	수동 차감: 프린트 (프린트)
291	34	2025-10-30	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	0	0	100	create	5	2025-10-30 06:50:48.154022	웹 UI를 통한 포인트 신규 입력
292	42	2025-10-30	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	6	2025-10-30 06:52:09.70066	웹 UI를 통한 포인트 신규 입력
293	41	2025-10-30	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-10-30 06:54:12.456697	웹 UI를 통한 포인트 신규 입력
294	32	2025-10-30	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-10-30 06:57:08.844457	웹 UI를 통한 포인트 신규 입력
295	45	2025-10-30	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-10-30 07:01:40.533397	웹 UI를 통한 포인트 신규 입력
296	50	2025-10-30	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	1	2025-10-30 07:33:55.781926	웹 UI를 통한 포인트 신규 입력
297	43	2025-10-31	0	0	0	0	0	0	0	0	0	100	0	0	200	400	0	100	0	0	create	5	2025-10-31 06:05:47.97165	웹 UI를 통한 포인트 신규 입력
298	35	2025-10-31	0	0	0	0	0	0	0	0	0	100	0	0	200	500	0	100	0	100	create	5	2025-10-31 06:31:46.100358	웹 UI를 통한 포인트 신규 입력
299	59	2025-10-31	0	0	0	0	0	0	0	0	0	200	100	0	200	600	0	100	0	0	create	5	2025-10-31 06:57:18.432027	웹 UI를 통한 포인트 신규 입력
300	48	2025-10-31	0	0	0	0	0	0	0	0	0	100	200	0	200	500	0	0	0	0	create	6	2025-10-31 07:32:40.161407	웹 UI를 통한 포인트 신규 입력
301	50	2025-10-31	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	6	2025-10-31 07:46:08.569009	웹 UI를 통한 포인트 신규 입력
302	41	2025-10-31	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	5	2025-10-31 07:56:55.181341	웹 UI를 통한 포인트 신규 입력
303	41	2025-10-31	100	100	0	200	400	0	0	0	0	100	100	0	200	500	0	100	0	0	update	5	2025-10-31 07:57:27.660018	웹 UI를 통한 포인트 수정
304	44	2025-10-31	0	0	0	0	0	0	0	0	0	200	100	100	0	500	0	100	0	0	create	5	2025-10-31 07:58:25.555791	웹 UI를 통한 포인트 신규 입력
305	44	2025-10-31	0	0	0	0	500	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	5	2025-10-31 07:59:58.672654	수동 추가: 10/30 포인트 (포인트 입력 누락)
306	34	2025-10-31	0	0	0	0	0	0	0	0	0	0	0	0	0	-300	0	0	0	0	차감	6	2025-10-31 08:02:43.314344	수동 차감: 학습실출입 (학습실출입)
307	32	2025-10-31	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-10-31 08:05:32.646634	웹 UI를 통한 포인트 신규 입력
308	31	2025-10-31	0	0	0	0	0	0	0	0	0	200	100	0	200	600	0	100	0	0	create	1	2025-10-31 08:07:18.486327	웹 UI를 통한 포인트 신규 입력
309	47	2025-10-31	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	1	2025-10-31 08:22:01.467783	웹 UI를 통한 포인트 신규 입력
310	54	2025-10-31	0	0	0	0	0	0	0	0	0	0	0	0	200	300	0	100	0	0	create	1	2025-10-31 08:26:55.620489	웹 UI를 통한 포인트 신규 입력
311	31	2025-11-03	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-03 05:36:36.460651	웹 UI를 통한 포인트 신규 입력
312	40	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-11-03 06:20:06.51711	웹 UI를 통한 포인트 신규 입력
313	43	2025-11-03	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-11-03 06:39:10.150964	웹 UI를 통한 포인트 신규 입력
314	56	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	0	500	100	0	0	0	create	5	2025-11-03 06:43:30.313799	웹 UI를 통한 포인트 신규 입력
315	48	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-11-03 06:47:14.285963	웹 UI를 통한 포인트 신규 입력
316	42	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-11-03 07:06:08.958323	웹 UI를 통한 포인트 신규 입력
317	59	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	5	2025-11-03 07:34:37.379374	웹 UI를 통한 포인트 신규 입력
318	32	2025-11-03	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-03 07:48:24.724113	웹 UI를 통한 포인트 신규 입력
319	50	2025-11-03	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-11-03 07:51:49.009603	웹 UI를 통한 포인트 신규 입력
320	46	2025-11-03	0	0	0	0	0	0	0	0	0	0	0	0	0	300	0	0	0	0	추가	6	2025-11-03 08:00:10.837725	수동 추가: 10월 31일 (10월 31일)
321	46	2025-11-03	0	0	0	0	300	0	0	0	0	200	100	100	200	1000	100	0	0	0	update	6	2025-11-03 08:00:54.50142	웹 UI를 통한 포인트 수정
322	41	2025-11-03	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-11-03 08:02:48.256695	웹 UI를 통한 포인트 신규 입력
323	54	2025-11-03	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-11-03 08:24:48.813636	웹 UI를 통한 포인트 신규 입력
324	36	2025-11-03	0	0	0	0	0	0	0	0	0	100	100	100	100	500	0	0	0	100	create	5	2025-11-03 08:37:14.928967	웹 UI를 통한 포인트 신규 입력
325	36	2025-11-03	0	0	0	0	500	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	5	2025-11-03 08:38:21.597799	수동 추가: 추가 학습 (추가 학습(쎈))
326	34	2025-11-03	0	0	0	0	0	0	0	0	0	100	200	100	200	800	100	0	0	100	create	5	2025-11-03 08:51:54.222515	웹 UI를 통한 포인트 신규 입력
327	36	2025-11-03	100	100	100	100	600	0	0	0	100	100	100	100	200	700	0	0	0	100	update	5	2025-11-03 09:02:07.303381	웹 UI를 통한 포인트 수정
328	45	2025-11-04	0	0	0	0	0	0	0	0	0	0	0	0	0	400	0	0	0	0	추가	1	2025-11-04 06:45:55.534556	수동 추가: 10/30 포인트 (포인트 입력 누락)
329	45	2025-11-04	0	0	0	0	400	0	0	0	0	200	100	100	200	1100	0	100	0	0	update	1	2025-11-04 06:46:48.259021	웹 UI를 통한 포인트 수정
330	40	2025-11-04	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	1	2025-11-04 06:53:25.600873	웹 UI를 통한 포인트 신규 입력
331	34	2025-11-04	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-11-04 07:06:59.947517	웹 UI를 통한 포인트 신규 입력
332	46	2025-11-04	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-04 07:28:31.70135	웹 UI를 통한 포인트 신규 입력
333	43	2025-11-04	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-11-04 07:53:56.439102	웹 UI를 통한 포인트 신규 입력
334	47	2025-11-04	0	0	0	0	0	0	0	0	0	200	100	100	100	600	0	100	0	0	create	6	2025-11-04 07:56:38.254718	웹 UI를 통한 포인트 신규 입력
335	31	2025-11-04	0	0	0	0	0	0	0	0	0	100	200	100	200	800	0	100	0	100	create	1	2025-11-04 07:59:10.742383	웹 UI를 통한 포인트 신규 입력
336	32	2025-11-04	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-11-04 08:00:21.102406	웹 UI를 통한 포인트 신규 입력
337	33	2025-11-04	0	0	0	0	0	0	0	0	0	0	0	0	0	200	0	0	0	0	추가	1	2025-11-04 08:07:22.748305	수동 추가: 10/29 포인트 (포인트 입력 누락)
338	33	2025-11-04	0	0	0	0	200	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	1	2025-11-04 08:07:53.677755	수동 추가: 11/3 포인트 (포인트 입력 누락)
339	33	2025-11-04	0	0	0	0	1000	0	0	0	0	100	200	100	200	1800	0	100	0	100	update	1	2025-11-04 08:08:32.261568	웹 UI를 통한 포인트 수정
340	50	2025-11-04	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-04 08:09:00.387561	웹 UI를 통한 포인트 신규 입력
341	59	2025-11-04	0	0	0	0	0	0	0	0	0	100	0	100	200	500	0	100	0	0	create	5	2025-11-04 08:10:30.823521	웹 UI를 통한 포인트 신규 입력
342	54	2025-11-04	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-11-04 08:42:36.238001	웹 UI를 통한 포인트 신규 입력
343	41	2025-11-04	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	5	2025-11-04 08:55:31.338135	웹 UI를 통한 포인트 신규 입력
344	37	2025-11-04	0	0	0	0	0	0	0	0	0	0	0	0	0	100	0	100	0	0	create	5	2025-11-04 08:57:42.007423	웹 UI를 통한 포인트 신규 입력
345	31	2025-11-05	0	0	0	0	0	0	0	0	0	200	200	0	200	700	0	0	0	100	create	5	2025-11-05 04:43:23.051717	웹 UI를 통한 포인트 신규 입력
346	35	2025-11-05	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	5	2025-11-05 05:15:22.871606	웹 UI를 통한 포인트 신규 입력
347	40	2025-11-05	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	5	2025-11-05 05:24:57.215482	웹 UI를 통한 포인트 신규 입력
348	43	2025-11-05	0	0	0	0	0	0	0	0	0	200	200	0	200	600	0	0	0	0	create	5	2025-11-05 05:36:47.254301	웹 UI를 통한 포인트 신규 입력
349	35	2025-11-05	200	0	0	200	500	0	0	0	100	200	100	0	200	600	0	0	0	100	update	5	2025-11-05 05:43:11.742943	웹 UI를 통한 포인트 수정
350	32	2025-11-05	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-05 07:26:19.609118	웹 UI를 통한 포인트 신규 입력
351	54	2025-11-05	0	0	0	0	0	0	0	0	0	200	200	0	200	600	0	0	0	0	create	5	2025-11-05 07:27:21.190734	웹 UI를 통한 포인트 신규 입력
352	50	2025-11-05	0	0	0	0	0	0	0	0	0	200	0	100	0	300	0	0	0	0	create	6	2025-11-05 07:28:52.754404	웹 UI를 통한 포인트 신규 입력
353	59	2025-11-05	0	0	0	0	0	0	0	0	0	100	200	0	200	500	0	0	0	0	create	5	2025-11-05 07:46:02.240738	웹 UI를 통한 포인트 신규 입력
354	46	2025-11-05	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	5	2025-11-05 07:49:04.287553	웹 UI를 통한 포인트 신규 입력
355	45	2025-11-05	0	0	0	0	0	0	0	0	0	200	200	0	200	600	0	0	0	0	create	6	2025-11-05 07:50:14.196994	웹 UI를 통한 포인트 신규 입력
356	48	2025-11-05	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	6	2025-11-05 07:51:06.656405	웹 UI를 통한 포인트 신규 입력
357	41	2025-11-05	0	0	0	0	0	0	0	0	0	100	100	0	200	400	0	0	0	0	create	5	2025-11-05 08:04:40.876285	웹 UI를 통한 포인트 신규 입력
358	33	2025-11-05	0	0	0	0	0	0	0	0	0	200	200	0	200	700	0	0	0	100	create	5	2025-11-05 08:17:55.307934	웹 UI를 통한 포인트 신규 입력
359	40	2025-11-06	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	1	2025-11-06 05:38:29.526577	웹 UI를 통한 포인트 신규 입력
360	43	2025-11-06	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	1	2025-11-06 06:07:07.428702	웹 UI를 통한 포인트 신규 입력
361	49	2025-11-06	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	6	2025-11-06 06:38:33.52445	웹 UI를 통한 포인트 신규 입력
362	48	2025-11-06	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-06 06:42:09.422264	웹 UI를 통한 포인트 신규 입력
363	42	2025-11-06	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	6	2025-11-06 06:44:13.275684	웹 UI를 통한 포인트 신규 입력
364	41	2025-11-06	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-06 07:45:58.364886	웹 UI를 통한 포인트 신규 입력
365	59	2025-11-06	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-11-06 07:47:36.692963	웹 UI를 통한 포인트 신규 입력
366	32	2025-11-06	0	0	0	0	0	0	0	0	0	0	0	0	0	300	0	0	0	0	추가	1	2025-11-06 07:56:01.962574	수동 추가: 11/5 포인트 추가 (포인트 입력 누락)
367	32	2025-11-06	0	0	0	0	300	0	0	0	0	200	200	100	200	1100	0	0	0	100	update	1	2025-11-06 07:56:23.436339	웹 UI를 통한 포인트 수정
368	31	2025-11-06	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	1	2025-11-06 08:05:56.7177	웹 UI를 통한 포인트 신규 입력
369	46	2025-11-06	0	0	0	0	0	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	6	2025-11-06 08:13:00.199213	수동 차감: 프린트 (프린트)
370	46	2025-11-06	0	0	0	0	-200	0	0	0	0	200	0	100	200	300	0	0	0	0	update	6	2025-11-06 08:13:26.200131	웹 UI를 통한 포인트 수정
371	33	2025-11-06	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-11-06 08:33:02.890911	웹 UI를 통한 포인트 신규 입력
372	54	2025-11-06	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-11-06 08:43:00.953377	웹 UI를 통한 포인트 신규 입력
373	51	2025-11-06	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	1	2025-11-06 08:46:59.394292	웹 UI를 통한 포인트 신규 입력
374	40	2025-11-07	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-11-07 06:11:27.50982	웹 UI를 통한 포인트 신규 입력
375	49	2025-11-07	0	0	0	0	0	0	0	0	0	200	200	100	0	600	0	100	0	0	create	6	2025-11-07 06:14:43.147263	웹 UI를 통한 포인트 신규 입력
376	43	2025-11-07	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-11-07 06:15:40.079084	웹 UI를 통한 포인트 신규 입력
377	59	2025-11-07	0	0	0	0	0	0	0	0	0	200	0	100	200	600	0	100	0	0	create	5	2025-11-07 07:01:41.893962	웹 UI를 통한 포인트 신규 입력
378	32	2025-11-07	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	6	2025-11-07 08:00:00.854773	웹 UI를 통한 포인트 신규 입력
379	47	2025-11-07	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-07 08:04:02.677628	웹 UI를 통한 포인트 신규 입력
380	33	2025-11-07	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	5	2025-11-07 08:09:03.036582	웹 UI를 통한 포인트 신규 입력
381	46	2025-11-07	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-07 08:10:39.79374	웹 UI를 통한 포인트 신규 입력
382	48	2025-11-07	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-07 08:20:23.64095	웹 UI를 통한 포인트 신규 입력
383	48	2025-11-07	0	0	0	0	600	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	6	2025-11-07 08:21:34.563905	수동 차감: 이면지 (이면지)
384	45	2025-11-07	0	0	0	0	0	0	0	0	0	200	100	100	0	500	0	100	0	0	create	5	2025-11-07 08:40:12.93093	웹 UI를 통한 포인트 신규 입력
385	31	2025-11-07	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	5	2025-11-07 08:44:41.437099	웹 UI를 통한 포인트 신규 입력
386	35	2025-11-07	0	0	0	0	0	0	0	0	0	200	100	100	200	800	0	100	0	100	create	5	2025-11-07 09:01:29.181729	웹 UI를 통한 포인트 신규 입력
387	31	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-10 05:30:11.22961	웹 UI를 통한 포인트 신규 입력
388	43	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	5	2025-11-10 06:26:56.25044	웹 UI를 통한 포인트 신규 입력
389	45	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-11-10 06:53:25.953185	웹 UI를 통한 포인트 신규 입력
390	40	2025-11-10	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-11-10 06:54:39.568583	웹 UI를 통한 포인트 신규 입력
391	49	2025-11-10	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	1	2025-11-10 06:56:20.001266	웹 UI를 통한 포인트 신규 입력
392	59	2025-11-10	0	0	0	0	0	0	0	0	0	200	0	100	200	600	100	0	0	0	create	5	2025-11-10 07:43:37.870873	웹 UI를 통한 포인트 신규 입력
393	32	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-10 07:46:04.953287	웹 UI를 통한 포인트 신규 입력
394	36	2025-11-10	0	0	0	0	0	0	0	0	0	0	0	0	0	-600	0	0	0	0	차감	1	2025-11-10 07:48:33.077301	수동 차감: 연필 구매 (연필 2개 구매)
395	48	2025-11-10	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-11-10 07:50:42.194742	웹 UI를 통한 포인트 신규 입력
396	35	2025-11-10	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-11-10 07:57:37.726776	웹 UI를 통한 포인트 신규 입력
397	52	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-11-10 07:57:49.00397	웹 UI를 통한 포인트 신규 입력
398	35	2025-11-10	200	100	100	200	700	0	100	0	0	200	100	100	200	800	0	100	0	100	update	5	2025-11-10 07:57:51.608093	웹 UI를 통한 포인트 수정
399	52	2025-11-10	0	0	0	0	800	0	0	0	0	0	0	0	0	700	0	0	0	0	차감	1	2025-11-10 07:58:17.941533	수동 차감: 종이 구매 (종이 구매 1장)
400	54	2025-11-10	0	0	0	0	0	0	0	0	0	200	100	100	0	500	100	0	0	0	create	1	2025-11-10 08:00:30.884507	웹 UI를 통한 포인트 신규 입력
401	46	2025-11-10	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	5	2025-11-10 08:03:51.061919	웹 UI를 통한 포인트 신규 입력
402	33	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-10 08:10:26.591923	웹 UI를 통한 포인트 신규 입력
403	39	2025-11-10	0	0	0	0	0	0	0	0	0	200	100	0	0	300	0	0	0	0	create	1	2025-11-10 08:31:16.230108	웹 UI를 통한 포인트 신규 입력
404	41	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	5	2025-11-10 08:32:26.241294	웹 UI를 통한 포인트 신규 입력
405	34	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-10 08:36:46.114355	웹 UI를 통한 포인트 신규 입력
406	54	2025-11-10	200	100	100	0	500	100	0	0	0	200	100	100	200	700	100	0	0	0	update	1	2025-11-10 08:50:33.764369	웹 UI를 통한 포인트 수정
407	36	2025-11-10	0	0	0	0	-600	0	0	0	0	100	100	100	100	0	100	0	0	100	update	5	2025-11-10 08:52:32.601594	웹 UI를 통한 포인트 수정
408	44	2025-11-10	0	0	0	0	0	0	0	0	0	200	200	100	0	600	100	0	0	0	create	5	2025-11-10 08:53:45.916261	웹 UI를 통한 포인트 신규 입력
409	36	2025-11-10	0	0	0	0	0	0	0	0	0	0	0	0	0	200	0	0	0	0	추가	5	2025-11-10 08:54:48.600122	수동 추가: 추가 학습 (쎈)
410	36	2025-11-10	100	100	100	100	200	100	0	0	100	100	100	100	0	100	100	0	0	100	update	5	2025-11-10 08:57:55.317067	웹 UI를 통한 포인트 수정
411	31	2025-11-11	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	5	2025-11-11 06:33:51.166473	웹 UI를 통한 포인트 신규 입력
412	40	2025-11-11	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-11-11 06:57:03.831093	웹 UI를 통한 포인트 신규 입력
413	35	2025-11-11	0	0	0	0	0	0	0	0	0	200	100	100	200	800	0	100	0	100	create	5	2025-11-11 07:39:49.469585	웹 UI를 통한 포인트 신규 입력
414	35	2025-11-11	0	0	0	0	800	0	0	0	0	0	0	0	0	700	0	0	0	0	차감	5	2025-11-11 07:40:20.205433	수동 차감: 프린트 (프린트)
415	43	2025-11-11	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-11-11 07:41:28.170102	웹 UI를 통한 포인트 신규 입력
416	46	2025-11-11	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-11-11 07:54:08.667685	웹 UI를 통한 포인트 신규 입력
417	46	2025-11-11	0	0	0	0	700	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	5	2025-11-11 07:54:38.646224	수동 차감: 프린트 (프린트)
418	59	2025-11-11	0	0	0	0	0	0	0	0	0	100	0	100	200	500	0	100	0	0	create	5	2025-11-11 07:55:34.502093	웹 UI를 통한 포인트 신규 입력
419	50	2025-11-11	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-11-11 07:58:52.893336	웹 UI를 통한 포인트 신규 입력
420	32	2025-11-11	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-11-11 08:03:56.423803	웹 UI를 통한 포인트 신규 입력
421	32	2025-11-11	0	0	0	0	900	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	1	2025-11-11 08:04:29.586904	수동 차감: 프린트 (구매)
422	54	2025-11-11	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	1	2025-11-11 08:44:45.571612	웹 UI를 통한 포인트 신규 입력
423	41	2025-11-11	0	0	0	0	0	0	0	0	0	100	200	100	100	600	0	100	0	0	create	5	2025-11-11 08:59:49.445649	웹 UI를 통한 포인트 신규 입력
424	31	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-11-12 04:41:19.622271	웹 UI를 통한 포인트 신규 입력
425	35	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-12 04:48:52.457204	웹 UI를 통한 포인트 신규 입력
426	59	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	6	2025-11-12 06:22:11.642058	웹 UI를 통한 포인트 신규 입력
427	32	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	6	2025-11-12 06:37:03.587617	웹 UI를 통한 포인트 신규 입력
428	59	2025-11-12	0	0	0	0	200	0	0	0	0	0	0	0	0	100	0	0	0	0	차감	6	2025-11-12 06:38:14.612025	수동 차감: 프린트 (프린트)
429	32	2025-11-12	0	0	0	0	200	0	0	0	0	0	0	0	0	100	0	0	0	0	차감	6	2025-11-12 06:39:49.83083	수동 차감: 프린트 (프린트)
430	33	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-11-12 07:35:04.452128	웹 UI를 통한 포인트 신규 입력
431	41	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	1	2025-11-12 07:35:48.965335	웹 UI를 통한 포인트 신규 입력
432	54	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-12 08:00:35.650705	웹 UI를 통한 포인트 신규 입력
433	43	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-12 08:01:29.498813	웹 UI를 통한 포인트 신규 입력
434	50	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-12 08:02:53.25228	웹 UI를 통한 포인트 신규 입력
435	39	2025-11-12	0	0	0	0	0	0	0	0	0	0	0	100	0	100	0	0	0	0	create	5	2025-11-12 08:37:22.164668	웹 UI를 통한 포인트 신규 입력
436	43	2025-11-13	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-11-13 05:39:45.442438	웹 UI를 통한 포인트 신규 입력
437	43	2025-11-13	0	0	0	0	700	0	0	0	0	0	0	0	0	200	0	0	0	0	차감	5	2025-11-13 05:41:07.313775	수동 차감: 지우개 (지우개 구매)
438	40	2025-11-13	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-11-13 06:22:33.552475	웹 UI를 통한 포인트 신규 입력
439	49	2025-11-13	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	6	2025-11-13 06:29:10.953506	웹 UI를 통한 포인트 신규 입력
440	42	2025-11-13	0	0	0	0	0	0	0	0	0	100	0	100	0	200	0	0	0	0	create	6	2025-11-13 06:37:06.262368	웹 UI를 통한 포인트 신규 입력
441	48	2025-11-13	0	0	0	0	0	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	6	2025-11-13 06:39:21.671978	수동 추가: 11일포인트 (11일포인트)
442	48	2025-11-13	0	0	0	0	600	0	0	0	0	100	100	100	200	1100	0	0	0	0	update	6	2025-11-13 06:39:59.56288	웹 UI를 통한 포인트 수정
443	59	2025-11-13	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-13 07:03:30.455567	웹 UI를 통한 포인트 신규 입력
444	32	2025-11-13	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	0	0	100	create	1	2025-11-13 07:07:58.22135	웹 UI를 통한 포인트 신규 입력
445	41	2025-11-13	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-13 07:08:57.073314	웹 UI를 통한 포인트 신규 입력
446	44	2025-11-13	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	5	2025-11-13 07:32:40.43378	웹 UI를 통한 포인트 신규 입력
447	31	2025-11-13	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-11-13 07:57:34.744403	웹 UI를 통한 포인트 신규 입력
448	46	2025-11-13	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-11-13 07:59:26.173204	웹 UI를 통한 포인트 신규 입력
449	46	2025-11-13	0	0	0	0	500	0	0	0	0	0	0	0	0	300	0	0	0	0	차감	6	2025-11-13 08:00:52.228271	수동 차감: 프린트 (프린트)
450	46	2025-11-13	0	0	0	0	300	0	0	0	0	0	0	0	0	500	0	0	0	0	추가	6	2025-11-13 08:01:19.42599	수동 추가: 추가학습 (추가학습)
451	54	2025-11-13	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-11-13 08:12:57.03913	웹 UI를 통한 포인트 신규 입력
452	37	2025-11-13	0	0	0	0	0	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	6	2025-11-13 08:24:01.031121	수동 차감: 프린트 (프린트)
453	37	2025-11-13	0	0	0	0	-200	0	0	0	0	0	100	100	0	0	0	0	0	0	update	6	2025-11-13 08:25:52.217595	웹 UI를 통한 포인트 수정
454	37	2025-11-13	0	0	0	0	0	0	0	0	0	0	0	0	0	500	0	0	0	0	추가	6	2025-11-13 08:26:21.768521	수동 추가: 추가학습 (추가학습)
455	39	2025-11-13	0	0	0	0	0	0	0	0	0	0	100	100	0	200	0	0	0	0	create	6	2025-11-13 08:28:59.666094	웹 UI를 통한 포인트 신규 입력
456	33	2025-11-13	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	1	2025-11-13 08:29:29.868927	웹 UI를 통한 포인트 신규 입력
457	39	2025-11-13	0	0	0	0	200	0	0	0	0	0	0	0	0	500	0	0	0	0	추가	6	2025-11-13 08:29:30.529808	수동 추가: 추가학습 (추가학습)
458	40	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	1	2025-11-14 05:27:32.292298	웹 UI를 통한 포인트 신규 입력
459	49	2025-11-14	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-14 06:12:47.778756	웹 UI를 통한 포인트 신규 입력
460	35	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-14 06:59:11.934002	웹 UI를 통한 포인트 신규 입력
461	32	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-11-14 07:04:22.217511	웹 UI를 통한 포인트 신규 입력
462	31	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-14 07:48:07.391051	웹 UI를 통한 포인트 신규 입력
463	50	2025-11-14	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-11-14 07:57:39.341327	웹 UI를 통한 포인트 신규 입력
464	33	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-14 08:04:16.082668	웹 UI를 통한 포인트 신규 입력
465	42	2025-11-14	0	0	0	0	0	0	0	0	0	0	200	0	0	200	0	0	0	0	create	6	2025-11-14 08:07:33.154207	웹 UI를 통한 포인트 신규 입력
466	47	2025-11-14	0	0	0	0	0	0	0	0	0	100	100	100	100	400	0	0	0	0	create	6	2025-11-14 08:17:41.323542	웹 UI를 통한 포인트 신규 입력
467	54	2025-11-14	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-11-14 08:20:56.611061	웹 UI를 통한 포인트 신규 입력
468	46	2025-11-14	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-14 08:29:47.28915	웹 UI를 통한 포인트 신규 입력
469	46	2025-11-14	0	0	0	0	500	0	0	0	0	0	0	0	0	300	0	0	0	0	차감	5	2025-11-14 08:30:43.396571	수동 차감: 프린트 (프린트)
470	31	2025-11-17	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-11-17 05:38:23.367534	웹 UI를 통한 포인트 신규 입력
471	49	2025-11-17	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-17 05:51:21.249509	웹 UI를 통한 포인트 신규 입력
472	49	2025-11-17	0	0	0	0	600	0	0	0	0	0	0	0	0	800	0	0	0	0	추가	6	2025-11-17 05:52:08.034773	수동 추가: 추가학습 (추가학습)
473	43	2025-11-17	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	5	2025-11-17 06:31:42.526942	웹 UI를 통한 포인트 신규 입력
474	42	2025-11-17	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-17 06:48:05.657116	웹 UI를 통한 포인트 신규 입력
475	45	2025-11-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-11-17 07:34:02.282631	웹 UI를 통한 포인트 신규 입력
476	54	2025-11-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-11-17 07:57:34.62493	웹 UI를 통한 포인트 신규 입력
477	40	2025-11-17	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-11-17 07:59:30.599181	웹 UI를 통한 포인트 신규 입력
478	32	2025-11-17	0	0	0	0	0	0	0	0	0	100	200	100	200	800	100	0	0	100	create	1	2025-11-17 08:10:41.619856	웹 UI를 통한 포인트 신규 입력
479	47	2025-11-17	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-17 08:15:39.979252	웹 UI를 통한 포인트 신규 입력
480	35	2025-11-17	0	0	0	0	0	0	0	0	0	200	100	100	200	800	100	0	0	100	create	5	2025-11-17 08:35:51.541969	웹 UI를 통한 포인트 신규 입력
481	36	2025-11-17	0	0	0	0	0	0	0	0	0	100	100	100	0	400	100	0	0	0	create	5	2025-11-17 08:54:27.92998	웹 UI를 통한 포인트 신규 입력
482	36	2025-11-17	0	0	0	0	400	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	5	2025-11-17 08:55:33.892674	수동 추가: 11/13 포인트 (포인트 누락)
483	31	2025-11-18	0	0	0	0	0	0	0	0	0	200	100	100	200	800	0	100	0	100	create	1	2025-11-18 06:24:22.673036	웹 UI를 통한 포인트 신규 입력
484	40	2025-11-18	0	0	0	0	0	0	0	0	0	0	0	0	0	-900	0	0	0	0	차감	1	2025-11-18 06:29:24.570028	수동 차감: 연필 (연필 3개 구매)
485	59	2025-11-18	0	0	0	0	0	0	0	0	0	200	0	100	200	600	0	100	0	0	create	5	2025-11-18 07:02:48.355121	웹 UI를 통한 포인트 신규 입력
486	32	2025-11-18	0	0	0	0	0	0	0	0	0	100	200	100	200	800	0	100	0	100	create	1	2025-11-18 07:43:11.981851	웹 UI를 통한 포인트 신규 입력
487	43	2025-11-18	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-11-18 07:43:27.726189	웹 UI를 통한 포인트 신규 입력
488	44	2025-11-18	0	0	0	0	0	0	0	0	0	100	0	100	0	300	0	100	0	0	create	1	2025-11-18 07:43:59.532924	웹 UI를 통한 포인트 신규 입력
489	40	2025-11-18	0	0	0	0	-900	0	0	0	0	200	100	100	200	-200	0	100	0	0	update	1	2025-11-18 07:49:26.715153	웹 UI를 통한 포인트 수정
490	50	2025-11-18	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-18 07:58:42.920732	웹 UI를 통한 포인트 신규 입력
491	46	2025-11-18	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-18 07:59:39.153761	웹 UI를 통한 포인트 신규 입력
492	44	2025-11-18	100	0	100	0	300	0	100	0	0	100	100	100	0	400	0	100	0	0	update	6	2025-11-18 08:20:51.746971	웹 UI를 통한 포인트 수정
493	44	2025-11-18	0	0	0	0	400	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	6	2025-11-18 08:22:03.763949	수동 추가: 추가학습 (추가학습)
494	48	2025-11-18	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-18 08:26:31.965013	웹 UI를 통한 포인트 신규 입력
495	38	2025-11-18	0	0	0	0	0	0	0	0	0	100	0	0	0	200	0	100	0	0	create	1	2025-11-18 08:29:02.076821	웹 UI를 통한 포인트 신규 입력
496	47	2025-11-18	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-18 08:31:09.491147	웹 UI를 통한 포인트 신규 입력
497	33	2025-11-18	0	0	0	0	0	0	0	0	0	0	0	0	0	700	0	0	0	0	추가	1	2025-11-18 08:51:16.683149	수동 추가: 11/17 포인트 (포인트 입력 누락)
498	54	2025-11-18	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-11-18 08:51:57.024714	웹 UI를 통한 포인트 신규 입력
499	33	2025-11-18	0	0	0	0	700	0	0	0	0	200	200	100	200	1600	0	100	0	100	update	1	2025-11-18 08:52:09.612755	웹 UI를 통한 포인트 수정
500	31	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	1	2025-11-19 04:46:29.21943	웹 UI를 통한 포인트 신규 입력
501	40	2025-11-19	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-11-19 05:36:30.186279	웹 UI를 통한 포인트 신규 입력
502	59	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-19 05:51:42.128369	웹 UI를 통한 포인트 신규 입력
503	59	2025-11-19	200	200	100	200	800	0	0	0	100	0	0	0	0	0	0	0	0	0	update	5	2025-11-19 05:51:56.874898	웹 UI를 통한 포인트 수정
504	35	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-19 05:52:19.558993	웹 UI를 통한 포인트 신규 입력
505	35	2025-11-19	0	0	0	0	800	0	0	0	0	0	0	0	0	1700	0	0	0	0	추가	5	2025-11-19 05:52:53.27767	수동 추가: 11/18 포인트 (포인트 누락)
506	43	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	5	2025-11-19 05:55:06.489201	웹 UI를 통한 포인트 신규 입력
507	32	2025-11-19	0	0	0	0	0	0	0	0	0	0	0	0	200	200	0	0	0	0	create	5	2025-11-19 07:36:26.198648	웹 UI를 통한 포인트 신규 입력
508	48	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-11-19 07:42:30.749534	웹 UI를 통한 포인트 신규 입력
509	33	2025-11-19	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	1	2025-11-19 07:42:55.422938	웹 UI를 통한 포인트 신규 입력
510	42	2025-11-19	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	6	2025-11-19 07:52:57.438614	웹 UI를 통한 포인트 신규 입력
511	36	2025-11-19	0	0	0	0	0	0	0	0	0	100	0	0	0	100	0	0	0	0	create	5	2025-11-19 07:56:41.769027	웹 UI를 통한 포인트 신규 입력
512	41	2025-11-19	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-19 08:15:55.697804	웹 UI를 통한 포인트 신규 입력
513	46	2025-11-19	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-19 08:28:53.450562	웹 UI를 통한 포인트 신규 입력
514	47	2025-11-19	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-11-19 08:29:38.501785	웹 UI를 통한 포인트 신규 입력
515	44	2025-11-19	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	6	2025-11-19 08:36:12.530122	웹 UI를 통한 포인트 신규 입력
516	44	2025-11-19	0	0	0	0	500	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	6	2025-11-19 08:37:24.628041	수동 추가: 추가학습 (추가학습)
517	39	2025-11-19	0	0	0	0	0	0	0	0	0	100	0	100	0	200	0	0	0	0	create	6	2025-11-19 08:38:18.578374	웹 UI를 통한 포인트 신규 입력
518	59	2025-11-19	0	0	0	0	0	0	0	0	0	200	0	100	200	500	0	0	0	0	update	1	2025-11-19 08:52:27.259186	웹 UI를 통한 포인트 수정
519	40	2025-11-20	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	1	2025-11-20 06:00:08.51555	웹 UI를 통한 포인트 신규 입력
520	42	2025-11-20	0	0	0	0	0	0	0	0	0	100	100	100	0	300	0	0	0	0	create	6	2025-11-20 06:38:35.185337	웹 UI를 통한 포인트 신규 입력
521	42	2025-11-20	0	0	0	0	300	0	0	0	0	0	0	0	0	400	0	0	0	0	추가	6	2025-11-20 06:39:27.81879	수동 추가: 추가학습 (추가학습)
522	35	2025-11-20	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-20 07:34:56.53936	웹 UI를 통한 포인트 신규 입력
523	41	2025-11-20	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-11-20 07:54:19.375178	웹 UI를 통한 포인트 신규 입력
524	47	2025-11-20	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-11-20 08:06:23.85391	웹 UI를 통한 포인트 신규 입력
525	33	2025-11-20	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	5	2025-11-20 08:22:05.525701	웹 UI를 통한 포인트 신규 입력
526	40	2025-11-21	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-11-21 05:47:31.0616	웹 UI를 통한 포인트 신규 입력
527	59	2025-11-21	0	0	0	0	0	0	0	0	0	200	0	100	200	600	0	100	0	0	create	5	2025-11-21 06:21:16.89035	웹 UI를 통한 포인트 신규 입력
528	43	2025-11-21	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-11-21 06:55:47.78424	웹 UI를 통한 포인트 신규 입력
529	35	2025-11-21	0	0	0	0	0	0	0	0	0	100	100	100	200	700	0	100	0	100	create	5	2025-11-21 07:01:26.604798	웹 UI를 통한 포인트 신규 입력
530	44	2025-11-21	0	0	0	0	0	0	0	0	0	0	0	0	0	100	0	100	0	0	create	5	2025-11-21 07:36:46.442349	웹 UI를 통한 포인트 신규 입력
531	50	2025-11-21	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-21 07:39:55.905849	웹 UI를 통한 포인트 신규 입력
532	48	2025-11-21	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-21 07:41:19.418975	웹 UI를 통한 포인트 신규 입력
533	46	2025-11-21	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-21 07:42:46.865877	웹 UI를 통한 포인트 신규 입력
534	32	2025-11-21	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	1	2025-11-21 08:03:58.659656	웹 UI를 통한 포인트 신규 입력
535	32	2025-11-21	0	0	0	0	800	0	0	0	0	0	0	0	0	1200	0	0	0	0	추가	1	2025-11-21 08:04:43.749621	수동 추가: 추가포인트 (어제 날짜 + 국어 더 풀음)
536	31	2025-11-21	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-11-21 08:24:45.104105	웹 UI를 통한 포인트 신규 입력
537	31	2025-11-21	0	0	0	0	900	0	0	0	0	0	0	0	0	1300	0	0	0	0	추가	1	2025-11-21 08:26:23.57628	수동 추가: 추가포인트 (어제 날짜 + 국어 더 풀음)
538	31	2025-11-24	0	0	0	0	0	0	0	0	0	100	200	100	200	800	100	0	0	100	create	5	2025-11-24 06:02:31.591558	웹 UI를 통한 포인트 신규 입력
539	43	2025-11-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	5	2025-11-24 06:16:33.617494	웹 UI를 통한 포인트 신규 입력
540	42	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-24 06:33:37.977567	웹 UI를 통한 포인트 신규 입력
541	49	2025-11-24	0	0	0	0	0	0	0	0	0	200	100	100	100	500	0	0	0	0	create	6	2025-11-24 06:41:10.546624	웹 UI를 통한 포인트 신규 입력
542	40	2025-11-24	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	5	2025-11-24 06:42:37.872689	웹 UI를 통한 포인트 신규 입력
543	46	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-24 06:48:32.758161	웹 UI를 통한 포인트 신규 입력
544	45	2025-11-24	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	6	2025-11-24 06:49:26.557834	웹 UI를 통한 포인트 신규 입력
545	59	2025-11-24	0	0	0	0	0	0	0	0	0	200	0	100	200	600	100	0	0	0	create	5	2025-11-24 07:42:46.938851	웹 UI를 통한 포인트 신규 입력
546	48	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-24 07:44:28.42637	웹 UI를 통한 포인트 신규 입력
547	32	2025-11-24	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	6	2025-11-24 07:52:42.54457	웹 UI를 통한 포인트 신규 입력
548	47	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	6	2025-11-24 07:59:08.550599	웹 UI를 통한 포인트 신규 입력
549	33	2025-11-24	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	6	2025-11-24 08:21:24.586128	웹 UI를 통한 포인트 신규 입력
550	50	2025-11-24	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	6	2025-11-24 08:25:23.843301	웹 UI를 통한 포인트 신규 입력
551	37	2025-11-24	0	0	0	0	0	0	0	0	0	200	200	100	0	600	100	0	0	0	create	6	2025-11-24 08:29:34.527522	웹 UI를 통한 포인트 신규 입력
552	54	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	5	2025-11-24 08:31:13.1453	웹 UI를 통한 포인트 신규 입력
553	44	2025-11-24	0	0	0	0	0	0	0	0	0	100	100	100	0	400	100	0	0	0	create	5	2025-11-24 08:34:20.800591	웹 UI를 통한 포인트 신규 입력
554	39	2025-11-24	0	0	0	0	0	0	0	0	0	0	0	0	0	5000	0	0	0	0	추가	6	2025-11-24 08:35:22.240483	수동 추가: 미기입포인트 (수첩교환미기입)
555	44	2025-11-24	0	0	0	0	400	0	0	0	0	0	0	0	0	500	0	0	0	0	추가	5	2025-11-24 08:35:27.80595	수동 추가: 11/21 포인트 (포인트 누락)
556	39	2025-11-24	0	0	0	0	5000	0	0	0	0	200	0	100	0	5400	100	0	0	0	update	6	2025-11-24 08:35:47.520359	웹 UI를 통한 포인트 수정
557	34	2025-11-24	0	0	0	0	0	0	0	0	0	0	0	0	0	900	0	0	0	0	추가	5	2025-11-24 08:54:21.792906	수동 추가: 11/18 포인트 (포인트 누락)
558	34	2025-11-24	0	0	0	0	900	0	0	0	0	0	0	0	0	1700	0	0	0	0	추가	5	2025-11-24 08:55:00.08751	수동 추가: 11/19 포인트  (포인트 누락)
559	34	2025-11-24	0	0	0	0	1700	0	0	0	0	0	0	0	0	2600	0	0	0	0	추가	5	2025-11-24 08:55:51.523418	수동 추가: 11/21 포인트 (포인트 누락)
560	34	2025-11-24	0	0	0	0	2600	0	0	0	0	200	200	100	100	3400	100	0	0	100	update	5	2025-11-24 08:56:54.794609	웹 UI를 통한 포인트 수정
561	49	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	6	2025-11-25 05:35:30.283173	웹 UI를 통한 포인트 신규 입력
562	35	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	6	2025-11-25 05:41:06.395863	웹 UI를 통한 포인트 신규 입력
563	31	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	6	2025-11-25 05:41:40.747481	웹 UI를 통한 포인트 신규 입력
564	45	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	0	200	400	0	0	0	0	create	6	2025-11-25 06:20:36.307499	웹 UI를 통한 포인트 신규 입력
565	46	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	6	2025-11-25 06:21:09.666887	웹 UI를 통한 포인트 신규 입력
566	40	2025-11-25	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	6	2025-11-25 06:21:43.585336	웹 UI를 통한 포인트 신규 입력
567	43	2025-11-25	0	0	0	0	0	0	0	0	0	100	0	0	200	300	0	0	0	0	create	6	2025-11-25 06:22:20.491878	웹 UI를 통한 포인트 신규 입력
568	50	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-25 07:22:38.693118	웹 UI를 통한 포인트 신규 입력
569	50	2025-11-25	0	0	0	0	600	0	0	0	0	0	0	0	0	1100	0	0	0	0	추가	6	2025-11-25 07:23:40.300418	수동 추가: 도우미 (도우미)
570	47	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	0	200	400	0	0	0	0	create	6	2025-11-25 07:29:22.25652	웹 UI를 통한 포인트 신규 입력
571	32	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	6	2025-11-25 07:32:37.119525	웹 UI를 통한 포인트 신규 입력
572	54	2025-11-25	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	6	2025-11-25 08:00:01.117373	웹 UI를 통한 포인트 신규 입력
573	44	2025-11-25	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	6	2025-11-25 08:04:40.391883	웹 UI를 통한 포인트 신규 입력
574	38	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	100	100	500	0	0	0	0	create	6	2025-11-25 08:14:29.002675	웹 UI를 통한 포인트 신규 입력
575	59	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	100	200	500	0	0	0	0	create	6	2025-11-25 08:17:53.755474	웹 UI를 통한 포인트 신규 입력
576	37	2025-11-25	0	0	0	0	0	0	0	0	0	200	100	100	100	500	0	0	0	0	create	6	2025-11-25 08:20:41.499336	웹 UI를 통한 포인트 신규 입력
577	48	2025-11-25	0	0	0	0	0	0	0	0	0	200	0	0	200	400	0	0	0	0	create	6	2025-11-25 08:26:15.531214	웹 UI를 통한 포인트 신규 입력
578	31	2025-11-26	0	0	0	0	0	0	0	0	0	200	0	0	200	500	0	0	0	100	create	6	2025-11-26 04:54:04.433248	웹 UI를 통한 포인트 신규 입력
579	35	2025-11-26	0	0	0	0	0	0	0	0	0	100	100	0	200	500	0	0	0	100	create	5	2025-11-26 05:37:03.495723	웹 UI를 통한 포인트 신규 입력
580	40	2025-11-26	0	0	0	0	0	0	0	0	0	100	0	100	200	400	0	0	0	0	create	5	2025-11-26 05:38:55.054004	웹 UI를 통한 포인트 신규 입력
581	50	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-11-26 05:52:30.204522	웹 UI를 통한 포인트 신규 입력
582	33	2025-11-26	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	5	2025-11-26 07:28:58.982448	웹 UI를 통한 포인트 신규 입력
583	43	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-11-26 07:33:32.992473	웹 UI를 통한 포인트 신규 입력
584	32	2025-11-26	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	0	0	100	create	6	2025-11-26 07:38:47.993509	웹 UI를 통한 포인트 신규 입력
585	43	2025-11-26	0	0	0	0	700	0	0	0	0	0	0	0	0	600	0	0	0	0	차감	5	2025-11-26 07:40:06.652977	수동 차감: 포인트 오류 (포인트 오류)
586	46	2025-11-26	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	6	2025-11-26 07:56:21.857556	웹 UI를 통한 포인트 신규 입력
587	45	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-11-26 07:57:01.596332	웹 UI를 통한 포인트 신규 입력
588	59	2025-11-26	0	0	0	0	0	0	0	0	0	200	0	100	200	500	0	0	0	0	create	5	2025-11-26 07:57:43.561396	웹 UI를 통한 포인트 신규 입력
589	59	2025-11-26	0	0	0	0	500	0	0	0	0	0	0	0	0	300	0	0	0	0	차감	5	2025-11-26 07:58:24.890983	수동 차감: 프린트 (프린트)
590	48	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	200	700	0	0	0	0	create	6	2025-11-26 08:04:21.132269	웹 UI를 통한 포인트 신규 입력
591	44	2025-11-26	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	5	2025-11-26 08:22:52.762514	웹 UI를 통한 포인트 신규 입력
592	44	2025-11-26	0	0	0	0	400	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	5	2025-11-26 08:23:33.383706	수동 추가: 5학년 수학 (5학년 수학)
593	52	2025-11-26	0	0	0	0	0	0	0	0	0	0	0	0	0	-200	0	0	0	0	차감	5	2025-11-26 08:24:17.379575	수동 차감: 프린트 (프린트)
594	54	2025-11-26	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-26 08:25:40.664109	웹 UI를 통한 포인트 신규 입력
595	34	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	5	2025-11-26 08:34:52.83994	웹 UI를 통한 포인트 신규 입력
596	34	2025-11-26	0	0	0	0	500	0	0	0	0	0	0	0	0	1000	0	0	0	0	추가	5	2025-11-26 08:35:35.878768	수동 추가: 추가 포인트 (추가 포인트 (쎈))
597	39	2025-11-26	0	0	0	0	0	0	0	0	0	200	200	100	0	500	0	0	0	0	create	6	2025-11-26 08:39:05.79785	웹 UI를 통한 포인트 신규 입력
598	40	2025-11-27	0	0	0	0	0	0	0	0	0	100	200	100	200	600	0	0	0	0	create	5	2025-11-27 05:37:35.378826	웹 UI를 통한 포인트 신규 입력
599	36	2025-11-27	0	0	0	0	0	0	0	0	0	0	0	0	0	300	0	0	0	0	추가	6	2025-11-27 05:47:04.939185	수동 추가: 24일 (미기입포인트)
600	36	2025-11-27	0	0	0	0	300	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	6	2025-11-27 05:47:47.073744	수동 추가: 25일 (미기입포인트)
601	59	2025-11-27	0	0	0	0	0	0	0	0	0	200	0	100	200	500	0	0	0	0	create	5	2025-11-27 06:04:56.83048	웹 UI를 통한 포인트 신규 입력
602	43	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	5	2025-11-27 06:08:34.535827	웹 UI를 통한 포인트 신규 입력
603	50	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-27 06:18:00.595207	웹 UI를 통한 포인트 신규 입력
604	48	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-27 06:55:50.134527	웹 UI를 통한 포인트 신규 입력
605	48	2025-11-27	0	0	0	0	600	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	6	2025-11-27 06:58:03.228843	수동 차감: 프린트 (프린트)
606	45	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-27 07:01:52.329319	웹 UI를 통한 포인트 신규 입력
607	45	2025-11-27	0	0	0	0	600	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	6	2025-11-27 07:03:06.180769	수동 차감: 프린트 (프린트)
608	59	2025-11-27	0	0	0	0	500	0	0	0	0	0	0	0	0	400	0	0	0	0	차감	5	2025-11-27 07:03:26.493496	수동 차감: 프린트 (프린트)
609	46	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-11-27 07:04:47.942483	웹 UI를 통한 포인트 신규 입력
610	32	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	0	0	100	create	6	2025-11-27 07:37:11.320865	웹 UI를 통한 포인트 신규 입력
611	36	2025-11-27	0	0	0	0	600	0	0	0	0	100	0	0	0	700	0	0	0	0	update	5	2025-11-27 07:51:02.318673	웹 UI를 통한 포인트 수정
612	31	2025-11-27	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-27 08:03:42.600732	웹 UI를 통한 포인트 신규 입력
613	44	2025-11-27	0	0	0	0	0	0	0	0	0	200	100	100	0	400	0	0	0	0	create	5	2025-11-27 08:06:22.801134	웹 UI를 통한 포인트 신규 입력
614	44	2025-11-27	0	0	0	0	400	0	0	0	0	0	0	0	0	600	0	0	0	0	추가	5	2025-11-27 08:07:35.996032	수동 추가: 5학년 수학 (수학)
615	38	2025-11-27	0	0	0	0	0	0	0	0	0	200	200	0	0	400	0	0	0	0	create	6	2025-11-27 08:13:00.830018	웹 UI를 통한 포인트 신규 입력
616	33	2025-11-27	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	0	0	100	create	5	2025-11-27 08:23:20.87083	웹 UI를 통한 포인트 신규 입력
617	39	2025-11-27	0	0	0	0	0	0	0	0	0	0	0	100	0	100	0	0	0	0	create	6	2025-11-27 08:37:50.704799	웹 UI를 통한 포인트 신규 입력
618	41	2025-11-27	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	5	2025-11-27 08:43:34.231351	웹 UI를 통한 포인트 신규 입력
619	59	2025-11-28	0	0	0	0	0	0	0	0	0	100	0	100	200	500	0	100	0	0	create	5	2025-11-28 06:09:02.795902	웹 UI를 통한 포인트 신규 입력
620	40	2025-11-28	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	5	2025-11-28 06:35:09.842798	웹 UI를 통한 포인트 신규 입력
621	43	2025-11-28	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-11-28 06:37:43.831779	웹 UI를 통한 포인트 신규 입력
622	35	2025-11-28	0	0	0	0	0	0	0	0	0	200	100	100	200	800	0	100	0	100	create	6	2025-11-28 06:52:08.371459	웹 UI를 통한 포인트 신규 입력
623	48	2025-11-28	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-28 07:03:22.869255	웹 UI를 통한 포인트 신규 입력
624	48	2025-11-28	0	0	0	0	600	0	0	0	0	0	0	0	0	300	0	0	0	0	차감	6	2025-11-28 07:04:22.728929	수동 차감: 프린트 (프린트)
625	46	2025-11-28	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	6	2025-11-28 07:05:56.463705	웹 UI를 통한 포인트 신규 입력
626	46	2025-11-28	0	0	0	0	700	0	0	0	0	0	0	0	0	500	0	0	0	0	차감	6	2025-11-28 07:07:13.11778	수동 차감: 프린트 (프린트)
627	49	2025-11-28	0	0	0	0	0	0	0	0	0	200	200	100	0	600	0	100	0	0	create	6	2025-11-28 07:39:54.885158	웹 UI를 통한 포인트 신규 입력
628	49	2025-11-28	0	0	0	0	600	0	0	0	0	0	0	0	0	1200	0	0	0	0	추가	6	2025-11-28 07:41:03.754404	수동 추가: 추가학습 (추가)
629	44	2025-11-28	0	0	0	0	0	0	0	0	0	200	200	100	0	600	0	100	0	0	create	6	2025-11-28 07:48:26.557673	웹 UI를 통한 포인트 신규 입력
630	44	2025-11-28	0	0	0	0	600	0	0	0	0	0	0	0	0	1100	0	0	0	0	추가	6	2025-11-28 07:49:22.923179	수동 추가: 추가학습 (추가)
631	31	2025-11-28	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	6	2025-11-28 07:58:19.036479	웹 UI를 통한 포인트 신규 입력
632	32	2025-11-28	0	0	0	0	0	0	0	0	0	100	200	100	200	800	0	100	0	100	create	6	2025-11-28 07:59:28.211978	웹 UI를 통한 포인트 신규 입력
633	47	2025-11-28	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-11-28 08:25:01.245296	웹 UI를 통한 포인트 신규 입력
634	31	2025-12-01	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-12-01 05:50:14.767413	웹 UI를 통한 포인트 신규 입력
635	43	2025-12-01	0	0	0	0	0	0	0	0	0	200	200	100	200	800	100	0	0	0	create	1	2025-12-01 06:04:09.622696	웹 UI를 통한 포인트 신규 입력
636	40	2025-12-01	0	0	0	0	0	0	0	0	0	100	100	100	200	600	100	0	0	0	create	1	2025-12-01 06:05:46.332247	웹 UI를 통한 포인트 신규 입력
637	50	2025-12-01	0	0	0	0	0	0	0	0	0	100	200	100	200	700	100	0	0	0	create	6	2025-12-01 06:35:10.814548	웹 UI를 통한 포인트 신규 입력
638	49	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	600	0	0	0	0	create	6	2025-12-01 06:43:51.614942	웹 UI를 통한 포인트 신규 입력
639	32	2025-12-01	0	0	0	0	0	0	0	0	0	200	200	100	200	900	100	0	0	100	create	1	2025-12-01 07:01:22.657361	웹 UI를 통한 포인트 신규 입력
640	48	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-12-01 07:42:00.064444	웹 UI를 통한 포인트 신규 입력
641	46	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-12-01 07:43:53.054212	웹 UI를 통한 포인트 신규 입력
642	47	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	6	2025-12-01 07:49:43.745762	웹 UI를 통한 포인트 신규 입력
643	36	2025-12-01	0	0	0	0	0	0	0	0	0	0	0	0	0	-300	0	0	0	0	차감	6	2025-12-01 07:51:31.620285	수동 차감: 연필  (연필)
644	35	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	800	100	0	0	100	create	6	2025-12-01 07:56:20.224337	웹 UI를 통한 포인트 신규 입력
645	45	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	700	100	0	0	0	create	1	2025-12-01 08:00:17.507602	웹 UI를 통한 포인트 신규 입력
646	41	2025-12-01	0	0	0	0	0	0	0	0	0	100	100	100	200	500	0	0	0	0	create	1	2025-12-01 08:17:19.345715	웹 UI를 통한 포인트 신규 입력
647	33	2025-12-01	0	0	0	0	0	0	0	0	0	100	200	100	200	800	100	0	0	100	create	1	2025-12-01 08:26:38.53364	웹 UI를 통한 포인트 신규 입력
648	59	2025-12-01	0	0	0	0	0	0	0	0	0	200	0	100	200	600	100	0	0	0	create	1	2025-12-01 08:33:40.815435	웹 UI를 통한 포인트 신규 입력
649	36	2025-12-01	0	0	0	0	-300	0	0	0	0	100	100	100	0	0	0	0	0	0	update	1	2025-12-01 08:50:15.564866	웹 UI를 통한 포인트 수정
650	34	2025-12-01	0	0	0	0	0	0	0	0	0	200	100	100	200	800	100	0	0	100	create	1	2025-12-01 09:02:31.822485	웹 UI를 통한 포인트 신규 입력
651	39	2025-12-02	0	0	0	0	0	0	0	0	0	100	100	0	0	200	0	0	0	0	create	6	2025-12-02 04:51:02.912953	웹 UI를 통한 포인트 신규 입력
652	49	2025-12-02	0	0	0	0	0	0	0	0	0	0	100	0	0	100	0	0	0	0	create	6	2025-12-02 05:40:15.624684	웹 UI를 통한 포인트 신규 입력
653	31	2025-12-02	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-12-02 05:48:49.940709	웹 UI를 통한 포인트 신규 입력
654	40	2025-12-02	0	0	0	0	0	0	0	0	0	100	200	100	200	700	0	100	0	0	create	1	2025-12-02 06:25:47.225943	웹 UI를 통한 포인트 신규 입력
655	43	2025-12-02	0	0	0	0	0	0	0	0	0	200	200	100	200	800	0	100	0	0	create	5	2025-12-02 06:25:56.788512	웹 UI를 통한 포인트 신규 입력
656	46	2025-12-02	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	5	2025-12-02 06:44:37.246452	웹 UI를 통한 포인트 신규 입력
657	45	2025-12-02	0	0	0	0	0	0	0	0	0	200	100	100	200	700	0	100	0	0	create	1	2025-12-02 06:45:23.146974	웹 UI를 통한 포인트 신규 입력
658	35	2025-12-02	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	5	2025-12-02 06:57:59.683665	웹 UI를 통한 포인트 신규 입력
659	47	2025-12-02	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	6	2025-12-02 07:52:37.902848	웹 UI를 통한 포인트 신규 입력
660	32	2025-12-02	0	0	0	0	0	0	0	0	0	200	100	100	200	800	0	100	0	100	create	1	2025-12-02 07:59:25.648111	웹 UI를 통한 포인트 신규 입력
661	48	2025-12-02	0	0	0	0	0	0	0	0	0	200	200	100	0	600	0	100	0	0	create	1	2025-12-02 08:48:27.376572	웹 UI를 통한 포인트 신규 입력
662	54	2025-12-02	0	0	0	0	0	0	0	0	0	100	100	100	200	600	0	100	0	0	create	1	2025-12-02 08:52:04.39583	웹 UI를 통한 포인트 신규 입력
663	59	2025-12-02	0	0	0	0	0	0	0	0	0	200	0	100	200	600	0	100	0	0	create	5	2025-12-02 08:53:50.639821	웹 UI를 통한 포인트 신규 입력
664	59	2025-12-02	200	0	100	200	600	0	100	0	0	200	0	100	0	400	0	100	0	0	update	5	2025-12-02 08:54:12.445997	웹 UI를 통한 포인트 수정
665	33	2025-12-02	0	0	0	0	0	0	0	0	0	200	200	100	200	900	0	100	0	100	create	1	2025-12-02 08:54:53.866803	웹 UI를 통한 포인트 신규 입력
666	43	2025-12-03	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	5	2025-12-03 05:11:54.987081	웹 UI를 통한 포인트 신규 입력
667	40	2025-12-03	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	5	2025-12-03 05:12:18.890849	웹 UI를 통한 포인트 신규 입력
668	31	2025-12-03	0	0	0	0	0	0	0	0	0	200	100	0	200	500	0	0	0	0	create	5	2025-12-03 05:12:47.93434	웹 UI를 통한 포인트 신규 입력
\.


--
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."user" (id, username, password_hash, name, role, created_at, login_attempts, last_attempt, is_locked, locked_until, email, firebase_uid) FROM stdin;
1	dev_hoon		dev_hoon	개발자	2025-09-30 04:44:07.838721	0	\N	f	\N	dev_hoon@gmail.com	rPz8S98pPscb6i2FVnjKtBH4d2f1
2	center_director		center_director	센터장	2025-10-02 13:20:07.871892	0	\N	f	\N	center_director@gmail.com	a8urJmIFrARGcWFMKHxLBwChOQI3
3	login_test		login_test	일반사용자	2025-10-04 08:56:37.908447	0	\N	f	\N	login_test@gmail.com	FUxSghdmJwV44yLY3dMsnWBOrHZ2
4	sowo_2		sowo_2	사회복무요원2	2025-10-14 04:09:46.600185	0	\N	f	\N	sowo_2@gmail.com	FnJw6SN9waf8OgHuDO0DMVq0Me42
5	sowo_1		sowo_1	사회복무요원1	2025-10-14 04:10:17.861234	0	\N	f	\N	sowo_1@gmail.com	t9qpfbwCgrcKtMppR2dHHQ64R6f1
6	teacher		teacher	돌봄선생님	2025-10-14 04:37:22.226538	0	\N	f	\N	teacher@gmail.com	KMekFkKB5RW8McMjDWVtuXBEKO63
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: realtime; Owner: supabase_admin
--

COPY realtime.schema_migrations (version, inserted_at) FROM stdin;
20211116024918	2025-09-30 03:32:38
20211116045059	2025-09-30 03:32:41
20211116050929	2025-09-30 03:32:43
20211116051442	2025-09-30 03:32:44
20211116212300	2025-09-30 03:32:46
20211116213355	2025-09-30 03:32:48
20211116213934	2025-09-30 03:32:50
20211116214523	2025-09-30 03:32:52
20211122062447	2025-09-30 03:32:54
20211124070109	2025-09-30 03:32:56
20211202204204	2025-09-30 03:32:58
20211202204605	2025-09-30 03:32:59
20211210212804	2025-09-30 03:33:05
20211228014915	2025-09-30 03:33:07
20220107221237	2025-09-30 03:33:09
20220228202821	2025-09-30 03:33:10
20220312004840	2025-09-30 03:33:12
20220603231003	2025-09-30 03:33:15
20220603232444	2025-09-30 03:33:17
20220615214548	2025-09-30 03:33:19
20220712093339	2025-09-30 03:33:21
20220908172859	2025-09-30 03:33:22
20220916233421	2025-09-30 03:33:24
20230119133233	2025-09-30 03:33:26
20230128025114	2025-09-30 03:33:28
20230128025212	2025-09-30 03:33:30
20230227211149	2025-09-30 03:33:32
20230228184745	2025-09-30 03:33:34
20230308225145	2025-09-30 03:33:35
20230328144023	2025-09-30 03:33:37
20231018144023	2025-09-30 03:33:39
20231204144023	2025-09-30 03:33:42
20231204144024	2025-09-30 03:33:44
20231204144025	2025-09-30 03:33:46
20240108234812	2025-09-30 03:33:47
20240109165339	2025-09-30 03:33:49
20240227174441	2025-09-30 03:33:52
20240311171622	2025-09-30 03:33:55
20240321100241	2025-09-30 03:33:59
20240401105812	2025-09-30 03:34:03
20240418121054	2025-09-30 03:34:06
20240523004032	2025-09-30 03:34:12
20240618124746	2025-09-30 03:34:14
20240801235015	2025-09-30 03:34:16
20240805133720	2025-09-30 03:34:17
20240827160934	2025-09-30 03:34:19
20240919163303	2025-09-30 03:34:22
20240919163305	2025-09-30 03:34:23
20241019105805	2025-09-30 03:34:25
20241030150047	2025-09-30 03:34:32
20241108114728	2025-09-30 03:34:34
20241121104152	2025-09-30 03:34:36
20241130184212	2025-09-30 03:34:38
20241220035512	2025-09-30 03:34:39
20241220123912	2025-09-30 03:34:41
20241224161212	2025-09-30 03:34:43
20250107150512	2025-09-30 03:34:45
20250110162412	2025-09-30 03:34:46
20250123174212	2025-09-30 03:34:48
20250128220012	2025-09-30 03:34:50
20250506224012	2025-09-30 03:34:51
20250523164012	2025-09-30 03:34:53
20250714121412	2025-09-30 03:34:55
20250905041441	2025-09-30 03:34:57
\.


--
-- Data for Name: subscription; Type: TABLE DATA; Schema: realtime; Owner: supabase_admin
--

COPY realtime.subscription (id, subscription_id, entity, filters, claims, created_at) FROM stdin;
\.


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets (id, name, owner, created_at, updated_at, public, avif_autodetection, file_size_limit, allowed_mime_types, owner_id, type) FROM stdin;
\.


--
-- Data for Name: buckets_analytics; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets_analytics (id, type, format, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.migrations (id, name, hash, executed_at) FROM stdin;
0	create-migrations-table	e18db593bcde2aca2a408c4d1100f6abba2195df	2025-09-30 03:32:35.700378
1	initialmigration	6ab16121fbaa08bbd11b712d05f358f9b555d777	2025-09-30 03:32:35.705624
2	storage-schema	5c7968fd083fcea04050c1b7f6253c9771b99011	2025-09-30 03:32:35.709721
3	pathtoken-column	2cb1b0004b817b29d5b0a971af16bafeede4b70d	2025-09-30 03:32:35.734023
4	add-migrations-rls	427c5b63fe1c5937495d9c635c263ee7a5905058	2025-09-30 03:32:35.783516
5	add-size-functions	79e081a1455b63666c1294a440f8ad4b1e6a7f84	2025-09-30 03:32:35.787756
6	change-column-name-in-get-size	f93f62afdf6613ee5e7e815b30d02dc990201044	2025-09-30 03:32:35.791267
7	add-rls-to-buckets	e7e7f86adbc51049f341dfe8d30256c1abca17aa	2025-09-30 03:32:35.794719
8	add-public-to-buckets	fd670db39ed65f9d08b01db09d6202503ca2bab3	2025-09-30 03:32:35.797768
9	fix-search-function	3a0af29f42e35a4d101c259ed955b67e1bee6825	2025-09-30 03:32:35.800593
10	search-files-search-function	68dc14822daad0ffac3746a502234f486182ef6e	2025-09-30 03:32:35.806037
11	add-trigger-to-auto-update-updated_at-column	7425bdb14366d1739fa8a18c83100636d74dcaa2	2025-09-30 03:32:35.810241
12	add-automatic-avif-detection-flag	8e92e1266eb29518b6a4c5313ab8f29dd0d08df9	2025-09-30 03:32:35.818152
13	add-bucket-custom-limits	cce962054138135cd9a8c4bcd531598684b25e7d	2025-09-30 03:32:35.821037
14	use-bytes-for-max-size	941c41b346f9802b411f06f30e972ad4744dad27	2025-09-30 03:32:35.823874
15	add-can-insert-object-function	934146bc38ead475f4ef4b555c524ee5d66799e5	2025-09-30 03:32:35.844686
16	add-version	76debf38d3fd07dcfc747ca49096457d95b1221b	2025-09-30 03:32:35.848376
17	drop-owner-foreign-key	f1cbb288f1b7a4c1eb8c38504b80ae2a0153d101	2025-09-30 03:32:35.851185
18	add_owner_id_column_deprecate_owner	e7a511b379110b08e2f214be852c35414749fe66	2025-09-30 03:32:35.854445
19	alter-default-value-objects-id	02e5e22a78626187e00d173dc45f58fa66a4f043	2025-09-30 03:32:35.859204
20	list-objects-with-delimiter	cd694ae708e51ba82bf012bba00caf4f3b6393b7	2025-09-30 03:32:35.862182
21	s3-multipart-uploads	8c804d4a566c40cd1e4cc5b3725a664a9303657f	2025-09-30 03:32:35.868657
22	s3-multipart-uploads-big-ints	9737dc258d2397953c9953d9b86920b8be0cdb73	2025-09-30 03:32:35.884802
23	optimize-search-function	9d7e604cddc4b56a5422dc68c9313f4a1b6f132c	2025-09-30 03:32:35.894768
24	operation-function	8312e37c2bf9e76bbe841aa5fda889206d2bf8aa	2025-09-30 03:32:35.898235
25	custom-metadata	d974c6057c3db1c1f847afa0e291e6165693b990	2025-09-30 03:32:35.900915
26	objects-prefixes	ef3f7871121cdc47a65308e6702519e853422ae2	2025-10-13 04:53:29.852931
27	search-v2	33b8f2a7ae53105f028e13e9fcda9dc4f356b4a2	2025-10-13 04:53:29.990614
28	object-bucket-name-sorting	ba85ec41b62c6a30a3f136788227ee47f311c436	2025-10-13 04:53:30.001168
29	create-prefixes	a7b1a22c0dc3ab630e3055bfec7ce7d2045c5b7b	2025-10-13 04:53:30.012568
30	update-object-levels	6c6f6cc9430d570f26284a24cf7b210599032db7	2025-10-13 04:53:30.019803
31	objects-level-index	33f1fef7ec7fea08bb892222f4f0f5d79bab5eb8	2025-10-13 04:53:30.027517
32	backward-compatible-index-on-objects	2d51eeb437a96868b36fcdfb1ddefdf13bef1647	2025-10-13 04:53:30.036664
33	backward-compatible-index-on-prefixes	fe473390e1b8c407434c0e470655945b110507bf	2025-10-13 04:53:30.042836
34	optimize-search-function-v1	82b0e469a00e8ebce495e29bfa70a0797f7ebd2c	2025-10-13 04:53:30.044455
35	add-insert-trigger-prefixes	63bb9fd05deb3dc5e9fa66c83e82b152f0caf589	2025-10-13 04:53:30.050553
36	optimise-existing-functions	81cf92eb0c36612865a18016a38496c530443899	2025-10-13 04:53:30.053765
37	add-bucket-name-length-trigger	3944135b4e3e8b22d6d4cbb568fe3b0b51df15c1	2025-10-13 04:53:30.067981
38	iceberg-catalog-flag-on-buckets	19a8bd89d5dfa69af7f222a46c726b7c41e462c5	2025-10-13 04:53:30.07082
39	add-search-v2-sort-support	39cf7d1e6bf515f4b02e41237aba845a7b492853	2025-10-13 04:53:30.089137
40	fix-prefix-race-conditions-optimized	fd02297e1c67df25a9fc110bf8c8a9af7fb06d1f	2025-10-13 04:53:30.092348
41	add-object-level-update-trigger	44c22478bf01744b2129efc480cd2edc9a7d60e9	2025-10-13 04:53:30.101962
42	rollback-prefix-triggers	f2ab4f526ab7f979541082992593938c05ee4b47	2025-10-13 04:53:30.107679
43	fix-object-level	ab837ad8f1c7d00cc0b7310e989a23388ff29fc6	2025-10-13 04:53:30.116017
\.


--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.objects (id, bucket_id, name, owner, created_at, updated_at, last_accessed_at, metadata, version, owner_id, user_metadata, level) FROM stdin;
\.


--
-- Data for Name: prefixes; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.prefixes (bucket_id, name, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads (id, in_progress_size, upload_signature, bucket_id, key, version, owner_id, created_at, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads_parts (id, upload_id, size, part_number, bucket_id, key, etag, owner_id, version, created_at) FROM stdin;
\.


--
-- Data for Name: secrets; Type: TABLE DATA; Schema: vault; Owner: supabase_admin
--

COPY vault.secrets (id, name, description, secret, key_id, nonce, created_at, updated_at) FROM stdin;
\.


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: supabase_auth_admin
--

SELECT pg_catalog.setval('auth.refresh_tokens_id_seq', 1, false);


--
-- Name: child_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.child_id_seq', 64, true);


--
-- Name: child_note_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.child_note_id_seq', 9, true);


--
-- Name: daily_points_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.daily_points_id_seq', 1292, true);


--
-- Name: learning_record_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.learning_record_id_seq', 210, true);


--
-- Name: notification_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notification_id_seq', 112, true);


--
-- Name: points_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.points_history_id_seq', 668, true);


--
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_id_seq', 6, true);


--
-- Name: subscription_id_seq; Type: SEQUENCE SET; Schema: realtime; Owner: supabase_admin
--

SELECT pg_catalog.setval('realtime.subscription_id_seq', 1, false);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_code_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_code_key UNIQUE (authorization_code);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_id_key UNIQUE (authorization_id);


--
-- Name: oauth_authorizations oauth_authorizations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_user_client_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_client_unique UNIQUE (user_id, client_id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: child_note child_note_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child_note
    ADD CONSTRAINT child_note_pkey PRIMARY KEY (id);


--
-- Name: child child_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child
    ADD CONSTRAINT child_pkey PRIMARY KEY (id);


--
-- Name: daily_points daily_points_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_points
    ADD CONSTRAINT daily_points_pkey PRIMARY KEY (id);


--
-- Name: learning_record learning_record_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_record
    ADD CONSTRAINT learning_record_pkey PRIMARY KEY (id);


--
-- Name: notification notification_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (id);


--
-- Name: points_history points_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.points_history
    ADD CONSTRAINT points_history_pkey PRIMARY KEY (id);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user user_firebase_uid_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_firebase_uid_key UNIQUE (firebase_uid);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user user_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_username_key UNIQUE (username);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets_analytics buckets_analytics_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets_analytics
    ADD CONSTRAINT buckets_analytics_pkey PRIMARY KEY (id);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: prefixes prefixes_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT prefixes_pkey PRIMARY KEY (bucket_id, level, name);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_auth_pending_exp_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_auth_pending_exp_idx ON auth.oauth_authorizations USING btree (expires_at) WHERE (status = 'pending'::auth.oauth_authorization_status);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: oauth_consents_active_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_client_idx ON auth.oauth_consents USING btree (client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_active_user_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_user_client_idx ON auth.oauth_consents USING btree (user_id, client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_user_order_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_user_order_idx ON auth.oauth_consents USING btree (user_id, granted_at DESC);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_oauth_client_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_oauth_client_id_idx ON auth.sessions USING btree (oauth_client_id);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: idx_child_grade; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_child_grade ON public.child USING btree (grade);


--
-- Name: idx_child_include_stats; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_child_include_stats ON public.child USING btree (include_in_stats) WHERE (include_in_stats = true);


--
-- Name: idx_daily_points_child_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_daily_points_child_id ON public.daily_points USING btree (child_id);


--
-- Name: idx_daily_points_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_daily_points_date ON public.daily_points USING btree (date);


--
-- Name: idx_daily_points_date_child; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_daily_points_date_child ON public.daily_points USING btree (date, child_id);


--
-- Name: idx_points_history_child_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_points_history_child_date ON public.points_history USING btree (child_id, date);


--
-- Name: idx_user_firebase_uid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_firebase_uid ON public."user" USING btree (firebase_uid);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: messages_inserted_at_topic_index; Type: INDEX; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE INDEX messages_inserted_at_topic_index ON ONLY realtime.messages USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: subscription_subscription_id_entity_filters_key; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_key ON realtime.subscription USING btree (subscription_id, entity, filters);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_name_bucket_level_unique; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX idx_name_bucket_level_unique ON storage.objects USING btree (name COLLATE "C", bucket_id, level);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: idx_objects_lower_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_lower_name ON storage.objects USING btree ((path_tokens[level]), lower(name) text_pattern_ops, bucket_id, level);


--
-- Name: idx_prefixes_lower_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_prefixes_lower_name ON storage.prefixes USING btree (bucket_id, level, ((string_to_array(name, '/'::text))[level]), lower(name) text_pattern_ops);


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: objects_bucket_id_level_idx; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX objects_bucket_id_level_idx ON storage.objects USING btree (bucket_id, level, name COLLATE "C");


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: supabase_admin
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: buckets enforce_bucket_name_length_trigger; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER enforce_bucket_name_length_trigger BEFORE INSERT OR UPDATE OF name ON storage.buckets FOR EACH ROW EXECUTE FUNCTION storage.enforce_bucket_name_length();


--
-- Name: objects objects_delete_delete_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_delete_delete_prefix AFTER DELETE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects objects_insert_create_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_insert_create_prefix BEFORE INSERT ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.objects_insert_prefix_trigger();


--
-- Name: objects objects_update_create_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_update_create_prefix BEFORE UPDATE ON storage.objects FOR EACH ROW WHEN (((new.name <> old.name) OR (new.bucket_id <> old.bucket_id))) EXECUTE FUNCTION storage.objects_update_prefix_trigger();


--
-- Name: prefixes prefixes_create_hierarchy; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER prefixes_create_hierarchy BEFORE INSERT ON storage.prefixes FOR EACH ROW WHEN ((pg_trigger_depth() < 1)) EXECUTE FUNCTION storage.prefixes_insert_trigger();


--
-- Name: prefixes prefixes_delete_hierarchy; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER prefixes_delete_hierarchy AFTER DELETE ON storage.prefixes FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_oauth_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_oauth_client_id_fkey FOREIGN KEY (oauth_client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: child_note child_note_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child_note
    ADD CONSTRAINT child_note_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.child(id);


--
-- Name: child_note child_note_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.child_note
    ADD CONSTRAINT child_note_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: daily_points daily_points_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_points
    ADD CONSTRAINT daily_points_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.child(id);


--
-- Name: daily_points daily_points_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_points
    ADD CONSTRAINT daily_points_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: learning_record learning_record_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_record
    ADD CONSTRAINT learning_record_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.child(id);


--
-- Name: learning_record learning_record_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_record
    ADD CONSTRAINT learning_record_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: notification notification_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.child(id);


--
-- Name: notification notification_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: notification notification_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public."user"(id);


--
-- Name: points_history points_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.points_history
    ADD CONSTRAINT points_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public."user"(id);


--
-- Name: points_history points_history_child_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.points_history
    ADD CONSTRAINT points_history_child_id_fkey FOREIGN KEY (child_id) REFERENCES public.child(id);


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: prefixes prefixes_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT "prefixes_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_analytics; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: prefixes; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.prefixes ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: postgres
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


ALTER PUBLICATION supabase_realtime OWNER TO postgres;

--
-- Name: SCHEMA auth; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA auth TO anon;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT USAGE ON SCHEMA auth TO service_role;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON SCHEMA auth TO dashboard_user;
GRANT USAGE ON SCHEMA auth TO postgres;


--
-- Name: SCHEMA extensions; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT ALL ON SCHEMA extensions TO dashboard_user;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO postgres;
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;


--
-- Name: SCHEMA realtime; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA realtime TO postgres;
GRANT USAGE ON SCHEMA realtime TO anon;
GRANT USAGE ON SCHEMA realtime TO authenticated;
GRANT USAGE ON SCHEMA realtime TO service_role;
GRANT ALL ON SCHEMA realtime TO supabase_realtime_admin;


--
-- Name: SCHEMA storage; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA storage TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA storage TO anon;
GRANT USAGE ON SCHEMA storage TO authenticated;
GRANT USAGE ON SCHEMA storage TO service_role;
GRANT ALL ON SCHEMA storage TO supabase_storage_admin;
GRANT ALL ON SCHEMA storage TO dashboard_user;


--
-- Name: SCHEMA vault; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA vault TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA vault TO service_role;


--
-- Name: FUNCTION email(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.email() TO dashboard_user;


--
-- Name: FUNCTION jwt(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.jwt() TO postgres;
GRANT ALL ON FUNCTION auth.jwt() TO dashboard_user;


--
-- Name: FUNCTION role(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.role() TO dashboard_user;


--
-- Name: FUNCTION uid(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.uid() TO dashboard_user;


--
-- Name: FUNCTION armor(bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.armor(bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO dashboard_user;


--
-- Name: FUNCTION armor(bytea, text[], text[]); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.armor(bytea, text[], text[]) FROM postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO dashboard_user;


--
-- Name: FUNCTION crypt(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.crypt(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO dashboard_user;


--
-- Name: FUNCTION dearmor(text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.dearmor(text) FROM postgres;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO dashboard_user;


--
-- Name: FUNCTION decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION decrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION digest(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.digest(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION digest(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.digest(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO dashboard_user;


--
-- Name: FUNCTION encrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION encrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION gen_random_bytes(integer); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_random_bytes(integer) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO dashboard_user;


--
-- Name: FUNCTION gen_random_uuid(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_random_uuid() FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO dashboard_user;


--
-- Name: FUNCTION gen_salt(text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_salt(text) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO dashboard_user;


--
-- Name: FUNCTION gen_salt(text, integer); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.gen_salt(text, integer) FROM postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO dashboard_user;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_cron_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO dashboard_user;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.grant_pg_graphql_access() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION grant_pg_net_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_net_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO dashboard_user;


--
-- Name: FUNCTION hmac(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.hmac(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION hmac(text, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.hmac(text, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO dashboard_user;


--
-- Name: FUNCTION pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) FROM postgres;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) TO dashboard_user;


--
-- Name: FUNCTION pgp_armor_headers(text, OUT key text, OUT value text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO dashboard_user;


--
-- Name: FUNCTION pgp_key_id(bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_key_id(bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO dashboard_user;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO dashboard_user;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) FROM postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO dashboard_user;


--
-- Name: FUNCTION pgrst_ddl_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_ddl_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgrst_drop_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_drop_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.set_graphql_placeholder() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v1(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v1() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v1mc(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v1mc() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v3(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v4(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v4() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO dashboard_user;


--
-- Name: FUNCTION uuid_generate_v5(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO dashboard_user;


--
-- Name: FUNCTION uuid_nil(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_nil() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_dns(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_dns() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_oid(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_oid() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_url(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_url() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO dashboard_user;


--
-- Name: FUNCTION uuid_ns_x500(); Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON FUNCTION extensions.uuid_ns_x500() FROM postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO dashboard_user;


--
-- Name: FUNCTION graphql("operationName" text, query text, variables jsonb, extensions jsonb); Type: ACL; Schema: graphql_public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO postgres;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO authenticated;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO service_role;


--
-- Name: FUNCTION get_auth(p_usename text); Type: ACL; Schema: pgbouncer; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION pgbouncer.get_auth(p_usename text) FROM PUBLIC;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO pgbouncer;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO postgres;


--
-- Name: FUNCTION apply_rls(wal jsonb, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO postgres;
GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO dashboard_user;


--
-- Name: FUNCTION build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO postgres;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO anon;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO service_role;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION "cast"(val text, type_ regtype); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO postgres;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO dashboard_user;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO anon;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO authenticated;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO service_role;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO supabase_realtime_admin;


--
-- Name: FUNCTION check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO postgres;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO anon;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO authenticated;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO service_role;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO supabase_realtime_admin;


--
-- Name: FUNCTION is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO postgres;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO anon;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO service_role;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION quote_wal2json(entity regclass); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO postgres;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO anon;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO authenticated;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO service_role;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO supabase_realtime_admin;


--
-- Name: FUNCTION send(payload jsonb, event text, topic text, private boolean); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO dashboard_user;


--
-- Name: FUNCTION subscription_check_filters(); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO postgres;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO dashboard_user;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO anon;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO authenticated;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO service_role;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO supabase_realtime_admin;


--
-- Name: FUNCTION to_regrole(role_name text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO postgres;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO anon;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO authenticated;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO service_role;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO supabase_realtime_admin;


--
-- Name: FUNCTION topic(); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.topic() TO postgres;
GRANT ALL ON FUNCTION realtime.topic() TO dashboard_user;


--
-- Name: FUNCTION _crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO service_role;


--
-- Name: FUNCTION create_secret(new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: FUNCTION update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: TABLE audit_log_entries; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.audit_log_entries TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.audit_log_entries TO postgres;
GRANT SELECT ON TABLE auth.audit_log_entries TO postgres WITH GRANT OPTION;


--
-- Name: TABLE flow_state; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.flow_state TO postgres;
GRANT SELECT ON TABLE auth.flow_state TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.flow_state TO dashboard_user;


--
-- Name: TABLE identities; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.identities TO postgres;
GRANT SELECT ON TABLE auth.identities TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.identities TO dashboard_user;


--
-- Name: TABLE instances; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.instances TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.instances TO postgres;
GRANT SELECT ON TABLE auth.instances TO postgres WITH GRANT OPTION;


--
-- Name: TABLE mfa_amr_claims; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_amr_claims TO postgres;
GRANT SELECT ON TABLE auth.mfa_amr_claims TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_amr_claims TO dashboard_user;


--
-- Name: TABLE mfa_challenges; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_challenges TO postgres;
GRANT SELECT ON TABLE auth.mfa_challenges TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_challenges TO dashboard_user;


--
-- Name: TABLE mfa_factors; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_factors TO postgres;
GRANT SELECT ON TABLE auth.mfa_factors TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_factors TO dashboard_user;


--
-- Name: TABLE oauth_authorizations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_authorizations TO postgres;
GRANT ALL ON TABLE auth.oauth_authorizations TO dashboard_user;


--
-- Name: TABLE oauth_clients; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_clients TO postgres;
GRANT ALL ON TABLE auth.oauth_clients TO dashboard_user;


--
-- Name: TABLE oauth_consents; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_consents TO postgres;
GRANT ALL ON TABLE auth.oauth_consents TO dashboard_user;


--
-- Name: TABLE one_time_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.one_time_tokens TO postgres;
GRANT SELECT ON TABLE auth.one_time_tokens TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.one_time_tokens TO dashboard_user;


--
-- Name: TABLE refresh_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.refresh_tokens TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.refresh_tokens TO postgres;
GRANT SELECT ON TABLE auth.refresh_tokens TO postgres WITH GRANT OPTION;


--
-- Name: SEQUENCE refresh_tokens_id_seq; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO dashboard_user;
GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO postgres;


--
-- Name: TABLE saml_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_providers TO postgres;
GRANT SELECT ON TABLE auth.saml_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_providers TO dashboard_user;


--
-- Name: TABLE saml_relay_states; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_relay_states TO postgres;
GRANT SELECT ON TABLE auth.saml_relay_states TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_relay_states TO dashboard_user;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT SELECT ON TABLE auth.schema_migrations TO postgres WITH GRANT OPTION;


--
-- Name: TABLE sessions; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sessions TO postgres;
GRANT SELECT ON TABLE auth.sessions TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sessions TO dashboard_user;


--
-- Name: TABLE sso_domains; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_domains TO postgres;
GRANT SELECT ON TABLE auth.sso_domains TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_domains TO dashboard_user;


--
-- Name: TABLE sso_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_providers TO postgres;
GRANT SELECT ON TABLE auth.sso_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_providers TO dashboard_user;


--
-- Name: TABLE users; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.users TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.users TO postgres;
GRANT SELECT ON TABLE auth.users TO postgres WITH GRANT OPTION;


--
-- Name: TABLE pg_stat_statements; Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON TABLE extensions.pg_stat_statements FROM postgres;
GRANT ALL ON TABLE extensions.pg_stat_statements TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE extensions.pg_stat_statements TO dashboard_user;


--
-- Name: TABLE pg_stat_statements_info; Type: ACL; Schema: extensions; Owner: postgres
--

REVOKE ALL ON TABLE extensions.pg_stat_statements_info FROM postgres;
GRANT ALL ON TABLE extensions.pg_stat_statements_info TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE extensions.pg_stat_statements_info TO dashboard_user;


--
-- Name: TABLE child; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.child TO anon;
GRANT ALL ON TABLE public.child TO authenticated;
GRANT ALL ON TABLE public.child TO service_role;


--
-- Name: SEQUENCE child_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.child_id_seq TO anon;
GRANT ALL ON SEQUENCE public.child_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.child_id_seq TO service_role;


--
-- Name: TABLE child_note; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.child_note TO anon;
GRANT ALL ON TABLE public.child_note TO authenticated;
GRANT ALL ON TABLE public.child_note TO service_role;


--
-- Name: SEQUENCE child_note_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.child_note_id_seq TO anon;
GRANT ALL ON SEQUENCE public.child_note_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.child_note_id_seq TO service_role;


--
-- Name: TABLE daily_points; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.daily_points TO anon;
GRANT ALL ON TABLE public.daily_points TO authenticated;
GRANT ALL ON TABLE public.daily_points TO service_role;


--
-- Name: SEQUENCE daily_points_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.daily_points_id_seq TO anon;
GRANT ALL ON SEQUENCE public.daily_points_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.daily_points_id_seq TO service_role;


--
-- Name: TABLE learning_record; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.learning_record TO anon;
GRANT ALL ON TABLE public.learning_record TO authenticated;
GRANT ALL ON TABLE public.learning_record TO service_role;


--
-- Name: SEQUENCE learning_record_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.learning_record_id_seq TO anon;
GRANT ALL ON SEQUENCE public.learning_record_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.learning_record_id_seq TO service_role;


--
-- Name: TABLE notification; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.notification TO anon;
GRANT ALL ON TABLE public.notification TO authenticated;
GRANT ALL ON TABLE public.notification TO service_role;


--
-- Name: SEQUENCE notification_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.notification_id_seq TO anon;
GRANT ALL ON SEQUENCE public.notification_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.notification_id_seq TO service_role;


--
-- Name: TABLE points_history; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.points_history TO anon;
GRANT ALL ON TABLE public.points_history TO authenticated;
GRANT ALL ON TABLE public.points_history TO service_role;


--
-- Name: SEQUENCE points_history_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.points_history_id_seq TO anon;
GRANT ALL ON SEQUENCE public.points_history_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.points_history_id_seq TO service_role;


--
-- Name: TABLE "user"; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public."user" TO anon;
GRANT ALL ON TABLE public."user" TO authenticated;
GRANT ALL ON TABLE public."user" TO service_role;


--
-- Name: SEQUENCE user_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.user_id_seq TO anon;
GRANT ALL ON SEQUENCE public.user_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.user_id_seq TO service_role;


--
-- Name: TABLE messages; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON TABLE realtime.messages TO postgres;
GRANT ALL ON TABLE realtime.messages TO dashboard_user;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO anon;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO authenticated;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO service_role;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.schema_migrations TO postgres;
GRANT ALL ON TABLE realtime.schema_migrations TO dashboard_user;
GRANT SELECT ON TABLE realtime.schema_migrations TO anon;
GRANT SELECT ON TABLE realtime.schema_migrations TO authenticated;
GRANT SELECT ON TABLE realtime.schema_migrations TO service_role;
GRANT ALL ON TABLE realtime.schema_migrations TO supabase_realtime_admin;


--
-- Name: TABLE subscription; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.subscription TO postgres;
GRANT ALL ON TABLE realtime.subscription TO dashboard_user;
GRANT SELECT ON TABLE realtime.subscription TO anon;
GRANT SELECT ON TABLE realtime.subscription TO authenticated;
GRANT SELECT ON TABLE realtime.subscription TO service_role;
GRANT ALL ON TABLE realtime.subscription TO supabase_realtime_admin;


--
-- Name: SEQUENCE subscription_id_seq; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO postgres;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO dashboard_user;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO anon;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO service_role;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO supabase_realtime_admin;


--
-- Name: TABLE buckets; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets TO anon;
GRANT ALL ON TABLE storage.buckets TO authenticated;
GRANT ALL ON TABLE storage.buckets TO service_role;
GRANT ALL ON TABLE storage.buckets TO postgres WITH GRANT OPTION;


--
-- Name: TABLE buckets_analytics; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets_analytics TO service_role;
GRANT ALL ON TABLE storage.buckets_analytics TO authenticated;
GRANT ALL ON TABLE storage.buckets_analytics TO anon;


--
-- Name: TABLE objects; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.objects TO anon;
GRANT ALL ON TABLE storage.objects TO authenticated;
GRANT ALL ON TABLE storage.objects TO service_role;
GRANT ALL ON TABLE storage.objects TO postgres WITH GRANT OPTION;


--
-- Name: TABLE prefixes; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.prefixes TO service_role;
GRANT ALL ON TABLE storage.prefixes TO authenticated;
GRANT ALL ON TABLE storage.prefixes TO anon;


--
-- Name: TABLE s3_multipart_uploads; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO anon;


--
-- Name: TABLE s3_multipart_uploads_parts; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads_parts TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO anon;


--
-- Name: TABLE secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.secrets TO service_role;


--
-- Name: TABLE decrypted_secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.decrypted_secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.decrypted_secrets TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON SEQUENCES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON FUNCTIONS TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON TABLES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO service_role;


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


ALTER EVENT TRIGGER issue_graphql_placeholder OWNER TO supabase_admin;

--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


ALTER EVENT TRIGGER issue_pg_cron_access OWNER TO supabase_admin;

--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE FUNCTION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


ALTER EVENT TRIGGER issue_pg_graphql_access OWNER TO supabase_admin;

--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


ALTER EVENT TRIGGER issue_pg_net_access OWNER TO supabase_admin;

--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


ALTER EVENT TRIGGER pgrst_ddl_watch OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


ALTER EVENT TRIGGER pgrst_drop_watch OWNER TO supabase_admin;

--
-- PostgreSQL database dump complete
--

\unrestrict ymVRjRMnxvPc2JkPdeKpxCv6teZVHWQSbNlX6cQbabVIPbGzPOAHwQ7ZfBkphG9

