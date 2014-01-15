import time

log = []
log_types = {}
log_active = False
start = None

def PLOG_CONTROL(active):
    global log_active   
    log_active = active
 
def PLOG_TYPE(index,name):
    global log_types
    log_types[index] = name
    return index

def PLOG(event_type,event_info):
    global log,log_active,start
    if not log_active:
        return
    now = time.time()
    if start == None:
        start = now
    log.append((now,event_type,event_info))

def PLOG_PRINT():
    global log,log_types,start
    for etime,etype,einfo in log:
        print "%02.03f:%s:%s"%(etime-start,log_types[etype],einfo)

