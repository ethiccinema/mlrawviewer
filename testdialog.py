import multiprocessing
import multiprocessing.queues
from multiprocessing import Process

def dialog_main(queue):
    import dialogs
    ret = dialogs.okToExit()
    queue.put(ret)

def output_main(queue,initial):
    import dialogs
    ret = dialogs.chooseOutputDir(initial)
    queue.put(ret)

def open_main(queue,initial,fileTypes):
    import dialogs
    ret = dialogs.openFilename(initial,fileTypes)
    queue.put(ret)

if __name__ == '__main__':
    queue = multiprocessing.queues.SimpleQueue()
    p = Process(target=open_main, args=(queue,"/var/",[('MLV',('*.MLV','*.mlv'))]))
    p.start()
    result = queue.get()
    print "Result:",result
    p.join()



