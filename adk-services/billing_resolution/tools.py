import sqlite3

DB_PATH = r"D:\Prodapt_Phase_2\data\telecom_ops.db"


async def lookup_billing_account(customer_id: str) -> dict:

    connection = sqlite3.connect(DB_PATH)

    # Get account information
    account = connection.execute(
        """
        SELECT
            customer_id,
            customer_name,
            account_type,
            current_balance,
            currency,
            account_status
        FROM billing_accounts
        WHERE customer_id = ?
        """,
        (customer_id,)
    ).fetchone()

    if not account:
        connection.close()

        return {
            "success": False,
            "message": f"Customer {customer_id} was not found."
        }

    # Get recent charges
    charges = connection.execute(
        """
        SELECT
            charge_id,
            description,
            amount,
            billing_period,
            charge_date,
            charge_type,
            is_duplicate_flag,
            invoice_status
        FROM billing_charges
        WHERE customer_id = ?
        ORDER BY charge_date DESC
        LIMIT 5
        """,
        (customer_id,)
    ).fetchall()

    connection.close()

    return {
        "success": True,
        "customer": {
            "customer_id": account[0],
            "customer_name": account[1],
            "account_type": account[2],
            "current_balance": account[3],
            "currency": account[4],
            "account_status": account[5]
        },
        "recent_charges": [
            {
                "charge_id": row[0],
                "description": row[1],
                "amount": row[2],
                "billing_period": row[3],
                "charge_date": row[4],
                "charge_type": row[5],
                "is_duplicate": bool(row[6]),
                "invoice_status": row[7]
            }
            for row in charges
        ]
    }


async def check_duplicate_charges(
    customer_id: str
) -> dict:

    connection = sqlite3.connect(DB_PATH)

    rows = connection.execute(
        """
        SELECT
            charge_id,
            description,
            amount,
            billing_period,
            charge_date,
            charge_type,
            invoice_status
        FROM billing_charges
        WHERE customer_id = ?
          AND is_duplicate_flag = 1
        ORDER BY charge_date DESC
        """,
        (customer_id,)
    ).fetchall()

    connection.close()

    duplicates = [
        {
            "charge_id": row[0],
            "description": row[1],
            "amount": row[2],
            "billing_period": row[3],
            "charge_date": row[4],
            "charge_type": row[5],
            "invoice_status": row[6]
        }
        for row in rows
    ]

    return {
        "success": True,
        "customer_id": customer_id,
        "duplicate_count": len(duplicates),
        "duplicate_charges": duplicates
    }


async def apply_billing_credit(
    customer_id: str,
    amount: float,
    reason: str
) -> dict:

    connection = sqlite3.connect(DB_PATH)

    # Check that the customer exists
    account = connection.execute(
        """
        SELECT current_balance
        FROM billing_accounts
        WHERE customer_id = ?
        """,
        (customer_id,)
    ).fetchone()

    if not account:
        connection.close()

        return {
            "success": False,
            "message": f"Customer {customer_id} was not found."
        }

    # Credits above $50 require approval
    if amount > 50:

        connection.execute(
            """
            INSERT INTO billing_credits
            (
                customer_id,
                amount,
                reason,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                customer_id,
                amount,
                reason,
                "PENDING_APPROVAL"
            )
        )

        connection.commit()
        connection.close()

        return {
            "success": True,
            "customer_id": customer_id,
            "amount": amount,
            "status": "PENDING_APPROVAL",
            "message": "Credit requires approval because it exceeds the $50 auto-approval limit."
        }

    # Credits of $50 or less are automatically approved
    connection.execute(
        """
        INSERT INTO billing_credits
        (
            customer_id,
            amount,
            reason,
            status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            customer_id,
            amount,
            reason,
            "APPLIED"
        )
    )

    # Apply the credit to the account balance
    connection.execute(
        """
        UPDATE billing_accounts
        SET current_balance = current_balance - ?
        WHERE customer_id = ?
        """,
        (
            amount,
            customer_id
        )
    )

    connection.commit()

    # Get the updated balance
    updated_account = connection.execute(
        """
        SELECT current_balance
        FROM billing_accounts
        WHERE customer_id = ?
        """,
        (customer_id,)
    ).fetchone()

    connection.close()

    return {
        "success": True,
        "customer_id": customer_id,
        "amount": amount,
        "status": "APPLIED",
        "new_balance": round(updated_account[0], 2),
        "message": "Credit applied successfully."
    }