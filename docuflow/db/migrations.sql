create table if not exists documents (
    document_id text primary key,
    file_path text not null,
    doc_type_hint text,
    status text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists processed_documents (
    id uuid primary key default gen_random_uuid(),
    document_id text not null references documents (document_id) on delete cascade,
    file_path text not null,
    doc_type_hint text,
    raw_text text,
    extracted_data jsonb,
    confidence_score double precision,
    validation_errors jsonb not null default '[]'::jsonb,
    category text,
    status text not null,
    created_at timestamptz not null default now()
);

create table if not exists pipeline_errors (
    id uuid primary key default gen_random_uuid(),
    document_id text not null,
    error text not null,
    created_at timestamptz not null default now()
);

create index if not exists processed_documents_document_id_idx
    on processed_documents (document_id);

create index if not exists pipeline_errors_document_id_idx
    on pipeline_errors (document_id);
