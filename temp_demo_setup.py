from app import initialize_database, get_db_connection, hash_password

initialize_database()

connection = get_db_connection()
cursor = connection.cursor(dictionary=True)

cursor.execute("SELECT id FROM students WHERE LOWER(email)=LOWER(%s)", ("studentdemo@example.com",))
row = cursor.fetchone()

if not row:
    cursor.execute(
        """
        INSERT INTO students (
            name, email, phone, hostel, block, room, password, status, rent_paid, rent_amount, rent_paid_amount
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            "Demo Student",
            "studentdemo@example.com",
            "9999999999",
            "Boys Hostel A",
            "Block A",
            "A-101",
            hash_password("student123"),
            "pending",
            "no",
            114000.00,
            0.00,
        ),
    )
    print("created")
else:
    print("exists")

cursor.execute("UPDATE students SET status=%s WHERE LOWER(email)=LOWER(%s)", ("approved", "studentdemo@example.com"))
connection.commit()
cursor.close()
connection.close()
print("approved")
