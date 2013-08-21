'''
Created on 4 Aug 2013

@author: Matthew Bradley


This is a quick and dirty implementation of an application to allow the race team at HillHead to control the race start lights. It is written
in Python using the pyserial module to talk to the EasyDaq USB relay over a serial port, and the Tk widget toolkit to provide the user interface.
The application is single threaded, and uses the Tk event scheduler to queue any asnchronous activity, including managing the serial interface.

Note that pyserial is not part of the standard ActivePython distribution, see pyserial.sourceforge.net. To install pyserial, first install
ActivePython then type the following from the command prompt:

pypm install pyserial

'''
import Tkinter as tk
import tkMessageBox as tkMB
import ttk as ttk
import tkFont
import datetime
import serial
import time
import logging


'''
 Changes

20130804 - MB - Added buttons to test lights on and lights off
20130805 - MB - Turned the relay functions into an encapsulated class that manages the relay card more as a session, with the following
additional functions: (a) check every five seconds that the connection to the serial port is active. If the port is not active,
close the serial port and reopen. (b) automatically delays a write to the serial port if the previous write was within the last
20 milliseconds. This ensures that we don't overwhelm the EasyDAQ card. (c) manages the serial connection. This moves the responsibility
from the Tk App to this object.
20130806 - MB - Added buttons to manually turn lights on and off. If the race sequence goes awry, or some special sequence is required
(e.g. 3,2,1), this allows the race team to control the lights manually. 
20130807 - MB - Changed configuration of minutes to race start to be zero minutes. This allows an immediate start of the light sequence,
for example if the race team forget to start initiate the lights countdown before the start of the race.
20130809 - MB Added a five minute "F flag" StartRaceStep. Changed label to "Minutes to F Flag".
20130818 - MB Added "current step" and "next step" labels with countdown on current step 
'''

# this would be much better as a parameter to the script
comPort = 'COM3'
logging.basicConfig(level=logging.INFO,
    format = "%(levelname)s:%(asctime)-15s %(message)s")


# how much faster we want the steps to go for testing
testSpeedRatio = 1

# constants for lights state
LIGHT_OFF = 0
LIGHT_ON = 1
LIGHT_FLASHING = 2

# constants for serial port session state
DISCONNECTED = 0
RECONNECTING = 1
CONNECTED = 2


