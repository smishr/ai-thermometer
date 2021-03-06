from threading import Thread
import time, os
import numpy as np
import cv2

def imx219_pipeline(
    capture_width=3264,
    capture_height=2464,
    display_width=1024,
    display_height=768,
    framerate=10,
    flip_method=2,
):
    return (
        "nvarguscamerasrc ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! "
        "appsink max-buffers=1 drop=true"
        % (
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )

def make_vis_stream(display_width=1088, display_height=816):

    pipeline = imx219_pipeline(
        capture_width=3264,
        capture_height=2464,
        display_width=display_width,
        display_height=display_height,
        framerate=21,
        flip_method=2,
    )
    
    return cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)


class GPUThread(Thread):

    def __init__(self, stream=None, frame_size=(1088, 816)):

        super(GPUThread, self).__init__()

        parent_dir_pth = os.path.dirname(os.path.abspath(__file__)) 
        prototxt_file_pth = parent_dir_pth + "/caffe/deploy.prototxt.txt"
        caffe_model_pth = parent_dir_pth + "/caffe/res10_300x300_ssd_iter_140000.caffemodel"

        if stream is None:
            stream = make_vis_stream(*frame_size)

        self._net = cv2.dnn.readNetFromCaffe(prototxt_file_pth, caffe_model_pth)

        if hasattr(cv2.dnn, 'DNN_BACKEND_CUDA'):
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        else:
            print("cv2.dnn.DNN_BACKEND_CUDA not available!")
            
        self._stream = stream
        self._delay = -1
        self._detections = None
        self._running = True
        self._frame = None

    def run(self):

        while self._running:
            loop_start = time.monotonic()
            ret, self._frame = self._stream.read()
            # ret, _frame = self._stream.retrieve()
            if ret is False:
                print("WARN: no frame")
                time.sleep(1)
                continue

            # detect
            blob = cv2.dnn.blobFromImage(
                cv2.resize(self._frame, (300, 300)),
                1.0,
                (300, 300),
                (104.0, 177.0, 123.0)
                )
            self._net.setInput(blob)
            detections = self._net.forward()

            self._detections = np.squeeze(detections)
            self._delay = 1000*(time.monotonic()-loop_start)
        
        print("releasing")
        self._stream.release()


    def get_faces(self):
        """
        :ret list of x,y positions of faces in image _frame:
        """

        return self._detections

    def stop(self):
        self._running = False

    @property
    def frame(self):
        return self._frame

    @property
    def detections(self):
        return self._detections
        
