"""Run sql/01..09 and 99_tests.sql in order on data/warehouse.duckdb, then export every table named out_* to data/output/.

    python src/run_sql.py            (all files)
    python src/run_sql.py 99         (only the files whose name starts with 99)
Stops with an error if a test in 99_tests.sql fails.
"""
import os
import sys

import duckdb

from common import DB, OUT, ROOT


def run(prefixes=None):
    os.chdir(ROOT)                                    # SQL files read data/... with relative paths
    con = duckdb.connect(str(DB))
    con.execute("CREATE TABLE IF NOT EXISTS workbook_kpi (metric VARCHAR, market VARCHAR, value DOUBLE)")
    for f in sorted((ROOT / "sql").glob("*.sql")):
        if prefixes and not f.name.startswith(tuple(prefixes)):
            continue
        con.execute(f.read_text(encoding="utf-8"))
        print("ran", f.name)
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'out\\_%' ESCAPE '\\'").fetchall():
        con.execute(f"COPY {t} TO '{(OUT / (t[4:] + '.csv')).as_posix()}' (HEADER)")
    res = con.execute("SELECT test, result, detail FROM test_results ORDER BY test").fetchall() if \
        con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'test_results'").fetchone()[0] else []
    con.close()
    for t, r, d in res:
        print(f"  {r:5} {t}: {d}")
    failed = [t for t, r, _ in res if r == "FAIL"]
    if failed:
        sys.exit(f"{len(failed)} test(s) failed: {failed}")
    return res


if __name__ == "__main__":
    run(sys.argv[1:] or None)
