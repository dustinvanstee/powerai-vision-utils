# paiv_utils.py

# Set of utility functions and classes to help me with PAIV projects
import cv2
import json
import requests
from PIL import ImageFont, ImageDraw, Image
import numpy as np
import colorsys
import random
import sys
from queue import Queue
from threading import Thread
import glob
import xml.etree.ElementTree
import os
import hashlib
import time
from sklearn.metrics import confusion_matrix
import sklearn_utils as su

# functions that start with _ imply that these are private functions

def nprint(mystring) :
    print("{} : {}".format(sys._getframe(1).f_code.co_name,mystring))


def _convert_xml(filein) :
    e = xml.etree.ElementTree.parse(filein).getroot()
    #class_list = []
    #box_list = []
    rv_list = []
    for obj in e.findall('object') :
        objclass = obj.find('name').text
        objclass = objclass.replace(' ','_')
        xmin = int(obj.find('bndbox').find('xmin').text)
        ymin = int(obj.find('bndbox').find('ymin').text)
        xmax = int(obj.find('bndbox').find('xmax').text)
        ymax = int(obj.find('bndbox').find('ymax').text)

        if(xmin < 0.0 or ymin < 0.0 or xmax < 0 or ymax <0 ) :
            nprint("Error, file {} somehow has a negative pixel location recorded.  Omitting that box ....".format(filein))
        else :
            box_dict = {"label" : objclass, "xmin" : xmin, "ymin" : ymin, "xmax" : xmax, "xmin" : xmin}
            #class_list.append(objclass)
            #box_list.append([xmin,ymin,xmax,ymax])
            rv_list.append(box_dict)
    # zip the class and box dimensions !
    #rv = list(zip(class_list,box_list))
    #image_name =  get_image_from_xml(filein)
    #pdb.set_trace()
    #write_coco_labels(experiment_dir,image_name,0.0,box_list,class_list,cn_dict,labels_file)

    return rv_list

def get_image_fn(paiv_file_name_base) :
    image_file = paiv_file_name_base + ".JPG"
    if(not(os.path.isfile(image_file))):
        image_file = paiv_file_name_base + ".jpg"
    if(not(os.path.isfile(image_file))):
        image_file = paiv_file_name_base + ".png"
    if(not(os.path.isfile(image_file))):
        image_file = None

    return image_file

# Hash function to uniquely identify an image by just pixel values
def get_np_hash(npary) :
    return hashlib.md5(npary.data).hexdigest()

#  Function to Read in an AI Vision data directory and return a python object (dict)
#  to be used for all kinds of experiments.
#  supports both object, classification modes (validate_mode setting)
#  returns a dictionary of dictionaries
#    top level dictionary keys are hash of np array
#      second level dictionary is the metadata associated with the image
def _load_paiv_dataset(data_dir, validate_mode) :
    paiv_dataset = {}
    if(os.path.exists(data_dir)) :
        os.chdir(data_dir)

        if(validate_mode == "object") :
            xml_file_list = glob.glob("*.xml")
            for xf in xml_file_list :
                (xf_file_base,junk) = xf.split(".")
                image_fn = get_image_fn(xf_file_base)
                np_hash = get_np_hash(cv2.imread(image_fn))
                paiv_dataset[np_hash] = {'id' : xf_file_base , 'boxes' : _convert_xml(xf)}
        else : # classification
            # read in prop.json file and stuff into hash !
            json_str = open(data_dir + "/prop.json").read()
            json_parsed = json.loads(json_str)
            file_class_list = json.loads(json_parsed['file_prop_info'])

            for i in file_class_list :
                xf_file_base = i['_id']
                # print(xf_file_base)

                image_fn = get_image_fn(xf_file_base)
                if(image_fn != None) :
                    np_hash = get_np_hash(cv2.imread(image_fn))
                    paiv_dataset[np_hash] = {'id' : xf_file_base, 'class' : i['category_name']}  # save the class for the image!


    else :
        nprint("Data Directory {} does not exist".format(data_dir))

    return paiv_dataset


