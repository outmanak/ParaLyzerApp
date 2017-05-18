#define CLOCK_PIN                     5                   // clock for switches, PORTD (PD5)
#define SYNC_PIN                      4                   // sync for switches, PORTD (PD4)
#define DATA_OUT_PIN                  7                   // daisy chain output pin, PORTD (PD7)
#define CAMERA_TRIGGER_PIN            3                   // trigger Thorlabs camera, PORTD (PD3)
#define TILTING_PIN                   2                   // trigger for the tilting machine, PORTD (PD2)
#define LED_PIN                       13

#define DIO_LINE_PORT                 PORTB               // all dio lines for HF2 are on PORTB

#define DATA_OUT_HIGH                 {PORTD |= 0x80;}
#define DATA_OUT_LOW                  {PORTD &= 0x7F;}

#define CLOCK_HIGH                    {PORTD |= 0x20;}
#define CLOCK_LOW                     {PORTD &= 0xDF;}
#define CLOCK_TOGGLE                  {((PORTD>>CLOCK_PIN)&1)?(CLOCK_LOW):(CLOCK_HIGH);}
#define CLOCK_TOGGLE_WITH_DELAY(t)    {delayMicroseconds(t);CLOCK_TOGGLE;}
#define CLOCK_HIGH_WITH_DELAY(t)      {CLOCK_HIGH;delayMicroseconds(t);}
#define CLOCK_LOW_WITH_DELAY(t)       {CLOCK_LOW;delayMicroseconds(t);}

#define SYNC_HIGH                     {PORTD |= 0x10;}
#define SYNC_LOW                      {PORTD &= 0xEF;}

#define CAMERA_TRIG_HIGH              {PORTD |= 0x08;}
#define CAMERA_TRIG_LOW               {PORTD &= 0xF7;}
#define IS_CAMERA_TRIGGER_HIGH        ((PORTD>>CAMERA_TRIGGER_PIN)&1)

#define TILTING_HIGH                  {PORTD |= 0x04;}
#define TILTING_LOW                   {PORTD &= 0xFB;}
#define TILTING_TRIGGER_PULSE         {TILTING_HIGH;TILTING_LOW;}

#define LED_ON                        {PORTB |= 0x20;}
#define LED_OFF                       {PORTB &= 0xDF;}
#define LED_TOGGLE                    {((PORTB>>5)&1)?(LED_OFF):(LED_ON);}

#define DEBUG_PRINT(msg)              {if(debugMode){Serial.println(msg);}}

#define SIZE_OF_ARRAY(arr)            (sizeof(arr)/sizeof(arr[0]))

#define MAX_DATA_LENGTH               512     // receive max 255 byte of data, excluding command string and number
#define MAX_OUTPUT_PINS               16
#define MAX_CHAMBERS                  15

#define CHAMBER_BYTE_STREAM_LEN       7
#define DIO_LINE_BYTES                1
#define SWITCH_BYTES                  2
#define INTERVAL_BYTES                4
#define MAX_NUM_SWITCHES              64


/* --- SWITCHING SCHEMES --- */
struct SwitchingScheme {
  unsigned short activeSwitches[2] = {0};     // store active switches as bytes from 0 to 8*num_ICs ... with current PCB (Ketki v4.0) 0..63 switches
  unsigned short hf2DioByte;                  // store 5 bits for DIO lines to HF2, first four bits encode chamber + MSB is electrode pair
  unsigned long chamberInterval;              // store 4 bytes of residence time in us for the chamber, max. 1.19 h, 0 means switch as fast as possible or stay if only one chamber is given
};

/* --- SERIAL INPUT PROCESSING --- */
String inputCommand = "";                 // a string to hold incoming data
String valueString = "";                  // value attached to command
unsigned int inputValue = 0;              // value attached to the command but converted as uint
byte data[MAX_DATA_LENGTH] = {0xff};      // array for bytes to process, set first value to 0xff to recognize data input, e.g. for help
unsigned short byteIdx = 0;
int bitIdx;
short swIdx;
short actSwIdx;

bool commandComplete = false;             // whether the string is complete
bool valueComplete   = false;             // whether the value is complete
bool allComplete     = false;             // whether everything was read from serial port till \n
bool inByteStream    = false;             // ignore special characters in case byte stream is being read
bool lockCommand     = false;             // to lock certain command execution
bool debugMode       = false;             // enable/disable printouts

