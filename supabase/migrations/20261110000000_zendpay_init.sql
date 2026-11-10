-- Zendpay (SIMULATION - virtual funds only) : initial schema for Supabase Postgres.
-- Run once in: Supabase Dashboard > SQL Editor > New query > paste > Run.
-- Amounts are stored in minor units (cents) as bigint. Timestamps are UTC ISO-8601 text
-- ("2026-11-10T09:30:00") with "C" collation so they sort/compare chronologically.

create table if not exists public.users (
  id              bigint generated always as identity primary key,
  role            text not null default 'user' check (role in ('user', 'owner')),
  surname         text not null,
  first_name      text not null,
  email           text not null unique,
  country         text,
  dial            text,
  phone           text,
  account_type    text,
  currency        text not null,
  account_number  text not null unique,
  password_hash   text not null,
  pin_hash        text,
  status          text not null default 'pending'
                  check (status in ('pending','active','restricted','suspended','rejected','deleted')),
  status_note     text,
  balance         bigint not null default 0 check (balance >= 0),   -- DB-level overdraft guard
  created_at      text collate "C" not null,
  decided_at      text collate "C",
  last_login      text collate "C"
);
-- exactly one owner account
create unique index if not exists users_single_owner on public.users (role) where role = 'owner';
create index if not exists users_status on public.users (status);

create table if not exists public.transactions (
  id            bigint generated always as identity primary key,
  ref           text not null,
  user_id       bigint not null references public.users(id),
  category      text not null,
  direction     text not null check (direction in ('in', 'out')),
  amount        bigint not null check (amount > 0),
  fee           bigint not null default 0 check (fee >= 0),
  currency      text not null,
  status        text not null check (status in ('Successful', 'Pending', 'Failed')),
  cp_name       text,
  cp_account    text,
  cp_bank       text,
  note          text,
  created_at    text collate "C" not null
);
create index if not exists tx_user_created on public.transactions (user_id, created_at);
create index if not exists tx_ref on public.transactions (ref);

create table if not exists public.deposit_requests (
  id          bigint generated always as identity primary key,
  user_id     bigint not null references public.users(id),
  tx_id       bigint references public.transactions(id),
  amount      bigint not null check (amount > 0),
  currency    text not null,
  status      text not null default 'pending' check (status in ('pending', 'approved', 'declined')),
  created_at  text collate "C" not null,
  decided_at  text collate "C"
);
create index if not exists dep_status on public.deposit_requests (status, user_id);

create table if not exists public.bank_accounts (
  id              bigint generated always as identity primary key,
  bank_name       text not null,
  account_number  text not null,
  account_name    text not null,
  currency        text not null,
  active          integer not null default 1,
  created_at      text collate "C" not null,
  unique (bank_name, account_number)
);

create table if not exists public.activity (
  id          bigint generated always as identity primary key,
  actor       text,
  action      text not null,
  detail      text,
  created_at  text collate "C" not null
);
create index if not exists activity_id_desc on public.activity (id desc);

-- login / PIN rate limiting (serverless instances share no memory, so it lives here)
create table if not exists public.attempts (
  id  bigint generated always as identity primary key,
  k   text not null,
  ts  double precision not null
);
create index if not exists attempts_k_ts on public.attempts (k, ts);

-- ---------------------------------------------------------------------------
-- SECURITY: Supabase exposes every table in the public schema through its REST API.
-- Turn on Row Level Security with NO policies and revoke API roles, so the anon /
-- authenticated keys can never read or write these tables. The Zendpay server connects
-- with the database owner role (via DATABASE_URL), which is not affected by RLS.
-- ---------------------------------------------------------------------------
alter table public.users             enable row level security;
alter table public.transactions      enable row level security;
alter table public.deposit_requests  enable row level security;
alter table public.bank_accounts     enable row level security;
alter table public.activity          enable row level security;
alter table public.attempts          enable row level security;

do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on all tables in schema public from %I', r);
      execute format('revoke all on all sequences in schema public from %I', r);
      execute format('alter default privileges in schema public revoke all on tables from %I', r);
      execute format('alter default privileges in schema public revoke all on sequences from %I', r);
    end if;
  end loop;
end $$;