def validate_model(paiv_results_file,  image_dir,  validate_mode) :
    '''
    Validate model : 
        prerequisites : 
        1.  first need to run paiv.fetch_scores to build a paiv_results_file.  This file contains
        all the scored results from hitting a PAIV model with images/video from a directory
        2.  need to specify the image directory where the source images exist
        
        3.  validate_mode is based on either doing object detection or classification validation ['object'|'classification']


    '''
    #test exists
    nprint("Loading Dataset to get ground truth labels")
    ground_truth = _load_paiv_dataset(image_dir, validate_mode)

    model_predictions_json = open(paiv_results_file).read()
    model_predictions = json.loads(model_predictions_json)

    #  Truth table
    # use sklearn metrics confusion_matrix.  need to build a long list of y_true, y_pred
    tt_label = {}
    ytrue_cum = []
    ypred_cum = []
    for mykey in model_predictions.keys() :
        # Each prediction could have a list of boxes ..
        print("model prediction : {}".format(model_predictions[mykey]))
        print("ground_truth     : {}".format(ground_truth[mykey]))
        if(validate_mode == 'object') :
            (ytrue, ypred) = return_ytrue_ypre_objdet(ground_truth[mykey]['boxes'], model_predictions[mykey]['classified'])
        elif(validate_mode == 'classification') :
            (ytrue, ypred) = return_ytrue_ypre_classification(ground_truth[mykey], model_predictions[mykey]['classified'])
        else :
            nprint("Error : invalid validate_mode passed")
        ytrue_cum = ytrue_cum + ytrue
        ypred_cum = ypred_cum + ypred
    # Function to automatically fetch data from API in threaded mode...
    # modes = video / image_dir
    classes = list(set(ytrue_cum+ypred_cum))
    cm = confusion_matrix(ytrue_cum, ypred_cum, labels=classes)
    su.plot_confusion_matrix(cm, classes, title='confusion matrix',normalize=False)
    print(cm)
    diag_sum = 0
    total_sum = np.sum(cm)
    for i in range(len(classes)) :
        tp = float(cm[i,i])
        diag_sum += tp
        tpfp = float(np.sum(cm[:,i]))
        tpfn = float(np.sum(cm[i,:]))
        fn = tpfn - tp
        fp = tpfp - tp
        if(tpfp != 0) :
            precision = tp / tpfp
        else :
            precision = 0.0

        if(tpfn != 0) :
            recall    = tp / tpfn
        else :
            recall = 0.0

        #nprint("class  = {} TP = {}  TP+FP ={}  TP+FN = {} ".format(classes[i], cm[i,i],np.sum(cm[:,i]),np.sum(cm[i,:])))
        nprint("class = {} : tp = {} : fp = {} : fn = {} : Precision = {:0.2f}  Recall = {:0.2f}".format(classes[i],tp,fp, fn,precision,recall))
    nprint("Overall Accuracy = {:0.2f}".format(diag_sum/total_sum))

def return_ytrue_ypre_classification(ground_truth, model_predictions) :
    # Examples of whats passed
    #model prediction : {'classified': {'No Nest': '0.95683'}, 'result': 'success', 'imageMd5': '0acfd6f5b3368d380a67ca9c8d309acd', 'imageUrl': 'http://powerai-vision-portal:9080/powerai-vision-api/uploads/temp/8f80467f-470c-47f3-bf3c-ab7e0880a66b/18c20462-c693-4735-875a-64a30d9974d4.jpg', 'webAPIId': '8f80467f-470c-47f3-bf3c-ab7e0880a66b'}
    #ground_truth     : {'class': 'No Nest', 'id': 'ffbc9c99-201a-4b1a-bce1-a1a1c3ecdc92'}

    # To be compatible with object detection, need to return a list of one item ...
    ytrue = []
    ytrue.append((ground_truth['class']))
    ypred = []
    ypred.append(list(model_predictions.keys())[0])
    return (ytrue, ypred)


