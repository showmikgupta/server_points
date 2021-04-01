from Item import Item

class BottleItem(Item):
    def __init__(self, id, name, price, type, description, max_quantity, probability, message, object):
        super().__init__(id, name, price, type, description, max_quantity, probability)
        self.message = message
        self.object = object
