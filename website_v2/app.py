import os
from flask import Flask, render_template, url_for, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from base64 import b64decode
import uuid
import io
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch
from torchvision import datasets
from torch.utils.data import DataLoader
import numpy as np
import cv2
import os


app = Flask(__name__)

UPLOAD_FOLDER = 'upload_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# detector code (Haider Zama) start
face_detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

def check_no_of_faces(f_path):
    img = cv2.imread(f_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    faces = face_detector.detectMultiScale(img, 1.1, 6)
    return len(faces), faces

def read_image(path):
    img = cv2.imread(path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    return img

def save_crop(img, faces, directory, idx=0, sf=20):
    i=idx
    print(f"index : {i}")
    for (x, y, w, h) in faces:
        # x = x - sf
        # y = y - 2*sf
        img2 = img
        # y:y+h+3*sf        x+w+2*sf
        crop = img2[y:y+h, x:x+w]
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        # img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
#         plt.imshow(np.squeeze(crop))
        cv2.imwrite(os.path.join(directory,'crop'+str(i)+'.jpeg'), crop)
#         cv2.imwrite('crop_img/crop'+str(i)+'.png',crop)
        i+=1

        print(x,y)

def add_data(path,username):
    img = read_image(path)
#     plt.imshow(img)
    directory = os.path.join('database',username)
    if not os.path.exists(directory):
        os.makedirs(directory)
        faces = face_detector.detectMultiScale(img, 1.1, 6)

        print(len(faces))
        if (len(faces) > 1):
            print("More than 1 face found!")
        elif (len(faces) == 0):
            print('No faces found')

        print(faces)
        save_crop(img, faces, directory)
        return '200'

    else:
        faces = face_detector.detectMultiScale(img, 1.1, 6)
        print(len(faces))
        if (len(faces) > 1):
            print("More than 1 face found!")
        elif (len(faces) == 0):
            print('No faces found')
        
        n = len(os.listdir(directory))
        save_crop(img, faces, directory, n)

def add_auth(path, faces):
    img = read_image(path)
#     plt.imshow(img)
    directory = os.path.join("images_for_auth")
    
    # faces = face_detector.detectMultiScale(img, 1.1, 6)
    # print(len(faces))
    
    if (len(faces) > 1):
        print("More than 1 face found!")
    elif (len(faces) == 0):
        print('No faces found')

    print(len(faces))
    save_crop(img, faces, directory)

# def add_to_database(f_path, u_name):
#     print(f_path)
#     fname = os.path.basename(f_path) 
#     print(fname)
#     if check_no_of_faces(f_path) == 0:
#         print("No faces found!")
#         return
#     if check_no_of_faces(f_path) > 1:
#         print("More than 1 faces found!")
#         return
#     directory = os.path.join('database',u_name)
#     if not os.path.exists(directory):
#         os.makedirs(directory)
#     new_path = os.path.join(directory,fname)
#     print(new_path)
#     os.replace(f_path, new_path)



mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) #initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() #initializing resnet for face img to embeding conversion


def face_match(img_path, data_path): # img_path= location of photo, data_path= location of data.pt 
    # getting embedding matrix of the given img
    img = Image.open(img_path)
    face, prob = mtcnn(img, return_prob=True) # returns cropped face and probability
    emb = resnet(face.unsqueeze(0)).detach() # detech is to make required gradient false
    
    saved_data = torch.load('data.pt') # loading data.pt file
    embedding_list = saved_data[0] # getting embedding data
    name_list = saved_data[1] # getting list of names
    dist_list = [] # list of matched distances, minimum distance is used to identify the person
    
    for idx, emb_db in enumerate(embedding_list):
        dist = torch.dist(emb, emb_db).item()
        dist_list.append(dist)
        
    idx_min = dist_list.index(min(dist_list))
    return (name_list[idx_min], min(dist_list))


# detector code (Haider Zama) end


class User(db.Model):
    username = db.Column(db.String(200), primary_key=True)
    def __repr__(self):
        return '<User %r>' % self.username

@app.route('/')
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        
        user = User.query.filter_by(username=username).first()
        if user == None:
            return render_template('index.html', user=username)
        else:
            return render_template('messages.html', message='The user is already registered in the database')

    else:
        return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user == None:
            return render_template('messages.html', message='User was not found in the database')
        else:
            return render_template('index.html', user=username)

    else:
        return render_template('login.html')

@app.route('/test-image', methods=['POST'])
def checkImage():
    filename = f'{uuid.uuid4().hex}.jpeg'
    message = request.get_json(force=True)
    encoded = message['image']
    decoded = b64decode(encoded)
    image = Image.open(io.BytesIO(decoded)) 
    # image.show()

    user = message['username']
    foundUser = User.query.filter_by(username=user).first()
    # if user is not fount, add to the database directory
    print('user: ', foundUser)
    print('filename outer: ', filename)
    if foundUser == None:
        # user came via signup
        image.save(filename)
        new_user = User(username=user)
        try:
            print('got user: ', user)
            db.session.add(new_user)
            db.session.commit()
            # add_to_database(filename, user)
            add_data(filename,user)
            print('filename inner: ', filename)
            os.remove(filename)
            response = {
                'prediction': { 'result': 'User was successfully registered' }
            }
        except:
            response = {
                'prediction': { 'result': 'There is already a user with the same name, try something different' }
            }
            
        return jsonify(response)
        # add_to_database(filename, user)
    # else save to the images_for_auth directory 
    else:
        # user came via login
        dataset=datasets.ImageFolder('database') # photos folder path 
        idx_to_class = {i:c for c,i in dataset.class_to_idx.items()} # accessing names of peoples from folder names

        def collate_fn(x):
            return x[0]

        loader = DataLoader(dataset, collate_fn=collate_fn)

        face_list = [] # list of cropped faces from photos folder
        name_list = [] # list of names corrospoing to cropped photos
        embedding_list = [] # list of embeding matrix after conversion from cropped faces to embedding matrix using resnet

        for img, idx in loader:
            face, prob = mtcnn(img, return_prob=True) 
            if face is not None and prob>0.90: # if face detected and porbability >         90%
                emb = resnet(face.unsqueeze(0)) # passing cropped face into resnet      model to get embedding matrix
                embedding_list.append(emb.detach()) # resulten embedding matrix is stored in a list
                name_list.append(idx_to_class[idx]) # names are stored in a list


        image.save('./images_for_auth/img.jpeg')
        data = [embedding_list, name_list]
        torch.save(data, 'data.pt') # saving data.pt file
        n, faces = check_no_of_faces('./images_for_auth/img.jpeg')
        add_auth('./images_for_auth/img.jpeg', faces)
        os.remove('./images_for_auth/img.jpeg')
        if n==0:
            response = {
                'prediction': { 'result': 'No Faces found' }
            }
        elif n>1:
            response = {
                'prediction': { 'result': 'More than one faces found' }
            }
        else:
            result = face_match('./images_for_auth/crop0.jpeg', 'data.pt')
            print(result)
            response = {
                'prediction': {
                    'result': result[0] if result[1]<0.84 else 'No Match found',
                }
            }
        return jsonify(response)




if __name__ == '__main__':
    app.run(debug=True)