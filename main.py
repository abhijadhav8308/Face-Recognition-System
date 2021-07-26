from flask import Flask, render_template, session, url_for, redirect, render_template, request, Response, flash
from flask_mysqldb import MySQL
import pandas as pd
import numpy as np
import cv2,csv,os
from datetime import date
from PIL import Image

app = Flask(__name__)
app.secret_key = "abc"
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'face_detection'

mysql = MySQL(app)

recognizer = cv2.face.LBPHFaceRecognizer_create()
detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml");
recognizer.read('trainer/trainer.yml')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
font = cv2.FONT_HERSHEY_SIMPLEX
count = 1
pic_limit = 30
roll_numbers = []
student_dict = {}

def verify_face(img):
    global roll_numbers, student_dict
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, 1.3, 5)
    for(x,y,w,h) in faces:
        cv2.rectangle(img, (x,y), (x+w,y+h), (0,255,0), 2)
        roi_gray = gray[y:y + h, x:x + w]
        roi_color = img[y:y + h, x:x + w]
        eyes = eye_cascade.detectMultiScale(roi_gray,minNeighbors=15)
        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)
        id, confidence = recognizer.predict(gray[y:y+h,x:x+w])
        confidence = "{0}%".format(round(confidence))
        print("{} with confidence {}".format(id,confidence))
        if int(confidence.split('%')[0]) > 90:
            roll_numbers.append(-1)
            cv2.putText(img, "Unknown", (x+5,y-5), font, 1, (255,255,255), 2)
            cv2.putText(img, str(confidence), (x+5,y+h-5), font, 1, (255,255,0), 1)  
        else:
            roll_numbers.append(id)
            cv2.putText(img, student_dict[int(id)], (x+5,y-5), font, 1, (255,255,255), 2)
            cv2.putText(img, str(confidence), (x+5,y+h-5), font, 1, (255,255,0), 1)  
    return img    

def save_images(img,roll):
    global count,pic_limit
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, 1.3, 5)
    for (x,y,w,h) in faces:     
        cv2.rectangle(img, (x,y), (x+w,y+h), (255,0,0), 2)     
        if count<=pic_limit:
            cv2.imwrite("dataset/User." + str(roll) + '.' + str(count) + ".jpg", gray[y:y+h,x:x+w])
        else:
            count=0
    count+=1
    return img

def gen_frames(roll):
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()  
        if not success:
            break
        else:
            frame = save_images(frame,roll)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def gen_frames2():
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()  
        if not success:
            break
        else:
            frame = verify_face(frame)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/video_feed',methods=['GET','POST'])
def video_feed():
    roll = request.args.get("roll")
    if roll == "-1":
        global student_dict
        cur = mysql.connection.cursor()
        cur.execute("select * from student")
        result = cur.fetchall()
        for row in result:
            student_dict[row[0]]=row[1]
        return Response(gen_frames2(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return Response(gen_frames(roll), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/add_student',methods=['GET','POST'])
def add_student():
    if request.method == "POST":
        details = request.form
        roll_no = details['roll_no']
        stud_name = details['stud_name']
        stud_mail = details['stud_email']
        stud_number = details['stud_number']
        cur = mysql.connection.cursor()
        cur.execute("insert into student(id,name,email,number) values(%s,%s,%s,%s)",(roll_no, stud_name, stud_mail, stud_number))
        mysql.connection.commit()
        cur.close()
        flash("Student Added")
    return render_template('add_student.html')

@app.route('/view_student',methods=['GET','POST'])
def view_student():
    cur = mysql.connection.cursor()
    cur.execute("select * from student")
    result = cur.fetchall()
    cur.close() 
    return render_template('view_student.html',result=result)

@app.route('/edit_student',methods=['GET','POST'])
def edit_student():
    cur = mysql.connection.cursor()
    if request.method == "POST":
        details = request.form
        og_roll_no = details['og_roll_no']
        new_roll_no = details['roll_no']
        stud_name = details['stud_name']
        stud_mail = details['stud_email']
        stud_number = details['stud_number']
        cur.execute("update student set id=%s,name=%s,email=%s,number=%s where id=%s",(new_roll_no,stud_name,stud_mail,stud_number,og_roll_no))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('view_student'))
    roll_no=request.args.get('roll_no')
    cur.execute("select * from student where id = %s" % format(roll_no))
    result = cur.fetchone()
    cur.close() 
    return render_template('edit_student.html',roll_no=roll_no,result=result)

@app.route('/update_info',methods=['POST'])
def update_info():
    btn_value = request.form['update_btn']
    btn_value,roll_no = btn_value.split('(')
    roll_no = roll_no.replace(")", "")
    if btn_value == 'Edit':
        return redirect(url_for('edit_student',roll_no=roll_no))
    elif btn_value == 'Delete':
        cur = mysql.connection.cursor()
        cur.execute("delete from student where id = %s" % (roll_no))
        mysql.connection.commit()
        cur.close() 
    return redirect(url_for('view_student'))

@app.route('/train_model',methods=['GET','POST'])
def train_model():
    path = 'dataset'
    imagePaths = [os.path.join(path,f) for f in os.listdir(path)]     
    faceSamples=[]
    ids = []
    for imagePath in imagePaths:
        PIL_img = Image.open(imagePath).convert('L') 
        img_numpy = np.array(PIL_img,'uint8')
        id = int(os.path.split(imagePath)[-1].split(".")[1])
        faces = detector.detectMultiScale(img_numpy)
        for (x,y,w,h) in faces:
            faceSamples.append(img_numpy[y:y+h,x:x+w])
            ids.append(id)
    recognizer.train(faceSamples, np.array(ids))
    recognizer.write('trainer/trainer.yml')
    flash("{0} faces trained.".format(len(np.unique(ids))))
    return redirect(url_for('home'))

@app.route('/attendance',methods=['GET','POST'])
def attendance():
    cur = mysql.connection.cursor()
    if request.method == "POST":
        global roll_numbers,student_dict
        present_id = max(roll_numbers,key=roll_numbers.count)
        if present_id == -1:
            flash("You are not a valid student")
        else:
            cur = mysql.connection.cursor()
            temp = cur.execute("select * from attendance where roll_no={} and date=CURDATE()".format(present_id))
            result = cur.fetchone()
            if temp!=0:
                flash("Your Attendance is Already Marked")
            else:
                cur.execute("insert into attendance(roll_no,name,date) values(%s,%s,CURDATE())",(present_id, student_dict[present_id]))
                mysql.connection.commit()
                flash("Attendance Marked Successfully")
    temp = cur.execute("select * from attendance")
    data = cur.fetchall()
    cur.close()
    return render_template('attendance.html',data=data)

if __name__ == '__main__':
    app.run(debug=True)