def return_ytrue_ypre_objdet(ground_truth, model_predictions) :
    # 1. build a sorted list of labels
    a = ground_truth
    ytrue_labels = [a["label"] for a in ground_truth]
    ypred_labels = [a["label"] for a in model_predictions]

    ytrue_labels = sorted(ytrue_labels)
    ypred_labels = sorted(ypred_labels)
    # 2. smart zipper labels

    ip = 0
    it = 0
    ytrue = []
    ypred = []
    # yaesh
    while( not( it >= len(ytrue_labels) and ip >= len(ypred_labels))) :

        ytl =  "zzzzzzzzz_null" if it >= len(ytrue_labels) else  ytrue_labels[it]
        ypl =  "zzzzzzzzz_null" if ip >= len(ypred_labels) else  ypred_labels[ip]

        if(ytl == ypl) :
            ytrue.append(ytl)
            ypred.append(ypl)
            it += 1
            ip += 1
        elif(ytl != ypl and ytl <= ypl) :
            ytrue.append(ytl)
            ypred.append("null")
            it += 1
        elif(ytl != ypl and ypl < ytl) :
            ytrue.append("null")
            ypred.append(ypl)
            ip += 1

    print("ytrue = {}".format(ytrue))
    print("ypred = {}".format(ypred))
    return (ytrue, ypred)




def fetch_scores(paiv_url, validate_mode="classification", media_mode="video", num_threads=2, frame_limit=50, image_dir="na", video_fn="na", paiv_results_file="fetch_scores.json"):

    # This consumer function yanks Frames off the queue and stores result in json list ...
    def consume_frames(q,result_dict,thread_id):
        fetch_fn = "paiv_{}.jpg".format(thread_id)
        while (q.qsize() > 0):
            print("Thr {} : Size of queue = {}".format(thread_id, q.qsize()))
            (frame_key, frame_np) = q.get()
            print("Thr {} : Frame id = {}".format(thread_id, frame_key))

            json_rv = get_json_from_paiv(paiv_url, frame_np, fetch_fn )
            result_dict[frame_key] = json_rv
            q.task_done()

    q = Queue(maxsize=0)
    result_json_hash = {}
    cap = None

    if(media_mode == "video") :
        frame_limit = int(frame_limit)
        cap  = cv2.VideoCapture(video_fn)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = cap.get(cv2.CAP_PROP_FPS) # fps = video.get(cv2.CAP_PROP_FPS)
        secs = total_frames / fps
        print("Total number of frames  = {} (frames)".format(total_frames))
        print("Frame rate              = {} (fps)".format(fps))
        print("Total seconds for video = {} (s)".format(secs))


        if(frame_limit > total_frames) :
            frame_limit = total_frames
        framecnt = 0 # equals one b/c I read a frame ...
        result_json_hash = [None] * int(frame_limit)


        # load num_threads images into queue with framecnt as index
        # Load Frames into Queue here.. then release the hounds
        # This is a serialized producer ....
        while(framecnt < frame_limit):
            # Load
            for i in range(frame_limit) :
                ret, frame = cap.read()
                q.put((framecnt,frame))
                framecnt += 1

    elif(media_mode == "image") :
        # load in numpy array into Q !!
        if(image_dir == "na") :
            nprint("ERROR : need to specify image_dir=<image directory> in function call")
            return "error"
        nprint("Loading Dataset to prepare for inferencing ")
        paiv_data = _load_paiv_dataset(image_dir, validate_mode)
        #result_json_hash = [None] * len(paiv_data)

        #load the images here!
        idx = 0
        for image_hash_key in paiv_data.keys() :
            image_id = paiv_data[image_hash_key]['id']
            image_file = get_image_fn(image_id)

            npary = cv2.imread(image_file)
            if(npary.any() == None) :
                nprint("Error loading {}.  Unsupported file extension\nexiting ....".format(image_file))
                return 1;

            mykey =get_np_hash(npary)

            q.put((mykey,npary))
            #print(idx)
            idx += 1


    # Setup Consumers.  They will fetch frame json info from api, and stick it in results list
    threads = [None] * num_threads
    for i in range(len(threads)):
        threads[i] = Thread(target=consume_frames, args=(q, result_json_hash, i))
        threads[i].start()

    # Block until all consumers are finished ....
    nprint("Waiting for all consumers to complete ....")
    for i in range(len(threads)):
        threads[i].join()
    #nprint("Total number of frames processed : {} ".format(fram))

    if(media_mode == "video") :
        cap.release()

    nprint("Writing json data to {}".format(paiv_results_file))
    f = open(paiv_results_file, 'w')
    f.write(json.dumps(result_json_hash))
    f.close()



