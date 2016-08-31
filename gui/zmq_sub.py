# Licensed under a 3-clause BSD style license - see LICENSE.rst
import zmq
from threading import Thread
from pickle import loads
from PyQt4 import QtCore
from PyQt4.QtGui import QLabel
from time import time
from ctapipe.core import Component

class ZmqSub(Thread, QtCore.QObject):

    """
    Manages communication with pipeline thanks to ZMQ SUB message
    Transmit information to GUI when pipeline change
    Parameters
    ----------
    pipegui : Pipelinegui
        Widget that draws pipeline by receiving information from this instance
    gui_port : str
        port to connect for ZMQ communication
    statusBar :  QtGui.QStatusBar
        MainWindow status bar to display information
    """
    message = QtCore.pyqtSignal(list)
    def __init__(self, pipegui=None, table_queue=None, gui_port=None, statusBar=None):
        Thread.__init__(self)
        QtCore.QObject.__init__(self)
        if gui_port is not None:
            self.context = zmq.Context()
            # Socket to talk to pipeline kernel and pipeline steps and router
            self.socket = self.context.socket(zmq.SUB)
            gui_adress = "tcp://*:" + str(gui_port)
            try:
                self.socket.bind(gui_adress)
            except zmq.error.ZMQError as e:
                print("ERROR: ".format(str(e), gui_adress))
            # Inform about connection in statusBar
            if statusBar is not None:
                self.statusBar = statusBar
                self.statusBar.insertPermanentWidget(0,QLabel("binded to " + gui_adress))
            # Register socket in a poll and register topics
            self.poll = zmq.Poller()
            self.poll.register(self.socket, zmq.POLLIN)
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'GUI_GRAPH')
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'GUI_STAGER_CHANGE')
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'GUI_CONSUMER_CHANGE')
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'GUI_PRODUCER_CHANGE')
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'GUI_ROUTER_CHANGE')
            self.socket.setsockopt_string(zmq.SUBSCRIBE, 'FINISH')
            # self,stop flag is set by ficnish method to stop this thread
            # properly when GUI is closed
            # self.pipegui will receive new pipeline information
            self.stop = False
            self.pipegui = pipegui
            self.table_queue = table_queue
            self.steps = list()
            self.config_time = 0
            self.last_send_config = 0
            self.nb_job_done=dict()
        else:
            self.stop = True

    def run(self):
        """
        Method representing the thread’s activity.
        """
        while not self.stop:
            conf_time = time()
            sockets = dict(self.poll.poll(1000))  # Poll or time out (1000ms)
            if self.socket in sockets and sockets[self.socket] == zmq.POLLIN:
                # receive a new message form pipeline
                receive = self.socket.recv_multipart()
                topic = receive[0]
                msg = loads(receive[1])
                if topic == b'FINISH':
                    self.reset()
                else:
                    self.update_full_state(topic,msg)
                    if (conf_time - self.last_send_config) >= 0.0416: # 24 images /sec
                        # inform pipegui
                        self.message.emit(self.steps)

                        self.last_send_config = conf_time
            else:
                if self.steps:
                    self.message.emit(self.steps)
                    self.last_send_config = conf_time

    def reset(self):
        """
        Clear the self.steps list
        """
        self.steps.clear()

    def update_full_state(self,topic,msg):
        """
        Redirect topic and message depending on topic
        Parameters:
        -----------
        topic : bytes
            define why message has been send
        msg: a Pickel dumps message
        """

        if topic == b'GUI_GRAPH':
            config_time, receiv_steps = msg
            if config_time != self.config_time:
                self.full_change(receiv_steps)
                self.config_time = config_time
        # Stager or Producer or Consumer state changes

        elif self.steps and (topic == b'GUI_STAGER_CHANGE' or
                           topic == b'GUI_CONSUMER_CHANGE' or
                           topic == b'GUI_PRODUCER_CHANGE'):
            self.step_change(msg)
        elif topic == b'GUI_ROUTER_CHANGE':
            self.router_change(msg)


    def full_change(self,receiv_steps):
        """
        Update self.steps with new receiv_steps
        Test if receiv_steps is same as self.steps.
        If yes do nothing otherwise set self.steps to receiv_steps
        Parameters:
        -----------
        receiv_steps: list of StagerRep
        """
        if not self.steps:
            self.steps = receiv_steps
        else:
            nb_corresponding_step = 0
            for new_step in receiv_steps:
                for step in self.steps:
                    if step.name == new_step.name:
                        step.nb_job_done = new_step.nb_job_done
                        nb_corresponding_step+=1
                        break
            if  nb_corresponding_step != len(self.steps):
                # in case of pipeline configuration change and GUI
                # is not restarted
                self.steps = receiv_steps

    def step_change(self, msg):
        """Find which pipeline step has changed, and update its corresponding
        StagerRep
        Parameters
        ----------
        msg: list
            contains step name, step running flag and step nb_job_done
            receiv_steps: list of GUIStepInfo describing pipeline contents
        """
        name, running , nb_job_done = msg
        for step in self.steps:
            if step.name == name.split('$$processus')[0]:
                step.running = running
                return

    def router_change(self, msg):
        """Called by ZmqSub instance when it receives zmq message from pipeline
        Update pipeline state (self.steps) and force to update drawing
        Parameters
        ----------
        msg : a Pickle.dumps message
        """
        name, queue = msg
        name = name.split('_router')[0]
        step = self.get_step_by_name(name)
        if step:
            step.queue_length = queue

    def get_step_by_name(self, name):
        ''' Find a PipeStep in self.producer_step or  self.stager_steps or
        self.consumer_step
        Return: PipeStep if found, otherwise None
        '''
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def finish(self):
        self.stop = True
