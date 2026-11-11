from app.database import SessionLocal
from app.services.terminal_service import create_terminal_secret


def main():
    with SessionLocal.begin() as db:
        key = create_terminal_secret(
            db=db,
            terminal_id=1,
        )

    print("Terminal credential created successfully.")
    print("Copy the key below into a secure location.")
    print("It will not be displayed again.")
    print()
    print(key)


if __name__ == "__main__":
    main()
