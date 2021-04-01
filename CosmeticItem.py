from Item import Item

class CosmeticItem(Item):
    def __init__(self, id, name, price, type, description, max_quantity, probability, survivability):
        super().__init__(id, name, price, type, description, max_quantity, probability)
        self.survivability = survivability
