import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "day1_minimal_demo" / "student.db"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "extracted_schema.txt"


def quote_identifier(name: str) -> str:
    """Safely quote a SQLite table name used in a PRAGMA statement."""
    return '"' + name.replace('"', '""') + '"'


def extract_schema(db_path: Path) -> str:
    """Read tables, columns and foreign keys from an existing SQLite database."""
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"找不到数据库文件：{db_path}")

    # mode=ro guarantees that schema extraction cannot modify the database.
    database_uri = f"{db_path.as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        if not table_rows:
            raise ValueError("数据库中没有可读取的用户表。")

        statements: list[str] = []
        for (table_name,) in table_rows:
            quoted_table = quote_identifier(table_name)
            columns = connection.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()
            foreign_keys = connection.execute(
                f"PRAGMA foreign_key_list({quoted_table})"
            ).fetchall()

            definitions: list[str] = []
            for _, column_name, data_type, not_null, default_value, primary_key in columns:
                parts = [column_name, data_type or "TEXT"]
                if primary_key:
                    parts.append("PRIMARY KEY")
                if not_null and not primary_key:
                    parts.append("NOT NULL")
                if default_value is not None:
                    parts.extend(["DEFAULT", str(default_value)])
                definitions.append("    " + " ".join(parts))

            # PRAGMA returns one row per foreign-key column. The demo database
            # only contains single-column foreign keys, so each row maps cleanly.
            for foreign_key in foreign_keys:
                _, _, referenced_table, from_column, to_column, *_ = foreign_key
                definitions.append(
                    "    "
                    f"FOREIGN KEY ({from_column}) "
                    f"REFERENCES {referenced_table}({to_column})"
                )

            statement = (
                f"CREATE TABLE {table_name} (\n"
                + ",\n".join(definitions)
                + "\n);"
            )
            statements.append(statement)

    return "\n\n".join(statements)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从SQLite数据库自动提取供Text-to-SQL使用的Schema"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    schema = extract_schema(args.db)
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(schema + "\n", encoding="utf-8")

    print(f"数据库：{args.db.resolve()}")
    print(f"Schema已保存：{output_path}")
    print("\n自动提取结果：\n")
    print(schema)


if __name__ == "__main__":
    main()