class EasyDaqUSBRelay:

    def __init__(self, serialPortName,tkRoot):
        # capture the name of the serial port. On windows, this will be COM3, COM4 etc. The COM port is set
        # when the relay card is first plugged into the PC. You can change it subsequently through the control panel.
        self.serialPortName = serialPortName
        
        #
        # We use the Tkinter event mechanism to schedule activity. You must therefore pass the root object of your Tkinter application
        #
        self.tkRoot = tkRoot
        
        # we use an observer model to enable observers to register for callbacks when the status of the
        # serial port connection changes from connected to not connected
        self.observers = []
        
        #
        # we create our serial port connection now. We don't open the connection until we are asked to connect
        #
        # timeout is set to 0.5 second for reads. 
        self.serialConnection = serial.Serial(timeout=0.5)
        
        # and tell the serial connection which serial port to connect
        self.serialConnection.port = self.serialPortName      
        
        # the baud rate is always 9600
        self.serialConnection.baudrate = 9600
        
        #
        # track whether or not we are enabled. If we are enabled, then we continue to check that have an active connection
        # and if not, we try to open the serial port. We start with not being enabled. As soon as we asked to connect,
        # we are enabled.
        #
        self.isEnabled = False
        
        
        #
        # track the time of the last command. We default to now as the startup time
        #
        self.lastPacketTime = datetime.datetime.now()
        
        #
        # trace the previous relay command. This enables us to resend in the event of a disconnect
        #
        self.currentRelayCommand = None
        self.previousRelayCommand = None
        
        #
        # We track our session status through constants DISCONNECTED,RECONNECTING,CONNECTED
        #
        self.sessionState = DISCONNECTED
            
    def setSessionState(self,state):
        self.sessionState = state
        logging.info("Session state is %s" % self.sessionStateDescription())
        self.notifyObservers()
        
    def beConnected(self):
        self.setSessionState(CONNECTED)
        
    def beNotConnected(self):
        self.setSessionState(DISCONNECTED)
        
    def beReconnecting(self):
        self.setSessionState(RECONNECTING)
        
        
    def sessionStateDescription(self):
        if self.sessionState == CONNECTED:
            return "CONNECTED"
        elif self.sessionState == DISCONNECTED:
            return "Warning: DISCONNECTED"
        elif self.sessionState == RECONNECTING:
            return "Warning: DISCONNECTED ATTEMPTING TO RECONNECT"
        
    def isConnected(self):
        return self.sessionState == CONNECTED
        
    def isDisconnected(self):
        return self.sessionState == DISCONNECTED
        
    def isReconnecting(self):
        return self.sessionState == RECONNECTING
        
    def notifyObservers(self):
        for anObserver in self.observers:
            anObserver.relayStateChanged(self)
    
    def addObserver(self, anObserver):
        '''
        Add an observer to the relay. The callback the method relayStatusChanged
        '''
        self.observers.append(anObserver)
        
    def processedCommand(self):
        '''
        We've processed a command. Capture the current date time.
        '''
        self.lastCommandProcessedTime = datetime.datetime.now()
        
    def maintainSession(self):
        # check the number of milliseconds since the last command.
        # If it is more than 5000 milliseconds
        if self.isConnected():
            logging.debug("Maintaining session")
            
            if (self.timeSinceLastPacket() > 5000):
                try:
                    logging.debug("Time since last packet %i so sending query packet" % self.timeSinceLastPacket())
                    # create a relay packet that requests the EasyDaq to output its status
                    self.currentRelayPacket = 'A' + chr(0)
                    # and queue a request
                    self.queuePacketToEasyDaq()
                    # schedule a read for 500 milliseconds
                    self.tkRoot.after(500,self.readSession)
                    # and schedule to do this again in 5000 milli
                    self.tkRoot.after(5000,self.maintainSession)
                except (serial.SerialException):
                    logging.debug("Exception writing read request to session")
                    self.beNotConnected()
                    self.reconnect()
            # otherwise maintain session when 5000 millis has elapsed
            else:
                self.tkRoot.after(5000-self.timeSinceLastPacket(),self.maintainSession)
                
        
    def readSession(self):
        logging.debug("Reading from session")
        try:
            # read a single byte. This should be our current status but at the moment we don't check for that
            x = self.serialConnection.read()
            logging.debug("Read from session")
            
        except (serial.SerialException, ValueError) as e:
            logging.error("I/O error: {0}".format(e))
            self.serialConnection.close()
            self.beReconnecting()
            self.reconnect()
    
    
    def establishSession(self):
        logging.debug("Establishing session in state: %s" % self.sessionStateDescription() )
        self.sendRelayConfiguration([0,0,0,0,0])
        
        previousState = self.sessionState
        
        # and be connected
        self.beConnected()
        
        if previousState == RECONNECTING:
                
            if self.currentRelayCommand:
                logging.info("Recovering ... sending current relay command: %s" % self.printableCommand(self.currentRelayCommand))
                self.currentRelayPacket = self.currentRelayCommand
                self.queuePacketToEasyDaq()
            elif self.previousRelayCommand:
                logging.info("Recovering ... sending previous relay command: %s" % self.printableCommand(self.previousRelayCommand))
                self.currentRelayPacket = self.previousRelayCommand
                self.queuePacketToEasyDaq()
        self.tkRoot.after(5000,self.maintainSession)
    
    def connect(self):
        # we are sometimes trying to connect when we are already
        # connected
        if not self.isConnected():
            logging.debug("Connecting to serial port")
            self.enabled = True
            try:
                # try to open the serial port
                if self.serialConnection.isOpen():
                    logging.debug("Request to open serial port when already open")
                else:
                    self.serialConnection.open()
                    logging.debug("Connected to serial port")
                # wait for a second and establish the session
                self.tkRoot.after(2000,self.establishSession)
            
            except (serial.SerialException,ValueError) as e:           
                logging.error("I/O error: {0}".format(e))
                self.serialConnection.close()
                self.beReconnecting()
                self.reconnect()
        else:
            logging.debug("Request for connect when already connected")
            
    
    def reconnect(self):
        logging.info("Reconnecting to serial port")
        self.tkRoot.after(5000,self.connect)
        
        
    
    def disconnect(self):
        self.enabled = False
        if self.isConnected:
            self.serialConnection.close()
            self.beNotConnected()
        
    def timeSinceLastPacket(self):
        '''
        calculate the time since the last command
        '''
        deltaSinceLastPacket = datetime.datetime.now() - self.lastPacketTime
        
        return int((deltaSinceLastPacket.microseconds/1000) + deltaSinceLastPacket.seconds*1000)
    
    
    def writePacketToEasyDaq(self):
        # if we are connected, we write our packet
        try:
            logging.debug("Writing to serial port: %s" % self.printableCommand(self.currentRelayPacket))
            self.serialConnection.write(self.currentRelayPacket)
            
            #
            # Not the most elegant, but we check to see if this packet is a command by looking for a C as the first byte of the packet
            #
            if self.currentRelayPacket[0] =='C':
                
                self.previousRelayCommand = self.currentRelayCommand
                self.currentRelayCommand = None

            
            self.lastPacketTime = datetime.datetime.now()
        except (serial.SerialException,ValueError) as e:
            logging.error("I/O error: {0}".format(e))
            self.serialConnection.close()
            self.beReconnecting()
            
            self.reconnect()
    
    def printableCommand(self,relayCommand):
        return relayCommand[0] + "," + str(ord(relayCommand[1]))
    
    def queuePacketToEasyDaq(self):
        '''
        Write a command to EasyDaq. If we have written a command within the last 100 milliseconds,
        then delay by 100 milliseconds, otherwise write the command now.
        '''
        # easy scenario is that we can write the command immediately
        
        
        # if time delta is at least 100 milliseconds
            
        if (self.timeSinceLastPacket() > 100):
            # we can write the command now.
            self.writePacketToEasyDaq()
                
        else:
            # and queue to be written in 100 milliseconds
            logging.debug("Queuing writing packet to easyDaq")
            self.tkRoot.after(100-self.timeSinceLastPacket(), self.writePacketToEasyDaq)

    def sendRelayCommand(self,relayArray):
        # turn the values in the list into a byte where the bit in the byte reflects the position in the list.
        
        commandValue = 0
        
        for i in range(len(relayArray)):
                bitValue = (relayArray[i] *  pow(2,i))
                commandValue = commandValue + bitValue
        
        logging.info("Sending C + %i" % commandValue)
        relayCommand = 'C' + chr(commandValue)
        self.currentRelayCommand = relayCommand
        
        self.currentRelayPacket = relayCommand
        # if we are connected, we queue the packet. If we are not connected,
        # the session recovery will play in the relay packet
        if self.isConnected():
            self.queuePacketToEasyDaq()


        
    def sendRelayConfiguration(self,relayArray):
        # turn the values in the list into a byte where the bit in the byte reflects the position in the list.
        
        commandValue = 0
        
        for i in range(len(relayArray)):
                bitValue = (relayArray[i] *  pow(2,i))
                commandValue = commandValue + bitValue
        
        logging.info("Sending B + %i" % commandValue)        
        self.currentRelayPacket = 'B' + chr(commandValue)
        
        self.queuePacketToEasyDaq()


    