/* --- OUTPUT SPEED --- */
unsigned int daisyPeriodTimeHalf = 1;     // This results in a 500 kHz clock (2 us period time)

/* --- PIN STUFF --- */
unsigned int dioOutputsToHF2[] = {8, 9, 10, 11, 12};   //, 13, 14, 15, 16, 17, 18, 19, 20};  // output pins for clock, sync, din, tilt, chamberIndex1, chamberIndex2, ..., chamberIndexN
int resetIndex = -1;                      // -1 = no reset pin, otherwise indicates the reset pin that is always pulled up

/* --- THORLABS CAMERA STUFF --- */
unsigned int cameraFrameRate = 20;        // frame rate in ms for the thorlabs camera
unsigned int cameraTrigHigh = 100;        // high time of trigger pulse in us
bool triggerCamera = false;               // should camera be triggered
unsigned long startTimerCamera;
unsigned long stopTimerCamera;
unsigned long cameraTimeFrame = (unsigned long)(1e6/cameraFrameRate);

/* --- DAISYCHAIN AUTO-LOOP --- */
struct SwitchingScheme *userSwitchingScheme = NULL;       // allocate array depending on how many chambers should be switched
unsigned short numSwitchingSchemes = 0;
unsigned int daisyFrameRate = 2000;                       // frame rate in us for the daisychaining
unsigned long startTimerDaisy;
unsigned long stopTimerDaisy;
unsigned long daisyTimeFrame = (unsigned long)(1e6/daisyFrameRate);
unsigned short chamberIdx = 0;

/* --- TILTER STUFF --- */
unsigned int tilterTrigHigh = 100;        // high time of trigger pulse in us
bool tiltPlatform = false;

bool startMeas = false;

/* --- BENCHMARKING --- */
unsigned long startTime = 0;
unsigned long endTime = 0;



// the setup function runs once when you press reset or power the board
void setup() {
  // initialize serial
  // NOTE: make sure it's the same speed given in Python code!
  Serial.begin(115200);

  // might be used without the shield...
//  SPI.begin(); //initialize the SPI protocol

  // define output pins
  pinMode(LED_PIN, OUTPUT);
  pinMode(SYNC_PIN, OUTPUT);
  pinMode(CLOCK_PIN, OUTPUT);
  pinMode(TILTING_PIN, OUTPUT);
  pinMode(DATA_OUT_PIN, OUTPUT);
  pinMode(CAMERA_TRIGGER_PIN, OUTPUT);
  
  for (unsigned short pinIdx = 0; pinIdx < SIZE_OF_ARRAY(dioOutputsToHF2); ++pinIdx) {
    pinMode(dioOutputsToHF2[pinIdx], OUTPUT);
  }
  
  // indicate user correct start
  startBlinkingSequence();
}

void loop() {

  // process received commands
  if (allComplete && !lockCommand) {
    
    // process received command and stop time
    startTime = micros();
    parseCommand();
    endTime = micros();
    
    DEBUG_PRINT("execution time: " + String(endTime - startTime) + " us");
    
    inputCommand = "";
    valueString  = "";
    inputValue   = 0;
    //inByteIdx = 0;
    //data[0] = 0xff;             // use this value to check if there is real input for the next command, e.g. with help
    
    commandComplete = false;
    valueComplete   = false;
    allComplete     = false;
    inByteStream    = false;
  }

  if (startMeas) {
    
    // trigger ThorLabs camera with certain frame rate
    if (triggerCamera && !IS_CAMERA_TRIGGER_HIGH && ( (stopTimerCamera = micros()) - startTimerCamera ) >= cameraTimeFrame) {
      CAMERA_TRIG_HIGH;
      // store time here to get the correct frame rate
      startTimerCamera = stopTimerCamera;
    }
    else if (triggerCamera && IS_CAMERA_TRIGGER_HIGH && ( (stopTimerCamera = micros()) - startTimerCamera ) >= cameraTrigHigh) {
      CAMERA_TRIG_LOW;
    }

    // only select next electrode pair if available and if more than one pair is given
    if (userSwitchingScheme != NULL && numSwitchingSchemes > 1) {
      if ( ((stopTimerDaisy = micros()) - startTimerDaisy ) >= userSwitchingScheme[chamberIdx].chamberInterval) {

        // get next chamber
        ++chamberIdx;

        // reset to zero, if array is smaller
        if (chamberIdx == numSwitchingSchemes) {
          chamberIdx = 0;
        }
        
        writeDaisyChain();
        updateHf2DioLines(userSwitchingScheme[chamberIdx].hf2DioByte);
        startTimerDaisy = stopTimerDaisy;
      }
    }
  }
}

