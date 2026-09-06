from app import app, seed_admin_user

if __name__ == "__main__":
    seed_admin_user()
    app.run(host="127.0.0.1", port=5000, debug=True)