class StartRaceSequence(object):
    def __init__(self):
        self.startRaceSteps = []
        self.raceStartTime = None
        self.isRunning = False
        self.raceStartTime = None
        self.raceFinishCallback = None
        self.observers = []
        
    def notifyObservers(self):
        for anObserver in self.observers:
            anObserver.startRaceSequenceChanged(self)
    
    def addObserver(self, anObserver):
        '''
        Add an observer to the relay. The callback the method relayStatusChanged
        '''
        self.observers.append(anObserver)
        
    def addStartStep(self, aStartStep):
        self.startRaceSteps.append(aStartStep)
        
    def start(self,easyDaqRelay,tkRoot):
        self.isRunning = True
        self.tkRoot = tkRoot
        self.easyDaqRelay = easyDaqRelay
        self.currentStepNumber = 0
        self.startCurrentStep()
        
    def reset(self):
        self.currentStep().stop()
        self.isRunning = False
        self.startRaceSteps = []
        self.notifyObservers()
        
    
    def currentStep(self):
        return self.startRaceSteps[self.currentStepNumber]
        
    def hasNextStep(self):
        return not self.nextStep() == None
        
    def nextStep(self):
        if self.currentStepNumber < (len(self.startRaceSteps)-1):
            return self.startRaceSteps[self.currentStepNumber+1]
        else:
            return None
    
    def startCurrentStep(self):
        self.currentStep().run(self.easyDaqRelay,self.tkRoot)
                    
        # calculate when the step should _finish_. This is the steps
        # toSecondsBefore subtracted from the race start time
        self.currentStepFinishTime = self.raceStartTime - datetime.timedelta(seconds=(self.currentStep().toSecondsBefore/ testSpeedRatio))
        
        # so now we know the duration of the step
        stepDuration = self.currentStepFinishTime - datetime.datetime.now()
        
        logging.info( "Step %i %s duration will be %f" % (self.currentStepNumber, self.currentStep(), stepDuration.total_seconds()))
        
        # and we move onto the next step after the duration of the step
        self.tkRoot.after(int(round(stepDuration.total_seconds()) * 1000), self.moveToNextStep)
        self.notifyObservers()


    def currentStepSecondsRemaining(self):
        timeRemaining =  self.currentStepFinishTime - datetime.datetime.now()
        
        return timeRemaining.seconds
            
    def moveToNextStep(self):
        # stop the current step
        self.currentStep().stop()
        # check that we're running
        if self.isRunning and self.currentStepNumber < len(self.startRaceSteps)-1:
            # increment the step number
            self.currentStepNumber += 1
            # and start the step
            self.startCurrentStep()
        else:
            # turn off all the lights
            # and turn off the lights
        
        
            self.easyDaqRelay.sendRelayCommand(
            [LIGHT_OFF, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF])
            self.isRunning = False
            self.notifyObservers()
            
         
        