/*
  SerialEvent occurs whenever a new data comes in the
 hardware serial RX.  This routine is run between each
 time loop() runs, so using delay inside loop can delay
 response.  Multiple bytes of data may be available.
 */
void serialEvent() {

  /* NOTE: At the moment parsing takes about 1.4 ms till the daisy chain is written... 
   * in order to switch chambers faster it's better to only send starting command and let Arduino do the work for generating the byte stream
   */
  
  while (Serial.available()) {
    // get the new byte:
    char inChar = (char)Serial.read();

//    Serial.println("inChar: " + String(int(inChar)));

    if (!allComplete) {
      if ( (inChar == ' ' || inChar == '\r') && !inByteStream ) {
        if (!commandComplete && !valueComplete && !allComplete) {
          commandComplete = true;
        }
        else if (!valueComplete && !allComplete) {
          valueComplete = true;
          inByteStream  = true;                       // in case there's more in the pipe set to byte stream
          byteIdx       = 0;                          // reset here in case strange characters come with the stream via pyserial (0xf0)
          inputValue    = valueString.toInt();        // returns 0 in case no proper conversion is possible
        }
        
        // check in case message is complete
        if (!allComplete && inChar == '\r') {
          allComplete = true;
        }
      }
      else {
        // NOTE: for some reason the first message after opening the serial port contains \xf0\xf0 at the beginning
        // so remove it for proper processing afterwards
        if (!commandComplete && isAlpha(inChar)) {
          inputCommand += inChar;
        }
        else if (commandComplete && !valueComplete && isDigit(inChar)) {
          valueString += inChar;      // in case a number > 9 is send use a string to collect and convert after
        }
        // NOTE: also additional words separated by a space after the command end up here... like 'help camera'
        else if (inByteStream) {
          if (byteIdx < inputValue*CHAMBER_BYTE_STREAM_LEN && byteIdx < MAX_DATA_LENGTH) {    // otherwise drop data
            data[byteIdx++] = (byte)inChar;
          }
          else if (byteIdx >= MAX_DATA_LENGTH) {
            Serial.println("ERROR: Max number of data bytes (" + String(MAX_DATA_LENGTH) + ") was reached!");
          }
        }
        
        // check again in case message is complete
        if (!allComplete && inChar == '\r') {
          allComplete = true;
        }
      }
    }
  }
}

