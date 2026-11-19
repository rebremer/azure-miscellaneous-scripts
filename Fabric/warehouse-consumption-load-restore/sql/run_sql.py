"""Run the numbered .sql files (or an ad-hoc statement) against a Fabric warehouse.

Usage:
  python run_sql.py deploy                      # run 01_*.sql, 02_*.sql, ... in order
  python run_sql.py file demo\\01_x.sql          # run one script file
  python run_sql.py query "select 1"            # ad-hoc statement
Required env: FABRIC_SQL_SERVER, AZURE_TENANT_ID
Optional env: FABRIC_SQL_DB (default: dwh_consumption)
Requires: az login, pyodbc, ODBC Driver 18 for SQL Server.
"""
import glob, os, re, struct, subprocess, sys
import pyodbc

SERVER = os.getenv("FABRIC_SQL_SERVER") or sys.exit("Set FABRIC_SQL_SERVER to your warehouse SQL endpoint.")
DB = os.getenv("FABRIC_SQL_DB", "dwh_consumption")
TENANT = os.getenv("AZURE_TENANT_ID") or sys.exit("Set AZURE_TENANT_ID to your tenant ID.")


def connect():
    token = subprocess.check_output(
        f"az account get-access-token --tenant {TENANT} --resource https://database.windows.net/ --query accessToken -o tsv",
        shell=True, text=True).strip().encode("utf-16-le")
    for attempt in range(4):
        try:
            return pyodbc.connect(
                f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DB};Encrypt=yes",
                attrs_before={1256: struct.pack("<I", len(token)) + token}, autocommit=True)
        except pyodbc.OperationalError:
            if attempt == 3:
                raise


def run(cur, sql):
    for batch in re.split(r"^\s*GO\s*$", sql, flags=re.M | re.I):
        if batch.strip():
            run_batch(cur, batch)


def run_batch(cur, sql):
    cur.execute(sql)
    while True:
        if cur.description:
            print([c[0] for c in cur.description])
            for r in cur.fetchall():
                print(tuple(r))
        if not cur.nextset():
            break


if __name__ == "__main__":
    cur = connect().cursor()
    if sys.argv[1] == "deploy":
        here = os.path.dirname(os.path.abspath(__file__))
        for f in sorted(glob.glob(os.path.join(here, "[0-9][0-9]_*.sql"))):
            print("==>", os.path.basename(f))
            run(cur, open(f, encoding="utf-8").read())
    elif sys.argv[1] == "file":
        run(cur, open(sys.argv[2], encoding="utf-8").read())
    else:
        run(cur, sys.argv[2])