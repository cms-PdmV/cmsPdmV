
class priority:
    def __init__(self):
        self.blocks = {
            1:95000,
            2:90000,
            3:85000,
            4:80000,
            5:70000,
            6:63000
            }
    def priority(self,level):
        if not int(level) in self.blocks:
            return 50000
        else:
            return self.blocks[int(level)]

    
