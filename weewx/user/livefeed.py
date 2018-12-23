#==============================================================================
#                    LiveFeed.py
#
# Writes data from the loop into memcache
#
#==============================================================================
import weewx
import weeutil
from weewx.engine import StdService
import weewx.units
import memcache
import json
import datetime
import Queue
import threading
import syslog
from weeutil.weeutil import to_int, to_float, to_bool, timestamp_to_string, accumulateLeaves


"""
Service to write specified fields from the packet loop to memcache as
a JSON document.

4/2/2016 - MB - After several hours looking at how to make the output of this
extension configurable, I decided to hard code the output to deliver a solution
for Hill Head Sailing Club.  


The input is the event.packet, a Python dictionary that looks like this:
	
The output is a JSON document that looks something like this:
    
{"outTemp": {"unit_label": "", "value": "0\u00b0C"}, "timestamp": "2016-04-17T19:22:04.094371", "windDir": {"unit_label": "", "value": "N"},
"pressure": {"unit_label": "mbar", "value": "1053"}, "windSpeed": {"unit_label": "knots", "value": "4"}, "windGust": {"unit_label": "knots", "value": "35"}}




The data elements (which we call observation types), output units and output
format are all configurable.

Internally, the service uses the weewx.units modules, in particular

- weewx.units.getStandardUnitType to determine the unit type and group
  for the input fields
  
- weewx.units.ValueHelper to do the conversions and formatting.

- weewx.units.get_label_string to output the label for the units

for example:
	
	>>> vt = (270, "degree_compass", "group_direction")
	>>> vh = weewx.units.ValueHelper(vt)
	>>> print vh
	270 [degrees]
	>>> print vh.ordinal_compass()
	W

	>>> vt = (68.01, "degree_F", "group_temperature")
	>>> vh = weewx.units.ValueHelper(vt)
	>>> vh.degree_C
	<weewx.units.ValueHelper object at 0xb747cdac>
	>>> print vh.degree_C.nolabel("%0.f")
	20

To output the label for the units, 

********************************************************************************

To use this service, add the following to your configuration file
weewx.conf:
	
The cache_key = the key that this service will use when writing the JSON document to the memcache server
obs_type = list of observation types that the service will include in the JSON document
output_formats = corresponding list of output formats, using the dot format for output described in the WeeWx
	documentation at http://www.weewx.com/docs/customizing.htm#customizing_templates. The first . is not needed.


[MemcacheJson]
  memcache_server = 127.0.0.1:11211
  cache_key = current_weather
  obs_types = windSpeed, windGust,windDir,outTemp,pressure

  
In this example, we are outputing wind speed, wind gust, wind direction, outside
temperature and pressure. We also always output the current date and time as dateTime.





********************************************************************************

To specify that this new service be loaded and run, it must be added to the
configuration option "report_services", located in sub-section [Engine][[Services]].

[Engine]
  [[Services]]
    ...
    process_services = weewx.engine.StdPrint, weewx.engine.StdReport, user.livefeed.MemcacheJson



********************************************************************************
"""

# for examples of python memcache
# http://stackoverflow.com/questions/868690/good-examples-of-python-memcache-memcached-being-used-in-python
#


#
# cheat sheet for memcache via telnet
# http://lzone.de/cheat-sheet/memcached
#
class MemcacheJson(StdService):
    """Service that prints diagnostic information when a LOOP
    or archive packet is received."""
    
    def shutDown(self):
        """Shut down any threads"""
        
        """Function to shut down a thread."""
        if self.loop_queue and self.loop_thread.isAlive():
            # Put a None in the queue to signal the thread to shutdown
            
            self.loop_queue.put(None)
            # Wait up to 20 seconds for the thread to exit:
            self.loop_thread.join(20.0)
            if self.loop_thread.isAlive():
                syslog.syslog(syslog.LOG_ERR, "MemcacheJson: Unable to shut down %s thread" % self.loop_thread.name)
            else:
                syslog.syslog(syslog.LOG_INFO, "MemcacheJson: Shut down %s thread." % self.loop_thread.name)
    
    def __init__(self, engine, config_dict):
        super(MemcacheJson, self).__init__(engine, config_dict)
        self.loop_queue = Queue.Queue()
        self.poster = MemcacheJsonPoster(engine,config_dict,self.loop_queue)
        self.loop_thread = threading.Thread(target=self.poster.run) 
        self.loop_thread.start()
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        
    def new_loop_packet(self, event):
    	  # TO-DO
        # if there is anything on the queue, remove it because we only want to update the 
        # memcache with the latest data. Note that queues are guaranteed thread safe, so this
        # should not cause a problem with the loop thread
        
        self.loop_queue.put(event)
          
		             
        
             
