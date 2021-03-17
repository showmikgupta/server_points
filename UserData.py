class UserData:
    def __init__(self, points, level, xp):
        self.points = points
        self.level = level
        self.xp = xp

    def get_level(self):
        return self.level

    def get_points(self):
        return self.points

    def get_xp(self):
        return self.xp

    def set_points(self, points):
        self.points = points

    def set_level(self, level):
        self.level = level

    def set_xp(self, xp):
        self.xp = xp

