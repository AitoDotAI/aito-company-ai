"""company-ai CLI: schema, loaders, the no-llm brief, and the log shorthand."""

import argparse
from datetime import date, datetime
from pathlib import Path

from . import brief as brief_mod
from . import loaders
from . import log as logbook
from . import schema
from .aito import AitoClient
from .config import SEED_DIR, Config, instance_host, is_local_instance


def _client(config: Config) -> AitoClient:
    return AitoClient(config.instance_url, config.api_key)


def _echo_target(config: Config) -> None:
    """Never let a write pick its target silently (findings 03, P0)."""
    print(f"→ aito: {instance_host(config.instance_url)}")


def _data_dir(args: argparse.Namespace, config: Config) -> Path:
    if args.dir:
        return Path(args.dir)
    if args.seed:
        return SEED_DIR
    assert config.data_dir, (
        "no data source: pass --seed, or set COMPANY_AI_DATA_DIR in .env, or pass --dir"
    )
    return config.data_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="company-ai",
        description="Loaders and schema for the company's Aito-backed sales agent.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("create-schema", help="create missing Aito tables")
    for name, help_text in (
        ("load-companies", "(re)load the companies entity (link target); load BEFORE contacts/deals"),
        ("load-rolodex", "(re)load contacts; drops touches, reload them after"),
        ("load-touches", "(re)load touches"),
        ("load-sessions", "(re)load website sessions (the acquisition funnel)"),
        ("load-materials", "(re)load the content catalog (materials)"),
        ("load-channels", "(re)load the channel catalog (channels)"),
        ("load-posts", "(re)load posts (material×channel); load materials+channels first"),
        ("load-todos", "(re)load the action source (the todos table)"),
        ("load-deals", "(re)load the sales pipeline (the deals table)"),
        ("load-decisions", "(re)load the decision log (the dogfood loop)"),
        ("load-experiments", "(re)load the experiments table (the learning board)"),
        ("load-events", "(re)load the events-to-attend table (the go/no-go board)"),
        ("load-documents", "(re)load the documents store (the knowledge store)"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--seed", action="store_true", help="load from data/seed/")
        p.add_argument("--dir", help="explicit data directory (overrides env and --seed)")
        p.add_argument("--force", action="store_true",
                       help="allow --seed against a non-local instance (dangerous)")

    cl = sub.add_parser("clear", help="empty a table back to a clean empty state")
    cl.add_argument("table", choices=sorted(schema.TABLES))

    ex = sub.add_parser("export", help="dump a table to a re-loadable CSV")
    ex.add_argument("table", choices=sorted(schema.TABLES))
    ex.add_argument("--dir", default=".", help="output directory (default: cwd)")

    sub.add_parser("doctor", help="read-only health/drift report for the instance")

    sub.add_parser("reindex-search",
                   help="rebuild the search index; embeds it when COMPANY_AI_EMBED_* is set")

    ea = sub.add_parser("export-all", help="dump every table to CSVs (migration step 1)")
    ea.add_argument("--dir", default=".", help="output directory (default: cwd)")

    la = sub.add_parser("load-all", help="load every CSV present in a dir (migration step 3)")
    la.add_argument("--seed", action="store_true", help="load from data/seed/")
    la.add_argument("--dir", help="explicit data directory (overrides env and --seed)")
    la.add_argument("--force", action="store_true",
                    help="allow --seed against a non-local instance (dangerous)")

    b = sub.add_parser("brief", help="the morning brief")
    b.add_argument("--no-llm", action="store_true",
                   help="print the raw three-query brief without a model in the loop")
    b.add_argument("--window", choices=sorted(schema.WINDOWS - {"other"}),
                   help="call window; default chosen from the current time")
    b.add_argument("--top-n", type=int, default=5)
    b.add_argument("--as-of", help="ISO date, defaults to today (used by booktests)")

    di = sub.add_parser("documents-import",
                        help="one-time import of a markdown dir into the documents store (docs/25)")
    di.add_argument("--dir", help="source dir of .md files; defaults to COMPANY_AI_LIBRARY_DIR")

    sub.add_parser("migrate-todo-revs",
                   help="one-time deploy step: version every todo (run with writers stopped)")

    sub.add_parser("migrate-journal",
                   help="one-time: fold journal entries into documents (Phase 2d, .ai/tasks/15)")

    tr = sub.add_parser("trilium-import",
                        help="import a Trilium note tree (Companies + daily) into documents (docs/25)")
    tr.add_argument("--db", required=True, help="path to the Trilium document.db (read-only)")
    tr.add_argument("--root", default="workspace", help="top-level Trilium note to scan under")
    tr.add_argument("--dry-run", action="store_true", help="print what would import; write nothing")

    d = sub.add_parser("dashboard", help="serve the read-only Segment 360 web dashboard")
    d.add_argument("--host", default="127.0.0.1")
    d.add_argument("--port", type=int, default=None,
                   help="default: COMPANY_AI_PORT from the env file, else 8770")

    br = sub.add_parser("board-run", help="run the week-prep composer (uses the LLM)")
    br.add_argument("prompt", choices=["week-prep.md"])
    br.add_argument("--mode", required=True, choices=["prepare", "plan"])
    br.add_argument("--as-of", help="ISO date, defaults to today")

    rr = sub.add_parser("routines-run",
                        help="auto-run every DUE routine through the assistant loop (uses the LLM)")
    rr.add_argument("--as-of", help="ISO date, defaults to today")
    rr.add_argument("--only", help="comma-separated routine_ids to limit the run")
    rr.add_argument("--force", action="store_true",
                    help="run even routines that aren't due (a deliberate re-run)")

    bk = sub.add_parser("backup", help="snapshot the database (Aito env), rotating old snapshots")
    bk.add_argument("--kind", choices=["daily", "tx"], default="daily",
                    help="daily (keep 7) or tx (keep 16, before risky write-bursts)")

    sub.add_parser("backups", help="list backup snapshots (restore points)")

    rs = sub.add_parser("restore", help="restore the database from a backup snapshot (promote an env)")
    rs.add_argument("name", help="the snapshot env to promote into master (see `backups`)")
    rs.add_argument("--force", action="store_true",
                    help="actually promote; without it, show the diff and stop (dry-run)")

    lg = sub.add_parser("log", help="log a touch: log <contact> <channel> <window> <outcome>")
    lg.add_argument("contact_id")
    lg.add_argument("channel")
    lg.add_argument("window")
    lg.add_argument("outcome")
    lg.add_argument("next_action", nargs="?", default=None)
    lg.add_argument("next_action_due", nargs="?", default=None,
                    help="ISO date; required when next_action is given")
    lg.add_argument("--notes", default=None)

    cp = sub.add_parser("complete", help="mark a todo done; advance its linked deal if given")
    cp.add_argument("todo_id")
    cp.add_argument("--deal-stage", choices=sorted(schema.DEAL_STAGES))
    cp.add_argument("--deal-probability", type=int)
    cp.add_argument("--deal-blocker", choices=sorted(schema.DEAL_BLOCKERS))

    ap = sub.add_parser("archive", help="archive (abandon) a todo; advances nothing")
    ap.add_argument("todo_id")

    args = parser.parse_args()
    config = Config.from_env()
    client = _client(config)

    # every command that writes echoes its target first — no silent db
    WRITE_CMDS = {"create-schema", "load-companies", "load-rolodex", "load-touches", "load-sessions",
                  "load-materials", "load-channels", "load-posts", "load-todos",
                  "load-deals", "load-decisions", "load-experiments", "load-events",
                  "load-documents", "documents-import", "migrate-journal", "migrate-todo-revs",
                  "trilium-import",
                  "load-all", "clear", "export", "export-all", "board-run",
                  "reindex-search",
                  "routines-run", "log", "complete", "archive", "backup", "restore"}
    if args.command in WRITE_CMDS:
        _echo_target(config)
    # refuse synthetic seed into a remote instance unless forced
    if args.command.startswith("load-") and getattr(args, "seed", False) \
            and not is_local_instance(config.instance_url) and not args.force:
        raise SystemExit(
            f"✗ refusing to load synthetic --seed data into a non-local instance "
            f"({instance_host(config.instance_url)}). Seed belongs on localhost; "
            f"re-run with --force only if you truly mean to overwrite it.")
    # mirror guard: refuse the PRIVATE dataset (a bare load-<table>, no --seed/
    # --dir, pulls COMPANY_AI_DATA_DIR) into a remote instance unless forced.
    # Real pipeline data belongs only on production/local, never on a shared
    # demo (docs/06-privacy). Use `./do seed <cfg>` for synthetic reloads.
    if args.command.startswith("load-") and not getattr(args, "seed", False) \
            and not getattr(args, "dir", None) and config.data_dir \
            and not is_local_instance(config.instance_url) \
            and not getattr(args, "force", False):
        raise SystemExit(
            f"✗ refusing to load the private dataset ({config.data_dir}) into a "
            f"non-local instance ({instance_host(config.instance_url)}). Real data "
            f"belongs on production only; use `./do seed` for a synthetic reload, "
            f"or --force if you truly mean to load real data here.")

    if args.command == "create-schema":
        report = loaders.create_schema(client)
        print(f"created tables: {report['created_tables'] or 'none'}")
        print(f"added columns:  {report['added_columns'] or 'none'}")
        if report["extra_columns"]:
            print(f"extra columns (left in place): {report['extra_columns']}")
        if report.get("needs_reload"):
            print(f"⚠ columns that need a reload to add (run load-<table>): "
                  f"{report['needs_reload']}")
        if not any((report["created_tables"], report["added_columns"],
                    report.get("needs_reload"))):
            print("schema already up to date")
    elif args.command == "load-companies":
        directory = _data_dir(args, config)
        count = loaders.load_companies(client, directory)
        print(f"companies: loaded {count} rows (distinct companies in the rolodex + deals CSVs)")
        print("note: load this BEFORE contacts/deals — it is their company_id link target")
    elif args.command == "load-rolodex":
        directory = _data_dir(args, config)
        count = loaders.load_rolodex(client, directory)
        print(f"contacts: loaded {count} rows from {directory / loaders.ROLODEX_FILE}")
        print("note: touches table was dropped (it links to contacts); run load-touches")
    elif args.command == "load-touches":
        directory = _data_dir(args, config)
        count = loaders.load_touches(client, directory)
        print(f"touches: loaded {count} rows from {directory / loaders.TOUCHES_FILE}")
    elif args.command == "load-sessions":
        directory = _data_dir(args, config)
        count = loaders.load_sessions(client, directory)
        print(f"sessions: loaded {count} rows from {directory / loaders.SESSIONS_FILE}")
    elif args.command == "load-materials":
        directory = _data_dir(args, config)
        count = loaders.load_materials(client, directory)
        print(f"materials: loaded {count} rows from {directory / loaders.MATERIALS_FILE}")
    elif args.command == "load-channels":
        directory = _data_dir(args, config)
        count = loaders.load_channels(client, directory)
        print(f"channels: loaded {count} rows from {directory / loaders.CHANNELS_FILE}")
    elif args.command == "load-posts":
        directory = _data_dir(args, config)
        count = loaders.load_posts(client, directory)
        print(f"posts: loaded {count} rows from {directory / loaders.POSTS_FILE}")
    elif args.command == "load-todos":
        directory = _data_dir(args, config)
        count = loaders.load_todos(client, directory)
        print(f"todos: loaded {count} rows from {directory / loaders.TODOS_FILE}")
    elif args.command == "load-deals":
        directory = _data_dir(args, config)
        count = loaders.load_deals(client, directory)
        print(f"deals: loaded {count} rows from {directory / loaders.DEALS_FILE}")
    elif args.command == "load-decisions":
        directory = _data_dir(args, config)
        count = loaders.load_decisions(client, directory)
        print(f"decisions: loaded {count} rows from {directory / loaders.DECISIONS_FILE}")
    elif args.command == "load-experiments":
        directory = _data_dir(args, config)
        count = loaders.load_experiments(client, directory)
        print(f"experiments: loaded {count} rows from {directory / loaders.EXPERIMENTS_FILE}")
    elif args.command == "load-events":
        directory = _data_dir(args, config)
        count = loaders.load_events(client, directory)
        print(f"events: loaded {count} rows from {directory / loaders.EVENTS_FILE}")
    elif args.command == "load-documents":
        directory = _data_dir(args, config)
        count = loaders.load_documents(client, directory)
        print(f"documents: loaded {count} rows from {directory / loaders.DOCUMENTS_FILE}")
    elif args.command == "documents-import":
        from . import documents
        source = Path(args.dir) if args.dir else config.library_dir
        rows = documents.scan_dir(source)
        report = logbook.import_documents(client, rows)
        print(f"documents-import from {source}: "
              f"+{report['added']} new, {report['replaced']} replaced, "
              f"{report['total']} total")
    elif args.command == "migrate-todo-revs":
        report = logbook.migrate_todo_revs(client)
        print(f"migrate-todo-revs: {report['versioned']} of {report['todos']} todos versioned; "
              f"all todos now carry a rev")
    elif args.command == "migrate-journal":
        report = logbook.migrate_journal(client)
        print(f"migrate-journal: +{report['migrated']} migrated, "
              f"{report['replaced']} replaced, {report['documents_total']} documents total")
    elif args.command == "trilium-import":
        from . import trilium
        if args.dry_run:
            rows = trilium.scan_trilium(args.db, root=args.root)
            co = sum(1 for r in rows if r["topics"] == "customer")
            print(f"trilium-import DRY RUN from {args.db}: {len(rows)} notes "
                  f"({co} company, {len(rows) - co} daily) — nothing written")
            for r in rows[:12]:
                print(f"  [{r['topics']}] {r['title']!r}  company={r['company']} noted_on={r['noted_on']}")
        else:
            report = trilium.import_trilium(client, args.db, root=args.root)
            print(f"trilium-import: +{report['added']} new, {report['replaced']} replaced, "
                  f"{report['companies_created']} companies created, {report['total']} documents total")
    elif args.command == "clear":
        loaders.clear_table(client, args.table)
        print(f"cleared {args.table}: now empty")
    elif args.command == "export":
        path, n = loaders.export_table(client, args.table, args.dir)
        print(f"exported {args.table}: {n} rows -> {path}")
    elif args.command == "doctor":
        report = loaders.diagnose(client)
        build = report["build"]
        print(f"instance: {instance_host(config.instance_url)}")
        if build.get("reachable"):
            print(f"build:    {build.get('builtAt', '?')}  git "
                  f"{str(build.get('gitRevision', '?'))[:10]}  version {build.get('version', '?')}")
        else:
            print("build:    UNREACHABLE")
        print(f"schema:   {'DRIFT' if report['schema_drift'] else 'matches the code'}")
        for t in report["tables"]:
            if not t["present"]:
                print(f"  {t['name']:12} — MISSING")
            else:
                miss = f"  missing cols {t['missing_columns']}" if t["missing_columns"] else ""
                extra = f"  +extra {t['extra_columns']}" if t["extra_columns"] else ""
                print(f"  {t['name']:12} {t['rows']:>6} rows{miss}{extra}")
                for m in t.get("mismatched_columns", []):
                    print(f"    ! {t['name']}.{m['column']} {m['field']}: "
                          f"code={m['want']!r} instance={m['have']!r} (needs recreate+reload)")
        if report["extra_tables"]:
            print(f"  extra tables (left in place): {report['extra_tables']}")
        if report["schema_drift"]:
            print("→ fix: company-ai create-schema  (adds missing tables/columns; "
                  "then reload any table flagged needs_reload or mismatched)")
    elif args.command == "reindex-search":
        # The only non-HTTP way to rebuild the index. Embedding happens HERE,
        # not on write (docs/23), so after turning COMPANY_AI_EMBED_* on, the
        # semantic layer stays dark until this runs — and the HTTP endpoint is
        # operator-only, which leaves an operator with no route at all.
        from . import embed as embed_mod
        from . import search as search_mod
        embedder = embed_mod.embedder(config) if config.embed_enabled else None
        if embedder is None:
            # Say WHICH file was read and WHICH names are missing. "Embeddings
            # are off" with no reason sends people to edit the wrong file — and
            # the dotenv that gets loaded is not always the one they think.
            # Names and set/unset only; never a value.
            import os
            names = ("COMPANY_AI_EMBED_ENDPOINT", "COMPANY_AI_EMBED_DEPLOYMENT",
                     "COMPANY_AI_EMBED_MODEL", "COMPANY_AI_EMBED_API_KEY",
                     "COMPANY_AI_LLM_API_KEY", "OPENAI_API_KEY",
                     "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_KEY",
                     "COMPANY_AI_LLM_AZURE_ENDPOINT", "REACT_APP_OPENAI_MODEL_URL",
                     "REACT_APP_OPENAI_MODEL_API_KEY")
            print("embeddings: OFF — text-match index only")
            print(f"  dotenv read: {os.environ.get('COMPANY_AI_ENV') or 'the default'}")
            for name in names:
                print(f"    {'set  ' if os.environ.get(name) else 'unset'}  {name}")
            print("  need EITHER  COMPANY_AI_EMBED_MODEL + a key      (OpenAI)")
            print("         OR    _ENDPOINT + _DEPLOYMENT + a key     (Azure)")
            print("  the key may be COMPANY_AI_EMBED_API_KEY or COMPANY_AI_LLM_API_KEY")
        else:
            kind = "Azure" if config.embed_is_azure else "OpenAI"
            print(f"embeddings: ON — {kind} {config.embed_target} — building vectors too")
        stats = search_mod.build_index(client, embed=embedder)
        print(f"  indexed {stats['indexed']} items")
        for kind, n in sorted(stats.get("by_kind", {}).items()):
            print(f"    {kind:8} {n}")
        if stats.get("vectors") is not None:
            print(f"  vectors {stats['vectors']}")
    elif args.command == "export-all":
        done = loaders.export_all(client, Path(args.dir))
        for table, n in done:
            print(f"  exported {table}: {n} rows")
        print(f"→ {len(done)} tables to {args.dir}")
    elif args.command == "load-all":
        directory = _data_dir(args, config)
        done = loaders.load_all(client, directory)
        for table, n in done:
            print(f"  loaded {table}: {n} rows")
        print(f"→ {len(done)} tables from {directory}")
    elif args.command == "brief":
        assert args.no_llm, (
            "the LLM brief runs in a Claude session via prompts/morning-brief.md; "
            "this CLI only renders the deterministic core: brief --no-llm"
        )
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        window = args.window or brief_mod.current_window(datetime.now().hour)
        print(brief_mod.render_brief(client, window, as_of, top_n=args.top_n))
    elif args.command == "board-run":
        from . import board
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        result = board.run(args.prompt, args.mode, client=client, as_of=as_of)
        print(f"# {args.prompt} ({args.mode}) via {result['model']}")
        if result["saved"]:
            print(f"# draft saved to {result['saved']}\n")
        print(result["text"])
    elif args.command == "routines-run":
        from . import routines
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        only = [s.strip() for s in args.only.split(",")] if args.only else None
        res = routines.run_due(client, as_of=as_of, only=only, force=args.force)
        print(f"# routines-run ({res['as_of']}): ran {res['count']} due routine(s)")
        for r in res["ran"]:
            print(f"  - {r['title'] or r['routine_id']}: "
                  f"{r['tool_calls']} tool call(s), {r['rounds']} round(s) -> document")
    elif args.command == "backup":
        import time
        from . import backups
        stamp = date.today().isoformat() if args.kind == backups.DAILY else str(int(time.time()))
        res = backups.backup(client, args.kind, stamp)
        print(f"backup: {res['created']} (keeping last {res['keep']} {args.kind})")
        if res["dropped"]:
            print(f"  rotated out: {', '.join(res['dropped'])}")
    elif args.command == "backups":
        from . import backups
        rows = backups.list_backups(client)
        if not rows:
            print("no backups yet — run `company-ai backup`")
        for r in rows:
            print(f"  {r['name']:28} [{r['kind']}]")
    elif args.command == "restore":
        import time
        from . import backups
        names = {e["name"] for e in client.list_envs()}
        if args.name not in names:
            raise SystemExit(f"unknown backup {args.name!r}; run `company-ai backups` to list")
        # show the diff so the operator sees exactly what master becomes
        snap = client.env_scoped(args.name)
        print(f"{'table':16} {'current':>8} {'backup':>8}")
        for tname in sorted(schema.TABLES):
            try:
                cur = client.count(tname)
            except Exception:
                cur = "-"
            try:
                bak = snap.count(tname)
            except Exception:
                bak = "-"
            print(f"{tname:16} {str(cur):>8} {str(bak):>8}")
        if not args.force:
            print(f"\nThis REPLACES master with '{args.name}'. Re-run with --force to do it.")
        else:
            res = backups.restore(client, args.name, str(int(time.time())))
            print(f"\nrestored master from {res['restored']} "
                  f"(undo point saved as {res['safety_snapshot']})")
    elif args.command == "dashboard":
        from . import api
        api.serve(config, host=args.host, port=args.port or config.port)
    elif args.command == "log":
        row = logbook.log_touch(
            client, args.contact_id, args.channel, args.window, args.outcome,
            next_action=args.next_action, next_action_due=args.next_action_due,
            notes=args.notes,
        )
        print(f"logged {row['touch_id']}: {row['contact_id']} {row['channel']} "
              f"{row['window']} {row['outcome']}")
    elif args.command == "complete":
        result = logbook.complete_todo(
            client, args.todo_id, deal_stage=args.deal_stage,
            deal_probability=args.deal_probability, deal_blocker=args.deal_blocker,
        )
        print(f"completed {result['todo']['todo_id']}: {result['todo']['title']}")
        if result["deal"]:
            d = result["deal"]
            print(f"  advanced deal {d['deal_id']} ({d['company']}) -> "
                  f"stage={d['stage']} probability={d['probability']}")
    elif args.command == "archive":
        result = logbook.archive_todo(client, args.todo_id)
        print(f"archived {result['todo']['todo_id']}: {result['todo']['title']}")


if __name__ == "__main__":
    main()
