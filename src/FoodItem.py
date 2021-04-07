from EdibleItem import EdibleItem

class FoodItem(EdibleItem):
    def __init__(self, id, name, price, type, description, max_quantity, probability, energy):
        super().__init__(id, name, price, type, description, max_quantity, probability, energy)
