class Inventory:
    def __init__(self, id, capacity):
        self.id = id  # unique identification number that gets assigned to a user
        self.capacity = capacity  # max amount of items that it can hold
        self.size = 0  # current amount of items
        self.inventory = {}  # dictionary of items and their amount