class StartRaceStep(object):
    def __init__(self, fromSecondsBefore, toSecondsBefore, lightState, description):
        self.fromSecondsBefore = fromSecondsBefore
        self.toSecondsBefore = toSecondsBefore
        self.lightState = lightState
        self.flashingState = 0
        self.description = description
        
        
    def __str__(self):
        return "%s for %d seconds" % (self.description, (self.fromSecondsBefore - self.toSecondsBefore))
        
    def run(self,easyDaqRelay,tkRoot):
        '''
        run this step
        '''
        self.easyDaqRelay = easyDaqRelay
        self.running = True
        self.tkRoot = tkRoot
        
        if LIGHT_FLASHING in self.lightState:
            self.runWithFlashingLights()
        else:
            self.runWithSteadyLights()
            
    def runWithSteadyLights(self):
        self.easyDaqRelay.sendRelayCommand(self.lightState)
        
    def stop(self):
        self.running = False
        
        
    def runWithFlashingLights(self):
        if self.running:
            # increment our state
            self.flashingState += 1
            
            
            
            # if we are on an even state, 
            if (self.flashingState % 2 == 0):
            
                # this cryptic looking statement creates a copy of the
                # light state list turning LIGHT_FLASHING to LIGHT_ON
                
                lightStateIteration = [LIGHT_ON if light == LIGHT_FLASHING else light for light in self.lightState]
             
            else:
                lightStateIteration = [LIGHT_OFF if light == LIGHT_FLASHING else light for light in self.lightState]
             
            self.easyDaqRelay.sendRelayCommand(lightStateIteration)
            self.tkRoot.after(500,self.runWithFlashingLights)
            