void parseCommand() {

  // throw info, if user wants to...
  DEBUG_PRINT("received command: \'" + inputCommand + "\'");

//  // for secure execution
//  lockCommand = true;
    
  // user tries to test serial interface
  // blink 5 times
  if (inputCommand == "test") {
    for (int blinkCnt = 0; blinkCnt < 5; ++blinkCnt) {
      blinkingScheme();
    }
    // throw user info
    Serial.println("Info: Test successfully executed.");
  }

  if (inputCommand == "camera") {
    /* Specify if camera is connected
     * Call 'camera 1' to indicate a camera is connected and needs to be triggered.
     * Call 'camera 0' to virtually unplug the camera (no more trigger pulses will be generated).
     * 
      */
    
    if (valueComplete) {
      if (inputValue) {
        triggerCamera = true;
      }
      else {
        triggerCamera = false;
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
  
  if (inputCommand == "help") {
    // print all available commands
    String helpString = "List of all available commands:\n";
    helpString += " camera x\n";
    helpString += " debug x\n";
    helpString += " getversion\n";
    helpString += " help\n";
//    helpString += " setclockspeed x\n";
    helpString += " setelectrodes n 0x00\n";
    helpString += " setframerate x\n";
    helpString += " start\n";
    helpString += " stop\n";
    helpString += " test\n";
    helpString += " tilt\n";
    helpString += " tilter x\n";
    Serial.println(helpString);
  }

  // debug mode - enable/disable all printouts
  if (inputCommand == "debug") {
    // debug 1 - enable printouts; debug 0 disbale printouts
    
    if (valueComplete) {
      if (inputValue) {
        debugMode = true;
        DEBUG_PRINT("Debug mode ON");
      }
      else {
        DEBUG_PRINT("Debug mode OFF");
        debugMode = false;
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }

  // just throw current version...
  else if (inputCommand == "getversion") {
    Serial.println("Arduino Uno, ArduinoHandler V0.3");
  }
  
  
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
#if 0
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
  
  // in case any problems arise during daisy chaining decrease the clock speed
  else if (inputCommand == "setclockspeed") {
    // "setClockSpeed 10" is setting the clock (of the output data) to 10 microseconds 
    
    if (valueComplete) {
      if (inputValue) {
        daisyPeriodTimeHalf = (unsigned int)(inputValue/2.0);
        
        DEBUG_PRINT("Set clockspeed to " + String(1e3/inputValue) + " kHz (bit length is " + String(inputValue) + " us)");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }

  // toggle reset pin
// NOTE: actually not used with Python script
  else if (inputCommand == "setreset") {
    // "setreset 2" is setting the inverted reset pin (pin which is always held high) to pin number 2. Setting a value of -1 is deactivating any reset pins (hard-wired to pull high)
    
    if (valueComplete) {
      if (inputValue) {
        resetIndex = inputValue;
        
        // execute only for valid pin
        // ignore if we disabled the output (e.g. value of -1)
        pinMode(resetIndex, OUTPUT);
        digitalWrite(resetIndex, HIGH);
        
        DEBUG_PRINT("Set reset pin to " + String(resetIndex) + ".");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
  
  // change number of bits per chunk
  else if (inputCommand == "setbitsperchunk") {
    // "setBitsPerChunk 11" is setting the number of bits read from a bit sequence to 11, i.e.: clock, sync, data, tilt + 7 bits for encoding the chamber index

    // store only valid values
    // limit to 16, no more available on board
    if (valueComplete) {
      if (inputValue > 0 && inputValue < MAX_OUTPUT_PINS) {
        csdtiIndicesCount = inputValue;
        
        DEBUG_PRINT("Set setbitsperchunk to " + String(csdtiIndicesCount) + " bit.");
      }
      else {
        DEBUG_PRINT("ERROR: Given number is invalid.");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }

  // NOTE: does not work with the current reading scheme
 
  else if (inputCommand == "setpins") {

    /* "setpins 9 5,4,7,2,8,9,10,11,12" is setting the following Arduino pins as outputs:
     *  9: how many pins are coming...
     *  5: clock
     *  4: sync
     *  7: data
     *  2: tilt
     *  8-12: identifier pins encoding the currently active recording site (8-12 = 5 bits = 32 sites)
     *  NOTE: pins are send as binary
     *  WARNING: if number of indices > MAX_OUTPUT_PINS, the remaining indices are skipped without warning! -> initialize correct number first by calling setbitsperchunk X
     */
    
    String msg = "";
    
    if (valueComplete) {
      if (inputValue) {
        for (unsigned int pinIdx = 0; pinIdx < inputValue; ++pinIdx) {
          // store pins from data array
          csdtiIndices[pinIdx] = (unsigned int)(data[pinIdx]-48);     // correct for affset in ascii
          // concat message for user
          msg += String(pinIdx) + ":" + String(csdtiIndices[pinIdx]) + ", ";
          // set certain pin as output
          pinMode(csdtiIndices[pinIdx], OUTPUT);
        }
    
        DEBUG_PRINT("Set " + String(inputValue) + " pins as output: " + msg + ".");
      }
      else {
        DEBUG_PRINT("ERROR: Given number of pins is invalid.");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
  
  else if (inputCommand == "processbytes") {
    // 'processbytes 8 ABCDEFGH' tries to interpret 8 bytes individually from the attached string and sends it to output pins -> clk, sync, output
    // NOTE: if no bytes are given the content of the last run will be send again...the buffer is not cleared
    
    // write chain of given bytes to output with sync scheme for data capturing of ADG1414
    if (valueComplete) {
      if (inputValue > 0 && inputValue < MAX_DATA_LENGTH) {
        // switch to given chamber
        writeDaisyChain();
        // tell HF2 what chamber via DIO lines
        writeHf2DioLines(data[0]);
      }
      else {
        DEBUG_PRINT("ERROR: Given number of bytes is invalid.");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
#endif
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------------------------------------------------------
  
  else if (inputCommand == "setelectrodes") {
    /* Define the chambers/electrodes to be selected during one switching scheme started by the command \'start\'.
     * E.g. \'setelectrodes 2 AB10125CD10125\r' will specify two chambers to be stored and can then be selected
     * The last part of the command is interpreted as bytes accordingly:
     *  - 2 bytes active switches
     *  - 1 byte for HF2 DIO line coding
     *  - 4 bytes waiting time in us after the chamber was selected (max. 1.19 h).
     * This scheme of 7 bytes is repeated for each chamber in the list (max. 390 bytes for 15 chambers with two pairs of electrodes).
     * The command 'start' start the selecting scheme and the command 'stop' stops it. 
     * 
     * NOTE: Size of the data capturing array is limited to 512 bytes.
     * NOTE: The 390 bytes are dynamically reserved, which means they should be still available after compiling!!!
     */


    // calc incrementers and offsets for easy counting
    unsigned short inc            = DIO_LINE_BYTES + SWITCH_BYTES + INTERVAL_BYTES;
    unsigned short dioOffset      = SWITCH_BYTES;
    unsigned short intervalOffset = DIO_LINE_BYTES + SWITCH_BYTES;

    unsigned int inDioIdx;
    unsigned int inByteIdx;
    unsigned int inResIdx;

    unsigned long valBuf;

    if (valueComplete) {
      if (inputValue > 0 && inputValue < MAX_DATA_LENGTH/inc) {

//        // stop timer ... otherwise data structure might be messed up
//        startMeas = false;
        
        // check if old data is available, delete it first
        if (userSwitchingScheme != NULL) {
          delete [] userSwitchingScheme;
          userSwitchingScheme = NULL;
          chamberIdx = 0;
          numSwitchingSchemes = 0;
        }
        
        // allocate array with given size for storing bytes accordingly
        userSwitchingScheme = new struct SwitchingScheme[inputValue];
        
        // only proceed if sucessfully allocated
        if (userSwitchingScheme != NULL) {
          
          // update number of electrode pairs, if successful
          numSwitchingSchemes = inputValue;
          
          // store bytes for each chamber setup accordingly
          for (chamberIdx = 0; chamberIdx < numSwitchingSchemes; ++chamberIdx) {

            inByteIdx = chamberIdx*inc;
            inDioIdx  = chamberIdx*inc + dioOffset;
            inResIdx  = chamberIdx*inc + intervalOffset;
            
            // first bytes for the switches
            for (byteIdx = 0; byteIdx < SWITCH_BYTES; ++byteIdx) {
              userSwitchingScheme[chamberIdx].activeSwitches[byteIdx] = (unsigned short)(data[inByteIdx+byteIdx]);
            }
            
            // DIO lines are always stored after the switch bytes
            userSwitchingScheme[chamberIdx].hf2DioByte = data[inDioIdx];

            // make sure nothing strange is in the memory
            userSwitchingScheme[chamberIdx].chamberInterval = 0;
            
            // multiplying with pow is too imprecise
            for (byteIdx = 0; byteIdx < 4; ++byteIdx) {
              valBuf = data[inResIdx+byteIdx];
              
              for (unsigned short shiftIdx = 0; shiftIdx < 3-byteIdx; ++shiftIdx) {
                valBuf = (valBuf << 8);
              }
              userSwitchingScheme[chamberIdx].chamberInterval += valBuf;
            }
          }
          
          // select the first chamber right away
          chamberIdx = 0;
          writeDaisyChain();
          updateHf2DioLines(userSwitchingScheme[chamberIdx].hf2DioByte);
        }
        else {
          Serial.println("ERROR: Could not allocate memory for storing switching scheme!");
        }
      }
      else {
        DEBUG_PRINT("ERROR: Given number of bytes is invalid.");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
  
  else if (inputCommand == "setframerate") {
    // 'setframerate 20' triggers ThorLabs DCC1240C camera 20 times per second
    
    if (valueComplete) {
      if (inputValue) {
        cameraFrameRate = inputValue;
        cameraTimeFrame = 1e6/cameraFrameRate;    // how many microseconds
        
        DEBUG_PRINT("Camera frame rate " + String(cameraFrameRate));
      }
      else {
        DEBUG_PRINT("ERROR: Given number of bytes is invalid.");
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }
  
  else if (inputCommand == "setdio") {
    if (valueComplete) {
      updateHf2DioLines(byte(inputValue));
    }
  }
  
  else if (inputCommand == "start") {
    // Start switching chambers (with camera triggering and/or tilting, depending on the setup).

    startMeas = true;
    
    // start timers...
    startTimerCamera = micros();
    startTimerDaisy  = startTimerCamera;
  }

  else if (inputCommand == "stop") {
    // Stop switching chambers (including camera and tilter triggering).
    startMeas = false;
  }

  else if (inputCommand == "tilt") {
    // execute a single trigger pulse to tilt platform
    if (tiltPlatform) {
      TILTING_TRIGGER_PULSE;
    }
  }

  else if (inputCommand == "tilter") {
    /* Specify if a tilter is connected.
     * Call \'tilter 1\' to indicate a tilter is connected and needs to be triggered.
     * Call \'tilter 0\' to virtually unplug the tilter (no more trigger pulses will be generated).
     */
    
    if (valueComplete) {
      if (inputValue) {
        tiltPlatform = true;
      }
      else {
        tiltPlatform = false;
      }
    }
    else {
      DEBUG_PRINT("ERROR: Number expected after command.");
    }
  }

//  // everything done, release lock
//  lockCommand = false;
}

void writeDaisyChain() {
  // stream received bytes from serial port to data output to change switches
  
  // everything done, release lock
//  bool oldLockState = lockCommand;
//  if (!lockCommand) {
//    lockCommand = true;
//  }

  
  // enable writing to switches
  // no changes on switches during toogling (only acquired with SYNC HIGH)
  SYNC_LOW;
  
  // write payload
  // changed order of writing, cause first byte which goes out will retain in the last switch
  // don't use for-loop it's too slow...
  
  swIdx = MAX_NUM_SWITCHES;
  actSwIdx = userSwitchingScheme[chamberIdx].activeSwitches[1];
  
  // write zeros till switch
  while (--swIdx > actSwIdx) {
    CLOCK_HIGH;
    CLOCK_LOW;
  }
  
  // write one for switch
  // data is captured on falling edge of clock
  CLOCK_HIGH;
  DATA_OUT_HIGH;
  CLOCK_LOW;
  DATA_OUT_LOW;
  // don't forget to increment clock
//  --swIdx;
    
  actSwIdx = userSwitchingScheme[chamberIdx].activeSwitches[0];
  // write zeros till switch
  while (--swIdx > actSwIdx) {
    CLOCK_HIGH;
    CLOCK_LOW;
  }
  
  // write one for switch
  // data is captured on falling edge of clock
  CLOCK_HIGH;
  DATA_OUT_HIGH;
  CLOCK_LOW;
  DATA_OUT_LOW;
  // don't forget to increment clock
//  --swIdx;
  
  // write zeros till switch
  while (--swIdx > -1) {
    CLOCK_HIGH;
    CLOCK_LOW;
  }
  
  // tell all switches to read register content
  SYNC_HIGH;

//  lockCommand = oldLockState;
}

// set dio lines of HF2 according to chamber number as binary
void updateHf2DioLines(byte chamber) {
  DIO_LINE_PORT = chamber & 0x1F;   // mask, only five bits are used
}

// send blink sequence to indicate that correct firmware is running
void startBlinkingSequence()
{
  LED_ON;
  delay(500);
  LED_OFF;
  delay(500);
  LED_ON;
  delay(100);
  LED_OFF;
  delay(100);
  LED_ON;
  delay(500);
  LED_OFF;
}

void blinkingScheme() {
  LED_ON;
  delay(300);
  LED_OFF;
  delay(300);
}

// might be used without the shield
/*
//SPI communication to the switches
void writeSPI(int slavePin, byte command){ 
      SPI.beginTransaction(SPISettings(FREQ, MSBFIRST, SPI_MODE1));
      digitalWrite(slavePin, LOW); //set the sync low
      SPI.transfer(command); //convert the int to a byte
      digitalWrite(slavePin, HIGH);
      SPI.endTransaction();
      delay(1);
}*/
