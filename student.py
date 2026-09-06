from app import db

class Student(db.Model):

    __tablename__="students"

    student_id=db.Column(db.Integer,primary_key=True)

    full_name=db.Column(db.String(100))

    email=db.Column(db.String(100),unique=True)

    phone=db.Column(db.String(15))

    hostel_name=db.Column(db.String(50))

    block_name=db.Column(db.String(20))

    room_number=db.Column(db.String(10))

    password=db.Column(db.String(255))