def nprint(mystring) :
    print("{} : {}".format(sys._getframe(1).f_code.co_name,mystring))

def generate_colors(class_names=['a','b','c','d','a1','b1','c1','d1','a2','b2','c2','d2']):
    hsv_tuples = [(x / len(class_names), 1., 1.) for x in range(len(class_names))]
    colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
    colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), colors))
    random.seed(10101)  # Fixed seed for consistent colors across runs.
    random.shuffle(colors)  # Shuffle colors to decorrelate adjacent classes.
    random.seed(None)  # Reset seed to default.
    return colors


def get_json_from_paiv(endpoint, img, temporary_fn ):
    json_rv = None
    if(endpoint != None ) :
        headers = {
            'authorization': "Basic ZXNlbnRpcmVcYdddddddddddddd",
            'cache-control': "no-cache",
        }
        # This code will stay here for reference.  Use this style if loading an image from disk

        cv2.imwrite(temporary_fn, img)
        files_like1 = open(temporary_fn,'rb')
        files1={'files': files_like1}

        # This code attempts to avoids writing the numpy array to disk, and just converts it to a byteIO stream...
        # This code attempts to avoids writing the numpy array to disk, and just converts it to a byteIO stream...

        # file_like = io.BufferedReader(io.BytesIO(img.tobytes()))
        # file_like2 = io.BufferedReader(dvIO(img.tobytes()))
        # files={'files': file_like2 }

        resp = requests.post(url=endpoint, verify=False, files=files1, headers=headers)  # files=files
        json_rv = json.loads(resp.text)

        #print(json.loads(resp.text))
    else :
        json_rv = {'empty_url' : ''}

    nprint("Returning data : {}".format(json_rv))

    return json_rv

def get_boxes_from_json(json_in) :
    '''
    Function to parse boxes in json form and read into a standard box class so that I can manipulate boxes ...
    :param json_in: 
    :return: list of boxes
    '''
    #print(json_in)
    rv_box_list = []

    try :
        box_list = json_in['classified']
        for box in box_list :
            tmpbox = Box(box['label'],box['xmin'],box['ymin'],box['xmax'],box['ymax'],box['confidence'])
            rv_box_list.append(tmpbox)

    except KeyError :
        nprint("No Json available")
    return rv_box_list

# This Function draws a nice looking bounding box ...
def draw_annotated_dot(img, box, color_bgr) :
    cv2.circle(img, box.center(), 6,  color_bgr, thickness=-1, lineType=8, shift=0)
    return img

def draw_annotated_box(img, box, color_bgr, mode="all") :
    cv2.rectangle(img, box.ulc(), box.lrc(), color_bgr, 1 )

    cv2.rectangle(img, box.ulc(yoff=-20), box.urc(), color_bgr, -1 ,)

    cv2.circle(img, box.center(), 6,  color_bgr, thickness=-1, lineType=8, shift=0)

    # Add a better looking font
    # cv2 use bgr, pil uses rgb!
    modified_img = img
    ft = cv2.FONT_HERSHEY_COMPLEX_SMALL
    COLOR_BLACK=(0,0,0)   # Make the text of the labels and the title white

    sz = 0.35
    # Draw Header ...
    txt_y_off = 30
    cv2.putText(img, box.label, box.ulc(yoff=-10,xoff=4), ft, sz, COLOR_BLACK, 1, cv2.LINE_AA)

    return modified_img





