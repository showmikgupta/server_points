from EdibleItem import EdibleItem


class DrinkItem(EdibleItem):
    def __init__(self, id, name, price, type, description, max_quantity, probability, energy, is_alcohol):
        super().__init__(id, name, price, type, description, max_quantity, probability, energy)
        self.is_alcohol = is_alcohol
