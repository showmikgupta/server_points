import uuid

class Shop:
    def __init__(self, name):
        self.name = name
        self.id = uuid.uuid1()
        self.items = []