class MemcacheJsonPoster():

    def __init__(self,engine, config_dict,loop_queue):

        self.memcache_server = config_dict['MemcacheJson']['memcache_server']
        self.obs_types = config_dict['MemcacheJson']['obs_types']
        self.cache_key = config_dict['MemcacheJson']['cache_key']
        self.log_success = True
        self.queue = loop_queue
        
		  # figure out what our input units must be. This is a one off, as our input units won't change.
        self.obs_type_input_units = dict([ (obs_type, weewx.units.getStandardUnitType(weewx.US, obs_type)) for obs_type in self.obs_types])
        syslog.syslog(syslog.LOG_INFO,"MemcacheJson: setup obs_type_input_units")
    
    def run(self):
        """If there is a database specified, open the database, then call
        run_loop() with the database.  If no database is specified, simply
        call run_loop()."""
        
        # Open up the archive. Use a 'with' statement. This will automatically
        # close the archive in the case of an exception:
        if self.memcache_server is not None:
            syslog.syslog(syslog.LOG_INFO, "MemcacheJson: Connecting to memcache server %s." % self.memcache_server)
            self.mc = self.createMemcacheConnection()
            if self.mc.set("test_weewx","hello"):
                syslog.syslog(syslog.LOG_INFO, "MemcacheJson: Connected to memcache server %s." % self.memcache_server)
            else:
            	 syslog.syslog(syslog.LOG_INFO, "MemcacheJson: Unable to connect to memcache server %s." % self.memcache_server)
            
            self.run_loop()
        
    def createMemcacheConnection(self):
        return memcache.Client([self.memcache_server],debug=0)    
    
    def run_loop(self):
        """Runs a continuous loop, waiting for records to appear in the queue,
        then processing them.
        """
        # TO-DO - tidy up this double loop
        while True :
            while True:
                # This will block until something appears in the queue:
                _record = self.queue.get()
                # A None record is our signal to exit:
                if _record is None:
                    syslog.syslog(syslog.LOG_INFO, "MemcacheJson: Disconnecting from memcache server %s ." % self.memcache_server)
                    try:
                        self.mc.disconnect_all()
                    finally:
                    	   # whatever happens, we want to return here    
                        return
    
                else:
                    try:
                        # python-memcached error handling is not great - the only way to know that your connection
                        # to memcached has failed is that attempting to set a key returns 0. Otherwise it returns True. It is,
                        # however, very fast. We also seem to get an AttributeError exception if the memcache connection disappears.
                        
                        # So our logic is:
                        # 1. If we have a connection object, process a record and try and set the cache.
                        # 2. If this fails, unset connection and wait for another record to process.
                        # 3. If we don't have a connection, try and create one.
                        #
                        # Although this can result in missing up to two live records, it does mean that
                        # we limit the rate of retrying.
                        
                        
                            if self.mc:
                                success = self.process_record(_record)
                                if not success:
                                    syslog.syslog(syslog.LOG_ERR, "MemcacheJson: Lost connection to memcache server %s ." % self.memcache_server)	
                                    self.mc = None
                            else:
                                self.mc = self.createMemcacheConnection()	
                            
                        # TO-Do - catch a memcache unavailable exception, 
                    except Exception, e:
                            # Some unknown exception occurred. Hopefully this will just occur once after an event, and not on every loop
                            syslog.syslog(syslog.LOG_CRIT, "memcache: Unexpected exception of type %s" % (type(e)))
                
                    
                #else:
                 #   if self.log_success:
                        #_time_str = timestamp_to_string(_record['dateTime'])
                        #syslog.syslog(syslog.LOG_INFO, "restx: %s: Published record %s" % 
                        #          (self.protocol_name, _time_str))
    
    
	    
    
    def process_record(self, event):
        """Write the  LOOP packet to memcache"""
        # we should really put this into a separate thread with a queue to keep it all tidy

        # as of weewx 3.8.2, if there is no reading for an observation type then it doesn't appear in the event packet

        filtered_packet = { obs_type : event.packet[obs_type] for obs_type in self.obs_types if obs_type in event.packet}

        
        # convert our obs value into a tuple of value plus unit. To quote from the comment in weewx.units:
        #	
        #A value-tuple with the value to be converted. The first
        #element is the value (either a scalar or iterable), the second element 
        #the unit type (e.g., "foot", or "inHg") it is in.
        # MB - and the third element is the group
                
        
        
                
        filtered_packet_value_tuples = { 
           obs_type : (filtered_packet[obs_type], 
               self.obs_type_input_units[obs_type][0],
               self.obs_type_input_units[obs_type][1]) 
           for obs_type in filtered_packet.viewkeys()
           }

        
        filtered_output = {}
        filtered_output['timestamp'] = datetime.datetime.now().isoformat()
        for obs_type in filtered_packet.viewkeys():
            value_helper = weewx.units.ValueHelper(filtered_packet_value_tuples[obs_type])
            
            # hard coded conversion and formatting
            if obs_type == 'windSpeed':
            	output_value = value_helper.knot.nolabel("%0.f")
            	unit_label = 'knots'
            elif obs_type == 'windGust':
            	output_value = value_helper.knot.nolabel("%0.f")
            	unit_label = 'knots'
            elif obs_type=='windDir':
               output_value = value_helper.ordinal_compass()
               unit_label = ''
            elif obs_type=='outTemp':
            	output_value = value_helper.degree_C.format("%0.f")
            	unit_label = ''
            elif obs_type=='pressure':
            	output_value = value_helper.mbar.nolabel("%0.f")
            	unit_label = 'mbar'
            else:
            	output_value = str(value_helper)
            observation_output = {
                'value':output_value,
                'unit_label':unit_label
            }
            filtered_output[obs_type] = observation_output
				

        
        json_string = json.dumps(filtered_output)
        return self.mc.set(self.cache_key,json_string)
        
    
   
