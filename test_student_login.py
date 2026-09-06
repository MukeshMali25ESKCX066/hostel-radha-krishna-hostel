#!/usr/bin/env python3
"""
Test script to create a student account and verify login functionality
"""
import mysql.connector
from werkzeug.security import generate_password_hash

def create_test_student():
    try:
        # Connect to database
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="hostel_tracker",
        )
        cursor = connection.cursor()
        
        # Insert a test student
        test_email = "student@test.com"
        test_password = "test123"
        hashed_password = generate_password_hash(test_password)
        
        # Check if student already exists
        cursor.execute("SELECT * FROM students WHERE email=%s", (test_email,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"✓ Test student already exists: {test_email}")
        else:
            cursor.execute(
                """
                INSERT INTO students (name, email, phone, hostel, block, room, password, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                ("Test Student", test_email, "9999999999", "Hostel A", "Block 1", "101", hashed_password, "approved")
            )
            connection.commit()
            print(f"✓ Test student created: {test_email}")
        
        cursor.close()
        connection.close()
        print(f"\nYou can now login with:")
        print(f"  Email: {test_email}")
        print(f"  Password: {test_password}")
        print(f"\nURL: http://127.0.0.1:5000/student-login")
        
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    create_test_student()
