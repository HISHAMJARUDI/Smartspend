from sqlalchemy import inspect
from app.database import Base

import app.models

models = [
    "schools",
    "users",
    "students",
    "wallets",
    "cards",
    "canteen_terminals",
    "terminal_credentials",
    "transactions",
    "ledger_accounts",
    "ledger_entries",
]

for name in models:
    table = Base.metadata.tables.get(name)

    if table is None:
        print(f"\n{name}: NOT FOUND")
        continue

    print(f"\n{'=' * 55}")
    print(f"TABLE: {name}")
    print("=" * 55)

    for column in table.columns:
        properties = []

        if column.primary_key:
            properties.append("PK")

        if column.foreign_keys:
            targets = [
                fk.target_fullname
                for fk in column.foreign_keys
            ]
            properties.append(
                "FK -> " + ", ".join(targets)
            )

        if not column.nullable:
            properties.append("NOT NULL")

        if column.unique:
            properties.append("UNIQUE")

        if column.default is not None:
            properties.append("DEFAULT")

        print(
            f"{column.name:<24} "
            f"{str(column.type):<20} "
            f"{', '.join(properties)}"
        )