def addFFlagStep(sequence,numberStarts):

    # 
    # We calculate the end time for the F Flag step as five minutes per numberStarts . The start time is five minutes earlier.
    sequence.addStartStep(StartRaceStep(300 + numberStarts*300, 0 + numberStarts*300,[LIGHT_OFF,LIGHT_OFF, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF], "F Flag, 10 minute warning"))
            
def addFiveMinuteStarts(sequence, numberStarts):


    for i in range(numberStarts):
    
        # we need to add on N race worth's of delay,
        # where N is the number of races after this race
        racesAfter = numberStarts - (i+1)
        
        raceDelay = racesAfter * 300
        
        descriptionRaceNumber = i + 1
        
        print sequence
        

        sequence.addStartStep(StartRaceStep(300 + raceDelay,240+ raceDelay,[LIGHT_ON, LIGHT_ON, LIGHT_ON, LIGHT_ON, LIGHT_ON],"Race %d, 5 minute lights" % descriptionRaceNumber))
        sequence.addStartStep(StartRaceStep(240+ raceDelay,180+ raceDelay,[ LIGHT_ON, LIGHT_ON, LIGHT_ON, LIGHT_ON,LIGHT_OFF],"Race %d, 4 minute lights" % descriptionRaceNumber))
        sequence.addStartStep(StartRaceStep(180+ raceDelay,120+ raceDelay,[LIGHT_ON, LIGHT_ON, LIGHT_ON,LIGHT_OFF, LIGHT_OFF ],"Race %d, 3 minute lights" % descriptionRaceNumber))
        sequence.addStartStep(StartRaceStep(120+ raceDelay,60+ raceDelay,[LIGHT_ON, LIGHT_ON, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF ],"Race %d, 2 minute lights" % descriptionRaceNumber))
        sequence.addStartStep(StartRaceStep(60+ raceDelay,30+ raceDelay,[LIGHT_ON,LIGHT_OFF, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF],"Race %d, 1 minute lights" % descriptionRaceNumber))
        sequence.addStartStep(StartRaceStep(30+ raceDelay,0+ raceDelay,[LIGHT_FLASHING,LIGHT_OFF, LIGHT_OFF, LIGHT_OFF, LIGHT_OFF ],"Race %d, 30 seconds lights" % descriptionRaceNumber))
        