# This Function will parse a counter dictionary and draw a nice box in upper left hand corner
def draw_counter_box(img, counter_title, counter_dict, color_dict ) :
    # This is the location on the screen where the ad times will go - if you want to move it to the right increase the AD_START_X
    num_counters = len(counter_dict)
    # Start at (25,25) for ulc, and scale accordingly for counters ....
    box_length = 260
    overlay_box = Box('none', 25,25,25+box_length, 100+num_counters*25,1.0)

    AD_BOX_COLOR=(180,160,160)  # Make the ad timing box grey
    COLOR_WHITE=(255,255,255)   # Make the text of the labels and the title white

    # Make an overlay with the image shaded the way we want it...
    overlay = img.copy()

    # Shade Counter Box
    cv2.rectangle(overlay, overlay_box.ulc(sf=1.0), overlay_box.lrc(sf=1.0), AD_BOX_COLOR, cv2.FILLED)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

    ft = cv2.FONT_HERSHEY_SIMPLEX
    sz = 0.7
    # Draw Header ...
    txt_y_off = 30
    cv2.putText(img, counter_title, overlay_box.ulc(sf=1.0,xoff=10,yoff=txt_y_off), ft, sz, COLOR_WHITE,2,cv2.LINE_AA)

    #Draw Counters
    i=1
    sz = 0.6
    for (k,v ) in sorted(counter_dict.items()):
        col = color_dict[k] if k in color_dict else (255,255,255)
        txt = "{} : {}".format(k, counter_dict[k])
        cv2.putText(img, txt, overlay_box.ulc(sf=1.0,xoff=10,yoff=txt_y_off+25*i), ft, sz, color_dict[k],2,cv2.LINE_AA)
        i += 1

    return img





class Box():
    '''
    data structure to hold box data
    '''
    def __init__(self,label,xmin,ymin,xmax,ymax,confidence):
        self.label = label
        self.xmin = xmin
        self.ymin=ymin
        self.xmax=xmax
        self.ymax = ymax
        self.confidence = confidence

    def center(self) :
        return (int((self.xmin+self.xmax)/2.0),int((self.ymin+self.ymax)/2.0))

    def ul(self):
        return (self.xmin,self.ymin)

    def lr(self):
        return (self.xmax,self.ymax)

    def ur(self):
        return (self.xmax,self.ymin)

    def ll(self):
        return (self.xmin,self.ymax)

    def ulc(self, sf=0.5, xoff=0,yoff=0):
        #scaled upper left box
        cent = self.center()
        ul =  self.ul()
        xulc = int(sf*(ul[0]-cent[0])+cent[0]) + xoff
        yulc = int(sf*(ul[1]-cent[1])+cent[1]) + yoff
        return(xulc,yulc)

    def lrc(self, sf=0.5, xoff=0,yoff=0):
        #scaled upper left box
        cent = self.center()
        lr =  self.lr()
        xlrc = int(sf*(lr[0]-cent[0])+cent[0]) + xoff
        ylrc = int(sf*(lr[1]-cent[1])+cent[1]) + yoff
        return(xlrc,ylrc)

    def urc(self, sf=0.5, xoff=0,yoff=0):
        #scaled upper left box
        cent = self.center()
        ur =  self.ur()
        xurc = int(sf*(ur[0]-cent[0])+cent[0]) + xoff
        yurc = int(sf*(ur[1]-cent[1])+cent[1]) + yoff
        return(xurc,yurc)


    def scale(self,wratio, hratio,offset_px):
        '''
        This function returns 480,640 boxes back to the original image scale
        :param ratio: 
        :param offset_px: 
        :return: a new box, with scale [xy] min/maxes
        '''
        import copy
        newbox = copy.copy(self)
        newbox.xmin = int(newbox.xmin * wratio )
        newbox.xmax = int(newbox.xmax * wratio )
        newbox.ymin = int(newbox.ymin * hratio + offset_px)
        newbox.ymax = int(newbox.ymax * hratio + offset_px)
        return newbox






        # SLOW SLOW SLOW PILLOW IMPLEMENTATION
        #if(mode == "use_pillow") :
        #    cv2_im_rgb = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
        #    pil_im = Image.fromarray(cv2_im_rgb)
        #    draw = ImageDraw.Draw(pil_im)
        #    # use a truetype font
        #    font = ImageFont.truetype("verdanab.ttf", 10)
        #
        #    # Draw the text
        #    color_rgbf = (color_bgr[2],color_bgr[1],color_bgr[0],0)
        #    color_rgbf_black = (0,0,0,0)
        #
        #    draw.text(box.ulc(yoff=-17,xoff=4), box.label, font=font, fill=color_rgbf_black)
        #    #cv2.putText(img,box.label, box.ulc(), font, 0.5, color,1,cv2.LINE_AA)
        #
        #    # Get back the image to OpenCV
        #    modified_img = cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)
        #elif(mode == "all") :