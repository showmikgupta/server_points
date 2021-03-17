class UserData:
    def __init__(self, user_id, points, level, xp):
        self.user_id = user_id
        self.points = points
        self.level = level
        self.xp = xp

    def get_user_id(self):
        return self.user_id

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

    def update_points(self, points):
        self.points += points

    def update_level(self, level):
        self.level += level

    def update_xp(self, xp):
        self.xp += xp
