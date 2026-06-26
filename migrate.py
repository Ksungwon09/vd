"""
DB 마이그레이션 스크립트 — OAuth2 전환 시 기존 users 테이블에 새 컬럼 추가

실행 방법:
  python migrate.py

주의: 서버를 먼저 내리고 실행하거나, SQLite WAL 모드가 아닌 경우 잠금 주의.
"""

import sqlite3
import os

DB_PATH = os.path.join("data", "vdownloader.db")

MIGRATIONS = [
    # OAuth2 관련 컬럼 추가 (이미 존재하면 무시)
    ("google_id",            "ALTER TABLE users ADD COLUMN google_id TEXT"),
    ("nickname",             "ALTER TABLE users ADD COLUMN nickname TEXT"),
    ("google_refresh_token", "ALTER TABLE users ADD COLUMN google_refresh_token TEXT"),
    ("auth_provider",        "ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local'"),
    ("needs_nickname",       "ALTER TABLE users ADD COLUMN needs_nickname INTEGER DEFAULT 0"),
]


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run():
    if not os.path.exists(DB_PATH):
        print(f"[migrate] DB 파일을 찾을 수 없습니다: {DB_PATH}")
        print("[migrate] 서버를 한 번 기동하면 자동 생성됩니다. 이후 다시 실행해주세요.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    applied = 0
    for col_name, sql in MIGRATIONS:
        if not column_exists(cur, "users", col_name):
            print(f"[migrate] 컬럼 추가: {col_name}")
            cur.execute(sql)
            applied += 1
        else:
            print(f"[migrate] 이미 존재: {col_name} (건너뜀)")

    # 기존 로컬 계정의 auth_provider를 'local'로 업데이트
    cur.execute(
        "UPDATE users SET auth_provider = 'local' "
        "WHERE auth_provider IS NULL AND password_hash IS NOT NULL"
    )

    conn.commit()
    conn.close()

    print(f"\n[migrate] 완료: {applied}개 컬럼 추가됨.")
    if applied > 0:
        print("[migrate] 이제 서버를 기동하세요.")


if __name__ == "__main__":
    run()
