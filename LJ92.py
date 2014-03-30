# Parse lossless JPEG (1992 version)

class lj92(object):
    def __init__(self):
        pass
    def parse(self,data):
        self.data = data
        print "%04x\t"%0
        for cn,c in enumerate(self.data):
            print "%02x"%ord(c),
            if cn%16==0: 
                print
                print "%04x\t"%cn,
        print