class Application(tk.Frame):              
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.easyDayRelay = None
        self.grid()                       
        self.createWidgets()
        self.connectToRelay()
        self.isFFlagStart = True
        self.startRaceSequence = StartRaceSequence()
        self.startRaceSequence.addObserver(self)
        
    
    
    
    def startCountdownOnConfirm(self):
        
        if self.startType.get() == "Flag":
            self.isFFlagStart = True
        else:
            self.isFFlagStart = False
        # build message
        if self.isFFlagStart:
            message = "F flag sequence with %d starts starting in %d minutes" % (self.numberStarts.get(), self.timeToSequenceStart.get())
        else:
            message = "C flag sequence with %d starts starting in %d minutes" % (self.numberStarts.get(), self.timeToSequenceStart.get())
            
        if tkMB.askokcancel("Start Sequence",message ):
            self.startCountdown()
            
    def startCountdown(self):
        self.isFlashing = False
        
        logging.info("Starting race sequence with %d starts " % self.numberStarts.get())
        
   
        # if this is an F Flag Start
        if self.isFFlagStart:
            addFFlagStep(self.startRaceSequence,self.numberStarts.get())
            
        # we always add our five minute starts
        addFiveMinuteStarts(self.startRaceSequence,self.numberStarts.get())
        
        # and schedule the start of the race sequence)
        startDelay = int(round(self.timeToSequenceStart.get() * 60 / testSpeedRatio))
        
        self.startSequenceTime = datetime.datetime.now() + datetime.timedelta(seconds=startDelay)
        
        if self.isFFlagStart:
            startSequenceMinutesDuration = (5*self.numberStarts.get()) + 5
        else:
            startSequenceMinutesDuration = (5*self.numberStarts.get())
        
        self.startRaceSequence.raceStartTime = datetime.datetime.now() + (datetime.timedelta(minutes=startSequenceMinutesDuration)/ testSpeedRatio)+datetime.timedelta(seconds=startDelay)
        

        logging.info("Starting light sequence in %d seconds" % startDelay)
        self.runRaceSequenceTimer = self.after(startDelay*1000,self.runRaceSequence)
        
        # start the countdown
        self.countdownRunning = True
        self.updateCountdown()
        
        # disable the start button#
        self.startButton['state'] = tk.DISABLED
        # enable the reset button
        self.resetSequenceButton['state'] = tk.NORMAL
        
    def updateCountdown(self):
        if self.countdownRunning:
            countdownTimeRemaining = self.startSequenceTime - datetime.datetime.now()
            minutes, seconds = divmod(countdownTimeRemaining.seconds, 60)
            
            self.countdownToFirstLight.set("%02d:%02d" % (minutes,seconds))
            
            self.after(250,self.updateCountdown)
    
    def runRaceSequence(self):
        self.countdownRunning = False
        self.countdownToFirstLight.set("Sequence started")
        self.startRaceSequence.start(self.easyDaqRelay,self)
        
    def connectToRelay(self):
        # create a relay instance
        self.easyDaqRelay = EasyDaqUSBRelay(comPort,self)
        # add ourselves as an observer
        self.easyDaqRelay.addObserver(self)
        # tell it to connect
        self.easyDaqRelay.connect()
            
 

    def lightsOff(self):
        self.isFlashing = False
        self.easyDaqRelay.sendRelayCommand([LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
        


    
    def quitApp(self):
        # when we quit we turn off all the lights
        
        if self.easyDaqRelay.isConnected():
            self.easyDaqRelay.sendRelayCommand([LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
            self.after(1000,self.easyDaqRelay.disconnect)
        # now ask ttk to quit
        self.after(2000,self.quit)
        
    def relayStateChanged(self,easyDaqRelay):
        self.relayStatus.set(easyDaqRelay.sessionStateDescription())
        if easyDaqRelay.isConnected():            
            self.enableLightButtons()
        else:
            
            self.disableLightButtons()
            
    def enableLightButtons(self):
        
        self.lightsOffButton['state'] = tk.NORMAL
        self.flashingOneLightButton['state'] = tk.NORMAL
        self.oneLightButton['state'] = tk.NORMAL
        self.twoLightsButton['state'] = tk.NORMAL
        self.threeLightsButton['state'] = tk.NORMAL
        self.fourLightsButton['state'] = tk.NORMAL
        self.fiveLightsButton['state'] = tk.NORMAL
        self.startButton['state'] = tk.NORMAL

    def disableLightButtons(self):
        
        self.lightsOffButton['state'] = tk.DISABLED
        self.oneLightButton['state'] = tk.DISABLED
        self.twoLightsButton['state'] = tk.DISABLED
        self.threeLightsButton['state'] = tk.DISABLED
        self.fourLightsButton['state'] = tk.DISABLED
        self.fiveLightsButton['state'] = tk.DISABLED
        self.startButton['state'] = tk.DISABLED

    def flashOn(self):
        if self.isFlashing:
            self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
            self.after(500,self.flashOff)
        
    def flashOff(self):
        if self.isFlashing:
            self.easyDaqRelay.sendRelayCommand([LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
            self.after(500,self.flashOn)
    
    
    def flashingOneLight(self):
        self.isFlashing = True
        
        self.flashOn()
    
    def oneLight(self):
        self.isFlashing = False
        
        self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
    
    def twoLights(self):
        self.isFlashing = False
        self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_ON,LIGHT_OFF,LIGHT_OFF,LIGHT_OFF])
    
    def threeLights(self):
        self.isFlashing = False
        self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_ON,LIGHT_ON,LIGHT_OFF,LIGHT_OFF])
    
    def fourLights(self):
        self.isFlashing = False
        
        self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_ON,LIGHT_ON,LIGHT_ON,LIGHT_OFF])
    
    
    def fiveLights(self):
        self.isFlashing = False
        
        self.easyDaqRelay.sendRelayCommand([LIGHT_ON,LIGHT_ON,LIGHT_ON,
            LIGHT_ON,LIGHT_ON])
        
    def resetSequence(self):
        # if we're counting down to the sequence start, cancel the timer
        if self.countdownRunning:
            self.countdownRunning = False
            self.after_cancel(self.runRaceSequenceTimer)
            
            
            
        if self.startRaceSequence.isRunning:
            self.startRaceSequence.reset()
            self.currentStepTimeRemaining.set("Not started")
        
        # either way, set the label back to ..:..
        self.startButton['state'] = tk.NORMAL
        self.resetSequenceButton['state'] = tk.DISABLED
        self.countdownToFirstLight.set("..:..")
    
    def createWidgets(self):
    
        style = ttk.Style()
        style.configure('.', font=('Helvetica',16))
    
        self.startType = tk.StringVar()
        self.startType.set("Flag")
        
        self.fFlagRadioButton = ttk.Radiobutton(self, 
            text='F flag sequence',
            #font=helv18,
            variable = self.startType,
            value = "Flag" )
        self.fFlagRadioButton.grid(row=0,column=0,sticky=tk.W,pady=2)
        
        
        self.classFlagRadioButton = ttk.Radiobutton(self, 
            text='Class flag sequence',
            #font=helv18,
            variable = self.startType,
            value = "Class" )
        self.classFlagRadioButton.grid(row=1,column=0,sticky=tk.W,pady=2)
        
    
        self.label1 = ttk.Label(self, text='Number of starts:')
        self.label1.grid(row=0,column=2,sticky=tk.E,pady=2)
            
        
        self.numberStarts = tk.IntVar()
        self.numberStartsSpinbox = tk.Spinbox(self,
            textvariable=self.numberStarts,
            from_=1,
            to=9,
            width=3)
        
        self.numberStartsSpinbox.grid(row=0,column=3,sticky=tk.W)
        
        
        self.label3 = ttk.Label(self, 
            text='Minutes to sequence start:')
        self.label3.grid(row=1,column=2,sticky=tk.E,pady=2)
        
        self.timeToSequenceStart = tk.IntVar()
        self.timeToSequenceStart.set(1)
        self.timeToSequenceStartSpinbox = tk.Spinbox(self,
            textvariable=self.timeToSequenceStart,
            from_=0,
            to=5,
            width=3)
        
        self.timeToSequenceStartSpinbox.grid(row=1,column=3,sticky=tk.W)
        
        self.label4 = ttk.Label(self,
        text="Countdown to start sequence")
        self.label4.grid(row=4,column=0,columnspan=2,sticky=tk.E,pady=10)
        
        self.countdownToFirstLight = tk.StringVar()
        self.countdownToFirstLight.set("..:..")
        self.countdownToFirstLightLabel = ttk.Label(self,
            textvariable=self.countdownToFirstLight,anchor=tk.W)
        self.countdownToFirstLightLabel.grid(row=4,column=2)

        self.relayStatus = tk.StringVar()
        self.relayStatus.set("Establishing session to lights")
        self.relayStatusLabel = ttk.Label(self, 
            textvariable=self.relayStatus,
            anchor=tk.W)
        self.relayStatusLabel.grid(row=6,column=0)




        self.lightsOffButton = ttk.Button(self, text='Lights off',
            state=tk.DISABLED,
            command=self.lightsOff)
        self.lightsOffButton.grid(row=4,column=5)
        
        
        self.oneLightButton = ttk.Button(self,text='1',
            state=tk.DISABLED,
            command=self.oneLight)
        self.oneLightButton.grid(row=0,column=4)
        
        
        self.flashingOneLightButton = ttk.Button(self,text='1 flashing',
            state=tk.DISABLED,
            command=self.flashingOneLight)
        self.flashingOneLightButton.grid(row=0,column=5)
        
        
        self.twoLightsButton = ttk.Button(self,text='2',
            state=tk.DISABLED,
            command=self.twoLights)
        self.twoLightsButton.grid(row=1,column=4)
        
        self.threeLightsButton = ttk.Button(self,text='3',
            state=tk.DISABLED,
            command=self.threeLights)
        self.threeLightsButton.grid(row=2,column=4)
        
        self.fourLightsButton = ttk.Button(self,text='4',
            state=tk.DISABLED,
            command=self.fourLights)
        self.fourLightsButton.grid(row=3,column=4)
        
        self.fiveLightsButton = ttk.Button(self,text='5',
            state=tk.DISABLED,
            command=self.fiveLights)
        self.fiveLightsButton.grid(row=4,column=4)
        
        
        # the start button is disabled on startup to give the
        # serial port connection time to establish. We enable
        # after 1 second.
        self.startButton = ttk.Button(self, text='Start sequence',
            state=tk.DISABLED,
            command=self.startCountdownOnConfirm)
        self.startButton.grid(row=2,column=0,ipadx=5,ipady=6,padx=2)
        
        self.resetSequenceButton = ttk.Button(self, text='Reset sequence',
            state=tk.DISABLED,
            command=self.resetSequence)
        self.resetSequenceButton.grid(row=3,column=0,ipadx=5,ipady=6,padx=2)
        
        
        self.quitButton = ttk.Button(self, text='Quit',
            command=self.quitApp)            
        self.quitButton.grid(row=7,column=5,ipadx=5,ipady=6,padx=2)      
        
        self.label5 = ttk.Label(self, text='Current step')
        self.label5.grid(row=7, column = 0)
        
        
        self.currentStepDescription = tk.StringVar()
        self.currentStepDescription.set("None")
        self.currentStepDescriptionLabel = ttk.Label(self,
            textvariable = self.currentStepDescription)
        self.currentStepDescriptionLabel.grid(row=7, column =1, columnspan=2)
        
        
        self.currentStepTimeRemaining = tk.StringVar()
        self.currentStepTimeRemaining.set("Not started")
        self.currentStepTimeRemainingLabel = ttk.Label(self,
            textvariable = self.currentStepTimeRemaining)
        self.currentStepTimeRemainingLabel.grid(row=7, column =3, columnspan=1)
        
        
        self.label6 = ttk.Label(self, text='Next step')
        self.label6.grid(row=8, column = 0)
        
        self.nextStepDescription = tk.StringVar()
        self.nextStepDescription.set("None")
        self.nextStepDescriptionLabel = ttk.Label(self,
            textvariable = self.nextStepDescription)
        self.nextStepDescriptionLabel.grid(row=8, column =1, columnspan=2)
        
        
    def updateCurrentStepTimeRemaining(self):
        if self.startRaceSequence.isRunning:
            
            
            minutes, seconds = divmod(self.startRaceSequence.currentStepSecondsRemaining(), 60)
            
            self.currentStepTimeRemaining.set("%02d:%02d" % (minutes,seconds))
            self.after(500,self.updateCurrentStepTimeRemaining)

    def startRaceSequenceChanged(self, startRaceSequence):
        
        if startRaceSequence.isRunning:
            
            self.currentStepDescription.set(str(startRaceSequence.currentStep()))
            self.updateCurrentStepTimeRemaining()
        else:
            self.currentStepDescription.set(str("None"))
            self.startButton["state"] = tk.NORMAL
            self.resetSequenceButton['state'] = tk.DISABLED
            
        if startRaceSequence.isRunning and startRaceSequence.hasNextStep():
            self.nextStepDescription.set(str(startRaceSequence.nextStep()))
        else:
            self.nextStepDescription.set("None")
            
        
        
app = Application()                       
app.master.title('HHSC Race Lights')    
app.mainloop()  